# ComplianceIQ built-in frameworks

ComplianceIQ ships **7 regional frameworks** with pre-built control→Azure Policy
catalogs. If a user's request matches one of these, they may not need to run a
PDF through extraction at all — the mapping already exists.

| Framework | Region | Sector | Policies |
|---|---|---|---|
| **SAMA** | Saudi Arabia | Financial | 48 |
| **ADHICS v2** | Abu Dhabi | Healthcare | 50 |
| **Saudi Arabia Government** (KSA Gov Cloud) | Saudi Arabia | Government | 58 |
| **NDMO Data Management** | Saudi Arabia | Government | 38 |
| **NCA CSCC v1.5** | Saudi Arabia | Government / CNI | 49 |
| **South African Government** | South Africa | Government | 56 |
| **Oman Government** | Oman | Government | 53 |

These are the **only** built-in frameworks. ComplianceIQ does **not** ship
NIST / CIS / ISO / FedRAMP / HIPAA / GDPR catalogs — for those (or any other
regulation) the user must supply the PDF and run it through the pipeline
(`ciq.py run --pdf ...`).

Each catalog maps controls to Azure Policy names + definition GUIDs, Defender for
Cloud control categories, and evidence/implementation guidance. Source of truth:
`README.md` "Supported Frameworks" and `framework/*/*_Initiative.json`.

## Finding a regulation (requirement a)
1. Ask the user for country / industry / framework name.
2. If it matches the table above, tell them it's built in.
3. Otherwise, help locate the **official** source document (regulator website)
   with `web_search`, get the PDF into the session, and process it. Never
   fabricate or paraphrase regulation text — only process a real document.
