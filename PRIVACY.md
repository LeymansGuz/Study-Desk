# Study Desk data-use notice

Version: 2026-11-03. This notice describes the local desktop and source editions maintained by [LeymansGuz](https://github.com/LeymansGuz/Study-Desk).

## On your computer

Documents, extracted text, embeddings, questions, attempts, session history and diagnostics are stored in your local application data directory. They are not encrypted by Study Desk. Use your operating system's account protection and disk encryption. Backups contain this study data; keep them private. Study Desk does not provide a cloud account or upload your library to its maintainer.

The desktop edition stores your DeepSeek key in the operating system credential store. The source edition reads your private `.env`. Keys are used by the local backend, never returned to the study interface or included in backups. Remove the desktop key using your operating system credential manager (service `StudyDesk.DeepSeek`, account `api-key`). Do not share keys or diagnostic exports publicly.

## External services

When you request AI generation, explanations, answers or hints, the backend sends relevant course excerpts, your topic/question, relevant attempts/history and generated content to DeepSeek. Verification and repairs may send this content again. These requests use your provider account and can incur charges. Avoid uploading personal, confidential or sensitive information. Local processing does not mean AI requests stay on your computer.

DeepSeek operates independently and may process data outside Hong Kong. Review [DeepSeek's API terms](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html) and [privacy policy](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html) before enabling AI. Its general privacy policy expressly distinguishes downstream application users; it does not replace this app's notice. Confirm your API account's applicable processing and retention terms with the provider. Study Desk cannot promise deletion from provider systems, a particular retention period, or that provider content is never used for other purposes.

Initial local embedding-model downloads contact model hosts. Explicit update checks/downloads contact GitHub and its download infrastructure, which receive connection information such as your IP address. Update checks disclose the installed version/platform through the selected update request; they do not send course content or your API key. There is no automatic upload of your study diagnostics to the maintainer. Optional automatic update checks are off by default.

## Your controls

You can use Workspace without accepting AI data use. In Settings you can review or withdraw your acknowledgement; withdrawal blocks future AI requests but cannot recall content already sent. An AI request already in progress may finish. Delete individual documents/courses and sessions using the app. To erase all local data, close the app and delete its application data directory and any backups/exports you made. Uninstalling the app preserves study data. See README for platform paths and backup/restore instructions.

Diagnostics include outcomes, timings, token usage and potentially generated content, source references and student attempts. Inspect any export before sharing it. Submit general issues through the GitHub repository, without private course materials, personal information or keys. If you handle other people's personal data, you are responsible for having an appropriate lawful basis and notices; this local acknowledgement alone does not establish that.
