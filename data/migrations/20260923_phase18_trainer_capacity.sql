CREATE TABLE IF NOT EXISTS institution_trainers (
    id TEXT PRIMARY KEY,
    institute_id TEXT NOT NULL,
    institute_name TEXT NOT NULL,
    district TEXT NOT NULL,
    name TEXT NOT NULL,
    employee_id TEXT,
    email TEXT,
    phone TEXT,
    designation TEXT NOT NULL DEFAULT 'Technical Instructor',
    primary_trade TEXT NOT NULL,
    skills JSONB NOT NULL DEFAULT '[]'::jsonb,
    certifications JSONB NOT NULL DEFAULT '[]'::jsonb,
    assigned_course_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    certified_skills JSONB NOT NULL DEFAULT '[]'::jsonb,
    years_experience INT NOT NULL DEFAULT 0,
    experience_years NUMERIC NOT NULL DEFAULT 0,
    industry_experience_years NUMERIC NOT NULL DEFAULT 0,
    highest_qualification TEXT,
    nsqf_certified_level INT NOT NULL DEFAULT 5,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'IN_TRAINING', 'ON_LEAVE', 'RETIRED')),
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    data_provenance TEXT NOT NULL DEFAULT 'INSTITUTE_AUTHORITATIVE',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE institution_trainers ADD COLUMN IF NOT EXISTS employee_id TEXT;
ALTER TABLE institution_trainers ADD COLUMN IF NOT EXISTS skills JSONB DEFAULT '[]'::jsonb;
ALTER TABLE institution_trainers ADD COLUMN IF NOT EXISTS certifications JSONB DEFAULT '[]'::jsonb;
ALTER TABLE institution_trainers ADD COLUMN IF NOT EXISTS experience_years NUMERIC DEFAULT 0;
ALTER TABLE institution_trainers ADD COLUMN IF NOT EXISTS industry_experience_years NUMERIC DEFAULT 0;
ALTER TABLE institution_trainers ADD COLUMN IF NOT EXISTS highest_qualification TEXT;

CREATE TABLE IF NOT EXISTS faculty_upskilling_nominations (
    id TEXT PRIMARY KEY,
    trainer_id TEXT NOT NULL REFERENCES institution_trainers(id) ON DELETE CASCADE,
    trainer_name TEXT NOT NULL,
    institute_id TEXT NOT NULL,
    institute_name TEXT NOT NULL,
    district TEXT NOT NULL,
    course_id TEXT,
    target_course_id TEXT,
    target_course_name TEXT,
    program_code TEXT,
    program_title TEXT,
    program_name TEXT NOT NULL,
    domain TEXT,
    partner_agency TEXT,
    certifying_body TEXT NOT NULL,
    duration_weeks INT NOT NULL DEFAULT 2,
    target_skills JSONB NOT NULL DEFAULT '[]'::jsonb,
    budget_inr INT NOT NULL DEFAULT 0,
    stipend_grant_inr INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'NOMINATED' CHECK (status IN ('NOMINATED', 'SANCTIONED', 'IN_PROGRESS', 'COMPLETED', 'REJECTED')),
    rationale TEXT,
    justification TEXT,
    nominated_at TIMESTAMPTZ,
    reviewed_by TEXT,
    review_notes TEXT,
    approved_by TEXT,
    sanctioned_at TIMESTAMPTZ,
    sanction_reference TEXT,
    sanction_amount_inr INT,
    completion_certificate_id TEXT,
    completion_date TEXT,
    completed_at TIMESTAMPTZ,
    certification_earned TEXT,
    feedback TEXT,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    data_provenance TEXT NOT NULL DEFAULT 'INSTITUTE_NOMINATION',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE faculty_upskilling_nominations ADD COLUMN IF NOT EXISTS course_id TEXT;
ALTER TABLE faculty_upskilling_nominations ADD COLUMN IF NOT EXISTS program_code TEXT;
ALTER TABLE faculty_upskilling_nominations ADD COLUMN IF NOT EXISTS program_title TEXT;
ALTER TABLE faculty_upskilling_nominations ADD COLUMN IF NOT EXISTS domain TEXT;
ALTER TABLE faculty_upskilling_nominations ADD COLUMN IF NOT EXISTS partner_agency TEXT;
ALTER TABLE faculty_upskilling_nominations ADD COLUMN IF NOT EXISTS budget_inr INT DEFAULT 0;
ALTER TABLE faculty_upskilling_nominations ADD COLUMN IF NOT EXISTS rationale TEXT;
ALTER TABLE faculty_upskilling_nominations ADD COLUMN IF NOT EXISTS nominated_at TIMESTAMPTZ;
ALTER TABLE faculty_upskilling_nominations ADD COLUMN IF NOT EXISTS approved_by TEXT;
ALTER TABLE faculty_upskilling_nominations ADD COLUMN IF NOT EXISTS sanctioned_at TIMESTAMPTZ;
ALTER TABLE faculty_upskilling_nominations ADD COLUMN IF NOT EXISTS sanction_reference TEXT;
ALTER TABLE faculty_upskilling_nominations ADD COLUMN IF NOT EXISTS sanction_amount_inr INT;
ALTER TABLE faculty_upskilling_nominations ADD COLUMN IF NOT EXISTS completion_date TEXT;
ALTER TABLE faculty_upskilling_nominations ADD COLUMN IF NOT EXISTS certification_earned TEXT;
ALTER TABLE faculty_upskilling_nominations ADD COLUMN IF NOT EXISTS feedback TEXT;

CREATE INDEX IF NOT EXISTS idx_trainers_institute_id ON institution_trainers(institute_id);
CREATE INDEX IF NOT EXISTS idx_trainers_district ON institution_trainers(district);
CREATE INDEX IF NOT EXISTS idx_trainers_trade ON institution_trainers(primary_trade);
CREATE INDEX IF NOT EXISTS idx_trainers_is_demo ON institution_trainers(is_demo);

CREATE INDEX IF NOT EXISTS idx_nominations_trainer_id ON faculty_upskilling_nominations(trainer_id);
CREATE INDEX IF NOT EXISTS idx_nominations_institute_id ON faculty_upskilling_nominations(institute_id);
CREATE INDEX IF NOT EXISTS idx_nominations_status ON faculty_upskilling_nominations(status);
CREATE INDEX IF NOT EXISTS idx_nominations_is_demo ON faculty_upskilling_nominations(is_demo);

ALTER TABLE institution_trainers ENABLE ROW LEVEL SECURITY;
ALTER TABLE faculty_upskilling_nominations ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'institution_trainers'
        AND policyname = 'service_role_all_trainers'
    ) THEN
        CREATE POLICY service_role_all_trainers
        ON institution_trainers
        FOR ALL
        TO service_role
        USING (true)
        WITH CHECK (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'faculty_upskilling_nominations'
        AND policyname = 'service_role_all_nominations'
    ) THEN
        CREATE POLICY service_role_all_nominations
        ON faculty_upskilling_nominations
        FOR ALL
        TO service_role
        USING (true)
        WITH CHECK (true);
    END IF;
END $$;
