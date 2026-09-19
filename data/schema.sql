-- SkillSetu Database Schema
-- Supabase PostgreSQL + pgvector ready
-- Run this in the Supabase SQL Editor after creating your project

-- Enable pgvector extension (uncomment when ready)
-- CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL CHECK (UPPER(role) IN ('GOVERNMENT', 'INSTITUTE', 'EMPLOYER', 'STUDENT', 'ADMIN', 'EMPLOYEE')),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- SKILLS (master taxonomy)
-- ============================================================
CREATE TABLE IF NOT EXISTS skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    nsqf_level INT CHECK (nsqf_level BETWEEN 1 AND 10),
    synonyms TEXT[] DEFAULT '{}',
    -- embedding VECTOR(384),  -- uncomment when pgvector RAG is activated
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- JOBS
-- ============================================================
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employer_id TEXT,
    external_id TEXT,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    district TEXT NOT NULL,
    industry TEXT NOT NULL,
    description TEXT,
    source TEXT DEFAULT 'DEMO_SYNTHETIC',
    source_label TEXT DEFAULT 'Demo Data',
    posted_date DATE DEFAULT CURRENT_DATE,
    CONSTRAINT uq_jobs_source_external_id UNIQUE (source, external_id)
);

-- ============================================================
-- JOB_SKILLS (many-to-many: jobs <-> skills)
-- ============================================================
CREATE TABLE IF NOT EXISTS job_skills (
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    proficiency_required TEXT CHECK (proficiency_required IN ('beginner', 'intermediate', 'advanced')),
    PRIMARY KEY (job_id, skill_id)
);

-- ============================================================
-- COURSES
-- ============================================================
CREATE TABLE IF NOT EXISTS courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    institute TEXT NOT NULL,
    district TEXT NOT NULL,
    description TEXT,
    enrolment_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- COURSE_SKILLS (many-to-many: courses <-> skills)
-- ============================================================
CREATE TABLE IF NOT EXISTS course_skills (
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    coverage_level INT CHECK (coverage_level BETWEEN 1 AND 5),
    PRIMARY KEY (course_id, skill_id)
);

-- ============================================================
-- PLACEMENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS placements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    year INT NOT NULL,
    student_count INT NOT NULL,
    placed_count INT NOT NULL
);

-- ============================================================
-- EMPLOYERS
-- ============================================================
CREATE TABLE IF NOT EXISTS employers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    industry TEXT NOT NULL,
    district TEXT NOT NULL,
    user_id TEXT,
    company_name TEXT,
    email TEXT,
    gstin TEXT,
    corporate_website TEXT,
    verification_status TEXT DEFAULT 'UNVERIFIED',
    verification_source TEXT,
    verification_method TEXT,
    verified_at TIMESTAMPTZ,
    verified_by TEXT,
    rejection_reason TEXT,
    evidence JSONB DEFAULT '{}'::jsonb,
    data_provenance TEXT DEFAULT 'DEMO_SYNTHETIC',
    source TEXT DEFAULT 'DEMO_SYNTHETIC',
    source_label TEXT DEFAULT 'Demo Data',
    confidence INT DEFAULT 0,
    is_demo BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE employers ADD COLUMN IF NOT EXISTS user_id TEXT;
ALTER TABLE employers ADD COLUMN IF NOT EXISTS company_name TEXT;
ALTER TABLE employers ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE employers ADD COLUMN IF NOT EXISTS gstin TEXT;
ALTER TABLE employers ADD COLUMN IF NOT EXISTS corporate_website TEXT;
ALTER TABLE employers ADD COLUMN IF NOT EXISTS verification_status TEXT DEFAULT 'UNVERIFIED';
ALTER TABLE employers ADD COLUMN IF NOT EXISTS verification_source TEXT;
ALTER TABLE employers ADD COLUMN IF NOT EXISTS verification_method TEXT;
ALTER TABLE employers ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
ALTER TABLE employers ADD COLUMN IF NOT EXISTS verified_by TEXT;
ALTER TABLE employers ADD COLUMN IF NOT EXISTS rejection_reason TEXT;
ALTER TABLE employers ADD COLUMN IF NOT EXISTS evidence JSONB DEFAULT '{}'::jsonb;
ALTER TABLE employers ADD COLUMN IF NOT EXISTS data_provenance TEXT DEFAULT 'DEMO_SYNTHETIC';
ALTER TABLE employers ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'DEMO_SYNTHETIC';
ALTER TABLE employers ADD COLUMN IF NOT EXISTS source_label TEXT DEFAULT 'Demo Data';
ALTER TABLE employers ADD COLUMN IF NOT EXISTS confidence INT DEFAULT 0;
ALTER TABLE employers ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE;
ALTER TABLE employers ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE employers ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

CREATE TABLE IF NOT EXISTS employer_verifications (
    id TEXT PRIMARY KEY,
    employer_id TEXT NOT NULL,
    user_id TEXT,
    company_name TEXT NOT NULL,
    email TEXT,
    gstin TEXT,
    corporate_website TEXT,
    official_documents JSONB DEFAULT '[]'::jsonb,
    notes TEXT,
    status TEXT DEFAULT 'PENDING',
    action TEXT DEFAULT 'SUBMIT',
    submitted_at TIMESTAMPTZ DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,
    admin_notes TEXT,
    rejection_reason TEXT,
    data_provenance TEXT DEFAULT 'EMPLOYER_SELF_DECLARED',
    source TEXT DEFAULT 'USER_SUBMITTED',
    is_demo BOOLEAN DEFAULT FALSE,
    evidence_payload JSONB DEFAULT '{}'::jsonb,
    confidence INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_employers_verification_status ON employers(verification_status);
CREATE INDEX IF NOT EXISTS idx_employer_verifications_status ON employer_verifications(status);
CREATE INDEX IF NOT EXISTS idx_employer_verifications_employer_id ON employer_verifications(employer_id);
CREATE INDEX IF NOT EXISTS idx_employer_verifications_is_demo ON employer_verifications(is_demo);


-- ============================================================
-- EMPLOYER_FEEDBACK (validation: confirm/correct/reject)
-- ============================================================
CREATE TABLE IF NOT EXISTS employer_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employer_id TEXT REFERENCES employers(id) ON DELETE CASCADE,
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    demand_level TEXT CHECK (demand_level IN ('low', 'medium', 'high', 'critical')),
    proficiency_required TEXT CHECK (proficiency_required IN ('beginner', 'intermediate', 'advanced')),
    status TEXT CHECK (status IN ('pending', 'confirmed', 'corrected', 'rejected')) DEFAULT 'pending',
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- INDUSTRY_SIGNALS
-- ============================================================
CREATE TABLE IF NOT EXISTS industry_signals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    technology TEXT NOT NULL,
    summary TEXT NOT NULL,
    impact_level TEXT CHECK (impact_level IN ('low', 'medium', 'high', 'critical')) NOT NULL,
    signal_date DATE DEFAULT CURRENT_DATE
);

-- ============================================================
-- SIGNAL_SKILLS (many-to-many: signals <-> skills)
-- ============================================================
CREATE TABLE IF NOT EXISTS signal_skills (
    signal_id TEXT REFERENCES industry_signals(id) ON DELETE CASCADE,
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    impact_score INT CHECK (impact_score BETWEEN 1 AND 10),
    PRIMARY KEY (signal_id, skill_id)
);

-- ============================================================
-- SKILL_FORECASTS
-- ============================================================
CREATE TABLE IF NOT EXISTS skill_forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    period TEXT CHECK (period IN ('6m', '12m', '24m')) NOT NULL,
    current_demand TEXT CHECK (current_demand IN ('low', 'medium', 'high', 'very_high')),
    future_demand TEXT CHECK (future_demand IN ('low', 'medium', 'high', 'very_high')),
    trend TEXT CHECK (trend IN ('rising', 'stable', 'declining')) NOT NULL,
    confidence INT CHECK (confidence BETWEEN 0 AND 100),
    UNIQUE (skill_id, period)
);

-- ============================================================
-- STUDENT_PROFILES
-- ============================================================
CREATE TABLE IF NOT EXISTS student_profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    full_name TEXT,
    institution TEXT,
    degree TEXT,
    education_level TEXT,
    academic_year TEXT,
    graduation_year INT,
    target_role TEXT NOT NULL,
    desired_role TEXT,
    preferred_location TEXT,
    career_interests TEXT[] DEFAULT '{}',
    skills JSONB DEFAULT '[]'::jsonb,
    projects JSONB DEFAULT '[]'::jsonb,
    certifications JSONB DEFAULT '[]'::jsonb,
    courses JSONB DEFAULT '[]'::jsonb,
    experience JSONB DEFAULT '[]'::jsonb,
    skill_match_pct INT DEFAULT 0,
    source TEXT DEFAULT 'USER_SUBMITTED',
    is_demo BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS full_name TEXT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS institution TEXT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS degree TEXT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS education_level TEXT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS academic_year TEXT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS graduation_year INT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS desired_role TEXT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS preferred_location TEXT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS career_interests TEXT[] DEFAULT '{}';
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS skills JSONB DEFAULT '[]'::jsonb;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS projects JSONB DEFAULT '[]'::jsonb;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS certifications JSONB DEFAULT '[]'::jsonb;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS courses JSONB DEFAULT '[]'::jsonb;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS experience JSONB DEFAULT '[]'::jsonb;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'USER_SUBMITTED';
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

CREATE TABLE IF NOT EXISTS employee_profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    full_name TEXT,
    "current_role" TEXT NOT NULL,
    years_of_experience NUMERIC(4,1) DEFAULT 0,
    industry TEXT,
    education TEXT,
    target_role TEXT,
    preferred_location TEXT,
    skills JSONB DEFAULT '[]'::jsonb,
    certifications JSONB DEFAULT '[]'::jsonb,
    source TEXT DEFAULT 'USER_SUBMITTED',
    is_demo BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE employee_profiles ADD COLUMN IF NOT EXISTS full_name TEXT;
ALTER TABLE employee_profiles ADD COLUMN IF NOT EXISTS "current_role" TEXT;
ALTER TABLE employee_profiles ADD COLUMN IF NOT EXISTS years_of_experience NUMERIC(4,1) DEFAULT 0;
ALTER TABLE employee_profiles ADD COLUMN IF NOT EXISTS industry TEXT;
ALTER TABLE employee_profiles ADD COLUMN IF NOT EXISTS education TEXT;
ALTER TABLE employee_profiles ADD COLUMN IF NOT EXISTS target_role TEXT;
ALTER TABLE employee_profiles ADD COLUMN IF NOT EXISTS preferred_location TEXT;
ALTER TABLE employee_profiles ADD COLUMN IF NOT EXISTS skills JSONB DEFAULT '[]'::jsonb;
ALTER TABLE employee_profiles ADD COLUMN IF NOT EXISTS certifications JSONB DEFAULT '[]'::jsonb;
ALTER TABLE employee_profiles ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'USER_SUBMITTED';
ALTER TABLE employee_profiles ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE;
ALTER TABLE employee_profiles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE employee_profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- ============================================================
-- STUDENT_SKILLS
-- ============================================================
CREATE TABLE IF NOT EXISTS student_skills (
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    proficiency TEXT CHECK (proficiency IN ('beginner', 'intermediate', 'advanced', 'expert')) NOT NULL,
    PRIMARY KEY (user_id, skill_id)
);

-- ============================================================
-- RECOMMENDATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_type TEXT CHECK (target_type IN ('course', 'district', 'student', 'curriculum')) NOT NULL,
    target_id TEXT,
    recommendation TEXT NOT NULL,
    reason TEXT NOT NULL,
    supporting_data JSONB DEFAULT '{}',
    confidence INT CHECK (confidence BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- INDEXES for common queries
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_jobs_district ON jobs(district);
CREATE INDEX IF NOT EXISTS idx_jobs_industry ON jobs(industry);
CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);
CREATE INDEX IF NOT EXISTS idx_employer_feedback_status ON employer_feedback(status);
CREATE INDEX IF NOT EXISTS idx_skill_forecasts_trend ON skill_forecasts(trend);
CREATE INDEX IF NOT EXISTS idx_recommendations_target_type ON recommendations(target_type);

-- ============================================================
-- SCHEMES (student welfare & government programmes)
-- ============================================================
CREATE TABLE IF NOT EXISTS schemes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_code TEXT UNIQUE,
    title TEXT NOT NULL,
    department TEXT NOT NULL,
    scheme_type TEXT NOT NULL CHECK (scheme_type IN (
        'scholarship', 'fee_waiver', 'hostel_allowance',
        'training_scheme', 'stipend', 'tool_grant'
    )),
    beneficiary_category TEXT[] DEFAULT '{}',
    income_ceiling_annual INT,
    benefit_description TEXT NOT NULL,
    max_amount INT,
    eligible_course_types TEXT[] DEFAULT '{}',
    application_portal_url TEXT,
    deadline_date DATE,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'upcoming', 'closed')),
    source TEXT NOT NULL,
    external_id TEXT,
    last_synced_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (source, external_id)
);

-- ============================================================
-- JOBS — extended for internships, apprenticeships, vocational training
-- ============================================================
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS opportunity_type TEXT
    DEFAULT 'job' CHECK (opportunity_type IN (
        'job', 'internship', 'apprenticeship', 'vocational_training'
    ));
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS external_id TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS portal_source TEXT DEFAULT 'direct';
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS stipend_amount INT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS duration_months INT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS min_education TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS vacancies_count INT DEFAULT 1;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS apply_url TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source_url TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS verification_status TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS verification_method TEXT DEFAULT 'STRUCTURAL_API_VALIDATION';
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS confidence INT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS freshness_status TEXT DEFAULT 'UNKNOWN';
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_demo BOOLEAN;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS data_provenance TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS deadline TIMESTAMPTZ;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS employer_id TEXT;
CREATE INDEX IF NOT EXISTS idx_jobs_employer_id ON jobs(employer_id);

-- SCHEMES provenance and verification extensions
ALTER TABLE schemes ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE schemes ADD COLUMN IF NOT EXISTS source_url TEXT;
ALTER TABLE schemes ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE schemes ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
ALTER TABLE schemes ADD COLUMN IF NOT EXISTS verification_status TEXT;
ALTER TABLE schemes ADD COLUMN IF NOT EXISTS verification_method TEXT DEFAULT 'GOVERNMENT_PORTAL_API_FEED';
ALTER TABLE schemes ADD COLUMN IF NOT EXISTS confidence INT;
ALTER TABLE schemes ADD COLUMN IF NOT EXISTS freshness_status TEXT DEFAULT 'UNKNOWN';
ALTER TABLE schemes ADD COLUMN IF NOT EXISTS is_demo BOOLEAN;

-- ============================================================
-- SYNC_LOGS (ingestion audit trail)
-- ============================================================
CREATE TABLE IF NOT EXISTS sync_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name TEXT NOT NULL,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed', 'partial', 'no_data', 'NO_DATA')),
    records_fetched INT DEFAULT 0,
    records_added INT DEFAULT 0,
    records_updated INT DEFAULT 0,
    records_skipped INT DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    duration_ms INT
);

-- ============================================================
-- INDEXES for new tables
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_schemes_type ON schemes(scheme_type);
CREATE INDEX IF NOT EXISTS idx_schemes_status ON schemes(status);
CREATE INDEX IF NOT EXISTS idx_jobs_opportunity_type ON jobs(opportunity_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_source_external_id
    ON jobs(source, external_id) WHERE external_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sync_logs_source ON sync_logs(source_name, started_at DESC);

-- ============================================================
-- PHASE 23-25 EXTENSIONS: AUTHENTICATION, EMPLOYER DEMANDS, & INSTITUTES
-- ============================================================

-- USERS Table extensions for Phase 23 Auth
ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS hashed_password TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS organization_id TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS district TEXT DEFAULT 'Maharashtra';
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'USER_SUBMITTED';
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- EMPLOYER_FEEDBACK Table extensions
ALTER TABLE employer_feedback ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'USER_SUBMITTED';
ALTER TABLE employer_feedback ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE;
ALTER TABLE employer_feedback ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- EMPLOYER_DEMANDS Table for Phase 14 & 25
CREATE TABLE IF NOT EXISTS employer_demands (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    user_email TEXT,
    employer_id TEXT,
    company_name TEXT,
    employer_name TEXT,
    industry TEXT NOT NULL,
    district TEXT NOT NULL,
    job_role TEXT,
    role_title TEXT,
    required_skills TEXT[] DEFAULT '{}',
    skills TEXT[] DEFAULT '{}',
    preferred_proficiency TEXT DEFAULT 'intermediate',
    proficiency_required TEXT,
    openings_count INT DEFAULT 1,
    positions_count INT DEFAULT 1,
    experience_level TEXT DEFAULT 'Entry Level (0-1 yrs)',
    hiring_timeline TEXT DEFAULT 'Immediate (0-30 days)',
    urgency TEXT,
    additional_requirements TEXT,
    hiring_challenge TEXT,
    nsqf_level INT DEFAULT 5,
    validation_status TEXT DEFAULT 'PENDING' CHECK (validation_status IN ('PENDING', 'VALIDATED', 'REJECTED')),
    admin_notes TEXT,
    validated_by TEXT,
    source TEXT DEFAULT 'EMPLOYER_SUBMITTED',
    is_demo BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    submitted_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE employer_demands ADD COLUMN IF NOT EXISTS user_email TEXT;
ALTER TABLE employer_demands ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();


-- COURSES Table extensions for Phase 25 Institute Pipeline
ALTER TABLE courses ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'Vocational & Technical';
ALTER TABLE courses ADD COLUMN IF NOT EXISTS skills TEXT[] DEFAULT '{}';
ALTER TABLE courses ADD COLUMN IF NOT EXISTS nsqf_level INT DEFAULT 5;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS enrolment_capacity INT DEFAULT 60;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS placed_count INT DEFAULT 0;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS placement_rate INT DEFAULT 70;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS duration_weeks INT DEFAULT 12;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS certifications TEXT;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';
ALTER TABLE courses ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'USER_SUBMITTED';
ALTER TABLE courses ADD COLUMN IF NOT EXISTS data_provenance TEXT DEFAULT 'INSTITUTE_REPORTED';
ALTER TABLE courses ADD COLUMN IF NOT EXISTS user_id TEXT;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS institute_id TEXT;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_employer_demands_district ON employer_demands(district);
CREATE INDEX IF NOT EXISTS idx_employer_demands_status ON employer_demands(validation_status);
CREATE INDEX IF NOT EXISTS idx_employer_demands_user ON employer_demands(user_id);
CREATE INDEX IF NOT EXISTS idx_courses_district ON courses(district);
CREATE INDEX IF NOT EXISTS idx_courses_user ON courses(user_id);
CREATE INDEX IF NOT EXISTS idx_courses_status ON courses(status);

-- ============================================================
-- Phase 26: Industry Intelligence & Signal Ingestion Pipeline
-- ============================================================
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'INDUSTRY_DEMAND';
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS industry TEXT DEFAULT 'Cross-Sector Tech';
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS skills TEXT[] DEFAULT '{}';
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS tools TEXT[] DEFAULT '{}';
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS source_url TEXT;
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS source_name TEXT;
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS source_type TEXT DEFAULT 'INDUSTRY_ANNOUNCEMENT';
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS collected_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS validation_status TEXT DEFAULT 'APPROVED' CHECK (validation_status IN ('APPROVED', 'PENDING', 'REJECTED', 'ARCHIVED'));
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE;
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS data_provenance TEXT DEFAULT 'VERIFIED_EXTERNAL_FEED';
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS freshness TEXT DEFAULT 'NEW';
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS is_ai_processed BOOLEAN DEFAULT FALSE;
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS ai_metadata JSONB;
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS signature TEXT;
ALTER TABLE industry_signals ADD COLUMN IF NOT EXISTS admin_notes TEXT;

CREATE INDEX IF NOT EXISTS idx_signals_published ON industry_signals(published_at);
CREATE INDEX IF NOT EXISTS idx_signals_collected ON industry_signals(collected_at);
CREATE INDEX IF NOT EXISTS idx_signals_category ON industry_signals(category);
CREATE INDEX IF NOT EXISTS idx_signals_industry ON industry_signals(industry);
CREATE INDEX IF NOT EXISTS idx_signals_active ON industry_signals(is_active);
CREATE INDEX IF NOT EXISTS idx_signals_status ON industry_signals(validation_status);

-- ============================================================
-- STUDENT_ASSESSMENTS Table for Phase 24 & Real-Data Hardening
-- ============================================================
CREATE TABLE IF NOT EXISTS student_assessments (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    user_email TEXT,
    name TEXT NOT NULL,
    education TEXT,
    district TEXT DEFAULT 'Maharashtra',
    career_goal TEXT NOT NULL,
    interests TEXT[] DEFAULT '{}',
    current_skills JSONB DEFAULT '[]'::jsonb,
    quiz_answers JSONB DEFAULT '{}'::jsonb,
    quiz_score_pct INT DEFAULT 0,
    skill_match_pct INT DEFAULT 0,
    combined_readiness_score INT DEFAULT 0,
    evaluation_summary JSONB DEFAULT '{}'::jsonb,
    source TEXT DEFAULT 'USER_SUBMITTED',
    is_demo BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_student_assessments_user ON student_assessments(user_id);
CREATE INDEX IF NOT EXISTS idx_student_assessments_district ON student_assessments(district);
CREATE INDEX IF NOT EXISTS idx_student_assessments_goal ON student_assessments(career_goal);

-- ============================================================
-- GOV_OPPORTUNITIES Table for Phase 25 & Government Scheme Publishing
-- ============================================================
CREATE TABLE IF NOT EXISTS gov_opportunities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT,
    description TEXT,
    eligibility_criteria TEXT,
    target_skills TEXT[] DEFAULT '{}',
    district_coverage TEXT[] DEFAULT '{}',
    opportunity_type TEXT DEFAULT 'APPRENTICESHIP',
    application_url TEXT,
    deadline TEXT,
    status TEXT DEFAULT 'active',
    source TEXT DEFAULT 'USER_SUBMITTED',
    data_provenance TEXT DEFAULT 'GOVERNMENT_OFFICIAL',
    is_demo BOOLEAN DEFAULT FALSE,
    user_id TEXT,
    user_email TEXT,
    verification_status TEXT,
    source_type TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gov_opps_status ON gov_opportunities(status);
CREATE INDEX IF NOT EXISTS idx_gov_opps_type ON gov_opportunities(opportunity_type);

ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS full_name TEXT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS institution TEXT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS degree TEXT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS education_level TEXT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS academic_year TEXT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS graduation_year INT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS desired_role TEXT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS preferred_location TEXT;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS career_interests TEXT[] DEFAULT '{}';
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS skills JSONB DEFAULT '[]'::jsonb;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS projects JSONB DEFAULT '[]'::jsonb;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS certifications JSONB DEFAULT '[]'::jsonb;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS courses JSONB DEFAULT '[]'::jsonb;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'USER_SUBMITTED';
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE;
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

CREATE TABLE IF NOT EXISTS employee_profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    full_name TEXT,
    "current_role" TEXT NOT NULL,
    years_of_experience NUMERIC(4,1) DEFAULT 0,
    industry TEXT,
    education TEXT,
    target_role TEXT,
    preferred_location TEXT,
    skills JSONB DEFAULT '[]'::jsonb,
    certifications JSONB DEFAULT '[]'::jsonb,
    source TEXT DEFAULT 'USER_SUBMITTED',
    is_demo BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_student_profiles_target_role ON student_profiles(target_role);
CREATE INDEX IF NOT EXISTS idx_student_profiles_preferred_location ON student_profiles(preferred_location);
CREATE INDEX IF NOT EXISTS idx_employee_profiles_target_role ON employee_profiles(target_role);
CREATE INDEX IF NOT EXISTS idx_employee_profiles_current_role ON employee_profiles("current_role");
CREATE INDEX IF NOT EXISTS idx_employee_profiles_industry ON employee_profiles(industry);

CREATE OR REPLACE FUNCTION public.sync_student_profile_atomic(p_profile JSONB)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_user_id TEXT;
    v_calling_user TEXT;
    v_saved_profile public.student_profiles%ROWTYPE;
    v_invalid_skill JSONB;
BEGIN
    v_user_id := p_profile->>'user_id';
    IF v_user_id IS NULL OR trim(v_user_id) = '' THEN
        RAISE EXCEPTION 'user_id is required in profile payload';
    END IF;

    v_calling_user := auth.uid()::text;
    IF v_calling_user IS NOT NULL AND v_calling_user <> v_user_id THEN
        IF NOT EXISTS (
            SELECT 1 FROM public.users
            WHERE id = v_calling_user
              AND role = 'ADMIN'
        ) THEN
            RAISE EXCEPTION 'Unauthorized: user % cannot modify profile for %', v_calling_user, v_user_id;
        END IF;
    END IF;

    IF p_profile ? 'skill_match_pct' THEN
        IF p_profile->>'skill_match_pct' IS NULL
           OR (p_profile->>'skill_match_pct') !~ '^[0-9]+$'
           OR (p_profile->>'skill_match_pct')::INT < 0
           OR (p_profile->>'skill_match_pct')::INT > 100 THEN
            RAISE EXCEPTION 'Invalid skill_match_pct: %', p_profile->>'skill_match_pct';
        END IF;
    END IF;

    IF p_profile ? 'skills' AND jsonb_typeof(p_profile->'skills') = 'array' THEN
        SELECT elem INTO v_invalid_skill
        FROM jsonb_array_elements(p_profile->'skills') AS elem
        WHERE jsonb_typeof(elem) = 'object'
          AND elem ? 'proficiency'
          AND lower(elem->>'proficiency') NOT IN ('beginner', 'intermediate', 'advanced', 'expert')
        LIMIT 1;

        IF v_invalid_skill IS NOT NULL THEN
            RAISE EXCEPTION 'Invalid skill proficiency: %', v_invalid_skill;
        END IF;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM public.users WHERE id = v_user_id) THEN
        BEGIN
            INSERT INTO public.users (id, name, email, role)
            VALUES (
                v_user_id,
                COALESCE(NULLIF(p_profile->>'full_name', ''), 'Platform User'),
                COALESCE(NULLIF(p_profile->>'email', ''), v_user_id || '@skillsetu.gov.in'),
                'STUDENT'
            );
        EXCEPTION WHEN unique_violation THEN
            INSERT INTO public.users (id, name, email, role)
            VALUES (
                v_user_id,
                COALESCE(NULLIF(p_profile->>'full_name', ''), 'Platform User'),
                v_user_id || '_' || substr(md5(random()::text), 1, 6) || '@skillsetu.gov.in',
                'STUDENT'
            )
            ON CONFLICT DO NOTHING;
        END;
    END IF;

    INSERT INTO public.student_profiles (
        user_id,
        full_name,
        institution,
        degree,
        education_level,
        academic_year,
        graduation_year,
        target_role,
        desired_role,
        preferred_location,
        career_interests,
        skills,
        projects,
        certifications,
        courses,
        experience,
        skill_match_pct,
        source,
        is_demo,
        created_at,
        updated_at
    ) VALUES (
        v_user_id,
        p_profile->>'full_name',
        p_profile->>'institution',
        p_profile->>'degree',
        p_profile->>'education_level',
        p_profile->>'academic_year',
        CASE
            WHEN p_profile->>'graduation_year' ~ '^[0-9]+$'
            THEN (p_profile->>'graduation_year')::INT
            ELSE NULL
        END,
        COALESCE(p_profile->>'target_role', p_profile->>'desired_role', ''),
        p_profile->>'desired_role',
        p_profile->>'preferred_location',
        CASE
            WHEN p_profile ? 'career_interests' AND jsonb_typeof(p_profile->'career_interests') = 'array'
            THEN ARRAY(SELECT jsonb_array_elements_text(p_profile->'career_interests'))
            ELSE '{}'::text[]
        END,
        CASE
            WHEN p_profile ? 'skills' AND jsonb_typeof(p_profile->'skills') = 'array'
            THEN p_profile->'skills'
            ELSE '[]'::jsonb
        END,
        CASE
            WHEN p_profile ? 'projects' AND jsonb_typeof(p_profile->'projects') = 'array'
            THEN p_profile->'projects'
            ELSE '[]'::jsonb
        END,
        CASE
            WHEN p_profile ? 'certifications' AND jsonb_typeof(p_profile->'certifications') = 'array'
            THEN p_profile->'certifications'
            ELSE '[]'::jsonb
        END,
        CASE
            WHEN p_profile ? 'courses' AND jsonb_typeof(p_profile->'courses') = 'array'
            THEN p_profile->'courses'
            ELSE '[]'::jsonb
        END,
        CASE
            WHEN p_profile ? 'experience' AND jsonb_typeof(p_profile->'experience') = 'array'
            THEN p_profile->'experience'
            ELSE '[]'::jsonb
        END,
        CASE
            WHEN p_profile ? 'skill_match_pct' AND p_profile->>'skill_match_pct' ~ '^[0-9]+$'
            THEN (p_profile->>'skill_match_pct')::INT
            ELSE 0
        END,
        COALESCE(NULLIF(p_profile->>'source', ''), 'USER_SUBMITTED'),
        COALESCE((p_profile->>'is_demo')::BOOLEAN, FALSE),
        COALESCE(NULLIF(p_profile->>'created_at', '')::TIMESTAMPTZ, now()),
        COALESCE(NULLIF(p_profile->>'updated_at', '')::TIMESTAMPTZ, now())
    )
    ON CONFLICT (user_id) DO UPDATE SET
        full_name = COALESCE(EXCLUDED.full_name, student_profiles.full_name),
        institution = COALESCE(EXCLUDED.institution, student_profiles.institution),
        degree = COALESCE(EXCLUDED.degree, student_profiles.degree),
        education_level = COALESCE(EXCLUDED.education_level, student_profiles.education_level),
        academic_year = COALESCE(EXCLUDED.academic_year, student_profiles.academic_year),
        graduation_year = COALESCE(EXCLUDED.graduation_year, student_profiles.graduation_year),
        target_role = CASE WHEN EXCLUDED.target_role <> '' THEN EXCLUDED.target_role ELSE student_profiles.target_role END,
        desired_role = COALESCE(EXCLUDED.desired_role, student_profiles.desired_role),
        preferred_location = COALESCE(EXCLUDED.preferred_location, student_profiles.preferred_location),
        career_interests = CASE
            WHEN p_profile ? 'career_interests' AND jsonb_typeof(p_profile->'career_interests') = 'array'
            THEN EXCLUDED.career_interests
            ELSE student_profiles.career_interests
        END,
        skills = CASE
            WHEN p_profile ? 'skills' AND jsonb_typeof(p_profile->'skills') = 'array'
            THEN EXCLUDED.skills
            ELSE student_profiles.skills
        END,
        projects = CASE
            WHEN p_profile ? 'projects' AND jsonb_typeof(p_profile->'projects') = 'array'
            THEN EXCLUDED.projects
            ELSE student_profiles.projects
        END,
        certifications = CASE
            WHEN p_profile ? 'certifications' AND jsonb_typeof(p_profile->'certifications') = 'array'
            THEN EXCLUDED.certifications
            ELSE student_profiles.certifications
        END,
        courses = CASE
            WHEN p_profile ? 'courses' AND jsonb_typeof(p_profile->'courses') = 'array'
            THEN EXCLUDED.courses
            ELSE student_profiles.courses
        END,
        experience = CASE
            WHEN p_profile ? 'experience' AND jsonb_typeof(p_profile->'experience') = 'array'
            THEN EXCLUDED.experience
            ELSE student_profiles.experience
        END,
        skill_match_pct = CASE
            WHEN p_profile ? 'skill_match_pct' AND p_profile->>'skill_match_pct' ~ '^[0-9]+$'
            THEN EXCLUDED.skill_match_pct
            ELSE student_profiles.skill_match_pct
        END,
        source = COALESCE(EXCLUDED.source, student_profiles.source),
        is_demo = COALESCE(EXCLUDED.is_demo, student_profiles.is_demo),
        updated_at = now()
    RETURNING * INTO v_saved_profile;

    IF p_profile ? 'skills' AND jsonb_typeof(p_profile->'skills') = 'array' THEN
        DELETE FROM public.student_skills
        WHERE user_id = v_user_id
          AND skill_id NOT IN (
              SELECT resolved_skill_id
              FROM (
                  SELECT (
                      SELECT s.id
                      FROM public.skills s
                      WHERE (
                          (
                              (elem->>'skill_id') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                              AND s.id = (elem->>'skill_id')::uuid
                          ) OR (
                              (elem->>'id') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                              AND s.id = (elem->>'id')::uuid
                          ) OR (
                              COALESCE(elem->>'skill_name', elem->>'name', '') <> ''
                              AND lower(s.name) = lower(COALESCE(elem->>'skill_name', elem->>'name'))
                          ) OR (
                              COALESCE(elem->>'skill_name', elem->>'name', '') <> ''
                              AND EXISTS (
                                  SELECT 1 FROM unnest(COALESCE(s.synonyms, '{}'::text[])) syn
                                  WHERE lower(syn) = lower(COALESCE(elem->>'skill_name', elem->>'name'))
                              )
                          )
                      )
                      LIMIT 1
                  ) AS resolved_skill_id
                  FROM jsonb_array_elements(p_profile->'skills') AS elem
                  WHERE jsonb_typeof(elem) = 'object'
              ) sub
              WHERE resolved_skill_id IS NOT NULL
          );

        INSERT INTO public.student_skills (user_id, skill_id, proficiency)
        SELECT DISTINCT ON (target_skill_id)
            v_user_id,
            target_skill_id,
            prof
        FROM (
            SELECT
                (
                    SELECT s.id
                    FROM public.skills s
                    WHERE (
                        (
                            (elem->>'skill_id') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                            AND s.id = (elem->>'skill_id')::uuid
                        ) OR (
                            (elem->>'id') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                            AND s.id = (elem->>'id')::uuid
                        ) OR (
                            COALESCE(elem->>'skill_name', elem->>'name', '') <> ''
                            AND lower(s.name) = lower(COALESCE(elem->>'skill_name', elem->>'name'))
                        ) OR (
                            COALESCE(elem->>'skill_name', elem->>'name', '') <> ''
                            AND EXISTS (
                                SELECT 1 FROM unnest(COALESCE(s.synonyms, '{}'::text[])) syn
                                WHERE lower(syn) = lower(COALESCE(elem->>'skill_name', elem->>'name'))
                            )
                        )
                    )
                    LIMIT 1
                ) AS target_skill_id,
                CASE
                    WHEN lower(COALESCE(elem->>'proficiency', 'intermediate')) IN ('beginner', 'intermediate', 'advanced', 'expert')
                    THEN lower(COALESCE(elem->>'proficiency', 'intermediate'))
                    ELSE 'intermediate'
                END AS prof
            FROM jsonb_array_elements(p_profile->'skills') AS elem
            WHERE jsonb_typeof(elem) = 'object'
        ) sub
        WHERE target_skill_id IS NOT NULL
        ORDER BY target_skill_id, prof
        ON CONFLICT (user_id, skill_id) DO UPDATE SET
            proficiency = EXCLUDED.proficiency;
    END IF;

    RETURN to_jsonb(v_saved_profile);
END;
$$;

REVOKE ALL ON FUNCTION public.sync_student_profile_atomic(JSONB) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.sync_student_profile_atomic(JSONB) TO authenticated, service_role;

CREATE OR REPLACE FUNCTION public.update_employer_verification_atomic(p_params JSONB)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_employer_id TEXT;
    v_target_status TEXT;
    v_verifier_id TEXT;
    v_admin_notes TEXT;
    v_rejection_reason TEXT;
    v_verification_method TEXT;
    v_evidence_updates JSONB;
    v_emp public.employers%ROWTYPE;
    v_updated_emp public.employers%ROWTYPE;
    v_current_status TEXT;
    v_now TIMESTAMPTZ := clock_timestamp();
    v_verified_at TIMESTAMPTZ;
    v_verified_by TEXT;
    v_ver_source TEXT;
    v_ver_method TEXT;
    v_data_prov TEXT;
    v_conf INT;
    v_rej_reason TEXT;
    v_evidence JSONB;
    v_verification_id TEXT;
    v_action TEXT;
    v_sub_source TEXT;
BEGIN
    v_employer_id := p_params->>'employer_id';
    IF v_employer_id IS NULL OR trim(v_employer_id) = '' THEN
        RAISE EXCEPTION 'Employer id is required';
    END IF;

    v_target_status := upper(COALESCE(p_params->>'target_status', ''));
    IF v_target_status NOT IN ('UNVERIFIED', 'PENDING', 'VERIFIED', 'REJECTED') THEN
        RAISE EXCEPTION 'Invalid verification status %', v_target_status;
    END IF;

    SELECT * INTO v_emp FROM public.employers WHERE id = v_employer_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Employer ''%'' not found', v_employer_id;
    END IF;

    v_current_status := upper(COALESCE(v_emp.verification_status, 'UNVERIFIED'));
    IF v_current_status = 'VERIFIED' AND v_target_status = 'VERIFIED' THEN
        RAISE EXCEPTION 'Employer is already verified';
    END IF;

    v_verifier_id := p_params->>'verifier_id';
    v_admin_notes := p_params->>'admin_notes';
    v_rejection_reason := p_params->>'rejection_reason';
    v_verification_method := p_params->>'verification_method';
    v_evidence_updates := p_params->'evidence_updates';

    IF v_target_status = 'VERIFIED' THEN
        v_verified_at := v_now;
        v_verified_by := COALESCE(v_verifier_id, 'ADMIN');
        v_ver_source := 'AUTHORITATIVE_ADMIN_VERIFICATION';
        v_ver_method := COALESCE(v_verification_method, 'GOVERNMENT_REGISTRY_AND_DOCUMENT_AUDIT');
        v_data_prov := 'AUTHORITATIVE_VERIFIED';
        v_conf := 95;
        v_rej_reason := NULL;
        v_action := 'APPROVE';
        v_sub_source := 'AUTHORITATIVE_ADMIN_VERIFICATION';
    ELSIF v_target_status = 'REJECTED' THEN
        IF v_rejection_reason IS NULL OR trim(v_rejection_reason) = '' THEN
            RAISE EXCEPTION 'Rejection reason is mandatory when rejecting verification';
        END IF;
        v_verified_at := NULL;
        v_verified_by := COALESCE(v_verifier_id, 'ADMIN');
        v_ver_source := v_emp.verification_source;
        v_ver_method := v_emp.verification_method;
        v_rej_reason := trim(v_rejection_reason);
        v_data_prov := 'ADMIN_REJECTED';
        v_conf := 0;
        v_action := 'REJECT';
        v_sub_source := 'USER_SUBMITTED';
    ELSIF v_target_status = 'PENDING' THEN
        v_verified_at := NULL;
        v_verified_by := NULL;
        v_ver_source := NULL;
        v_ver_method := NULL;
        v_rej_reason := NULL;
        v_data_prov := 'EMPLOYER_SELF_DECLARED';
        v_conf := 25;
        v_action := 'SUBMIT';
        v_sub_source := 'USER_SUBMITTED';
    ELSE
        v_verified_at := NULL;
        v_verified_by := NULL;
        v_ver_source := NULL;
        v_ver_method := NULL;
        v_rej_reason := NULL;
        v_data_prov := 'UNVERIFIED';
        v_conf := 0;
        v_action := 'SUBMIT';
        v_sub_source := 'USER_SUBMITTED';
    END IF;

    v_evidence := COALESCE(v_emp.evidence, '{}'::jsonb);
    IF v_evidence_updates IS NOT NULL AND jsonb_typeof(v_evidence_updates) = 'object' THEN
        v_evidence := v_evidence || v_evidence_updates;
    END IF;

    UPDATE public.employers
    SET verification_status = v_target_status,
        verified_at = v_verified_at,
        verified_by = v_verified_by,
        verification_source = v_ver_source,
        verification_method = v_ver_method,
        data_provenance = v_data_prov,
        confidence = v_conf,
        rejection_reason = v_rej_reason,
        evidence = v_evidence,
        company_name = CASE
            WHEN v_evidence_updates ? 'company_name' THEN v_evidence_updates->>'company_name'
            ELSE company_name
        END,
        gstin = CASE
            WHEN v_evidence_updates ? 'gstin' THEN v_evidence_updates->>'gstin'
            ELSE gstin
        END,
        corporate_website = CASE
            WHEN v_evidence_updates ? 'corporate_website' THEN v_evidence_updates->>'corporate_website'
            ELSE corporate_website
        END,
        email = CASE
            WHEN v_evidence_updates ? 'email' THEN v_evidence_updates->>'email'
            ELSE email
        END,
        updated_at = v_now
    WHERE id = v_employer_id
    RETURNING * INTO v_updated_emp;

    v_verification_id := 'ev-' || substr(md5(random()::text || clock_timestamp()::text), 1, 12);

    INSERT INTO public.employer_verifications (
        id,
        employer_id,
        user_id,
        company_name,
        email,
        gstin,
        corporate_website,
        status,
        action,
        submitted_at,
        reviewed_at,
        reviewed_by,
        admin_notes,
        rejection_reason,
        data_provenance,
        source,
        is_demo,
        evidence_payload,
        confidence,
        verification_method,
        created_at,
        updated_at
    ) VALUES (
        v_verification_id,
        v_employer_id,
        v_emp.user_id,
        COALESCE(v_updated_emp.company_name, v_updated_emp.name, 'Employer'),
        v_updated_emp.email,
        v_updated_emp.gstin,
        v_updated_emp.corporate_website,
        v_target_status,
        v_action,
        COALESCE(v_emp.created_at, v_now),
        CASE WHEN v_target_status IN ('VERIFIED', 'REJECTED') THEN v_now ELSE NULL END,
        CASE WHEN v_target_status IN ('VERIFIED', 'REJECTED') THEN v_verifier_id ELSE NULL END,
        v_admin_notes,
        v_rej_reason,
        v_data_prov,
        v_sub_source,
        COALESCE(v_emp.is_demo, false),
        v_evidence,
        v_conf,
        v_ver_method,
        v_now,
        v_now
    );

    RETURN to_jsonb(v_updated_emp);
END;
$$;

REVOKE ALL ON FUNCTION public.update_employer_verification_atomic(JSONB) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.update_employer_verification_atomic(JSONB) TO service_role;

CREATE TABLE IF NOT EXISTS curriculum_proposals (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL,
    course_name TEXT NOT NULL,
    institute_id TEXT NOT NULL,
    institute_name TEXT NOT NULL,
    district TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'SUBMITTED', 'UNDER_STATE_REVIEW', 'APPROVED', 'REJECTED', 'ADOPTED')),
    target_academic_cycle TEXT NOT NULL,
    modules_to_add JSONB NOT NULL DEFAULT '[]'::jsonb,
    modules_to_prune JSONB NOT NULL DEFAULT '[]'::jsonb,
    equipment_requirements JSONB NOT NULL DEFAULT '[]'::jsonb,
    total_equipment_budget_inr BIGINT DEFAULT 0,
    trainer_upskilling JSONB NOT NULL DEFAULT '[]'::jsonb,
    supporting_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    previous_curriculum_snapshot JSONB DEFAULT '{}'::jsonb,
    adopted_curriculum_snapshot JSONB DEFAULT '{}'::jsonb,
    adoption_metadata JSONB DEFAULT '{}'::jsonb,
    data_provenance TEXT NOT NULL DEFAULT 'INSTITUTE_SUBMITTED',
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    user_id TEXT,
    user_email TEXT,
    submitted_at TIMESTAMPTZ,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    adopted_at TIMESTAMPTZ,
    adopted_by TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE courses ADD COLUMN IF NOT EXISTS curriculum_version INT DEFAULT 1;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS last_curriculum_modernization_at TIMESTAMPTZ;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS modernization_proposal_id TEXT;

CREATE INDEX IF NOT EXISTS idx_curriculum_proposals_course_id ON curriculum_proposals(course_id);
CREATE INDEX IF NOT EXISTS idx_curriculum_proposals_institute_id ON curriculum_proposals(institute_id);
CREATE INDEX IF NOT EXISTS idx_curriculum_proposals_status ON curriculum_proposals(status);
CREATE INDEX IF NOT EXISTS idx_curriculum_proposals_district ON curriculum_proposals(district);
CREATE INDEX IF NOT EXISTS idx_curriculum_proposals_is_demo ON curriculum_proposals(is_demo);

ALTER TABLE curriculum_proposals ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'curriculum_proposals'
        AND policyname = 'service_role_all_curriculum_proposals'
    ) THEN
        CREATE POLICY service_role_all_curriculum_proposals
        ON curriculum_proposals
        FOR ALL
        TO service_role
        USING (true)
        WITH CHECK (true);
    END IF;
END $$;





CREATE TABLE IF NOT EXISTS placement_outcomes (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL,
    course_name TEXT NOT NULL,
    institute_id TEXT NOT NULL,
    institute_name TEXT NOT NULL,
    employer_id TEXT,
    employer_name TEXT,
    candidate_id TEXT,
    candidate_name TEXT,
    role_title TEXT NOT NULL,
    district TEXT NOT NULL,
    industry TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'TRAINING_COMPLETED' CHECK (status IN ('TRAINING_COMPLETED', 'PLACEMENT_PENDING', 'PLACED', 'EMPLOYED', 'EMPLOYER_FEEDBACK_PENDING', 'FEEDBACK_RECEIVED', 'NOT_PLACED', 'WITHDRAWN', 'UNKNOWN')),
    placement_date DATE,
    salary_annual_inr INT,
    skills_utilized JSONB NOT NULL DEFAULT '[]'::jsonb,
    source TEXT NOT NULL DEFAULT 'INSTITUTE_REPORTED',
    data_provenance TEXT NOT NULL DEFAULT 'INSTITUTE_AUTHORITATIVE',
    verification_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (verification_status IN ('VERIFIED', 'PENDING', 'UNVERIFIED', 'REJECTED')),
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    user_id TEXT,
    user_email TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS placement_employer_feedback (
    id TEXT PRIMARY KEY,
    placement_outcome_id TEXT NOT NULL REFERENCES placement_outcomes(id) ON DELETE CASCADE,
    employer_id TEXT NOT NULL,
    employer_name TEXT NOT NULL,
    skill_adequacy_score INT NOT NULL CHECK (skill_adequacy_score BETWEEN 1 AND 5),
    practical_readiness TEXT NOT NULL CHECK (practical_readiness IN ('PRODUCTION_READY', 'NEEDS_SUPERVISION', 'UNPREPARED')),
    missing_skills JSONB NOT NULL DEFAULT '[]'::jsonb,
    training_relevance TEXT NOT NULL CHECK (training_relevance IN ('HIGHLY_RELEVANT', 'PARTIALLY_RELEVANT', 'OUTDATED')),
    hiring_difficulty TEXT NOT NULL CHECK (hiring_difficulty IN ('LOW', 'MODERATE', 'EXTREME')),
    feedback_notes TEXT,
    is_verified_employer BOOLEAN NOT NULL DEFAULT FALSE,
    source TEXT NOT NULL DEFAULT 'EMPLOYER_SUBMITTED',
    data_provenance TEXT NOT NULL DEFAULT 'EMPLOYER_VERIFIED',
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    user_id TEXT,
    user_email TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_placement_feedback_outcome UNIQUE (placement_outcome_id)
);

CREATE INDEX IF NOT EXISTS idx_placement_outcomes_course_id ON placement_outcomes(course_id);
CREATE INDEX IF NOT EXISTS idx_placement_outcomes_institute_id ON placement_outcomes(institute_id);
CREATE INDEX IF NOT EXISTS idx_placement_outcomes_employer_id ON placement_outcomes(employer_id);
CREATE INDEX IF NOT EXISTS idx_placement_outcomes_status ON placement_outcomes(status);
CREATE INDEX IF NOT EXISTS idx_placement_outcomes_district ON placement_outcomes(district);
CREATE INDEX IF NOT EXISTS idx_placement_outcomes_is_demo ON placement_outcomes(is_demo);

CREATE INDEX IF NOT EXISTS idx_placement_feedback_outcome_id ON placement_employer_feedback(placement_outcome_id);
CREATE INDEX IF NOT EXISTS idx_placement_feedback_employer_id ON placement_employer_feedback(employer_id);
CREATE INDEX IF NOT EXISTS idx_placement_feedback_is_demo ON placement_employer_feedback(is_demo);

ALTER TABLE placement_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE placement_employer_feedback ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'placement_outcomes'
        AND policyname = 'service_role_all_placement_outcomes'
    ) THEN
        CREATE POLICY service_role_all_placement_outcomes
        ON placement_outcomes
        FOR ALL
        TO service_role
        USING (true)
        WITH CHECK (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'placement_employer_feedback'
        AND policyname = 'service_role_all_placement_employer_feedback'
    ) THEN
        CREATE POLICY service_role_all_placement_employer_feedback
        ON placement_employer_feedback
        FOR ALL
        TO service_role
        USING (true)
        WITH CHECK (true);
    END IF;
END $$;

ALTER TABLE placement_outcomes 
ADD COLUMN IF NOT EXISTS retention_status TEXT 
CHECK (retention_status IN ('6_MONTH_RETAINED', '12_MONTH_RETAINED', 'ATTRITED', 'UNKNOWN'));

CREATE TABLE IF NOT EXISTS institution_accreditations (
    id TEXT PRIMARY KEY,
    institute_id TEXT NOT NULL,
    institute_name TEXT NOT NULL,
    district TEXT NOT NULL,
    composite_score NUMERIC(5, 2) NOT NULL,
    accreditation_tier TEXT NOT NULL CHECK (accreditation_tier IN ('TIER_1_EXCELLENCE', 'TIER_2_ACCREDITED', 'TIER_3_PROVISIONAL', 'TIER_4_PERFORMANCE_WATCH')),
    placement_score NUMERIC(5, 2) NOT NULL,
    curriculum_score NUMERIC(5, 2) NOT NULL,
    employer_satisfaction_score NUMERIC(5, 2) NOT NULL,
    wage_premium_score NUMERIC(5, 2) NOT NULL,
    evidence_confidence TEXT NOT NULL CHECK (evidence_confidence IN ('HIGH', 'MODERATE', 'LOW', 'INSUFFICIENT_EVIDENCE')),
    total_candidates_evaluated INT NOT NULL DEFAULT 0,
    placed_candidates INT NOT NULL DEFAULT 0,
    average_salary_inr INT NOT NULL DEFAULT 0,
    roi_multiplier NUMERIC(6, 2) NOT NULL DEFAULT 1.0,
    valid_until DATE,
    evaluator_user_id TEXT,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    data_provenance TEXT NOT NULL DEFAULT 'STATE_DETERMINISTIC_ACCREDITATION',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS institution_audit_notices (
    id TEXT PRIMARY KEY,
    institute_id TEXT NOT NULL,
    institute_name TEXT NOT NULL,
    district TEXT NOT NULL,
    notice_type TEXT NOT NULL CHECK (notice_type IN ('PERFORMANCE_WARNING', 'CURRICULUM_DEFICIT', 'COMPLIANCE_REVIEW', 'EXCELLENCE_COMMENDATION')),
    severity TEXT NOT NULL CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'INFO')),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    mandated_action TEXT,
    deadline_date DATE,
    status TEXT NOT NULL DEFAULT 'ISSUED' CHECK (status IN ('ISSUED', 'IN_REMEDIATION', 'RESOLVED', 'ESCALATED')),
    issued_by TEXT NOT NULL,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_accreditations_inst_id ON institution_accreditations(institute_id);
CREATE INDEX IF NOT EXISTS idx_accreditations_district ON institution_accreditations(district);
CREATE INDEX IF NOT EXISTS idx_accreditations_tier ON institution_accreditations(accreditation_tier);
CREATE INDEX IF NOT EXISTS idx_accreditations_is_demo ON institution_accreditations(is_demo);
CREATE INDEX IF NOT EXISTS idx_audit_notices_inst_id ON institution_audit_notices(institute_id);
CREATE INDEX IF NOT EXISTS idx_audit_notices_status ON institution_audit_notices(status);
CREATE INDEX IF NOT EXISTS idx_audit_notices_is_demo ON institution_audit_notices(is_demo);

ALTER TABLE institution_accreditations ENABLE ROW LEVEL SECURITY;
ALTER TABLE institution_audit_notices ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'institution_accreditations'
        AND policyname = 'service_role_all_accreditations'
    ) THEN
        CREATE POLICY service_role_all_accreditations
        ON institution_accreditations
        FOR ALL
        TO service_role
        USING (true)
        WITH CHECK (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'institution_audit_notices'
        AND policyname = 'service_role_all_audit_notices'
    ) THEN
        CREATE POLICY service_role_all_audit_notices
        ON institution_audit_notices
        FOR ALL
        TO service_role
        USING (true)
        WITH CHECK (true);
    END IF;
END $$;

