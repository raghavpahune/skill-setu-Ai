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
