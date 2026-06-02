-- Refine pending_notifications view to only notify from new jobs onwards
CREATE OR REPLACE VIEW pending_notifications AS
SELECT 
    s.chat_id,
    s.keyword,
    j.job_id,
    j.title,
    j.description,
    j.url,
    j.source
FROM subscriptions s
JOIN jobs j ON j.source = ANY(s.sources)
LEFT JOIN notifications_sent n ON n.chat_id = s.chat_id AND n.job_id = j.job_id
WHERE n.job_id IS NULL
  AND j.scraped_at >= s.created_at
  AND (
      j.title ILIKE '%' || s.keyword || '%' 
      OR j.description ILIKE '%' || s.keyword || '%'
  );
