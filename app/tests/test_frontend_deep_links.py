"""Regression tests for reverse-proxied Streamlit deep links."""

from pathlib import Path


NGINX_CONFIG = Path(__file__).resolve().parents[1] / "frontend" / "nginx.conf"


def test_deep_link_streamlit_discovery_falls_back_to_root_endpoints():
    config = NGINX_CONFIG.read_text()

    assert "location ~ ^/.+/_stcore/(health|host-config)$" in config
    assert "return 404;" in config
    assert "location ~ ^/.+/_stcore/(.*)$" in config
    assert "proxy_pass http://streamlit_upstream/_stcore/$1$is_args$args;" in config
    assert "location ~ ^/.+/(static/.*)$" in config
    assert "proxy_pass http://streamlit_upstream/$1$is_args$args;" in config
