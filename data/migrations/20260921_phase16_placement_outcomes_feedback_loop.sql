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

ALTER TABLE placement_employer_feedback ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

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
