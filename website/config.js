/*
 * ComplianceIQ marketing site — runtime configuration.
 *
 * Two knobs drive every off-site link:
 *
 *  1. COMPLIANCEIQ_APP_URL — the deployed app root (the "current deployment
 *     landing page"). Used by the Sign in / Start mapping / Review mapping CTAs;
 *     the app then presents the branded Entra sign-in card.
 *     PUBLIC REPO: commit ONLY the placeholder below. Set the real URL at deploy
 *     time (see README: env-substitution entrypoint or by editing this file).
 *
 *  2. COMPLIANCEIQ_REPO_URL — the public GitHub source repository. Used by the
 *     Resources link (repo root) and the Get started CTA (deployment guide).
 *     Safe to commit because the repository is public; override it in a fork.
 */
window.COMPLIANCEIQ_APP_URL = "https://app.example.com";
window.COMPLIANCEIQ_REPO_URL = "https://github.com/warrendt/compliance-iq";
