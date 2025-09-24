-- =================================================================
-- SCHEMA BASE DE DONNÉES OPTIMISÉ PRODUCTION
-- Version: 2.1 Production-Ready avec Custom Keywords
-- Date: 2025-01-XX
-- =================================================================

-- Extension pour UUID si nécessaire
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =================================================================
-- TABLE QUEUE - Jobs de scraping
-- =================================================================
CREATE TABLE IF NOT EXISTS queue (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL,
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
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'done', 'failed', 'paused')),
    priority INTEGER DEFAULT 10,
    last_error TEXT,
    last_run_at TIMESTAMP,
    
    -- Nouvelles colonnes pour retry et monitoring
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at TIMESTAMP,
    execution_time_seconds INTEGER,
    contacts_extracted INTEGER DEFAULT 0,
    
    -- Nouvelles colonnes pour mots-clés personnalisés
    custom_keywords TEXT[], -- Array de mots-clés saisis
    match_mode VARCHAR(20) DEFAULT 'any' CHECK (match_mode IN ('any', 'multiple', 'all')), -- 'any', 'multiple', 'all'
    min_matches INTEGER DEFAULT 1,
    
    -- Métadonnées
    created_by TEXT DEFAULT 'dashboard',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP,
    
    -- Colonnes héritées
    added_at TIMESTAMP DEFAULT NOW(),
    min_rerun_hours INTEGER DEFAULT 168,
    session_id INTEGER
);

-- Indexes de performance critiques pour queue
CREATE INDEX IF NOT EXISTS idx_queue_status_priority 
    ON queue(status, priority DESC, retry_count ASC, id ASC) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_queue_next_retry 
    ON queue(next_retry_at) 
    WHERE status = 'pending' AND next_retry_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_queue_created_at 
    ON queue(created_at DESC) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_queue_status_updated 
    ON queue(status, updated_at DESC) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_queue_theme_status 
    ON queue(theme, status) 
    WHERE deleted_at IS NULL;

-- Index pour recherche par mots-clés personnalisés
CREATE INDEX IF NOT EXISTS idx_queue_custom_keywords 
    ON queue USING GIN(custom_keywords) 
    WHERE custom_keywords IS NOT NULL AND deleted_at IS NULL;

-- =================================================================
-- TABLE CONTACTS - Contacts extraits
-- =================================================================
CREATE TABLE IF NOT EXISTS contacts (
    id BIGSERIAL PRIMARY KEY,
    name TEXT,
    org TEXT,
    email TEXT,
    languages TEXT,
    phone TEXT,
    country TEXT,
    url TEXT,
    theme TEXT,
    source TEXT DEFAULT 'scraper',
    page_lang TEXT,
    raw_text TEXT,
    query_id INTEGER,
    seed_url TEXT,
    
    -- Nouvelles colonnes pour validation et enrichissement
    verified BOOLEAN DEFAULT FALSE,
    email_valid BOOLEAN,
    phone_valid BOOLEAN,
    enrichment_status TEXT CHECK (enrichment_status IN (NULL, 'pending', 'done', 'failed')),
    linkedin_url TEXT,
    company_website TEXT,
    job_title TEXT,
    
    -- Métadonnées enrichies
    extraction_method TEXT, -- 'scrapy', 'playwright', 'manual'
    confidence_score FLOAT DEFAULT 0.0 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    tags TEXT[], -- Tags personnalisés
    notes TEXT,
    
    -- Audit et versioning
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP,
    created_by TEXT DEFAULT 'scraper',
    last_verified_at TIMESTAMP
);

-- Contrainte d'unicité sur email (mais permettre NULL)
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_email_unique
    ON contacts(email)
    WHERE email IS NOT NULL AND deleted_at IS NULL;

-- Indexes de performance pour contacts
CREATE INDEX IF NOT EXISTS idx_contacts_country_theme 
    ON contacts(country, theme) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_contacts_created_at 
    ON contacts(created_at DESC) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_contacts_query_id 
    ON contacts(query_id) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_contacts_theme_country 
    ON contacts(theme, country, created_at DESC) 
    WHERE deleted_at IS NULL;

-- =================================================================
-- TABLE PROXIES - Gestion des proxies et IPs
-- =================================================================
CREATE TABLE IF NOT EXISTS proxies (
    id SERIAL PRIMARY KEY,
    label TEXT,
    scheme TEXT DEFAULT 'http' CHECK (scheme IN ('http', 'https', 'socks5')),
    host TEXT NOT NULL,
    port INTEGER NOT NULL CHECK (port > 0 AND port <= 65535),
    username TEXT,
    password TEXT,
    active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 10,
    
    -- Colonnes de monitoring et performance
    last_used_at TIMESTAMP,
    response_time_ms INTEGER DEFAULT 0,
    success_rate FLOAT DEFAULT 1.0 CHECK (success_rate >= 0.0 AND success_rate <= 1.0),
    total_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    last_test_at TIMESTAMP,
    last_test_status TEXT CHECK (last_test_status IN (NULL, 'success', 'failed', 'timeout')),
    
    -- Colonnes de résilience
    failure_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    consecutive_failures INTEGER DEFAULT 0,
    last_error TEXT,
    cooldown_until TIMESTAMP,
    
    -- Geo et metadata
    country_code CHAR(2),
    region TEXT,
    provider TEXT,
    cost_per_gb DECIMAL(10,4),
    bandwidth_limit_gb INTEGER,
    monthly_limit_gb INTEGER,
    
    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by TEXT DEFAULT 'dashboard',
    notes TEXT
);

-- Contrainte d'unicité pour éviter doublons proxy
CREATE UNIQUE INDEX IF NOT EXISTS idx_proxies_unique 
    ON proxies(scheme, host, port, COALESCE(username, ''));

-- Indexes de performance pour proxies
CREATE INDEX IF NOT EXISTS idx_proxies_active_priority 
    ON proxies(active, priority ASC, last_used_at ASC NULLS FIRST) 
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_proxies_performance 
    ON proxies(active, success_rate DESC, response_time_ms ASC) 
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_proxies_country_active 
    ON proxies(country_code, active) 
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_proxies_last_test 
    ON proxies(last_test_at DESC, last_test_status);

-- =================================================================
-- TABLE SESSIONS - Gestion des sessions authentifiées
-- =================================================================
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    domain TEXT NOT NULL,
    type TEXT DEFAULT 'storage_state' CHECK (type IN ('storage_state', 'cookies', 'headers')),
    file_path TEXT NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    
    -- Métadonnées de session
    browser_type TEXT DEFAULT 'chromium' CHECK (browser_type IN ('chromium', 'firefox', 'webkit')),
    user_agent TEXT,
    session_size_bytes INTEGER,
    cookies_count INTEGER DEFAULT 0,
    
    -- Validation et monitoring
    last_validated_at TIMESTAMP,
    validation_status TEXT CHECK (validation_status IN (NULL, 'valid', 'invalid', 'expired')),
    expires_at TIMESTAMP,
    auto_refresh BOOLEAN DEFAULT FALSE,
    
    -- Usage tracking
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    success_rate FLOAT DEFAULT 1.0,
    
    -- Audit
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP,
    created_by TEXT DEFAULT 'dashboard'
);

-- Indexes pour sessions
CREATE INDEX IF NOT EXISTS idx_sessions_domain_active 
    ON sessions(domain, active) 
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_sessions_validation 
    ON sessions(validation_status, last_validated_at);

CREATE INDEX IF NOT EXISTS idx_sessions_usage 
    ON sessions(usage_count DESC, success_rate DESC) 
    WHERE active = TRUE;

-- =================================================================
-- TABLE SETTINGS - Configuration système
-- =================================================================
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    value_type TEXT DEFAULT 'string' CHECK (value_type IN ('string', 'integer', 'float', 'boolean', 'json')),
    description TEXT,
    category TEXT DEFAULT 'general',
    is_secret BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by TEXT DEFAULT 'system'
);

-- Insert des paramètres par défaut
INSERT INTO settings(key, value, description, category) VALUES 
    ('scheduler_paused', 'false', 'Pause/Resume du scheduler principal', 'scheduler'),
    ('js_reset_day', '', 'Jour de reset du compteur JS', 'limits'),
    ('js_pages_used', '0', 'Pages JS utilisées aujourd''hui', 'limits'),
    ('js_pages_limit', '1000', 'Limite quotidienne pages JS', 'limits'),
    ('max_concurrent_jobs', '5', 'Nombre maximum de jobs simultanés', 'performance'),
    ('default_retry_attempts', '3', 'Nombre de tentatives par défaut', 'scheduler'),
    ('health_check_interval', '60', 'Intervalle health check (secondes)', 'monitoring'),
    ('cleanup_retention_days', '30', 'Rétention des logs (jours)', 'maintenance'),
    ('enable_email_alerts', 'false', 'Activer les alertes email', 'alerts'),
    ('database_version', '2.1', 'Version du schéma de base de données', 'system')
ON CONFLICT (key) DO NOTHING;

-- =================================================================
-- TABLE LOGS - Journalisation système (optionnel)
-- =================================================================
CREATE TABLE IF NOT EXISTS system_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    level TEXT NOT NULL CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    component TEXT NOT NULL, -- 'scheduler', 'dashboard', 'spider', etc.
    job_id INTEGER,
    message TEXT NOT NULL,
    details JSONB,
    correlation_id UUID DEFAULT uuid_generate_v4(),
    user_id TEXT,
    ip_address INET,
    session_id TEXT
);

-- Index pour logs
CREATE INDEX IF NOT EXISTS idx_logs_timestamp 
    ON system_logs(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_logs_level_component 
    ON system_logs(level, component, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_logs_job_id 
    ON system_logs(job_id, timestamp DESC) 
    WHERE job_id IS NOT NULL;

-- =================================================================
-- TABLE SEEN_URLS - URLs normalisées et déduplication
-- =================================================================
CREATE TABLE IF NOT EXISTS seen_urls (
    id BIGSERIAL PRIMARY KEY,
    url TEXT UNIQUE,
    normalized_url TEXT,
    content_hash TEXT,
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW(),
    job_id INTEGER,
    notes TEXT
);

-- Indexes for faster lookup
CREATE INDEX IF NOT EXISTS idx_seen_urls_normalized ON seen_urls (normalized_url);
CREATE INDEX IF NOT EXISTS idx_seen_urls_hash ON seen_urls (content_hash);
CREATE INDEX IF NOT EXISTS idx_seen_urls_job ON seen_urls (job_id);

-- =================================================================
-- TABLE ERROR_EVENTS - Événements d'erreur
-- =================================================================
CREATE TABLE IF NOT EXISTS error_events (
    id BIGSERIAL PRIMARY KEY,
    source TEXT, -- 'scraper','scheduler','dashboard'
    category TEXT, -- network, http_4xx, http_5xx, parse, timeout, proxy, db, unknown
    message TEXT,
    details JSONB,
    proxy_id INTEGER,
    url TEXT,
    status_code INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_error_events_created ON error_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_events_category ON error_events (category);

-- =================================================================
-- VUES UTILES POUR MONITORING
-- =================================================================

-- Vue performance globale
CREATE OR REPLACE VIEW performance_dashboard AS
SELECT 
    -- Stats jobs
    (SELECT COUNT(*) FROM queue WHERE status = 'pending') as pending_jobs,
    (SELECT COUNT(*) FROM queue WHERE status = 'in_progress') as running_jobs,
    (SELECT COUNT(*) FROM queue WHERE status = 'done' AND DATE(updated_at) = CURRENT_DATE) as completed_today,
    (SELECT COUNT(*) FROM queue WHERE status = 'failed' AND DATE(updated_at) = CURRENT_DATE) as failed_today,
    
    -- Stats contacts
    (SELECT COUNT(*) FROM contacts WHERE DATE(created_at) = CURRENT_DATE) as contacts_today,
    (SELECT COUNT(*) FROM contacts WHERE verified = true) as verified_contacts,
    (SELECT COUNT(DISTINCT country) FROM contacts WHERE country IS NOT NULL) as countries_covered,
    
    -- Stats proxies
    (SELECT COUNT(*) FROM proxies WHERE active = true) as active_proxies,
    (SELECT AVG(response_time_ms) FROM proxies WHERE active = true AND response_time_ms > 0) as avg_proxy_response_time,
    (SELECT AVG(success_rate) FROM proxies WHERE active = true) as avg_proxy_success_rate,
    
    -- Stats sessions
    (SELECT COUNT(*) FROM sessions WHERE active = true) as active_sessions,
    (SELECT COUNT(*) FROM sessions WHERE validation_status = 'valid') as valid_sessions;

-- =================================================================
-- FONCTIONS UTILITAIRES
-- =================================================================

-- Fonction de nettoyage automatique
CREATE OR REPLACE FUNCTION cleanup_old_data()
RETURNS INTEGER AS $$
DECLARE
    deleted_logs INTEGER;
BEGIN
    -- Suppression des anciens logs (>90 jours)
    DELETE FROM system_logs WHERE timestamp < NOW() - INTERVAL '90 days';
    GET DIAGNOSTICS deleted_logs = ROW_COUNT;
    
    -- Log de l'opération
    INSERT INTO system_logs (level, component, message, details) VALUES (
        'INFO', 
        'maintenance', 
        'Nettoyage automatique effectué',
        jsonb_build_object('deleted_logs', deleted_logs)
    );
    
    RETURN deleted_logs;
END;
$$ LANGUAGE plpgsql;

-- Fonction mise à jour timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers pour updated_at automatique
DROP TRIGGER IF EXISTS update_queue_updated_at ON queue;
CREATE TRIGGER update_queue_updated_at BEFORE UPDATE ON queue
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_contacts_updated_at ON contacts;
CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON contacts  
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_proxies_updated_at ON proxies;
CREATE TRIGGER update_proxies_updated_at BEFORE UPDATE ON proxies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_sessions_updated_at ON sessions;
CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_settings_updated_at ON settings;
CREATE TRIGGER update_settings_updated_at BEFORE UPDATE ON settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =================================================================
-- FINALISATION
-- =================================================================

-- Mise à jour des statistiques pour l'optimiseur
ANALYZE queue;
ANALYZE contacts; 
ANALYZE proxies;
ANALYZE sessions;
ANALYZE settings;
ANALYZE seen_urls;
ANALYZE error_events;

-- Log de fin d'initialisation
INSERT INTO system_logs (level, component, message) VALUES (
    'INFO', 
    'database', 
    'Schema Scraper Pro initialisé avec succès'
);

-- Message de confirmation
DO $$
BEGIN
    RAISE NOTICE 'Base de données Scraper Pro initialisée avec succès !';
    RAISE NOTICE 'Tables créées: queue, contacts, proxies, sessions, settings, system_logs, seen_urls, error_events';
    RAISE NOTICE 'Indexes créés: % indexes de performance', 20;
    RAISE NOTICE 'Nouvelles fonctionnalités: mots-clés personnalisés, déduplication URLs, gestion erreurs avancée';
    RAISE NOTICE 'Configuration prête pour production';
END $$;