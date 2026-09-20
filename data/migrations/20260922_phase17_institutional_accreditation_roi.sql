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
    remediation_notes TEXT,
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
