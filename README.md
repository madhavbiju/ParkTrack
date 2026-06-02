# Park Track

A highly-scalable, zero-cost Telegram Job Notification Bot. It integrates a Python scraper (running on GitHub Actions) with a Cloudflare Worker backend and a Supabase PostgreSQL database. 

This architecture separates user subscription interaction (handled at the edge via Cloudflare Workers) from daily data collection and notification delivery (handled via GitHub Actions).

---

## 🚀 Repository Structure
```
tpJobSearch/
├── .github/
│   └── workflows/
│       └── scrape.yml        # GHA schedule for daily scraping & dispatch
├── worker/
│   └── index.js              # Cloudflare Worker Telegram Webhook subscription handler
├── requirements.txt          # Python scraper dependencies
├── schema.sql                # Supabase PostgreSQL tables, indexes, and views
├── scraper.py                # Pipeline script containing scraper & notifier logic
├── .env.example              # Template env file for local testing
├── .gitignore                # Protects local environment credentials
└── README.md                 # Project description & guide
```

---

## 🛠️ Step-by-Step Setup Guide

### Step 1: Database Setup (Supabase)
1. Create a free project in the [Supabase Console](https://database.supabase.com/).
2. Navigate to the **SQL Editor** in the side panel.
3. Open a new query, copy the entire content of `schema.sql` from this repository, and click **Run**. This will create the `jobs`, `subscriptions`, and `notifications_sent` tables, alongside the optimized indexes and the `pending_notifications` view.

---

### Step 2: Deploy user subscriptions (Cloudflare Worker)
The Cloudflare Worker acts as the 24/7 serverless webhook that listens to users adding and listing keywords.
1. Deploy the script located in `worker/index.js` to a new Cloudflare Worker (you can use wrangler via `npx wrangler deploy` inside the `worker` folder).
2. Go to your Cloudflare Worker dashboard, navigate to **Settings** -> **Variables**, and add the following environment variables:
   - `SUPABASE_URL`: Your Supabase project URL.
   - `SUPABASE_SERVICE_ROLE_KEY`: Your Supabase service role API key.
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot API token (obtained from [@BotFather](https://t.me/BotFather)).
3. Hook your bot to your Worker by running the following command in your terminal (replace with your values):
   ```bash
   curl -F "url=https://your-worker-subdomain.workers.dev" https://api.telegram.org/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook
   ```

Now, try sending `/start`, `/add python`, or `/list` to your Telegram Bot. It should reply instantly!

---

### Step 3: Scraper Automation (GitHub Actions)
The scraper fetches new jobs daily, bulk upserts them to Supabase, and dispatches messages to users matching their registered keywords.
1. Push this codebase to your own GitHub Repository.
2. In your GitHub repository, go to **Settings** -> **Secrets and variables** -> **Actions** -> **Repository Secrets**.
3. Add the following secrets:
   - `SUPABASE_URL`: Your Supabase project URL.
   - `SUPABASE_SERVICE_ROLE_KEY`: Your Supabase service role API key.
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot API token.
4. The scraper is configured (`.github/workflows/scrape.yml`) to run automatically once a day. You can also trigger it manually by visiting the **Actions** tab in your repository, selecting the **Daily Job Scraper** workflow, and clicking **Run workflow**.

---

## 📝 Available Bot Commands
- `/start` or `/subscribe` — Explains usage and registers the user.
- `/add <keyword>` — Subscribes to a keyword (e.g. `/add react`). Input is automatically sanitized (lowercase, alphanumeric, dots, hyphens, capped at 30 chars).
- `/remove <keyword>` — Unsubscribes from a keyword (e.g. `/remove react`).
- `/list` — Lists all your active subscriptions.
