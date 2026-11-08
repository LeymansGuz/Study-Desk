# Get an API key

[Back to README](../README.md#first-launch) · [Connection settings](AI-AND-PIPELINE.md#connect-a-provider)

Use your own provider account. A chat website login/subscription is not an API
key: check the API account's billing and available credits separately.

| Provider | Get a key | Instructions |
|---|---|---|
| DeepSeek — tested paid baseline | [API keys](https://platform.deepseek.com/api_keys) | [Steps](#deepseek) |
| OpenRouter — eligible free or paid models | [API keys](https://openrouter.ai/keys) | [Steps](#openrouter) |
| OpenAI API | [API keys](https://platform.openai.com/api-keys) | [Steps](#openai-api) |
| Claude API | [API keys](https://platform.claude.com/settings/keys) | [Steps](#claude-api) |
| Other compatible provider / local server | Your provider's developer dashboard | [Steps](#custom-endpoints-and-local-servers) |

## Use the key in Study Desk

1. Open **Settings → AI connection** and choose the matching provider.
2. Paste the key and choose **Save and use** to save it and load models.
3. Choose a model and, for OpenRouter, an eligible hosting endpoint; save again.

No terminal or `.env` editing is needed in the desktop app. Each provider keeps
its own key. When returning to it, leave the key field blank to reuse the saved key.

## DeepSeek

1. Sign in or create an account on the [DeepSeek API platform](https://platform.deepseek.com/).
   Complete any verification requested by the platform.
2. Open [API keys](https://platform.deepseek.com/api_keys), create a key and name it **Study Desk**.
3. Copy the generated key into Study Desk with **DeepSeek** selected.
4. Check the API platform's balance/billing and add funds if needed for paid use.
   Select Flash in Study Desk for the tested paid baseline.

Free use of the DeepSeek chat website does not establish available API balance.
Official references: [API setup](https://api-docs.deepseek.com/) and
[balance/authentication errors](https://api-docs.deepseek.com/quick_start/error_codes/).

## OpenRouter

1. Sign in or create an [OpenRouter account](https://openrouter.ai/).
2. Open [API keys](https://openrouter.ai/keys), create a key named **Study Desk**,
   and choose a credit limit where offered.
3. Copy the key into Study Desk with **OpenRouter** selected.
4. For the free route, keep **Free only** selected and choose an eligible free
   model/host. Paid models require available credits in your OpenRouter account.

One key can access both free and paid models. OpenRouter's `:free` variants do not
require a credit purchase, while some other zero-priced entries can require a
funded account. Free availability and allowances can change. Study Desk limits
free models to **Brief overview** in Explain; it does not automatically switch to
paid usage. One explanation can use several requests for generation and checking.

Official references: [key creation and credit limits](https://openrouter.ai/docs/api_reference/authentication),
[free models](https://openrouter.ai/collections/free-models) and
[allowances](https://openrouter.ai/docs/api_reference/limits).

## OpenAI API

1. Sign in or create an account on the [OpenAI API platform](https://platform.openai.com/).
2. Choose the project you intend to use, open [API keys](https://platform.openai.com/api-keys),
   and create a project API key named **Study Desk**. Use a normal inference key,
   not an organisation Admin API key.
3. Copy the key into Study Desk with **OpenAI API** selected.
4. Check [API billing/credits](https://platform.openai.com/account/billing/overview)
   and ensure the project has access to your chosen model. Restricted keys need
   permission to list models and create Responses.

A ChatGPT login is not an API credential. Any API credits included with an account
or promotion must be available in the API platform; do not assume a subscription
makes all API calls free.

Official OpenAI documentation: [quickstart](https://developers.openai.com/api/docs/quickstart)
and [API keys](https://developers.openai.com/api/docs/guides/api-keys).

## Claude API

1. Sign in or create an account in the [Claude Console](https://platform.claude.com/).
2. Open [API keys](https://platform.claude.com/settings/keys) and create a normal
   API key named **Study Desk**, linked to your account and scoped to your workspace.
   Do not use an Admin API key.
3. Copy the key when it is displayed and paste it into Study Desk with **Claude API** selected.
4. Check [Console billing](https://platform.claude.com/settings/billing) for available
   API credits; add or claim eligible credits if necessary.

Choose workspace scope during key creation: unscoped keys require an additional
workspace header that Study Desk does not configure. A Claude chat subscription
alone is not an API key; any included API credits must be claimed/available in
its Console account.

Official references: [create and scope a key](https://platform.claude.com/docs/en/get-api-key)
and [API billing](https://support.claude.com/en/articles/8977456-how-do-i-pay-for-my-claude-api-usage).

## Custom endpoints and local servers

For another hosted OpenAI-compatible provider, obtain a key from its official
developer dashboard. Choose **Custom compatible endpoint** in Study Desk and enter its documented
Chat Completions base URL and key. Use the base URL, not a complete
`/chat/completions` request URL. Remote endpoints must use HTTPS.

A local server may need no external account/key. Start it first, use its loopback
base URL (for example `http://127.0.0.1:1234/v1`), and leave the key blank only if
that server requires none. Compatibility and answer quality depend on its model
and API support; connecting successfully is not a quality certification.

## Key not accepted?

- Check that the key belongs to the selected provider and has no copied spaces.
- Check model/project/workspace permissions, API balance and account/regional eligibility.
- A key may be shown only once. If lost, create a replacement; if exposed, revoke it.
- Keep it out of chat messages, screenshots, GitHub issues and source commits.

See [connection troubleshooting](TROUBLESHOOTING.md#api-key-model-or-free-allowance-errors).
Dashboard labels can change; the official links above are the starting points.
Provider instructions checked **8 November 2026**.
