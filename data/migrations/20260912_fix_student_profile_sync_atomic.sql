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
