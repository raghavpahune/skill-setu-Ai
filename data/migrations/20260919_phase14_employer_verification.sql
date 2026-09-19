ALTER TABLE employer_feedback DROP CONSTRAINT IF EXISTS employer_feedback_employer_id_fkey;
ALTER TABLE employer_feedback ALTER COLUMN employer_id TYPE TEXT USING employer_id::text;
ALTER TABLE employers ALTER COLUMN id TYPE TEXT USING id::text;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'employer_feedback_employer_id_fkey'
    ) THEN
        ALTER TABLE employer_feedback
        ADD CONSTRAINT employer_feedback_employer_id_fkey
        FOREIGN KEY (employer_id) REFERENCES employers(id) ON DELETE CASCADE;
    END IF;
END $$;

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

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS employer_id TEXT;
CREATE INDEX IF NOT EXISTS idx_jobs_employer_id ON jobs(employer_id);

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
GRANT EXECUTE ON FUNCTION public.update_employer_verification_atomic(JSONB) TO authenticated, service_role;
