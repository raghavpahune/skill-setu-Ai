import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';


const POPULAR_ROLES = [
  'AI Engineer',
  'Data Analyst',
  'EV Technician',
  'Cloud Architect',
  'Cybersecurity Analyst',
  'Robotics Engineer',
  'Full Stack Developer',
  'IoT Engineer',
  'Smart Manufacturing Engineer',
];

const INTEREST_DOMAINS = [
  { id: 'ai_ml', name: 'AI / ML', icon: '🤖' },
  { id: 'data_science', name: 'Data Science', icon: '📊' },
  { id: 'cloud', name: 'Cloud Computing', icon: '☁️' },
  { id: 'cybersecurity', name: 'Cybersecurity', icon: '🛡️' },
  { id: 'ev', name: 'Electric Vehicles', icon: '⚡' },
  { id: 'robotics', name: 'Robotics & Automation', icon: '🦾' },
  { id: 'iot', name: 'IoT & Embedded', icon: '📡' },
  { id: 'web_dev', name: 'Web Development', icon: '🌐' },
  { id: 'manufacturing', name: 'Smart Manufacturing', icon: '⚙️' },
];

const MAHARASHTRA_DISTRICTS = [
  'Maharashtra (All / State-wide)',
  'Pune',
  'Mumbai City',
  'Mumbai Suburban',
  'Thane',
  'Nagpur',
  'Nashik',
  'Chhatrapati Sambhajinagar (Aurangabad)',
  'Kolhapur',
  'Solapur',
  'Amravati',
  'Nanded',
  'Satara',
  'Raigad',
  'Palghar',
  'Ahmednagar',
];

const SUGGESTED_SKILLS = [
  'Python', 'SQL', 'Machine Learning', 'Deep Learning', 'Generative AI',
  'AI Agents', 'RAG', 'Data Analysis', 'Cloud Computing', 'AWS',
  'Cybersecurity', 'React', 'Node.js', 'EV Battery Technology',
  'EV Motor Design', 'PLC Programming', 'CNC Programming', 'Robotics',
  'Electrical Maintenance', 'DevOps', 'Kubernetes', 'Power BI', 'AutoCAD',
];

export default function StudentAssessmentForm({ onOpenExplainability, onAssessmentSubmitted }) {
  const { user } = useAuth();
  const [step, setStep] = useState(1);
  const [quizQuestions, setQuizQuestions] = useState([]);
  const [loadingQuestions, setLoadingQuestions] = useState(true);
  const [profileIncomplete, setProfileIncomplete] = useState(false);
  const [incompleteMessage, setIncompleteMessage] = useState('');
  const [assessmentDomain, setAssessmentDomain] = useState('general');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [latestAssessment, setLatestAssessment] = useState(null);

  const [historyList, setHistoryList] = useState([]);
  const [historyFilter, setHistoryFilter] = useState('all');
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [selectedHistoryItem, setSelectedHistoryItem] = useState(null);

  // Form State
  const [form, setForm] = useState({
    name: user?.full_name || '',
    education: user?.education || 'B.Tech Computer Engineering',
    district: user?.district || 'Pune',
    career_goal: 'AI Engineer',
    custom_career_goal: '',
    interests: ['AI / ML', 'Data Science'],
    current_skills: [
      { skill_name: 'Python', proficiency: 'intermediate' },
      { skill_name: 'SQL', proficiency: 'beginner' },
    ],
    quiz_answers: {},
  });

  useEffect(() => {
    if (user?.full_name) {
      setForm((prev) => ({
        ...prev,
        name: prev.name || user.full_name,
        education: prev.education || user.education || 'B.Tech Computer Engineering',
        district: user.district || prev.district,
      }));
    }
  }, [user]);


  const [skillInput, setSkillInput] = useState('');
  const [skillProficiency, setSkillProficiency] = useState('intermediate');

  const loadAssessmentHistory = () => {
    setLoadingHistory(true);
    api.getStudentAssessments({ limit: 50 })
      .then((res) => {
        if (res?.assessments) {
          setHistoryList(res.assessments);
        }
        setLoadingHistory(false);
      })
      .catch(() => setLoadingHistory(false));
  };

  useEffect(() => {
    api.getStudentProfile()
      .then((res) => {
        if (res?.profile) {
          const p = res.profile;
          setForm((prev) => {
            const loadedSkills = Array.isArray(p.skills) && p.skills.length > 0
              ? p.skills.map((s) => ({
                  skill_name: s.skill_name || s.name || '',
                  proficiency: s.proficiency || 'intermediate',
                })).filter((s) => s.skill_name)
              : prev.current_skills;

            return {
              ...prev,
              name: p.full_name || prev.name,
              education: p.degree || p.education_level || prev.education,
              district: p.preferred_location || prev.district,
              career_goal: p.target_role || p.desired_role || prev.career_goal,
              interests: Array.isArray(p.career_interests) && p.career_interests.length > 0
                ? p.career_interests
                : prev.interests,
              current_skills: loadedSkills,
            };
          });
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    api.getAssessmentQuizQuestions()
      .then((res) => {
        if (res?.status === 'profile_incomplete' && (!res.questions || res.questions.length === 0)) {
          setProfileIncomplete(true);
          setIncompleteMessage(res.message || 'Please complete your Skill Passport before taking your personalized assessment.');
          setLoadingQuestions(false);
          return;
        }
        setProfileIncomplete(false);
        if (res?.domain) {
          setAssessmentDomain(res.domain);
        }
        if (res?.questions && res.questions.length > 0) {
          setQuizQuestions(res.questions);
          const initialAnswers = {};
          res.questions.forEach((q) => {
            if (q.options?.length > 0) {
              initialAnswers[q.id] = q.options[0].key;
            }
          });
          setForm((prev) => ({ ...prev, quiz_answers: initialAnswers }));
        }
        setLoadingQuestions(false);
      })
      .catch((err) => {
        console.warn('Failed to load quiz questions:', err);
        setLoadingQuestions(false);
      });

    loadAssessmentHistory();
  }, []);

  // Add Skill to list
  const handleAddSkill = (skillName) => {
    const target = skillName || skillInput;
    if (!target || !target.trim()) return;
    const clean = target.trim();
    if (form.current_skills.some((s) => s.skill_name.toLowerCase() === clean.toLowerCase())) {
      return;
    }
    setForm((prev) => ({
      ...prev,
      current_skills: [...prev.current_skills, { skill_name: clean, proficiency: skillProficiency }],
    }));
    setSkillInput('');
  };

  const handleRemoveSkill = (skillName) => {
    setForm((prev) => ({
      ...prev,
      current_skills: prev.current_skills.filter((s) => s.skill_name !== skillName),
    }));
  };

  const handleToggleInterest = (domainName) => {
    setForm((prev) => {
      const exists = prev.interests.includes(domainName);
      return {
        ...prev,
        interests: exists
          ? prev.interests.filter((i) => i !== domainName)
          : [...prev.interests, domainName],
      };
    });
  };

  const handleQuizAnswer = (qId, optionKey) => {
    setForm((prev) => ({
      ...prev,
      quiz_answers: {
        ...prev.quiz_answers,
        [qId]: optionKey,
      },
    }));
  };

  // Submission handler
  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);

    const targetGoal = form.career_goal === 'Custom' ? form.custom_career_goal : form.career_goal;

    if (!form.name.trim() || !form.education.trim()) {
      setSubmitError('Please complete your Name and Current Education to proceed.');
      setSubmitting(false);
      setStep(1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    if (!targetGoal.trim()) {
      setSubmitError('Please choose or enter a Target Career Goal.');
      setSubmitting(false);
      setStep(2);
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    const payload = {
      name: form.name.trim(),
      education: form.education.trim(),
      district: form.district || 'Pune',
      career_goal: targetGoal.trim(),
      interests: form.interests || [],
      current_skills: form.current_skills || [],
      quiz_answers: form.quiz_answers || {},
    };

    try {
      const res = await api.submitStudentAssessment(payload);
      if (res?.assessment) {
        setLatestAssessment(res.assessment);
        setSelectedHistoryItem(null);
        setStep(5); // Jump to Results view
        window.scrollTo({ top: 0, behavior: 'smooth' });
        loadAssessmentHistory();
        if (typeof onAssessmentSubmitted === 'function') {
          try {
            onAssessmentSubmitted(res.assessment);
          } catch (callbackErr) {
            console.warn('[SkillSetu] onAssessmentSubmitted callback warning:', callbackErr);
          }
        }
      } else {
        throw new Error(res?.error || 'Failed to evaluate assessment submission.');
      }
    } catch (err) {
      setSubmitError(err?.message || 'Error submitting assessment. Please check network connection.');
    } finally {
      setSubmitting(false);
    }
  };

  const activeAssessment = selectedHistoryItem || latestAssessment || (historyList.length > 0 ? historyList[0] : null);

  const filteredHistory = historyList.filter((item) => {
    if (historyFilter === 'USER_SUBMITTED') return item.source === 'USER_SUBMITTED';
    if (historyFilter === 'DEMO_SYNTHETIC') return item.source === 'DEMO_SYNTHETIC';
    return true;
  });

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Assessment Header Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-teal-950 to-slate-900 border border-slate-800 rounded-2xl p-6 text-white shadow-md relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-96 bg-teal-500/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20"></div>
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-teal-500/20 text-teal-300 border border-teal-500/30 text-xs font-mono font-semibold uppercase tracking-wider">
              <span>Phase 12</span>
              <span>•</span>
              <span>Candidate Self-Assessment & Diagnostic Engine</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              Student Skills & Career Readiness Profiler
            </h2>
            <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
              Submit your academic background, self-reported skills, career goals, and complete a quick 5-question diagnostic quiz. Our grounded labour-market engine instantly computes your target competency match and identifies exact curriculum priorities.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 shrink-0">
            {step === 5 && (
              <button
                onClick={() => {
                  setSelectedHistoryItem(null);
                  setStep(1);
                }}
                className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-bold transition-colors border border-slate-700 shadow-sm cursor-pointer text-center"
              >
                + Start New Assessment
              </button>
            )}
            <div className="px-4 py-2.5 rounded-xl bg-slate-800/80 border border-slate-700 text-xs font-mono text-center">
              <span className="text-slate-400 block text-[10px]">PROVENANCE PROTOCOL</span>
              <span className="text-teal-400 font-bold">Self-Reported Evidence</span>
            </div>
          </div>
        </div>
      </div>

      {/* Stepper Progress Bar (when taking quiz) */}
      {step < 5 && (
        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 dark:text-slate-400 mb-2">
            <span className="text-teal-600 dark:text-teal-400 font-mono">Step {step} of 4</span>
            <span>
              {step === 1 && 'Academic & Demographics'}
              {step === 2 && 'Career Goal & Interests'}
              {step === 3 && 'Current Competencies'}
              {step === 4 && 'Diagnostic Aptitude Quiz'}
            </span>
          </div>
          <div className="grid grid-cols-4 gap-2">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className={`h-2 rounded-full transition-all duration-300 ${
                  i <= step
                    ? 'bg-gradient-to-r from-teal-500 to-emerald-500'
                    : 'bg-slate-100 dark:bg-slate-800'
                }`}
              ></div>
            ))}
          </div>
        </div>
      )}

      {submitError && (
        <div className="p-4 rounded-xl border border-rose-200 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-300 text-xs flex items-center gap-2">
          <span>⚠️</span>
          <span>{submitError}</span>
        </div>
      )}

      {/* MAIN FORM FLOW */}
      {step === 1 && (
        <div className="bg-white dark:bg-slate-900 p-6 sm:p-8 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-6">
          <div className="border-b border-slate-100 dark:border-slate-800 pb-4">
            <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <span>👤</span> Candidate Background & Location
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Enter your official name, enrolled course or vocational qualification, and district
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 text-xs">
            <div className="space-y-1.5">
              <label className="font-bold text-slate-700 dark:text-slate-300 block">
                Full Name *
              </label>
              <input
                type="text"
                required
                value={form.name}
                onChange={(e) => {
                  const val = e.target.value;
                  setForm((prev) => ({ ...prev, name: val }));
                }}
                placeholder="e.g. Tanmay Deshmukh"
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white font-medium focus:ring-2 focus:ring-teal-500 outline-none"
              />
            </div>

            <div className="space-y-1.5">
              <label className="font-bold text-slate-700 dark:text-slate-300 block">
                Current Education / Degree / Trade *
              </label>
              <input
                type="text"
                required
                value={form.education}
                onChange={(e) => {
                  const val = e.target.value;
                  setForm((prev) => ({ ...prev, education: val }));
                }}
                placeholder="e.g. B.Tech Computer Engineering, Diploma Mechanical, ITI Fitter, BCA"
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white font-medium focus:ring-2 focus:ring-teal-500 outline-none"
              />
            </div>

            <div className="space-y-1.5 md:col-span-2">
              <label className="font-bold text-slate-700 dark:text-slate-300 block">
                Maharashtra District / Region
              </label>
              <select
                value={form.district}
                onChange={(e) => {
                  const val = e.target.value;
                  setForm((prev) => ({ ...prev, district: val }));
                }}
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white font-medium focus:ring-2 focus:ring-teal-500 outline-none cursor-pointer"
              >
                {MAHARASHTRA_DISTRICTS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex justify-end pt-4 border-t border-slate-100 dark:border-slate-800">
            <button
              onClick={() => {
                if (!form.name.trim() || !form.education.trim()) {
                  setSubmitError('Please enter your Name and Current Education to proceed.');
                  return;
                }
                setSubmitError(null);
                setStep(2);
              }}
              className="px-6 py-2.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-xl shadow-xs transition-colors cursor-pointer flex items-center gap-1.5"
            >
              <span>Next: Career Goal & Interests</span>
              <span>→</span>
            </button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="bg-white dark:bg-slate-900 p-6 sm:p-8 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-6">
          <div className="border-b border-slate-100 dark:border-slate-800 pb-4">
            <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <span>🎯</span> Career Goal & Domain Interests
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Select your target employment aspiration and check technology sectors that match your career focus
            </p>
          </div>

          {/* Career Goal Picker */}
          <div className="space-y-3 text-xs">
            <label className="font-bold text-slate-700 dark:text-slate-300 block">
              Target Career Role *
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              {POPULAR_ROLES.map((role) => (
                <button
                  key={role}
                  type="button"
                  onClick={() => setForm((prev) => ({ ...prev, career_goal: role }))}
                  className={`p-3 rounded-xl border text-left font-bold transition-all cursor-pointer ${
                    form.career_goal === role
                      ? 'border-teal-500 bg-teal-50 dark:bg-teal-950/60 text-teal-800 dark:text-teal-200 ring-2 ring-teal-500/20'
                      : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/60 text-slate-700 dark:text-slate-300 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span>{role}</span>
                    {form.career_goal === role && <span className="text-teal-600 dark:text-teal-400 font-bold">✓</span>}
                  </div>
                </button>
              ))}
              <button
                type="button"
                onClick={() => setForm((prev) => ({ ...prev, career_goal: 'Custom' }))}
                className={`p-3 rounded-xl border text-left font-bold transition-all cursor-pointer ${
                  form.career_goal === 'Custom'
                    ? 'border-teal-500 bg-teal-50 dark:bg-teal-950/60 text-teal-800 dark:text-teal-200 ring-2 ring-teal-500/20'
                    : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/60 text-slate-700 dark:text-slate-300 hover:border-slate-300'
                }`}
              >
                + Other / Custom Role
              </button>
            </div>

            {form.career_goal === 'Custom' && (
              <input
                type="text"
                value={form.custom_career_goal}
                onChange={(e) => {
                  const val = e.target.value;
                  setForm((prev) => ({ ...prev, custom_career_goal: val }));
                }}
                placeholder="Enter your custom career role title (e.g. Embedded Firmware Engineer)"
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white font-medium focus:ring-2 focus:ring-teal-500 outline-none mt-2"
              />
            )}
          </div>

          {/* Domain Interests Chips */}
          <div className="space-y-3 text-xs pt-2">
            <label className="font-bold text-slate-700 dark:text-slate-300 block">
              Industry & Technology Domains of Interest
            </label>
            <div className="flex flex-wrap gap-2">
              {INTEREST_DOMAINS.map((dom) => {
                const isSelected = form.interests.includes(dom.name);
                return (
                  <button
                    key={dom.id}
                    type="button"
                    onClick={() => handleToggleInterest(dom.name)}
                    className={`px-3 py-2 rounded-xl text-xs font-semibold border flex items-center gap-1.5 transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-teal-600 text-white border-teal-600 shadow-2xs'
                        : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700'
                    }`}
                  >
                    <span>{dom.icon}</span>
                    <span>{dom.name}</span>
                    {isSelected && <span className="ml-1 text-[10px]">✕</span>}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex justify-between pt-4 border-t border-slate-100 dark:border-slate-800">
            <button
              onClick={() => setStep(1)}
              className="px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-bold rounded-xl transition-colors cursor-pointer"
            >
              ← Back
            </button>
            <button
              onClick={() => {
                const goal = form.career_goal === 'Custom' ? form.custom_career_goal : form.career_goal;
                if (!goal.trim()) {
                  setSubmitError('Please choose or enter a Target Career Goal.');
                  return;
                }
                setSubmitError(null);
                setStep(3);
              }}
              className="px-6 py-2.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-xl shadow-xs transition-colors cursor-pointer flex items-center gap-1.5"
            >
              <span>Next: Current Skills</span>
              <span>→</span>
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="bg-white dark:bg-slate-900 p-6 sm:p-8 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-6">
          <div className="border-b border-slate-100 dark:border-slate-800 pb-4">
            <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <span>🛠️</span> Current Skills & Self-Assessed Proficiency
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Add competencies you currently possess with your self-reported proficiency level
            </p>
          </div>

          {/* Add Skill Bar */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-3">
            <label className="text-xs font-bold text-slate-700 dark:text-slate-300 block">
              Add a Skill
            </label>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddSkill();
                  }
                }}
                placeholder="Type skill name (e.g. Python, React, CAD, PLC, EV Battery)..."
                className="flex-1 px-3.5 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-xs font-medium text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-teal-500"
              />
              <select
                value={skillProficiency}
                onChange={(e) => setSkillProficiency(e.target.value)}
                className="px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-xs font-bold text-slate-800 dark:text-slate-200 cursor-pointer"
              >
                <option value="beginner">Beginner (Foundational)</option>
                <option value="intermediate">Intermediate (Working)</option>
                <option value="advanced">Advanced (Production)</option>
              </select>
              <button
                type="button"
                onClick={() => handleAddSkill()}
                className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-xs font-bold transition-colors cursor-pointer"
              >
                + Add
              </button>
            </div>

            {/* Quick Suggestion Pills */}
            <div className="pt-2">
              <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 block mb-1.5">
                Quick add suggested skills:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {SUGGESTED_SKILLS.slice(0, 14).map((sk) => {
                  const alreadyAdded = form.current_skills.some(
                    (s) => s.skill_name.toLowerCase() === sk.toLowerCase()
                  );
                  return (
                    <button
                      key={sk}
                      type="button"
                      disabled={alreadyAdded}
                      onClick={() => handleAddSkill(sk)}
                      className={`px-2 py-1 rounded text-[11px] font-medium border transition-colors ${
                        alreadyAdded
                          ? 'bg-slate-100 dark:bg-slate-800/80 text-slate-400 border-slate-200 dark:border-slate-700 opacity-60 cursor-default'
                          : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-teal-500 hover:text-teal-600 cursor-pointer'
                      }`}
                    >
                      + {sk}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Current Skills Table / List */}
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-700 dark:text-slate-300">
                Your Added Competencies ({form.current_skills.length})
              </span>
              <span className="text-[10px] text-slate-400 font-mono">Self-Reported</span>
            </div>

            {form.current_skills.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {form.current_skills.map((sk) => (
                  <div
                    key={sk.skill_name}
                    className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 flex items-center justify-between"
                  >
                    <div>
                      <span className="font-bold text-slate-900 dark:text-white block">{sk.skill_name}</span>
                      <span className="text-[10px] font-mono text-teal-600 dark:text-teal-400 capitalize">
                        {sk.proficiency} Level
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveSkill(sk.skill_name)}
                      className="text-slate-400 hover:text-rose-500 p-1 transition-colors cursor-pointer"
                      title="Remove skill"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-400 text-xs py-4 text-center border border-dashed rounded-xl">
                No skills added yet. Add at least 1-2 skills above to evaluate your profile.
              </p>
            )}
          </div>

          <div className="flex justify-between pt-4 border-t border-slate-100 dark:border-slate-800">
            <button
              onClick={() => setStep(2)}
              className="px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-bold rounded-xl transition-colors cursor-pointer"
            >
              ← Back
            </button>
            <button
              onClick={() => {
                if (form.current_skills.length === 0) {
                  setSubmitError('Please add at least one current skill before proceeding to the quiz.');
                  return;
                }
                setSubmitError(null);
                setStep(4);
              }}
              className="px-6 py-2.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-xl shadow-xs transition-colors cursor-pointer flex items-center gap-1.5"
            >
              <span>Next: Diagnostic Quiz</span>
              <span>→</span>
            </button>
          </div>
        </div>
      )}

      {step === 4 && (
        <div className="bg-white dark:bg-slate-900 p-6 sm:p-8 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-6">
          <div className="border-b border-slate-100 dark:border-slate-800 pb-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <span>🧠</span> Diagnostic Skill & Career Aptitude Quiz
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  5 practical scenario-based questions to calibrate your problem-solving aptitude and technical maturity
                </p>
              </div>
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 bg-teal-50 dark:bg-teal-950 text-teal-700 dark:text-teal-300 rounded border border-teal-200 dark:border-teal-800">
                5 Questions
              </span>
            </div>
          </div>

          {profileIncomplete ? (
            <div className="p-6 rounded-2xl border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-200 text-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2 font-bold text-base">
                  <span>⚠️</span>
                  <span>Skill Passport Incomplete</span>
                </div>
                <p className="text-xs text-amber-800 dark:text-amber-300">
                  {incompleteMessage || 'Please complete your Skill Passport before taking your personalized assessment.'}
                </p>
              </div>
              <Link
                to="/student/profile"
                className="px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold rounded-xl whitespace-nowrap transition-colors shadow-xs"
              >
                Complete Skill Passport →
              </Link>
            </div>
          ) : loadingQuestions ? (
            <div className="py-12 text-center text-xs text-slate-500 animate-pulse">
              Loading diagnostic questions from SkillSetuAI intelligence engine...
            </div>
          ) : (
            <div className="space-y-6">
              {quizQuestions.map((q, idx) => (
                <div
                  key={q.id}
                  className="p-4 sm:p-5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/80 space-y-3"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono text-teal-600 dark:text-teal-400 font-bold uppercase tracking-wider text-[11px]">
                      Question {idx + 1} • {q.category}
                    </span>
                    {q.skills?.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {q.skills.map((sk) => (
                          <span
                            key={sk}
                            className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-teal-50 dark:bg-teal-950 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800"
                          >
                            {sk}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <h4 className="font-bold text-slate-900 dark:text-white text-xs sm:text-sm leading-snug">
                    {q.question}
                  </h4>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 text-xs">
                    {q.options.map((opt) => {
                      const isSelected = form.quiz_answers[q.id] === opt.key;
                      return (
                        <button
                          key={opt.key}
                          type="button"
                          onClick={() => handleQuizAnswer(q.id, opt.key)}
                          className={`p-3 rounded-xl border text-left font-medium transition-all cursor-pointer flex items-start gap-2.5 ${
                            isSelected
                              ? 'border-teal-500 bg-teal-50 dark:bg-teal-950/70 text-teal-900 dark:text-teal-100 ring-2 ring-teal-500/20'
                              : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:border-slate-300'
                          }`}
                        >
                          <span
                            className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[11px] shrink-0 ${
                              isSelected
                                ? 'bg-teal-600 text-white'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                            }`}
                          >
                            {opt.key.toUpperCase()}
                          </span>
                          <span className="leading-relaxed">{opt.text}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}

          {submitError && (
            <div className="p-4 rounded-xl border border-rose-200 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-300 text-xs flex items-center gap-2">
              <span>⚠️</span>
              <span>{submitError}</span>
            </div>
          )}

          <div className="flex justify-between pt-4 border-t border-slate-100 dark:border-slate-800">
            <button
              onClick={() => setStep(3)}
              disabled={submitting}
              className="px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-bold rounded-xl transition-colors cursor-pointer disabled:opacity-50"
            >
              ← Back
            </button>
            <button
              onClick={handleSubmit}
              disabled={submitting || (profileIncomplete && quizQuestions.length === 0)}
              className="px-8 py-3 bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-700 hover:to-emerald-700 text-white text-xs font-bold rounded-xl shadow-md transition-all cursor-pointer flex items-center gap-2 disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                  <span>Evaluating Assessment...</span>
                </>
              ) : (
                <>
                  <span>🚀 Submit & Calculate Readiness Report</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* STEP 5 / RESULTS VIEW */}
      {step === 5 && activeAssessment && (
        <div className="space-y-6 animate-fadeIn">
          {/* Assessment Overview Card */}
          <div className="bg-white dark:bg-slate-900 p-6 sm:p-8 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 mb-6 border-b border-slate-100 dark:border-slate-800">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-white">
                    {activeAssessment.name}’s Assessment Evaluation
                  </h3>
                  <span
                    className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full border uppercase font-mono ${
                      activeAssessment.source === 'USER_SUBMITTED'
                        ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                        : 'bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                    }`}
                  >
                    {activeAssessment.source === 'USER_SUBMITTED' ? 'User Submitted' : 'Demo Benchmark'}
                  </span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  {activeAssessment.education} • {activeAssessment.district} • Target:{' '}
                  <strong className="text-slate-900 dark:text-white">{activeAssessment.career_goal}</strong>
                </p>
              </div>

              <div className="text-xs text-slate-400 font-mono self-start sm:self-auto">
                ID: {activeAssessment.id}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              <div className="p-4 rounded-xl bg-emerald-50/60 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900/60">
                <span className="text-[10px] font-bold text-emerald-800 dark:text-emerald-300 uppercase font-mono block">
                  Domain Readiness Score
                </span>
                <div className="text-2xl font-extrabold text-slate-900 dark:text-white mt-1">
                  {activeAssessment.domain_readiness_score ?? activeAssessment.combined_readiness_score ?? 0}%
                </div>
                <p className="text-[11px] text-emerald-700 dark:text-emerald-400 mt-0.5">
                  Calibrated across domain aptitude & role prerequisites
                </p>
              </div>

              <div className="p-4 rounded-xl bg-blue-50/60 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900/60">
                <span className="text-[10px] font-bold text-blue-800 dark:text-blue-300 uppercase font-mono block">
                  Skill Proficiency Score
                </span>
                <div className="text-2xl font-extrabold text-slate-900 dark:text-white mt-1">
                  {activeAssessment.skill_proficiency_score ?? activeAssessment.skill_match_pct ?? 0}%
                </div>
                <p className="text-[11px] text-blue-700 dark:text-blue-400 mt-0.5">
                  Reported vs required {activeAssessment.career_goal} competencies
                </p>
              </div>

              <div className="p-4 rounded-xl bg-teal-50/60 dark:bg-teal-950/30 border border-teal-200 dark:border-teal-900/60">
                <span className="text-[10px] font-bold text-teal-800 dark:text-teal-300 uppercase font-mono block">
                  Diagnostic Aptitude
                </span>
                <div className="text-2xl font-extrabold text-slate-900 dark:text-white mt-1">
                  {activeAssessment.quiz_score_pct}%
                </div>
                <p className="text-[11px] text-teal-700 dark:text-teal-400 mt-0.5">
                  Scenario-based problem solving score
                </p>
              </div>

              <div className="p-4 rounded-xl bg-purple-50/60 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-900/60">
                <span className="text-[10px] font-bold text-purple-800 dark:text-purple-300 uppercase font-mono block">
                  Overall Readiness
                </span>
                <div className="text-lg font-extrabold text-slate-900 dark:text-white mt-1 uppercase">
                  {activeAssessment.evaluation_summary?.readiness_level?.replace('_', ' ') || 'EVALUATED'}
                </div>
                <p className="text-[11px] text-purple-700 dark:text-purple-400 mt-0.5">
                  Live Maharashtra benchmark
                </p>
              </div>
            </div>

            {activeAssessment.knowledge_breakdown && (
              <div className="space-y-3 mb-8 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                <h4 className="font-bold text-slate-900 dark:text-white text-sm">
                  Knowledge Breakdown by Competency
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                  <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800">
                    <span className="font-bold text-emerald-800 dark:text-emerald-300 block mb-1">
                      Strong Knowledge ({activeAssessment.knowledge_breakdown.strong?.length || 0})
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {activeAssessment.knowledge_breakdown.strong?.map((s) => (
                        <span key={s} className="px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900 text-emerald-800 dark:text-emerald-200 text-[10px]">
                          {s}
                        </span>
                      ))}
                      {!activeAssessment.knowledge_breakdown.strong?.length && <span className="text-slate-400 text-[10px]">None identified</span>}
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800">
                    <span className="font-bold text-blue-800 dark:text-blue-300 block mb-1">
                      Moderate Knowledge ({activeAssessment.knowledge_breakdown.moderate?.length || 0})
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {activeAssessment.knowledge_breakdown.moderate?.map((s) => (
                        <span key={s} className="px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 text-[10px]">
                          {s}
                        </span>
                      ))}
                      {!activeAssessment.knowledge_breakdown.moderate?.length && <span className="text-slate-400 text-[10px]">None identified</span>}
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800">
                    <span className="font-bold text-amber-800 dark:text-amber-300 block mb-1">
                      Weak Knowledge ({activeAssessment.knowledge_breakdown.weak?.length || 0})
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {activeAssessment.knowledge_breakdown.weak?.map((s) => (
                        <span key={s} className="px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900 text-amber-800 dark:text-amber-200 text-[10px]">
                          {s}
                        </span>
                      ))}
                      {!activeAssessment.knowledge_breakdown.weak?.length && <span className="text-slate-400 text-[10px]">None identified</span>}
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800">
                    <span className="font-bold text-rose-800 dark:text-rose-300 block mb-1">
                      Missing Prerequisites ({activeAssessment.knowledge_breakdown.missing?.length || 0})
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {activeAssessment.knowledge_breakdown.missing?.map((m) => (
                        <span key={m.skill_id || m.name} className="px-1.5 py-0.5 rounded bg-rose-100 dark:bg-rose-900 text-rose-800 dark:text-rose-200 text-[10px]">
                          {m.name || m.skill_name}
                        </span>
                      ))}
                      {!activeAssessment.knowledge_breakdown.missing?.length && <span className="text-slate-400 text-[10px]">None</span>}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Priority Skill Gaps */}
            <div className="space-y-4 mb-8">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                <div>
                  <h4 className="font-bold text-slate-900 dark:text-white text-sm">
                    Identified Competency Deficits to Bridge
                  </h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    High-demand prerequisites for {activeAssessment.career_goal} requiring prioritized learning
                  </p>
                </div>
              </div>

              {activeAssessment.evaluation_summary?.missing_skills?.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {activeAssessment.evaluation_summary.missing_skills.map((m) => (
                    <div
                      key={m.skill_id || m.name}
                      className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-2 flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between gap-1 mb-1">
                          <span className="font-bold text-slate-900 dark:text-white text-xs">
                            {m.name}
                          </span>
                          <span
                            className={`text-[9px] font-bold px-1.5 py-0.5 rounded font-mono uppercase ${
                              m.priority === 'CRITICAL'
                                ? 'bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300'
                                : 'bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300'
                            }`}
                          >
                            {m.priority} Deficit
                          </span>
                        </div>
                        <span className="text-[10px] text-slate-500 dark:text-slate-400 font-medium block">
                          {m.category} {m.nsqf_level ? `• NSQF Level ${m.nsqf_level}` : ''}
                        </span>
                      </div>

                      {onOpenExplainability && (
                        <button
                          onClick={() => onOpenExplainability(m.skill_id || m.name, m.name)}
                          className="mt-2 text-[10px] font-bold text-teal-700 dark:text-teal-300 bg-teal-50 dark:bg-teal-950/60 hover:bg-teal-100 dark:hover:bg-teal-900 px-2 py-1 rounded border border-teal-200 dark:border-teal-800 transition-colors cursor-pointer text-center"
                        >
                          Why learn this? (5D Evidence) ⓘ
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-emerald-600 dark:text-emerald-400 font-semibold p-4 bg-emerald-50 dark:bg-emerald-950/30 rounded-xl border border-emerald-200 dark:border-emerald-800">
                  ✓ Excellent alignment! You already possess the primary competencies for this target career role.
                </p>
              )}
            </div>

            {/* Recommended Action Steps */}
            {activeAssessment.evaluation_summary?.recommended_next_steps?.length > 0 && (
              <div className="space-y-3 mb-6 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700">
                <h4 className="font-bold text-slate-900 dark:text-white text-xs uppercase tracking-wider font-mono">
                  Recommended Sequential Learning Pathway
                </h4>
                <ul className="space-y-2 text-xs text-slate-700 dark:text-slate-300">
                  {activeAssessment.evaluation_summary.recommended_next_steps.map((st, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="w-5 h-5 rounded-full bg-teal-600 text-white font-bold text-[10px] flex items-center justify-center shrink-0 mt-0.5">
                        {idx + 1}
                      </span>
                      <span className="leading-relaxed">{st}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Bottom Actions */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-slate-100 dark:border-slate-800">
              <Link
                to="/student/copilot"
                className="px-4 py-2 bg-slate-900 dark:bg-teal-600 hover:bg-slate-800 dark:hover:bg-teal-700 text-white text-xs font-bold rounded-xl transition-colors shadow-2xs flex items-center gap-1.5 cursor-pointer"
              >
                <span>Consult Career Copilot for Personalized Plan</span>
                <span>→</span>
              </Link>
              <button
                onClick={() => {
                  setSelectedHistoryItem(null);
                  setStep(1);
                }}
                className="px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-bold rounded-xl hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors cursor-pointer"
              >
                + Retake Assessment
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ASSESSMENT HISTORY / BENCHMARK RECORDS TABLE */}
      <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
          <div>
            <h3 className="font-bold text-slate-900 dark:text-white text-base">
              Candidate Self-Assessment Registry
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Review saved student submissions and benchmark demo profiles
            </p>
          </div>

          <div className="inline-flex rounded-lg border border-slate-200 dark:border-slate-700 p-0.5 bg-slate-50 dark:bg-slate-800/80 text-[11px] font-semibold">
            <button
              onClick={() => setHistoryFilter('all')}
              className={`px-3 py-1 rounded-md transition-colors cursor-pointer ${
                historyFilter === 'all'
                  ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs font-bold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              All ({historyList.length})
            </button>
            <button
              onClick={() => setHistoryFilter('USER_SUBMITTED')}
              className={`px-3 py-1 rounded-md transition-colors cursor-pointer ${
                historyFilter === 'USER_SUBMITTED'
                  ? 'bg-white dark:bg-slate-900 text-emerald-700 dark:text-emerald-300 shadow-2xs font-bold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-emerald-600'
              }`}
            >
              User Submitted ({historyList.filter((h) => h.source === 'USER_SUBMITTED').length})
            </button>
            <button
              onClick={() => setHistoryFilter('DEMO_SYNTHETIC')}
              className={`px-3 py-1 rounded-md transition-colors cursor-pointer ${
                historyFilter === 'DEMO_SYNTHETIC'
                  ? 'bg-white dark:bg-slate-900 text-amber-700 dark:text-amber-300 shadow-2xs font-bold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-amber-600'
              }`}
            >
              Demo ({historyList.filter((h) => h.source === 'DEMO_SYNTHETIC').length})
            </button>
          </div>
        </div>

        {loadingHistory ? (
          <div className="py-6 text-center text-xs text-slate-500 animate-pulse">
            Loading assessment records...
          </div>
        ) : filteredHistory.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 font-semibold border-b border-slate-200 dark:border-slate-700">
                <tr>
                  <th className="p-3">Candidate</th>
                  <th className="p-3">Education / District</th>
                  <th className="p-3">Target Goal</th>
                  <th className="p-3">Quiz Score</th>
                  <th className="p-3">Match %</th>
                  <th className="p-3">Data Provenance</th>
                  <th className="p-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredHistory.map((item) => (
                  <tr
                    key={item.id}
                    className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="p-3 font-bold text-slate-900 dark:text-white">
                      <div>{item.name}</div>
                      <div className="text-[10px] text-slate-400 font-mono font-normal">{item.id}</div>
                    </td>
                    <td className="p-3 text-slate-600 dark:text-slate-300">
                      <div>{item.education}</div>
                      <span className="text-[10px] text-slate-400">{item.district}</span>
                    </td>
                    <td className="p-3 font-semibold text-teal-700 dark:text-teal-400">
                      {item.career_goal}
                    </td>
                    <td className="p-3 font-mono font-bold text-slate-900 dark:text-white">
                      {item.quiz_score_pct}%
                    </td>
                    <td className="p-3 font-mono font-bold text-slate-900 dark:text-white">
                      {item.skill_match_pct}%
                    </td>
                    <td className="p-3">
                      <span
                        className={`inline-block text-[10px] font-bold px-2 py-0.5 rounded font-mono uppercase ${
                          item.source === 'USER_SUBMITTED'
                            ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                            : 'bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800'
                        }`}
                      >
                        {item.source === 'USER_SUBMITTED' ? 'User Submitted' : 'Demo Benchmark'}
                      </span>
                    </td>
                    <td className="p-3 text-right">
                      <button
                        onClick={() => {
                          setSelectedHistoryItem(item);
                          setStep(5);
                          window.scrollTo({ top: 0, behavior: 'smooth' });
                        }}
                        className="px-2.5 py-1 text-xs font-bold rounded-lg bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 hover:bg-teal-100 dark:hover:bg-teal-900 border border-teal-200 dark:border-teal-800 transition-colors cursor-pointer"
                      >
                        View Report ↗
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-slate-500 py-6 text-center">
            No assessment records match the selected filter.
          </p>
        )}
      </div>
    </div>
  );
}
