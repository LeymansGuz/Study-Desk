# Local beta compliance scope

Reviewed 3 November 2026. These are practical safeguards, not legal clearance.

## Implemented safeguards

- A versioned data-use notice and usage terms appear before the first AI request. A server-side check blocks AI requests without the current acknowledgement. Settings supports review and withdrawal.
- The notice covers local unencrypted data/backups, diagnostics, DeepSeek content transfers/costs, model downloads and manual GitHub update connections. It makes no guarantee about provider retention/training or universal answer correctness.
- Uploads require an explicit rights confirmation. Private study does not automatically permit every use or redistribution. No copyrighted course library is distributed with the app.
- Local deletion, backup, credential-removal and reporting instructions are documented. Study telemetry is not automatically sent to the maintainer. Public issues must not contain personal information, keys or protected course content.
- Python licence files preserve relative paths. Distribution metadata, Python/Node/OPA licences and locked Rust dependency notices accompany desktop builds. Frontend licences are retained; the MIT licence covers Study Desk's own code.
- Updates authenticate payloads and signed versions, preserve the separate data folder, and require a verified backup before installation.

## Remaining responsibilities

Acknowledgement does not prove document-processing permission or establish a lawful basis for other people's personal data. Users need the necessary permissions and must assess their DeepSeek account's terms. Commercial activity, collection of user data or redistribution of protected content changes this assessment.

Bundled notices and dependency inventories do not prove that every native/transitive licence obligation is satisfied. Review native-library and Linux/AppImage copyleft source/relinking obligations before broader redistribution. OS code signing/notarization and target-device GUI testing are separate from updater authentication. Do not advertise legal risk-free status or guaranteed AI correctness.

Primary references: [DeepSeek API terms](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html), [DeepSeek privacy policy](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html) (which distinguishes downstream apps), and [Hong Kong IPD copyright FAQs](https://www.ipd.gov.hk/en/copyright/legislative-proposals-and-amendments/copyright-amendment-ordinance-2022/details-faqs/index.html). Privacy obligations depend on who controls actual personal-data processing. Seek Hong Kong legal advice if the scope expands.
