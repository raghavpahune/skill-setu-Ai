function getApiBase() {
  // 1. Explicit Vite environment variable (baked in at build time)
  const envUrl = import.meta.env?.VITE_API_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim()) {
    const clean = envUrl.trim().replace(/\/+$/, '');
    return clean.endsWith('/api') ? clean : `${clean}/api`;
  }

  // 2. Runtime override via window or localStorage (allows instant configuration without rebuild)
  if (typeof window !== 'undefined') {
    const localOverride = window.localStorage?.getItem('skillsetu_api_url') || window.__SKILLSETU_API_URL__;
    if (localOverride && typeof localOverride === 'string' && localOverride.trim()) {
      const clean = localOverride.trim().replace(/\/+$/, '');
      return clean.endsWith('/api') ? clean : `${clean}/api`;
    }

    // 3. Localhost development
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      return 'http://127.0.0.1:8000/api';
    }
  }

  // 4. Production default relative URL (works seamlessly with same-origin or Vercel rewrites)
  return '/api';
}

const API_BASE = getApiBase();

async function fetchJSON(endpoint, options = {}) {
  const base = getApiBase();
  const url = `${base}${endpoint}`;
  
  const token = typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_auth_token') : null;
  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};

  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const isBlob = typeof Blob !== 'undefined' && options.body instanceof Blob;

  const defaultHeaders = (!isFormData && !isBlob)
    ? { 'Content-Type': 'application/json', ...authHeaders }
    : { ...authHeaders };

  const mergedHeaders = {
    ...defaultHeaders,
    ...(options.headers || {}),
  };

  let finalBody = options.body;
  if (
    finalBody !== undefined &&
    finalBody !== null &&
    typeof finalBody === 'object' &&
    !isFormData &&
    !isBlob
  ) {
    finalBody = JSON.stringify(finalBody);
  }

  const controller = new AbortController();
  let isTimedOut = false;
  const timeoutId = setTimeout(() => {
    isTimedOut = true;
    controller.abort();
  }, 25000);

  if (options.signal) {
    if (options.signal.aborted) {
      controller.abort();
    } else {
      options.signal.addEventListener('abort', () => controller.abort(), { once: true });
    }
  }

  try {
    const res = await fetch(url, {
      ...options,
      headers: mergedHeaders,
      body: finalBody,
      signal: controller.signal,
    });

    if (!res.ok) {
      const errText = await res.text().catch(() => '');
      let errMsg = `API error: ${res.status} ${res.statusText}`;
      try {
        const errJson = JSON.parse(errText);
        if (errJson.detail) errMsg = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
        if (errJson.message) errMsg = errJson.message;
      } catch {
        if (errText && errText.length < 120 && !errText.includes('<html')) {
          errMsg = errText;
        }
      }
      if (errText && (errText.includes('<!DOCTYPE') || errText.includes('<html'))) {
        errMsg = `Backend API at "${base}" returned HTTP ${res.status} HTML. Verify VITE_API_URL or backend service status.`;
      }
      const apiErr = new Error(errMsg);
      apiErr.status = res.status;
      throw apiErr;
    }

    const contentType = res.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
      const text = await res.text();
      if (text.includes('<!DOCTYPE') || text.includes('<html')) {
        throw new Error(
          `Backend API is not reachable at "${url}". The request returned an HTML page instead of JSON. Configure VITE_API_URL to point to your deployed Render backend.`
        );
      }
      try {
        return JSON.parse(text);
      } catch {
        return text;
      }
    }

    return await res.json();
  } catch (err) {
    if (isTimedOut || (err && err.name === 'AbortError' && isTimedOut)) {
      const timeoutErr = new Error('Request timed out after 25 seconds. Please check your network connection and backend availability.');
      timeoutErr.isTimeout = true;
      throw timeoutErr;
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

export const api = {
  // Authentication & RBAC (Phase 23)
  login: (email, password) => fetchJSON('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  }),
  register: (userData) => fetchJSON('/auth/register', {
    method: 'POST',
    body: JSON.stringify(userData),
  }),
  getMe: () => fetchJSON('/auth/me'),
  logout: () => fetchJSON('/auth/logout', { method: 'POST' }),

  // Health
  getHealth: () => fetchJSON('/health'),

  // Skills & Demand
  getSkills: () => fetchJSON('/skills'),
  getSkill: (id) => fetchJSON(`/skills/${id}`),
  getJobs: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJSON(`/jobs${query ? `?${query}` : ''}`);
  },
  getJobDemand: (groupBy = 'district') => fetchJSON(`/jobs/demand?group_by=${groupBy}`),

  // Skill Gaps
  getGaps: (district) => fetchJSON(district ? `/gaps/district/${district}` : '/gaps'),

  // Courses & Health
  getCourses: () => fetchJSON('/courses'),
  getCourseRecommendations: () => fetchJSON('/courses/recommendations'),

  getSignals: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJSON(`/industry/signals${query ? `?${query}` : ''}`);
  },
  getForecasts: (skillId) => fetchJSON(skillId ? `/forecast/skill/${skillId}` : '/forecast'),

  // Districts & Platform Metrics (§13 & §33)
  getDistricts: () => fetchJSON('/districts'),
  getDistrictPlan: (name) => fetchJSON(`/districts/${name}/plan`),
  getPlatformMetrics: () => fetchJSON('/districts/metrics/summary'),

  // Student & Passport
  getStudents: () => fetchJSON('/students'),
  getMyPassport: () => fetchJSON('/student/me/passport'),
  getMyRoadmap: () => fetchJSON('/student/me/roadmap'),
  recalculateMyRoadmap: () => fetchJSON('/student/me/roadmap/recalculate', { method: 'POST' }),
  getStudentPassport: (id) => fetchJSON(`/student/${id}/passport`),
  getStudentRoadmap: (id) => fetchJSON(`/student/${id}/roadmap`),
  recalculateStudentRoadmap: (id) => fetchJSON(`/student/${id}/roadmap/recalculate`, { method: 'POST' }),
  getStudentAlertDomains: () => fetchJSON('/student/alert-domains'),

  getStudentProfile: () => fetchJSON('/student/profile'),
  createStudentProfile: (payload) => fetchJSON('/student/profile', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  updateStudentProfile: (payload) => fetchJSON('/student/profile', {
    method: 'PUT',
    body: JSON.stringify(payload),
  }),
  patchStudentProfile: (payload) => fetchJSON('/student/profile', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  }),
  updateStudentSkills: (skills) => fetchJSON('/student/profile/skills', {
    method: 'PUT',
    body: JSON.stringify({ skills }),
  }),
  addStudentSkill: (skill) => fetchJSON('/student/profile/skills', {
    method: 'POST',
    body: JSON.stringify(skill),
  }),
  deleteStudentSkill: (skillName) => fetchJSON(`/student/profile/skills/${encodeURIComponent(skillName)}`, {
    method: 'DELETE',
  }),
  updateStudentProjects: (projects) => fetchJSON('/student/profile/projects', {
    method: 'PUT',
    body: JSON.stringify({ projects }),
  }),
  updateStudentCertifications: (certifications) => fetchJSON('/student/profile/certifications', {
    method: 'PUT',
    body: JSON.stringify({ certifications }),
  }),
  updateStudentCourses: (courses) => fetchJSON('/student/profile/courses', {
    method: 'PUT',
    body: JSON.stringify({ courses }),
  }),

  getEmployeeProfile: () => fetchJSON('/employee/profile'),
  createEmployeeProfile: (payload) => fetchJSON('/employee/profile', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  updateEmployeeProfile: (payload) => fetchJSON('/employee/profile', {
    method: 'PUT',
    body: JSON.stringify(payload),
  }),
  patchEmployeeProfile: (payload) => fetchJSON('/employee/profile', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  }),
  updateEmployeeSkills: (skills) => fetchJSON('/employee/profile/skills', {
    method: 'PUT',
    body: JSON.stringify({ skills }),
  }),
  addEmployeeSkill: (skill) => fetchJSON('/employee/profile/skills', {
    method: 'POST',
    body: JSON.stringify(skill),
  }),
  deleteEmployeeSkill: (skillName) => fetchJSON(`/employee/profile/skills/${encodeURIComponent(skillName)}`, {
    method: 'DELETE',
  }),
  updateEmployeeCertifications: (certifications) => fetchJSON('/employee/profile/certifications', {
    method: 'PUT',
    body: JSON.stringify({ certifications }),
  }),

  getStudentIndustryAlerts: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJSON(`/student/industry-alerts${query ? `?${query}` : ''}`);
  },
  getSkillExplainability: (skill, studentId = null) => {
    const query = studentId ? `?student_id=${encodeURIComponent(studentId)}` : '';
    return fetchJSON(`/student/skill-explainability/${encodeURIComponent(skill)}${query}`);
  },

  // Student Data Collection & Assessment (Phase 12)
  getAssessmentQuizQuestions: () => fetchJSON('/student/assessment/quiz-questions'),
  submitStudentAssessment: (payload) => fetchJSON('/student/assessment', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  getStudentAssessments: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJSON(`/student/assessments${query ? `?${query}` : ''}`);
  },
  getStudentAssessment: (id) => fetchJSON(`/student/assessment/${encodeURIComponent(id)}`),

  // Admin Data Management (Phase 13)
  getAdminAssessments: (params = {}, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const query = new URLSearchParams(params).toString();
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON(`/admin/assessments${query ? `?${query}` : ''}`, { headers });
  },
  getAdminAssessment: (id, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON(`/admin/assessments/${encodeURIComponent(id)}`, { headers });
  },
  getAdminAssessmentStats: (adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON('/admin/assessments/stats/summary', { headers });
  },
  deleteAdminAssessment: (id, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON(`/admin/assessments/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      headers,
    });
  },
  getDataGovernance: (adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON('/admin/data-governance', { headers });
  },


  askCopilot: (question, role = 'student', district = null, studentId = null, contextData = null) => fetchJSON('/copilot/ask', {
    method: 'POST',
    body: JSON.stringify({ question, role, district, student_id: studentId, context_data: contextData }),
  }),
  explainCareerCopilot: (studentId, question = null, district = null) => fetchJSON('/copilot/explain-career', {
    method: 'POST',
    body: JSON.stringify({ student_id: studentId, question, district }),
  }),


  // Schemes & Student Welfare
  getSchemes: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJSON(`/schemes${query ? `?${query}` : ''}`);
  },
  getSchemeCategories: () => fetchJSON('/schemes/categories'),
  getScheme: (id) => fetchJSON(`/schemes/${id}`),

  // Opportunities (Apprenticeships, Internships, Vocational Training, Jobs)
  getOpportunities: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJSON(`/opportunities${query ? `?${query}` : ''}`);
  },
  getOpportunitiesSummary: () => fetchJSON('/opportunities/summary'),
  getOpportunity: (id) => fetchJSON(`/opportunities/${id}`),

  // Data Ingestion & Automated Sync
  getSyncStatus: () => fetchJSON('/sync/status'),
  getSyncLogs: (limit = 20, offset = 0) => fetchJSON(`/sync/logs?limit=${limit}&offset=${offset}`),
  triggerSync: (source = 'data.gov.in', adminKey = '') => fetchJSON(`/sync/trigger?source=${source}`, {
    method: 'POST',
    headers: adminKey ? { 'X-Admin-Key': adminKey } : {},
  }),

  // AI Diagnostic
  getHealthAI: () => fetchJSON('/health/ai'),

  // Employer Validation & Demand Hub (Phase 8, 14 & 25)
  getEmployerValidations: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJSON(`/employer/validate${query ? `?${query}` : ''}`);
  },
  submitEmployerFeedback: (feedbackId, status, notes = null, proficiency = null) => fetchJSON('/employer/feedback', {
    method: 'POST',
    body: JSON.stringify({
      feedback_id: feedbackId,
      status,
      notes,
      proficiency_required: proficiency,
    }),
  }),
  getEmployerDemands: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJSON(`/employer/demands${query ? `?${query}` : ''}`);
  },
  getMyEmployerDemands: () => fetchJSON('/employer/my-demands'),
  getEmployerDemand: (id) => fetchJSON(`/employer/demands/${encodeURIComponent(id)}`),
  submitEmployerDemand: (demandData) => fetchJSON('/employer/demands', {
    method: 'POST',
    body: JSON.stringify(demandData),
  }),
  updateEmployerDemand: (id, updates) => fetchJSON(`/employer/demands/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  }),
  deleteEmployerDemand: (id) => fetchJSON(`/employer/demands/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  }),
  getDifficultSkills: () => fetchJSON('/employer/difficult-skills'),
  getEmployerSummary: () => fetchJSON('/employer/summary'),
  verifyEmployerIdentity: (data) => fetchJSON('/employer/verify-identity', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Institute Data Pipeline & Course Management (Phase 25 & 34)
  getInstituteCourses: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJSON(`/institute/courses${query ? `?${query}` : ''}`);
  },
  getMyInstituteCourses: () => fetchJSON('/institute/my-courses'),
  extractInstituteSyllabus: (data) => fetchJSON('/institute/syllabus/extract', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  submitInstituteCourse: (courseData) => fetchJSON('/institute/courses', {
    method: 'POST',
    body: JSON.stringify(courseData),
  }),
  updateInstituteCourse: (id, updates) => fetchJSON(`/institute/courses/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  }),
  deleteInstituteCourse: (id) => fetchJSON(`/institute/courses/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  }),
  getAdminCourses: (params = {}, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const query = new URLSearchParams(params).toString();
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON(`/admin/institute/courses${query ? `?${query}` : ''}`, { headers });
  },
  updateAdminCourse: (id, updates, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON(`/admin/institute/courses/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify(updates),
    });
  },
  deleteAdminCourse: (id, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON(`/admin/institute/courses/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      headers,
    });
  },

  // Admin Employer Demand Management & Validation (Phase 14)
  getAdminEmployerDemands: (params = {}, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const query = new URLSearchParams(params).toString();
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON(`/admin/employer/demands${query ? `?${query}` : ''}`, { headers });
  },
  updateAdminEmployerDemandStatus: (id, status, notes = '', adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON(`/admin/employer/demands/${encodeURIComponent(id)}/status`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ status, admin_notes: notes }),
    });
  },
  deleteAdminEmployerDemand: (id, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON(`/admin/employer/demands/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      headers,
    });
  },

  // Policy What-If Simulator
  runSimulation: (scenario) => fetchJSON('/simulator/whatif', {
    method: 'POST',
    body: JSON.stringify(scenario),
  }),
  getSimulatorCategories: () => fetchJSON('/simulator/categories'),

  // Government Opportunities (Phase 15)
  getGovOpportunities: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJSON(`/gov/opportunities${query ? `?${query}` : ''}`);
  },
  getGovOpportunityTypes: () => fetchJSON('/gov/opportunities/types'),
  getGovOpportunity: (id) => fetchJSON(`/gov/opportunities/${encodeURIComponent(id)}`),
  getRecommendedSchemes: (studentId) => fetchJSON(`/schemes/recommended/${encodeURIComponent(studentId)}`),
  getRecommendedGovOpportunities: (studentId) => fetchJSON(`/gov/opportunities/recommended/${encodeURIComponent(studentId)}`),
  submitGovOpportunity: (data) => fetchJSON('/gov/opportunities', { method: 'POST', body: JSON.stringify(data) }),

  // Admin Government Opportunities (Phase 15)
  getAdminGovOpportunities: (params = {}, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const query = new URLSearchParams(params).toString();
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON(`/admin/gov/opportunities${query ? `?${query}` : ''}`, { headers });
  },
  createAdminGovOpportunity: (data, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON('/admin/gov/opportunities', {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
    });
  },
  updateAdminGovOpportunity: (id, data, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON(`/admin/gov/opportunities/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify(data),
    });
  },
  deleteAdminGovOpportunity: (id, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON(`/admin/gov/opportunities/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      headers,
    });
  },

  // Career Recommendations & Skill-Gap Engine (Phase 16)
  getStudentCareerRecommendations: (studentId) => {
    return fetchJSON(`/student/recommendations/${encodeURIComponent(studentId)}`);
  },
  explainStudentRecommendationsAi: (studentId, prompt = null) => {
    return fetchJSON(`/student/recommendations/${encodeURIComponent(studentId)}/explain-ai`, {
      method: 'POST',
      body: JSON.stringify({ prompt }),
    });
  },

  // Phase 26: Industry Intelligence & Automated Ingestion
  getIndustrySignals: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJSON(`/industry/signals${query ? `?${query}` : ''}`);
  },
  getIndustrySignalById: (id) => {
    return fetchJSON(`/industry/signals/${encodeURIComponent(id)}`);
  },
  triggerAdminIndustryIngest: (payload = null, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON('/admin/industry/ingest', {
      method: 'POST',
      headers,
      body: payload ? JSON.stringify(payload) : undefined,
    });
  },
  getAdminIndustryIngestionStatus: (adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON('/admin/industry/ingestion-status', { headers });
  },
  getAdminIndustrySignals: (params = {}, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const query = new URLSearchParams(params).toString();
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON(`/admin/industry/signals${query ? `?${query}` : ''}`, { headers });
  },
  updateAdminIndustrySignal: (id, data, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON(`/admin/industry/signals/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify(data),
    });
  },
  deleteAdminIndustrySignal: (id, adminKey = '') => {
    const key = adminKey || (typeof window !== 'undefined' ? window.localStorage?.getItem('skillsetu_admin_key') : '');
    const headers = key ? { 'X-Admin-Key': key } : {};
    return fetchJSON(`/admin/industry/signals/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      headers,
    });
  },
  // Phase 27: Multi-Horizon Forecasting & Curriculum Modernization
  getMultiHorizonForecasts: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJSON(`/forecast${query ? `?${query}` : ''}`);
  },
  getFutureSkillsRadar: () => {
    return fetchJSON('/forecast/radar');
  },
  getSkillForecastTrajectory: (skillId) => {
    return fetchJSON(`/forecast/skill/${encodeURIComponent(skillId)}`);
  },
  getCurriculumAudit: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJSON(`/curriculum/audit${query ? `?${query}` : ''}`);
  },
  getCurriculumSummary: () => {
    return fetchJSON('/curriculum/summary');
  },
  getCourseModernizationBlueprint: (courseId) => {
    return fetchJSON(`/curriculum/recommendations/${encodeURIComponent(courseId)}`);
  },
};


