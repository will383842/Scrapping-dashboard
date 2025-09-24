--
-- PostgreSQL database dump
--

\restrict Wqe26LJqcLLaTKohfcx1WyPajiVwW3cWihFTiTJdOvJzGEdbZ7GdNJzISdcKWGs

-- Dumped from database version 15.14
-- Dumped by pg_dump version 15.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: cleanup_old_data(); Type: FUNCTION; Schema: public; Owner: scraper_admin
--

CREATE FUNCTION public.cleanup_old_data() RETURNS integer
    LANGUAGE plpgsql
    AS $$
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
$$;


ALTER FUNCTION public.cleanup_old_data() OWNER TO scraper_admin;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: scraper_admin
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_updated_at_column() OWNER TO scraper_admin;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: contacts; Type: TABLE; Schema: public; Owner: scraper_admin
--

CREATE TABLE public.contacts (
    id bigint NOT NULL,
    name text,
    org text,
    email text,
    languages text,
    phone text,
    country text,
    url text,
    theme text,
    source text DEFAULT 'scraper'::text,
    page_lang text,
    raw_text text,
    query_id integer,
    seed_url text,
    verified boolean DEFAULT false,
    email_valid boolean,
    phone_valid boolean,
    enrichment_status text,
    linkedin_url text,
    company_website text,
    job_title text,
    extraction_method text,
    confidence_score double precision DEFAULT 0.0,
    tags text[],
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone,
    created_by text DEFAULT 'scraper'::text,
    last_verified_at timestamp without time zone,
    CONSTRAINT contacts_confidence_score_check CHECK (((confidence_score >= (0.0)::double precision) AND (confidence_score <= (1.0)::double precision))),
    CONSTRAINT contacts_enrichment_status_check CHECK ((enrichment_status = ANY (ARRAY[NULL::text, 'pending'::text, 'done'::text, 'failed'::text])))
);


ALTER TABLE public.contacts OWNER TO scraper_admin;

--
-- Name: contacts_id_seq; Type: SEQUENCE; Schema: public; Owner: scraper_admin
--

CREATE SEQUENCE public.contacts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.contacts_id_seq OWNER TO scraper_admin;

--
-- Name: contacts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: scraper_admin
--

ALTER SEQUENCE public.contacts_id_seq OWNED BY public.contacts.id;


--
-- Name: proxies; Type: TABLE; Schema: public; Owner: scraper_admin
--

CREATE TABLE public.proxies (
    id integer NOT NULL,
    label text,
    scheme text DEFAULT 'http'::text,
    host text NOT NULL,
    port integer NOT NULL,
    username text,
    password text,
    active boolean DEFAULT true,
    priority integer DEFAULT 10,
    last_used_at timestamp without time zone,
    response_time_ms integer DEFAULT 0,
    success_rate double precision DEFAULT 1.0,
    total_requests integer DEFAULT 0,
    failed_requests integer DEFAULT 0,
    last_test_at timestamp without time zone,
    last_test_status text,
    country_code character(2),
    region text,
    provider text,
    cost_per_gb numeric(10,4),
    bandwidth_limit_gb integer,
    monthly_limit_gb integer,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    created_by text DEFAULT 'dashboard'::text,
    notes text,
    CONSTRAINT proxies_last_test_status_check CHECK ((last_test_status = ANY (ARRAY[NULL::text, 'success'::text, 'failed'::text, 'timeout'::text]))),
    CONSTRAINT proxies_port_check CHECK (((port > 0) AND (port <= 65535))),
    CONSTRAINT proxies_scheme_check CHECK ((scheme = ANY (ARRAY['http'::text, 'https'::text, 'socks5'::text]))),
    CONSTRAINT proxies_success_rate_check CHECK (((success_rate >= (0.0)::double precision) AND (success_rate <= (1.0)::double precision)))
);


ALTER TABLE public.proxies OWNER TO scraper_admin;

--
-- Name: queue; Type: TABLE; Schema: public; Owner: scraper_admin
--

CREATE TABLE public.queue (
    id integer NOT NULL,
    url text NOT NULL,
    country_filter text,
    lang_filter text,
    theme text,
    source_scope text,
    query_group_id text,
    use_js boolean DEFAULT false,
    max_pages_per_domain integer DEFAULT 15,
    cost_hint text,
    target_count integer DEFAULT 0,
    logic_mode text DEFAULT 'or'::text,
    status text DEFAULT 'pending'::text,
    priority integer DEFAULT 10,
    last_error text,
    last_run_at timestamp without time zone,
    retry_count integer DEFAULT 0,
    max_retries integer DEFAULT 3,
    next_retry_at timestamp without time zone,
    execution_time_seconds integer,
    contacts_extracted integer DEFAULT 0,
    created_by text DEFAULT 'dashboard'::text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone,
    added_at timestamp without time zone DEFAULT now(),
    min_rerun_hours integer DEFAULT 168,
    session_id integer,
    CONSTRAINT queue_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'in_progress'::text, 'done'::text, 'failed'::text, 'paused'::text])))
);


ALTER TABLE public.queue OWNER TO scraper_admin;

--
-- Name: sessions; Type: TABLE; Schema: public; Owner: scraper_admin
--

CREATE TABLE public.sessions (
    id integer NOT NULL,
    domain text NOT NULL,
    type text DEFAULT 'storage_state'::text,
    file_path text NOT NULL,
    active boolean DEFAULT true,
    browser_type text DEFAULT 'chromium'::text,
    user_agent text,
    session_size_bytes integer,
    cookies_count integer DEFAULT 0,
    last_validated_at timestamp without time zone,
    validation_status text,
    expires_at timestamp without time zone,
    auto_refresh boolean DEFAULT false,
    usage_count integer DEFAULT 0,
    last_used_at timestamp without time zone,
    success_rate double precision DEFAULT 1.0,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone,
    created_by text DEFAULT 'dashboard'::text,
    CONSTRAINT sessions_browser_type_check CHECK ((browser_type = ANY (ARRAY['chromium'::text, 'firefox'::text, 'webkit'::text]))),
    CONSTRAINT sessions_type_check CHECK ((type = ANY (ARRAY['storage_state'::text, 'cookies'::text, 'headers'::text]))),
    CONSTRAINT sessions_validation_status_check CHECK ((validation_status = ANY (ARRAY[NULL::text, 'valid'::text, 'invalid'::text, 'expired'::text])))
);


ALTER TABLE public.sessions OWNER TO scraper_admin;

--
-- Name: performance_dashboard; Type: VIEW; Schema: public; Owner: scraper_admin
--

CREATE VIEW public.performance_dashboard AS
 SELECT ( SELECT count(*) AS count
           FROM public.queue
          WHERE (queue.status = 'pending'::text)) AS pending_jobs,
    ( SELECT count(*) AS count
           FROM public.queue
          WHERE (queue.status = 'in_progress'::text)) AS running_jobs,
    ( SELECT count(*) AS count
           FROM public.queue
          WHERE ((queue.status = 'done'::text) AND (date(queue.updated_at) = CURRENT_DATE))) AS completed_today,
    ( SELECT count(*) AS count
           FROM public.queue
          WHERE ((queue.status = 'failed'::text) AND (date(queue.updated_at) = CURRENT_DATE))) AS failed_today,
    ( SELECT count(*) AS count
           FROM public.contacts
          WHERE (date(contacts.created_at) = CURRENT_DATE)) AS contacts_today,
    ( SELECT count(*) AS count
           FROM public.contacts
          WHERE (contacts.verified = true)) AS verified_contacts,
    ( SELECT count(DISTINCT contacts.country) AS count
           FROM public.contacts
          WHERE (contacts.country IS NOT NULL)) AS countries_covered,
    ( SELECT count(*) AS count
           FROM public.proxies
          WHERE (proxies.active = true)) AS active_proxies,
    ( SELECT avg(proxies.response_time_ms) AS avg
           FROM public.proxies
          WHERE ((proxies.active = true) AND (proxies.response_time_ms > 0))) AS avg_proxy_response_time,
    ( SELECT avg(proxies.success_rate) AS avg
           FROM public.proxies
          WHERE (proxies.active = true)) AS avg_proxy_success_rate,
    ( SELECT count(*) AS count
           FROM public.sessions
          WHERE (sessions.active = true)) AS active_sessions,
    ( SELECT count(*) AS count
           FROM public.sessions
          WHERE (sessions.validation_status = 'valid'::text)) AS valid_sessions;


ALTER TABLE public.performance_dashboard OWNER TO scraper_admin;

--
-- Name: proxies_id_seq; Type: SEQUENCE; Schema: public; Owner: scraper_admin
--

CREATE SEQUENCE public.proxies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.proxies_id_seq OWNER TO scraper_admin;

--
-- Name: proxies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: scraper_admin
--

ALTER SEQUENCE public.proxies_id_seq OWNED BY public.proxies.id;


--
-- Name: queue_id_seq; Type: SEQUENCE; Schema: public; Owner: scraper_admin
--

CREATE SEQUENCE public.queue_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.queue_id_seq OWNER TO scraper_admin;

--
-- Name: queue_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: scraper_admin
--

ALTER SEQUENCE public.queue_id_seq OWNED BY public.queue.id;


--
-- Name: sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: scraper_admin
--

CREATE SEQUENCE public.sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.sessions_id_seq OWNER TO scraper_admin;

--
-- Name: sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: scraper_admin
--

ALTER SEQUENCE public.sessions_id_seq OWNED BY public.sessions.id;


--
-- Name: settings; Type: TABLE; Schema: public; Owner: scraper_admin
--

CREATE TABLE public.settings (
    key text NOT NULL,
    value text NOT NULL,
    value_type text DEFAULT 'string'::text,
    description text,
    category text DEFAULT 'general'::text,
    is_secret boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now(),
    updated_by text DEFAULT 'system'::text,
    CONSTRAINT settings_value_type_check CHECK ((value_type = ANY (ARRAY['string'::text, 'integer'::text, 'float'::text, 'boolean'::text, 'json'::text])))
);


ALTER TABLE public.settings OWNER TO scraper_admin;

--
-- Name: system_logs; Type: TABLE; Schema: public; Owner: scraper_admin
--

CREATE TABLE public.system_logs (
    id bigint NOT NULL,
    "timestamp" timestamp without time zone DEFAULT now(),
    level text NOT NULL,
    component text NOT NULL,
    job_id integer,
    message text NOT NULL,
    details jsonb,
    correlation_id uuid DEFAULT public.uuid_generate_v4(),
    user_id text,
    ip_address inet,
    session_id text,
    CONSTRAINT system_logs_level_check CHECK ((level = ANY (ARRAY['DEBUG'::text, 'INFO'::text, 'WARNING'::text, 'ERROR'::text, 'CRITICAL'::text])))
);


ALTER TABLE public.system_logs OWNER TO scraper_admin;

--
-- Name: system_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: scraper_admin
--

CREATE SEQUENCE public.system_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.system_logs_id_seq OWNER TO scraper_admin;

--
-- Name: system_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: scraper_admin
--

ALTER SEQUENCE public.system_logs_id_seq OWNED BY public.system_logs.id;


--
-- Name: contacts id; Type: DEFAULT; Schema: public; Owner: scraper_admin
--

ALTER TABLE ONLY public.contacts ALTER COLUMN id SET DEFAULT nextval('public.contacts_id_seq'::regclass);


--
-- Name: proxies id; Type: DEFAULT; Schema: public; Owner: scraper_admin
--

ALTER TABLE ONLY public.proxies ALTER COLUMN id SET DEFAULT nextval('public.proxies_id_seq'::regclass);


--
-- Name: queue id; Type: DEFAULT; Schema: public; Owner: scraper_admin
--

ALTER TABLE ONLY public.queue ALTER COLUMN id SET DEFAULT nextval('public.queue_id_seq'::regclass);


--
-- Name: sessions id; Type: DEFAULT; Schema: public; Owner: scraper_admin
--

ALTER TABLE ONLY public.sessions ALTER COLUMN id SET DEFAULT nextval('public.sessions_id_seq'::regclass);


--
-- Name: system_logs id; Type: DEFAULT; Schema: public; Owner: scraper_admin
--

ALTER TABLE ONLY public.system_logs ALTER COLUMN id SET DEFAULT nextval('public.system_logs_id_seq'::regclass);


--
-- Data for Name: contacts; Type: TABLE DATA; Schema: public; Owner: scraper_admin
--

COPY public.contacts (id, name, org, email, languages, phone, country, url, theme, source, page_lang, raw_text, query_id, seed_url, verified, email_valid, phone_valid, enrichment_status, linkedin_url, company_website, job_title, extraction_method, confidence_score, tags, notes, created_at, updated_at, deleted_at, created_by, last_verified_at) FROM stdin;
\.


--
-- Data for Name: proxies; Type: TABLE DATA; Schema: public; Owner: scraper_admin
--

COPY public.proxies (id, label, scheme, host, port, username, password, active, priority, last_used_at, response_time_ms, success_rate, total_requests, failed_requests, last_test_at, last_test_status, country_code, region, provider, cost_per_gb, bandwidth_limit_gb, monthly_limit_gb, created_at, updated_at, created_by, notes) FROM stdin;
\.


--
-- Data for Name: queue; Type: TABLE DATA; Schema: public; Owner: scraper_admin
--

COPY public.queue (id, url, country_filter, lang_filter, theme, source_scope, query_group_id, use_js, max_pages_per_domain, cost_hint, target_count, logic_mode, status, priority, last_error, last_run_at, retry_count, max_retries, next_retry_at, execution_time_seconds, contacts_extracted, created_by, created_at, updated_at, deleted_at, added_at, min_rerun_hours, session_id) FROM stdin;
1	https://www.thelawyersglobal.org/	United States	en	lawyers	\N	\N	f	15	\N	100	or	pending	10	\N	\N	0	3	\N	\N	0	admin	2025-09-24 00:11:16.672869	2025-09-24 00:11:16.672869	\N	2025-09-24 00:11:16.672869	168	\N
\.


--
-- Data for Name: sessions; Type: TABLE DATA; Schema: public; Owner: scraper_admin
--

COPY public.sessions (id, domain, type, file_path, active, browser_type, user_agent, session_size_bytes, cookies_count, last_validated_at, validation_status, expires_at, auto_refresh, usage_count, last_used_at, success_rate, notes, created_at, updated_at, deleted_at, created_by) FROM stdin;
\.


--
-- Data for Name: settings; Type: TABLE DATA; Schema: public; Owner: scraper_admin
--

COPY public.settings (key, value, value_type, description, category, is_secret, updated_at, updated_by) FROM stdin;
scheduler_paused	false	string	Pause/Resume du scheduler principal	scheduler	f	2025-09-23 19:44:01.181171	system
js_reset_day		string	Jour de reset du compteur JS	limits	f	2025-09-23 19:44:01.181171	system
js_pages_used	0	string	Pages JS utilisées aujourd'hui	limits	f	2025-09-23 19:44:01.181171	system
js_pages_limit	1000	string	Limite quotidienne pages JS	limits	f	2025-09-23 19:44:01.181171	system
max_concurrent_jobs	5	string	Nombre maximum de jobs simultanés	performance	f	2025-09-23 19:44:01.181171	system
default_retry_attempts	3	string	Nombre de tentatives par défaut	scheduler	f	2025-09-23 19:44:01.181171	system
health_check_interval	60	string	Intervalle health check (secondes)	monitoring	f	2025-09-23 19:44:01.181171	system
cleanup_retention_days	30	string	Rétention des logs (jours)	maintenance	f	2025-09-23 19:44:01.181171	system
enable_email_alerts	false	string	Activer les alertes email	alerts	f	2025-09-23 19:44:01.181171	system
database_version	2.0	string	Version du schéma de base de données	system	f	2025-09-23 19:44:01.181171	system
\.


--
-- Data for Name: system_logs; Type: TABLE DATA; Schema: public; Owner: scraper_admin
--

COPY public.system_logs (id, "timestamp", level, component, job_id, message, details, correlation_id, user_id, ip_address, session_id) FROM stdin;
1	2025-09-23 19:44:01.32324	INFO	database	\N	Schema Scraper Pro initialisé avec succès	\N	2e2ae228-64a0-4e2c-8ea0-11a9638f3ccc	\N	\N	\N
\.


--
-- Name: contacts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: scraper_admin
--

SELECT pg_catalog.setval('public.contacts_id_seq', 1, false);


--
-- Name: proxies_id_seq; Type: SEQUENCE SET; Schema: public; Owner: scraper_admin
--

SELECT pg_catalog.setval('public.proxies_id_seq', 1, false);


--
-- Name: queue_id_seq; Type: SEQUENCE SET; Schema: public; Owner: scraper_admin
--

SELECT pg_catalog.setval('public.queue_id_seq', 1, true);


--
-- Name: sessions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: scraper_admin
--

SELECT pg_catalog.setval('public.sessions_id_seq', 1, false);


--
-- Name: system_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: scraper_admin
--

SELECT pg_catalog.setval('public.system_logs_id_seq', 1, true);


--
-- Name: contacts contacts_pkey; Type: CONSTRAINT; Schema: public; Owner: scraper_admin
--

ALTER TABLE ONLY public.contacts
    ADD CONSTRAINT contacts_pkey PRIMARY KEY (id);


--
-- Name: proxies proxies_pkey; Type: CONSTRAINT; Schema: public; Owner: scraper_admin
--

ALTER TABLE ONLY public.proxies
    ADD CONSTRAINT proxies_pkey PRIMARY KEY (id);


--
-- Name: queue queue_pkey; Type: CONSTRAINT; Schema: public; Owner: scraper_admin
--

ALTER TABLE ONLY public.queue
    ADD CONSTRAINT queue_pkey PRIMARY KEY (id);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: scraper_admin
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: settings settings_pkey; Type: CONSTRAINT; Schema: public; Owner: scraper_admin
--

ALTER TABLE ONLY public.settings
    ADD CONSTRAINT settings_pkey PRIMARY KEY (key);


--
-- Name: system_logs system_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: scraper_admin
--

ALTER TABLE ONLY public.system_logs
    ADD CONSTRAINT system_logs_pkey PRIMARY KEY (id);


--
-- Name: idx_contacts_country; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_contacts_country ON public.contacts USING btree (country);


--
-- Name: idx_contacts_country_theme; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_contacts_country_theme ON public.contacts USING btree (country, theme) WHERE (deleted_at IS NULL);


--
-- Name: idx_contacts_created_at; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_contacts_created_at ON public.contacts USING btree (created_at DESC) WHERE (deleted_at IS NULL);


--
-- Name: idx_contacts_email_unique; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE UNIQUE INDEX idx_contacts_email_unique ON public.contacts USING btree (email) WHERE ((email IS NOT NULL) AND (deleted_at IS NULL));


--
-- Name: idx_contacts_query_id; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_contacts_query_id ON public.contacts USING btree (query_id) WHERE (deleted_at IS NULL);


--
-- Name: idx_contacts_theme_country; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_contacts_theme_country ON public.contacts USING btree (theme, country, created_at DESC) WHERE (deleted_at IS NULL);


--
-- Name: idx_logs_job_id; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_logs_job_id ON public.system_logs USING btree (job_id, "timestamp" DESC) WHERE (job_id IS NOT NULL);


--
-- Name: idx_logs_level_component; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_logs_level_component ON public.system_logs USING btree (level, component, "timestamp" DESC);


--
-- Name: idx_logs_timestamp; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_logs_timestamp ON public.system_logs USING btree ("timestamp" DESC);


--
-- Name: idx_proxies_active; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_proxies_active ON public.proxies USING btree (active);


--
-- Name: idx_proxies_active_priority; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_proxies_active_priority ON public.proxies USING btree (active, priority, last_used_at NULLS FIRST) WHERE (active = true);


--
-- Name: idx_proxies_country_active; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_proxies_country_active ON public.proxies USING btree (country_code, active) WHERE (active = true);


--
-- Name: idx_proxies_last_test; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_proxies_last_test ON public.proxies USING btree (last_test_at DESC, last_test_status);


--
-- Name: idx_proxies_performance; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_proxies_performance ON public.proxies USING btree (active, success_rate DESC, response_time_ms) WHERE (active = true);


--
-- Name: idx_proxies_priority; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_proxies_priority ON public.proxies USING btree (priority);


--
-- Name: idx_proxies_unique; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE UNIQUE INDEX idx_proxies_unique ON public.proxies USING btree (scheme, host, port, COALESCE(username, ''::text));


--
-- Name: idx_queue_created_at; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_queue_created_at ON public.queue USING btree (created_at DESC) WHERE (deleted_at IS NULL);


--
-- Name: idx_queue_next_retry; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_queue_next_retry ON public.queue USING btree (next_retry_at) WHERE ((status = 'pending'::text) AND (next_retry_at IS NOT NULL));


--
-- Name: idx_queue_status; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_queue_status ON public.queue USING btree (status);


--
-- Name: idx_queue_status_priority; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_queue_status_priority ON public.queue USING btree (status, priority DESC, retry_count, id) WHERE (deleted_at IS NULL);


--
-- Name: idx_queue_status_updated; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_queue_status_updated ON public.queue USING btree (status, updated_at DESC) WHERE (deleted_at IS NULL);


--
-- Name: idx_queue_theme_status; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_queue_theme_status ON public.queue USING btree (theme, status) WHERE (deleted_at IS NULL);


--
-- Name: idx_queue_updated_at; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_queue_updated_at ON public.queue USING btree (updated_at);


--
-- Name: idx_sessions_domain_active; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_sessions_domain_active ON public.sessions USING btree (domain, active) WHERE (active = true);


--
-- Name: idx_sessions_usage; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_sessions_usage ON public.sessions USING btree (usage_count DESC, success_rate DESC) WHERE (active = true);


--
-- Name: idx_sessions_validation; Type: INDEX; Schema: public; Owner: scraper_admin
--

CREATE INDEX idx_sessions_validation ON public.sessions USING btree (validation_status, last_validated_at);


--
-- Name: contacts update_contacts_updated_at; Type: TRIGGER; Schema: public; Owner: scraper_admin
--

CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON public.contacts FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: proxies update_proxies_updated_at; Type: TRIGGER; Schema: public; Owner: scraper_admin
--

CREATE TRIGGER update_proxies_updated_at BEFORE UPDATE ON public.proxies FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: queue update_queue_updated_at; Type: TRIGGER; Schema: public; Owner: scraper_admin
--

CREATE TRIGGER update_queue_updated_at BEFORE UPDATE ON public.queue FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: sessions update_sessions_updated_at; Type: TRIGGER; Schema: public; Owner: scraper_admin
--

CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON public.sessions FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: settings update_settings_updated_at; Type: TRIGGER; Schema: public; Owner: scraper_admin
--

CREATE TRIGGER update_settings_updated_at BEFORE UPDATE ON public.settings FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- PostgreSQL database dump complete
--

\unrestrict Wqe26LJqcLLaTKohfcx1WyPajiVwW3cWihFTiTJdOvJzGEdbZ7GdNJzISdcKWGs

