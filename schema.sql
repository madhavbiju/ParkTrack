-- Database setup schema for Park Track

-- 1. Create the jobs table
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    url TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('technopark', 'infopark')),
    scraped_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Create the subscriptions table
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    keyword TEXT NOT NULL,
    sources TEXT[] NOT NULL DEFAULT '{technopark,infopark}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_chat_keyword UNIQUE (chat_id, keyword)
);

-- 3. Create the notifications_sent table
CREATE TABLE IF NOT EXISTS notifications_sent (
    chat_id BIGINT NOT NULL,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT pk_notifications_sent PRIMARY KEY (chat_id, job_id)
);

-- 4. Create Indexes for optimization
-- Optimize search on jobs title and description
CREATE INDEX IF NOT EXISTS idx_jobs_search ON jobs (title, description);

-- Optimize queries on user keywords
CREATE INDEX IF NOT EXISTS idx_subscriptions_keyword ON subscriptions (keyword);

-- Optimize GIN search for array containment on source restriction
CREATE INDEX IF NOT EXISTS idx_subscriptions_sources ON subscriptions USING GIN (sources);

-- 5. Create Pending Notifications View
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
  AND (
      j.title ILIKE '%' || s.keyword || '%' 
      OR j.description ILIKE '%' || s.keyword || '%'
  );
