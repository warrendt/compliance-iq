#!/bin/sh
set -eu

mkdir -p /tmp/nginx-proxy-temp /tmp/nginx-client-temp /tmp/nginx-fastcgi-temp /tmp/nginx-uwsgi-temp /tmp/nginx-scgi-temp

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

nginx -c /app/nginx.conf -g 'daemon off;'
