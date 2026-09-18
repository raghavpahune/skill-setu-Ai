CREATE OR REPLACE FUNCTION canonical_gov_opportunity_id(p_name text, p_dept text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT 'gov-' || substring(
        encode(
            sha256(
                (
                    length(lower(trim(coalesce(p_name, ''))))::text || ':' ||
                    lower(trim(coalesce(p_name, ''))) || ':' ||
                    length(lower(trim(coalesce(p_dept, ''))))::text || ':' ||
                    lower(trim(coalesce(p_dept, '')))
                )::bytea
            ),
            'hex'
        )
        FROM 1 FOR 32
    );
$$;

DO $$
DECLARE
    v_group RECORD;
    v_survivor_id text;
BEGIN
    FOR v_group IN
        SELECT
            canonical_gov_opportunity_id(name, department) AS target_canonical_id,
            count(*) AS cnt
        FROM gov_opportunities
        WHERE name IS NOT NULL AND trim(name) <> ''
        GROUP BY canonical_gov_opportunity_id(name, department)
        HAVING count(*) > 1
    LOOP
        SELECT id INTO v_survivor_id
        FROM gov_opportunities
        WHERE canonical_gov_opportunity_id(name, department) = v_group.target_canonical_id
        ORDER BY
            CASE WHEN is_demo = false THEN 0 ELSE 1 END ASC,
            CASE data_provenance
                WHEN 'GOVERNMENT_OFFICIAL' THEN 1
                WHEN 'VERIFIED_SNAPSHOT' THEN 2
                WHEN 'USER_SUBMITTED' THEN 3
                WHEN 'ADMIN_CREATED' THEN 4
                WHEN 'UNVERIFIED_EXTERNAL_SOURCE' THEN 5
                ELSE 6
            END ASC,
            CASE verification_status
                WHEN 'VERIFIED' THEN 1
                WHEN 'APPROVED' THEN 1
                WHEN 'PENDING' THEN 2
                ELSE 3
            END ASC,
            CASE WHEN status = 'active' THEN 0 ELSE 1 END ASC,
            updated_at DESC NULLS LAST,
            created_at DESC NULLS LAST,
            id ASC
        LIMIT 1;

        UPDATE gov_opportunities s
        SET
            description = COALESCE(NULLIF(s.description, ''), d.description),
            eligibility_criteria = COALESCE(NULLIF(s.eligibility_criteria, ''), d.eligibility_criteria),
            application_url = COALESCE(NULLIF(s.application_url, ''), d.application_url),
            deadline = COALESCE(NULLIF(s.deadline, ''), d.deadline),
            target_skills = (
                SELECT ARRAY(
                    SELECT DISTINCT unnest(COALESCE(s.target_skills, '{}'::text[]) || COALESCE(d.target_skills, '{}'::text[]))
                )
            ),
            district_coverage = (
                SELECT ARRAY(
                    SELECT DISTINCT unnest(COALESCE(s.district_coverage, '{}'::text[]) || COALESCE(d.district_coverage, '{}'::text[]))
                )
            ),
            created_at = LEAST(s.created_at, d.created_at),
            updated_at = GREATEST(s.updated_at, d.updated_at)
        FROM (
            SELECT
                v_group.target_canonical_id AS target_canonical_id,
                (ARRAY_AGG(description ORDER BY updated_at DESC) FILTER (WHERE description IS NOT NULL AND description <> ''))[1] AS description,
                (ARRAY_AGG(eligibility_criteria ORDER BY updated_at DESC) FILTER (WHERE eligibility_criteria IS NOT NULL AND eligibility_criteria <> ''))[1] AS eligibility_criteria,
                (ARRAY_AGG(application_url ORDER BY updated_at DESC) FILTER (WHERE application_url IS NOT NULL AND application_url <> ''))[1] AS application_url,
                (ARRAY_AGG(deadline ORDER BY updated_at DESC) FILTER (WHERE deadline IS NOT NULL AND deadline <> ''))[1] AS deadline,
                (
                    SELECT ARRAY(
                        SELECT DISTINCT unnest(COALESCE(target_skills, '{}'::text[]))
                        FROM gov_opportunities sub
                        WHERE canonical_gov_opportunity_id(sub.name, sub.department) = v_group.target_canonical_id
                    )
                ) AS target_skills,
                (
                    SELECT ARRAY(
                        SELECT DISTINCT unnest(COALESCE(district_coverage, '{}'::text[]))
                        FROM gov_opportunities sub
                        WHERE canonical_gov_opportunity_id(sub.name, sub.department) = v_group.target_canonical_id
                    )
                ) AS district_coverage,
                MIN(created_at) AS created_at,
                MAX(updated_at) AS updated_at
            FROM gov_opportunities
            WHERE canonical_gov_opportunity_id(name, department) = v_group.target_canonical_id
        ) d
        WHERE s.id = v_survivor_id;

        DELETE FROM gov_opportunities
        WHERE canonical_gov_opportunity_id(name, department) = v_group.target_canonical_id
          AND id <> v_survivor_id;
    END LOOP;

    FOR v_group IN
        SELECT
            id,
            canonical_gov_opportunity_id(name, department) AS target_canonical_id
        FROM gov_opportunities
        WHERE name IS NOT NULL AND trim(name) <> ''
          AND id <> canonical_gov_opportunity_id(name, department)
    LOOP
        UPDATE gov_opportunities
        SET id = v_group.target_canonical_id
        WHERE id = v_group.id;
    END LOOP;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_gov_opportunities_canonical_key
ON gov_opportunities (lower(trim(name)), lower(trim(coalesce(department, ''))))
WHERE name IS NOT NULL AND trim(name) <> '';
