#!/bin/sh
set -eu

mkdir -p /tmp/nginx-proxy-temp /tmp/nginx-client-temp /tmp/nginx-fastcgi-temp /tmp/nginx-uwsgi-temp /tmp/nginx-scgi-temp

streamlit run app.py --server.port=8502 --server.address=127.0.0.1 &
streamlit_pid=$!

cleanup() {
    kill "$streamlit_pid" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

nginx -c /app/nginx.conf -g 'daemon off;'
