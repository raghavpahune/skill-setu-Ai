import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { formatEmployeeProfilePayload, validateEmployeeProfile } from '../utils/profileValidator';

const PROFICIENCY_LEVELS = [
  { id: 'beginner', label: 'Beginner', badge: 'bg-sky-50 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-800' },
  { id: 'intermediate', label: 'Intermediate', badge: 'bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-800' },
  { id: 'advanced', label: 'Advanced', badge: 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800' },
  { id: 'expert', label: 'Expert', badge: 'bg-purple-50 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800' },
];

const INDUSTRIES = [
  'IT / Software Services',
  'Electric Vehicles & Automotive',
  'Manufacturing & Heavy Engineering',
  'Healthcare & Pharmaceuticals',
  'Green Energy & Solar Power',
  'Logistics & Supply Chain',
  'Financial Services & Banking',
  'Telecommunications',
  'Other',
];

export default function EmployeeProfile() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [passport, setPassport] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState(null);
  const [isLoadError, setIsLoadError] = useState(false);
  const [successMsg, setSuccessMsg] = useState(null);
  const [isNewProfile, setIsNewProfile] = useState(false);

  const [form, setForm] = useState({
    current_role: '',
    years_of_experience: 0,
    industry: 'IT / Software Services',
    education: '',
    target_role: '',
    preferred_location: '',
    skills: [],
    certifications: [],
  });

  const [newSkill, setNewSkill] = useState({ name: '', proficiency: 'advanced' });
  const [newCert, setNewCert] = useState({ name: '', issuer: '', issue_date: '', url: '' });

  const loadIntelligence = useCallback(async () => {
    try {
      const [passRes, alertRes] = await Promise.allSettled([
        api.getMySkillPassport(),
        api.getStudentIndustryAlerts({ student_id: user?.id }),
      ]);
      if (passRes.status === 'fulfilled' && passRes.value) {
        setPassport(passRes.value);
      }
      if (alertRes.status === 'fulfilled' && alertRes.value?.alerts) {
        setAlerts(alertRes.value.alerts.slice(0, 3));
      }
    } catch {
    }
  }, [user?.id]);

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setApiError(null);
    setIsLoadError(false);
    try {
      const res = await api.getEmployeeProfile();
      if (res && res.profile) {
        setProfile(res.profile);
        setIsNewProfile(false);
        setForm({
          current_role: res.profile.current_role || '',
          years_of_experience: res.profile.years_of_experience || 0,
          industry: res.profile.industry || 'IT / Software Services',
          education: res.profile.education || '',
          target_role: res.profile.target_role || '',
          preferred_location: res.profile.preferred_location || '',
          skills: res.profile.skills || [],
          certifications: res.profile.certifications || [],
        });
        loadIntelligence();
      }
    } catch (err) {
      if (err.message && err.message.includes('404')) {
        setIsNewProfile(true);
        setProfile(null);
      } else {
        setIsLoadError(true);
        setApiError(err.message || 'Failed loading employee profile.');
      }
    } finally {
      setLoading(false);
    }
  }, [loadIntelligence]);

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
    setNewSkill({ name: '', proficiency: 'advanced' });
  };

  const handleRemoveSkill = (skillName) => {
    setForm((prev) => ({
      ...prev,
      skills: prev.skills.filter((s) => (s.skill_name || s.name) !== skillName),
    }));
  };

  const handleAddCert = (e) => {
    e.preventDefault();
    if (!newCert.name.trim() || !newCert.issuer.trim()) return;
    setForm((prev) => ({
      ...prev,
      certifications: [
        ...prev.certifications,
        {
          name: newCert.name.trim(),
          issuer: newCert.issuer.trim(),
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setApiError(null);
    setIsLoadError(false);
    setSuccessMsg(null);

    const payload = formatEmployeeProfilePayload(form);
    const validation = validateEmployeeProfile(payload);
    if (!validation.isValid) {
      setIsLoadError(false);
      setApiError(validation.errors.join(', '));
      return;
    }

    setSaving(true);
    try {
      let saved;
      if (isNewProfile) {
        saved = await api.createEmployeeProfile(payload);
        setIsNewProfile(false);
      } else {
        saved = await api.updateEmployeeProfile(payload);
      }
      if (saved && saved.profile) {
        setProfile(saved.profile);
        loadIntelligence();
      }
      setSuccessMsg('Employee Profile & Skill Passport successfully updated.');
    } catch (err) {
      setIsLoadError(false);
      setApiError(err.message || 'Failed saving employee profile.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="mb-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-2xl">💼</span>
              <h1 className="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
                Employee Profile & Skill Passport
              </h1>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Track professional experience, technical credentials, and target career advancement roles.
            </p>
          </div>
          <button
            onClick={handleSubmit}
            disabled={saving}
            className="px-5 py-2 text-xs font-bold rounded-xl bg-teal-600 hover:bg-teal-700 text-white shadow-sm disabled:opacity-50 transition-colors cursor-pointer flex items-center gap-2 self-start md:self-auto"
          >
            {saving && <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />}
            {saving ? 'Saving...' : 'Save Profile'}
          </button>
        </div>

        {apiError && (
          <div className="mb-6 p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-rose-800 dark:text-rose-300 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span>⚠️</span>
              <span>{apiError}</span>
            </div>
            {isLoadError && (
              <button
                type="button"
                onClick={loadProfile}
                className="px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-[11px] font-bold"
              >
                Retry
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
          </div>
        ) : isNewProfile && !profile ? (
          <div className="mb-8 p-8 text-center rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
            <div className="w-16 h-16 rounded-2xl bg-teal-50 dark:bg-teal-950/60 border border-teal-200 dark:border-teal-800 text-teal-600 dark:text-teal-400 flex items-center justify-center text-3xl mx-auto mb-4">
              💼
            </div>
            <h2 className="text-lg font-black text-slate-900 dark:text-white mb-1">
              Initialize Your Professional Profile
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto mb-6">
              Create your verified employee skill passport to map current competencies against market demand and transition targets.
            </p>
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
            <h2 className="text-sm font-black text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <span>🏢</span> Current Professional Standing
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Current Role / Designation *
                </label>
                <input
                  type="text"
                  value={form.current_role}
                  onChange={(e) => handleFieldChange('current_role', e.target.value)}
                  placeholder="e.g. Senior Software Engineer, EV Technician"
                  required
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Years of Experience
                </label>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  max="50"
                  value={form.years_of_experience}
                  onChange={(e) => handleFieldChange('years_of_experience', e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Industry Sector
                </label>
                <select
                  value={form.industry}
                  onChange={(e) => handleFieldChange('industry', e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
                >
                  {INDUSTRIES.map((ind) => (
                    <option key={ind} value={ind}>{ind}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Highest Qualification / Education
                </label>
                <input
                  type="text"
                  value={form.education}
                  onChange={(e) => handleFieldChange('education', e.target.value)}
                  placeholder="e.g. B.E Mechanical, BCA, Diploma"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
                />
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
            <h2 className="text-sm font-black text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <span>🎯</span> Career Target & Location
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Target Next Role / Transition Goal
                </label>
                <input
                  type="text"
                  value={form.target_role}
                  onChange={(e) => handleFieldChange('target_role', e.target.value)}
                  placeholder="e.g. Lead Solutions Architect, Plant Supervisor"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Preferred Location
                </label>
                <input
                  type="text"
                  value={form.preferred_location}
                  onChange={(e) => handleFieldChange('preferred_location', e.target.value)}
                  placeholder="e.g. Pune, Chhatrapati Sambhajinagar, Remote"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-hidden focus:border-teal-500"
                />
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
            <h2 className="text-sm font-black text-slate-900 dark:text-white mb-2 flex items-center gap-2">
              <span>⚡</span> Skills & Proficiency
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
              Record domain competencies with standardized proficiency ratings.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-4">
              <input
                type="text"
                value={newSkill.name}
                onChange={(e) => setNewSkill((prev) => ({ ...prev, name: e.target.value }))}
                placeholder="Skill name (e.g. PostgreSQL, CAN Bus)"
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
              <p className="text-xs text-slate-400 dark:text-slate-500 italic">No skills registered yet.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                {form.skills.map((sk) => {
                  const sName = sk.skill_name || sk.name;
                  const lvlConfig = PROFICIENCY_LEVELS.find((l) => l.id === (sk.proficiency || '').toLowerCase()) || PROFICIENCY_LEVELS[1];
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
              <span>📜</span> Professional Certifications
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
                placeholder="Issuing Authority (e.g. AWS, Cisco, Siemens) *"
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
                  Add Certification
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

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-200 dark:border-slate-800">
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2.5 text-xs font-bold rounded-xl bg-teal-600 hover:bg-teal-700 text-white shadow-md disabled:opacity-50 transition-colors cursor-pointer flex items-center gap-2"
            >
              {saving && <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />}
              {saving ? 'Saving...' : 'Save Employee Profile'}
            </button>
          </div>
        </form>

        {profile && passport && (
          <div className="mt-8 space-y-6">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
                <div>
                  <h2 className="text-sm font-black text-slate-900 dark:text-white flex items-center gap-2">
                    <span>🚀</span> Target Transition Readiness: {passport.target_role || form.target_role || 'Target Role'}
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Live alignment of current competencies against verified Maharashtra job market specifications.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => navigate(`/student/copilot?role=employee&q=${encodeURIComponent(`How can I transition from ${form.current_role || 'my current role'} to ${passport.target_role || form.target_role || 'my target role'}?`)}`)}
                  className="px-4 py-2 bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-700 hover:to-emerald-700 text-white rounded-xl text-xs font-bold shadow-xs cursor-pointer flex items-center gap-1.5 self-start sm:self-auto"
                >
                  <span>🤖</span> Consult AI Copilot →
                </button>
              </div>

              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 mb-4">
                <div className="flex justify-between items-center mb-1.5">
                  <span className="text-xs font-bold text-slate-700 dark:text-slate-300">Transition Skill Match</span>
                  <span className="text-xs font-black text-teal-600 dark:text-teal-400">{passport.skill_match_pct || 0}%</span>
                </div>
                <div className="w-full h-2.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-teal-500 to-emerald-500 rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, Math.max(0, passport.skill_match_pct || 0))}%` }}
                  />
                </div>
              </div>

              {passport.missing_skills && passport.missing_skills.length > 0 && (
                <div>
                  <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 mb-2 flex items-center gap-1.5">
                    <span>⚡</span> High-Priority Bridge Competencies:
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {passport.missing_skills.map((ms) => (
                      <span
                        key={ms.skill_id || ms.skill_name}
                        className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-900/60"
                      >
                        {ms.skill_name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {alerts && alerts.length > 0 && (
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
                <h2 className="text-sm font-black text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <span>📊</span> Industry Intelligence & Technology Signals ({form.industry})
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {alerts.map((al) => (
                    <div
                      key={al.signal_id || al.title}
                      className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between gap-1 mb-1.5">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-teal-600 dark:text-teal-400">
                            {al.domain_name || 'Market Signal'}
                          </span>
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-teal-100 dark:bg-teal-950/80 text-teal-800 dark:text-teal-300">
                            {al.impact_level || 'HIGH'}
                          </span>
                        </div>
                        <p className="text-xs font-bold text-slate-900 dark:text-white mb-1">
                          {al.headline || al.title}
                        </p>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 line-clamp-2">
                          {al.summary}
                        </p>
                      </div>
                      {al.top_affected_skills && al.top_affected_skills.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-slate-200/60 dark:border-slate-800/60 flex flex-wrap gap-1">
                          {al.top_affected_skills.slice(0, 2).map((sk) => (
                            <span key={sk.name || sk} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium">
                              {sk.name || sk}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  );
}
