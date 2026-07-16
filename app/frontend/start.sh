#!/bin/sh
set -u

mkdir -p /tmp/nginx-proxy-temp /tmp/nginx-client-temp /tmp/nginx-fastcgi-temp /tmp/nginx-uwsgi-temp /tmp/nginx-scgi-temp

# Supervise Streamlit. nginx runs in the foreground as PID 1, so if the
# Streamlit process ever exits the container would otherwise stay "healthy"
# (nginx alive) while every request proxied to 127.0.0.1:8502 returns 502/404
# indefinitely, recoverable only by a manual redeploy. Restarting Streamlit
# whenever it exits keeps the app self-healing: users see a brief reconnect
# instead of a permanently wedged container.
run_streamlit() {
    while true; do
        echo "[start.sh] starting Streamlit on 127.0.0.1:8502"
        streamlit run app.py --server.port=8502 --server.address=127.0.0.1
        status=$?
        echo "[start.sh] Streamlit exited (status $status); restarting in 2s" >&2
        sleep 2
    done
}

run_streamlit &
streamlit_supervisor_pid=$!

cleanup() {
    kill "$streamlit_supervisor_pid" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

nginx -c /app/nginx.conf -g 'daemon off;'
