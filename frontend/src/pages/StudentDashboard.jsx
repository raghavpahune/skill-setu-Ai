import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Layout from '../components/Layout';
import StatCard from '../components/StatCard';
import PassportRadar from '../components/PassportRadar';
import StudentAlertsFeed from '../components/StudentAlertsFeed';
import SkillExplainabilityModal from '../components/SkillExplainabilityModal';
import StudentAssessmentForm from '../components/StudentAssessmentForm';
import CareerRecommendationsView from '../components/CareerRecommendationsView';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';




function EmptyState({
  title = 'No records available',
  message = 'No data points were returned for this section.',
  icon,
  action,
}) {
  return (
    <div className="py-12 px-4 text-center rounded-xl bg-slate-50 dark:bg-slate-900 border border-dashed border-slate-200 dark:border-slate-800">
      <div className="w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-lg mx-auto mb-3 shadow-2xs">
        {icon || '📭'}
      </div>
      <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200 mb-1">{title}</h4>
      <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto mb-4">{message}</p>
      {action && <div>{action}</div>}
    </div>
  );
}

function ErrorBanner({ message, onRetry }) {
  return (
    <div className="p-4 mb-6 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-rose-800 dark:text-rose-300 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs">
      <div className="flex items-center gap-2.5">
        <span className="text-base">⚠️</span>
        <span className="font-semibold">{message}</span>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-[11px] font-bold shadow-xs cursor-pointer self-start sm:self-auto transition-colors"
        >
          Retry Fetch
        </button>
      )}
    </div>
  );
}

function SkeletonKpiCard() {
  return (
    <div className="p-4 sm:p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 animate-pulse">
      <div className="h-3 w-24 bg-slate-200 dark:bg-slate-800 rounded mb-2.5"></div>
      <div className="h-8 w-28 bg-slate-200 dark:bg-slate-800 rounded mb-2"></div>
      <div className="h-3 w-32 bg-slate-100 dark:bg-slate-800/60 rounded"></div>
    </div>
  );
}

function SkeletonRoadmapStep() {
  return (
    <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 animate-pulse flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
      <div className="flex items-start gap-3 w-full sm:w-3/4">
        <div className="w-8 h-8 rounded-lg bg-slate-200 dark:bg-slate-700 shrink-0"></div>
        <div className="space-y-2 w-full">
          <div className="h-4 w-40 bg-slate-200 dark:bg-slate-700 rounded"></div>
          <div className="h-3 w-full bg-slate-100 dark:bg-slate-800 rounded"></div>
        </div>
      </div>
      <div className="h-8 w-24 bg-slate-200 dark:bg-slate-700 rounded self-end sm:self-center"></div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="h-6 w-48 bg-slate-200 dark:bg-slate-700 rounded mb-4"></div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-20 bg-slate-100 dark:bg-slate-800 rounded-xl"></div>
        ))}
      </div>
      <div className="h-64 bg-slate-100 dark:bg-slate-800 rounded-xl"></div>
    </div>
  );
}

function OpportunitySkeleton() {
  return (
    <div className="animate-pulse p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
      <div className="flex items-start gap-3 w-full">
        <div className="w-8 h-8 rounded-lg bg-slate-200 dark:bg-slate-700 shrink-0"></div>
        <div className="space-y-2 w-full">
          <div className="h-4 w-40 bg-slate-200 dark:bg-slate-700 rounded"></div>
          <div className="h-3 w-full bg-slate-100 dark:bg-slate-800 rounded"></div>
        </div>
      </div>
      <div className="h-8 w-24 bg-slate-200 dark:bg-slate-700 rounded self-end sm:self-center"></div>
    </div>
  );
}

const VALID_STUDENT_TABS = ['passport', 'assessment', 'recommendations', 'roadmap', 'signals'];

export default function StudentDashboard() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const urlTab = searchParams.get('tab');
  const mainTab = urlTab && VALID_STUDENT_TABS.includes(urlTab) ? urlTab : 'passport';
  const [students, setStudents] = useState([]);
  const [selectedStudentId, setSelectedStudentId] = useState(user?.role === 'STUDENT' || user?.id ? 'me' : '');
  const [passport, setPassport] = useState(null);
  const [roadmap, setRoadmap] = useState(null);
  const [schemes, setSchemes] = useState([]);
  const [schemesLoading, setSchemesLoading] = useState(false);
  const [schemesError, setSchemesError] = useState(null);
  const [opportunities, setOpportunities] = useState([]);
  const [oppsLoading, setOppsLoading] = useState(false);
  const [oppsError, setOppsError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [passportError, setPassportError] = useState(null);
  const [roadmapError, setRoadmapError] = useState(null);
  const [recalculatingRoadmap, setRecalculatingRoadmap] = useState(false);
  const [filterTab, setFilterTab] = useState('all'); // 'all' | 'acquired' | 'gaps'

  const handleTabChange = (newTab) => {
    if (VALID_STUDENT_TABS.includes(newTab)) {
      const newParams = new URLSearchParams(searchParams);
      newParams.set('tab', newTab);
      setSearchParams(newParams, { replace: true });
      // Notify window resize so DemoTour updates position
      setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
      }, 50);
    }
  };

  // Skill Explainability Modal state (PROJECT_SPEC Section 18)
  const [explainModalOpen, setExplainModalOpen] = useState(false);
  const [selectedExplainSkill, setSelectedExplainSkill] = useState('');
  const [selectedExplainSkillName, setSelectedExplainSkillName] = useState('');

  const handleOpenExplainability = (skillIdOrName, skillName = '') => {
    setSelectedExplainSkill(skillIdOrName);
    setSelectedExplainSkillName(skillName || skillIdOrName);
    setExplainModalOpen(true);
  };

  useEffect(() => {
    let isCurrent = true;
    setStudents((prev) => prev.filter((s) => s.user_id !== 'me'));

    if (!user?.id) {
      setPassport(null);
      setSelectedStudentId((prev) => (prev === 'me' ? '' : prev));
    }

    if (user?.id) {
      if (user.role === 'STUDENT') {
        setSelectedStudentId('me');
      }
      api.getMyPassport()
        .then((myPass) => {
          if (!isCurrent) return;
          if (myPass && (myPass.is_personalized || myPass.source === 'USER_SUBMITTED')) {
            setSelectedStudentId('me');
            setPassport(myPass);
            setStudents((prev) => {
              const filtered = prev.filter((s) => s.user_id !== 'me');
              const meItem = {
                user_id: 'me',
                name: `${myPass.name || user.full_name || 'My Profile'} (Live Profile)`,
                target_role: myPass.target_role || 'Target Career',
                skill_match_pct: myPass.skill_match_pct || 0,
                source: 'USER_SUBMITTED',
              };
              return [meItem, ...filtered];
            });
          } else if (myPass && myPass.has_assessment === false) {
            setPassport(myPass);
            setStudents((prev) => {
              const filtered = prev.filter((s) => s.user_id !== 'me');
              const meItem = {
                user_id: 'me',
                name: `${user.full_name || 'My Profile'} (Unassessed)`,
                target_role: 'Pending Assessment',
                skill_match_pct: 0,
                source: 'NO_SUBMISSION',
              };
              return [meItem, ...filtered];
            });
          }
        })
        .catch(() => {});
    }

    api.getStudents()
      .then((res) => {
        if (!isCurrent) return;
        const studentList = Array.isArray(res) ? res.filter((r) => r.user_id !== 'me') : [];
        setStudents((prev) => {
          const currentMe = user?.id ? prev.find((s) => s.user_id === 'me') : null;
          if (currentMe) {
            return [currentMe, ...studentList];
          }
          return studentList;
        });
        if (studentList.length > 0) {
          setSelectedStudentId((prev) => prev || (user?.id && user.role === 'STUDENT' ? 'me' : studentList[0].user_id));
        }
      })
      .catch((err) => {
        if (!isCurrent) return;
        console.warn('Failed to load candidate list:', err);
      });

    return () => {
      isCurrent = false;
    };
  }, [user]);

  // Load personalized recommendations when student changes (Phase 15)
  const loadSchemesAndOpps = useCallback(() => {
    if (!selectedStudentId) return;

    setSchemesLoading(true);
    setSchemesError(null);
    setOppsLoading(true);
    setOppsError(null);

    // Load schemes with deduplication by scheme_code || id
    api.getRecommendedSchemes(selectedStudentId)
      .then((res) => {
        const rawSchemes = (res && Array.isArray(res.schemes)) ? res.schemes : (Array.isArray(res) ? res : []);
        const seen = new Set();
        const unique = [];
        for (const s of rawSchemes) {
          const key = s.scheme_code || s.id || s.title;
          if (key && !seen.has(key)) {
            seen.add(key);
            unique.push(s);
          }
        }
        setSchemes(unique.slice(0, 4));
      })
      .catch((err) => {
        // Fallback: load all schemes (non-personalized)
        api.getSchemes({ limit: 4 })
          .then((res) => {
            const raw = Array.isArray(res) ? res : [];
            const seen = new Set();
            const unique = [];
            for (const s of raw) {
              const key = s.scheme_code || s.id || s.title;
              if (key && !seen.has(key)) {
                seen.add(key);
                unique.push(s);
              }
            }
            setSchemes(unique);
          })
          .catch((e) => setSchemesError(e?.message || 'Failed to load welfare schemes.'));
      })
      .finally(() => setSchemesLoading(false));

    // Load opportunities with deduplication by external_id || id
    api.getRecommendedGovOpportunities(selectedStudentId)
      .then((res) => {
        const rawOpps = (res && Array.isArray(res.opportunities)) ? res.opportunities : (Array.isArray(res) ? res : []);
        const seen = new Set();
        const unique = [];
        for (const o of rawOpps) {
          const key = o.external_id || o.id || o.name;
          if (key && !seen.has(key)) {
            seen.add(key);
            unique.push(o);
          }
        }
        setOpportunities(unique.slice(0, 4));
      })
      .catch((err) => {
        // Fallback: load generic opportunities
        api.getOpportunities({ limit: 4 })
          .then((res) => {
            const raw = Array.isArray(res) ? res : [];
            const seen = new Set();
            const unique = [];
            for (const o of raw) {
              const key = o.external_id || o.id || o.name;
              if (key && !seen.has(key)) {
                seen.add(key);
                unique.push(o);
              }
            }
            setOpportunities(unique);
          })
          .catch((e) => setOppsError(e?.message || 'Failed to load opportunities.'));
      })
      .finally(() => setOppsLoading(false));
  }, [selectedStudentId]);

  useEffect(() => {
    loadSchemesAndOpps();
  }, [loadSchemesAndOpps]);

  // Fetch passport and roadmap whenever candidate changes
  const fetchStudentData = () => {
    if (!selectedStudentId) return;
    setLoading(true);
    setPassportError(null);
    setRoadmapError(null);

    const passportPromise = selectedStudentId === 'me'
      ? api.getMyPassport()
      : api.getStudentPassport(selectedStudentId);

    const roadmapPromise = selectedStudentId === 'me'
      ? api.getMyRoadmap()
      : api.getStudentRoadmap(selectedStudentId);

    Promise.allSettled([passportPromise, roadmapPromise]).then(([pRes, rRes]) => {
      if (pRes.status === 'fulfilled' && pRes.value && !pRes.value.error) {
        setPassport(pRes.value);
      } else {
        const errMsg = pRes.status === 'rejected'
          ? (pRes.reason?.message || 'Failed to connect to passport API')
          : (pRes.value?.error || 'Candidate passport record not found');
        setPassportError(errMsg);
      }

      if (rRes.status === 'fulfilled' && rRes.value && !rRes.value.error) {
        setRoadmap(rRes.value);
      } else {
        const errMsg = rRes.status === 'rejected'
          ? (rRes.reason?.message || 'Failed to connect to roadmap API')
          : (rRes.value?.error || 'Curriculum roadmap not available for this role');
        setRoadmapError(errMsg);
      }
      setLoading(false);
    });
  };

  useEffect(() => {
    fetchStudentData();
  }, [selectedStudentId]);

  const handleRecalculateRoadmap = async () => {
    try {
      setRecalculatingRoadmap(true);
      setRoadmapError(null);
      const res = selectedStudentId === 'me'
        ? await api.recalculateMyRoadmap()
        : await api.recalculateStudentRoadmap(selectedStudentId);
      setRoadmap(res);
    } catch (err) {
      setRoadmapError(err?.message || 'Failed to recalculate adaptive roadmap');
    } finally {
      setRecalculatingRoadmap(false);
    }
  };


  // Derived calculations for Comparison Flow
  const comparisonData = useMemo(() => {
    if (!passport) return { items: [], acquired: [], gaps: [], additional: [] };

    const currentMap = new Map((passport.current_skills || []).map((c) => [c.skill_id, c]));
    const requiredSkills = passport.required_skills || [];

    const items = requiredSkills.map((req) => {
      const cur = currentMap.get(req.skill_id);
      const isAcquired = !!cur;
      const proficiency = cur?.proficiency || 'none';
      const profScore = { beginner: 35, intermediate: 70, advanced: 100 }[proficiency] || 0;
      const isProficient = proficiency === 'advanced' || proficiency === 'intermediate';

      // Check if skill is in recommended roadmap
      const roadmapStep = (roadmap?.roadmap || []).find((s) => s.skill_id === req.skill_id);

      return {
        skill_id: req.skill_id,
        skill_name: req.skill_name || req.skill_id,
        category: req.category || cur?.category || 'Technical',
        nsqf_level: req.nsqf_level || cur?.nsqf_level || null,
        proficiency,
        profScore,
        isAcquired,
        isProficient,
        status: !isAcquired ? 'gap' : isProficient ? 'proficient' : 'upskill',
        roadmapStep: roadmapStep?.step || null,
      };
    });

    const acquired = items.filter((i) => i.isAcquired);
    const gaps = items.filter((i) => !i.isAcquired);

    // Cross-functional / secondary skills held by student outside role requirements
    const requiredIds = new Set(requiredSkills.map((r) => r.skill_id));
    const additional = (passport.current_skills || []).filter((c) => !requiredIds.has(c.skill_id));

    return { items, acquired, gaps, additional };
  }, [passport, roadmap]);

  const filteredItems = useMemo(() => {
    if (filterTab === 'acquired') return comparisonData.acquired;
    if (filterTab === 'gaps') return comparisonData.gaps;
    return comparisonData.items;
  }, [comparisonData, filterTab]);

  return (
    <Layout>
      {/* Header & Main Navigation Tabs */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
              Student Dynamic Skill Passport & Profiler
            </h1>
            <span className="text-[11px] font-mono px-2 py-0.5 bg-teal-50 dark:bg-teal-950 text-teal-800 dark:text-teal-300 font-semibold rounded border border-teal-200 dark:border-teal-800">
              NSQF Aligned
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            Personalized competency verification, self-assessment diagnostic quiz, labour benchmark alignment, and validated roadmaps
          </p>
        </div>

        {/* Candidate Profile Selector & Quick Switch Pills (relevant when on Passport or Recommendations tab) */}
        {(mainTab === 'passport' || mainTab === 'recommendations') && students.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 self-start md:self-auto">
            <div className="flex items-center gap-2 bg-white dark:bg-slate-900 p-1.5 px-3 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
              <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Candidate:</span>
              <select
                value={selectedStudentId}
                onChange={(e) => setSelectedStudentId(e.target.value)}
                disabled={loading}
                className="px-2.5 py-1 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-bold text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500 cursor-pointer disabled:opacity-50"
              >
                {students.map((s) => (
                  <option key={s.user_id} value={s.user_id}>
                    {s.name} ({s.target_role})
                  </option>
                ))}
              </select>
            </div>

            {/* Quick Persona Pills for Live Pitch */}
            <div className="hidden lg:flex items-center gap-1">
              {students.slice(0, 4).map((s) => {
                const isSelected = selectedStudentId === s.user_id;
                const roleIcon = s.target_role.includes('AI') ? '🤖' : s.target_role.includes('Cloud') ? '☁️' : s.target_role.includes('EV') ? '⚡' : '📊';
                return (
                  <button
                    key={s.user_id}
                    onClick={() => setSelectedStudentId(s.user_id)}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all cursor-pointer flex items-center gap-1 ${
                      isSelected
                        ? 'bg-teal-600 text-white shadow-2xs ring-1 ring-teal-500'
                        : 'bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-800'
                    }`}
                  >
                    <span>{roleIcon}</span>
                    <span>{s.name.split(' ')[0]}</span>
                  </button>
                );
              })}
            </div>
            {user?.role === 'STUDENT' && selectedStudentId === 'me' && (
              <Link
                to="/student/profile"
                className="px-3 py-1.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold shadow-xs flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <span>⚙️</span>
                <span>Edit Skill Passport</span>
              </Link>
            )}
          </div>
        )}
      </div>

             {/* Top Main Section Switcher Tabs */}
      <div className="flex items-center gap-2 mb-6 border-b border-slate-200 dark:border-slate-800 pb-3 flex-wrap">
        <button
          onClick={() => handleTabChange('passport')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center gap-2 ${
            mainTab === 'passport'
              ? 'bg-slate-900 dark:bg-teal-700 text-white shadow-xs'
              : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800'
          }`}
        >
          <span>🎓</span>
          <span>Skill Passport</span>
          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300">
            Radar
          </span>
        </button>

        <button
          onClick={() => handleTabChange('assessment')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center gap-2 ${
            mainTab === 'assessment'
              ? 'bg-slate-900 dark:bg-teal-700 text-white shadow-xs'
              : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800'
          }`}
        >
          <span>📝</span>
          <span>Diagnostic Assessment</span>
          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300">
            Quiz
          </span>
        </button>

        <button
          onClick={() => handleTabChange('recommendations')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center gap-2 ${
            mainTab === 'recommendations'
              ? 'bg-slate-900 dark:bg-teal-700 text-white shadow-xs'
              : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800'
          }`}
        >
          <span>🎯</span>
          <span>Career Recommendations</span>
          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-indigo-100 dark:bg-indigo-950 text-indigo-800 dark:text-indigo-300">
            Job Match
          </span>
        </button>

        <button
          onClick={() => handleTabChange('roadmap')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center gap-2 ${
            mainTab === 'roadmap'
              ? 'bg-slate-900 dark:bg-teal-700 text-white shadow-xs'
              : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800'
          }`}
        >
          <span>🗺️</span>
          <span>Learning Roadmap</span>
          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300">
            NSQF
          </span>
        </button>

        <button
          onClick={() => handleTabChange('signals')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center gap-2 ${
            mainTab === 'signals'
              ? 'bg-slate-900 dark:bg-teal-700 text-white shadow-xs'
              : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800'
          }`}
        >
          <span>📡</span>
          <span>Industry & Tech Alerts</span>
          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-purple-100 dark:bg-purple-950 text-purple-800 dark:text-purple-300">
            Alerts Feed
          </span>
        </button>
      </div>

      {/* VIEW 1: DYNAMIC SKILL PASSPORT & COMPETENCIES */}
      {mainTab === 'passport' && (
        <div data-demo="student-passport-section" className="space-y-8 animate-fadeIn">
          {/* Global Error Banner */}
          {passportError && (
            <ErrorBanner
              message={`Failed to retrieve skill passport data for candidate (${passportError}).`}
              onRetry={fetchStudentData}
            />
          )}

          {/* Dynamic Alignment Workflow Banner */}
          <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 dark:from-slate-900 dark:via-teal-950/40 dark:to-slate-900 border border-slate-800 rounded-xl p-4 sm:p-5 text-white flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-sm">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 text-[11px] text-teal-400 font-semibold uppercase tracking-wider font-mono">
                <span>Career Pathway Sequence</span>
                <span>•</span>
                {passport?.has_assessment === false ? (
                  <span className="px-2 py-0.5 rounded bg-amber-900/80 border border-amber-500 text-amber-300 text-[10px] font-bold">
                    ⚠️ Unassessed Candidate Profile
                  </span>
                ) : passport?.source === 'USER_SUBMITTED' || passport?.is_personalized ? (
                  <span className="px-2 py-0.5 rounded bg-emerald-900/80 border border-emerald-500 text-emerald-300 text-[10px] font-bold">
                    🟢 Live Personalized Data
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded bg-blue-900/80 border border-blue-500 text-blue-300 text-[10px] font-bold">
                    🔵 Demo Baseline Preview
                  </span>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 text-xs font-medium">
                <span className="bg-slate-800/90 border border-slate-700 px-2.5 py-1 rounded text-slate-200">
                  1. Current Competencies
                </span>
                <span className="text-teal-400 font-bold">→</span>
                <span className="bg-rose-950/80 border border-rose-800 px-2.5 py-1 rounded text-rose-300">
                  2. Priority Skill Gaps
                </span>
                <span className="text-teal-400 font-bold">→</span>
                <span className="bg-teal-950/80 border border-teal-800 px-2.5 py-1 rounded text-teal-300">
                  3. Recommended Pathway
                </span>
                <span className="text-teal-400 font-bold">→</span>
                <span className="bg-emerald-950/80 border border-emerald-800 px-2.5 py-1 rounded text-emerald-300">
                  4. Industry Placement
                </span>
              </div>
            </div>


            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => handleTabChange('assessment')}
                className="px-3.5 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white text-xs font-bold rounded-lg shadow-xs transition-all cursor-pointer flex items-center gap-1.5"
              >
                <span>Take Diagnostic Quiz</span>
                <span>📝</span>
              </button>
              <Link
                to="/copilot?role=student"
                className="px-3.5 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-lg shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
              >
                <span>Consult Copilot</span>
                <span>→</span>
              </Link>
            </div>
          </div>

          {/* Unassessed Candidate Onboarding State (PROJECT_SPEC Requirement 2) */}
          {selectedStudentId === 'me' && passport?.has_assessment === false && (
            <div className="bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl p-6 text-center my-4 space-y-3">
              <div className="text-3xl">📝</div>
              <h3 className="text-lg font-bold text-amber-900 dark:text-amber-200">
                No Personalized Assessment Completed Yet
              </h3>
              <p className="text-xs text-amber-700 dark:text-amber-300 max-w-lg mx-auto leading-relaxed">
                You are viewing your personal candidate profile. Take the quick 3-minute diagnostic assessment to generate your Skill Passport, radar benchmarks, and personalized learning roadmap.
              </p>
              <div className="flex items-center justify-center gap-3 pt-2">
                <button
                  onClick={() => handleTabChange('assessment')}
                  className="px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs rounded-lg shadow-sm transition-all cursor-pointer"
                >
                  Start Diagnostic Assessment Now →
                </button>
                {students.some((s) => s.user_id === 'stu-001') && (
                  <button
                    onClick={() => setSelectedStudentId('stu-001')}
                    className="px-4 py-2.5 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-semibold text-xs rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-all cursor-pointer"
                  >
                    Preview Demo Student (Aarav Patil)
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Top KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            {loading ? (
              <>
                <SkeletonKpiCard />
                <SkeletonKpiCard />
                <SkeletonKpiCard />
                <SkeletonKpiCard />
              </>
            ) : (
              <>
                <StatCard
                  title="Candidate Profile"
                  value={passport?.name || (user?.full_name || 'My Profile')}
                  subtitle={`ID: ${selectedStudentId}`}
                  icon="🎓"
                />
                <StatCard
                  title="Target Career Role"
                  value={passport?.has_assessment === false ? 'Pending Assessment' : (passport?.target_role || 'AI Engineer')}
                  subtitle={passport?.has_assessment === false ? 'Complete diagnostic to set' : 'Industry benchmark target'}
                  icon="🎯"
                  color="teal"
                />
                <StatCard
                  title="Competency Match"
                  value={`${passport?.skill_match_pct || 0}%`}
                  subtitle="Match vs target requirements"
                  icon="📊"
                  color={
                    (passport?.skill_match_pct || 0) >= 70
                      ? 'teal'
                      : (passport?.skill_match_pct || 0) >= 40
                      ? 'amber'
                      : 'rose'
                  }
                />
                <StatCard
                  title="Critical Skill Gaps"
                  value={passport?.has_assessment === false ? 'Diagnostic Needed' : `${passport?.missing_skills?.length || 0} Skills`}
                  subtitle={passport?.has_assessment === false ? 'Take 3-min quiz' : 'Prerequisites to bridge'}
                  icon="⚡"
                  color="rose"
                />
              </>
            )}
          </div>

          {/* Grid: Skill Passport Radar & Competency Comparison */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left: Competency Benchmark Radar (5 cols on lg) */}
            <div data-demo="student-passport-radar" className="lg:col-span-5 bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100 dark:border-slate-800">
                  <div>
                    <h3 className="font-bold text-slate-900 dark:text-white text-base">
                      Competency Benchmark Radar
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Candidate mastery vs 100% employer benchmark
                    </p>
                  </div>
                  <span className="text-[11px] font-mono px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold rounded border border-slate-200 dark:border-slate-700">
                    Competency Standards
                  </span>
                </div>

                {loading ? (
                  <div className="h-72 flex items-center justify-center animate-pulse">
                    <div className="w-48 h-48 rounded-full border-4 border-dashed border-slate-200 dark:border-slate-800"></div>
                  </div>
                ) : (
                  <PassportRadar
                    currentSkills={passport?.current_skills}
                    requiredSkills={passport?.required_skills}
                    className="h-72"
                  />
                )}
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-teal-500"></span> Candidate Mastery
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-slate-400 border border-slate-600"></span> Target Role Benchmark
                </span>
              </div>
            </div>

            {/* Right: Detailed Competencies vs Skill Gaps Breakdown (7 cols on lg) */}
            <div data-demo="skill-explainability-trigger" className="lg:col-span-7 bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col justify-between">
              <div>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-2 border-b border-slate-100 dark:border-slate-800">
                  <div>
                    <h3 className="font-bold text-slate-900 dark:text-white text-base">
                      Verified Competencies vs. Skill Gaps
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Comparing candidate baseline against <strong>{passport?.target_role || 'Target Role'}</strong>
                    </p>
                  </div>

                  {/* Filter Sub-Tabs */}
                  <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg self-start sm:self-auto text-xs">
                    <button
                      onClick={() => setFilterTab('all')}
                      className={`px-2.5 py-1 rounded font-semibold transition-colors cursor-pointer ${
                        filterTab === 'all'
                          ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-2xs'
                          : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                      }`}
                    >
                      All ({comparisonData.items.length})
                    </button>
                    <button
                      onClick={() => setFilterTab('acquired')}
                      className={`px-2.5 py-1 rounded font-semibold transition-colors cursor-pointer ${
                        filterTab === 'acquired'
                          ? 'bg-white dark:bg-slate-700 text-teal-700 dark:text-teal-300 shadow-2xs'
                          : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                      }`}
                    >
                      Verified ({comparisonData.acquired.length})
                    </button>
                    <button
                      onClick={() => setFilterTab('gaps')}
                      className={`px-2.5 py-1 rounded font-semibold transition-colors cursor-pointer ${
                        filterTab === 'gaps'
                          ? 'bg-white dark:bg-slate-700 text-rose-700 dark:text-rose-300 shadow-2xs'
                          : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                      }`}
                    >
                      Gaps ({comparisonData.gaps.length})
                    </button>
                  </div>
                </div>

                {loading ? (
                  <div className="space-y-3">
                    <div className="h-12 bg-slate-100 dark:bg-slate-800/60 rounded-lg animate-pulse"></div>
                    <div className="h-12 bg-slate-100 dark:bg-slate-800/60 rounded-lg animate-pulse"></div>
                    <div className="h-12 bg-slate-100 dark:bg-slate-800/60 rounded-lg animate-pulse"></div>
                  </div>
                ) : filteredItems.length === 0 ? (
                  <EmptyState
                    title="No skills found for this filter"
                    message="Switch filter tabs above to view acquired skills or pending requirements."
                  />
                ) : (
                  <div className="space-y-2.5 max-h-[360px] overflow-y-auto pr-1">
                    {filteredItems.map((item) => (
                      <div
                        key={item.skill_id}
                        className={`p-3 rounded-lg border flex items-center justify-between gap-3 text-xs transition-colors ${
                          item.isAcquired
                            ? 'bg-teal-50/40 dark:bg-teal-950/20 border-teal-100 dark:border-teal-900/50'
                            : 'bg-rose-50/40 dark:bg-rose-950/20 border-rose-100 dark:border-rose-900/50'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <span
                            className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                              item.isAcquired
                                ? 'bg-teal-100 dark:bg-teal-900 text-teal-800 dark:text-teal-200'
                                : 'bg-rose-100 dark:bg-rose-900 text-rose-800 dark:text-rose-200'
                            }`}
                          >
                            {item.isAcquired ? '✓' : '!'}
                          </span>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-slate-900 dark:text-white">
                                {item.skill_name}
                              </span>
                              {item.category && (
                                <span className="px-1.5 py-0.2 rounded text-[10px] bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
                                  {item.category}
                                </span>
                              )}
                            </div>
                            <span className="text-[11px] text-slate-500 dark:text-slate-400">
                              {item.isAcquired
                                ? `Acquired: ${item.proficiency} (${item.profScore}%)`
                                : 'Prerequisite Missing / Unassessed'}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            onClick={() => handleOpenExplainability(item.skill_id, item.skill_name)}
                            className="text-xs font-semibold text-teal-700 dark:text-teal-400 hover:underline cursor-pointer flex items-center gap-1"
                            title="Why Should I Learn This? 5D Evidence Breakdown"
                          >
                            <span>Why?</span>
                            <span className="text-[10px] font-mono px-1 bg-teal-100 dark:bg-teal-950 rounded">ⓘ</span>
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="mt-6 pt-3 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  Ready to bridge these competency deficits?
                </span>
                <button
                  onClick={() => handleTabChange('roadmap')}
                  className="px-3.5 py-1.5 bg-slate-900 dark:bg-teal-600 text-white text-xs font-bold rounded-lg hover:bg-slate-800 dark:hover:bg-teal-700 transition-colors shadow-2xs cursor-pointer"
                >
                  View Learning Roadmap →
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* VIEW 2: PHASE 12 DIAGNOSTIC ASSESSMENT & QUIZ */}
      {mainTab === 'assessment' && (
        <div data-demo="student-assessment-section" className="animate-fadeIn">
          <StudentAssessmentForm
            onOpenExplainability={handleOpenExplainability}
            onAssessmentSubmitted={(newAssessment) => {
              api.getMyPassport().then((myPass) => {
                if (myPass) {
                  setPassport(myPass);
                  setSelectedStudentId('me');
                }
              }).catch(() => {});
              api.getStudents().then((res) => {
                const studentList = Array.isArray(res) ? res : [];
                setStudents((prev) => {
                  const hasMe = prev.some((s) => s.user_id === 'me');
                  const meItem = prev.find((s) => s.user_id === 'me');
                  if (studentList.length > 0) {
                    return hasMe ? [meItem, ...studentList.filter((r) => r.user_id !== 'me')] : studentList;
                  }
                  return hasMe ? [meItem] : [];
                });
              });
              setSelectedStudentId('me');
              fetchStudentData();
            }}
          />

        </div>
      )}


      {/* VIEW 3: PHASE 16 CAREER RECOMMENDATIONS */}
      {mainTab === 'recommendations' && (
        <div data-demo="career-recommendations-section" className="animate-fadeIn">
          <CareerRecommendationsView
            studentId={selectedStudentId}
            onOpenExplainability={handleOpenExplainability}
          />
        </div>
      )}

      {/* VIEW 4: SEQUENTIAL LEARNING ROADMAP */}
      {mainTab === 'roadmap' && (
        <div data-demo="student-roadmap-section" className="space-y-8 animate-fadeIn">
          {/* Guided Career & Skill Roadmap */}
          <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5 pb-3 border-b border-slate-100 dark:border-slate-800">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-slate-900 dark:text-white text-lg">
                    Evidence-Based Career & Learning Roadmap
                  </h3>
                  <span className="text-xs font-bold px-2.5 py-0.5 bg-teal-50 dark:bg-teal-950 text-teal-800 dark:text-teal-300 rounded-full border border-teal-200 dark:border-teal-800">
                    Labour-Market Validated
                  </span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  Prioritized sequential pathway to bridge competency deficits and achieve full eligibility for{' '}
                  <strong>{passport?.target_role || 'Target Role'}</strong>
                </p>
              </div>

              <div className="flex items-center gap-3 self-start sm:self-auto">
                <div className="text-xs font-mono text-slate-500 dark:text-slate-400">
                  Target Horizon: 2025–2027
                </div>
                <button
                  onClick={handleRecalculateRoadmap}
                  disabled={recalculatingRoadmap}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800 hover:bg-teal-100 dark:hover:bg-teal-900 transition-colors disabled:opacity-50 cursor-pointer"
                >
                  <svg className={`w-3.5 h-3.5 ${recalculatingRoadmap ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  <span>{recalculatingRoadmap ? 'Recalculating...' : 'Recalculate Roadmap'}</span>
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 mb-6 text-xs">
              <div className="p-2.5 rounded-lg bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900/60">
                <span className="text-[10px] font-bold text-emerald-800 dark:text-emerald-300 uppercase font-mono block">
                  Stage 1 • Baseline
                </span>
                <p className="font-semibold text-slate-900 dark:text-white text-[11px] mt-0.5">
                  {roadmap?.summary?.skipped ?? comparisonData.acquired.length} Mastered (Skip)
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-rose-50/70 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/60">
                <span className="text-[10px] font-bold text-rose-800 dark:text-rose-300 uppercase font-mono block">
                  Stage 2 • Core Gaps
                </span>
                <p className="font-semibold text-slate-900 dark:text-white text-[11px] mt-0.5">
                  {roadmap?.summary?.to_learn ?? comparisonData.gaps.length} Target Deficits
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-teal-50/70 dark:bg-teal-950/30 border border-teal-200 dark:border-teal-900/60">
                <span className="text-[10px] font-bold text-teal-800 dark:text-teal-300 uppercase font-mono block">
                  Stage 3 • Learning Track
                </span>
                <p className="font-semibold text-slate-900 dark:text-white text-[11px] mt-0.5">
                  {roadmap?.roadmap?.length || 0} Modules ({roadmap?.total_estimated_hours || 0}h)
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700">
                <span className="text-[10px] font-bold text-slate-700 dark:text-slate-300 uppercase font-mono block">
                  Stage 4 • Job Readiness
                </span>
                <p className="font-semibold text-slate-900 dark:text-white text-[11px] mt-0.5">
                  {roadmap?.readiness_score ?? comparisonData?.overall_match_pct ?? 0}% Role Qualified
                </p>
              </div>
            </div>

            {/* Roadmap Steps */}
            {roadmapError ? (
              <ErrorBanner
                message={`Failed to retrieve recommended roadmap (${roadmapError}).`}
                onRetry={fetchStudentData}
              />
            ) : loading ? (
              <div className="space-y-3">
                <SkeletonRoadmapStep />
                <SkeletonRoadmapStep />
                <SkeletonRoadmapStep />
              </div>
            ) : roadmap?.roadmap && roadmap.roadmap.length > 0 ? (
              <div data-demo="student-roadmap-list" className="space-y-3.5">
                {roadmap.roadmap.map((step, idx) => (
                  <div
                    key={step.skill_id || idx}
                    className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 hover:border-teal-300 dark:hover:border-teal-600 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-2xs"
                  >
                    <div className="flex items-start gap-3.5 w-full sm:w-3/4">
                      <div className="w-8 h-8 rounded-lg bg-slate-900 dark:bg-teal-600 text-white font-bold text-sm flex items-center justify-center shrink-0 shadow-2xs">
                        {step.step || idx + 1}
                      </div>
                      <div className="space-y-1.5 w-full">
                        <div className="flex flex-wrap items-center gap-2">
                          <h4 className="font-bold text-slate-900 dark:text-white text-sm">
                            {step.skill_name}
                          </h4>
                          {step.status === 'SKIP' && (
                            <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-bold uppercase border border-emerald-300 dark:border-emerald-800 font-mono">
                              Mastered • Skip
                            </span>
                          )}
                          {step.status === 'REVIEW' && (
                            <span className="px-2 py-0.5 rounded text-[10px] bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 font-bold uppercase border border-amber-300 dark:border-amber-800 font-mono">
                              Refresher • Review
                            </span>
                          )}
                          {step.status === 'LEARN' && (
                            <span className="px-2 py-0.5 rounded text-[10px] bg-indigo-100 dark:bg-indigo-950 text-indigo-800 dark:text-indigo-300 font-bold uppercase border border-indigo-300 dark:border-indigo-800 font-mono">
                              Core Target • Learn
                            </span>
                          )}
                          {step.status === 'PROJECT' && (
                            <span className="px-2 py-0.5 rounded text-[10px] bg-purple-100 dark:bg-purple-950 text-purple-800 dark:text-purple-300 font-bold uppercase border border-purple-300 dark:border-purple-800 font-mono">
                              Capstone Project
                            </span>
                          )}
                          {step.category && (
                            <span className="px-2 py-0.5 rounded text-[10px] bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 font-medium">
                              {step.category}
                            </span>
                          )}
                          {step.nsqf_level && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-mono">
                              NSQF L{step.nsqf_level}
                            </span>
                          )}
                          {step.estimated_hours > 0 && (
                            <span className="text-[10px] text-slate-500 dark:text-slate-400 font-mono">
                              • ~{step.estimated_hours}h
                            </span>
                          )}
                          <span className="px-2 py-0.5 rounded text-[10px] bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300 font-semibold uppercase border border-teal-200 dark:border-teal-800 font-mono">
                            Trend: {step.trend || 'rising'}
                          </span>
                        </div>
                        {step.prerequisites && step.prerequisites.length > 0 && (
                          <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono flex items-center gap-1">
                            <span className="text-slate-400 dark:text-slate-500">Prerequisites:</span>
                            <span className="text-teal-700 dark:text-teal-300 font-semibold">{step.prerequisites.join(' → ')}</span>
                          </div>
                        )}
                        <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                          <button
                            onClick={() => handleOpenExplainability(step.skill_id, step.skill_name)}
                            className="text-teal-800 dark:text-teal-300 font-bold hover:underline cursor-pointer inline-flex items-center gap-1 mr-1"
                            title="Click to open 5-dimension grounded explainability breakdown"
                          >
                            <span>Why learn this?</span>
                            <span className="text-[9px] font-mono px-1 py-0.2 bg-teal-100 dark:bg-teal-900 rounded">5D Evidence ⓘ</span>
                          </button>{' '}
                          {step.why}
                        </p>
                        {step.deliverables && step.deliverables.length > 0 && (
                          <div className="mt-2 p-2.5 rounded-lg bg-purple-50/70 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-900/60 text-xs">
                            <span className="font-bold text-purple-900 dark:text-purple-200 block mb-1">Key Portfolio Deliverables:</span>
                            <ul className="list-disc list-inside space-y-0.5 text-purple-800 dark:text-purple-300 font-mono text-[11px]">
                              {step.deliverables.map((d, dIdx) => (
                                <li key={dIdx}>{d}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="shrink-0 self-end sm:flex-row sm:items-center flex items-center gap-2">
                      <button
                        onClick={() => handleOpenExplainability(step.skill_id, step.skill_name)}
                        className="text-xs font-bold text-teal-700 dark:text-teal-300 hover:text-teal-900 dark:hover:text-teal-100 bg-teal-50 dark:bg-teal-950/60 px-3 py-2 rounded-lg border border-teal-200 dark:border-teal-800 shadow-2xs hover:bg-teal-100 dark:hover:bg-teal-900 transition-colors inline-block cursor-pointer"
                      >
                        Explain Demand ⓘ
                      </button>
                      <Link
                        to="/copilot?role=student"
                        className="text-xs font-bold text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-slate-100 bg-white dark:bg-slate-800 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 shadow-2xs hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors inline-block cursor-pointer"
                      >
                        Curriculum Advice →
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No Curriculum Roadmap Steps Available"
                message={`All core prerequisites for ${passport?.target_role || 'this role'} appear to be satisfied, or the curriculum pathway is being updated.`}
                action={
                  <Link
                    to="/copilot?role=student"
                    className="inline-block px-4 py-1.5 bg-teal-600 text-white rounded-lg text-xs font-bold hover:bg-teal-700 transition-colors"
                  >
                    Ask Career Copilot
                  </Link>
                }
              />
            )}
          </div>

          {/* State Welfare Schemes — Personalized */}
          <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100 dark:border-slate-800">
                <div>
                  <h3 className="font-bold text-slate-900 dark:text-white text-base">
                    Recommended Welfare & Scholarship Schemes
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Matched to your profile — verify eligibility on official portals
                  </p>
                </div>
                <span className="text-[10px] font-mono font-semibold px-2 py-0.5 bg-teal-50 dark:bg-teal-950 text-teal-800 dark:text-teal-300 rounded border border-teal-200 dark:border-teal-800">
                  MahaDBT / OGD
                </span>
              </div>

              {schemes.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {schemes.map((s) => (
                    <div
                      key={s.id}
                      className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700/80 hover:border-teal-300 dark:hover:border-teal-600 transition-colors flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <h4 className="font-bold text-slate-900 dark:text-white text-xs leading-snug">
                            {s.title}
                          </h4>
                          {s.max_amount > 0 && (
                            <span className="text-[11px] font-mono font-bold text-teal-700 dark:text-teal-400 shrink-0">
                              ₹{s.max_amount.toLocaleString('en-IN')}
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-600 dark:text-slate-300 line-clamp-2 mb-2">
                          {s.benefit_description}
                        </p>
                        {/* Match Reasons (Phase 15) */}
                        {s.match_reasons && s.match_reasons.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-2">
                            {s.match_reasons.map((reason, idx) => (
                              <span key={idx} className="text-[9px] px-1.5 py-0.5 rounded bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800 font-medium">
                                ✓ {reason}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 pt-2 border-t border-slate-200/60 dark:border-slate-700/60">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-300">
                            {s.scheme_type?.replace('_', ' ')}
                          </span>
                        </div>
                        {s.application_portal_url && (
                          <a
                            href={s.application_portal_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-teal-600 dark:text-teal-400 font-bold hover:underline"
                          >
                            View on Portal →
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : schemesLoading ? (
                <div className="py-8 text-center text-slate-400">
                  <div className="w-6 h-6 border-2 border-teal-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                  <p className="text-xs">Loading welfare schemes...</p>
                </div>
              ) : schemesError ? (
                <div className="py-4 text-center text-rose-500 text-xs">
                  <p>{schemesError}</p>
                  <button onClick={loadSchemesAndOpps} className="mt-2 px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded font-bold">Retry</button>
                </div>
              ) : (
                <p className="text-xs text-slate-500 py-4 text-center">No matching welfare schemes found for this profile.</p>
              )}


            </div>
          </div>
        </div>
      )}

      {/* VIEW 5: INDUSTRY ALERTS & GOVERNMENT OPPORTUNITIES */}
      {mainTab === 'signals' && (
        <div data-demo="student-signals-section" className="space-y-8 animate-fadeIn">
          {/* Section 19: Personalized Industry & Technology Alerts Feed */}
          <div data-demo="student-industry-alerts">
            <StudentAlertsFeed
              studentId={selectedStudentId}
              onOpenExplainability={handleOpenExplainability}
            />
          </div>

          {/* Government Opportunities — Personalized (Phase 15) */}
          <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100 dark:border-slate-800">
                <div>
                  <h3 className="font-bold text-slate-900 dark:text-white text-base">
                    Recommended Apprenticeships & Training Programs
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Government opportunities matched to your skills & district
                  </p>
                </div>
                <span className="text-[10px] font-mono font-semibold px-2 py-0.5 bg-blue-50 dark:bg-blue-950 text-blue-800 dark:text-blue-300 rounded border border-blue-200 dark:border-blue-800">
                  NAPS / DVET / MSSDS
                </span>
              </div>

              {opportunities.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {opportunities.map((opp) => (
                    <div
                      key={opp.id}
                      className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700/80 hover:border-blue-300 dark:hover:border-blue-600 transition-colors flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <div>
                            <h4 className="font-bold text-slate-900 dark:text-white text-xs leading-snug">
                              {opp.name || opp.title}
                            </h4>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400">
                              {opp.department || opp.company} • <span className="font-semibold text-slate-700 dark:text-slate-300">
                                {typeof opp.district_coverage === 'object' ? (opp.district_coverage || []).join(', ') : (opp.district_coverage || opp.district || '')}
                              </span>
                            </p>
                          </div>
                          <span className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 uppercase text-[9px] font-mono font-semibold shrink-0">
                            {(opp.opportunity_type || 'opportunity').replace('_', ' ')}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-600 dark:text-slate-300 line-clamp-2 mb-2">
                          {opp.description || ''}
                        </p>
                        {/* Match Reasons (Phase 15) */}
                        {opp.match_reasons && opp.match_reasons.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-2">
                            {opp.match_reasons.map((reason, idx) => (
                              <span key={idx} className="text-[9px] px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300 border border-blue-200 dark:border-blue-800 font-medium">
                                ✓ {reason}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 pt-2 mt-1 border-t border-slate-200/60 dark:border-slate-700/60">
                        <div className="flex items-center gap-2">
                          <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
                            {opp.source || 'DEMO_SYNTHETIC'}
                          </span>
                        </div>
                        {(opp.application_url || opp.apply_url) && (
                          <a
                            href={opp.application_url || opp.apply_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 dark:text-blue-400 font-bold hover:underline"
                          >
                            View & Apply →
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : oppsLoading ? (
                <div className="py-8 text-center text-slate-400">
                  <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                  <p className="text-xs">Loading opportunities...</p>
                </div>
              ) : oppsError ? (
                <div className="py-4 text-center text-rose-500 text-xs">
                  <p>{oppsError}</p>
                  <button onClick={loadSchemesAndOpps} className="mt-2 px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded font-bold">Retry</button>
                </div>
              ) : (
                <p className="text-xs text-slate-500 py-4 text-center">No matching government opportunities found for this profile.</p>
              )}


            </div>
          </div>
        </div>
      )}

      {/* Section 18: "Why Should I Learn This?" 5-Dimension Explainability Modal */}
      <SkillExplainabilityModal
        isOpen={explainModalOpen}
        onClose={() => setExplainModalOpen(false)}
        skillQuery={selectedExplainSkill}
        studentId={selectedStudentId}
        skillNameFallback={selectedExplainSkillName}
      />
    </Layout>
  );
}

