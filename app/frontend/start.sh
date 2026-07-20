#!/bin/sh
set -eu

mkdir -p /tmp/nginx-proxy-temp /tmp/nginx-client-temp /tmp/nginx-fastcgi-temp /tmp/nginx-uwsgi-temp /tmp/nginx-scgi-temp

# ---------------------------------------------------------------------------
# Render nginx config from the template.
#
# The committed /app/nginx.conf carries an `/api/` reverse-proxy block with
# __PLACEHOLDER__ tokens. We resolve those from BACKEND_URL at container start
# (the backend FQDN is only known at deploy time) and write the result to
# /tmp/nginx.conf. When BACKEND_URL is unset (e.g. a Streamlit-only local run)
# the whole block is removed so nginx still starts cleanly.
# ---------------------------------------------------------------------------
render_nginx_conf() {
    src=/app/nginx.conf
    dst=/tmp/nginx.conf

    if [ -n "${BACKEND_URL:-}" ]; then
        backend_url=$(printf '%s' "$BACKEND_URL" | sed 's:/*$::')   # strip trailing /
        # host[:port] with the scheme removed, for the upstream Host header.
        backend_host=$(printf '%s' "$backend_url" | sed -E 's#^[a-zA-Z]+://##')
        # First nameserver from the container's resolver (Azure DNS in ACA).
        dns_resolver=$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf 2>/dev/null || true)
        [ -n "$dns_resolver" ] || dns_resolver=168.63.129.16

        sed \
            -e "s#__BACKEND_URL__#${backend_url}#g" \
            -e "s#__BACKEND_HOST__#${backend_host}#g" \
            -e "s#__DNS_RESOLVER__#${dns_resolver}#g" \
            "$src" > "$dst"
        echo "[start.sh] /api proxy -> ${backend_url} (resolver ${dns_resolver})"
    else
        # Drop the API proxy block entirely when no backend is configured.
        sed '/# __API_PROXY_START__/,/# __API_PROXY_END__/d' "$src" > "$dst"
        echo "[start.sh] BACKEND_URL unset; /api proxy disabled"
    fi
}

render_nginx_conf

# Supervise Streamlit: nginx (foreground) proxies to 127.0.0.1:8502, so if the
# Streamlit process ever exits nginx would otherwise serve 502s forever. This
# loop relaunches Streamlit within ~1s of any exit, making the frontend
# self-heal instead of getting stuck behind a permanent "Connection error".
streamlit_pidfile=/tmp/streamlit.pid

streamlit_supervisor() {
    while true; do
        echo "[start.sh] launching Streamlit on 127.0.0.1:8502"
        streamlit run app.py --server.port=8502 --server.address=127.0.0.1 &
        child=$!
        echo "$child" > "$streamlit_pidfile"
        wait "$child" || true
        echo "[start.sh] Streamlit exited; restarting in 1s" >&2
        sleep 1
    done
}

streamlit_supervisor &
supervisor_pid=$!

cleanup() {
    kill "$supervisor_pid" 2>/dev/null || true
    [ -f "$streamlit_pidfile" ] && kill "$(cat "$streamlit_pidfile")" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

nginx -c /tmp/nginx.conf -g 'daemon off;'
