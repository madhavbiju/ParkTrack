-- Migration: Consolidated Daily Digest Refactoring

-- 1. Drop old pending_notifications view
DROP VIEW IF EXISTS pending_notifications;

-- 2. Clear out jobs to allow clean addition of company_name NOT NULL column
TRUNCATE TABLE jobs CASCADE;

-- 3. Modify jobs table
ALTER TABLE jobs ADD COLUMN company_name TEXT NOT NULL;
ALTER TABLE jobs ADD COLUMN posted_date DATE;
ALTER TABLE jobs ADD COLUMN expiry_date DATE;

-- 4. Create standard B-Tree index on company_name
CREATE INDEX IF NOT EXISTS idx_jobs_company_name ON jobs (company_name);

-- 5. Create new pending_notifications_consolidated view
CREATE OR REPLACE VIEW pending_notifications_consolidated AS
WITH matched_pairs AS (
    SELECT DISTINCT
        s.chat_id,
        j.job_id,
        j.title,
        j.company_name,
        j.source,
        j.posted_date,
        j.expiry_date,
        j.url
    FROM subscriptions s
    JOIN jobs j ON j.source = ANY(s.sources)
    LEFT JOIN notifications_sent n ON n.chat_id = s.chat_id AND n.job_id = j.job_id
    WHERE n.job_id IS NULL
      AND j.scraped_at >= s.created_at
      AND (
          j.title ILIKE '%' || s.keyword || '%' 
          OR j.description ILIKE '%' || s.keyword || '%'
          OR j.company_name ILIKE '%' || s.keyword || '%'
      )
)
SELECT 
    chat_id,
    array_agg(job_id) AS job_ids,
    string_agg(
        '• *' || replace(replace(replace(replace(title, '*', '\*'), '_', '\_'), '[', '\['), '`', '\`') || '* at _' || replace(replace(replace(replace(company_name, '*', '\*'), '_', '\_'), '[', '\['), '`', '\`') || '_ (' || upper(source) || ')' || chr(10) ||
        '  📅 Posted: ' || coalesce(to_char(posted_date, 'DD-Mon-YYYY'), 'N/A') || '  |  ⏳ Deadline: ' || coalesce(to_char(expiry_date, 'DD-Mon-YYYY'), 'N/A') || chr(10) ||
        '  🔗 [Apply Here](' || url || ')',
        chr(10) || chr(10)
    ) AS jobs_markdown
FROM matched_pairs
GROUP BY chat_id;
