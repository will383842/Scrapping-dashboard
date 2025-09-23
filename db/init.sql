
CREATE TABLE IF NOT EXISTS queue (
  id SERIAL PRIMARY KEY,
  url TEXT,
  country_filter TEXT,
  lang_filter TEXT,
  theme TEXT,
  source_scope TEXT,
  query_group_id TEXT,
  use_js BOOLEAN DEFAULT FALSE,
  max_pages_per_domain INTEGER DEFAULT 15,
  cost_hint TEXT,
  target_count INTEGER DEFAULT 0,
  logic_mode TEXT DEFAULT 'or',
  status TEXT DEFAULT 'pending',
  last_error TEXT,
  last_run_at TIMESTAMP,
  added_at TIMESTAMP DEFAULT now(),
  deleted_at TIMESTAMP,
  min_rerun_hours INTEGER DEFAULT 168
);

CREATE UNIQUE INDEX IF NOT EXISTS queue_uniqueness
ON queue (
  COALESCE(url,''),
  COALESCE(country_filter,''),
  COALESCE(lang_filter,''),
  COALESCE(theme,''),
  COALESCE(query_group_id,''),
  COALESCE(logic_mode,''),
  use_js,
  max_pages_per_domain
)
WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS contacts (
  id BIGSERIAL PRIMARY KEY,
  name TEXT,
  org TEXT,
  email TEXT UNIQUE NOT NULL,
  languages TEXT,
  phone TEXT,
  country TEXT,
  url TEXT,
  theme TEXT,
  source TEXT,
  page_lang TEXT,
  raw_text TEXT,
  query_id INTEGER,
  seed_url TEXT,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  deleted_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proxies (
  id SERIAL PRIMARY KEY,
  label TEXT,
  scheme TEXT DEFAULT 'http',
  host TEXT,
  port INTEGER,
  username TEXT,
  password TEXT,
  active BOOLEAN DEFAULT true,
  priority INTEGER DEFAULT 10,
  last_used_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS settings ( key TEXT PRIMARY KEY, value TEXT );
INSERT INTO settings(key,value) VALUES ('scheduler_paused','false') ON CONFLICT(key) DO NOTHING;
INSERT INTO settings(key,value) VALUES ('js_reset_day','') ON CONFLICT(key) DO NOTHING;
INSERT INTO settings(key,value) VALUES ('js_pages_used','0') ON CONFLICT(key) DO NOTHING;
INSERT INTO settings(key,value) VALUES ('js_pages_limit', COALESCE(NULLIF('${JS_PAGES_LIMIT}',''),'300')) ON CONFLICT(key) DO NOTHING;

CREATE INDEX IF NOT EXISTS contacts_query_idx ON contacts(query_id) WHERE deleted_at IS NULL;


-- Sessions for authenticated scraping
CREATE TABLE IF NOT EXISTS sessions (
  id SERIAL PRIMARY KEY,
  domain TEXT NOT NULL,
  type TEXT DEFAULT 'storage_state', -- 'storage_state' or 'cookies'
  file_path TEXT NOT NULL,
  active BOOLEAN DEFAULT true,
  notes TEXT,
  created_at TIMESTAMP DEFAULT now(),
  last_used_at TIMESTAMP
);

-- Attach a session to a queue job
DO $$ BEGIN
  ALTER TABLE queue ADD COLUMN session_id INTEGER;
EXCEPTION WHEN duplicate_column THEN
  NULL;
END $$;

CREATE INDEX IF NOT EXISTS sessions_domain_idx ON sessions(domain);

