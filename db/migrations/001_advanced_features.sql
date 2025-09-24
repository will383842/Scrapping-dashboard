-- =================================================================
-- MIGRATION 001 - Advanced Features Implementation
-- Version: 2.1 - Proxy Management, Anti-Doublons, Checkpointing
-- Date: 2025-01-XX
-- =================================================================

BEGIN;

-- Vérifier la version actuelle
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM settings WHERE key = 'database_version') THEN
        INSERT INTO settings (key, value, description, category) 
        VALUES ('database_version', '2.0', 'Version initiale', 'system');
    END IF;
END $$;

-- =================================================================
-- ÉTENDRE TABLE QUEUE - Nouvelles fonctionnalités
-- =================================================================

-- Ajouter colonnes manquantes à queue
DO $$
BEGIN
    -- Colonnes de rotation proxy
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='queue' AND column_name='proxy_rotation_mode') THEN
        ALTER TABLE queue ADD COLUMN proxy_rotation_mode TEXT DEFAULT 'per_spider' CHECK (proxy_rotation_mode IN ('per_spider', 'per_request', 'sticky'));
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='queue' AND column_name='sticky_ttl_seconds') THEN
        ALTER TABLE queue ADD COLUMN sticky_ttl_seconds INTEGER DEFAULT 180;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='queue' AND column_name='proxy_country_filter') THEN
        ALTER TABLE queue ADD COLUMN proxy_country_filter TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='queue' AND column_name='proxy_pool_tag') THEN
        ALTER TABLE queue ADD COLUMN proxy_pool_tag TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='queue' AND column_name='rps_per_proxy') THEN
        ALTER TABLE queue ADD COLUMN rps_per_proxy DECIMAL(5,2) DEFAULT 2.0;
    END IF;
    
    -- Colonnes de retry
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='queue' AND column_name='retry_strategy') THEN
        ALTER TABLE queue ADD COLUMN retry_strategy TEXT DEFAULT 'exponential' CHECK (retry_strategy IN ('exponential', 'linear', 'fixed'));
    END IF;
    
    -- Colonnes de localisation
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='queue' AND column_name='user_agent_country') THEN
        ALTER TABLE queue ADD COLUMN user_agent_country TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='queue' AND column_name='accept_language') THEN
        ALTER TABLE queue ADD COLUMN accept_language TEXT;
    END IF;
    
    -- Colonnes de checkpointing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='queue' AND column_name='checkpoint_data') THEN
        ALTER TABLE queue ADD COLUMN checkpoint_data JSONB DEFAULT '{}';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='queue' AND column_name='phase_status') THEN
        ALTER TABLE queue ADD COLUMN phase_status JSONB DEFAULT '{"search": "pending", "listing": "pending", "detail": "pending", "download": "pending"}';
    END IF;
END $$;

-- =================================================================
-- ÉTENDRE TABLE PROXIES - Fonctionnalités avancées
-- =================================================================

DO $$
BEGIN
    -- Colonnes de poids et priorité
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='proxies' AND column_name='weight') THEN
        ALTER TABLE proxies ADD COLUMN weight INTEGER DEFAULT 100 CHECK (weight > 0);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='proxies' AND column_name='cooldown_until') THEN
        ALTER TABLE proxies ADD COLUMN cooldown_until TIMESTAMP;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='proxies' AND column_name='rps_max') THEN
        ALTER TABLE proxies ADD COLUMN rps_max DECIMAL(5,2) DEFAULT 2.0 CHECK (rps_max > 0);
    END IF;
    
    -- Colonnes sticky
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='proxies' AND column_name='sticky_group') THEN
        ALTER TABLE proxies ADD COLUMN sticky_group TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='proxies' AND column_name='sticky_tag') THEN
        ALTER TABLE proxies ADD COLUMN sticky_tag TEXT;
    END IF;
    
    -- Colonnes métriques avancées
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='proxies' AND column_name='successful_requests') THEN
        ALTER TABLE proxies ADD COLUMN successful_requests INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='proxies' AND column_name='consecutive_failures') THEN
        ALTER TABLE proxies ADD COLUMN consecutive_failures INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='proxies' AND column_name='last_success_at') THEN
        ALTER TABLE proxies ADD COLUMN last_success_at TIMESTAMP;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='proxies' AND column_name='last_failure_at') THEN
        ALTER TABLE proxies ADD COLUMN last_failure_at TIMESTAMP;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='proxies' AND column_name='average_latency_ms') THEN
        ALTER TABLE proxies ADD COLUMN average_latency_ms DECIMAL(8,2) DEFAULT 0;
    END IF;
    
    -- Colonnes circuit breaker
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='proxies' AND column_name='circuit_breaker_status') THEN
        ALTER TABLE proxies ADD COLUMN circuit_breaker_status TEXT DEFAULT 'closed' CHECK (circuit_breaker_status IN ('closed', 'open', 'half_open'));
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='proxies' AND column_name='circuit_breaker_failures') THEN
        ALTER TABLE proxies ADD COLUMN circuit_breaker_failures INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='proxies' AND column_name='circuit_breaker_last_failure') THEN
        ALTER TABLE proxies ADD COLUMN circuit_breaker_last_failure TIMESTAMP;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='proxies' AND column_name='circuit_breaker_next_attempt') THEN
        ALTER TABLE proxies ADD COLUMN circuit_breaker_next_attempt TIMESTAMP;
    END IF;
END $$;

-- =================================================================
-- ÉTENDRE TABLE CONTACTS - Déduplication et validation
-- =================================================================

DO $$
BEGIN
    -- Colonnes pour validation et enrichissement
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='contacts' AND column_name='contact_hash') THEN
        ALTER TABLE contacts ADD COLUMN contact_hash CHAR(64);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='contacts' AND column_name='duplicate_of') THEN
        ALTER TABLE contacts ADD COLUMN duplicate_of BIGINT REFERENCES contacts(id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='contacts' AND column_name='is_primary') THEN
        ALTER TABLE contacts ADD COLUMN is_primary BOOLEAN DEFAULT TRUE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='contacts' AND column_name='merge_count') THEN
        ALTER TABLE contacts ADD COLUMN merge_count INTEGER DEFAULT 0;
    END IF;
END $$;

-- =================================================================
-- ÉTENDRE TABLE SESSIONS - Validation avancée
-- =================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sessions' AND column_name='validation_frequency_hours') THEN
        ALTER TABLE sessions ADD COLUMN validation_frequency_hours INTEGER DEFAULT 24;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sessions' AND column_name='sticky_domain_pattern') THEN
        ALTER TABLE sessions ADD COLUMN sticky_domain_pattern TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sessions' AND column_name='max_concurrent_uses') THEN
        ALTER TABLE sessions ADD COLUMN max_concurrent_uses INTEGER DEFAULT 1;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sessions' AND column_name='current_uses') THEN
        ALTER TABLE sessions ADD COLUMN current_uses INTEGER DEFAULT 0;
    END IF;
END $$;

-- =================================================================
-- CRÉER NOUVELLES TABLES
-- =================================================================

-- Table seen_urls pour anti-doublons
CREATE TABLE IF NOT EXISTS seen_urls (
    id BIGSERIAL PRIMARY KEY,
    
    -- URL normalisée et identification
    original_url TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    url_hash CHAR(64) NOT NULL, -- SHA256 de l'URL normalisée
    domain TEXT NOT NULL,
    path_hash CHAR(64), -- SHA256 du path pour groupement
    
    -- Status et historique
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW(),
    visit_count INTEGER DEFAULT 1,
    last_status_code INTEGER,
    last_response_time_ms INTEGER,
    
    -- Résultats extraction
    contacts_extracted INTEGER DEFAULT 0,
    content_hash CHAR(64), -- SHA256 du contenu pour détecter changements
    content_size_bytes INTEGER,
    last_extraction_at TIMESTAMP,
    
    -- Métadonnées scraping
    job_id INTEGER REFERENCES queue(id) ON DELETE SET NULL,
    theme TEXT,
    language TEXT,
    country TEXT,
    
    -- Statut de traitement
    processing_status TEXT DEFAULT 'pending' CHECK (processing_status IN ('pending', 'processing', 'done', 'failed', 'skipped')),
    skip_reason TEXT, -- 'duplicate', 'no_contacts', 'error', 'robots_txt', etc.
    
    -- Refresh et revisit
    next_revisit_after TIMESTAMP,
    etag TEXT,
    last_modified TIMESTAMP,
    
    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Table job_runs pour journalisation
CREATE TABLE IF NOT EXISTS job_runs (
    id BIGSERIAL PRIMARY KEY,
    
    -- Référence job
    job_id INTEGER NOT NULL REFERENCES queue(id) ON DELETE CASCADE,
    run_number INTEGER NOT NULL, -- Numéro du run pour ce job
    
    -- Timestamps exécution
    started_at TIMESTAMP DEFAULT NOW(),
    finished_at TIMESTAMP,
    duration_seconds INTEGER,
    
    -- Configuration du run
    proxy_config JSONB DEFAULT '{}',
    spider_config JSONB DEFAULT '{}',
    retry_config JSONB DEFAULT '{}',
    
    -- Résultats
    status TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled', 'timeout')),
    pages_crawled INTEGER DEFAULT 0,
    contacts_extracted INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    
    -- Ressources utilisées
    proxies_used INTEGER DEFAULT 0,
    requests_count INTEGER DEFAULT 0,
    data_downloaded_bytes BIGINT DEFAULT 0,
    
    -- Erreur info
    error_message TEXT,
    error_details JSONB,
    
    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Table job_checkpoints pour reprise après coupure
CREATE TABLE IF NOT EXISTS job_checkpoints (
    id BIGSERIAL PRIMARY KEY,
    
    -- Référence job et run
    job_id INTEGER NOT NULL REFERENCES queue(id) ON DELETE CASCADE,
    run_id BIGINT NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    
    -- Phase et position
    phase TEXT NOT NULL CHECK (phase IN ('search', 'listing', 'detail', 'download')),
    checkpoint_key TEXT NOT NULL, -- 'page_42', 'cursor_abc123', 'scroll_1000', etc.
    
    -- Données de reprise
    checkpoint_data JSONB NOT NULL DEFAULT '{}',
    pages_processed INTEGER DEFAULT 0,
    items_processed INTEGER DEFAULT 0,
    
    -- Metadata
    checkpoint_at TIMESTAMP DEFAULT NOW(),
    valid_until TIMESTAMP, -- Expiration du checkpoint
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    resumed_from BOOLEAN DEFAULT FALSE,
    
    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Table proxy_stats pour métriques détaillées
CREATE TABLE IF NOT EXISTS proxy_stats (
    id BIGSERIAL PRIMARY KEY,
    
    -- Référence proxy
    proxy_id INTEGER NOT NULL REFERENCES proxies(id) ON DELETE CASCADE,
    
    -- Période de mesure
    measurement_date DATE DEFAULT CURRENT_DATE,
    hour_of_day INTEGER CHECK (hour_of_day >= 0 AND hour_of_day <= 23),
    
    -- Métriques de performance
    requests_count INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    timeout_requests INTEGER DEFAULT 0,
    
    -- Métriques de temps
    total_response_time_ms BIGINT DEFAULT 0,
    min_response_time_ms INTEGER,
    max_response_time_ms INTEGER,
    avg_response_time_ms DECIMAL(8,2),
    
    -- Métriques d'erreurs
    error_4xx_count INTEGER DEFAULT 0,
    error_5xx_count INTEGER DEFAULT 0,
    connection_errors INTEGER DEFAULT 0,
    
    -- Métriques rate limiting
    rate_limited_count INTEGER DEFAULT 0,
    captcha_count INTEGER DEFAULT 0,
    blocked_count INTEGER DEFAULT 0,
    
    -- Données transférées
    bytes_downloaded BIGINT DEFAULT 0,
    bytes_uploaded BIGINT DEFAULT 0,
    
    -- Timestamp
    created_at TIMESTAMP DEFAULT NOW()
);

-- Étendre table system_logs
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='system_logs' AND column_name='category') THEN
        ALTER TABLE system_logs ADD COLUMN category TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='system_logs' AND column_name='severity') THEN
        ALTER TABLE system_logs ADD COLUMN severity INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='system_logs' AND column_name='resolved') THEN
        ALTER TABLE system_logs ADD COLUMN resolved BOOLEAN DEFAULT FALSE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='system_logs' AND column_name='resolved_at') THEN
        ALTER TABLE system_logs ADD COLUMN resolved_at TIMESTAMP;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='system_logs' AND column_name='resolved_by') THEN
        ALTER TABLE system_logs ADD COLUMN resolved_by TEXT;
    END IF;
END $$;

-- =================================================================
-- CRÉER NOUVEAUX INDEXES
-- =================================================================

-- Indexes pour queue
CREATE INDEX IF NOT EXISTS idx_queue_proxy_rotation 
    ON queue(proxy_rotation_mode, proxy_country_filter, proxy_pool_tag) 
    WHERE deleted_at IS NULL;

-- Indexes pour proxies  
CREATE INDEX IF NOT EXISTS idx_proxies_selection 
    ON proxies(active, circuit_breaker_status, priority ASC, weight DESC, success_rate DESC, average_latency_ms ASC) 
    WHERE active = TRUE AND (cooldown_until IS NULL OR cooldown_until < NOW());

CREATE INDEX IF NOT EXISTS idx_proxies_sticky 
    ON proxies(sticky_group, sticky_tag, active) 
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_proxies_cooldown 
    ON proxies(cooldown_until) 
    WHERE cooldown_until IS NOT NULL;

-- Indexes pour seen_urls
CREATE UNIQUE INDEX IF NOT EXISTS idx_seen_urls_hash 
    ON seen_urls(url_hash);

CREATE INDEX IF NOT EXISTS idx_seen_urls_domain 
    ON seen_urls(domain, last_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_seen_urls_job 
    ON seen_urls(job_id, processing_status);

CREATE INDEX IF NOT EXISTS idx_seen_urls_revisit 
    ON seen_urls(next_revisit_after) 
    WHERE next_revisit_after IS NOT NULL;

-- Indexes pour job_runs
CREATE INDEX IF NOT EXISTS idx_job_runs_job 
    ON job_runs(job_id, run_number DESC);

CREATE INDEX IF NOT EXISTS idx_job_runs_status 
    ON job_runs(status, started_at DESC);

-- Indexes pour job_checkpoints
CREATE UNIQUE INDEX IF NOT EXISTS idx_job_checkpoints_unique 
    ON job_checkpoints(job_id, run_id, phase) 
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_job_checkpoints_recovery 
    ON job_checkpoints(job_id, phase, checkpoint_at DESC) 
    WHERE is_active = TRUE;

-- Indexes pour proxy_stats
CREATE UNIQUE INDEX IF NOT EXISTS idx_proxy_stats_unique 
    ON proxy_stats(proxy_id, measurement_date, hour_of_day);

CREATE INDEX IF NOT EXISTS idx_proxy_stats_date 
    ON proxy_stats(measurement_date DESC, hour_of_day);

-- Indexes pour contacts (déduplication)
CREATE INDEX IF NOT EXISTS idx_contacts_hash 
    ON contacts(contact_hash) 
    WHERE contact_hash IS NOT NULL AND deleted_at IS NULL;

-- Indexes pour system_logs (étendus)
CREATE INDEX IF NOT EXISTS idx_logs_component_category 
    ON system_logs(component, category, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_logs_severity_unresolved 
    ON system_logs(severity DESC, resolved, timestamp DESC) 
    WHERE severity >= 2;

-- =================================================================
-- AJOUTER NOUVEAUX SETTINGS
-- =================================================================

INSERT INTO settings(key, value, description, category) VALUES 
    ('proxy_rotation_default_mode', 'per_spider', 'Mode de rotation par défaut', 'proxy'),
    ('proxy_sticky_ttl_default', '180', 'TTL sticky par défaut (secondes)', 'proxy'),
    ('proxy_rps_datacenter_default', '2.0', 'RPS par défaut datacenter', 'proxy'),
    ('proxy_rps_residential_default', '0.5', 'RPS par défaut résidentiel', 'proxy'),
    ('proxy_cooldown_initial', '30', 'Cooldown initial (secondes)', 'proxy'),
    ('proxy_circuit_breaker_threshold', '5', 'Seuil circuit breaker', 'proxy'),
    ('url_cache_ttl_seconds', '3600', 'TTL cache URLs (secondes)', 'cache'),
    ('content_hash_enabled', 'true', 'Activer hash contenu', 'deduplication'),
    ('revisit_delay_hours', '168', 'Délai revisit URLs (heures)', 'deduplication'),
    ('checkpoint_interval_pages', '100', 'Intervalle checkpoint (pages)', 'recovery'),
    ('rate_limit_domain_default', '2.0', 'Rate limit par domaine par défaut', 'limits')
ON CONFLICT (key) DO NOTHING;

-- =================================================================
-- CRÉER NOUVEAUX TRIGGERS
-- =================================================================

-- Trigger pour seen_urls
DROP TRIGGER IF EXISTS update_seen_urls_updated_at ON seen_urls;
CREATE TRIGGER update_seen_urls_updated_at BEFORE UPDATE ON seen_urls
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger pour job_runs
DROP TRIGGER IF EXISTS update_job_runs_updated_at ON job_runs;
CREATE TRIGGER update_job_runs_updated_at BEFORE UPDATE ON job_runs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger pour job_checkpoints  
DROP TRIGGER IF EXISTS update_job_checkpoints_updated_at ON job_checkpoints;
CREATE TRIGGER update_job_checkpoints_updated_at BEFORE UPDATE ON job_checkpoints
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =================================================================
-- RECRÉER VUES
-- =================================================================

-- Vue performance globale étendue
DROP VIEW IF EXISTS performance_dashboard;
CREATE VIEW performance_dashboard AS
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
    (SELECT COUNT(*) FROM proxies WHERE active = true AND (cooldown_until IS NULL OR cooldown_until < NOW())) as active_proxies,
    (SELECT AVG(average_latency_ms) FROM proxies WHERE active = true AND average_latency_ms > 0) as avg_proxy_response_time,
    (SELECT AVG(success_rate) FROM proxies WHERE active = true) as avg_proxy_success_rate,
    (SELECT COUNT(*) FROM proxies WHERE circuit_breaker_status = 'open') as circuit_breaker_open,
    
    -- Stats sessions
    (SELECT COUNT(*) FROM sessions WHERE active = true) as active_sessions,
    (SELECT COUNT(*) FROM sessions WHERE validation_status = 'valid') as valid_sessions,
    
    -- Stats anti-doublons
    (SELECT COUNT(*) FROM seen_urls WHERE DATE(first_seen_at) = CURRENT_DATE) as urls_seen_today,
    (SELECT COUNT(*) FROM seen_urls WHERE processing_status = 'skipped' AND skip_reason = 'duplicate') as duplicates_skipped;

-- =================================================================
-- METTRE À JOUR VERSION
-- =================================================================

UPDATE settings SET value = '2.1', updated_at = NOW() WHERE key = 'database_version';

-- Log de migration
INSERT INTO system_logs (level, component, message, category, details) VALUES (
    'INFO', 
    'migration', 
    'Migration 001 appliquée avec succès',
    'system',
    jsonb_build_object(
        'version_from', '2.0',
        'version_to', '2.1',
        'features_added', jsonb_build_array(
            'proxy_advanced_rotation',
            'anti_duplicate_urls', 
            'job_checkpointing',
            'circuit_breakers',
            'proxy_stats_tracking'
        )
    )
);

COMMIT;

-- Message de confirmation
DO $$
BEGIN
    RAISE NOTICE 'Migration 001 terminée avec succès !';
    RAISE NOTICE 'Fonctionnalités ajoutées: Rotation Proxy Avancée, Anti-Doublons, Checkpointing, Circuit Breakers';
    RAISE NOTICE 'Base de données mise à jour vers la version 2.1';
END $$;