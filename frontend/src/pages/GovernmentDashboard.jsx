import React, { useState, useEffect, useCallback, useMemo, Component } from 'react';
import { Link } from 'react-router-dom';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import Layout from '../components/Layout';
import StatCard from '../components/StatCard';
import MaharashtraMap from '../components/MaharashtraMap';
import SkillGapBar from '../components/SkillGapBar';
import SignalCard from '../components/SignalCard';
import RecommendationCard from '../components/RecommendationCard';
import { api } from '../services/api';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';

class SectionErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error(`[SectionErrorBoundary:${this.props.name || 'Unknown'}]`, error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 rounded-xl border border-amber-200 dark:border-amber-900/60 bg-amber-50/40 dark:bg-amber-950/20 text-amber-900 dark:text-amber-200 my-4">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-base">⚠️</span>
            <h4 className="text-xs font-bold uppercase tracking-wider">
              {this.props.name || 'Dashboard Section'} Temporarily Unavailable
            </h4>
          </div>
          <p className="text-[11px] text-amber-700/90 dark:text-amber-400">
            This module encountered a rendering error and recovered gracefully. Other dashboard modules remain fully functional.
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="mt-3 px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded text-xs font-semibold shadow-2xs transition-colors cursor-pointer"
          >
            Retry Section
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function SectionHeader({
  title,
  subtitle,
  decisionNote,
  badge,
  badgeColor = 'slate',
}) {
  const colors = {
    slate: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700',
    rose: 'bg-rose-50 dark:bg-rose-950/70 text-rose-800 dark:text-rose-300 border-rose-200 dark:border-rose-800',
    teal: 'bg-teal-50 dark:bg-teal-950/70 text-teal-800 dark:text-teal-300 border-teal-200 dark:border-teal-800',
    amber: 'bg-amber-50 dark:bg-amber-950/70 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800',
  };

  return (
    <div className="mb-4 pb-3 border-b border-slate-100 dark:border-slate-800">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5">
        <div className="flex items-center gap-2 flex-wrap">
          <h3 className="font-bold text-slate-900 dark:text-white text-base tracking-tight">{title}</h3>
          {badge && (
            <span className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded border ${colors[badgeColor] || colors.slate}`}>
              {badge}
            </span>
          )}
        </div>
      </div>
      {subtitle && (
        <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 leading-relaxed">
          {subtitle}
        </p>
      )}
      {decisionNote && (
        <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-teal-700 dark:text-teal-400 font-medium">
          <span className="font-semibold uppercase tracking-wider text-[10px]">Decision Impact:</span>
          <span>{decisionNote}</span>
        </div>
      )}
    </div>
  );
}

function EmptyState({
  title = 'No records available',
  message = 'No data points were returned for this section.',
  icon,
}) {
  return (
    <div className="py-10 px-4 text-center rounded-xl border border-dashed border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30">
      <div className="w-9 h-9 mx-auto mb-2 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400 dark:text-slate-500">
        {icon || (
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
        )}
      </div>
      <h4 className="text-xs font-bold text-slate-700 dark:text-slate-300">{title}</h4>
      <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 max-w-sm mx-auto">{message}</p>
    </div>
  );
}

function ErrorState({
  title = 'Data Service Unavailable',
  message = 'Unable to retrieve telemetry from the backend service.',
  onRetry,
}) {
  return (
    <div className="py-8 px-4 text-center rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/40 dark:bg-rose-950/20 text-rose-800 dark:text-rose-300">
      <div className="w-8 h-8 mx-auto mb-2 rounded-full bg-rose-100 dark:bg-rose-900/50 flex items-center justify-center text-rose-600 dark:text-rose-400">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </div>
      <h4 className="text-xs font-bold">{title}</h4>
      <p className="text-[11px] text-rose-700/80 dark:text-rose-400 mt-0.5 max-w-sm mx-auto">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2.5 px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded text-xs font-semibold shadow-2xs transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}

function SkeletonKpiCard({ dominant = false }) {
  return (
    <div className={`p-4 sm:p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 animate-pulse ${dominant ? 'ring-2 ring-amber-500/20' : ''}`}>
      <div className="flex items-start justify-between">
        <div>
          <div className="h-3 w-28 bg-slate-200 dark:bg-slate-800 rounded mb-2.5"></div>
          <div className={`${dominant ? 'h-9 w-24' : 'h-8 w-20'} bg-slate-200 dark:bg-slate-800 rounded mb-2`}></div>
        </div>
        <div className="w-9 h-9 rounded-lg bg-slate-100 dark:bg-slate-800"></div>
      </div>
      <div className="h-3 w-36 bg-slate-100 dark:bg-slate-800/60 rounded mt-2"></div>
    </div>
  );
}

function SkeletonChart() {
  return (
    <div className="h-72 w-full flex flex-col justify-end gap-3 p-4 animate-pulse">
      <div className="h-5 w-4/5 bg-slate-100 dark:bg-slate-800/80 rounded"></div>
      <div className="h-5 w-3/5 bg-slate-100 dark:bg-slate-800/80 rounded"></div>
      <div className="h-5 w-5/6 bg-slate-100 dark:bg-slate-800/80 rounded"></div>
      <div className="h-5 w-2/3 bg-slate-100 dark:bg-slate-800/80 rounded"></div>
      <div className="h-5 w-3/4 bg-slate-100 dark:bg-slate-800/80 rounded"></div>
      <div className="h-5 w-1/2 bg-slate-100 dark:bg-slate-800/80 rounded"></div>
    </div>
  );
}

function SkeletonGaps() {
  return (
    <div className="space-y-4 py-2 animate-pulse">
      {[1, 2, 3].map((i) => (
        <div key={i} className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
          <div className="flex justify-between mb-2">
            <div className="h-3 w-32 bg-slate-200 dark:bg-slate-700 rounded"></div>
            <div className="h-3 w-16 bg-slate-200 dark:bg-slate-700 rounded"></div>
          </div>
          <div className="h-2 w-full bg-slate-200 dark:bg-slate-700 rounded"></div>
        </div>
      ))}
    </div>
  );
}

// Data Normalization Helpers
function extractArray(val, keys = []) {
  if (Array.isArray(val)) return val;
  if (val && typeof val === 'object') {
    for (const key of keys) {
      if (Array.isArray(val[key])) return val[key];
    }
  }
  return [];
}

export default function GovernmentDashboard() {
  const { user, role } = useAuth();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [selectedDistrict, setSelectedDistrict] = useState('Pune');
  const [jobsCount, setJobsCount] = useState(0);
  const [gaps, setGaps] = useState([]);
  const [signals, setSignals] = useState([]);
  const [forecasts, setForecasts] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [demandStats, setDemandStats] = useState([]);
  const [loading, setLoading] = useState(true);

  // Policy What-If Simulator state
  const [simScenario, setSimScenario] = useState('capacity_increase');
  const [simCategory, setSimCategory] = useState('');
  const [simDistrict, setSimDistrict] = useState('');
  const [simCapacityPct, setSimCapacityPct] = useState(30);
  const [simStaleYears, setSimStaleYears] = useState(2);
  const [simResult, setSimResult] = useState(null);
  const [simLoading, setSimLoading] = useState(false);
  const [simError, setSimError] = useState(null);
  const [simCategories, setSimCategories] = useState([]);

  // Load simulator categories on mount
  useEffect(() => {
    let mounted = true;
    api.getSimulatorCategories().then(res => {
      if (mounted && res && Array.isArray(res.categories)) {
        setSimCategories(res.categories);
      }
    }).catch(() => {});
    return () => { mounted = false; };
  }, []);

  const runSimulation = useCallback(() => {
    setSimLoading(true);
    setSimError(null);
    api.runSimulation({
      scenario_type: simScenario,
      skill_category: simCategory || null,
      district: simDistrict || null,
      capacity_change_pct: simCapacityPct,
      stale_years: simStaleYears,
    }).then(res => {
      setSimResult(res);
      setSimLoading(false);
    }).catch(err => {
      setSimError(err.message || 'Simulation failed');
      setSimLoading(false);
    });
  }, [simScenario, simCategory, simDistrict, simCapacityPct, simStaleYears]);

  const resetSimulation = () => {
    setSimResult(null);
    setSimError(null);
    setSimScenario('capacity_increase');
    setSimCategory('');
    setSimDistrict('');
    setSimCapacityPct(30);
    setSimStaleYears(2);
  };

  const [errors, setErrors] = useState({
    jobs: false,
    gaps: false,
    signals: false,
    forecasts: false,
    recommendations: false,
    demand: false,
  });

  const [platformMetrics, setPlatformMetrics] = useState(null);
  const [govOpportunities, setGovOpportunities] = useState([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);
  const [govForm, setGovForm] = useState({
    name: '',
    department: 'Skill Development, Employment & Entrepreneurship Dept',
    description: '',
    eligibility_criteria: 'Diploma, ITI, or Degree holders aged 18-28 resident in Maharashtra',
    target_skills: 'PLC Programming, Automation, EV Technology',
    district_coverage: 'Pune, Mumbai City, Aurangabad, Nagpur',
    opportunity_type: 'APPRENTICESHIP',
    application_url: 'https://mahaswayam.gov.in',
    deadline: '2026-12-31',
  });

  const handleGovSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    const name = govForm.name.trim();
    const description = govForm.description.trim();
    if (!name || !description) {
      setToastMessage({ type: 'error', text: 'Please provide both opportunity name and description.' });
      return;
    }
    let appUrl = govForm.application_url.trim();
    if (appUrl && !appUrl.startsWith('http://') && !appUrl.startsWith('https://')) {
      appUrl = `https://${appUrl}`;
    }
    setSubmitting(true);
    try {
      const skillsArray = govForm.target_skills.split(',').map((s) => s.trim()).filter(Boolean);
      const districtsArray = govForm.district_coverage.split(',').map((d) => d.trim()).filter(Boolean);
      const payload = {
        name,
        department: govForm.department.trim(),
        description,
        eligibility_criteria: govForm.eligibility_criteria.trim() || null,
        target_skills: skillsArray,
        district_coverage: districtsArray.length > 0 ? districtsArray : ['Maharashtra'],
        opportunity_type: govForm.opportunity_type,
        application_url: appUrl || 'https://mahaswayam.gov.in',
        deadline: govForm.deadline.trim() || null,
        status: 'active',
      };
      await api.submitGovOpportunity(payload);
      setToastMessage({ type: 'success', text: `Government Opportunity "${payload.name}" published successfully!` });
      setIsModalOpen(false);
      setGovForm((prev) => ({ ...prev, name: '', description: '' }));
      fetchData();
    } catch (err) {
      setToastMessage({ type: 'error', text: err.message || 'Failed to publish government opportunity.' });
    } finally {
      setSubmitting(false);
    }
  };

  const fetchData = () => {
    setLoading(true);
    setErrors({
      jobs: false,
      gaps: false,
      signals: false,
      forecasts: false,
      recommendations: false,
      demand: false,
    });

    Promise.allSettled([
      api.getJobs(),
      api.getGaps(),
      api.getSignals(),
      api.getForecasts(),
      api.getCourseRecommendations(),
      api.getJobDemand('skill'),
      api.getPlatformMetrics(),
      api.getGovOpportunities(),
    ]).then(([jobsRes, gapsRes, sigRes, fcRes, recRes, demRes, metRes, oppsRes]) => {
      if (jobsRes.status === 'fulfilled') {
        const jobsArr = extractArray(jobsRes.value, ['jobs', 'data']);
        if (jobsArr.length > 0) {
          setJobsCount(jobsArr.length);
        } else if (typeof jobsRes.value?.total === 'number') {
          setJobsCount(jobsRes.value.total);
        } else if (typeof jobsRes.value?.count === 'number') {
          setJobsCount(jobsRes.value.count);
        }
      } else if (jobsRes.status === 'rejected') {
        setErrors((prev) => ({ ...prev, jobs: true }));
      }

      if (gapsRes.status === 'fulfilled') {
        const gapsArr = extractArray(gapsRes.value, ['gaps', 'items', 'data']);
        const normalizedGaps = gapsArr.map((g, idx) => {
          const dPct = typeof g.demand_pct === 'number' ? g.demand_pct : (typeof g.demand === 'number' ? g.demand : 0);
          const cPct = typeof g.coverage_pct === 'number' ? g.coverage_pct : (typeof g.coverage === 'number' ? g.coverage : 0);
          return {
            skill_id: g.skill_id || `gap-${idx}`,
            skill_name: g.skill_name || g.name || 'Technical Competency',
            category: g.category || 'Engineering & Technology',
            demand_pct: dPct,
            coverage_pct: cPct,
            gap_pct: typeof g.gap_pct === 'number' ? g.gap_pct : Math.max(0, dPct - cPct),
            priority: (g.priority || 'HIGH').toUpperCase(),
            demand_count: typeof g.demand_count === 'number' ? g.demand_count : (typeof g.count === 'number' ? g.count : 0),
          };
        });
        setGaps(normalizedGaps);
      } else if (gapsRes.status === 'rejected') {
        setErrors((prev) => ({ ...prev, gaps: true }));
      }

      if (sigRes.status === 'fulfilled') {
        const sigArr = extractArray(sigRes.value, ['signals', 'data', 'items']);
        const normalizedSignals = sigArr.map((s, idx) => ({
          id: s.id || `sig-${idx}`,
          title: s.title || 'Market Signal',
          source: s.source || s.source_name || 'Market Signal Pipeline',
          signal_date: s.signal_date || s.collected_at || s.published_at || 'Recent',
          impact_level: (s.impact_level || 'medium').toLowerCase(),
          summary: s.summary || s.description || '',
          affected_skills: Array.isArray(s.affected_skills) ? s.affected_skills : (s.skills || []),
        }));
        setSignals(normalizedSignals.slice(0, 4));
      } else if (sigRes.status === 'rejected') {
        setErrors((prev) => ({ ...prev, signals: true }));
      }

      if (fcRes.status === 'fulfilled') {
        const fcArr = extractArray(fcRes.value, ['forecasts', 'data', 'items']);
        const normalizedForecasts = fcArr.map((f, idx) => ({
          id: f.id || `fc-${idx}`,
          skill_name: f.skill_name || f.name || 'Emerging Technology',
          period: f.period || '12M',
          future_demand: (f.future_demand || 'high_growth').replace('_', ' '),
          trend: (f.trend || 'rising').toLowerCase(),
          confidence: typeof f.confidence === 'number' ? f.confidence : (typeof f.confidence_pct === 'number' ? f.confidence_pct : 0),
        }));
        setForecasts(normalizedForecasts.slice(0, 6));
      } else if (fcRes.status === 'rejected') {
        setErrors((prev) => ({ ...prev, forecasts: true }));
      }

      if (recRes.status === 'fulfilled') {
        const recArr = extractArray(recRes.value, ['recommendations', 'data', 'items']);
        const normalizedRecs = recArr.map((r, idx) => ({
          id: r.id || `rec-${idx}`,
          recommendation: r.recommendation || r.title || 'Curriculum Recommendation',
          reason: r.reason || r.description || '',
          priority: r.priority || 'High',
          confidence: typeof r.confidence === 'number' ? r.confidence : 0,
          gap_pct: typeof r.gap_pct === 'number' ? r.gap_pct : 0,
          future_demand: r.future_demand || 'Rising',
          trend: r.trend || 'rising',
          related_signals: Array.isArray(r.related_signals) ? r.related_signals : (r.signals || []),
        }));
        setRecommendations(normalizedRecs.slice(0, 4));
      } else if (recRes.status === 'rejected') {
        setErrors((prev) => ({ ...prev, recommendations: true }));
      }

      if (demRes.status === 'fulfilled') {
        const demArr = extractArray(demRes.value, ['demand', 'skills', 'data', 'items']);
        const normalizedDemand = demArr.map((d, idx) => ({
          name: d.name || d.skill_name || d.skill || `Skill ${idx + 1}`,
          count: typeof d.count === 'number' ? d.count : (typeof d.vacancies === 'number' ? d.vacancies : 10),
        }));
        setDemandStats(normalizedDemand.slice(0, 8));
      } else if (demRes.status === 'rejected') {
        setErrors((prev) => ({ ...prev, demand: true }));
      }

      if (metRes.status === 'fulfilled' && metRes.value && (metRes.value.status === 'success' || metRes.value.placement_rate_pct !== undefined)) {
        setPlatformMetrics(metRes.value);
      }

      if (oppsRes && oppsRes.status === 'fulfilled') {
        const oppsArr = extractArray(oppsRes.value, ['opportunities', 'data', 'items']);
        setGovOpportunities(oppsArr);
      }

      setLoading(false);
    });
  };

  useEffect(() => {
    fetchData();
  }, []);

  const avgDeficit = Array.isArray(gaps) && gaps.length > 0
    ? `${Math.round(gaps.reduce((acc, g) => acc + (Number(g.gap_pct) || 0), 0) / gaps.length)}%`
    : 'No Data';

  const actionsCount = Array.isArray(recommendations) && recommendations.length > 0
    ? `${recommendations.length} Actions`
    : '0 Actions';

  const topEmerging = useMemo(() => {
    if (Array.isArray(forecasts) && forecasts.length > 0) {
      const top = forecasts[0];
      return {
        value: top.skill_name || 'AI & EV',
        subtitle: `↑ ${top.future_demand || 'Rising'} ${top.period || '24M'} projection`,
      };
    }
    if (Array.isArray(signals) && signals.length > 0) {
      const topSig = signals[0];
      return {
        value: topSig.title ? (topSig.title.length > 20 ? `${topSig.title.slice(0, 18)}…` : topSig.title) : 'Active Signal',
        subtitle: topSig.source || 'Industry Signal',
      };
    }
    return {
      value: 'No Data',
      subtitle: 'No authoritative projections available',
    };
  }, [forecasts, signals]);

  const userRole = (role || user?.role || '').toUpperCase();
  const canPublish = userRole === 'GOVERNMENT' || userRole === 'ADMIN';

  return (
    <Layout>
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
              Maharashtra Labour Market Intelligence Hub
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 bg-teal-50 dark:bg-teal-950 text-teal-800 dark:text-teal-300 font-semibold rounded border border-teal-200 dark:border-teal-800">
              State Policy Console
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-1">
            Labour market intelligence connecting employer vacancies, district training capacity, and curriculum modernization across Maharashtra
          </p>
        </div>

        <div className="flex items-center gap-2 self-start shrink-0 flex-wrap">
          {canPublish && (
            <button
              onClick={() => setIsModalOpen(true)}
              className="px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white text-sm font-semibold rounded-lg shadow-xs transition-all flex items-center gap-1.5 cursor-pointer"
            >
              <span>Publish Scheme / Opportunity</span>
              <span>🏛️</span>
            </button>
          )}
          <Link
            to="/curriculum"
            className="px-4 py-2 bg-slate-800 dark:bg-slate-700 hover:bg-slate-700 dark:hover:bg-slate-600 text-white text-sm font-semibold rounded-lg shadow-xs transition-colors flex items-center gap-1.5"
          >
            <span>📋</span>
            <span>Curriculum Intelligence</span>
          </Link>
          <Link
            to={`/government/district/${encodeURIComponent(selectedDistrict || 'Pune')}`}
            className="px-4 py-2 bg-slate-900 dark:bg-teal-600 hover:bg-slate-800 dark:hover:bg-teal-700 text-white text-sm font-semibold rounded-lg shadow-xs transition-colors flex items-center gap-1.5"
          >
            <span>Inspect {selectedDistrict || 'Pune'} Micro-Plan</span>
            <span>→</span>
          </Link>
        </div>
      </div>


      {/* Toast Notification */}
      {toastMessage && (
        <div
          className={`mb-6 p-4 rounded-xl text-xs font-bold border flex items-center justify-between gap-2 ${
            toastMessage.type === 'success'
              ? 'bg-emerald-50 dark:bg-emerald-950/60 border-emerald-300 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200'
              : 'bg-rose-50 dark:bg-rose-950/60 border-rose-300 dark:border-rose-800 text-rose-800 dark:text-rose-200'
          }`}
        >
          <span>{toastMessage.text}</span>
          <button
            onClick={() => setToastMessage(null)}
            className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 cursor-pointer font-bold text-sm px-2"
          >
            ×
          </button>
        </div>
      )}

      {/* KPI Cards — Dominant Hierarchy */}
      <SectionErrorBoundary name="State KPI Telemetry">
        <div data-demo="government-kpis" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {loading ? (
            <>
              <SkeletonKpiCard dominant={true} />
              <SkeletonKpiCard />
              <SkeletonKpiCard />
              <SkeletonKpiCard />
            </>
          ) : (
            <>
              {errors.gaps ? (
                <div className="p-4 sm:p-5 rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/30 dark:bg-rose-950/20 flex flex-col justify-center">
                  <ErrorState title="Deficit Unavailable" message="Failed to load skill deficit telemetry" onRetry={fetchData} />
                </div>
              ) : (
                <StatCard
                  title="Average Skill Deficit"
                  value={avgDeficit}
                  subtitle="Demand vs. ITI curriculum coverage"
                  icon="⚡"
                  color="amber"
                  dominant={true}
                  badge="Primary Policy Alert"
                  trend={!Array.isArray(gaps) || gaps.length === 0 ? undefined : 'up'}
                  trendLabel={!Array.isArray(gaps) || gaps.length === 0 ? undefined : '+4% YoY'}
                />
              )}
              {errors.jobs ? (
                <div className="p-4 sm:p-5 rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/30 dark:bg-rose-950/20 flex flex-col justify-center">
                  <ErrorState title="Demand Unavailable" message="Failed to load job demand telemetry" onRetry={fetchData} />
                </div>
              ) : (
                <StatCard
                  title="State Job Demand"
                  value={jobsCount > 0 ? `${jobsCount.toLocaleString()}+` : '0'}
                  subtitle="Indexed across industrial hubs"
                  icon="💼"
                  color="white"
                />
              )}
              {errors.recommendations ? (
                <div className="p-4 sm:p-5 rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/30 dark:bg-rose-950/20 flex flex-col justify-center">
                  <ErrorState title="Upgrades Unavailable" message="Failed to load recommendations" onRetry={fetchData} />
                </div>
              ) : (
                <StatCard
                  title="Curriculum Upgrades"
                  value={actionsCount}
                  subtitle="High priority syllabus revisions"
                  icon="📘"
                  color="rose"
                />
              )}
              {/* Supporting Metric 4 */}
              <StatCard
                title="Top Emerging Field"
                value={topEmerging.value}
                subtitle={topEmerging.subtitle}
                icon="🚀"
                color="teal"
              />
            </>
          )}
        </div>
      </SectionErrorBoundary>

      {/* District Map Explorer */}
      <SectionErrorBoundary name="District Workforce Map">
        <div data-demo="district-heatmap" className="mb-8">
          <MaharashtraMap
            selectedDistrict={selectedDistrict}
            onSelectDistrict={(name) => setSelectedDistrict(name)}
          />
        </div>
      </SectionErrorBoundary>

      {/* Grid: Skill Demand Bar Chart & Skill Gaps */}
      <SectionErrorBoundary name="Statewide Demand & Curriculum Deficits">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Left: Top In-Demand Skills Chart */}
          <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col justify-between">
            <div>
              <SectionHeader
                title="Statewide Employer Skill Demand"
                subtitle="Aggregated frequency of technical proficiencies parsed from active Maharashtra job listings."
                decisionNote="Guides state vocational seat intake expansion for high-growth sectors."
                badge="Active Job Postings"
              />

              {loading ? (
                <SkeletonChart />
              ) : errors.demand ? (
                <ErrorState
                  title="Failed to Load Skill Demand Analytics"
                  message="The job demand analytics service did not respond."
                  onRetry={fetchData}
                />
              ) : demandStats.length > 0 ? (
                <div className="h-72 w-full min-h-[280px]">
                  <ResponsiveContainer width="100%" height="100%" minHeight={280}>
                    <BarChart
                      data={demandStats}
                      layout="vertical"
                      margin={{ top: 5, right: 20, left: 40, bottom: 5 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        horizontal={false}
                        stroke={isDark ? '#1e293b' : '#f1f5f9'}
                      />
                      <XAxis
                        type="number"
                        tick={{ fontSize: 11, fill: isDark ? '#94a3b8' : '#64748b' }}
                      />
                      <YAxis
                        dataKey="name"
                        type="category"
                        tick={{ fontSize: 11, fill: isDark ? '#cbd5e1' : '#1e293b' }}
                        width={110}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: isDark ? '#020617' : '#0f172a',
                          borderColor: isDark ? '#1e293b' : '#334155',
                          borderRadius: '8px',
                          color: '#fff',
                          fontSize: '12px',
                        }}
                      />
                      <Bar
                        dataKey="count"
                        fill={isDark ? '#14b8a6' : '#0f172a'}
                        radius={[0, 4, 4, 0]}
                        name="Active Vacancies"
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyState
                  title="No Authoritative Demand Data Available"
                  message="Statewide employer skill demand requires active job listings. No vacancies are currently indexed."
                />
              )}
            </div>
          </div>

          {/* Right: Critical Skill Gaps */}
          <div data-demo="skill-gaps-table" className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col justify-between">
            <div>
              <SectionHeader
                title="Critical Curriculum Deficits"
                subtitle="High-demand technical skills with insufficient instructional coverage in current ITI trades."
                decisionNote="Directs emergency syllabus revision mandates for state curriculum boards."
                badge="Action Required"
                badgeColor="rose"
              />

              {loading ? (
                <SkeletonGaps />
              ) : errors.gaps ? (
                <ErrorState
                  title="Failed to Load Skill Gap Analytics"
                  message="The curriculum gap engine is currently unavailable."
                  onRetry={fetchData}
                />
              ) : gaps.length > 0 ? (
                <div className="space-y-3">
                  {gaps.slice(0, 3).map((g) => (
                    <SkillGapBar
                      key={g.skill_id}
                      skillName={g.skill_name}
                      category={g.category}
                      demandPct={g.demand_pct}
                      coveragePct={g.coverage_pct}
                      gapPct={g.gap_pct}
                      priority={g.priority}
                      demandCount={g.demand_count}
                    />
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="No Authoritative Deficits Detected"
                  message="No active employer-linked skill deficit records available. Ingest real labour-market data to compute statewide deficits."
                />
              )}
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
              <span className="text-slate-500 dark:text-slate-400">
                Showing top priority state-wide deficits
              </span>
              {role === 'ADMIN' ? (
                <Link
                  to="/institute"
                  className="font-bold text-teal-700 dark:text-teal-400 hover:text-teal-900 dark:hover:text-teal-200 hover:underline flex items-center gap-1"
                >
                  <span>Audit Institute Courses</span>
                  <span>→</span>
                </Link>
              ) : (
                <Link
                  to="/student/copilot?role=government&q=Which+vocational+courses+in+Maharashtra+address+the+highest-priority+skill+deficits%3F"
                  className="font-bold text-teal-700 dark:text-teal-400 hover:text-teal-900 dark:hover:text-teal-200 hover:underline flex items-center gap-1"
                >
                  <span>Ask AI Copilot for Institute Alignment</span>
                  <span>→</span>
                </Link>
              )}
            </div>
          </div>
        </div>
      </SectionErrorBoundary>

      {/* Grid: Future Skill Forecasts & Industry Signals */}
      <SectionErrorBoundary name="Predictive Forecasting & Industry Signals">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Future Forecasts */}
          <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col justify-between">
            <div>
              <SectionHeader
                title="Predictive Horizon Forecasting (6–24 Months)"
                subtitle="Forward projections modeled from macroeconomic industrial trends and employer surveys."
                decisionNote="Enables 2-year advance vocational planning before talent shortages materialize."
                badge="Predictive Model"
                badgeColor="teal"
              />

              {loading ? (
                <div className="space-y-3 py-2 animate-pulse">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <div key={i} className="h-8 bg-slate-100 dark:bg-slate-800/60 rounded"></div>
                  ))}
                </div>
              ) : errors.forecasts ? (
                <ErrorState
                  title="Failed to Load Forecast Analytics"
                  message="The predictive horizon forecasting model did not return data."
                  onRetry={fetchData}
                />
              ) : forecasts.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 font-semibold border-b border-slate-200 dark:border-slate-700">
                      <tr>
                        <th className="p-2.5">Skill Domain</th>
                        <th className="p-2.5">Horizon</th>
                        <th className="p-2.5">Future Demand</th>
                        <th className="p-2.5">Trend Vector</th>
                        <th className="p-2.5 text-right">Confidence</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {forecasts.map((f) => (
                        <tr
                          key={f.id}
                          className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors"
                        >
                          <td className="p-2.5 font-bold text-slate-900 dark:text-white">
                            {f.skill_name}
                          </td>
                          <td className="p-2.5 font-mono text-slate-500 dark:text-slate-400 uppercase">
                            {f.period}
                          </td>
                          <td className="p-2.5">
                            <span className="px-2 py-0.5 rounded font-semibold capitalize bg-teal-50 dark:bg-teal-950 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800 text-[11px]">
                              {f.future_demand?.replace('_', ' ')}
                            </span>
                          </td>
                          <td className="p-2.5">
                            <span
                              className={`font-semibold ${
                                f.trend === 'rising'
                                  ? 'text-emerald-600 dark:text-emerald-400'
                                  : f.trend === 'declining'
                                  ? 'text-rose-600 dark:text-rose-400'
                                  : 'text-slate-600 dark:text-slate-400'
                              }`}
                            >
                              {f.trend === 'rising'
                                ? '↑ Rising'
                                : f.trend === 'declining'
                                ? '↓ Declining'
                                : '→ Stable'}
                            </span>
                          </td>
                          <td className="p-2.5 text-right font-mono font-bold text-slate-700 dark:text-slate-300">
                            {f.confidence}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState
                  title="No Authoritative Forecasts Available"
                  message="Predictive horizon models require live employer demand and market intelligence."
                />
              )}
            </div>
          </div>

          {/* Industry Signals */}
          <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col justify-between">
            <div>
              <SectionHeader
                title="Macro-Industrial & Policy Signals"
                subtitle="Verified plant investments, technological transitions, and policy developments."
                decisionNote="Provides qualitative ground-truth to validate quantitative statistical models."
                badge="Market Signals"
              />

              {loading ? (
                <div className="space-y-3 py-2 animate-pulse">
                  <div className="h-28 bg-slate-100 dark:bg-slate-800/60 rounded-xl"></div>
                  <div className="h-28 bg-slate-100 dark:bg-slate-800/60 rounded-xl"></div>
                </div>
              ) : errors.signals ? (
                <ErrorState
                  title="Failed to Load Industry Signals"
                  message="The external market signal pipeline could not be retrieved."
                  onRetry={fetchData}
                />
              ) : signals.length > 0 ? (
                <div className="space-y-3">
                  {signals.slice(0, 2).map((sig) => (
                    <SignalCard key={sig.id} signal={sig} />
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="No Macro Signals Available"
                  message="No recent verified industrial investments or policy signals recorded."
                />
              )}
            </div>
          </div>
        </div>
      </SectionErrorBoundary>

      {/* Policy What-If Simulator — Spec Section 20 */}
      <SectionErrorBoundary name="Policy What-If Simulator">
        <div data-demo="policy-whatif-simulator" className="bg-gradient-to-br from-indigo-50 via-white to-slate-50 dark:from-indigo-950/30 dark:via-slate-900 dark:to-slate-900 p-6 rounded-xl border border-indigo-200 dark:border-indigo-800/50 mb-8 relative overflow-hidden">
          {/* Subtle decorative accent */}
          <div className="absolute top-0 right-0 w-40 h-40 bg-indigo-100/40 dark:bg-indigo-900/20 rounded-full -translate-y-1/2 translate-x-1/2 pointer-events-none" />

          <SectionHeader
            title="Policy What-If Simulator"
            subtitle="Decision-support tool: simulate capacity changes, curriculum stagnation, or new course additions and view projected impact on Maharashtra's workforce pipeline."
            decisionNote="All projections are simulated estimates for planning purposes — not guaranteed predictions."
            badge="Decision Support"
            badgeColor="amber"
          />

          {/* Scenario Selector Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
            {[
              { id: 'capacity_increase', icon: '📈', label: 'Increase Training Capacity', desc: 'What if we add more training seats in a skill area?' },
              { id: 'curriculum_stale', icon: '⏳', label: 'Curriculum Stagnation', desc: 'What if curriculum is NOT updated for N years?' },
              { id: 'new_course', icon: '🆕', label: 'Add New Course', desc: 'What if a new course is introduced for a skill gap?' },
            ].map(s => (
              <button
                key={s.id}
                onClick={() => { setSimScenario(s.id); setSimResult(null); setSimError(null); }}
                className={`text-left p-4 rounded-lg border-2 transition-all duration-200 ${
                  simScenario === s.id
                    ? 'border-indigo-500 dark:border-indigo-400 bg-indigo-50 dark:bg-indigo-950/40 shadow-sm'
                    : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60 hover:border-indigo-300 dark:hover:border-indigo-600'
                }`}
              >
                <div className="text-xl mb-1">{s.icon}</div>
                <div className={`text-sm font-semibold ${simScenario === s.id ? 'text-indigo-900 dark:text-indigo-200' : 'text-slate-800 dark:text-slate-200'}`}>{s.label}</div>
                <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 leading-snug">{s.desc}</div>
              </button>
            ))}
          </div>

          {/* Parameter Controls */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
            {/* Skill Category */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1 uppercase tracking-wider">Skill Category</label>
              <select
                value={simCategory}
                onChange={e => setSimCategory(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-indigo-400 focus:border-indigo-400 outline-none transition-colors"
              >
                <option value="">All Categories</option>
                {simCategories.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            {/* District */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1 uppercase tracking-wider">District</label>
              <select
                value={simDistrict}
                onChange={e => setSimDistrict(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-indigo-400 focus:border-indigo-400 outline-none transition-colors"
              >
                <option value="">All Districts</option>
                {['Pune', 'Mumbai', 'Nagpur', 'Nashik', 'Chhatrapati Sambhajinagar', 'Kolhapur', 'Solapur', 'Amravati', 'Thane', 'Ratnagiri'].map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>

            {/* Capacity % — only for capacity_increase */}
            {simScenario === 'capacity_increase' && (
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1 uppercase tracking-wider">Capacity Increase: {simCapacityPct}%</label>
                <input
                  type="range"
                  min="10"
                  max="100"
                  step="5"
                  value={simCapacityPct}
                  onChange={e => setSimCapacityPct(Number(e.target.value))}
                  className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                />
                <div className="flex justify-between text-[10px] text-slate-400 mt-0.5"><span>10%</span><span>100%</span></div>
              </div>
            )}

            {/* Stale Years — only for curriculum_stale */}
            {simScenario === 'curriculum_stale' && (
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1 uppercase tracking-wider">Stale Period: {simStaleYears} Year{simStaleYears > 1 ? 's' : ''}</label>
                <input
                  type="range"
                  min="1"
                  max="5"
                  step="1"
                  value={simStaleYears}
                  onChange={e => setSimStaleYears(Number(e.target.value))}
                  className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-500"
                />
                <div className="flex justify-between text-[10px] text-slate-400 mt-0.5"><span>1yr</span><span>5yr</span></div>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex items-end gap-2">
              <button
                onClick={runSimulation}
                disabled={simLoading}
                className="flex-1 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-500 dark:hover:bg-indigo-600 text-white text-sm font-semibold rounded-lg shadow-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {simLoading ? 'Simulating…' : '▶ Run Simulation'}
              </button>
              {simResult && (
                <button
                  onClick={resetSimulation}
                  className="px-3 py-2 border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-400 text-sm font-medium rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                  ↺ Reset
                </button>
              )}
            </div>
          </div>

          {/* Error State */}
          {simError && (
            <div className="p-4 rounded-lg bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-800 text-sm text-rose-800 dark:text-rose-300 mb-4">
              <span className="font-semibold">Simulation Error:</span> {simError}
            </div>
          )}

          {/* Simulation Loading */}
          {simLoading && (
            <div className="py-8 text-center animate-pulse">
              <div className="inline-block w-8 h-8 border-3 border-indigo-400 border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-3">Running policy simulation…</p>
            </div>
          )}

          {/* Results Panel */}
          {simResult && !simLoading && (
            <div className="space-y-5">
              {/* SIMULATED ESTIMATE Banner */}
              <div className="flex items-center gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800">
                <span className="text-lg">⚠️</span>
                <div>
                  <span className="text-[10px] font-mono font-bold px-2 py-0.5 bg-amber-200 dark:bg-amber-800 text-amber-900 dark:text-amber-200 rounded mr-2">SIMULATED ESTIMATE</span>
                  <span className="text-xs text-amber-800 dark:text-amber-300">{simResult.disclaimer}</span>
                </div>
              </div>

              {/* Baseline vs Projected Comparison Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Baseline Card */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700">
                  <div className="text-[10px] font-mono font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">Current Baseline</div>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-slate-600 dark:text-slate-400">Training Seats</span>
                      <span className="text-sm font-bold text-slate-900 dark:text-white">{simResult.baseline?.total_training_seats?.toLocaleString?.() || 14800}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-slate-600 dark:text-slate-400">Avg Skill Gap</span>
                      <span className="text-sm font-bold text-slate-900 dark:text-white">{simResult.baseline?.avg_skill_gap_pct || 34.2}%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-slate-600 dark:text-slate-400">Placement Rate</span>
                      <span className="text-sm font-bold text-slate-900 dark:text-white">{simResult.baseline?.placement_rate_pct || 78.4}%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-slate-600 dark:text-slate-400">Courses</span>
                      <span className="text-sm font-bold text-slate-900 dark:text-white">{simResult.baseline?.courses_count || 120}</span>
                    </div>
                  </div>
                </div>

                {/* Projected Card */}
                <div className="p-4 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 border-2 border-indigo-300 dark:border-indigo-700">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-[10px] font-mono font-semibold text-indigo-700 dark:text-indigo-300 uppercase tracking-wider">Projected State</span>
                    <span className="text-[9px] font-mono px-1.5 py-0.5 bg-amber-200 dark:bg-amber-800 text-amber-900 dark:text-amber-200 rounded">ESTIMATE</span>
                  </div>
                  <div className="space-y-3">
                    {simResult.projection?.projected_total_seats != null && (
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-indigo-700 dark:text-indigo-300">Training Seats</span>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-indigo-900 dark:text-indigo-100">{simResult.projection.projected_total_seats?.toLocaleString?.()}</span>
                          {simResult.projection.seats_added > 0 && <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">+{simResult.projection.seats_added}</span>}
                        </div>
                      </div>
                    )}
                    {simResult.projection?.projected_avg_gap_pct != null && (
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-indigo-700 dark:text-indigo-300">Avg Skill Gap</span>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-indigo-900 dark:text-indigo-100">{simResult.projection.projected_avg_gap_pct}%</span>
                          {(simResult.projection.gap_reduction_pct > 0 || simResult.projection.gap_improvement_pct > 0) && (
                            <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">▼ {simResult.projection.gap_reduction_pct || simResult.projection.gap_improvement_pct}%</span>
                          )}
                          {simResult.projection.gap_increase_pct > 0 && (
                            <span className="text-[10px] font-semibold text-rose-600 dark:text-rose-400">▲ +{simResult.projection.gap_increase_pct}%</span>
                          )}
                        </div>
                      </div>
                    )}
                    {simResult.projection?.projected_placement_rate_pct != null && (
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-indigo-700 dark:text-indigo-300">Placement Rate</span>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-indigo-900 dark:text-indigo-100">{simResult.projection.projected_placement_rate_pct}%</span>
                          {simResult.projection.placement_rate_change > 0 && (
                            <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">+{simResult.projection.placement_rate_change}%</span>
                          )}
                          {simResult.projection.placement_boost_pct > 0 && (
                            <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">+{simResult.projection.placement_boost_pct}%</span>
                          )}
                          {simResult.projection.placement_decline_pct > 0 && (
                            <span className="text-[10px] font-semibold text-rose-600 dark:text-rose-400">▼ -{simResult.projection.placement_decline_pct}%</span>
                          )}
                        </div>
                      </div>
                    )}
                    {simResult.projection?.trainers_required != null && (
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-indigo-700 dark:text-indigo-300">Trainers Required</span>
                        <span className="text-sm font-bold text-indigo-900 dark:text-indigo-100">{simResult.projection.trainers_required}</span>
                      </div>
                    )}
                    {simResult.projection?.equipment_units_required != null && (
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-indigo-700 dark:text-indigo-300">Equipment Units</span>
                        <span className="text-sm font-bold text-indigo-900 dark:text-indigo-100">{simResult.projection.equipment_units_required}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Affected Skills Detail */}
              {(simResult.projection?.affected_skill_gaps?.length > 0 || simResult.projection?.skills_addressed?.length > 0 || simResult.projection?.emerging_skills_at_risk?.length > 0) && (
                <div className="bg-white dark:bg-slate-800/60 p-4 rounded-xl border border-slate-200 dark:border-slate-700">
                  <div className="text-[10px] font-mono font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">
                    {simScenario === 'curriculum_stale' ? 'Skills at Risk' : 'Affected Skills'}
                  </div>
                  <div className="space-y-2">
                    {/* capacity_increase gaps */}
                    {simResult.projection?.affected_skill_gaps?.map((g, i) => (
                      <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-slate-50 dark:bg-slate-800/40">
                        <span className="text-xs font-medium text-slate-800 dark:text-slate-200">{g.skill}</span>
                        <div className="flex items-center gap-3 text-[11px]">
                          <span className="text-slate-500 dark:text-slate-400">{g.current_gap_pct}%</span>
                          <span className="text-slate-400">→</span>
                          <span className="font-semibold text-emerald-600 dark:text-emerald-400">{g.projected_gap_pct}%</span>
                          <span className="text-[10px] text-emerald-500 dark:text-emerald-400">▼{g.reduction_pct}%</span>
                        </div>
                      </div>
                    ))}
                    {/* new_course skills */}
                    {simResult.projection?.skills_addressed?.map((g, i) => (
                      <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-slate-50 dark:bg-slate-800/40">
                        <span className="text-xs font-medium text-slate-800 dark:text-slate-200">{g.skill}</span>
                        <div className="flex items-center gap-3 text-[11px]">
                          <span className="text-slate-500 dark:text-slate-400">{g.current_gap_pct}%</span>
                          <span className="text-slate-400">→</span>
                          <span className="font-semibold text-emerald-600 dark:text-emerald-400">{g.projected_gap_pct}%</span>
                          <span className="text-[10px] text-emerald-500 dark:text-emerald-400">▼{g.reduction_pct}%</span>
                        </div>
                      </div>
                    ))}
                    {/* curriculum_stale risks */}
                    {simResult.projection?.emerging_skills_at_risk?.map((s, i) => (
                      <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-rose-50/60 dark:bg-rose-950/20">
                        <div>
                          <span className="text-xs font-medium text-slate-800 dark:text-slate-200">{s.skill}</span>
                          <span className="text-[10px] text-slate-400 ml-1.5">{s.category}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-slate-400">Future: {s.future_demand}</span>
                          <span className={`text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded ${
                            s.curriculum_coverage_risk === 'NOT COVERED'
                              ? 'bg-rose-200 dark:bg-rose-800 text-rose-800 dark:text-rose-200'
                              : 'bg-amber-200 dark:bg-amber-800 text-amber-800 dark:text-amber-200'
                          }`}>{s.curriculum_coverage_risk}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Curriculum Stale Warning */}
              {simResult.projection?.industry_shortage_warning && (
                <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-300">
                  <span className="font-semibold">⚠️ Industry Shortage Warning: </span>{simResult.projection.industry_shortage_warning}
                </div>
              )}

              {/* Affected Courses (capacity_increase) */}
              {simResult.projection?.affected_courses?.length > 0 && (
                <div className="bg-white dark:bg-slate-800/60 p-4 rounded-xl border border-slate-200 dark:border-slate-700">
                  <div className="text-[10px] font-mono font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">
                    Affected Training Programs ({simResult.projection.affected_courses_count || simResult.projection.affected_courses.length})
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {simResult.projection.affected_courses.map((c, i) => (
                      <span key={i} className="text-[11px] px-2.5 py-1 rounded-full bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                        {c.name} — {c.district}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Empty state — no simulation run yet */}
          {!simResult && !simLoading && !simError && (
            <div className="py-6 text-center">
              <p className="text-sm text-slate-400 dark:text-slate-500">Select a scenario, configure parameters, and click <span className="font-semibold text-indigo-600 dark:text-indigo-400">Run Simulation</span> to see projected impact.</p>
            </div>
          )}
        </div>
      </SectionErrorBoundary>

      {/* Curriculum Recommendations Section */}
      <SectionErrorBoundary name="Curriculum Recommendations">
        <div className="bg-slate-50 dark:bg-slate-900/60 p-6 rounded-xl border border-slate-200 dark:border-slate-800 mb-8">
          <SectionHeader
            title="Actionable Curriculum Revision Directives"
            subtitle="AI-synthesized, evidence-backed course modifications formulated for MSBTE & Directorate of Vocational Education."
            decisionNote="Ready-to-table formal curriculum revision agenda for upcoming academic councils."
            badge="Council Ready"
            badgeColor="teal"
          />

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-pulse">
              <div className="h-32 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700"></div>
              <div className="h-32 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700"></div>
            </div>
          ) : errors.recommendations ? (
            <ErrorState
              title="Failed to Load Curriculum Recommendations"
              message="The recommendation generation engine encountered a communication issue."
              onRetry={fetchData}
            />
          ) : recommendations.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {recommendations.map((rec, idx) => (
                <RecommendationCard key={idx} rec={rec} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No Curriculum Action Items Pending"
              message="Curricula across evaluated trades align with current market requirements."
            />
          )}
        </div>
      </SectionErrorBoundary>

      {/* State-Wide Platform Success Metrics (§33) */}
      <SectionErrorBoundary name="Section 33 Platform Success Metrics">
        <div data-demo="platform-success-metrics" className="bg-white dark:bg-slate-900 p-6 sm:p-7 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs mb-8">
          <SectionHeader
            title="State-Wide Platform Success Metrics"
            subtitle="Consolidated telemetry tracking placement rates, skill mismatch index, employer approval rate, and capacity gaps across Maharashtra."
            decisionNote="Executive scorecard established under PROJECT_SPEC Section 33 for longitudinal state performance audits."
            badge="Section 33 KPI Scorecard"
            badgeColor="teal"
          />

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 mt-4">
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700">
              <div className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">1. Placement Rate</div>
              <div className="text-xl sm:text-2xl font-black text-slate-900 dark:text-white mt-1">
                {platformMetrics?.placement_rate_pct != null ? `${platformMetrics.placement_rate_pct}%` : '—'}
              </div>
              <div className="text-[10px] text-emerald-600 dark:text-emerald-400 mt-0.5 font-medium">State-wide average conversion</div>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700">
              <div className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">2. Skill Mismatch Score</div>
              <div className="text-xl sm:text-2xl font-black text-amber-600 dark:text-amber-400 mt-1">
                {platformMetrics?.skill_mismatch_score != null ? `${platformMetrics.skill_mismatch_score}%` : '—'}
              </div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">Average net curriculum deficit</div>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700">
              <div className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">3. Employer Approval</div>
              <div className="text-xl sm:text-2xl font-black text-teal-600 dark:text-teal-400 mt-1">
                {platformMetrics?.employer_approval_rate_pct != null ? `${platformMetrics.employer_approval_rate_pct}%` : '—'}
              </div>
              <div className="text-[10px] text-teal-600 dark:text-teal-400 mt-0.5 font-medium">Human-in-the-loop consensus</div>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700">
              <div className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">4. Syllabus Revision Cycle</div>
              <div className="text-xl sm:text-2xl font-black text-indigo-600 dark:text-indigo-400 mt-1">
                {platformMetrics?.avg_curriculum_update_time_months != null ? `${platformMetrics.avg_curriculum_update_time_months} mo` : '—'}
              </div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">Down from 24-month baseline</div>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700">
              <div className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">5. Training Seat Deficit</div>
              <div className="text-xl sm:text-2xl font-black text-rose-600 dark:text-rose-400 mt-1">
                {platformMetrics?.training_capacity_deficit_seats != null ? platformMetrics.training_capacity_deficit_seats.toLocaleString() : '—'}
              </div>
              <div className="text-[10px] text-rose-600 dark:text-rose-400 mt-0.5">High-priority seats needed</div>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700">
              <div className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">6. Equipment & Trainer Gaps</div>
              <div className="text-xl sm:text-2xl font-black text-blue-600 dark:text-blue-400 mt-1">
                {platformMetrics?.equipment_trainer_gap_count != null ? `${platformMetrics.equipment_trainer_gap_count} Trades` : '—'}
              </div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">Requiring lab or faculty grants</div>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700 col-span-2 sm:col-span-3 lg:col-span-2">
              <div className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">7. Student Recommendation Engagement</div>
              <div className="flex items-center justify-between mt-1">
                <div className="text-xl sm:text-2xl font-black text-emerald-600 dark:text-emerald-400">
                  {platformMetrics?.student_engagement_rate_pct != null ? `${platformMetrics.student_engagement_rate_pct}%` : '—'}
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 rounded border border-emerald-200 dark:border-emerald-800 font-bold">
                  High Adoption
                </span>
              </div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">Youth completing assessments & following verified roadmaps</div>
            </div>
          </div>
        </div>
      </SectionErrorBoundary>

      <SectionErrorBoundary sectionName="Published Government Opportunities & Schemes">
        <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs mb-8">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  Active Government Opportunities & Schemes
                </h3>
                <span className="text-[10px] font-mono px-2 py-0.5 bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 font-semibold rounded border border-emerald-200 dark:border-emerald-800">
                  {govOpportunities.length} Active
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Official schemes, apprenticeships, and vocational training initiatives published to the state registry.
              </p>
            </div>
            {canPublish && (
              <button
                onClick={() => setIsModalOpen(true)}
                className="px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-lg shadow-xs transition-colors cursor-pointer self-start flex items-center gap-1.5"
              >
                <span>+</span>
                <span>Publish New Scheme</span>
              </button>
            )}
          </div>

          {loading ? (
            <div className="py-8 text-center text-xs text-slate-400">Loading published opportunities...</div>
          ) : govOpportunities.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {govOpportunities.map((opp) => (
                <div
                  key={opp.id}
                  className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 hover:border-teal-500/40 transition-colors flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-teal-50 dark:bg-teal-950 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
                        {opp.opportunity_type || 'APPRENTICESHIP'}
                      </span>
                      <span className="text-[10px] font-semibold text-slate-400">
                        {opp.deadline ? `Deadline: ${opp.deadline}` : 'Open Enrollment'}
                      </span>
                    </div>
                    <h4 className="text-sm font-bold text-slate-900 dark:text-white line-clamp-2">
                      {opp.name}
                    </h4>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                      {opp.department}
                    </p>
                    <p className="text-xs text-slate-600 dark:text-slate-300 mt-2 line-clamp-3">
                      {opp.description}
                    </p>
                    {Array.isArray(opp.target_skills) && opp.target_skills.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-3">
                        {opp.target_skills.slice(0, 4).map((sk, i) => (
                          <span
                            key={i}
                            className="text-[10px] px-2 py-0.5 rounded bg-slate-200/70 dark:bg-slate-700 text-slate-700 dark:text-slate-300 font-medium"
                          >
                            {sk}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="mt-4 pt-3 border-t border-slate-200/60 dark:border-slate-700/60 flex items-center justify-between">
                    <span className="text-[11px] text-slate-500 dark:text-slate-400">
                      📍 {Array.isArray(opp.district_coverage) ? opp.district_coverage.join(', ') : (opp.district_coverage || 'Maharashtra')}
                    </span>
                    {opp.application_url && (
                      <a
                        href={opp.application_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-bold text-teal-600 dark:text-teal-400 hover:underline inline-flex items-center gap-1"
                      >
                        <span>Apply</span>
                        <span>↗</span>
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No Active Opportunities Published"
              message="Published government opportunities and schemes will appear here once submitted through the state console."
            />
          )}
        </div>
      </SectionErrorBoundary>

      {/* Publish Scheme / Opportunity Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-fadeIn">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                  Publish Government Opportunity / Scheme
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Notify youth across Maharashtra and connect candidates to state-sponsored initiatives
                </p>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleGovSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Scheme / Opportunity Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={govForm.name}
                    onChange={(e) => setGovForm({ ...govForm, name: e.target.value })}
                    placeholder="e.g. CM Apprenticeship Promotion Scheme"
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white font-medium focus:ring-2 focus:ring-teal-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Nodal Department *
                  </label>
                  <input
                    type="text"
                    required
                    value={govForm.department}
                    onChange={(e) => setGovForm({ ...govForm, department: e.target.value })}
                    placeholder="e.g. Skill Development Dept"
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white font-medium focus:ring-2 focus:ring-teal-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Opportunity Type
                  </label>
                  <select
                    value={govForm.opportunity_type}
                    onChange={(e) => setGovForm({ ...govForm, opportunity_type: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white font-medium focus:ring-2 focus:ring-teal-500 focus:outline-none"
                  >
                    <option value="APPRENTICESHIP">Apprenticeship</option>
                    <option value="VOCATIONAL_TRAINING">Vocational Training</option>
                    <option value="EMPLOYMENT_SCHEME">Employment Scheme</option>
                    <option value="SUBSIDY">Financial Subsidy / Stipend</option>
                  </select>
                </div>

                <div>
                  <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                    District Coverage (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={govForm.district_coverage}
                    onChange={(e) => setGovForm({ ...govForm, district_coverage: e.target.value })}
                    placeholder="e.g. Pune, Mumbai City, Maharashtra"
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white font-medium focus:ring-2 focus:ring-teal-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Target Competencies / Skills (comma-separated)
                </label>
                <input
                  type="text"
                  value={govForm.target_skills}
                  onChange={(e) => setGovForm({ ...govForm, target_skills: e.target.value })}
                  placeholder="e.g. PLC Programming, Automation, EV Technology"
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white font-medium focus:ring-2 focus:ring-teal-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Brief Description *
                </label>
                <textarea
                  required
                  rows={3}
                  value={govForm.description}
                  onChange={(e) => setGovForm({ ...govForm, description: e.target.value })}
                  placeholder="Describe the opportunity, monthly stipend, training duration, and target youth cohort..."
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white font-medium focus:ring-2 focus:ring-teal-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Eligibility Criteria
                  </label>
                  <input
                    type="text"
                    value={govForm.eligibility_criteria}
                    onChange={(e) => setGovForm({ ...govForm, eligibility_criteria: e.target.value })}
                    placeholder="e.g. 10th/12th/ITI pass aged 18-28"
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white font-medium focus:ring-2 focus:ring-teal-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Application Deadline
                  </label>
                  <input
                    type="date"
                    value={govForm.deadline}
                    onChange={(e) => setGovForm({ ...govForm, deadline: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white font-medium focus:ring-2 focus:ring-teal-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Official Portal / Application URL
                </label>
                <input
                  type="url"
                  value={govForm.application_url}
                  onChange={(e) => setGovForm({ ...govForm, application_url: e.target.value })}
                  placeholder="https://mahaswayam.gov.in"
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white font-medium focus:ring-2 focus:ring-teal-500 focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  disabled={submitting}
                  className="px-4 py-2 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-lg font-bold hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-bold shadow-xs transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  {submitting ? 'Publishing...' : 'Publish to State Registry 🏛️'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Layout>
  );
}

