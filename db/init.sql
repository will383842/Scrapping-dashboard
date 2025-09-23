-- =================================================================
-- SCHEMA BASE DE DONNÉES OPTIMISÉ PRODUCTION
-- Version: 2.0 Production-Ready
-- Date: 2025-09-23
-- =================================================================

-- Extension pour UUID si nécessaire
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

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

-- Contrainte d'unicité pour éviter les doublons
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

-- Indexes de performance critiques pour queue
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_queue_status_priority 
    ON queue(status, priority DESC, retry_count ASC, id ASC) 
    WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_queue_next_retry 
    ON queue(next_retry_at) 
    WHERE status = 'pending' AND next_retry_at IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_queue_created_at 
    ON queue(created_at DESC) 
    WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_queue_status_updated 
    ON queue(status, updated_at DESC) 
    WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_queue_theme_status 
    ON queue(theme, status) 
    WHERE deleted_at IS NULL;

-- =================================================================
-- TABLE CONTACTS - Contacts extraits
-- =================================================================
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

-- Indexes de performance pour contacts
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contacts_email_verified 
    ON contacts(email, verified) 
    WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contacts_country_theme 
    ON contacts(country, theme) 
    WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contacts_created_at 
    ON contacts(created_at DESC) 
    WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contacts_query_id 
    ON contacts(query_id) 
    WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contacts_theme_country 
    ON contacts(theme, country, created_at DESC) 
    WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contacts_name_org_trgm 
    ON contacts USING gin((name || ' ' || COALESCE(org, '')) gin_trgm_ops) 
    WHERE deleted_at IS NULL;

-- Index pour recherche full-text (optionnel)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contacts_fulltext 
    ON contacts USING gin(to_tsvector('english', 
        COALESCE(name, '') || ' ' || 
        COALESCE(org, '') || ' ' || 
        COALESCE(email, '')
    )) WHERE deleted_at IS NULL;

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
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_proxies_active_priority 
    ON proxies(active, priority ASC, last_used_at ASC NULLS FIRST) 
    WHERE active = TRUE;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_proxies_performance 
    ON proxies(active, success_rate DESC, response_time_ms ASC) 
    WHERE active = TRUE;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_proxies_country_active 
    ON proxies(country_code, active) 
    WHERE active = TRUE;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_proxies_last_test 
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
    created_by TEXT DEFAULT 'dashboard'
);

-- Indexes pour sessions
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_domain_active 
    ON sessions(domain, active) 
    WHERE active = TRUE;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_validation 
    ON sessions(validation_status, last_validated_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_usage 
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
    ('js_pages_limit', COALESCE(NULLIF('${JS_PAGES_LIMIT}',''), '1000'), 'Limite quotidienne pages JS', 'limits'),
    ('max_concurrent_jobs', '5', 'Nombre maximum de jobs simultanés', 'performance'),
    ('default_retry_attempts', '3', 'Nombre de tentatives par défaut', 'scheduler'),
    ('health_check_interval', '60', 'Intervalle health check (secondes)', 'monitoring'),
    ('cleanup_retention_days', '30', 'Rétention des logs (jours)', 'maintenance'),
    ('enable_email_alerts', 'false', 'Activer les alertes email', 'alerts'),
    ('smtp_host', '', 'Serveur SMTP pour alertes', 'alerts'),
    ('alert_email_recipients', '', 'Destinataires alertes (JSON array)', 'alerts')
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

-- Partitioning par mois pour les logs (optionnel pour gros volumes)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_timestamp 
    ON system_logs(timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_level_component 
    ON system_logs(level, component, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_job_id 
    ON system_logs(job_id, timestamp DESC) 
    WHERE job_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_correlation 
    ON system_logs(correlation_id) 
    WHERE correlation_id IS NOT NULL;

-- =================================================================
-- TABLE METRICS - Métriques de performance (optionnel)
-- =================================================================
CREATE TABLE IF NOT EXISTS metrics (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    metric_name TEXT NOT NULL,
    metric_value FLOAT NOT NULL,
    metric_type TEXT CHECK (metric_type IN ('counter', 'gauge', 'histogram')),
    labels JSONB, -- Étiquettes additionnelles
    job_id INTEGER,
    component TEXT
);

-- Index pour métriques
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_metrics_name_timestamp 
    ON metrics(metric_name, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_metrics_component 
    ON metrics(component, timestamp DESC) 
    WHERE component IS NOT NULL;

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

-- Vue jobs problématiques
CREATE OR REPLACE VIEW problematic_jobs AS
SELECT 
    id,
    url,
    status,
    retry_count,
    max_retries,
    last_error,
    next_retry_at,
    created_at,
    updated_at,
    CASE 
        WHEN retry_count >= max_retries THEN 'max_retries_reached'
        WHEN status = 'failed' AND retry_count < max_retries THEN 'will_retry'
        WHEN status = 'in_progress' AND updated_at < NOW() - INTERVAL '1 hour' THEN 'stuck'
        ELSE 'normal'
    END as problem_type
FROM queue 
WHERE status IN ('failed', 'in_progress')
   OR (status = 'pending' AND retry_count > 0)
ORDER BY updated_at DESC;

-- Vue top domaines
CREATE OR REPLACE VIEW top_domains AS
SELECT 
    SPLIT_PART(SPLIT_PART(url, '/', 3), ':', 1) as domain,
    COUNT(*) as total_jobs,
    COUNT(*) FILTER (WHERE status = 'done') as successful_jobs,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_jobs,
    AVG(contacts_extracted) FILTER (WHERE contacts_extracted > 0) as avg_contacts_per_job,
    MAX(updated_at) as last_activity
FROM queue 
WHERE deleted_at IS NULL
GROUP BY domain
HAVING COUNT(*) >= 5
ORDER BY successful_jobs DESC, total_jobs DESC;

-- =================================================================
-- FONCTIONS UTILITAIRES
-- =================================================================

-- Fonction de nettoyage automatique
CREATE OR REPLACE FUNCTION cleanup_old_data()
RETURNS INTEGER AS $$
DECLARE
    deleted_logs INTEGER;
    deleted_metrics INTEGER;
BEGIN
    -- Suppression des anciens logs (>90 jours)
    DELETE FROM system_logs WHERE timestamp < NOW() - INTERVAL '90 days';
    GET DIAGNOSTICS deleted_logs = ROW_COUNT;
    
    -- Suppression des anciennes métriques (>30 jours) 
    DELETE FROM metrics WHERE timestamp < NOW() - INTERVAL '30 days';
    GET DIAGNOSTICS deleted_metrics = ROW_COUNT;
    
    -- Log de l'opération
    INSERT INTO system_logs (level, component, message, details) VALUES (
        'INFO', 
        'maintenance', 
        'Nettoyage automatique effectué',
        jsonb_build_object('deleted_logs', deleted_logs, 'deleted_metrics', deleted_metrics)
    );
    
    RETURN deleted_logs + deleted_metrics;
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
CREATE TRIGGER update_queue_updated_at BEFORE UPDATE ON queue
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON contacts  
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_proxies_updated_at BEFORE UPDATE ON proxies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_settings_updated_at BEFORE UPDATE ON settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =================================================================
-- PERMISSIONS ET SÉCURITÉ (optionnel)
-- =================================================================

-- Utilisateur en lecture seule pour monitoring
-- CREATE USER scraper_readonly WITH PASSWORD 'readonly_password';
-- GRANT CONNECT ON DATABASE scraper_pro TO scraper_readonly;
-- GRANT USAGE ON SCHEMA public TO scraper_readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO scraper_readonly;

-- =================================================================
-- OPTIMISATIONS FINALES
-- =================================================================

-- Mise à jour des statistiques pour l'optimiseur
ANALYZE queue;
ANALYZE contacts; 
ANALYZE proxies;
ANALYZE sessions;
ANALYZE settings;

-- Configuration optimale PostgreSQL (à ajouter dans postgresql.conf)
-- shared_preload_libraries = 'pg_stat_statements'
-- pg_stat_statements.track = all
-- log_statement = 'mod'
-- log_min_duration_statement = 1000

COMMIT;