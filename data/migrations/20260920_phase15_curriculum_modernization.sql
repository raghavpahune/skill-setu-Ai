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
