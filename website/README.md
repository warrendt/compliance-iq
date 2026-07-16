# ComplianceIQ — Marketing Website

A standalone public marketing/landing site for **ComplianceIQ**. Hand-crafted
HTML + CSS + a little vanilla JS, served as static files by nginx. **No
framework, no Tailwind, zero build step.**

> This site is a **separate deliverable** from the ComplianceIQ application. It
> runs in its **own container** and is **not** part of the app's azd
> Infrastructure-as-Code. Nothing here touches `azure.yaml`, `app/`, or any
> Bicep/ARM.

---

## Structure

```
website/
├── index.html            # Home: hero + pipeline, 7 frameworks, how-it-works
├── platform.html         # Platform: architecture + Azure infrastructure
├── frameworks.html       # Frameworks: the 7 supported standards + deployment
├── styles.css            # All styling (palette matches the app sign-in card)
├── main.js               # Link wiring (app + GitHub) + mobile nav + footer year
├── config.js             # COMPLIANCEIQ_APP_URL + COMPLIANCEIQ_REPO_URL
├── assets/
│   ├── logo-full.png       # Full-colour lockup — Open Graph / social image
│   ├── logo-icon.png       # Colour shield mark — favicon source
│   ├── logo-icon-white.png # White shield mark — nav + footer (on navy)
│   ├── logo-white.png      # White knockout of full lockup (available for dark bg)
│   ├── favicon.ico / favicon-32.png / favicon-48.png
│   ├── apple-touch-icon.png
│   └── icon-192.png        # PWA / share icon
├── Dockerfile            # nginx:alpine, static
├── nginx.conf            # Listens on :8080, gzip, security headers, /healthz
├── docker-entrypoint.d/
│   └── 10-app-url.sh      # Injects COMPLIANCEIQ_APP_URL into config.js at start
├── .dockerignore
└── README.md
```

## Pages & navigation

| Nav item        | Target                                        | Wiring                     |
| --------------- | --------------------------------------------- | -------------------------- |
| Platform        | `platform.html` (architecture)                | static link               |
| Frameworks      | `frameworks.html` (the 7 supported standards) | static link               |
| Resources       | GitHub repository                             | `[data-repo-link]`        |
| Sign in         | deployed app root (Entra sign-in)             | `[data-app-link]`         |
| Get started     | `app/DEPLOYMENT.md` in the repo               | `[data-repo-deploy]`      |
| Start / Review mapping | deployed app root                      | `[data-app-link]`         |

Every link has a real `href` in the HTML (works with JS disabled); `main.js`
then overrides the app/GitHub links from `config.js` so both destinations are
configurable in one place.

## Run locally

Any static server works. Two options:

```bash
# 1) Plain Python (from the website/ folder)
python3 -m http.server 8088
#   → http://localhost:8088

# 2) Docker (matches production)
docker build -t complianceiq-site website/
docker run --rm -p 8088:8080 complianceiq-site
#   → http://localhost:8088   (health: http://localhost:8088/healthz)
```

## Links: app URL and GitHub repo

CTAs point at **two** configurable destinations, both set in `config.js`:

- **`COMPLIANCEIQ_APP_URL`** — the deployed app root. Powers **Sign in**, **Start
  mapping**, and **Review mapping**. The repo commits only a **placeholder**
  (`https://app.example.com`); when set, these CTAs land on the app, which then
  shows the branded Entra sign-in card.
- **`COMPLIANCEIQ_REPO_URL`** — the public GitHub repository. Powers **Resources**
  (repo root) and **Get started** (→ `app/DEPLOYMENT.md`). Safe to commit; it is
  public.

`main.js` reads both and wires `[data-app-link]`, `[data-repo-link]`, and
`[data-repo-deploy]` accordingly.

Set the real **app** URL at deploy time **without rebuilding** — the entrypoint
rewrites `config.js` from an environment variable:

```bash
docker run --rm -p 8088:8080 \
  -e COMPLIANCEIQ_APP_URL="https://your-app-host.example" \
  complianceiq-site
```

Or, for a static host, edit the one line in `config.js` before publishing.

> **Public repo rule:** never commit the real deployed app hostname or any
> environment-specific identifier. Keep `COMPLIANCEIQ_APP_URL` on the placeholder.

## Deploy

The image is a plain static nginx container (listens on `:8080`, exposes
`/healthz`). Deploy it wherever you host containers, then set
`COMPLIANCEIQ_APP_URL`. Point your custom domain's DNS (A/CNAME) at the host and
terminate TLS at your load balancer / ingress. This container serves plain HTTP
on `:8080` and is TLS-agnostic by design.

## Design

Palette and shapes mirror the app's Phase-1 sign-in card: navy backgrounds
(`#0d2036` / `#10243e` / `#081524`), primary blue `#0F6CBD`, lighter accent
`#2f8fe0`, white cards, rounded corners, soft shadows. The hero pipeline diagram
is rebuilt in HTML/CSS/SVG (not a screenshot) so it stays crisp and responsive.

## Accessibility

Semantic landmarks, a skip link, keyboard-focusable CTAs with visible focus
rings, `alt`/`aria` on imagery and the diagram, an accessible mobile nav toggle
(`aria-expanded`, Escape + outside-click to close), and
`prefers-reduced-motion` support.

## Verify

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8088              # 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8088/platform.html    # 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8088/frameworks.html  # 200
curl -s http://localhost:8088 | grep "deployable cloud controls" # hero copy
curl -s http://localhost:8088/healthz                            # ok
```
