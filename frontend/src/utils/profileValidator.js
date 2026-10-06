export const ALLOWED_PROFICIENCIES = ['beginner', 'intermediate', 'advanced', 'expert'];

export function normalizeProficiency(val) {
  if (!val || typeof val !== 'string') {
    return 'beginner';
  }
  const clean = val.trim().toLowerCase();
  if (ALLOWED_PROFICIENCIES.includes(clean)) {
    return clean;
  }
  return 'beginner';
}

export function deduplicateSkills(skills) {
  if (!Array.isArray(skills)) {
    return [];
  }
  const seen = new Map();
  for (const item of skills) {
    if (!item) continue;
    const name = (item.skill_name || item.name || '').trim();
    if (!name) continue;
    const key = name.toLowerCase();
    const proficiency = normalizeProficiency(item.proficiency);
    const skill_id = item.skill_id && typeof item.skill_id === 'string' ? item.skill_id.trim() : null;
    const verified = Boolean(item.verified);
    seen.set(key, {
      skill_name: name,
      proficiency,
      skill_id,
      verified,
    });
  }
  return Array.from(seen.values());
}

export function formatStudentProfilePayload(form) {
  if (!form || typeof form !== 'object') {
    return {};
  }
  const skills = deduplicateSkills(form.skills);
  const projects = Array.isArray(form.projects)
    ? form.projects.map((p) => ({
        name: (p.name || '').trim(),
        description: (p.description || '').trim(),
        skills: Array.isArray(p.skills)
          ? p.skills.map((s) => (typeof s === 'string' ? s.trim() : '')).filter(Boolean)
          : [],
        url: p.url && typeof p.url === 'string' && p.url.trim() ? p.url.trim() : null,
      })).filter((p) => p.name)
    : [];

  const certifications = Array.isArray(form.certifications)
    ? form.certifications.map((c) => ({
        name: (c.name || '').trim(),
        issuer: (c.issuer || '').trim(),
        issue_date: c.issue_date && typeof c.issue_date === 'string' && c.issue_date.trim() ? c.issue_date.trim() : null,
        url: c.url && typeof c.url === 'string' && c.url.trim() ? c.url.trim() : null,
      })).filter((c) => c.name && c.issuer)
    : [];

  const courses = Array.isArray(form.courses)
    ? form.courses.map((co) => ({
        course_name: (co.course_name || co.name || '').trim(),
        provider: co.provider && typeof co.provider === 'string' && co.provider.trim() ? co.provider.trim() : null,
        status: (co.status || 'completed').trim().toLowerCase(),
      })).filter((co) => co.course_name)
    : [];

  const experience = Array.isArray(form.experience)
    ? form.experience.map((e) => ({
        company: (e.company || '').trim(),
        role: (e.role || '').trim(),
        duration: e.duration && typeof e.duration === 'string' && e.duration.trim() ? e.duration.trim() : null,
        description: (e.description || '').trim(),
      })).filter((e) => e.company && e.role)
    : [];

  const gradYear = form.graduation_year !== undefined && form.graduation_year !== null && form.graduation_year !== ''
    ? (Number.isInteger(Number(form.graduation_year)) ? parseInt(form.graduation_year, 10) : Number(form.graduation_year))
    : null;

  return {
    full_name: form.full_name && typeof form.full_name === 'string' && form.full_name.trim() ? form.full_name.trim() : null,
    institution: form.institution && typeof form.institution === 'string' && form.institution.trim() ? form.institution.trim() : null,
    degree: form.degree && typeof form.degree === 'string' && form.degree.trim() ? form.degree.trim() : null,
    education_level: form.education_level && typeof form.education_level === 'string' && form.education_level.trim() ? form.education_level.trim() : null,
    academic_year: form.academic_year && typeof form.academic_year === 'string' && form.academic_year.trim() ? form.academic_year.trim() : null,
    graduation_year: gradYear,
    desired_role: form.desired_role && typeof form.desired_role === 'string' && form.desired_role.trim() ? form.desired_role.trim() : null,
    target_role: form.desired_role && typeof form.desired_role === 'string' && form.desired_role.trim() ? form.desired_role.trim() : (form.target_role && typeof form.target_role === 'string' && form.target_role.trim() ? form.target_role.trim() : null),
    preferred_location: form.preferred_location && typeof form.preferred_location === 'string' && form.preferred_location.trim() ? form.preferred_location.trim() : null,
    career_interests: Array.isArray(form.career_interests)
      ? Array.from(new Set(form.career_interests.map((ci) => (typeof ci === 'string' ? ci.trim() : '')).filter(Boolean)))
      : [],
    skills,
    projects,
    certifications,
    courses,
    experience,
  };
}

export function formatEmployeeProfilePayload(form) {
  if (!form || typeof form !== 'object') {
    return {};
  }
  const skills = deduplicateSkills(form.skills);
  const certifications = Array.isArray(form.certifications)
    ? form.certifications.map((c) => ({
        name: (c.name || '').trim(),
        issuer: (c.issuer || '').trim(),
        issue_date: c.issue_date && typeof c.issue_date === 'string' && c.issue_date.trim() ? c.issue_date.trim() : null,
        url: c.url && typeof c.url === 'string' && c.url.trim() ? c.url.trim() : null,
      })).filter((c) => c.name && c.issuer)
    : [];

  const yoe = form.years_of_experience !== undefined && form.years_of_experience !== null && form.years_of_experience !== ''
    ? parseFloat(form.years_of_experience)
    : 0;

  return {
    current_role: (form.current_role || '').trim(),
    years_of_experience: !Number.isNaN(yoe) ? yoe : 0,
    industry: form.industry && typeof form.industry === 'string' && form.industry.trim() ? form.industry.trim() : null,
    education: form.education && typeof form.education === 'string' && form.education.trim() ? form.education.trim() : null,
    target_role: form.target_role && typeof form.target_role === 'string' && form.target_role.trim() ? form.target_role.trim() : null,
    preferred_location: form.preferred_location && typeof form.preferred_location === 'string' && form.preferred_location.trim() ? form.preferred_location.trim() : null,
    skills,
    certifications,
  };
}

export function validateStudentProfile(payload) {
  const errors = [];
  if (!payload || typeof payload !== 'object') {
    return { isValid: false, errors: ['Profile payload must be an object'] };
  }
  if (payload.graduation_year !== null && payload.graduation_year !== undefined) {
    if (!Number.isInteger(payload.graduation_year) || payload.graduation_year < 1970 || payload.graduation_year > 2100) {
      errors.push('Graduation year must be a valid year between 1970 and 2100');
    }
  }
  return {
    isValid: errors.length === 0,
    errors,
  };
}

export function validateEmployeeProfile(payload) {
  const errors = [];
  if (!payload || typeof payload !== 'object') {
    return { isValid: false, errors: ['Profile payload must be an object'] };
  }
  if (!payload.current_role || !payload.current_role.trim()) {
    errors.push('Current role is required for employee profile');
  }
  if (typeof payload.years_of_experience !== 'number' || Number.isNaN(payload.years_of_experience) || payload.years_of_experience < 0 || payload.years_of_experience > 70) {
    errors.push('Years of experience must be between 0 and 70');
  }
  return {
    isValid: errors.length === 0,
    errors,
  };
}
