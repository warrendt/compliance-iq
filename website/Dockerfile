# ComplianceIQ marketing website — static site served by nginx.
# No build step: plain HTML/CSS/JS copied into the image.
FROM nginx:alpine

# Site config (listens on :8080).
COPY nginx.conf /etc/nginx/nginx.conf

# Static assets.
COPY index.html platform.html frameworks.html styles.css main.js config.js /usr/share/nginx/html/
COPY assets/ /usr/share/nginx/html/assets/

# Inject the app URL at container start from COMPLIANCEIQ_APP_URL (if set).
# nginx:alpine runs every /docker-entrypoint.d/*.sh before starting nginx.
COPY docker-entrypoint.d/10-app-url.sh /docker-entrypoint.d/10-app-url.sh
RUN chmod +x /docker-entrypoint.d/10-app-url.sh

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
