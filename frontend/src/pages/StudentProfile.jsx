import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { formatStudentProfilePayload, validateStudentProfile } from '../utils/profileValidator';

const PROFICIENCY_LEVELS = [
  { id: 'beginner', label: 'Beginner', badge: 'bg-sky-50 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-800' },
  { id: 'intermediate', label: 'Intermediate', badge: 'bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-800' },
  { id: 'advanced', label: 'Advanced', badge: 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800' },
  { id: 'expert', label: 'Expert', badge: 'bg-purple-50 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800' },
];

const EDUCATION_LEVELS = [
  'Vocational / ITI',
  'Polytechnic Diploma',
  'Undergraduate (B.Tech / B.E / B.Sc)',
  'Postgraduate (M.Tech / M.Sc / MCA)',
  'Doctorate / Research',
  'Other',
];

const ACADEMIC_YEARS = [
  '1st Year',
  '2nd Year',
  '3rd Year',
  'Final Year',
  'Graduated / Alumni',
];

export default function StudentProfile() {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState(null);
  const [isLoadError, setIsLoadError] = useState(false);
  const [successMsg, setSuccessMsg] = useState(null);
  const [isNewProfile, setIsNewProfile] = useState(false);

  const [form, setForm] = useState({
    full_name: '',
    institution: '',
    degree: '',
    education_level: 'Undergraduate (B.Tech / B.E / B.Sc)',
    academic_year: 'Final Year',
    graduation_year: new Date().getFullYear(),
    desired_role: '',
    preferred_location: '',
    career_interests: [],
    skills: [],
    projects: [],
    certifications: [],
    courses: [],
    experience: [],
  });

  const [newSkill, setNewSkill] = useState({ name: '', proficiency: 'intermediate' });
  const [newInterest, setNewInterest] = useState('');
  const [newProject, setNewProject] = useState({ name: '', description: '', skills: '', url: '' });
  const [newCert, setNewCert] = useState({ name: '', issuer: '', issue_date: '', url: '' });
  const [newCourse, setNewCourse] = useState({ course_name: '', provider: '', status: 'completed' });
  const [newExp, setNewExp] = useState({ company: '', role: '', duration: '', description: '' });

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setApiError(null);
    setIsLoadError(false);
    try {
      const res = await api.getStudentProfile();
      if (res && res.profile) {
        setProfile(res.profile);
        setIsNewProfile(false);
        setForm({
          full_name: res.profile.full_name || (user?.full_name || user?.name || ''),
          institution: res.profile.institution || '',
          degree: res.profile.degree || '',
          education_level: res.profile.education_level || 'Undergraduate (B.Tech / B.E / B.Sc)',
          academic_year: res.profile.academic_year || 'Final Year',
          graduation_year: res.profile.graduation_year || new Date().getFullYear(),
          desired_role: res.profile.desired_role || res.profile.target_role || '',
          preferred_location: res.profile.preferred_location || '',
          career_interests: res.profile.career_interests || [],
          skills: res.profile.skills || [],
          projects: res.profile.projects || [],
          certifications: res.profile.certifications || [],
          courses: res.profile.courses || [],
          experience: res.profile.experience || [],
        });
      }
    } catch (err) {
      if (err.message && err.message.includes('404')) {
        setIsNewProfile(true);
        setProfile(null);
      } else {
        setIsLoadError(true);
        setApiError(err.message || 'Failed loading profile from server.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleFieldChange = (field, val) => {
    setForm((prev) => ({ ...prev, [field]: val }));
    setSuccessMsg(null);
  };

  const handleAddSkill = (e) => {
    e.preventDefault();
    const clean = newSkill.name.trim();
    if (!clean) return;
    const exists = form.skills.some((s) => (s.skill_name || s.name || '').toLowerCase() === clean.toLowerCase());
    if (exists) {
      setForm((prev) => ({
        ...prev,
        skills: prev.skills.map((s) =>
          (s.skill_name || s.name || '').toLowerCase() === clean.toLowerCase()
            ? { ...s, proficiency: newSkill.proficiency }
            : s
        ),
      }));
    } else {
      setForm((prev) => ({
        ...prev,
        skills: [...prev.skills, { skill_name: clean, proficiency: newSkill.proficiency }],
      }));
    }
    setNewSkill({ name: '', proficiency: 'intermediate' });
  };

  const handleRemoveSkill = (skillName) => {
    setForm((prev) => ({
      ...prev,
      skills: prev.skills.filter((s) => (s.skill_name || s.name) !== skillName),
    }));
  };

  const handleAddInterest = (e) => {
    e.preventDefault();
    const clean = newInterest.trim();
    if (!clean) return;
    if (!form.career_interests.includes(clean)) {
      setForm((prev) => ({
        ...prev,
        career_interests: [...prev.career_interests, clean],
      }));
    }
    setNewInterest('');
  };

  const handleRemoveInterest = (interest) => {
    setForm((prev) => ({
      ...prev,
      career_interests: prev.career_interests.filter((i) => i !== interest),
    }));
  };

  const handleAddProject = (e) => {
    e.preventDefault();
    if (!newProject.name.trim()) return;
    const skillsList = newProject.skills
      ? newProject.skills.split(',').map((s) => s.trim()).filter(Boolean)
      : [];
    setForm((prev) => ({
      ...prev,
      projects: [
        ...prev.projects,
        {
          name: newProject.name.trim(),
          description: newProject.description.trim(),
          skills: skillsList,
          url: newProject.url.trim() || null,
        },
      ],
    }));
    setNewProject({ name: '', description: '', skills: '', url: '' });
  };

  const handleRemoveProject = (index) => {
    setForm((prev) => ({
      ...prev,
      projects: prev.projects.filter((_, i) => i !== index),
    }));
  };

  const handleAddCert = (e) => {
    e.preventDefault();
    if (!newCert.name.trim()) return;
    setForm((prev) => ({
      ...prev,
      certifications: [
        ...prev.certifications,
        {
          name: newCert.name.trim(),
          issuer: newCert.issuer.trim() || 'Self-Certified / Industry',
          issue_date: newCert.issue_date || null,
          url: newCert.url.trim() || null,
        },
      ],
    }));
    setNewCert({ name: '', issuer: '', issue_date: '', url: '' });
  };

  const handleRemoveCert = (index) => {
    setForm((prev) => ({
      ...prev,
      certifications: prev.certifications.filter((_, i) => i !== index),
    }));
  };

  const handleAddCourse = (e) => {
    e.preventDefault();
    if (!newCourse.course_name.trim()) return;
    setForm((prev) => ({
      ...prev,
      courses: [
        ...prev.courses,
        {
          course_name: newCourse.course_name.trim(),
          provider: newCourse.provider.trim() || null,
          status: newCourse.status || 'completed',
        },
      ],
    }));
    setNewCourse({ course_name: '', provider: '', status: 'completed' });
  };

  const handleRemoveCourse = (index) => {
    setForm((prev) => ({
      ...prev,
      courses: prev.courses.filter((_, i) => i !== index),
    }));
  };

  const handleAddExp = (e) => {
    e.preventDefault();
    if (!newExp.company.trim() || !newExp.role.trim()) return;
    setForm((prev) => ({
      ...prev,
      experience: [
        ...prev.experience,
        {
          company: newExp.company.trim(),
          role: newExp.role.trim(),
          duration: newExp.duration.trim() || null,
          description: newExp.description.trim() || '',
        },
      ],
    }));
    setNewExp({ company: '', role: '', duration: '', description: '' });
  };

  const handleRemoveExp = (index) => {
    setForm((prev) => ({
      ...prev,
      experience: prev.experience.filter((_, i) => i !== index),
    }));
  };

  const handleSubmit = async (e) => {
    if (e && typeof e.preventDefault === 'function') {
      e.preventDefault();
    }
    setApiError(null);
    setIsLoadError(false);
    setSuccessMsg(null);

    const payload = formatStudentProfilePayload(form);
    const validation = validateStudentProfile(payload);
    if (!validation.isValid) {
      setIsLoadError(false);
      setApiError(validation.errors.join(', '));
      return;
    }

    setSaving(true);
    try {
      let saved;
      if (isNewProfile) {
        saved = await api.createStudentProfile(payload);
        setIsNewProfile(false);
      } else {
        saved = await api.updateStudentProfile(payload);
      }

      if (!saved || !saved.profile) {
        throw new Error('Server did not return authoritative saved profile.');
      }

      const authoritativeProfile = saved.profile;
      setProfile(authoritativeProfile);
      setForm({
        full_name: authoritativeProfile.full_name || (user?.full_name || user?.name || ''),
        institution: authoritativeProfile.institution || '',
        degree: authoritativeProfile.degree || '',
        education_level: authoritativeProfile.education_level || 'Undergraduate (B.Tech / B.E / B.Sc)',
        academic_year: authoritativeProfile.academic_year || 'Final Year',
        graduation_year: authoritativeProfile.graduation_year || new Date().getFullYear(),
        desired_role: authoritativeProfile.desired_role || authoritativeProfile.target_role || '',
        target_role: authoritativeProfile.target_role || authoritativeProfile.desired_role || '',
        preferred_location: authoritativeProfile.preferred_location || '',
        career_interests: authoritativeProfile.career_interests || [],
        skills: authoritativeProfile.skills || [],
        projects: authoritativeProfile.projects || [],
        certifications: authoritativeProfile.certifications || [],
        courses: authoritativeProfile.courses || [],
        experience: authoritativeProfile.experience || [],
      });
      setSuccessMsg('Skill Passport saved successfully! Authoritative record updated in Supabase.');
    } catch (err) {
      setIsLoadError(false);
      if (err.isTimeout) {
        setApiError('Request timed out after 25 seconds. Please check your network connection and retry.');
      } else if (err.status === 401 || err.status === 403) {
        setApiError(err.message || 'Authorization failed. Please log in again.');
      } else if (err.status >= 500) {
        setApiError(err.message || 'Database persistence failed. Please try again.');
      } else if (typeof navigator !== 'undefined' && !navigator.onLine) {
        setApiError('Network connection unavailable. Please check your internet connection.');
      } else {
        setApiError(err.message || 'Failed saving profile. Please check inputs.');
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="mb-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-2xl">🎓</span>
              <h1 className="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
                Student Profile & Skill Passport
              </h1>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Authoritative verified record of education, skills, projects, and target role.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to="/student"
              className="px-4 py-2 text-xs font-bold rounded-xl border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
            >
              Back to Dashboard
            </Link>
            <button
              onClick={handleSubmit}
              disabled={saving}
              className="px-5 py-2 text-xs font-bold rounded-xl bg-teal-600 hover:bg-teal-700 text-white shadow-sm disabled:opacity-50 transition-colors cursor-pointer flex items-center gap-2"
            >
              {saving && <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />}
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>

        {apiError && (
          <div className="mb-6 p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-rose-800 dark:text-rose-300 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span>⚠️</span>
              <span>{apiError}</span>
            </div>
            {isLoadError ? (
              <button
                type="button"
                onClick={loadProfile}
                className="px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-[11px] font-bold cursor-pointer"
              >
                Retry Load
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={saving}
                className="px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-[11px] font-bold cursor-pointer disabled:opacity-50"
              >
                {saving ? 'Retrying...' : 'Retry Save'}
              </button>
            )}
          </div>
        )}

        {successMsg && (
          <div className="mb-6 p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/60 text-emerald-800 dark:text-emerald-300 text-xs flex items-center gap-2">
            <span>✅</span>
            <span>{successMsg}</span>
          </div>
        )}

        {loading ? (
          <div className="space-y-6 animate-pulse">
            <div className="h-32 bg-slate-100 dark:bg-slate-800 rounded-2xl" />
            <div className="h-64 bg-slate-100 dark:bg-slate-800 rounded-2xl" />
            <div className="h-48 bg-slate-100 dark:bg-slate-800 rounded-2xl" />
          </div>
        ) : isNewProfile && !profile ? (
          <div className="mb-8 p-8 text-center rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
            <div className="w-16 h-16 rounded-2xl bg-teal-50 dark:bg-teal-950/60 border border-teal-200 dark:border-teal-800 text-teal-600 dark:text-teal-400 flex items-center justify-center text-3xl mx-auto mb-4">
              🛂
            </div>
            <h2 className="text-lg font-black text-slate-900 dark:text-white mb-1">
              Initialize Your Skill Passport
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto mb-6">
              No authenticated profile was found for your account. Complete your educational details and skills below to generate your official SkillSetuAI passport.
            </p>
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
            <h2 className="text-sm font-black text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <span>👤</span> Personal & Account Details
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  value={form.full_name}
                  onChange={(e) => handleFieldChange('full_name', e.target.value)}
                  placeholder="e.g. Aditi Sharma"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Verified Email
                </label>
                <input
                  type="text"
                  disabled
                  value={user?.email || ''}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-900/60 text-slate-500 dark:text-slate-400 cursor-not-allowed"
                />
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
            <h2 className="text-sm font-black text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <span>🏛️</span> Academic & Education Information
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Institution / College Name
                </label>
                <input
                  type="text"
                  value={form.institution}
                  onChange={(e) => handleFieldChange('institution', e.target.value)}
                  placeholder="e.g. Government Polytechnic Pune"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Degree / Program
                </label>
                <input
                  type="text"
                  value={form.degree}
                  onChange={(e) => handleFieldChange('degree', e.target.value)}
                  placeholder="e.g. Diploma in Computer Engineering"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Education Level
                </label>
                <select
                  value={form.education_level}
                  onChange={(e) => handleFieldChange('education_level', e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
                >
                  {EDUCATION_LEVELS.map((lvl) => (
                    <option key={lvl} value={lvl}>{lvl}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Year of Study
                  </label>
                  <select
                    value={form.academic_year}
                    onChange={(e) => handleFieldChange('academic_year', e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
                  >
                    {ACADEMIC_YEARS.map((yr) => (
                      <option key={yr} value={yr}>{yr}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Graduation Year
                  </label>
                  <input
                    type="number"
                    value={form.graduation_year}
                    onChange={(e) => handleFieldChange('graduation_year', e.target.value)}
                    min="1980"
                    max="2035"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
            <h2 className="text-sm font-black text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <span>🎯</span> Career Target & Interests
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Desired Target Role
                </label>
                <input
                  type="text"
                  value={form.desired_role}
                  onChange={(e) => handleFieldChange('desired_role', e.target.value)}
                  placeholder="e.g. AI Engineer, EV Specialist, Data Analyst"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Preferred Work Location
                </label>
                <input
                  type="text"
                  value={form.preferred_location}
                  onChange={(e) => handleFieldChange('preferred_location', e.target.value)}
                  placeholder="e.g. Pune, Mumbai, Nagpur, Remote"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                Career Interests & Industry Verticals
              </label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={newInterest}
                  onChange={(e) => setNewInterest(e.target.value)}
                  placeholder="e.g. Machine Learning, Electric Vehicles, Cloud Infrastructure"
                  className="flex-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
                />
                <button
                  type="button"
                  onClick={handleAddInterest}
                  className="px-4 py-2 text-xs font-bold rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700"
                >
                  Add
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {form.career_interests.map((ci) => (
                  <span
                    key={ci}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
                  >
                    {ci}
                    <button
                      type="button"
                      onClick={() => handleRemoveInterest(ci)}
                      className="text-slate-400 hover:text-rose-500 text-xs font-bold cursor-pointer"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
            <h2 className="text-sm font-black text-slate-900 dark:text-white mb-2 flex items-center gap-2">
              <span>⚡</span> Skills & Proficiency Levels
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
              Add technical and operational competencies. Bounded proficiency levels ensure reliable matching.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-4">
              <input
                type="text"
                value={newSkill.name}
                onChange={(e) => setNewSkill((prev) => ({ ...prev, name: e.target.value }))}
                placeholder="Skill name (e.g. Python, PLC Programming)"
                className="px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
              />
              <select
                value={newSkill.proficiency}
                onChange={(e) => setNewSkill((prev) => ({ ...prev, proficiency: e.target.value }))}
                className="px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
              >
                {PROFICIENCY_LEVELS.map((lvl) => (
                  <option key={lvl.id} value={lvl.id}>{lvl.label}</option>
                ))}
              </select>
              <button
                type="button"
                onClick={handleAddSkill}
                className="px-4 py-2 text-xs font-bold rounded-xl bg-teal-600 hover:bg-teal-700 text-white cursor-pointer"
              >
                Add Skill
              </button>
            </div>
            {form.skills.length === 0 ? (
              <p className="text-xs text-slate-400 dark:text-slate-500 italic">No skills added yet.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                {form.skills.map((sk) => {
                  const sName = sk.skill_name || sk.name;
                  const lvlConfig = PROFICIENCY_LEVELS.find((l) => l.id === (sk.proficiency || '').toLowerCase()) || PROFICIENCY_LEVELS[0];
                  return (
                    <div
                      key={sName}
                      className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 flex items-center justify-between"
                    >
                      <div>
                        <p className="text-xs font-bold text-slate-800 dark:text-slate-200">{sName}</p>
                        <span className={`inline-block mt-1 px-2 py-0.5 rounded text-[10px] font-extrabold border ${lvlConfig.badge}`}>
                          {lvlConfig.label}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoveSkill(sName)}
                        className="text-slate-400 hover:text-rose-500 text-sm font-bold cursor-pointer p-1"
                      >
                        ×
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
            <h2 className="text-sm font-black text-slate-900 dark:text-white mb-2 flex items-center gap-2">
              <span>🚀</span> Projects
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
              Hands-on capstone and laboratory projects demonstrating applied skills.
            </p>
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 mb-4 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <input
                  type="text"
                  value={newProject.name}
                  onChange={(e) => setNewProject((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="Project Name *"
                  className="px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
                />
                <input
                  type="url"
                  value={newProject.url}
                  onChange={(e) => setNewProject((prev) => ({ ...prev, url: e.target.value }))}
                  placeholder="Project / Repo URL"
                  className="px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
                />
              </div>
              <textarea
                value={newProject.description}
                onChange={(e) => setNewProject((prev) => ({ ...prev, description: e.target.value }))}
                placeholder="Brief description of outcomes and methodology..."
                rows={2}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
              />
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newProject.skills}
                  onChange={(e) => setNewProject((prev) => ({ ...prev, skills: e.target.value }))}
                  placeholder="Technologies used (comma separated, e.g. Python, Docker)"
                  className="flex-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
                />
                <button
                  type="button"
                  onClick={handleAddProject}
                  className="px-4 py-2 text-xs font-bold rounded-xl bg-slate-800 hover:bg-slate-900 dark:bg-slate-700 text-white cursor-pointer"
                >
                  Add Project
                </button>
              </div>
            </div>
            {form.projects.length > 0 && (
              <div className="space-y-2">
                {form.projects.map((p, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 flex items-start justify-between"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-xs font-bold text-slate-800 dark:text-slate-200">{p.name}</p>
                        {p.url && (
                          <a
                            href={p.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[11px] text-teal-600 dark:text-teal-400 underline"
                          >
                            Link
                          </a>
                        )}
                      </div>
                      {p.description && <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">{p.description}</p>}
                      {p.skills && p.skills.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {p.skills.map((s, si) => (
                            <span key={si} className="px-1.5 py-0.5 rounded text-[10px] bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveProject(idx)}
                      className="text-slate-400 hover:text-rose-500 text-sm font-bold cursor-pointer"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
              <h2 className="text-sm font-black text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                <span>📜</span> Certifications
              </h2>
              <div className="space-y-2 mb-3">
                <input
                  type="text"
                  value={newCert.name}
                  onChange={(e) => setNewCert((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="Certification Name *"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white"
                />
                <input
                  type="text"
                  value={newCert.issuer}
                  onChange={(e) => setNewCert((prev) => ({ ...prev, issuer: e.target.value }))}
                  placeholder="Issuing Organization *"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white"
                />
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="date"
                    value={newCert.issue_date}
                    onChange={(e) => setNewCert((prev) => ({ ...prev, issue_date: e.target.value }))}
                    className="px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white"
                  />
                  <button
                    type="button"
                    onClick={handleAddCert}
                    className="px-3 py-2 text-xs font-bold rounded-xl bg-slate-800 hover:bg-slate-900 dark:bg-slate-700 text-white cursor-pointer"
                  >
                    Add Cert
                  </button>
                </div>
              </div>
              {form.certifications.length > 0 && (
                <div className="space-y-2">
                  {form.certifications.map((c, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 flex items-center justify-between"
                    >
                      <div>
                        <p className="text-xs font-bold text-slate-800 dark:text-slate-200">{c.name}</p>
                        <p className="text-[10px] text-slate-500 dark:text-slate-400">{c.issuer} {c.issue_date && `• ${c.issue_date}`}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoveCert(idx)}
                        className="text-slate-400 hover:text-rose-500 text-sm font-bold cursor-pointer"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
              <h2 className="text-sm font-black text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                <span>📚</span> Completed / Current Courses
              </h2>
              <div className="space-y-2 mb-3">
                <input
                  type="text"
                  value={newCourse.course_name}
                  onChange={(e) => setNewCourse((prev) => ({ ...prev, course_name: e.target.value }))}
                  placeholder="Course Name *"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white"
                />
                <input
                  type="text"
                  value={newCourse.provider}
                  onChange={(e) => setNewCourse((prev) => ({ ...prev, provider: e.target.value }))}
                  placeholder="Provider / Platform (e.g. NPTEL, Coursera)"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white"
                />
                <div className="grid grid-cols-2 gap-2">
                  <select
                    value={newCourse.status}
                    onChange={(e) => setNewCourse((prev) => ({ ...prev, status: e.target.value }))}
                    className="px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white"
                  >
                    <option value="completed">Completed</option>
                    <option value="in_progress">In Progress</option>
                  </select>
                  <button
                    type="button"
                    onClick={handleAddCourse}
                    className="px-3 py-2 text-xs font-bold rounded-xl bg-slate-800 hover:bg-slate-900 dark:bg-slate-700 text-white cursor-pointer"
                  >
                    Add Course
                  </button>
                </div>
              </div>
              {form.courses.length > 0 && (
                <div className="space-y-2">
                  {form.courses.map((co, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 flex items-center justify-between"
                    >
                      <div>
                        <p className="text-xs font-bold text-slate-800 dark:text-slate-200">{co.course_name}</p>
                        <p className="text-[10px] text-slate-500 dark:text-slate-400">
                          {co.provider || 'Self-paced'} • <span className="capitalize">{co.status}</span>
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoveCourse(idx)}
                        className="text-slate-400 hover:text-rose-500 text-sm font-bold cursor-pointer"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
            <h2 className="text-sm font-black text-slate-900 dark:text-white mb-2 flex items-center gap-2">
              <span>💼</span> Work Experience & Internships
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
              Industry internships, apprenticeships, or relevant employment experience.
            </p>
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 mb-4 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <input
                  type="text"
                  value={newExp.company}
                  onChange={(e) => setNewExp((prev) => ({ ...prev, company: e.target.value }))}
                  placeholder="Company / Organization *"
                  className="px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
                />
                <input
                  type="text"
                  value={newExp.role}
                  onChange={(e) => setNewExp((prev) => ({ ...prev, role: e.target.value }))}
                  placeholder="Role / Title *"
                  className="px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
                />
                <input
                  type="text"
                  value={newExp.duration}
                  onChange={(e) => setNewExp((prev) => ({ ...prev, duration: e.target.value }))}
                  placeholder="Duration (e.g. Jun 2025 - Aug 2025)"
                  className="px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
                />
              </div>
              <textarea
                value={newExp.description}
                onChange={(e) => setNewExp((prev) => ({ ...prev, description: e.target.value }))}
                placeholder="Key responsibilities and achievements..."
                rows={2}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
              />
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={handleAddExp}
                  className="px-4 py-2 text-xs font-bold rounded-xl bg-slate-800 hover:bg-slate-900 dark:bg-slate-700 text-white cursor-pointer"
                >
                  Add Experience
                </button>
              </div>
            </div>
            {form.experience.length > 0 && (
              <div className="space-y-2">
                {form.experience.map((exp, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 flex items-start justify-between"
                  >
                    <div>
                      <p className="text-xs font-bold text-slate-800 dark:text-slate-200">{exp.role} at {exp.company}</p>
                      {exp.duration && <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">{exp.duration}</p>}
                      {exp.description && <p className="text-[11px] text-slate-600 dark:text-slate-300 mt-1">{exp.description}</p>}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveExp(idx)}
                      className="text-slate-400 hover:text-rose-500 text-sm font-bold cursor-pointer"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-200 dark:border-slate-800">
            <Link
              to="/student"
              className="px-5 py-2.5 text-xs font-bold rounded-xl border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2.5 text-xs font-bold rounded-xl bg-teal-600 hover:bg-teal-700 text-white shadow-md disabled:opacity-50 transition-colors cursor-pointer flex items-center gap-2"
            >
              {saving && <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />}
              {saving ? 'Persisting Profile...' : 'Save Skill Passport'}
            </button>
          </div>
        </form>
      </div>
    </Layout>
  );
}
