# Local beta compliance scope

Technical documentation reviewed **8 November 2026**. This describes implemented
safeguards, not a new legal opinion or legal clearance.

[Privacy notice](PRIVACY.md) · [Usage terms](TERMS.md) · [Licensing and notices](THIRD-PARTY-NOTICES.md) · [Security review](SECURITY-AUDIT.md)

## Implemented safeguards

| Area | Safeguard |
|---|---|
| AI data use | Versioned privacy/usage notices and server-side acknowledgement before AI requests; review/withdrawal in Settings. |
| Provider transfers | Notice covers the selected provider/host, relevant study content, validation retries, costs and account eligibility. |
| Upload rights | Explicit rights confirmation; no copyrighted course library is distributed with the app. |
| Local control | Local deletion and backup controls; no automatic study-diagnostic upload to the maintainer. |
| Credentials | Desktop keys remain in the OS credential store and outside backups/releases; source `.env` is private. |
| Distribution notices | Original frontend licences, Python licence paths, Node/OPA notices and locked Rust inventory are preserved. |
| Updates | Signed/version-bound payloads, idle checks, verified backups and separate study-data storage. |

## Limits and responsibilities

- Acknowledgement does not prove permission to process documents or establish a
  lawful basis for another person's personal data.
- Users must assess their chosen provider and hosting endpoint's applicable
  processing, account and eligibility terms. The app does not promise retention,
  deletion or training practices on their behalf.
- Private study, free use or sharing with friends is not a blanket permission to
  redistribute protected material. See the unchanged usage terms.
- Bundled notices and inventories do not prove every native/transitive licence
  obligation is satisfied. Review source/relinking obligations before redistribution.
- OS signing/notarization, updater authentication and device compatibility are
  separate checks. AI verification is not a guarantee of truth.
- Commercial use, collecting user data or distributing protected course content
  changes the scope and calls for a new assessment.

The policy meaning and acknowledgement version remain unchanged by the documentation
reorganisation; navigation and headings have been clarified.

## Existing reference material

[DeepSeek API terms](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html),
[DeepSeek privacy policy](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html),
and [Hong Kong IPD copyright FAQs](https://www.ipd.gov.hk/en/copyright/legislative-proposals-and-amendments/copyright-amendment-ordinance-2022/details-faqs/index.html).
The privacy notice links the other supported providers. These references are not
a fresh jurisdiction-wide legal audit; seek appropriate advice if the scope expands.
