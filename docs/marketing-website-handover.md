# Handover — ComplianceIQ Marketing Website

**Branch:** `warrendt-marketing-website` · **Scope:** new top-level `website/`
folder only. Nothing under `app/`, `azure.yaml`, or `app/infra/**` was touched.

## What was built

A standalone, static marketing/landing site for ComplianceIQ, faithfully
reproducing the supplied homepage mockup. Hand-written HTML/CSS/vanilla JS,
served by `nginx:alpine`. Zero build step, no framework.

Sections: sticky navy nav (logo + Platform/Frameworks/Resources + Sign in +
Get started) · hero (headline with blue accent, sub, two CTAs) · rebuilt
HTML/CSS/SVG **pipeline diagram** (Source control → AI mapping → Azure Policy /
Defender guidance → Review, 92% confidence) · trust bar (Government · Healthcare
· Financial Services) · **7 Supported Frameworks** badges · **How it works**
(3-card flow + Govern/Map/Enforce/Report stepper) · navy footer.

## Why these choices

- **No build step / vanilla stack** — Warren's decision; keeps the deliverable
  trivial to host and audit.
- **Pipeline & how-it-works rebuilt in HTML/CSS/SVG**, not screenshots — crisp
  at any width and responsive.
- **Single app-URL indirection** (`config.js` → `window.COMPLIANCEIQ_APP_URL`)
  so no environment-specific hostname is committed to this public repo. The
  container entrypoint can override it from an env var at deploy time.

## Architecture

```mermaid
flowchart LR
    subgraph Browser
      HTML[index.html] --> CSS[styles.css]
      HTML --> CFG[config.js<br/>COMPLIANCEIQ_APP_URL]
      HTML --> JS[main.js]
      JS -->|wires [data-app-link]| CTA[CTAs → app root]
    end
    subgraph Container["nginx:alpine (:8080)"]
      ENTRY[10-app-url.sh] -->|rewrites at start| CFG
      NGINX[nginx.conf] --> HTML
    end
    ENV[[COMPLIANCEIQ_APP_URL env]] -.optional.-> ENTRY
    CTA -->|when set| APP[ComplianceIQ app<br/>branded Entra sign-in]
```

## App-URL config (critical)

| Where | Value |
| --- | --- |
| Committed `config.js` | `https://app.example.com` (placeholder only) |
| Deploy override | `-e COMPLIANCEIQ_APP_URL=…` → entrypoint rewrites `config.js` |
| Static host | edit the single line in `config.js` before publishing |

## How to verify

```bash
docker build -t complianceiq-site website/
docker run --rm -p 8088:8080 complianceiq-site
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8088   # 200
curl -s http://localhost:8088 | grep "deployable cloud controls"
```

Verified this session: image builds, container returns HTTP 200, `/healthz`
returns `ok`, hero copy present, entrypoint logs placeholder fallback. Headless
Playwright screenshots (desktop 1440px + mobile 390px, incl. open mobile menu)
match the mockup aesthetic.

## Assets

`logo-full.png` is the trimmed, transparent brand lockup (derived from the
supplied `logo-full.jpg` source with PIL). Other variants: `logo-icon.png`
(colour shield, favicon source), `logo-icon-white.png` (white shield, used in
nav + footer on navy), `logo-white.png` (white knockout of the full lockup),
plus a favicon set (`favicon.ico`, `favicon-32/48.png`, `apple-touch-icon.png`,
`icon-192.png`). The nav/footer wordmark is live text for crispness; the white
shield sits beside it on the navy background.

## Not done / caveats

- **TLS & custom domain** are host concerns — the container serves plain HTTP on
  `:8080`; terminate TLS at the ingress/LB and point DNS at the host.
- Nav dropdown carets are shown but **anchor to on-page sections** (v1 scope);
  no mega-menus.
- Framework "logos" are typographic monogram badges (NIST/CIS/ISO/FedRAMP/
  HIPAA/GDPR), not official trademark artwork — avoids shipping third-party
  marks. Swap for licensed SVGs later if desired.
- No automated tests: this is a static HTML/CSS/JS site with no test harness in
  the stack. Verification is the Docker build + curl + Playwright screenshots
  above.
