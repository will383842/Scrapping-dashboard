-- ============================================================================
-- OPTIMIZATIONS SQL - SCRAPER PRO
-- Version: 2.0 Production-Ready
-- Description: Optimisations supplémentaires et configuration PostgreSQL
-- ============================================================================

BEGIN;

-- ==========================================================================
-- INDEX SUPPLÉMENTAIRES POUR PERFORMANCE
-- ==========================================================================

-- Index pour recherche email insensible à la casse
CREATE INDEX IF NOT EXISTS idx_contacts_email_lower 
    ON contacts (LOWER(email)) 
    WHERE deleted_at IS NULL;

-- Index pour extraction du domaine email
CREATE INDEX IF NOT EXISTS idx_contacts_domain 
    ON contacts ((split_part(email, '@', 2))) 
    WHERE deleted_at IS NULL;

-- Index composite pour queue optimisée
CREATE INDEX IF NOT EXISTS idx_queue_status_priority_retry 
    ON queue (status, priority DESC, retry_count ASC, id ASC) 
    WHERE deleted_at IS NULL;

-- Index pour performance des proxies
CREATE INDEX IF NOT EXISTS idx_proxies_active_performance 
    ON proxies (active, success_rate DESC, response_time_ms ASC) 
    WHERE active = true;

-- Index pour sessions par domaine et validation
CREATE INDEX IF NOT EXISTS idx_sessions_domain_validation 
    ON sessions (domain, validation_status, active) 
    WHERE active = true;

-- Index pour recherche full-text contacts (français)
CREATE INDEX IF NOT EXISTS idx_contacts_search_french 
    ON contacts USING gin(to_tsvector('french', 
        COALESCE(name, '') || ' ' || 
        COALESCE(org, '') || ' ' || 
        COALESCE(email, '')
    )) WHERE deleted_at IS NULL;

-- Index pour recherche full-text contacts (anglais)
CREATE INDEX IF NOT EXISTS idx_contacts_search_english 
    ON contacts USING gin(to_tsvector('english', 
        COALESCE(name, '') || ' ' || 
        COALESCE(org, '') || ' ' || 
        COALESCE(email, '')
    )) WHERE deleted_at IS NULL;

-- Index pour performance des jobs par thème et pays
CREATE INDEX IF NOT EXISTS idx_queue_theme_country 
    ON queue (theme, country_filter, status) 
    WHERE deleted_at IS NULL;

-- Index pour statistiques par date
CREATE INDEX IF NOT EXISTS idx_contacts_created_date 
    ON contacts (DATE(created_at)) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_queue_updated_date 
    ON queue (DATE(updated_at), status) 
    WHERE deleted_at IS NULL;

-- Index pour monitoring proxies
CREATE INDEX IF NOT EXISTS idx_proxies_last_test 
    ON proxies (last_test_at DESC, last_test_status) 
    WHERE active = true;

-- ==========================================================================
-- CONFIGURATION POSTGRESQL AVANCÉE
-- ==========================================================================

-- Extensions utiles
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Configuration des statistiques
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET pg_stat_statements.track = 'all';
ALTER SYSTEM SET pg_stat_statements.max = 10000;
ALTER SYSTEM SET pg_stat_statements.save = on;

-- Paramètres de performance
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET seq_page_cost = 1.0;
ALTER SYSTEM SET cpu_tuple_cost = 0.01;
ALTER SYSTEM SET cpu_index_tuple_cost = 0.005;
ALTER SYSTEM SET cpu_operator_cost = 0.0025;

-- Configuration mémoire
ALTER SYSTEM SET work_mem = '32MB';
ALTER SYSTEM SET maintenance_work_mem = '256MB';
ALTER SYSTEM SET autovacuum_work_mem = '128MB';

-- Configuration WAL et checkpoints
ALTER SYSTEM SET wal_buffers = '32MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET max_wal_size = '2GB';
ALTER SYSTEM SET min_wal_size = '512MB';

-- Configuration logging pour monitoring
ALTER SYSTEM SET log_min_duration_statement = 1000;
ALTER SYSTEM SET log_checkpoints = on;
ALTER SYSTEM SET log_connections = on;
ALTER SYSTEM SET log_disconnections = on;
ALTER SYSTEM SET log_lock_waits = on;
ALTER SYSTEM SET log_temp_files = 0;

-- Configuration autovacuum
ALTER SYSTEM SET autovacuum_max_workers = 4;
ALTER SYSTEM SET autovacuum_naptime = '30s';
ALTER SYSTEM SET autovacuum_vacuum_threshold = 50;
ALTER SYSTEM SET autovacuum_analyze_threshold = 50;
ALTER SYSTEM SET autovacuum_vacuum_scale_factor = 0.1;
ALTER SYSTEM SET autovacuum_analyze_scale_factor = 0.05;

-- Statistiques et monitoring
ALTER SYSTEM SET track_activities = on;
ALTER SYSTEM SET track_counts = on;
ALTER SYSTEM SET track_functions = 'all';
ALTER SYSTEM SET track_io_timing = on;

-- Configuration connexions
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET superuser_reserved_connections = 3;

-- ==========================================================================
-- VUES MATÉRIALISÉES POUR PERFORMANCE
-- ==========================================================================

-- Vue matérialisée pour statistiques contacts par pays
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_contacts_by_country AS
SELECT 
    country,
    theme,
    COUNT(*) as total_contacts,
    COUNT(*) FILTER (WHERE verified = true) as verified_contacts,
    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days') as recent_contacts,
    MAX(created_at) as last_contact_date
FROM contacts 
WHERE deleted_at IS NULL AND country IS NOT NULL
GROUP BY country, theme
WITH DATA;

-- Index sur la vue matérialisée
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_contacts_country_theme 
    ON mv_contacts_by_country (country, theme);

-- Vue matérialisée pour statistiques jobs
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_jobs_stats AS
SELECT 
    theme,
    country_filter,
    DATE(created_at) as job_date,
    COUNT(*) as total_jobs,
    COUNT(*) FILTER (WHERE status = 'done') as completed_jobs,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_jobs,
    AVG(contacts_extracted) FILTER (WHERE contacts_extracted > 0) as avg_contacts_per_job,
    SUM(contacts_extracted) as total_contacts_extracted
FROM queue 
WHERE deleted_at IS NULL AND created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY theme, country_filter, DATE(created_at)
WITH DATA;

-- Index sur la vue matérialisée jobs
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_jobs_theme_country_date 
    ON mv_jobs_stats (theme, country_filter, job_date);

-- ==========================================================================
-- FONCTIONS UTILITAIRES
-- ==========================================================================

-- Fonction de refresh des vues matérialisées
CREATE OR REPLACE FUNCTION refresh_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_contacts_by_country;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_jobs_stats;
    
    INSERT INTO system_logs (level, component, message) VALUES (
        'INFO', 
        'maintenance', 
        'Vues matérialisées rafraîchies avec succès'
    );
END;
$$ LANGUAGE plpgsql;

-- Fonction de nettoyage avancé
CREATE OR REPLACE FUNCTION advanced_cleanup()
RETURNS TABLE (
    table_name text, 
    deleted_rows integer
) AS $$
DECLARE
    deleted_logs integer;
    deleted_metrics integer;
    deleted_jobs integer;
BEGIN
    -- Suppression des anciens logs (>90 jours)
    DELETE FROM system_logs WHERE timestamp < NOW() - INTERVAL '90 days';
    GET DIAGNOSTICS deleted_logs = ROW_COUNT;
    
    -- Suppression des anciennes métriques (>30 jours) 
    DELETE FROM metrics WHERE timestamp < NOW() - INTERVAL '30 days';
    GET DIAGNOSTICS deleted_metrics = ROW_COUNT;
    
    -- Suppression des jobs terminés anciens (>30 jours)
    UPDATE queue SET deleted_at = NOW() 
    WHERE status IN ('done', 'failed') 
      AND updated_at < NOW() - INTERVAL '30 days'
      AND deleted_at IS NULL;
    GET DIAGNOSTICS deleted_jobs = ROW_COUNT;
    
    -- Retourner les statistiques
    RETURN QUERY VALUES 
        ('system_logs', deleted_logs),
        ('metrics', deleted_metrics),
        ('queue', deleted_jobs);
        
    -- Log de l'opération
    INSERT INTO system_logs (level, component, message, details) VALUES (
        'INFO', 
        'maintenance', 
        'Nettoyage avancé effectué',
        jsonb_build_object(
            'deleted_logs', deleted_logs, 
            'deleted_metrics', deleted_metrics,
            'deleted_jobs', deleted_jobs
        )
    );
END;
$$ LANGUAGE plpgsql;

-- ==========================================================================
-- TRIGGERS POUR MAINTENANCE AUTOMATIQUE
-- ==========================================================================

-- Trigger pour mise à jour automatique des vues matérialisées
CREATE OR REPLACE FUNCTION trigger_refresh_mv_contacts()
RETURNS trigger AS $$
BEGIN
    -- Programmer un refresh différé (évite les locks)
    PERFORM pg_notify('refresh_mv', 'contacts');
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Créer le trigger sur contacts
DROP TRIGGER IF EXISTS tr_contacts_refresh_mv ON contacts;
CREATE TRIGGER tr_contacts_refresh_mv
    AFTER INSERT OR UPDATE OR DELETE ON contacts
    FOR EACH STATEMENT
    EXECUTE FUNCTION trigger_refresh_mv_contacts();

-- ==========================================================================
-- CONFIGURATION FINALE
-- ==========================================================================

-- Insertion des métriques de configuration
INSERT INTO settings (key, value, description, category) VALUES 
    ('database_optimized_at', NOW()::text, 'Date optimisation DB', 'performance'),
    ('indexes_created', '12', 'Nombre index créés', 'performance'),
    ('materialized_views_created', '2', 'Vues matérialisées créées', 'performance'),
    ('pg_stat_statements_enabled', 'true', 'Monitoring requêtes activé', 'monitoring'),
    ('full_text_search_enabled', 'true', 'Recherche full-text activée', 'features'),
    ('autovacuum_optimized', 'true', 'Autovacuum optimisé', 'performance'),
    ('advanced_functions_created', 'true', 'Fonctions avancées créées', 'maintenance')
ON CONFLICT (key) DO UPDATE SET 
    value = EXCLUDED.value,
    updated_at = NOW();

-- Commentaires pour documentation
COMMENT ON DATABASE scraper_pro IS 'Scraper Pro - Base de données optimisée pour performance production';
COMMENT ON TABLE contacts IS 'Contacts extraits avec index performance et recherche full-text';
COMMENT ON TABLE queue IS 'Queue jobs avec priorités et retry automatique optimisés';
COMMENT ON TABLE proxies IS 'Proxies avec monitoring performance temps réel';
COMMENT ON MATERIALIZED VIEW mv_contacts_by_country IS 'Statistiques contacts par pays (rafraîchi automatiquement)';
COMMENT ON MATERIALIZED VIEW mv_jobs_stats IS 'Statistiques jobs pour reporting (90 derniers jours)';

COMMIT;

-- Mise à jour finale des statistiques
ANALYZE;

-- Message de confirmation
DO $$
BEGIN
    RAISE NOTICE 'Optimisations PostgreSQL appliquées avec succès !';
    RAISE NOTICE 'Index créés: 12 | Vues matérialisées: 2 | Fonctions: 3';
    RAISE NOTICE 'Configuration avancée activée pour production';
END $$;