-- Migration: Enforce Word Boundaries in Notification Matching

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
          j.title ~* ('(^|[^a-zA-Z0-9_])' || regexp_replace(s.keyword, '([.\+*?\[\](){}|^$])', '\\\1', 'g') || '([^a-zA-Z0-9_]|$)')
          OR j.description ~* ('(^|[^a-zA-Z0-9_])' || regexp_replace(s.keyword, '([.\+*?\[\](){}|^$])', '\\\1', 'g') || '([^a-zA-Z0-9_]|$)')
          OR j.company_name ~* ('(^|[^a-zA-Z0-9_])' || regexp_replace(s.keyword, '([.\+*?\[\](){}|^$])', '\\\1', 'g') || '([^a-zA-Z0-9_]|$)')
      )
)
SELECT 
    chat_id,
    array_agg(job_id) AS job_ids,
    string_agg(
        '• *' || replace(replace(replace(replace(title, '*', '\*'), '_', '\_'), '[', '\['), '`', '\`') || '*' || chr(10) ||
        '  Company: ' || replace(replace(replace(replace(company_name, '*', '\*'), '_', '\_'), '[', '\['), '`', '\`') || chr(10) ||
        '  Source: ' || upper(source) || chr(10) ||
        '  Posted: ' || coalesce(to_char(posted_date, 'DD-Mon-YYYY'), 'N/A') || chr(10) ||
        '  Deadline: ' || coalesce(to_char(expiry_date, 'DD-Mon-YYYY'), 'N/A') || chr(10) ||
        '  Link: [Apply Here](' || url || ')',
        chr(10) || chr(10)
    ) AS jobs_markdown
FROM matched_pairs
GROUP BY chat_id;
