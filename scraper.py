import os
import re
import time
import logging
import sys
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client, Client

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scraper.log')
    ]
)
logger = logging.getLogger("scraper")

# Load environment variables
load_dotenv()

# Configuration Validation
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY or not TELEGRAM_BOT_TOKEN:
    logger.error("Missing critical environment variables: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, or TELEGRAM_BOT_TOKEN.")
    sys.exit(1)

# Clean up SUPABASE_URL if it has /rest/v1 or /rest/v1/ at the end
if SUPABASE_URL.endswith("/rest/v1"):
    SUPABASE_URL = SUPABASE_URL[:-8]
elif SUPABASE_URL.endswith("/rest/v1/"):
    SUPABASE_URL = SUPABASE_URL[:-9]

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Date parser helpers
def parse_date(date_str, format_str):
    try:
        return datetime.strptime(date_str.strip(), format_str).strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return None

def parse_infopark_date(date_str):
    # Try DD-MM-YYYY
    parsed = parse_date(date_str, "%d-%m-%Y")
    if parsed:
        return parsed
    # Try DD MMM YYYY (e.g. 02 Jun 2026)
    parsed = parse_date(date_str, "%d %b %Y")
    if parsed:
        return parsed
    return None

def scrape_technopark():
    logger.info("Scraping Technopark API...")
    jobs = []
    session = requests.Session()
    session.headers.update({
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'Referer': 'https://technopark.in/job-search',
        'X-Requested-With': 'XMLHttpRequest'
    })

    page = 1
    while True:
        url = f"https://technopark.in/api/paginated-jobs?page={page}&search=&type="
        try:
            logger.info(f"Fetching Technopark page {page}...")
            response = session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            job_listings = data.get('data', [])
            if not job_listings:
                logger.info("No more job listings found on Technopark.")
                break
                
            for item in job_listings:
                numeric_id = item.get('id')
                if not numeric_id:
                    continue
                job_id = f"technopark-{numeric_id}"
                title = item.get('job_title', '').strip()
                company_data = item.get('company', {})
                company_name = company_data.get('company', 'Unknown').strip()
                
                # Format url using numeric id
                job_url = f"https://technopark.in/job-details/{numeric_id}"
                posted_date = item.get('posted_date')
                closing_date = item.get('closing_date')
                
                jobs.append({
                    "job_id": job_id,
                    "title": title,
                    "company_name": company_name,
                    "posted_date": posted_date if posted_date else None,
                    "expiry_date": closing_date if closing_date else None,
                    "description": f"Company: {company_name}",
                    "url": job_url,
                    "source": "technopark",
                    "scraped_at": datetime.now(timezone.utc).isoformat()
                })
                
            last_page = data.get('last_page', 1)
            if page >= last_page:
                logger.info(f"Reached last page {last_page} of Technopark.")
                break
            page += 1
        except Exception as e:
            logger.error(f"Error scraping Technopark page {page}: {e}")
            break
            
    return jobs

def scrape_infopark():
    logger.info("Scraping Infopark Career Portal...")
    jobs = []
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    })

    page = 1
    while True:
        url = f"https://infopark.in/companies/job-search/1?page={page}"
        try:
            logger.info(f"Fetching Infopark page {page}...")
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            tbody = soup.find('tbody')
            if not tbody:
                logger.info(f"No tbody found on Infopark page {page}. Stopping.")
                break
                
            rows = tbody.find_all('tr')
            if not rows:
                logger.info("No more job listings found on Infopark.")
                break
                
            # Check for out-of-bounds page returning "No Jobs." row
            if len(rows) == 1 and "no jobs" in rows[0].text.lower():
                logger.info("No more job listings found on Infopark (reached 'No Jobs').")
                break
                
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 5:
                    continue
                    
                posted_date_raw = cols[0].text.strip()
                title = cols[1].text.strip()
                company_name = cols[2].text.strip()
                closing_date_raw = cols[3].text.strip()
                
                a_tag = cols[4].find('a')
                if not a_tag or not a_tag.get('href'):
                    continue
                job_url = a_tag['href']
                
                # Extract job_id from URL: e.g., https://infopark.in/company-jobs/details/23859/312
                match = re.search(r'/details/(\d+)', job_url)
                if not match:
                    continue
                raw_id = match.group(1)
                job_id = f"infopark-{raw_id}"
                posted_date = parse_infopark_date(posted_date_raw)
                expiry_date = parse_infopark_date(closing_date_raw)
                
                jobs.append({
                    "job_id": job_id,
                    "title": title,
                    "company_name": company_name,
                    "posted_date": posted_date,
                    "expiry_date": expiry_date,
                    "description": f"Company: {company_name}",
                    "url": job_url,
                    "source": "infopark",
                    "scraped_at": datetime.now(timezone.utc).isoformat()
                })
            page += 1
        except Exception as e:
            logger.error(f"Error scraping Infopark page {page}: {e}")
            break
            
    return jobs

def send_telegram_notification(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    response = requests.post(url, json=payload, timeout=10)
    
    # Check for blocking errors
    if response.status_code in (403, 400):
        # 403: Bot blocked by user, 400: Chat not found
        response_data = response.json()
        description = response_data.get("description", "").lower()
        if "blocked" in description or "chat not found" in description:
            logger.warning(f"Telegram user {chat_id} has blocked the bot or chat does not exist. Removing subscriptions.")
            # Remove this user's subscriptions immediately
            try:
                supabase.table("subscriptions").delete().eq("chat_id", chat_id).execute()
                logger.info(f"Successfully deleted all subscriptions for chat_id {chat_id}")
            except Exception as delete_err:
                logger.error(f"Failed to delete subscriptions for chat_id {chat_id}: {delete_err}")
            
    response.raise_for_status()

def main():
    logger.info("Starting Scraper Pipeline...")
    
    # 1. Scrape Portals
    tp_jobs = scrape_technopark()
    ip_jobs = scrape_infopark()
    all_scraped_jobs = tp_jobs + ip_jobs
    
    logger.info(f"Total scraped jobs: {len(all_scraped_jobs)} (Technopark: {len(tp_jobs)}, Infopark: {len(ip_jobs)})")
    
    if not all_scraped_jobs:
        logger.info("No jobs scraped. Exiting pipeline.")
        return
        
    # 2. Bulk Upsert into Supabase
    try:
        logger.info("Bulk upserting jobs into database...")
        # Chunk upsert in case of a very large list
        chunk_size = 100
        for i in range(0, len(all_scraped_jobs), chunk_size):
            chunk = all_scraped_jobs[i:i + chunk_size]
            # Supabase PostgREST bulk upsert
            supabase.table("jobs").upsert(chunk).execute()
        logger.info("Jobs successfully bulk upserted.")
    except Exception as e:
        logger.error(f"Error bulk upserting jobs: {e}")
        # We can still proceed to send notifications for successfully matched ones already in DB
        
    # 3. Fetch Pending Notifications from consolidated view
    pending_list = []
    try:
        logger.info("Querying pending notifications view...")
        response = supabase.table("pending_notifications_consolidated").select("*").execute()
        pending_list = response.data
        logger.info(f"Found {len(pending_list)} users with consolidated pending notifications.")
    except Exception as e:
        logger.error(f"Error querying pending_notifications_consolidated: {e}")
        return

    if not pending_list:
        logger.info("No new matching jobs found to notify. Exiting.")
        return

    # 4. Dispatch Loop with Scale Protection and Digest Splitter
    successful_notifications = []
    for item in pending_list:
        chat_id = item["chat_id"]
        job_ids = item["job_ids"]
        jobs_markdown = item["jobs_markdown"]

        if not jobs_markdown or not job_ids:
            continue

        # Split consolidated markdown into parts if it exceeds Telegram's limit (4000 characters)
        message_parts = []
        current_part = []
        current_len = 0
        
        # Split by double newline to separate individual job blocks
        blocks = jobs_markdown.split('\n\n')
        for block in blocks:
            block_len = len(block)
            # Add 2 for '\n\n' delimiter when combining
            if current_part and current_len + block_len + 2 > 4000:
                message_parts.append('\n\n'.join(current_part))
                current_part = [block]
                current_len = block_len
            else:
                current_part.append(block)
                current_len += block_len + (2 if len(current_part) > 1 else 0)
                
        if current_part:
            message_parts.append('\n\n'.join(current_part))

        # Send digest parts
        try:
            total_parts = len(message_parts)
            for idx, part in enumerate(message_parts, 1):
                if total_parts > 1:
                    message_text = f"📦 *Daily Job Digest (Part {idx}/{total_parts})*:\n\n{part}"
                else:
                    message_text = f"🚀 *Daily Job Digest*:\n\n{part}"

                logger.info(f"Notifying chat {chat_id} about digest part {idx}/{total_parts}...")
                send_telegram_notification(chat_id, message_text)
                
                # Rate limit protection between successive messages
                time.sleep(0.05)
                
            # If all parts were successfully sent, add all job_ids to notifications_sent list
            for jid in job_ids:
                successful_notifications.append({
                    "chat_id": chat_id,
                    "job_id": jid
                })
        except Exception as e:
            logger.error(f"Failed to deliver digest to chat {chat_id}: {e}")

    # 5. Post-Delivery Log: Batch log sent messages
    if successful_notifications:
        try:
            logger.info(f"Logging {len(successful_notifications)} sent notifications to database...")
            supabase.table("notifications_sent").insert(successful_notifications).execute()
            logger.info("Sent notifications successfully logged.")
        except Exception as e:
            logger.error(f"Error logging sent notifications: {e}")
            
    # 6. Database Maintenance: Clean up jobs older than 90 days
    try:
        logger.info("Cleaning up jobs older than 90 days...")
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        supabase.table("jobs").delete().lt("scraped_at", cutoff).execute()
        # Deleting old jobs will automatically cascade delete from notifications_sent
        logger.info("Database cleanup completed successfully.")
    except Exception as e:
        logger.error(f"Error cleaning up old jobs: {e}")
            
    logger.info("Scraper Pipeline completed successfully.")

if __name__ == "__main__":
    main()
