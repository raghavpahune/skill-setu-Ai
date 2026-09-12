import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  Cell,
} from 'recharts';
import Layout from '../components/Layout';
import StatCard from '../components/StatCard';
import SignalCard from '../components/SignalCard';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

const DISTRICTS = [

  'All Districts',
  'Pune',
  'Mumbai',
  'Nagpur',
  'Nashik',
  'Chhatrapati Sambhajinagar',
  'Thane',
  'Kolhapur',
  'Solapur',
  'Amravati',
];

const INDUSTRIES = [
  'All Industries',
  'IT/ITES',
  'Electric Vehicles',
  'Manufacturing',
  'Pharmaceuticals',
  'Green Energy',
  'Logistics',
  'Emerging Tech',
];

const PRESET_FEEDBACK_NOTES = [
  'Candidates lack production hands-on deployment and testing experience.',
  'Need high-voltage safety and diagnostic certification before placement.',
  'Theoretical knowledge is good, but practical lab tools (Docker/K8s/PLC) are missing.',
  'Recommend upgrading course from introductory awareness to senior production-grade.',
];

const AVAILABLE_TAXONOMY_SKILLS = [
  'Generative AI',
  'RAG',
  'AI Agents',
  'Python',
  'Vector Databases',
  'Machine Learning',
  'Deep Learning',
  'PyTorch',
  'Kubernetes',
  'Docker',
  'AWS',
  'CI/CD',
  'Cybersecurity',
  'Network Security',
  'EV Battery Technology',
  'Battery Management (BMS)',
  'Motor Control',
  'PLC Programming',
  'SCADA',
  'Industrial Robotics',
  'IoT',
  'Solar Energy',
  'Drone Technology',
  'CAD/CAM',
  'Data Analytics',
  'SQL',
];

export default function EmployerDashboard() {
  const { user, role } = useAuth();
  const [activeTab, setActiveTab] = useState('validation'); // 'validation' | 'demand' | 'difficult' | 'signals'
  const [validations, setValidations] = useState([]);
  const [demands, setDemands] = useState([]);
  const [difficultSkills, setDifficultSkills] = useState([]);
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(null);
  const [isDemoMode, setIsDemoMode] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState('all');
  const [districtFilter, setDistrictFilter] = useState('All Districts');
  const [industryFilter, setIndustryFilter] = useState('All Industries');
  const [urgencyFilter, setUrgencyFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('table'); // 'table' | 'cards'

  // Modal / Feedback state
  const [activeFeedback, setActiveFeedback] = useState(null);
  const [correctionNote, setCorrectionNote] = useState('');
  const [selectedProficiency, setSelectedProficiency] = useState('advanced');

  // New Demand Form state (Phase 14)
  const [demandForm, setDemandForm] = useState({
    employer_name: user?.name || '',
    company_name: user?.name || '',
    industry: 'IT & Software',
    district: 'Pune',
    role_title: '',
    job_role: '',
    selectedSkills: ['Generative AI', 'RAG'],
    customSkillInput: '',
    proficiency_required: 'advanced',
    preferred_proficiency: 'advanced',
    nsqf_level: 6,
    urgency: 'immediate',
    hiring_timeline: 'Immediate (0-30 days)',
    positions_count: 5,
    openings_count: 5,
    experience_level: 'Entry Level (0-1 yrs)',
    hiring_challenge: '',
    additional_requirements: '',
    gstin: '',
  });
  const [submittingDemand, setSubmittingDemand] = useState(false);

  // Notifications
  const [toastMessage, setToastMessage] = useState(null);

  const loadEmployerData = async () => {
    setLoading(true);
    setApiError(null);
    try {
      const [valsRes, demandsRes, diffRes, sigsRes, healthRes] = await Promise.all([
        api.getEmployerValidations(),
        api.getEmployerDemands(),
        api.getDifficultSkills(),
        api.getSignals(),
        api.getHealth().catch(() => null),
      ]);
      if (healthRes) {
        setIsDemoMode(Boolean(healthRes.demo_mode ?? healthRes.is_demo));
      }
      if (Array.isArray(valsRes)) setValidations(valsRes);
      if (Array.isArray(demandsRes)) setDemands(demandsRes);
      if (Array.isArray(diffRes)) setDifficultSkills(diffRes);
      if (Array.isArray(sigsRes)) {
        setSignals(sigsRes);
      } else if (sigsRes?.signals && Array.isArray(sigsRes.signals)) {
        setSignals(sigsRes.signals);
      } else {
        setSignals([]);
      }
    } catch (err) {
      console.warn('Failed loading employer live data:', err);
      setApiError(err?.message || 'Failed to load live employer data. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEmployerData();
  }, []);


  const showToast = (type, message) => {
    setToastMessage({ type, message });
    setTimeout(() => {
      setToastMessage(null);
    }, 4000);
  };

  // Actions
  const handleAction = async (feedbackId, status, notes = null, prof = null) => {
    // Optimistic UI update
    setValidations((prev) =>
      prev.map((v) =>
        v.id === feedbackId
          ? {
              ...v,
              status,
              notes: notes !== null ? notes : v.notes,
              proficiency_required: prof !== null ? prof : v.proficiency_required,
            }
          : v
      )
    );


    try {
      await api.submitEmployerFeedback(feedbackId, status, notes, prof);
      showToast('success', `Signal calibrated as ${status.toUpperCase()}`);
      setActiveFeedback(null);
    } catch (err) {
      console.warn('Backend feedback update fallback handled:', err);
      showToast('success', `Signal recorded locally as ${status.toUpperCase()} (Offline Ready)`);
      setActiveFeedback(null);
    }
  };

  const handleBatchConfirmFiltered = () => {
    const pendingFiltered = filteredValidations.filter((v) => v.status === 'pending');
    if (pendingFiltered.length === 0) {
      showToast('info', 'No pending signals in current filtered view.');
      return;
    }

    setValidations((prev) =>
      prev.map((v) => {
        const isTarget = pendingFiltered.some((pf) => pf.id === v.id);
        return isTarget ? { ...v, status: 'confirmed' } : v;
      })
    );

    // Trigger async updates in background
    Promise.all(
      pendingFiltered.map((item) =>
        api.submitEmployerFeedback(item.id, 'confirmed').catch(() => null)
      )
    );

    showToast('success', `Batch confirmed ${pendingFiltered.length} industry skill signals!`);
  };

  const handleDemandSubmit = async (e) => {
    e.preventDefault();
    const role = (demandForm.job_role || demandForm.role_title || '').trim();
    const company = (demandForm.company_name || demandForm.employer_name || '').trim();
    if (!company) {
      showToast('error', 'Please enter Company / Organization name.');
      return;
    }
    if (!role) {
      showToast('error', 'Please enter a target Job Role Title.');
      return;
    }
    if (demandForm.selectedSkills.length === 0) {
      showToast('error', 'Please add at least one required skill.');
      return;
    }

    setSubmittingDemand(true);
    const newDemandData = {
      company_name: company,
      employer_name: company,
      industry: demandForm.industry,
      district: demandForm.district,
      job_role: role,
      role_title: role,
      required_skills: demandForm.selectedSkills,
      skills: demandForm.selectedSkills,
      preferred_proficiency: demandForm.proficiency_required,
      proficiency_required: demandForm.proficiency_required,
      nsqf_level: Number(demandForm.nsqf_level),
      hiring_timeline: demandForm.hiring_timeline,
      urgency: demandForm.urgency,
      openings_count: Number(demandForm.positions_count) || 10,
      positions_count: Number(demandForm.positions_count) || 10,
      experience_level: demandForm.experience_level,
      gstin: demandForm.gstin?.trim() || null,
      additional_requirements: demandForm.hiring_challenge.trim() || null,
      hiring_challenge: demandForm.hiring_challenge.trim() || null,
    };

    try {
      const res = await api.submitEmployerDemand(newDemandData);
      const savedDemand = res?.demand || {
        ...newDemandData,
        id: `ed-${Date.now()}`,
        source: 'EMPLOYER_SUBMITTED',
        validation_status: 'PENDING',
        provenance_label: 'Employer Submitted — Pending Validation',
        is_demo: false,
        submitted_date: new Date().toISOString().split('T')[0],
        status: 'pending',
      };
      setDemands((prev) => [savedDemand, ...prev]);
      showToast('success', `Hiring demand for "${role}" submitted — Status: Pending Validation`);
      // Reset role & challenge
      setDemandForm((prev) => ({
        ...prev,
        role_title: '',
        job_role: '',
        hiring_challenge: '',
        additional_requirements: '',
        customSkillInput: '',
      }));
    } catch (err) {
      console.error('Backend demand submit error:', err);
      showToast('error', `Failed to submit hiring demand: ${err?.message || 'Server error'}`);
    } finally {
      setSubmittingDemand(false);
    }
  };



  const handleAddSkillToForm = (skill) => {
    if (!skill || demandForm.selectedSkills.includes(skill)) return;
    setDemandForm((prev) => ({
      ...prev,
      selectedSkills: [...prev.selectedSkills, skill],
    }));
  };

  const handleRemoveSkillFromForm = (skillToRemove) => {
    setDemandForm((prev) => ({
      ...prev,
      selectedSkills: prev.selectedSkills.filter((s) => s !== skillToRemove),
    }));
  };

  const handleAddCustomSkill = (e) => {
    if (e.key === 'Enter' || e.type === 'click') {
      e.preventDefault();
      const s = demandForm.customSkillInput.trim();
      if (s && !demandForm.selectedSkills.includes(s)) {
        handleAddSkillToForm(s);
        setDemandForm((prev) => ({ ...prev, customSkillInput: '' }));
      }
    }
  };

  const exportValidationsJSON = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(validations, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `skillsetu_employer_validations_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    showToast('info', 'Employer validation report exported.');
  };

  // Filtered validations
  const filteredValidations = useMemo(() => {
    return validations.filter((v) => {
      if (statusFilter !== 'all' && v.status?.toLowerCase() !== statusFilter.toLowerCase()) return false;
      if (districtFilter !== 'All Districts' && v.district?.toLowerCase() !== districtFilter.toLowerCase()) return false;
      if (industryFilter !== 'All Industries' && v.industry?.toLowerCase() !== industryFilter.toLowerCase()) return false;
      if (urgencyFilter !== 'all' && v.demand_level?.toLowerCase() !== urgencyFilter.toLowerCase()) return false;

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const skillMatch = v.skill_name?.toLowerCase().includes(q);
        const empMatch = v.employer_name?.toLowerCase().includes(q);
        const notesMatch = v.notes?.toLowerCase().includes(q);
        const catMatch = v.skill_category?.toLowerCase().includes(q);
        if (!skillMatch && !empMatch && !notesMatch && !catMatch) return false;
      }
      return true;
    });
  }, [validations, statusFilter, districtFilter, industryFilter, urgencyFilter, searchQuery]);

  // Statistics calculation
  const totalCount = validations.length;
  const confirmedCount = validations.filter((v) => v.status === 'confirmed').length;
  const pendingCount = validations.filter((v) => v.status === 'pending').length;
  const correctedCount = validations.filter((v) => v.status === 'corrected').length;
  const rejectedCount = validations.filter((v) => v.status === 'rejected').length;
  const reviewedCount = confirmedCount + correctedCount + rejectedCount;
  const approvalRate = reviewedCount > 0 ? Math.round((confirmedCount / reviewedCount) * 100) : 0;

  // Chart data for Difficult Skills
  const difficultChartData = useMemo(() => {
    return difficultSkills.slice(0, 6).map((d) => ({
      name: d.skill_name.length > 20 ? d.skill_name.slice(0, 18) + '…' : d.skill_name,
      fullName: d.skill_name,
      deficit: d.deficit_score,
      daysToFill: d.avg_days_to_fill ?? null,
      category: d.category,
    }));
  }, [difficultSkills]);

  return (
    <Layout>
      {/* Toast Banner */}
      {toastMessage && (
        <div
          className={`fixed top-20 right-6 z-50 px-4 py-3 rounded-xl shadow-lg border text-xs font-bold flex items-center gap-2.5 transition-all animate-slideDown ${
            toastMessage.type === 'success'
              ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-900 dark:text-emerald-200 border-emerald-300 dark:border-emerald-800'
              : toastMessage.type === 'error'
              ? 'bg-rose-50 dark:bg-rose-950 text-rose-900 dark:text-rose-200 border-rose-300 dark:border-rose-800'
              : 'bg-blue-50 dark:bg-blue-950 text-blue-900 dark:text-blue-200 border-blue-300 dark:border-blue-800'
          }`}
        >
          <span>{toastMessage.type === 'success' ? '✓' : toastMessage.type === 'error' ? '⚠️' : 'ℹ️'}</span>
          <span>{toastMessage.message}</span>
          <button onClick={() => setToastMessage(null)} className="ml-2 opacity-60 hover:opacity-100">
            ✕
          </button>
        </div>
      )}

      {/* Header & Badges */}
      <div data-demo="employer-dashboard-container" className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-purple-100 dark:bg-purple-950 text-purple-800 dark:text-purple-300 font-bold border border-purple-200 dark:border-purple-800">
              Human-in-the-Loop Validation
            </span>
            <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300 font-bold border border-teal-200 dark:border-teal-800">
              State Industry Feedback Loop
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            Employer Validation & Industry Demand Hub
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-3xl">
            Validate AI-forecasted skill trends, submit direct hiring specifications, and eliminate industrial talent deficits across Maharashtra’s industrial corridors.
          </p>
        </div>

        <div className="flex items-center gap-2.5 self-start lg:self-center flex-wrap">
          <button
            data-demo="employer-post-demand-btn"
            onClick={() => setActiveTab('demand')}
            className="px-4 py-2 bg-slate-900 dark:bg-teal-600 hover:bg-slate-800 dark:hover:bg-teal-700 text-white font-bold rounded-lg text-xs shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
          >
            <span>🚀</span>
            <span>Submit Live Demand</span>
          </button>
          {role === 'ADMIN' ? (
            <Link
              to="/admin"
              className="px-3.5 py-2 bg-purple-50 dark:bg-purple-950/60 hover:bg-purple-100 dark:hover:bg-purple-900/80 text-purple-800 dark:text-purple-300 font-bold rounded-lg text-xs border border-purple-200 dark:border-purple-800 transition-colors flex items-center gap-1.5"
              title="Open Admin Validation Registry"
            >
              <span>🛡️</span>
              <span>Admin Validation Gate →</span>
            </Link>
          ) : (
            <div className="px-3 py-1.5 bg-slate-50 dark:bg-slate-800/80 text-slate-700 dark:text-slate-300 font-medium rounded-lg text-xs border border-slate-200 dark:border-slate-700 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span>Live Employer Feed Active</span>
            </div>
          )}
          <button
            onClick={exportValidationsJSON}
            className="px-3.5 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-semibold rounded-lg text-xs border border-slate-200 dark:border-slate-700 transition-colors flex items-center gap-1.5 cursor-pointer"
            title="Export full validation audit trail"
          >
            <span>📥</span>
            <span>Export Signals</span>
          </button>
        </div>
      </div>


      {/* Ground-Truth Pipeline Stepper */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-950 rounded-xl p-4 sm:p-5 mb-6 text-white border border-slate-800 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
              <span className="text-[11px] font-bold uppercase tracking-wider text-teal-300">
                Authoritative Ground-Truth Calibration Pipeline
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-medium">
              <span className="bg-slate-800/80 px-2.5 py-1 rounded text-slate-300 border border-slate-700">
                1. AI Market Extractions
              </span>
              <span className="text-teal-400 font-bold">→</span>
              <span className="bg-purple-950/90 px-2.5 py-1 rounded text-purple-200 font-bold border border-purple-700 shadow-xs">
                2. Employer Sign-Off (Active)
              </span>
              <span className="text-teal-400 font-bold">→</span>
              <span className="bg-slate-800/80 px-2.5 py-1 rounded text-slate-300 border border-slate-700">
                3. ITI & Polytechnic Syllabi
              </span>
              <span className="text-teal-400 font-bold">→</span>
              <span className="bg-slate-800/80 px-2.5 py-1 rounded text-slate-300 border border-slate-700">
                4. Placement Verification
              </span>
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs shrink-0 border-t md:border-t-0 md:border-l border-slate-700 pt-3 md:pt-0 md:pl-5">
            <div>
              <p className="text-slate-400 text-[10px] uppercase tracking-wider font-semibold">Validation Queue</p>
              <p className="text-lg font-mono font-bold text-amber-400">{pendingCount} Awaiting Review</p>
            </div>
            <div>
              <p className="text-slate-400 text-[10px] uppercase tracking-wider font-semibold">Industry Consensus</p>
              <p className="text-lg font-mono font-bold text-emerald-400">{approvalRate}% Approved</p>
            </div>
          </div>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3.5 sm:gap-4 mb-7">
        <StatCard
          title="Signals Reviewed"
          value={totalCount.toString()}
          subtitle={`${reviewedCount} evaluated`}
          icon="📋"
          color="white"
        />
        <StatCard
          title="Industry Approval"
          value={`${approvalRate}%`}
          subtitle={`${confirmedCount} signals confirmed`}
          icon="✅"
          color="teal"
          trend="up"
          trendLabel="High Consensus"
        />
        <StatCard
          title="Pending Sign-Off"
          value={pendingCount.toString()}
          subtitle="Action required"
          icon="⏳"
          color="amber"
          badge={pendingCount > 0 ? 'Review' : 'Clear'}
        />
        <StatCard
          title="Human Corrections"
          value={correctedCount.toString()}
          subtitle="Refined requirements"
          icon="✍️"
          color="rose"
        />
        <StatCard
          title="Bottleneck Skills"
          value={difficultSkills.length.toString()}
          subtitle="Critical hiring deficits"
          icon="⚡"
          color="navy"
        />
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-1 border-b border-slate-200 dark:border-slate-800 mb-6 overflow-x-auto pb-1">
        <button
          onClick={() => setActiveTab('validation')}
          className={`px-4 py-2.5 text-xs sm:text-sm font-bold border-b-2 transition-all shrink-0 flex items-center gap-2 ${
            activeTab === 'validation'
              ? 'border-teal-600 text-teal-700 dark:text-teal-400'
              : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          <span>📋</span>
          <span>AI Validation Queue</span>
          <span className="ml-1 px-2 py-0.5 rounded-full text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono">
            {filteredValidations.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('demand')}
          className={`px-4 py-2.5 text-xs sm:text-sm font-bold border-b-2 transition-all shrink-0 flex items-center gap-2 ${
            activeTab === 'demand'
              ? 'border-teal-600 text-teal-700 dark:text-teal-400'
              : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          <span>🚀</span>
          <span>Submit Hiring Demand</span>
          <span className="ml-1 px-2 py-0.5 rounded-full text-[10px] bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300 font-mono">
            {demands.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('difficult')}
          className={`px-4 py-2.5 text-xs sm:text-sm font-bold border-b-2 transition-all shrink-0 flex items-center gap-2 ${
            activeTab === 'difficult'
              ? 'border-teal-600 text-teal-700 dark:text-teal-400'
              : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          <span>⚡</span>
          <span>Hard-to-Hire Shortage Matrix</span>
          <span className="ml-1 px-2 py-0.5 rounded-full text-[10px] bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 font-mono">
            {difficultSkills.length} Deficits
          </span>
        </button>

        <button
          onClick={() => setActiveTab('signals')}
          className={`px-4 py-2.5 text-xs sm:text-sm font-bold border-b-2 transition-all shrink-0 flex items-center gap-2 ${
            activeTab === 'signals'
              ? 'border-teal-600 text-teal-700 dark:text-teal-400'
              : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          <span>📡</span>
          <span>Industry Trends & Signals</span>
          <span className="ml-1 px-2 py-0.5 rounded-full text-[10px] bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300 font-mono">
            {signals.length}
          </span>
        </button>
      </div>

      {apiError && (
        <div className="mb-6 p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 text-amber-900 dark:text-amber-200 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center gap-2.5">
            <span className="text-base">⚠️</span>
            <div>
              <span className="font-bold">Live Data Disconnected: </span>
              <span>{apiError}</span>
            </div>
          </div>
          <button
            onClick={loadEmployerData}
            className="px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-bold transition-colors cursor-pointer self-start sm:self-auto"
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* TAB 1: AI SIGNAL VALIDATION QUEUE */}
      {activeTab === 'validation' && (
        <div data-demo="employer-validation-queue" className="space-y-6">
          {/* Filtering Controls Bar */}
          <div className="bg-white dark:bg-slate-900 p-4 sm:p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3 mb-3">
              {/* Search Bar */}
              <div className="lg:col-span-2">
                <label className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider block mb-1">
                  Search Skill / Company
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search by skill name, employer, or keyword..."
                    className="w-full pl-8 pr-3 py-2 bg-slate-50 dark:bg-slate-800/80 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg text-xs font-medium focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                  />
                  <span className="absolute left-2.5 top-2.5 text-slate-400 text-xs">🔍</span>
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600 text-xs font-bold"
                    >
                      ✕
                    </button>
                  )}
                </div>
              </div>

              {/* Status Filter */}
              <div>
                <label className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider block mb-1">
                  Validation Status
                </label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800/80 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg text-xs font-medium focus:ring-2 focus:ring-teal-500"
                >
                  <option value="all">All Statuses ({validations.length})</option>
                  <option value="pending">Pending Review ({pendingCount})</option>
                  <option value="confirmed">Confirmed ({confirmedCount})</option>
                  <option value="corrected">Corrected ({correctedCount})</option>
                  <option value="rejected">Rejected ({rejectedCount})</option>
                </select>
              </div>

              {/* District Filter */}
              <div>
                <label className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider block mb-1">
                  Industrial District
                </label>
                <select
                  value={districtFilter}
                  onChange={(e) => setDistrictFilter(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800/80 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg text-xs font-medium focus:ring-2 focus:ring-teal-500"
                >
                  {DISTRICTS.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>

              {/* Industry Filter */}
              <div>
                <label className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider block mb-1">
                  Sector / Industry
                </label>
                <select
                  value={industryFilter}
                  onChange={(e) => setIndustryFilter(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800/80 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg text-xs font-medium focus:ring-2 focus:ring-teal-500"
                >
                  {INDUSTRIES.map((ind) => (
                    <option key={ind} value={ind}>
                      {ind}
                    </option>
                  ))}
                </select>
              </div>

              {/* Demand Urgency Filter */}
              <div>
                <label className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider block mb-1">
                  Demand Urgency
                </label>
                <select
                  value={urgencyFilter}
                  onChange={(e) => setUrgencyFilter(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800/80 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg text-xs font-medium focus:ring-2 focus:ring-teal-500"
                >
                  <option value="all">All Urgencies</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
            </div>


            {/* Sub-bar: Actions and View Toggle */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <span>Showing <strong className="text-slate-800 dark:text-slate-200">{filteredValidations.length}</strong> signals</span>
                {(statusFilter !== 'all' || districtFilter !== 'All Districts' || industryFilter !== 'All Industries' || urgencyFilter !== 'all' || searchQuery) && (
                  <button
                    onClick={() => {
                      setStatusFilter('all');
                      setDistrictFilter('All Districts');
                      setIndustryFilter('All Industries');
                      setUrgencyFilter('all');
                      setSearchQuery('');
                    }}
                    className="text-teal-600 dark:text-teal-400 font-bold hover:underline ml-1"
                  >
                    Reset Filters
                  </button>
                )}

              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleBatchConfirmFiltered}
                  disabled={filteredValidations.filter((v) => v.status === 'pending').length === 0}
                  className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 text-white font-bold rounded-lg text-xs transition-colors shadow-2xs flex items-center gap-1"
                >
                  <span>✓</span>
                  <span>Confirm All Pending Filtered</span>
                </button>

                {/* Table / Cards toggle */}
                <div className="flex items-center bg-slate-100 dark:bg-slate-800 rounded-lg p-0.5 border border-slate-200 dark:border-slate-700 text-xs">
                  <button
                    onClick={() => setViewMode('table')}
                    className={`px-2.5 py-1 rounded-md font-bold transition-all ${
                      viewMode === 'table'
                        ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-2xs'
                        : 'text-slate-500 hover:text-slate-900 dark:text-slate-400'
                    }`}
                  >
                    Table
                  </button>
                  <button
                    onClick={() => setViewMode('cards')}
                    className={`px-2.5 py-1 rounded-md font-bold transition-all ${
                      viewMode === 'cards'
                        ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-2xs'
                        : 'text-slate-500 hover:text-slate-900 dark:text-slate-400'
                    }`}
                  >
                    Cards
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Validation Items List */}
          {filteredValidations.length === 0 ? (
            <div className="bg-white dark:bg-slate-900 rounded-xl p-12 text-center border border-slate-200 dark:border-slate-800 shadow-xs">
              <p className="text-4xl mb-2">🔍</p>
              <h3 className="text-base font-bold text-slate-800 dark:text-slate-200">No skill demand signals found</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm mx-auto">
                No validations match your current filter selection. Try adjusting your search keyword, district, or status.
              </p>
              <button
                onClick={() => {
                  setStatusFilter('all');
                  setDistrictFilter('All Districts');
                  setIndustryFilter('All Industries');
                  setSearchQuery('');
                }}
                className="mt-4 px-4 py-1.5 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-bold rounded-lg text-xs hover:bg-slate-200 transition-colors"
              >
                Clear All Filters
              </button>
            </div>
          ) : viewMode === 'table' ? (
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 font-bold uppercase tracking-wider text-[10px] border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="p-3.5">Skill & Taxonomy</th>
                      <th className="p-3.5">Validating Organization</th>
                      <th className="p-3.5">AI Estimated Demand</th>
                      <th className="p-3.5">Target Proficiency</th>
                      <th className="p-3.5">Validation Status</th>
                      <th className="p-3.5 text-right">Human Sign-Off</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {filteredValidations.map((v) => (
                      <tr key={v.id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors">
                        <td className="p-3.5 max-w-xs">
                          <div className="font-bold text-slate-900 dark:text-white text-xs">{v.skill_name}</div>
                          <div className="flex items-center gap-1.5 mt-1">
                            <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 text-[10px] font-mono font-semibold">
                              {v.skill_category || 'Technology'}
                            </span>
                            {v.nsqf_level && (
                              <span className="px-1.5 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 text-[10px] font-mono font-bold">
                                NSQF L{v.nsqf_level}
                              </span>
                            )}
                          </div>
                          {v.notes && (
                            <p className="text-[11px] text-slate-500 dark:text-slate-400 italic mt-1 line-clamp-2">
                              "{v.notes}"
                            </p>
                          )}
                        </td>

                        <td className="p-3.5 text-slate-700 dark:text-slate-300">
                          <div className="font-semibold text-slate-900 dark:text-white">{v.employer_name}</div>
                          <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 flex items-center gap-1">
                            <span>📍 {v.district || 'Maharashtra'}</span>
                            <span>·</span>
                            <span>{v.industry || 'Industry'}</span>
                          </div>
                        </td>

                        <td className="p-3.5">
                          <span
                            className={`px-2.5 py-1 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider inline-block ${
                              v.demand_level === 'critical'
                                ? 'bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-800'
                                : v.demand_level === 'high'
                                ? 'bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700'
                            }`}
                          >
                            {v.demand_level || 'high'}
                          </span>
                        </td>

                        <td className="p-3.5 font-mono capitalize text-slate-800 dark:text-slate-200 font-semibold">
                          {v.proficiency_required || 'intermediate'}
                        </td>

                        <td className="p-3.5">
                          <span
                            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full font-bold text-[11px] ${
                              v.status === 'confirmed'
                                ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800'
                                : v.status === 'corrected'
                                ? 'bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300 border border-blue-300 dark:border-blue-800'
                                : v.status === 'rejected'
                                ? 'bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-800'
                                : 'bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800'
                            }`}
                          >
                            {v.status === 'confirmed'
                              ? '✓ Confirmed'
                              : v.status === 'corrected'
                              ? '✍️ Corrected'
                              : v.status === 'rejected'
                              ? '✕ Rejected'
                              : '⏳ Pending Review'}
                          </span>
                        </td>

                        <td className="p-3.5 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => handleAction(v.id, 'confirmed')}
                              title="Confirm AI Signal as Accurately Reflecting Industry Need"
                              className={`px-2.5 py-1 font-bold rounded-md text-xs transition-colors shadow-2xs ${
                                v.status === 'confirmed'
                                  ? 'bg-emerald-800 text-white'
                                  : 'bg-emerald-600 hover:bg-emerald-700 text-white'
                              }`}
                            >
                              Confirm
                            </button>
                            <button
                              onClick={() => {
                                setActiveFeedback(v);
                                setCorrectionNote(v.notes || '');
                                setSelectedProficiency(v.proficiency_required || 'advanced');
                              }}
                              title="Refine Proficiency or Add Industry Context"
                              className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-md text-xs transition-colors shadow-2xs"
                            >
                              Correct
                            </button>
                            <button
                              onClick={() => handleAction(v.id, 'rejected')}
                              title="Reject (Skill not needed / replaced)"
                              className="px-2 py-1 bg-slate-200 dark:bg-slate-800 hover:bg-rose-100 dark:hover:bg-rose-950 hover:text-rose-800 dark:hover:text-rose-300 text-slate-700 dark:text-slate-300 font-bold rounded-md text-xs transition-colors"
                            >
                              Reject
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            /* Cards View */
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredValidations.map((v) => (
                <div
                  key={v.id}
                  className="bg-white dark:bg-slate-900 rounded-xl p-5 border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col justify-between hover:shadow-md transition-shadow"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider ${
                          v.demand_level === 'critical'
                            ? 'bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300 border border-rose-300'
                            : v.demand_level === 'high'
                            ? 'bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-300'
                            : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300'
                        }`}
                      >
                        {v.demand_level} Demand
                      </span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          v.status === 'confirmed'
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                            : v.status === 'corrected'
                            ? 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300'
                            : v.status === 'rejected'
                            ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                            : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                        }`}
                      >
                        {v.status}
                      </span>
                    </div>

                    <h4 className="font-bold text-slate-900 dark:text-white text-sm leading-snug">{v.skill_name}</h4>
                    <p className="text-xs text-slate-600 dark:text-slate-300 font-medium mt-1">{v.employer_name}</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      📍 {v.district} · {v.industry}
                    </p>

                    <div className="mt-3 py-2 px-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 text-xs">
                      <div className="flex justify-between items-center text-[11px]">
                        <span className="text-slate-500">Required Level:</span>
                        <span className="font-mono font-bold capitalize text-slate-800 dark:text-slate-200">
                          {v.proficiency_required || 'intermediate'}
                        </span>
                      </div>
                      {v.notes && (
                        <p className="mt-1.5 text-[11px] text-slate-600 dark:text-slate-300 italic border-t border-slate-200/60 dark:border-slate-700/60 pt-1.5">
                          "{v.notes}"
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-end gap-1.5">
                    <button
                      onClick={() => handleAction(v.id, 'confirmed')}
                      className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-md text-xs transition-colors"
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() => {
                        setActiveFeedback(v);
                        setCorrectionNote(v.notes || '');
                        setSelectedProficiency(v.proficiency_required || 'advanced');
                      }}
                      className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-md text-xs transition-colors"
                    >
                      Correct
                    </button>
                    <button
                      onClick={() => handleAction(v.id, 'rejected')}
                      className="px-2.5 py-1 bg-slate-100 dark:bg-slate-800 hover:bg-rose-100 text-slate-600 hover:text-rose-700 font-bold rounded-md text-xs transition-colors"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: SUBMIT SKILL DEMAND PORTAL (PHASE 14) */}
      {activeTab === 'demand' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Panel: Submission Form */}
          <div className="lg:col-span-7 bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
            <div className="flex items-center justify-between gap-2 mb-2 pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <span className="text-xl">🚀</span>
                <div>
                  <h3 className="font-bold text-slate-900 dark:text-white text-base">
                    Submit Industry Hiring & Skill Demand
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Direct employer requirements feed into state curriculum updates and skill-gap intelligence
                  </p>
                </div>
              </div>
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800 shrink-0">
                Employer Submitted — Pending Validation
              </span>
            </div>

            <form onSubmit={handleDemandSubmit} className="space-y-4 text-xs mt-4">
              {/* Organization & Industry */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">
                    Company / Organization Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={demandForm.employer_name}
                    onChange={(e) => setDemandForm({ ...demandForm, employer_name: e.target.value, company_name: e.target.value })}
                    placeholder="e.g. Tata Consultancy Services, Bajaj Auto, KPIT"
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg font-medium focus:ring-2 focus:ring-teal-500"
                  />
                </div>

                <div>
                  <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Industry Sector *</label>
                  <select
                    value={demandForm.industry}
                    onChange={(e) => setDemandForm({ ...demandForm, industry: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg font-medium focus:ring-2 focus:ring-teal-500"
                  >
                    {INDUSTRIES.filter((i) => i !== 'All Industries').map((ind) => (
                      <option key={ind} value={ind}>
                        {ind}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Corporate GSTIN Verification (Phase 34) */}
              <div className="p-3 rounded-lg bg-teal-50/50 dark:bg-teal-950/20 border border-teal-200 dark:border-teal-800/40">
                <div className="flex items-center justify-between mb-1.5">
                  <label className="font-bold text-teal-900 dark:text-teal-200 flex items-center gap-1.5">
                    <span>Corporate GSTIN Verification</span>
                    <span className="text-[10px] font-normal text-teal-600 dark:text-teal-400">(Optional — unlocks Verified Enterprise badge)</span>
                  </label>
                  {demandForm.gstin && demandForm.gstin.length === 15 && (
                    <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-950/60 px-2 py-0.5 rounded">
                      ✓ 15-char GSTIN
                    </span>
                  )}
                </div>
                <input
                  type="text"
                  maxLength={15}
                  value={demandForm.gstin || ''}
                  onChange={(e) => setDemandForm({ ...demandForm, gstin: e.target.value.toUpperCase() })}
                  placeholder="e.g. 27AABCU9603R1ZN (State Code 27 for Maharashtra)"
                  className="w-full px-3 py-1.5 bg-white dark:bg-slate-900 border border-teal-300 dark:border-teal-700 text-slate-900 dark:text-white rounded-lg font-mono text-xs focus:ring-2 focus:ring-teal-500"
                />
              </div>

              {/* District & Role Title */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">
                    Hiring Location / District *
                  </label>
                  <select
                    value={demandForm.district}
                    onChange={(e) => setDemandForm({ ...demandForm, district: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg font-medium focus:ring-2 focus:ring-teal-500"
                  >
                    {DISTRICTS.filter((d) => d !== 'All Districts').map((dist) => (
                      <option key={dist} value={dist}>
                        {dist}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">
                    Target Job Role / Designation *
                  </label>
                  <input
                    type="text"
                    required
                    value={demandForm.role_title}
                    onChange={(e) => setDemandForm({ ...demandForm, role_title: e.target.value, job_role: e.target.value })}
                    placeholder="e.g. EV Powertrain Diagnostics Specialist, Cloud Security Analyst"
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg font-medium focus:ring-2 focus:ring-teal-500"
                  />
                </div>
              </div>

              {/* In-Demand Skills Selector */}
              <div>
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">
                  Required Competencies & Skills * (Select or Type Custom)
                </label>
                {/* Active Skill Chips */}
                <div className="flex flex-wrap gap-1.5 p-2.5 bg-slate-50 dark:bg-slate-800/90 rounded-lg border border-slate-300 dark:border-slate-700 mb-2 min-h-12 items-center">
                  {demandForm.selectedSkills.map((sk) => (
                    <span
                      key={sk}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-teal-100 dark:bg-teal-950 text-teal-900 dark:text-teal-200 border border-teal-300 dark:border-teal-800 font-bold text-xs"
                    >
                      {sk}
                      <button
                        type="button"
                        onClick={() => handleRemoveSkillFromForm(sk)}
                        className="text-teal-700 hover:text-teal-900 font-bold"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  {demandForm.selectedSkills.length === 0 && (
                    <span className="text-slate-400 italic text-[11px]">No skills selected yet. Choose from below or add custom.</span>
                  )}
                </div>

                {/* Custom Skill Input */}
                <div className="flex items-center gap-2 mb-2">
                  <input
                    type="text"
                    value={demandForm.customSkillInput}
                    onChange={(e) => setDemandForm({ ...demandForm, customSkillInput: e.target.value })}
                    onKeyDown={handleAddCustomSkill}
                    placeholder="Type custom skill & press enter..."
                    className="flex-1 px-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg text-xs focus:ring-2 focus:ring-teal-500"
                  />
                  <button
                    type="button"
                    onClick={handleAddCustomSkill}
                    className="px-3 py-1.5 bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200 font-bold rounded-lg text-xs hover:bg-slate-300"
                  >
                    + Add
                  </button>
                </div>

                {/* Suggested Quick Chips */}
                <div className="flex flex-wrap gap-1">
                  <span className="text-[10px] text-slate-400 mr-1 self-center">Popular:</span>
                  {AVAILABLE_TAXONOMY_SKILLS.slice(0, 10).map((sk) => (
                    <button
                      key={sk}
                      type="button"
                      onClick={() => handleAddSkillToForm(sk)}
                      className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                        demandForm.selectedSkills.includes(sk)
                          ? 'bg-slate-200 dark:bg-slate-700 text-slate-400 cursor-default'
                          : 'bg-slate-100 dark:bg-slate-800 hover:bg-teal-50 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700'
                      }`}
                    >
                      + {sk}
                    </button>
                  ))}
                </div>
              </div>

              {/* Proficiency, Experience, Urgency, Open Positions */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div>
                  <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Preferred Proficiency</label>
                  <select
                    value={demandForm.proficiency_required}
                    onChange={(e) => setDemandForm({ ...demandForm, proficiency_required: e.target.value, preferred_proficiency: e.target.value })}
                    className="w-full px-2.5 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg font-medium"
                  >
                    <option value="beginner">Beginner / Foundational</option>
                    <option value="intermediate">Intermediate</option>
                    <option value="advanced">Advanced / Expert</option>
                  </select>
                </div>

                <div>
                  <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Experience Level</label>
                  <select
                    value={demandForm.experience_level}
                    onChange={(e) => setDemandForm({ ...demandForm, experience_level: e.target.value })}
                    className="w-full px-2.5 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg font-medium"
                  >
                    <option value="Entry Level (0-1 yrs)">Entry Level (0-1 yrs)</option>
                    <option value="Mid Level (2-4 yrs)">Mid Level (2-4 yrs)</option>
                    <option value="Senior (5+ yrs)">Senior (5+ yrs)</option>
                  </select>
                </div>

                <div>
                  <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Hiring Timeline</label>
                  <select
                    value={demandForm.hiring_timeline}
                    onChange={(e) => setDemandForm({ ...demandForm, hiring_timeline: e.target.value, urgency: e.target.value.toLowerCase().replace(/[^a-z0-9]/g, '_') })}
                    className="w-full px-2.5 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg font-medium"
                  >
                    <option value="Immediate (0-30 days)">Immediate (&lt;30d)</option>
                    <option value="1-3 Months">1-3 Months</option>
                    <option value="3-6 Months">3-6 Months</option>
                  </select>
                </div>

                <div>
                  <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Number of Openings</label>
                  <input
                    type="number"
                    min="1"
                    max="1000"
                    value={demandForm.positions_count}
                    onChange={(e) => setDemandForm({ ...demandForm, positions_count: Number(e.target.value), openings_count: Number(e.target.value) })}
                    className="w-full px-2.5 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg font-medium"
                  />
                </div>
              </div>

              {/* Qualitative Hiring Bottleneck / Additional Requirements */}
              <div>
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">
                  Additional Requirements / Specific Hiring Challenges (Optional):
                </label>
                <textarea
                  value={demandForm.hiring_challenge}
                  onChange={(e) => setDemandForm({ ...demandForm, hiring_challenge: e.target.value, additional_requirements: e.target.value })}
                  placeholder="e.g. Candidates understand theoretical concepts but lack practical lab experience with high-voltage testing or CAN bus diagnostics..."
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg h-20 focus:ring-2 focus:ring-teal-500 font-normal"
                />
              </div>

              {/* Submit Button */}
              <div className="pt-2">
                <button
                  type="submit"
                  disabled={submittingDemand}
                  className="w-full py-2.5 bg-slate-900 dark:bg-teal-600 hover:bg-slate-800 dark:hover:bg-teal-700 disabled:opacity-50 text-white font-bold rounded-lg text-xs shadow-sm transition-colors flex items-center justify-center gap-2 cursor-pointer"
                >
                  {submittingDemand ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Syncing Demand into State Intelligence Loop...</span>
                    </>
                  ) : (
                    <>
                      <span>📡</span>
                      <span>Submit Demand (Pending State Validation)</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>

          {/* Right Panel: Live Preview & Demand Stream */}
          <div className="lg:col-span-5 space-y-4">
            {/* Live Preview Card */}
            <div className="bg-gradient-to-br from-teal-900 to-slate-900 text-white p-5 rounded-xl border border-teal-700/50 shadow-sm">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-mono uppercase tracking-wider text-teal-300 font-bold block">
                  Live Demand Preview
                </span>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  Pending Validation
                </span>
              </div>
              <h4 className="font-black text-base tracking-tight">
                {demandForm.role_title || 'Role Title (e.g. Senior AI Engineer)'}
              </h4>
              <p className="text-xs text-teal-100 mt-0.5">
                {demandForm.employer_name} · 📍 {demandForm.district} ({demandForm.industry})
              </p>

              <div className="mt-3 flex flex-wrap gap-1.5">
                {demandForm.selectedSkills.map((s) => (
                  <span
                    key={s}
                    className="px-2 py-0.5 rounded bg-teal-800/80 text-teal-200 font-mono text-[10px] font-semibold border border-teal-600/60"
                  >
                    {s}
                  </span>
                ))}
              </div>

              <div className="mt-4 pt-3 border-t border-teal-800/60 flex items-center justify-between text-xs font-mono">
                <span>{demandForm.positions_count} Vacancies</span>
                <span className="capitalize px-2 py-0.5 rounded bg-amber-900/80 text-amber-200 border border-amber-600/60">
                  {demandForm.hiring_timeline}
                </span>
                <span>{demandForm.experience_level}</span>
              </div>
            </div>

            {/* Active Demand Signals List */}
            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800 mb-3">
                <div>
                  <h4 className="font-bold text-slate-900 dark:text-white text-xs uppercase tracking-wider">
                    Employer Hiring Requirements ({demands.length})
                  </h4>
                  <p className="text-[10px] text-slate-500">First-party industrial demand feed</p>
                </div>
                <span className="text-[10px] font-mono text-teal-600 font-bold">Live Stream</span>
              </div>

              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {demands.map((d) => {
                  const statusUpper = (d.validation_status || d.status || 'pending').toUpperCase();
                  const isVal = statusUpper === 'VALIDATED' || d.status === 'active';
                  const isRej = statusUpper === 'REJECTED';

                  return (
                    <div
                      key={d.id}
                      className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 text-xs space-y-2"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h5 className="font-bold text-slate-900 dark:text-white text-xs">
                            {d.job_role || d.role_title}
                          </h5>
                          <p className="text-[11px] text-slate-600 dark:text-slate-300 mt-0.5">
                            {d.company_name || d.employer_name} · 📍 {d.district} ({d.industry})
                          </p>
                        </div>
                        <span className="px-1.5 py-0.5 rounded bg-purple-100 dark:bg-purple-950 text-purple-800 dark:text-purple-300 font-mono text-[10px] font-bold shrink-0">
                          {d.openings_count || d.positions_count || 1} seats
                        </span>
                      </div>

                      <div className="flex flex-wrap gap-1">
                        {(d.required_skills || d.skills || []).map((sk, idx) => (
                          <span
                            key={idx}
                            className="px-1.5 py-0.5 rounded bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-[10px] font-medium border border-slate-200 dark:border-slate-600"
                          >
                            {typeof sk === 'object' ? sk.name : sk}
                          </span>
                        ))}
                      </div>

                      {/* Status & Provenance Badges */}
                      <div className="flex items-center justify-between pt-1 border-t border-slate-200/60 dark:border-slate-700/60 text-[10px]">
                        <span
                          className={`font-mono font-bold px-2 py-0.5 rounded uppercase ${
                            isVal
                              ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                              : isRej
                              ? 'bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800'
                              : 'bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800'
                          }`}
                        >
                          {isVal ? '✓ Validated Demand' : isRej ? '✕ Rejected' : '⏳ Pending Validation'}
                        </span>
                        <span className="text-slate-400 font-mono">
                          {d.source === 'EMPLOYER_SUBMITTED' ? 'Employer Direct' : 'Demo Benchmark'}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: HARD-TO-HIRE SKILLS & TALENT SHORTAGE MATRIX */}
      {activeTab === 'difficult' && (
        <div data-demo="employer-difficult-skills" className="space-y-6">
          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Deficit Intensity Chart */}
            <div className="lg:col-span-7 bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
              <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100 dark:border-slate-800">
                <div>
                  <h3 className="font-bold text-slate-900 dark:text-white text-sm">
                    Hardest-to-Hire Competencies vs. Average Days to Fill
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Deficit score (0-100) indexed against duration positions remain vacant in Maharashtra
                  </p>
                </div>
                <span className="text-xs font-mono text-rose-600 font-bold">{isDemoMode ? 'Benchmark Baseline: 28d' : 'Deficit Indices'}</span>
              </div>

              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={difficultChartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 10, fill: '#64748b' }}
                      angle={-15}
                      textAnchor="end"
                    />
                    <YAxis tick={{ fontSize: 10, fill: '#64748b' }} domain={[0, 100]} />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="bg-slate-900 text-white p-3 rounded-lg text-xs shadow-lg border border-slate-700">
                              <p className="font-bold">{data.fullName}</p>
                              <p className="text-teal-300 font-mono mt-1">Shortage Deficit: {data.deficit}%</p>
                              <p className="text-amber-300 font-mono">Avg Time to Fill: {data.daysToFill != null ? `${data.daysToFill} days` : 'Unavailable'}</p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                    <Bar dataKey="deficit" name="Deficit Index (%)" fill="#0d9488" radius={[4, 4, 0, 0]}>
                      {difficultChartData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={entry.deficit > 80 ? '#e11d48' : entry.deficit > 75 ? '#d97706' : '#0d9488'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Time-to-Fill Comparison Table */}
            <div className="lg:col-span-5 bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col justify-between">
              <div>
                <h3 className="font-bold text-slate-900 dark:text-white text-sm mb-1">
                  Hiring Latency Impact by Industrial Sector
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
                  Lag in technical recruitment directly throttles state manufacturing and IT GDP output
                </p>

                <div className="space-y-3">
                  {isDemoMode ? (
                    <>
                      <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-800 text-xs">
                        <div className="flex justify-between items-center font-bold text-rose-950 dark:text-rose-200">
                          <span>🤖 AI & Machine Learning</span>
                          <span className="font-mono">64 Days Avg [Demo Reference]</span>
                        </div>
                        <p className="text-[11px] text-rose-800 dark:text-rose-300 mt-1">
                          Critical shortage of RAG, Vector Search, and LLMOps engineers across Pune and Mumbai.
                        </p>
                      </div>

                      <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/50 border border-amber-200 dark:border-amber-800 text-xs">
                        <div className="flex justify-between items-center font-bold text-amber-950 dark:text-amber-200">
                          <span>⚡ Electric Vehicles & Batteries</span>
                          <span className="font-mono">58 Days Avg [Demo Reference]</span>
                        </div>
                        <p className="text-[11px] text-amber-800 dark:text-amber-300 mt-1">
                          Automotive hubs in Chakan & Sambhajinagar report high vacancy rates for BMS technicians.
                        </p>
                      </div>

                      <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800 text-xs">
                        <div className="flex justify-between items-center font-bold text-blue-950 dark:text-blue-200">
                          <span>🏭 Smart Manufacturing (IIoT)</span>
                          <span className="font-mono">47 Days Avg [Demo Reference]</span>
                        </div>
                        <p className="text-[11px] text-blue-800 dark:text-blue-300 mt-1">
                          SCADA, PLC, and industrial automation engineers required for Industry 4.0 plant retrofits.
                        </p>
                      </div>
                    </>
                  ) : (
                    <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-xs">
                      <div className="flex justify-between items-center font-bold text-slate-900 dark:text-white">
                        <span>Live Hiring Latency Indexing</span>
                        <span className="font-mono text-teal-600 dark:text-teal-400">Telemetry Pending</span>
                      </div>
                      <p className="text-[11px] text-slate-600 dark:text-slate-300 mt-1 leading-relaxed">
                        Sector time-to-fill averages require employer-recorded position closure timestamps. As vacancies are fulfilled through SkillSetuAI, real duration telemetry will be indexed here.
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 text-center">
                {role === 'ADMIN' ? (
                  <Link
                    to="/institute"
                    className="text-xs font-bold text-teal-600 dark:text-teal-400 hover:underline"
                  >
                    View State Institute Curriculum Alignment Recommendations →
                  </Link>
                ) : (
                  <Link
                    to="/student/copilot?role=employer&q=What+is+the+curriculum+alignment+and+talent+supply+for+Automation+Engineers+in+Maharashtra%3F"
                    className="text-xs font-bold text-teal-600 dark:text-teal-400 hover:underline"
                  >
                    Ask AI Copilot for Institute Talent Alignment & Supply →
                  </Link>
                )}
              </div>
            </div>
          </div>

          {/* Deep-Dive Deficit Cards */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wider">
              High-Deficit Competency Breakdown & Training Interventions
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {difficultSkills.map((sk) => (
                <div
                  key={sk.skill_id}
                  className="bg-white dark:bg-slate-900 rounded-xl p-5 border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div>
                        <h4 className="font-bold text-slate-900 dark:text-white text-sm">{sk.skill_name}</h4>
                        <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
                          <span className="font-medium text-teal-600">{sk.category}</span>
                          <span>·</span>
                          <span>NSQF Level {sk.nsqf_level}</span>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <span className="text-base font-black font-mono text-rose-600 dark:text-rose-400">
                          {sk.deficit_score}%
                        </span>
                        <p className="text-[10px] text-slate-400 uppercase font-semibold">Deficit Score</p>
                      </div>
                    </div>

                    {/* Progress bar */}
                    <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden my-2.5">
                      <div
                        className={`h-full rounded-full ${
                          sk.deficit_score > 80 ? 'bg-rose-500' : sk.deficit_score > 75 ? 'bg-amber-500' : 'bg-teal-500'
                        }`}
                        style={{ width: `${sk.deficit_score}%` }}
                      />
                    </div>

                    <div className="space-y-2 text-xs mt-3">
                      <div>
                        <span className="font-bold text-slate-700 dark:text-slate-300 block text-[11px]">
                          Root Cause of Shortage:
                        </span>
                        <p className="text-slate-600 dark:text-slate-400 text-[11px] leading-relaxed">
                          {sk.shortage_reason}
                        </p>
                      </div>

                      <div className="p-3 rounded-lg bg-teal-50/70 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800/80">
                        <span className="font-bold text-teal-900 dark:text-teal-300 block text-[11px] mb-0.5">
                          💡 Recommended Academic Intervention:
                        </span>
                        <p className="text-teal-800 dark:text-teal-200 text-[11px] leading-relaxed">
                          {sk.suggested_intervention || 'Intervention details unavailable'}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500">
                    <span>
                      Impacted Districts: <strong className="text-slate-800 dark:text-slate-200">{sk.top_districts?.length ? sk.top_districts.join(', ') : 'Statewide'}</strong>
                    </span>
                    <span className="font-mono font-bold text-amber-600">{sk.avg_days_to_fill != null ? `${sk.avg_days_to_fill}d avg fill time` : 'Fill time unavailable'}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: INDUSTRY TRENDS & TECHNOLOGY SIGNALS */}
      {activeTab === 'signals' && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
            <h3 className="font-bold text-slate-900 dark:text-white text-base">
              Emerging Industry & Technology Intelligence Signals
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-2xl">
              Signals extracted from industrial announcements, government technology initiatives, and OEM investments across Maharashtra.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {loading ? (
              <div className="col-span-3 text-center py-12 text-slate-400">
                <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                <p className="text-xs">Loading industry signals...</p>
              </div>
            ) : apiError ? (
              <div className="col-span-3 text-center py-12 text-rose-500 bg-rose-50 dark:bg-rose-950/30 rounded-xl border border-rose-200 dark:border-rose-800">
                <p className="text-sm font-semibold">Failed to load industry signals.</p>
                <p className="text-xs text-slate-400 mt-1">{apiError}</p>
                <button
                  onClick={loadEmployerData}
                  className="mt-3 px-3 py-1 bg-white dark:bg-slate-800 border border-rose-300 rounded text-xs font-semibold cursor-pointer"
                >
                  Retry
                </button>
              </div>
            ) : signals.length > 0 ? (
              signals.map((sig) => (
                <div key={sig.id || sig.title} className="flex flex-col justify-between">
                  <SignalCard signal={sig} />
                </div>
              ))
            ) : (
              <div className="col-span-3 text-center py-12 text-slate-400 bg-white dark:bg-slate-900 rounded-xl border border-dashed border-slate-200 dark:border-slate-800">
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">No current industry signals available.</p>
                <p className="text-xs text-slate-400 mt-1">Verified intelligence extracted from industrial announcements will appear here once published.</p>
              </div>
            )}
          </div>

        </div>
      )}

      {/* CORRECTION / REFINEMENT MODAL */}
      {activeFeedback && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-white dark:bg-slate-900 rounded-xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 dark:border-slate-800">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800 mb-4">
              <div>
                <span className="text-[10px] font-mono uppercase text-teal-600 font-bold block">
                  Authoritative Calibration
                </span>
                <h3 className="font-bold text-slate-900 dark:text-white text-base">
                  Refine Signal: "{activeFeedback.skill_name}"
                </h3>
              </div>
              <button
                onClick={() => setActiveFeedback(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-lg font-bold"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">
                  Required Competency Level for Candidate Hiring:
                </label>
                <select
                  value={selectedProficiency}
                  onChange={(e) => setSelectedProficiency(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg font-semibold focus:ring-2 focus:ring-teal-500"
                >
                  <option value="beginner">Beginner (Foundational Awareness / Theory)</option>
                  <option value="intermediate">Intermediate (Hands-On Implementation / Lab)</option>
                  <option value="advanced">Advanced (Production-Grade / Architect / Safety Certified)</option>
                </select>
              </div>

              <div>
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">
                  Industry Specification / Feedback Note:
                </label>
                <textarea
                  value={correctionNote}
                  onChange={(e) => setCorrectionNote(e.target.value)}
                  placeholder="e.g. Candidates must have experience with RAG pipelines and vector DBs rather than just standard prompt engineering..."
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg h-24 font-normal focus:ring-2 focus:ring-teal-500"
                />
              </div>

              {/* Preset chips */}
              <div>
                <span className="text-[10px] text-slate-400 block mb-1 font-semibold uppercase">
                  Quick Presets:
                </span>
                <div className="flex flex-wrap gap-1">
                  {PRESET_FEEDBACK_NOTES.map((note, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setCorrectionNote(note)}
                      className="px-2 py-1 bg-slate-100 dark:bg-slate-800 hover:bg-teal-50 hover:text-teal-800 text-[10px] text-slate-700 dark:text-slate-300 rounded border border-slate-200 dark:border-slate-700 text-left"
                    >
                      "{note.slice(0, 45)}…"
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-end gap-2">
              <button
                onClick={() => setActiveFeedback(null)}
                className="px-4 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-bold rounded-lg text-xs"
              >
                Cancel
              </button>
              <button
                onClick={() =>
                  handleAction(
                    activeFeedback.id,
                    'corrected',
                    correctionNote,
                    selectedProficiency
                  )
                }
                className="px-5 py-2 bg-slate-900 dark:bg-teal-600 hover:bg-slate-800 dark:hover:bg-teal-700 text-white font-bold rounded-lg text-xs shadow-xs"
              >
                Save Industry Signal
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
