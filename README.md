# 🧵 Meta Threads AI Agent

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Google GenAI SDK](https://img.shields.io/badge/google--genai-v1.0%2B-brightgreen.svg)](https://github.com/google-gemini/deprecations)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Automated-purple.svg)](https://github.com/features/actions)

A serverless, zero-maintenance, production-ready AI automation agent for **Meta Threads**. Powered by the official `google-genai` Python SDK and scheduled with **GitHub Actions**, this agent writes human-like, niche-specific Threads posts and engages with incoming replies on autopilot—with **zero hosting costs**.

---

## 🔒 Security & Privacy Architecture

This project is engineered with a **strict zero-leakage privacy guarantee**, making it **100% safe for public repositories and forks**:

1. **Zero Secret Storage in Git**:
   - Neither personal identifiers (`THREADS_USER_ID`) nor private credentials (`THREADS_ACCESS_TOKEN`, `META_APP_SECRET`, `GEMINI_API_KEY`) are ever hardcoded or committed into Git.
   - All sensitive credentials reside exclusively in **encrypted GitHub Repository Secrets** (for CI/CD runs) or git-ignored `.env` files (for local runs).
2. **Sanitized State Persistence**:
   - `state.json` ONLY records interaction tracking IDs (`replied_comment_ids`, `last_post_id`) so the bot remembers which comments and posts it has already processed.
   - The storage layer (`agent/storage.py`) programmatically strips all access tokens before saving `state.json` to disk, guaranteeing that credentials never touch disk or Git commits.
3. **Safe for Public Forks**:
   - Anyone can fork this repository publicly. No private credentials will ever be exposed.

---

## 🌟 Key Features

- ⚡ **100% Serverless & Zero Cost:** Runs on free GitHub Actions cron runners (`cron: "0 */6 * * *"`). No AWS, VPS, or Docker container needed.
- 🧠 **Google GenAI SDK Native:** Powered by `google-genai` with official Gemini models (`gemini-3-flash-preview` / `gemini-2.5-flash`). Never uses deprecated packages or legacy models.
- 🎯 **No-Code Persona Customization:** Control your niche, tone of voice, personality, post formats, and model selection from a single `config.json` file without touching Python code.
- 🛡️ **Intelligent Spam & Bot Filtering:** Evaluates incoming comments before replying. Discards promo spam, crypto scams, and bot follow-trains, while providing witty, concise peer-to-peer replies (≤ 15 words) to genuine followers.
- 🔒 **Secure & 100% Forkable:** Private keys and credentials remain safely in GitHub Repository Secrets. Anyone can fork this repository and launch their own agent in 5 minutes without exposing confidential tokens.

---

## 📁 Repository Structure

```text
.
├── .github/
│   └── workflows/
│       └── threads-agent.yml     # Automated 6-hour cron & dispatch workflow
├── agent/
│   ├── __init__.py               # Agent package definition
│   ├── brain.py                  # Gemini AI post & reply generation engine
│   ├── storage.py                # Safe sanitized state & config persistence
│   └── threads_api.py            # Meta Graph API client & auto-refresh logic
├── .env.example                  # Template for local environment variables
├── .gitignore                    # Prevents secret and cache leakage
├── config.json                   # User-configurable niche, persona, and settings
├── get_token.py                  # Automated OAuth & token retriever utility
├── state.json                    # Sanitized agent state (interaction IDs only)
├── main.py                       # Master execution pipeline
├── requirements.txt              # Production Python dependencies
└── README.md                     # Documentation & setup guide
```

---

## ⚙️ Configuration (`config.json`)

Customize the agent's behavior by editing [`config.json`](config.json):

```json
{
  "niche": "Competitive Gaming, Valorant, and Dark Psychological Anime",
  "persona": "A 20-something competitive gamer and anime enthusiast posting raw thoughts from their phone. Witty, blunt, relatable, never sounds like a brand or AI.",
  "custom_instructions": "Keep it authentic, punchy, and engaging. Maximum 1-2 sentences with natural phrasing.",
  "post_styles": [
    "VIRAL_QUESTION",
    "HOT_TAKE",
    "RELATABLE_MOMENT",
    "UNPOPULAR_OPINION"
  ],
  "auto_reply_enabled": true,
  "max_threads_to_scan": 3,
  "gemini_model": "gemini-3-flash-preview"
}
```

### Parameter Reference

| Key | Description |
|---|---|
| `niche` | The core topics, communities, or subject matter your account focuses on. |
| `persona` | The voice, age, background, and attitude of the account. |
| `custom_instructions` | Hard constraints on formatting, slang, punctuation, hashtags, or forbidden words. |
| `post_styles` | Array of rotation styles: `VIRAL_QUESTION`, `HOT_TAKE`, `RELATABLE_MOMENT`, etc. |
| `auto_reply_enabled` | `true` to scan recent threads and reply to incoming comments; `false` to disable. |
| `max_threads_to_scan` | Number of recent posts to check for user replies on each run (default: `3`). |
| `gemini_model` | Google Gemini model identifier (e.g. `gemini-3-flash-preview`). |

---

## 🚀 Step-by-Step Setup Guide

Follow this guide to launch your own automated Threads agent from scratch.

### Step 1: Fork This Repository
1. Click the **Fork** button at the top right of this repository.
2. Select your GitHub account and create the fork.

---

### Step 2: Get a Free Gemini API Key
1. Visit **[Google AI Studio](https://aistudio.google.com/)**.
2. Sign in with your Google account.
3. Click **Get API key** > **Create API key in new project**.
4. Copy the generated key. (Free tier includes generous RPM/RPD).

---

### Step 3: Set Up Meta Developer App & Threads API

#### 3.1 Create App
1. Go to **[Meta for Developers](https://developers.facebook.com/)** and log in.
2. Click **My Apps** > **Create App**.
3. Choose **Other** (or **I want to access Threads API**) > select **Threads** use case.
4. Name your app and finish creation.

#### 3.2 Add Required Permissions
Under the Threads API dashboard, ensure the following scopes are enabled:
- `threads_basic`
- `threads_content_publish`
- `threads_read_replies`
- `threads_manage_replies`

#### 3.3 Add Your Account as a Threads Tester
1. In the Meta Developer Dashboard, navigate to **Roles** > **Roles** (or **Threads Tester**).
2. Click **Add Threads Testers** and enter your Threads username.
3. Open the **Threads app** on your phone (or web):
   - Go to **Settings** > **Account** > **Website permissions** > **Invites**.
   - Accept the pending tester invitation.

#### 3.4 Automated Token Retrieval (Recommended Shortcut)
Instead of running manual `curl` commands, you can use the built-in automated utility:
```bash
python get_token.py
```
This utility provides two automated options:
- **Option 1 (Automated Browser OAuth):** Launches your browser, catches Meta's redirect callback automatically, exchanges for a 60-day long-lived token, and fetches your numeric `THREADS_USER_ID`.
- **Option 2 (Quick Token Resolver):** Paste any token from the Meta Developer dashboard to automatically validate it and resolve your numeric `THREADS_USER_ID`.

*(Optional manual method)*:
If you prefer manual `curl`, exchange your short-lived token via:
```bash
curl -i -X GET "https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret=YOUR_APP_SECRET&access_token=SHORT_LIVED_TOKEN"
```
And retrieve your numeric Threads User ID via:
```bash
curl -X GET "https://graph.threads.net/v1.0/me?fields=id,username&access_token=YOUR_TOKEN"
```

---

### Step 4: Configure GitHub Repository Secrets

1. In your forked repository, go to **Settings** > **Secrets and variables** > **Actions**.
2. Under **Repository secrets**, click **New repository secret** for each of these keys:

| Secret Name | Value |
|---|---|
| `GEMINI_API_KEY` | Your Google AI Studio API key |
| `THREADS_ACCESS_TOKEN` | Your 60-day long-lived Threads token |
| `THREADS_USER_ID` | Your numeric Threads user ID |
| `THREADS_APP_ID` | *(Optional)* Your Meta App ID |
| `THREADS_APP_SECRET` | *(Optional)* Your Meta App Secret |

---

### Step 5: Enable GitHub Actions Workflow Write Permissions

GitHub Actions requires write permissions to push the updated `state.json` file back to your repo:

1. In your repository, go to **Settings** > **Actions** > **General**.
2. Scroll down to **Workflow permissions**.
3. Select **Read and write permissions**.
4. Check **Allow GitHub Actions to create and approve pull requests**.
5. Click **Save**.

---

### Step 6: Trigger First Test Run

1. Click the **Actions** tab in your repository.
2. In the left sidebar, click **Threads AI Agent**.
3. Click the **Run workflow** dropdown on the right and press the green **Run workflow** button.
4. Watch the runner execute:
   - Verifies credentials
   - Generates an authentic post tailored to your persona
   - Publishes to Threads via Meta's 2-step container endpoint
   - Scans and replies to comments
   - Commits the updated sanitized `state.json` cleanly back to your repository

---

## 💻 Local Development (Optional)

To test the bot locally on your machine:

1. Clone your repository:
   ```bash
   git clone https://github.com/your-username/threads-ai-bot.git
   cd threads-ai-bot
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file from the template:
   ```bash
   cp .env.example .env
   ```
   Add your `GEMINI_API_KEY`, `THREADS_ACCESS_TOKEN`, and `THREADS_USER_ID`.

5. Run the agent:
   ```bash
   python main.py
   ```

---

## 🛡️ License

This project is licensed under the [MIT License](LICENSE). Feel free to fork, adapt, and share!

Developed with ❤️ by **[Lakshay](https://github.com/Lakshay-exec)**.
