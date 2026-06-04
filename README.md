# Park Track 🚀

Never miss a job opening from Technopark or Infopark again.

Park Track is a Telegram bot that monitors job listings from Kerala's biggest IT parks and sends you a clean daily digest of openings that match your interests. Instead of manually checking multiple job portals every day, you simply subscribe to keywords like `Laravel`, `React`, `AI`, `Python`, or `Full Stack`, and Park Track does the tracking for you.

Whether you're actively job hunting or just keeping an eye on the market, Park Track helps you stay updated without the noise.

---

## ✨ What Makes Park Track Different?

### 🎯 Smart Keyword Matching
Park Track doesn't rely on simple substring matching. It uses word-boundary-aware POSIX regular expressions to avoid false positives.
For example:
* `AI` won't match words like "email" or "unpaid"
* `.NET` only matches actual .NET roles
* Special developer terms like `C++`, `C#`, `UI/UX`, and `R&D` are handled correctly

### 📬 One Clean Daily Digest
Instead of flooding your Telegram with dozens of individual alerts throughout the day, Park Track combines all matching jobs into a single organized summary message.

### 🏢 Choose Your Sources
Filter by your preferred location:
* Technopark only
* Infopark only
* Both IT parks
You can switch anytime with a simple Telegram command.

### ⚡ Reliable Delivery
Built-in safeguards automatically handle Telegram's global rate limits and large message limits (auto-chunking messages that exceed 4,000 characters), ensuring your digests reach you reliably.

### 🔒 Secure by Design
Telegram webhook requests are validated using secret-token verification (`X-Telegram-Bot-Api-Secret-Token`) to prevent unauthorized spoofing requests.

---

## 🛠️ Built With

* **Cloudflare Workers** – Telegram bot backend (Edge)
* **Supabase (PostgreSQL)** – Data storage and matching engine
* **GitHub Actions** – Automated daily scraping and notification delivery
* **Python** – Scraping and notification services
* **Telegram Bot API** – User interaction and alerts

---

## 📁 Project Structure

* **[.github/workflows/scrape.yml](.github/workflows/scrape.yml)** – GitHub Actions schedule workflow
* **[supabase/migrations/](supabase/migrations/)** – Schema migrations for tables, indexes, and views
* **[worker/index.js](worker/index.js)** – Cloudflare Worker subscription handler
* **[worker/wrangler.toml](worker/wrangler.toml)** – Cloudflare Worker project settings
* **[scraper.py](scraper.py)** – Ingestion pipeline script
* **[notifier.py](notifier.py)** – Notification delivery service
* **[utils.py](utils.py)** – Shared database client and configuration helpers
* **[requirements.txt](requirements.txt)** – Python package dependencies
* **[.env.example](.env.example)** – Template environment file

---

## 🚀 Getting Started

### 1. Set Up Supabase
1. Create a Supabase project.
2. Run the SQL migrations found in the **[supabase/migrations/](supabase/migrations/)** folder sequentially using the Supabase Dashboard **SQL Editor**.

### 2. Deploy the Telegram Backend
1. Deploy the Cloudflare Worker inside the `worker/` directory:
   ```bash
   npx wrangler deploy
   ```
2. In your Cloudflare Worker Dashboard under **Settings -> Variables & Secrets**, add the required environment secrets:
   * `SUPABASE_URL`
   * `SUPABASE_SERVICE_ROLE_KEY`
   * `TELEGRAM_BOT_TOKEN`
   * `TELEGRAM_WEBHOOK_SECRET` (A secure random key to identify webhook traffic)
3. Register your Telegram webhook with Telegram:
   ```bash
   curl -F "url=https://<your-worker-name>.<your-subdomain>.workers.dev" \
        -F "secret_token=<your_webhook_secret>" \
        https://api.telegram.org/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook
   ```

### 3. Configure GitHub Actions
1. Push this repository to GitHub.
2. In your repository settings, go to **Settings -> Secrets and variables -> Actions**, and add the following repository secrets:
   * `SUPABASE_URL`
   * `SUPABASE_SERVICE_ROLE_KEY`
   * `TELEGRAM_BOT_TOKEN`

The workflow runs automatically every day at 10:00 AM IST and can also be triggered manually from your GitHub Actions tab.

---

## 🤖 Available Commands

### Subscribe to Keywords
```text
/add react, next.js, laravel
```
Subscribe to one or more keywords (comma-separated). Maximum of 6 active keywords per user.

### Remove a Keyword
```text
/remove react
```
Unsubscribe from a keyword.

### Select Job Sources
```text
/sources technopark
/sources infopark
/sources both
```
Filter which IT park openings to monitor.

### View Active Subscriptions
```text
/list
```
Displays your active keyword list and selected sources.

### Help
```text
/start
/help
```
Displays instructions and command references.

### Learn More
```text
/about
```

### Support the Project
```text
/donate
```
UPI ID: `madhavbiju0399@nyes`

---

## 💡 Why I Built This

Like many developers in Kerala, I found myself repeatedly checking Technopark and Infopark job portals for relevant openings. Most listings weren't relevant to my skills, and important opportunities were easy to miss.

Park Track was created to automate that process and deliver only the jobs that matter, directly to Telegram.

If it saves you even a few minutes every day—or helps you discover your next opportunity—it's doing its job.
