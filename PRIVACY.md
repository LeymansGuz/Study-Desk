# Study Desk data-use notice

Version: 2026-11-04. This notice describes the local desktop and source editions maintained by [LeymansGuz](https://github.com/LeymansGuz/Study-Desk).

## On your computer

Documents, extracted text, embeddings, questions, attempts, session history and diagnostics are stored in your local application data directory. They are not encrypted by Study Desk. Use your operating system's account protection and disk encryption. Backups contain this study data; keep them private. Study Desk does not provide a cloud account or upload your library to its maintainer.

The desktop edition stores a separate key for each provider in the operating system credential store. The source edition can read your private `.env` or use the same secure Settings flow. Keys are used by the local backend, never returned to the study interface or included in backups. Remove the desktop key using your operating system credential manager (service `StudyDesk.DeepSeek`, `StudyDesk.openrouter`, `StudyDesk.openai`, `StudyDesk.anthropic` or `StudyDesk.custom.<endpoint hash>`, account `api-key`). Do not share keys or diagnostic exports publicly.

## External services

Clipboard images are accessed only when you paste or choose Paste screenshot. The app does not monitor your clipboard. Attachment text/OCR is processed locally; reading an attachment makes no AI request. A bounded, temporary in-memory text cache reuses extraction for retries. Starting tutoring sends the reviewed question text to the provider after the AI data-use acknowledgement.

When you request AI generation, explanations, answers or hints, the backend sends relevant course excerpts, your topic/question, relevant attempts/history and generated content to your selected AI provider and, when using OpenRouter, its selected hosting provider. Verification and repairs may send this content again. These requests use your provider account and can incur charges. Avoid uploading personal, confidential or sensitive information. Local processing does not mean AI requests stay on your computer.

DeepSeek operates independently and may process data outside Hong Kong. Review [DeepSeek's API terms](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html) and [privacy policy](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html) before enabling AI. Its general privacy policy expressly distinguishes downstream application users; it does not replace this app's notice. Confirm your API account's applicable processing and retention terms with the provider. Study Desk cannot promise deletion from provider systems, a particular retention period, or that provider content is never used for other purposes.

Refreshing model catalogs and allowance checks contact the selected provider using its key without sending course excerpts. An explicitly approved connection test sends a small synthetic JSON request. OpenRouter may forward study requests to a separate hosting provider. Its free endpoints can have different logging, training and retention policies; review the selected endpoint before sending private notes. Custom connections send data to the endpoint you supply. Changing a connection does not change the recipient of an already-running workflow.

Review [OpenRouter terms](https://openrouter.ai/terms) and [privacy](https://openrouter.ai/privacy), [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data), and [Anthropic privacy](https://privacy.claude.com/) for the services you choose. Regional eligibility is model/provider-specific and can change. Study Desk does not bypass regional access restrictions.

Initial local embedding-model downloads contact model hosts. Explicit update checks/downloads contact GitHub and its download infrastructure, which receive connection information such as your IP address. Update checks disclose the installed version/platform through the selected update request; they do not send course content or your API key. There is no automatic upload of your study diagnostics to the maintainer. Optional automatic update checks are off by default.

## Your controls

You can use Workspace without accepting AI data use. In Settings you can review or withdraw your acknowledgement; withdrawal blocks future AI requests but cannot recall content already sent. An AI request already in progress may finish. Delete individual documents/courses and sessions using the app. To erase all local data, close the app and delete its application data directory and any backups/exports you made. Uninstalling the app preserves study data. See README for platform paths and backup/restore instructions.

Diagnostics include outcomes, timings, token usage and potentially generated content, source references and student attempts. Inspect any export before sharing it. Submit general issues through the GitHub repository, without private course materials, personal information or keys. If you handle other people's personal data, you are responsible for having an appropriate lawful basis and notices; this local acknowledgement alone does not establish that.
