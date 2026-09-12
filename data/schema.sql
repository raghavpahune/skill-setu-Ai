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
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    industry TEXT NOT NULL,
    district TEXT NOT NULL
);

-- ============================================================
-- EMPLOYER_FEEDBACK (validation: confirm/correct/reject)
-- ============================================================
CREATE TABLE IF NOT EXISTS employer_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employer_id UUID REFERENCES employers(id) ON DELETE CASCADE,
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
        WHERE elem ? 'proficiency'
          AND lower(elem->>'proficiency') NOT IN ('beginner', 'intermediate', 'advanced', 'expert')
        LIMIT 1;

        IF v_invalid_skill IS NOT NULL THEN
            RAISE EXCEPTION 'Invalid skill proficiency: %', v_invalid_skill;
        END IF;
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
        NULLIF(p_profile->>'graduation_year', '')::INT,
        COALESCE(p_profile->>'target_role', p_profile->>'desired_role', ''),
        p_profile->>'desired_role',
        p_profile->>'preferred_location',
        COALESCE(
            ARRAY(SELECT jsonb_array_elements_text(COALESCE(p_profile->'career_interests', '[]'::jsonb))),
            '{}'::text[]
        ),
        COALESCE(p_profile->'skills', '[]'::jsonb),
        COALESCE(p_profile->'projects', '[]'::jsonb),
        COALESCE(p_profile->'certifications', '[]'::jsonb),
        COALESCE(p_profile->'courses', '[]'::jsonb),
        COALESCE(p_profile->'experience', '[]'::jsonb),
        CASE
            WHEN p_profile ? 'skill_match_pct' THEN (p_profile->>'skill_match_pct')::INT
            ELSE 0
        END,
        COALESCE(p_profile->>'source', 'USER_SUBMITTED'),
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
        career_interests = CASE WHEN p_profile ? 'career_interests' THEN EXCLUDED.career_interests ELSE student_profiles.career_interests END,
        skills = CASE WHEN p_profile ? 'skills' THEN EXCLUDED.skills ELSE student_profiles.skills END,
        projects = CASE WHEN p_profile ? 'projects' THEN EXCLUDED.projects ELSE student_profiles.projects END,
        certifications = CASE WHEN p_profile ? 'certifications' THEN EXCLUDED.certifications ELSE student_profiles.certifications END,
        courses = CASE WHEN p_profile ? 'courses' THEN EXCLUDED.courses ELSE student_profiles.courses END,
        experience = CASE WHEN p_profile ? 'experience' THEN EXCLUDED.experience ELSE student_profiles.experience END,
        skill_match_pct = CASE
            WHEN p_profile ? 'skill_match_pct' THEN EXCLUDED.skill_match_pct
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
                  SELECT DISTINCT COALESCE(
                      CASE
                          WHEN (elem->>'skill_id') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                          THEN (elem->>'skill_id')::uuid
                          WHEN (elem->>'id') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                          THEN (elem->>'id')::uuid
                          ELSE NULL
                      END,
                      (
                          SELECT s.id FROM public.skills s
                          WHERE lower(s.name) = lower(COALESCE(elem->>'skill_name', elem->>'name', ''))
                             OR EXISTS (
                                 SELECT 1 FROM unnest(COALESCE(s.synonyms, '{}'::text[])) syn
                                 WHERE lower(syn) = lower(COALESCE(elem->>'skill_name', elem->>'name', ''))
                             )
                          LIMIT 1
                      )
                  ) AS resolved_skill_id
                  FROM jsonb_array_elements(p_profile->'skills') AS elem
                  WHERE COALESCE(elem->>'skill_id', elem->>'id', elem->>'skill_name', elem->>'name') IS NOT NULL
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
                COALESCE(
                    CASE
                        WHEN (elem->>'skill_id') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                        THEN (elem->>'skill_id')::uuid
                        WHEN (elem->>'id') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                        THEN (elem->>'id')::uuid
                        ELSE NULL
                    END,
                    (
                        SELECT s.id FROM public.skills s
                        WHERE lower(s.name) = lower(COALESCE(elem->>'skill_name', elem->>'name', ''))
                           OR EXISTS (
                               SELECT 1 FROM unnest(COALESCE(s.synonyms, '{}'::text[])) syn
                               WHERE lower(syn) = lower(COALESCE(elem->>'skill_name', elem->>'name', ''))
                           )
                        LIMIT 1
                    )
                ) AS target_skill_id,
                CASE
                    WHEN lower(COALESCE(elem->>'proficiency', 'intermediate')) IN ('beginner', 'intermediate', 'advanced', 'expert')
                    THEN lower(COALESCE(elem->>'proficiency', 'intermediate'))
                    ELSE 'intermediate'
                END AS prof
            FROM jsonb_array_elements(p_profile->'skills') AS elem
            WHERE COALESCE(elem->>'skill_id', elem->>'id', elem->>'skill_name', elem->>'name') IS NOT NULL
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
