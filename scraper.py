import re
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from utils import get_logger, supabase

# Get scraper-specific logger
logger = get_logger("scraper")

def parse_date(date_str, format_str):
    """
    Parses a date string with a given format and standardizes it to YYYY-MM-DD.
    """
    try:
        return datetime.strptime(date_str.strip(), format_str).strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return None

def parse_infopark_date(date_str):
    """
    Attempts to parse raw Infopark dates using multiple common formatting structures.
    """
    # Try DD-MM-YYYY
    parsed = parse_date(date_str, "%d-%m-%Y")
    if parsed:
        return parsed
    # Try DD MMM YYYY (e.g., 02 Jun 2026)
    parsed = parse_date(date_str, "%d %b %Y")
    if parsed:
        return parsed
    return None

def scrape_technopark(max_pages=100):
    """
    Queries the Technopark API page by page up to a safety max limit.
    Retrieves job ID, title, company name, URL, and raw dates.
    """
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
    while page <= max_pages:
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

def scrape_infopark(max_pages=100):
    """
    Parses Infopark HTML pages to extract job tables up to a safety max limit.
    """
    logger.info("Scraping Infopark Career Portal...")
    jobs = []
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    })

    page = 1
    while page <= max_pages:
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

def main():
    logger.info("Starting Scraper Job...")
    
    # 1. Scrape Portals
    tp_jobs = scrape_technopark()
    ip_jobs = scrape_infopark()
    all_scraped_jobs = tp_jobs + ip_jobs
    
    logger.info(f"Total scraped jobs: {len(all_scraped_jobs)} (Technopark: {len(tp_jobs)}, Infopark: {len(ip_jobs)})")
    
    if not all_scraped_jobs:
        logger.info("No jobs scraped. Exiting scraper.")
        return
        
    # 2. Bulk Upsert into Supabase
    try:
        logger.info("Bulk upserting jobs into database...")
        # Chunk upsert in case of a very large list
        chunk_size = 100
        for i in range(0, len(all_scraped_jobs), chunk_size):
            chunk = all_scraped_jobs[i:i + chunk_size]
            supabase.table("jobs").upsert(chunk).execute()
        logger.info("Jobs successfully bulk upserted.")
    except Exception as e:
        logger.error(f"Error bulk upserting jobs: {e}")
        
    # 3. Database Maintenance: Clean up jobs older than 90 days
    try:
        logger.info("Cleaning up jobs older than 90 days...")
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        supabase.table("jobs").delete().lt("scraped_at", cutoff).execute()
        logger.info("Database cleanup completed successfully.")
    except Exception as e:
        logger.error(f"Error cleaning up old jobs: {e}")
            
    logger.info("Scraper Job completed successfully.")

if __name__ == "__main__":
    main()
