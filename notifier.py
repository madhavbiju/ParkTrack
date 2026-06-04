import os
import sys
import time
import requests
from utils import get_logger, supabase

# Get notifier-specific logger
logger = get_logger("notifier")

# Configuration Validation
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    logger.error("Missing critical environment variable: TELEGRAM_BOT_TOKEN.")
    sys.exit(1)

def send_telegram_notification(chat_id, text):
    """
    Sends a markdown message to a Telegram chat, handling rate limits (429)
    and user block lists (403/400) automatically.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        response = requests.post(url, json=payload, timeout=10)
        
        # Handle HTTP 429 Too Many Requests (Rate Limiting)
        if response.status_code == 429:
            try:
                resp_json = response.json()
                retry_after = resp_json.get("parameters", {}).get("retry_after", 5)
            except Exception:
                retry_after = 5
                
            logger.warning(f"Telegram API rate limited (429) on attempt {attempt}/{max_retries}. Sleeping for {retry_after}s...")
            time.sleep(retry_after + 0.5)
            continue
            
        # Check for user blocking or chat deletion errors (403/400)
        if response.status_code in (403, 400):
            try:
                response_data = response.json()
                description = response_data.get("description", "").lower()
                if "blocked" in description or "chat not found" in description:
                    logger.warning(f"Telegram user {chat_id} has blocked the bot or chat does not exist. Removing subscriptions.")
                    try:
                        supabase.table("subscriptions").delete().eq("chat_id", chat_id).execute()
                        logger.info(f"Successfully deleted all subscriptions for chat_id {chat_id}")
                    except Exception as delete_err:
                        logger.error(f"Failed to delete subscriptions for chat_id {chat_id}: {delete_err}")
            except Exception as parse_err:
                logger.error(f"Failed to parse error response for chat_id {chat_id}: {parse_err}")
                
        response.raise_for_status()
        break

def main():
    """
    Main dispatch routine that queries pending alerts, splits digests
    to stay within Telegram length limits, and records dispatches.
    """
    logger.info("Starting Notifier Job...")
    
    # 1. Fetch Pending Notifications from consolidated view
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
        logger.info("No new matching jobs found to notify. Exiting notifier.")
        return

    # 2. Dispatch Loop with Scale Protection and Digest Splitter
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
        
        # Determine the correct delimiter based on what is present in the markdown
        delimiter = '\n\n'
        if '────────────────────────' in jobs_markdown:
            delimiter = '\n\n────────────────────────\n\n'
            
        blocks = jobs_markdown.split(delimiter)
        for block in blocks:
            block_len = len(block)
            delim_len = len(delimiter)
            
            # Check length guardrail
            if current_part and current_len + block_len + delim_len > 4000:
                message_parts.append(delimiter.join(current_part))
                current_part = [block]
                current_len = block_len
            else:
                current_part.append(block)
                current_len += block_len + (delim_len if len(current_part) > 1 else 0)
                
        if current_part:
            message_parts.append(delimiter.join(current_part))

        # Send digest parts
        try:
            total_parts = len(message_parts)
            for idx, part in enumerate(message_parts, 1):
                if total_parts > 1:
                    message_text = f"🚀 *Daily Job Digest (Part {idx}/{total_parts})*:\n\n{part}"
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

    # 3. Post-Delivery Log: Batch log sent messages
    if successful_notifications:
        try:
            logger.info(f"Logging {len(successful_notifications)} sent notifications to database...")
            supabase.table("notifications_sent").insert(successful_notifications).execute()
            logger.info("Sent notifications successfully logged.")
        except Exception as e:
            logger.error(f"Error logging sent notifications: {e}")
            
    logger.info("Notifier Job completed successfully.")

if __name__ == "__main__":
    main()
