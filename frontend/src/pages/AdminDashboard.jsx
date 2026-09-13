import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import Layout from '../components/Layout';
import StatCard from '../components/StatCard';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

const DISTRICTS = [
  'All Districts',
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

const ROLES = [
  'All Career Roles',
  'AI Engineer',
  'Data Analyst',
  'Data Scientist',
  'EV Technician',
  'Cloud Architect',
  'Cybersecurity Analyst',
  'Robotics Engineer',
  'Full Stack Developer',
  'IoT Engineer',
  'Smart Manufacturing Engineer',
];

const INDUSTRIES = [
  'All Industries',
  'IT & Software',
  'Automotive & EV',
  'Renewable Energy',
  'Healthcare',
  'Banking & BFSI',
  'Manufacturing & Industry 4.0',
  'Electronics & Semiconductor',
  'Logistics & Supply Chain',
  'Pharmaceuticals',
];

export default function AdminDashboard() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const VALID_ADMIN_TABS = ['overview', 'students', 'employers', 'institutes', 'gov', 'industry'];
  const urlTab = searchParams.get('tab');
  const adminTab = urlTab && VALID_ADMIN_TABS.includes(urlTab) ? urlTab : 'overview';

  const handleTabChange = (newTab) => {
    const newParams = new URLSearchParams(searchParams);
    newParams.set('tab', newTab);
    setSearchParams(newParams, { replace: true });
  };

  // Admin Key State (optional custom header override for specialized environments)
  const [adminKey, setAdminKey] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.localStorage?.getItem('skillsetu_admin_key') || 'demo-admin-key-2026';
    }
    return 'demo-admin-key-2026';
  });

  // Student Data & Stats State (Phase 12 & 13)
  const [stats, setStats] = useState(null);
  const [assessments, setAssessments] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  // Student Filter State
  const [sourceFilter, setSourceFilter] = useState('all'); // 'all' | 'USER_SUBMITTED' | 'DEMO_SYNTHETIC'
  const [districtFilter, setDistrictFilter] = useState('All Districts');
  const [careerGoalFilter, setCareerGoalFilter] = useState('All Career Roles');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(0);
  const pageSize = 15;

  // Student Detailed Modal State
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [inspectModalOpen, setInspectModalOpen] = useState(false);
  const [actionMessage, setActionMessage] = useState(null);

  // Employer Demands State (Phase 14)
  const [employerDemands, setEmployerDemands] = useState([]);
  const [empTotalCount, setEmpTotalCount] = useState(0);
  const [empLoading, setEmpLoading] = useState(false);
  const [empDistrictFilter, setEmpDistrictFilter] = useState('All Districts');
  const [empIndustryFilter, setEmpIndustryFilter] = useState('All Industries');
  const [empStatusFilter, setEmpStatusFilter] = useState('all'); // 'all' | 'PENDING' | 'VALIDATED' | 'REJECTED'
  const [empSourceFilter, setEmpSourceFilter] = useState('all'); // 'all' | 'EMPLOYER_SUBMITTED' | 'DEMO_SYNTHETIC'
  const [empSearchTerm, setEmpSearchTerm] = useState('');
  const [selectedDemand, setSelectedDemand] = useState(null);
  const [inspectDemandModalOpen, setInspectDemandModalOpen] = useState(false);
  const [adminNotesInput, setAdminNotesInput] = useState('');

  // Institute Courses State (Phase 25)
  const [adminCourses, setAdminCourses] = useState([]);
  const [coursesLoading, setCoursesLoading] = useState(false);
  const [courseStats, setCourseStats] = useState({ total: 0, user_submitted_count: 0, demo_synthetic_count: 0 });
  const [courseDistrictFilter, setCourseDistrictFilter] = useState('All Districts');
  const [courseCategoryFilter, setCourseCategoryFilter] = useState('all');
  const [courseSourceFilter, setCourseSourceFilter] = useState('all');
  const [courseStatusFilter, setCourseStatusFilter] = useState('all');
  const [courseSearchTerm, setCourseSearchTerm] = useState('');
  const [selectedAdminCourse, setSelectedAdminCourse] = useState(null);
  const [inspectCourseModalOpen, setInspectCourseModalOpen] = useState(false);

  // Government Opportunities State (Phase 15)
  const [govOpportunities, setGovOpportunities] = useState([]);
  const [govLoading, setGovLoading] = useState(false);
  const [govStats, setGovStats] = useState({ total: 0, active_count: 0, inactive_count: 0, demo_count: 0 });
  const [govDistrictFilter, setGovDistrictFilter] = useState('all');
  const [govTypeFilter, setGovTypeFilter] = useState('all');
  const [govStatusFilter, setGovStatusFilter] = useState('all');
  const [govSearchTerm, setGovSearchTerm] = useState('');
  const [govAddModalOpen, setGovAddModalOpen] = useState(false);
  const [selectedGovOpp, setSelectedGovOpp] = useState(null);
  const [inspectGovModalOpen, setInspectGovModalOpen] = useState(false);

  // Industry Signals & Intelligence State (Phase 26)
  const [adminSignals, setAdminSignals] = useState([]);
  const [signalsLoading, setSignalsLoading] = useState(false);
  const [signalStats, setSignalStats] = useState({
    total: 0,
    approved_count: 0,
    pending_count: 0,
    rejected_count: 0,
    active_count: 0,
    fresh_count: 0,
  });
  const [ingestionStatus, setIngestionStatus] = useState(null);
  const [ingestRunning, setIngestRunning] = useState(false);
  const [signalCategoryFilter, setSignalCategoryFilter] = useState('all');
  const [signalIndustryFilter, setSignalIndustryFilter] = useState('all');
  const [signalStatusFilter, setSignalStatusFilter] = useState('all');
  const [signalFreshnessFilter, setSignalFreshnessFilter] = useState('all');
  const [signalSearchTerm, setSignalSearchTerm] = useState('');
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [inspectSignalModalOpen, setInspectSignalModalOpen] = useState(false);
  const [signalAdminNotesInput, setSignalAdminNotesInput] = useState('');
  const [governanceData, setGovernanceData] = useState(null);

  // Load Student Assessment Data & Data Governance
  const fetchData = useCallback(() => {
    setLoading(true);
    setAuthError(null);

    const params = {
      limit: pageSize,
      offset: page * pageSize,
    };

    if (sourceFilter !== 'all') params.source = sourceFilter;
    if (districtFilter !== 'All Districts') params.district = districtFilter;
    if (careerGoalFilter !== 'All Career Roles') params.career_goal = careerGoalFilter;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    if (searchTerm.trim()) params.search = searchTerm.trim();

    Promise.allSettled([
      api.getAdminAssessmentStats(adminKey),
      api.getAdminAssessments(params, adminKey),
      api.getDataGovernance(adminKey),
    ]).then(([statsRes, listRes, govRes]) => {
      if (statsRes.status === 'fulfilled' && statsRes.value?.status === 'success') {
        setStats(statsRes.value);
      } else if (statsRes.status === 'rejected' && statsRes.reason?.message?.includes('401')) {
        setAuthError('Unauthorized: Invalid or missing administrator key.');
      }

      if (listRes.status === 'fulfilled' && listRes.value?.status === 'success') {
        setAssessments(listRes.value.assessments || []);
        setTotalCount(listRes.value.total || 0);
      } else if (listRes.status === 'rejected' && listRes.reason?.message?.includes('401')) {
        setAuthError('Unauthorized: Invalid or missing administrator key.');
      }

      if (govRes.status === 'fulfilled' && govRes.value?.status === 'success') {
        setGovernanceData(govRes.value);
      }

      setLoading(false);
    });
  }, [adminKey, sourceFilter, districtFilter, careerGoalFilter, dateFrom, dateTo, searchTerm, page]);


  // Load Employer Demands Data (Phase 14)
  const fetchEmployerData = useCallback(() => {
    setEmpLoading(true);
    const params = {};
    if (empDistrictFilter !== 'All Districts') params.district = empDistrictFilter;
    if (empIndustryFilter !== 'All Industries') params.industry = empIndustryFilter;
    if (empStatusFilter !== 'all') params.status = empStatusFilter;
    if (empSourceFilter !== 'all') params.source = empSourceFilter;
    if (empSearchTerm.trim()) params.search = empSearchTerm.trim();

    api.getAdminEmployerDemands(params, adminKey)
      .then((res) => {
        if (res?.status === 'success') {
          setEmployerDemands(res.demands || []);
          setEmpTotalCount(res.total || 0);
        }
      })
      .catch((err) => {
        if (err?.message?.includes('401')) {
          setAuthError('Unauthorized: Invalid or missing administrator key.');
        }
      })
      .finally(() => {
        setEmpLoading(false);
      });
  }, [adminKey, empDistrictFilter, empIndustryFilter, empStatusFilter, empSourceFilter, empSearchTerm]);

  // Load Institute Courses Data (Phase 25)
  const fetchAdminCourses = useCallback(() => {
    setCoursesLoading(true);
    const params = {};
    if (courseDistrictFilter !== 'All Districts') params.district = courseDistrictFilter;
    if (courseCategoryFilter !== 'all') params.category = courseCategoryFilter;
    if (courseSourceFilter !== 'all') params.source = courseSourceFilter;
    if (courseStatusFilter !== 'all') params.status = courseStatusFilter;
    if (courseSearchTerm.trim()) params.search = courseSearchTerm.trim();

    api.getAdminCourses(params, adminKey)
      .then((res) => {
        if (res?.status === 'success') {
          setAdminCourses(res.courses || []);
          setCourseStats({
            total: res.total || 0,
            user_submitted_count: res.user_submitted_count || 0,
            demo_synthetic_count: res.demo_synthetic_count || 0,
          });
        }
      })
      .catch((err) => {
        if (err?.message?.includes('401')) {
          setAuthError('Unauthorized: Invalid or missing administrator key.');
        }
      })
      .finally(() => {
        setCoursesLoading(false);
      });
  }, [adminKey, courseDistrictFilter, courseCategoryFilter, courseSourceFilter, courseStatusFilter, courseSearchTerm]);

  // Load Government Opportunities Data (Phase 15)
  const fetchGovData = useCallback(() => {
    setGovLoading(true);
    const params = {};
    if (govDistrictFilter !== 'all') params.district = govDistrictFilter;
    if (govTypeFilter !== 'all') params.opportunity_type = govTypeFilter;
    if (govStatusFilter !== 'all') params.status = govStatusFilter;
    if (govSearchTerm.trim()) params.search = govSearchTerm.trim();

    api.getAdminGovOpportunities(params, adminKey)
      .then((res) => {
        if (res?.status === 'success') {
          setGovOpportunities(res.opportunities || []);
          setGovStats({ total: res.total || 0, active_count: res.active_count || 0, inactive_count: res.inactive_count || 0, demo_count: res.demo_count || 0 });
        }
      })
      .catch((err) => {
        if (err?.message?.includes('401')) {
          setAuthError('Unauthorized: Invalid or missing administrator key.');
        }
      })
      .finally(() => setGovLoading(false));
  }, [adminKey, govDistrictFilter, govTypeFilter, govStatusFilter, govSearchTerm]);

  // Load Industry Signals & Ingestion Data (Phase 26)
  const fetchAdminSignals = useCallback(() => {
    setSignalsLoading(true);
    const params = {};
    if (signalCategoryFilter !== 'all') params.category = signalCategoryFilter;
    if (signalIndustryFilter !== 'all') params.industry = signalIndustryFilter;
    if (signalStatusFilter !== 'all') params.status = signalStatusFilter;
    if (signalFreshnessFilter !== 'all') params.freshness = signalFreshnessFilter;
    if (signalSearchTerm.trim()) params.search = signalSearchTerm.trim();

    Promise.allSettled([
      api.getAdminIndustrySignals(params, adminKey),
      api.getAdminIndustryIngestionStatus(adminKey),
    ]).then(([signalsRes, statusRes]) => {
      if (signalsRes.status === 'fulfilled' && signalsRes.value?.status === 'success') {
        setAdminSignals(signalsRes.value.signals || []);
        setSignalStats({
          total: signalsRes.value.total || 0,
          approved_count: signalsRes.value.approved_count || 0,
          pending_count: signalsRes.value.pending_count || 0,
          rejected_count: signalsRes.value.rejected_count || 0,
          active_count: signalsRes.value.active_count || 0,
          fresh_count: signalsRes.value.fresh_count || 0,
        });
      }
      if (statusRes.status === 'fulfilled' && statusRes.value?.status === 'success') {
        setIngestionStatus(statusRes.value.ingestion_status || null);
      }
      setSignalsLoading(false);
    }).catch(() => {
      setSignalsLoading(false);
    });
  }, [adminKey, signalCategoryFilter, signalIndustryFilter, signalStatusFilter, signalFreshnessFilter, signalSearchTerm]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (adminTab === 'overview') {
      fetchEmployerData();
      fetchAdminCourses();
      fetchGovData();
      fetchAdminSignals();
    } else if (adminTab === 'employers') {
      fetchEmployerData();
    } else if (adminTab === 'institutes') {
      fetchAdminCourses();
    } else if (adminTab === 'gov') {
      fetchGovData();
    } else if (adminTab === 'industry') {
      fetchAdminSignals();
    }
  }, [adminTab, fetchEmployerData, fetchAdminCourses, fetchGovData, fetchAdminSignals]);

  // Trigger Automated Ingestion Handler (Phase 26)
  const handleTriggerIndustryIngest = async () => {
    setIngestRunning(true);
    try {
      const res = await api.triggerAdminIndustryIngest(null, adminKey);
      setActionMessage(res.message || 'Industry intelligence ingestion completed successfully.');
      setTimeout(() => setActionMessage(null), 5000);
      fetchAdminSignals();
    } catch (err) {
      alert(`Ingestion run failed: ${err?.message || err}`);
    } finally {
      setIngestRunning(false);
    }
  };

  // Update Industry Signal Status Handler (Phase 26)
  const handleUpdateSignalStatus = async (id, status, notes = '') => {
    try {
      await api.updateAdminIndustrySignal(id, { validation_status: status, admin_notes: notes }, adminKey);
      setActionMessage(`Industry signal '${id}' status updated to ${status}.`);
      setTimeout(() => setActionMessage(null), 4000);
      if (selectedSignal?.id === id) {
        setInspectSignalModalOpen(false);
      }
      fetchAdminSignals();
    } catch (err) {
      alert(`Failed to update signal status: ${err?.message || err}`);
    }
  };

  // Toggle Industry Signal Active State Handler (Phase 26)
  const handleToggleSignalActive = async (id, currentActive) => {
    try {
      await api.updateAdminIndustrySignal(id, { is_active: !currentActive }, adminKey);
      setActionMessage(`Industry signal '${id}' is now ${!currentActive ? 'Active' : 'Inactive'}.`);
      setTimeout(() => setActionMessage(null), 4000);
      fetchAdminSignals();
    } catch (err) {
      alert(`Failed to toggle signal active state: ${err?.message || err}`);
    }
  };

  // Delete Industry Signal Handler (Phase 26)
  const handleDeleteSignal = async (id, title) => {
    if (!window.confirm(`Are you sure you want to permanently remove signal '${title}' (${id})?`)) {
      return;
    }
    try {
      await api.deleteAdminIndustrySignal(id, adminKey);
      setActionMessage(`Signal '${id}' permanently removed.`);
      setTimeout(() => setActionMessage(null), 4000);
      if (selectedSignal?.id === id) {
        setInspectSignalModalOpen(false);
      }
      fetchAdminSignals();
    } catch (err) {
      alert(`Failed to delete signal: ${err?.message || err}`);
    }
  };

  // Delete Assessment Record Handler
  const handleDelete = async (id, name) => {
    if (!window.confirm(`Are you sure you want to remove assessment record for '${name}' (${id})?`)) {
      return;
    }
    try {
      await api.deleteAdminAssessment(id, adminKey);
      setActionMessage(`Record '${id}' successfully removed.`);
      setTimeout(() => setActionMessage(null), 4000);
      if (selectedRecord?.id === id) {
        setInspectModalOpen(false);
      }
      fetchData();
    } catch (err) {
      alert(`Failed to delete record: ${err?.message || err}`);
    }
  };

  // Update Employer Demand Status Handler (Phase 14)
  const handleUpdateDemandStatus = async (id, newStatus, notes = '') => {
    try {
      await api.updateAdminEmployerDemandStatus(id, newStatus, notes, adminKey);
      setActionMessage(`Employer demand '${id}' updated to status: ${newStatus}`);
      setTimeout(() => setActionMessage(null), 4000);
      if (selectedDemand?.id === id) {
        setSelectedDemand((prev) => (prev ? { ...prev, validation_status: newStatus, admin_notes: notes } : null));
      }
      fetchEmployerData();
    } catch (err) {
      alert(`Failed to update status: ${err?.message || err}`);
    }
  };

  // Delete Employer Demand Handler (Phase 14)
  // Government Opportunity Handlers (Phase 15)
  const handleDeleteGov = async (id, name) => {
    if (!window.confirm(`Remove government opportunity '${name}' (${id})?`)) return;
    try {
      await api.deleteAdminGovOpportunity(id, adminKey);
      setActionMessage(`Government opportunity '${id}' removed.`);
      setTimeout(() => setActionMessage(null), 4000);
      if (selectedGovOpp?.id === id) setInspectGovModalOpen(false);
      fetchGovData();
    } catch (err) {
      alert(`Failed to delete: ${err?.message || err}`);
    }
  };

  const handleAddGovOpportunity = async (formData) => {
    try {
      const res = await api.createAdminGovOpportunity(formData, adminKey);
      if (res?.status === 'success') {
        setActionMessage(`Government opportunity '${res.opportunity?.id}' created.`);
        setTimeout(() => setActionMessage(null), 4000);
        setGovAddModalOpen(false);
        fetchGovData();
      }
    } catch (err) {
      alert(`Failed to create: ${err?.message || err}`);
    }
  };

  const handleUpdateGovStatus = async (id, newStatus) => {
    try {
      await api.updateAdminGovOpportunity(id, { status: newStatus }, adminKey);
      setActionMessage(`Government opportunity '${id}' updated to ${newStatus}.`);
      setTimeout(() => setActionMessage(null), 4000);
      fetchGovData();
    } catch (err) {
      alert(`Failed to update: ${err?.message || err}`);
    }
  };

  const handleDeleteDemand = async (id, company, role) => {
    if (!window.confirm(`Are you sure you want to remove demand '${role}' from '${company}' (${id})?`)) {
      return;
    }
    try {
      await api.deleteAdminEmployerDemand(id, adminKey);
      setActionMessage(`Employer requirement '${id}' successfully removed.`);
      setTimeout(() => setActionMessage(null), 4000);
      if (selectedDemand?.id === id) {
        setInspectDemandModalOpen(false);
      }
      fetchEmployerData();
    } catch (err) {
      alert(`Failed to delete employer demand: ${err?.message || err}`);
    }
  };

  // Institute Courses Handlers (Phase 25)
  const handleDeleteAdminCourse = async (id, name) => {
    if (!window.confirm(`Are you sure you want to remove course '${name}' (${id})?`)) {
      return;
    }
    try {
      await api.deleteAdminCourse(id, adminKey);
      setActionMessage(`Course program '${id}' successfully removed.`);
      setTimeout(() => setActionMessage(null), 4000);
      if (selectedAdminCourse?.id === id) {
        setInspectCourseModalOpen(false);
      }
      fetchAdminCourses();
    } catch (err) {
      alert(`Failed to delete course program: ${err?.message || err}`);
    }
  };

  const handleUpdateAdminCourseStatus = async (id, newStatus) => {
    try {
      await api.updateAdminCourse(id, { status: newStatus }, adminKey);
      setActionMessage(`Course '${id}' status updated to ${newStatus}.`);
      setTimeout(() => setActionMessage(null), 4000);
      fetchAdminCourses();
    } catch (err) {
      alert(`Failed to update course status: ${err?.message || err}`);
    }
  };


  // Export to JSON / CSV
  const handleExportJSON = () => {
    const safeAssessments = Array.isArray(assessments) ? assessments : [];
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(safeAssessments, null, 2));
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute('href', dataStr);
    dlAnchor.setAttribute('download', `skillsetu_assessments_${new Date().toISOString().slice(0, 10)}.json`);
    dlAnchor.click();
  };

  const handleExportCSV = () => {
    const safeAssessments = Array.isArray(assessments) ? assessments : [];
    if (safeAssessments.length === 0) return;
    const headers = ['ID', 'Name', 'Education', 'District', 'Career Goal', 'Quiz Score %', 'Match %', 'Source', 'Date'];
    const rows = safeAssessments.map((a) => [
      a?.id,
      `"${(a?.name || '').replace(/"/g, '""')}"`,
      `"${(a?.education || '').replace(/"/g, '""')}"`,
      `"${(a?.district || '').replace(/"/g, '""')}"`,
      `"${(a?.career_goal || '').replace(/"/g, '""')}"`,
      a?.quiz_score_pct || 0,
      a?.skill_match_pct || 0,
      a?.source || '',
      a?.submitted_at || '',
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute('href', encodeURI(csvContent));
    dlAnchor.setAttribute('download', `skillsetu_assessments_${new Date().toISOString().slice(0, 10)}.csv`);
    dlAnchor.click();
  };

  const totalPages = Math.ceil((totalCount || 0) / pageSize) || 1;

  // Employer Demands Computed Metrics
  const safeEmployerDemands = Array.isArray(employerDemands) ? employerDemands : [];
  const empPendingCount = safeEmployerDemands.filter((d) => (d?.validation_status || d?.status || '').toUpperCase() === 'PENDING').length;
  const empValidatedCount = safeEmployerDemands.filter((d) => (d?.validation_status || d?.status || '').toUpperCase() === 'VALIDATED' || d?.status === 'active').length;
  const empRejectedCount = safeEmployerDemands.filter((d) => (d?.validation_status || d?.status || '').toUpperCase() === 'REJECTED').length;
  const empTotalPositions = safeEmployerDemands.reduce((sum, d) => sum + Number(d?.openings_count || d?.positions_count || 1), 0);

  // Export Employer Demands to CSV
  const handleExportEmployerCSV = () => {
    if (safeEmployerDemands.length === 0) return;
    const headers = ['ID', 'Company', 'Industry', 'District', 'Job Role', 'Openings', 'Experience Level', 'Timeline', 'Proficiency', 'Status', 'Source', 'Submitted At'];
    const rows = safeEmployerDemands.map((d) => [
      d?.id,
      `"${(d?.company_name || d?.employer_name || '').replace(/"/g, '""')}"`,
      `"${(d?.industry || '').replace(/"/g, '""')}"`,
      `"${(d?.district || '').replace(/"/g, '""')}"`,
      `"${(d?.job_role || d?.role_title || '').replace(/"/g, '""')}"`,
      d?.openings_count || d?.positions_count || 1,
      `"${(d?.experience_level || '').replace(/"/g, '""')}"`,
      `"${(d?.hiring_timeline || d?.urgency || '').replace(/"/g, '""')}"`,
      `"${(d?.preferred_proficiency || d?.proficiency_required || '').replace(/"/g, '""')}"`,
      d?.validation_status || d?.status || 'PENDING',
      d?.source || '',
      d?.submitted_at || d?.submitted_date || '',
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute('href', encodeURI(csvContent));
    dlAnchor.setAttribute('download', `skillsetu_employer_demands_${new Date().toISOString().slice(0, 10)}.csv`);
    dlAnchor.click();
  };

  return (
    <Layout>
      <div data-demo="admin-dashboard-container">
        {/* Header & Access Bar */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                State Data Management & Validation Registry
              </h1>
              <span className="text-[11px] font-mono px-2 py-0.5 bg-rose-100 dark:bg-rose-950/80 text-rose-700 dark:text-rose-300 font-bold rounded border border-rose-300 dark:border-rose-800">
                ADMIN CONTROL CENTER
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
              Administrative audit, candidate assessment telemetry, and first-party employer demand validation
            </p>
          </div>

          {/* Admin Identity & Security Status */}
          <div className="flex items-center gap-2 bg-white dark:bg-slate-900 p-2 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs self-start md:self-auto text-xs">
            <div className="flex items-center gap-2 font-mono text-[11px] text-slate-700 dark:text-slate-200 px-2.5 py-1.5 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="font-semibold text-slate-800 dark:text-slate-100">
                {user?.full_name || 'Administrator'}
              </span>
              <span className="text-[10px] uppercase px-1.5 py-0.2 rounded bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 font-bold">
                {user?.role || 'ADMIN'}
              </span>
            </div>
          </div>
        </div>

        {/* Navigation Tab Bar */}
        <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 mb-6 pb-2 overflow-x-auto">
          <button
            onClick={() => handleTabChange('overview')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-colors cursor-pointer shrink-0 ${
              adminTab === 'overview'
                ? 'bg-slate-900 dark:bg-teal-600 text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            <span>📊</span>
            <span>Executive Overview</span>
          </button>

          <button
            onClick={() => handleTabChange('students')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-colors cursor-pointer shrink-0 ${
              adminTab === 'students'
                ? 'bg-slate-900 dark:bg-teal-600 text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            <span>👥</span>
            <span>Student Assessments</span>
            <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] bg-slate-700 dark:bg-teal-800 text-slate-200">
              {stats?.total_submissions || assessments.length}
            </span>
          </button>

          <button
            onClick={() => handleTabChange('employers')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-colors cursor-pointer shrink-0 ${
              adminTab === 'employers'
                ? 'bg-slate-900 dark:bg-teal-600 text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            <span>🏢</span>
            <span>Employer Demands</span>
            {empPendingCount > 0 && (
              <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] bg-amber-500 text-slate-950 font-bold font-mono">
                {empPendingCount} Pending
              </span>
            )}
          </button>

          <button
            onClick={() => handleTabChange('institutes')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-colors cursor-pointer shrink-0 ${
              adminTab === 'institutes'
                ? 'bg-slate-900 dark:bg-teal-600 text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            <span>🎓</span>
            <span>Institute Programs</span>
            <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] bg-slate-700 dark:bg-teal-800 text-slate-200">
              {courseStats.total || adminCourses.length}
            </span>
          </button>

          <button
            onClick={() => handleTabChange('gov')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-colors cursor-pointer shrink-0 ${
              adminTab === 'gov'
                ? 'bg-slate-900 dark:bg-teal-600 text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            <span>🏛️</span>
            <span>Government Opportunities</span>
            <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] bg-slate-700 dark:bg-teal-800 text-slate-200">
              {govStats.total}
            </span>
          </button>

          <button
            onClick={() => handleTabChange('industry')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-colors cursor-pointer shrink-0 ${
              adminTab === 'industry'
                ? 'bg-slate-900 dark:bg-teal-600 text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            <span>📡</span>
            <span>Industry Intelligence</span>
            <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] bg-slate-700 dark:bg-teal-800 text-slate-200">
              {signalStats.total || adminSignals.length}
            </span>
          </button>
        </div>

        {actionMessage && (
          <div className="mb-6 p-4 rounded-xl border border-emerald-200 dark:border-emerald-900 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 text-xs flex items-center gap-2 shadow-xs">
            <span>✓</span>
            <span className="font-semibold">{actionMessage}</span>
          </div>
        )}

        {authError && (
          <div className="mb-6 p-4 rounded-xl border border-rose-200 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-300 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
            <div className="flex items-center gap-2">
              <span>🔒</span>
              <span className="font-semibold">{authError}</span>
            </div>
            <a
              href="/login"
              className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white font-bold rounded-lg transition-colors shrink-0 cursor-pointer text-xs"
            >
              Sign In as Administrator →
            </a>
          </div>
        )}

        {/* ========================================================================= */}
        {/* VIEW 0: EXECUTIVE ADMINISTRATIVE OVERVIEW (PHASE 24) */}
        {/* ========================================================================= */}
        {adminTab === 'overview' && (
          <div data-demo="admin-overview-section" className="space-y-8 animate-fadeIn">
            {/* Top KPI Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3 sm:gap-4">
              <StatCard
                title="Total Submissions"
                value={stats?.total_submissions ?? assessments.length}
                subtitle="All cohort assessments"
                icon="📋"
              />
              <StatCard
                title="Real Submissions"
                value={stats?.user_submitted_count ?? assessments.filter((a) => a.source === 'USER_SUBMITTED').length}
                subtitle="Real candidate assessments"
                icon="🛡️"
                color="teal"
              />
              <StatCard
                title="Demo Benchmarks"
                value={stats?.demo_synthetic_count ?? assessments.filter((a) => a.source === 'DEMO_SYNTHETIC').length}
                subtitle="Synthetic baseline records"
                icon="🔬"
                color="slate"
              />
              <StatCard
                title="Avg Quiz Score"
                value={stats ? `${stats.avg_quiz_score}%` : '...'}
                subtitle="Diagnostic aptitude"
                icon="🧠"
                color="emerald"
              />
              <StatCard
                title="Employer Demands"
                value={employerDemands.length || '...'}
                subtitle={`${empPendingCount} pending review`}
                icon="🏢"
                color="amber"
              />
              <StatCard
                title="Gov Schemes"
                value={govStats.total || govOpportunities.length}
                subtitle={`${govStats.active_count || govOpportunities.length} active programs`}
                icon="🏛️"
                color="blue"
              />
              <StatCard
                title="Industry Signals"
                value={signalStats.total || adminSignals.length}
                subtitle={`${signalStats.fresh_count} fresh (<7d)`}
                icon="📡"
                color="indigo"
              />
            </div>

            {/* Provenance Assurance Banner */}
            <div className="p-4 rounded-2xl bg-gradient-to-r from-teal-500/10 via-slate-500/10 to-indigo-500/10 border border-teal-500/20 dark:border-teal-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-3">
                <span className="text-2xl">⚖️</span>
                <div>
                  <h4 className="font-extrabold text-slate-900 dark:text-white">
                    Data Provenance & Audit Integrity Enforced
                  </h4>
                  <p className="text-slate-600 dark:text-slate-400 mt-0.5">
                    Real candidate assessments (<span className="font-mono text-teal-700 dark:text-teal-300 font-bold">USER_SUBMITTED</span>) are cryptographically partitioned from synthetic baseline benchmarks (<span className="font-mono text-slate-600 dark:text-slate-400 font-bold">DEMO_SYNTHETIC</span>).
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="px-2.5 py-1 rounded-lg bg-teal-100 dark:bg-teal-950/80 text-teal-800 dark:text-teal-300 border border-teal-300 dark:border-teal-800 font-mono font-bold text-[11px]">
                  {stats?.user_submitted_count || 0} Real
                </span>
                <span className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700 font-mono font-bold text-[11px]">
                  {stats?.demo_synthetic_count || 0} Demo
                </span>
              </div>
            </div>

            {/* Analytics Grid */}
            {stats && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* District Distribution */}
                <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                    <h3 className="text-xs font-bold uppercase tracking-wider font-mono text-slate-700 dark:text-slate-300">
                      📍 District Representation
                    </h3>
                    <span className="text-[10px] font-mono text-slate-400">Maharashtra</span>
                  </div>
                  <div className="space-y-2.5">
                    {(stats.district_distribution || []).slice(0, 6).map((d) => (
                      <div key={d.district} className="space-y-1 text-xs">
                        <div className="flex justify-between font-semibold">
                          <span className="text-slate-800 dark:text-slate-200">{d.district}</span>
                          <span className="font-mono text-slate-500">{d.count} candidates</span>
                        </div>
                        <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-teal-500 rounded-full"
                            style={{ width: `${Math.min(100, (d.count / Math.max(1, stats.total_submissions)) * 100)}%` }}
                          ></div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Top Missing Skills / Skill Gaps */}
                <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                    <h3 className="text-xs font-bold uppercase tracking-wider font-mono text-slate-700 dark:text-slate-300">
                      ⚠️ Top Skill Deficits in Cohort
                    </h3>
                    <span className="text-[10px] font-mono text-rose-500 font-bold">Deficit Ranking</span>
                  </div>
                  <div className="space-y-1.5">
                    {(stats.top_missing_skills || stats.common_missing_skills || []).slice(0, 6).map((sk) => {
                      const skillName = sk.skill_name || sk.skill || sk.name;
                      const count = sk.deficit_count || sk.frequency || sk.count || 0;
                      return (
                        <div key={skillName} className="flex items-center justify-between text-xs py-1.5 px-2.5 rounded-lg bg-rose-50/50 dark:bg-rose-950/20 border border-rose-100 dark:border-rose-900/50">
                          <span className="font-semibold text-slate-800 dark:text-slate-200">{skillName}</span>
                          <span className="font-mono text-rose-600 dark:text-rose-400 font-bold text-[11px]">
                            {count} deficits
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Career Goals & Readiness Tiers */}
                <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                    <h3 className="text-xs font-bold uppercase tracking-wider font-mono text-slate-700 dark:text-slate-300">
                      🚀 Top Career Aspirations
                    </h3>
                    <span className="text-[10px] font-mono text-teal-600 dark:text-teal-400">Target Roles</span>
                  </div>
                  <div className="space-y-2">
                    {(stats.career_goal_distribution || stats.top_career_goals || []).slice(0, 6).map((cg) => (
                      <div key={cg.career_goal} className="flex items-center justify-between p-2 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 text-xs">
                        <span className="font-semibold text-slate-800 dark:text-slate-200">{cg.career_goal}</span>
                        <span className="px-2 py-0.5 rounded font-mono font-bold text-[10px] bg-teal-50 dark:bg-teal-950 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
                          {cg.count} ({cg.share_pct || Math.round((cg.count / Math.max(1, stats.total_submissions)) * 100)}%)
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Real Data vs Demo Data Governance Card (§30) */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 mb-4 border-b border-slate-100 dark:border-slate-800">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-extrabold text-slate-900 dark:text-white">
                      Data Governance & Hybrid Provenance Architecture
                    </h3>
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                      Governance Active
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Real first-party user submissions persisted to disk and database alongside the immutable DEMO_SYNTHETIC benchmark baseline.
                  </p>
                </div>
                <div className="flex items-center gap-3 text-xs font-mono">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                    <span className="text-slate-700 dark:text-slate-200 font-bold">
                      {governanceData?.total_real_user_submitted ?? assessments.filter((a) => a.source === 'USER_SUBMITTED').length} Live
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-slate-400"></span>
                    <span className="text-slate-500 dark:text-slate-400 font-medium">
                      {governanceData?.total_demo_synthetic ?? assessments.filter((a) => a.source === 'DEMO_SYNTHETIC').length} Demo Baseline
                    </span>
                  </div>
                </div>
              </div>

              {governanceData?.tables && (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                  {Object.entries(governanceData.tables).slice(0, 5).map(([tbl, tinfo]) => (
                    <div key={tbl} className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700">
                      <div className="text-[10px] font-mono text-slate-500 dark:text-slate-400 uppercase tracking-wider font-semibold truncate">
                        {tbl.replace('_', ' ')}
                      </div>
                      <div className="flex items-center justify-between mt-1.5">
                        <span className="text-sm font-black text-slate-900 dark:text-white">
                          {tinfo.total} total
                        </span>
                        {tinfo.real_user_submitted > 0 ? (
                          <span className="text-[10px] font-mono font-bold px-1.5 py-0.2 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300">
                            {tinfo.real_user_submitted} Real
                          </span>
                        ) : (
                          <span className="text-[10px] font-mono text-slate-400">
                            Demo Only
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Recent Submissions Feed */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">

              <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-extrabold text-slate-900 dark:text-white">
                    Recent Candidate Submissions & Diagnostic Results
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Latest submissions received across all Maharashtra districts
                  </p>
                </div>
                <button
                  onClick={() => handleTabChange('students')}
                  className="px-3 py-1.5 text-xs font-bold text-teal-600 dark:text-teal-400 hover:underline cursor-pointer"
                >
                  View All ({stats?.total_submissions || assessments.length}) →
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800">
                    <tr>
                      <th className="p-3.5 font-bold">Candidate Name</th>
                      <th className="p-3.5 font-bold">District</th>
                      <th className="p-3.5 font-bold">Career Goal</th>
                      <th className="p-3.5 font-bold text-center">Quiz Score</th>
                      <th className="p-3.5 font-bold text-center">Skill Match</th>
                      <th className="p-3.5 font-bold text-center">Provenance</th>
                      <th className="p-3.5 font-bold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {assessments.slice(0, 6).map((a) => (
                      <tr key={a.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                        <td className="p-3.5 font-semibold text-slate-900 dark:text-white">
                          <div>{a.name || 'Anonymous Candidate'}</div>
                          <div className="text-[10px] text-slate-400 font-mono">{a.id}</div>
                        </td>
                        <td className="p-3.5 text-slate-600 dark:text-slate-300 font-medium">
                          {a.district || 'Maharashtra'}
                        </td>
                        <td className="p-3.5 text-slate-800 dark:text-slate-200 font-semibold">
                          {a.career_goal || 'Unspecified'}
                        </td>
                        <td className="p-3.5 text-center font-mono font-bold text-emerald-600 dark:text-emerald-400">
                          {a.quiz_score_pct ?? 0}%
                        </td>
                        <td className="p-3.5 text-center font-mono font-bold text-teal-600 dark:text-teal-400">
                          {a.skill_match_pct ?? 0}%
                        </td>
                        <td className="p-3.5 text-center">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                              a.source === 'USER_SUBMITTED'
                                ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700'
                            }`}
                          >
                            {a.source === 'USER_SUBMITTED' ? 'USER SUBMITTED' : 'DEMO SYNTHETIC'}
                          </span>
                        </td>
                        <td className="p-3.5 text-right">
                          <button
                            onClick={() => {
                              setSelectedRecord(a);
                              setInspectModalOpen(true);
                            }}
                            className="px-2.5 py-1 bg-slate-100 hover:bg-teal-50 hover:text-teal-700 dark:bg-slate-800 dark:hover:bg-teal-950 dark:hover:text-teal-300 text-slate-700 dark:text-slate-300 font-bold rounded-lg transition-colors cursor-pointer text-[11px]"
                          >
                            Inspect 🔍
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Quick Action Navigation Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
              <div
                onClick={() => handleTabChange('students')}
                className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:border-teal-500 transition-all cursor-pointer group"
              >
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-xl bg-teal-50 dark:bg-teal-950 text-teal-600 dark:text-teal-400 flex items-center justify-center text-xl font-bold group-hover:scale-105 transition-transform">
                    👥
                  </div>
                  <div>
                    <h4 className="font-extrabold text-slate-900 dark:text-white text-sm">
                      Student Registry
                    </h4>
                    <span className="text-[11px] text-slate-400 font-mono">
                      {stats?.total_submissions || assessments.length} records
                    </span>
                  </div>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Filter by district, target career, or data source with CSV export and competency audit.
                </p>
              </div>

              <div
                onClick={() => handleTabChange('employers')}
                className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:border-amber-500 transition-all cursor-pointer group"
              >
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-xl bg-amber-50 dark:bg-amber-950 text-amber-600 dark:text-amber-400 flex items-center justify-center text-xl font-bold group-hover:scale-105 transition-transform">
                    🏢
                  </div>
                  <div>
                    <h4 className="font-extrabold text-slate-900 dark:text-white text-sm">
                      Employer Demands
                    </h4>
                    <span className="text-[11px] text-amber-600 dark:text-amber-400 font-mono font-bold">
                      {empPendingCount} pending review
                    </span>
                  </div>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Audit and validate corporate hiring requirements to inject real industry signals into state curriculum.
                </p>
              </div>

              <div
                onClick={() => handleTabChange('institutes')}
                className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:border-purple-500 transition-all cursor-pointer group"
              >
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-xl bg-purple-50 dark:bg-purple-950 text-purple-600 dark:text-purple-400 flex items-center justify-center text-xl font-bold group-hover:scale-105 transition-transform">
                    🎓
                  </div>
                  <div>
                    <h4 className="font-extrabold text-slate-900 dark:text-white text-sm">
                      Institute Programs
                    </h4>
                    <span className="text-[11px] text-purple-600 dark:text-purple-400 font-mono font-bold">
                      {courseStats.total || adminCourses.length} accredited courses
                    </span>
                  </div>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Manage vocational courses, inspect first-party curricula, and review placement health.
                </p>
              </div>

              <div
                onClick={() => handleTabChange('gov')}
                className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:border-blue-500 transition-all cursor-pointer group"
              >
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 flex items-center justify-center text-xl font-bold group-hover:scale-105 transition-transform">
                    🏛️
                  </div>
                  <div>
                    <h4 className="font-extrabold text-slate-900 dark:text-white text-sm">
                      Gov Opportunities
                    </h4>
                    <span className="text-[11px] text-slate-400 font-mono">
                      {govStats.total} schemes registered
                    </span>
                  </div>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Publish, update, and manage state welfare schemes, ITI apprenticeships, and skilling programs.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* VIEW 1: STUDENT ASSESSMENTS & TELEMETRY (PHASE 12 & 13) */}
        {/* ========================================================================= */}
        {adminTab === 'students' && (
        <div data-demo="admin-students-section">
          {/* Top Aggregate KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4 mb-8">
            <StatCard
              title="Total Submissions"
              value={stats?.total_submissions ?? '...'}
              subtitle="All records in registry"
              icon="📋"
            />
            <StatCard
              title="User Submitted"
              value={stats?.user_submitted_count ?? '...'}
              subtitle="Candidate self-assessments"
              icon="👤"
              color="teal"
            />
            <StatCard
              title="Demo Benchmarks"
              value={stats?.demo_synthetic_count ?? '...'}
              subtitle="Synthetic baseline profiles"
              icon="🔬"
              color="slate"
            />
            <StatCard
              title="Avg Quiz Score"
              value={stats ? `${stats.avg_quiz_score}%` : '...'}
              subtitle="Diagnostic aptitude test"
              icon="🧠"
              color="emerald"
            />
            <StatCard
              title="Avg Role Match"
              value={stats ? `${stats.avg_skill_match}%` : '...'}
              subtitle="Competency vs goal"
              icon="🎯"
              color="amber"
            />
          </div>

          {/* Visual Labour-Market Analytics Grid */}
          {stats && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
              {/* Col 1: District Distribution */}
              <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                  <h3 className="text-xs font-bold uppercase tracking-wider font-mono text-slate-700 dark:text-slate-300">
                    📍 Geographic Distribution
                  </h3>
                  <span className="text-[10px] font-mono text-slate-400">Maharashtra</span>
                </div>
                <div className="space-y-2.5">
                  {stats.district_distribution?.slice(0, 5).map((d) => (
                    <div key={d.district} className="space-y-1 text-xs">
                      <div className="flex justify-between font-semibold">
                        <span className="text-slate-800 dark:text-slate-200">{d.district}</span>
                        <span className="font-mono text-slate-500">{d.count} candidates</span>
                      </div>
                      <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-teal-500 rounded-full"
                          style={{ width: `${Math.min(100, (d.count / Math.max(1, stats.total_submissions)) * 100)}%` }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Col 2: Top Career Ambitions */}
              <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                  <h3 className="text-xs font-bold uppercase tracking-wider font-mono text-slate-700 dark:text-slate-300">
                    🚀 Target Career Aspirations
                  </h3>
                  <span className="text-[10px] font-mono text-slate-400">Top Selected</span>
                </div>
                <div className="space-y-2">
                  {stats.top_career_goals?.slice(0, 5).map((cg) => (
                    <div key={cg.career_goal} className="flex items-center justify-between p-2 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 text-xs">
                      <span className="font-semibold text-slate-800 dark:text-slate-200">{cg.career_goal}</span>
                      <span className="px-2 py-0.5 rounded font-mono font-bold text-[10px] bg-teal-50 dark:bg-teal-950 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
                        {cg.count} ({cg.share_pct}%)
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Col 3: Critical State Skill Bottlenecks */}
              <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                  <h3 className="text-xs font-bold uppercase tracking-wider font-mono text-slate-700 dark:text-slate-300">
                    ⚠️ Skill Gaps in Assessed Cohort
                  </h3>
                  <span className="text-[10px] font-mono text-rose-500 font-bold">Deficit Rank</span>
                </div>
                <div className="space-y-1.5">
                  {stats.common_missing_skills?.slice(0, 5).map((sk) => (
                    <div key={sk.skill} className="flex items-center justify-between text-xs py-1 px-2 rounded-lg bg-rose-50/50 dark:bg-rose-950/20 border border-rose-100 dark:border-rose-900/50">
                      <span className="font-medium text-slate-800 dark:text-slate-200">{sk.skill}</span>
                      <span className="font-mono text-rose-600 dark:text-rose-400 font-bold text-[11px]">
                        {sk.frequency} missing
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Filtering & Audit Controls */}
          <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-4 mb-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
              <div>
                <h2 className="text-base font-extrabold text-slate-900 dark:text-white">
                  Assessment Registry & Submissions
                </h2>
                <p className="text-xs text-slate-500">
                  Filtering {assessments.length} matching candidate assessment records
                </p>
              </div>

              {/* Export Buttons */}
              <div className="flex items-center gap-2">
                <button
                  onClick={handleExportCSV}
                  className="px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-xl text-xs font-bold transition-colors cursor-pointer"
                >
                  Export CSV 📄
                </button>
                <button
                  onClick={handleExportJSON}
                  className="px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-xl text-xs font-bold transition-colors cursor-pointer"
                >
                  Export JSON 📦
                </button>
              </div>
            </div>

            {/* Filter Controls Row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3 text-xs">
              {/* Search */}
              <div className="lg:col-span-2">
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Search Candidate</label>
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => {
                    setSearchTerm(e.target.value);
                    setPage(0);
                  }}
                  placeholder="Name, skills, or education..."
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-medium outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>

              {/* Source Filter */}
              <div>
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Data Source</label>
                <select
                  value={sourceFilter}
                  onChange={(e) => {
                    setSourceFilter(e.target.value);
                    setPage(0);
                  }}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-medium outline-none focus:ring-2 focus:ring-teal-500"
                >
                  <option value="all">All Sources</option>
                  <option value="USER_SUBMITTED">User Submitted</option>
                  <option value="DEMO_SYNTHETIC">Demo Synthetic</option>
                </select>
              </div>

              {/* District Filter */}
              <div>
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">District</label>
                <select
                  value={districtFilter}
                  onChange={(e) => {
                    setDistrictFilter(e.target.value);
                    setPage(0);
                  }}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-medium outline-none focus:ring-2 focus:ring-teal-500"
                >
                  {DISTRICTS.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>

              {/* Career Goal Filter */}
              <div>
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Career Goal</label>
                <select
                  value={careerGoalFilter}
                  onChange={(e) => {
                    setCareerGoalFilter(e.target.value);
                    setPage(0);
                  }}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-medium outline-none focus:ring-2 focus:ring-teal-500"
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </div>

              {/* Date From */}
              <div>
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Date From</label>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => {
                    setDateFrom(e.target.value);
                    setPage(0);
                  }}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-medium outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>
            </div>
          </div>

          {/* Assessment Table View */}
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden mb-6">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 font-mono uppercase text-[10px] tracking-wider border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-3 px-4">Candidate & ID</th>
                    <th className="py-3 px-4">Education & District</th>
                    <th className="py-3 px-4">Career Goal</th>
                    <th className="py-3 px-4">Quiz Score</th>
                    <th className="py-3 px-4">Skill Match</th>
                    <th className="py-3 px-4">Data Source</th>
                    <th className="py-3 px-4">Date</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {loading && (
                    <tr>
                      <td colSpan="8" className="py-12 text-center text-slate-400 font-mono">
                        Loading assessment registry data...
                      </td>
                    </tr>
                  )}

                  {!loading && assessments.length === 0 && (
                    <tr>
                      <td colSpan="8" className="py-12 text-center text-slate-400 font-mono">
                        No candidate assessment records found matching active filters.
                      </td>
                    </tr>
                  )}

                  {!loading &&
                    assessments.map((a) => (
                      <tr key={a.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                        <td className="py-3 px-4">
                          <div className="font-bold text-slate-900 dark:text-white">{a.name}</div>
                          <div className="font-mono text-[10px] text-slate-400">{a.id}</div>
                        </td>
                        <td className="py-3 px-4">
                          <div className="text-slate-800 dark:text-slate-200 font-medium">{a.education}</div>
                          <div className="text-slate-500 text-[11px]">📍 {a.district}</div>
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-bold text-slate-900 dark:text-white block">{a.career_goal}</span>
                          <span className="text-[10px] text-slate-400">
                            {a.evaluation_summary?.missing_skills?.length || 0} gaps flagged
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-mono font-bold px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                            {a.quiz_score_pct}%
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-mono font-bold px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                            {a.skill_match_pct}%
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`font-mono text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                              a.source === 'USER_SUBMITTED'
                                ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700'
                            }`}
                          >
                            {a.source === 'USER_SUBMITTED' ? 'User Submitted' : 'Demo Benchmark'}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-[11px] text-slate-500">
                          {a.submitted_at?.slice(0, 10) || 'N/A'}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => {
                                setSelectedRecord(a);
                                setInspectModalOpen(true);
                              }}
                              className="px-2.5 py-1 bg-slate-100 dark:bg-slate-800 hover:bg-teal-50 dark:hover:bg-teal-950 hover:text-teal-700 text-slate-700 dark:text-slate-300 rounded-lg font-bold text-[11px] transition-colors cursor-pointer"
                            >
                              Inspect 🔍
                            </button>
                            <button
                              onClick={() => handleDelete(a.id, a.name)}
                              className="p-1 text-slate-400 hover:text-rose-600 rounded transition-colors cursor-pointer"
                              title="Delete Record"
                            >
                              ✕
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between p-4 border-t border-slate-100 dark:border-slate-800 text-xs">
                <button
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  className="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 font-bold text-slate-700 dark:text-slate-300 disabled:opacity-40 cursor-pointer"
                >
                  ← Previous Page
                </button>
                <span className="text-slate-500 font-mono">
                  Page {page + 1} of {totalPages}
                </span>
                <button
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  className="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 font-bold text-slate-700 dark:text-slate-300 disabled:opacity-40 cursor-pointer"
                >
                  Next Page →
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* VIEW 2: EMPLOYER DEMANDS & VALIDATION (PHASE 14) */}
      {/* ========================================================================= */}
      {adminTab === 'employers' && (
        <div data-demo="admin-employers-section">
          {/* Top KPI StatCards */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4 mb-8">
            <StatCard
              title="Total Demands"
              value={employerDemands.length}
              subtitle="All registered requirements"
              icon="🏢"
            />
            <StatCard
              title="Pending Validation"
              value={empPendingCount}
              subtitle="Awaiting administrative review"
              icon="⏳"
              color={empPendingCount > 0 ? 'amber' : 'slate'}
            />
            <StatCard
              title="Validated Signals"
              value={empValidatedCount}
              subtitle="Active in skill gap calculations"
              icon="✓"
              color="emerald"
            />
            <StatCard
              title="Rejected"
              value={empRejectedCount}
              subtitle="Invalid or spam requests"
              icon="✕"
              color="rose"
            />
            <StatCard
              title="Total Vacancies"
              value={empTotalPositions}
              subtitle="Open industrial positions"
              icon="💼"
              color="purple"
            />
          </div>

          {/* Employer Demands Filter & Search Bar */}
          <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-4 mb-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
              <div>
                <h2 className="text-base font-extrabold text-slate-900 dark:text-white">
                  Employer Hiring Requirements & Validation Hub
                </h2>
                <p className="text-xs text-slate-500">
                  Inspect industry skill needs, review provenance, and calibrate validation status for the intelligence loop
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={fetchEmployerData}
                  className="px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-xl text-xs font-bold transition-colors cursor-pointer"
                >
                  Refresh 🔄
                </button>
                <button
                  onClick={handleExportEmployerCSV}
                  className="px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-xl text-xs font-bold transition-colors cursor-pointer"
                >
                  Export CSV 📄
                </button>
              </div>
            </div>

            {/* Filter Controls Row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 text-xs">
              {/* Search */}
              <div>
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Search Company / Role</label>
                <input
                  type="text"
                  value={empSearchTerm}
                  onChange={(e) => setEmpSearchTerm(e.target.value)}
                  placeholder="e.g. Tata Motors, EV Architect..."
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-medium outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>

              {/* Status Filter */}
              <div>
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Validation Status</label>
                <select
                  value={empStatusFilter}
                  onChange={(e) => setEmpStatusFilter(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-medium outline-none focus:ring-2 focus:ring-teal-500"
                >
                  <option value="all">All Statuses</option>
                  <option value="PENDING">Pending Validation (⏳)</option>
                  <option value="VALIDATED">Validated (✓)</option>
                  <option value="REJECTED">Rejected (✕)</option>
                </select>
              </div>

              {/* District Filter */}
              <div>
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">District Location</label>
                <select
                  value={empDistrictFilter}
                  onChange={(e) => setEmpDistrictFilter(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-medium outline-none focus:ring-2 focus:ring-teal-500"
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
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Industry Domain</label>
                <select
                  value={empIndustryFilter}
                  onChange={(e) => setEmpIndustryFilter(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-medium outline-none focus:ring-2 focus:ring-teal-500"
                >
                  {INDUSTRIES.map((ind) => (
                    <option key={ind} value={ind}>
                      {ind}
                    </option>
                  ))}
                </select>
              </div>

              {/* Source Filter */}
              <div>
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Origin Source</label>
                <select
                  value={empSourceFilter}
                  onChange={(e) => setEmpSourceFilter(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-medium outline-none focus:ring-2 focus:ring-teal-500"
                >
                  <option value="all">All Sources</option>
                  <option value="EMPLOYER_SUBMITTED">Employer Submitted</option>
                  <option value="DEMO_SYNTHETIC">Demo Synthetic</option>
                </select>
              </div>
            </div>
          </div>

          {/* Employer Demands Table */}
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden mb-6">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 font-mono uppercase text-[10px] tracking-wider border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-3 px-4">Company & Location</th>
                    <th className="py-3 px-4">Target Role & Industry</th>
                    <th className="py-3 px-4">Openings</th>
                    <th className="py-3 px-4">Required Skills</th>
                    <th className="py-3 px-4">Validation Status</th>
                    <th className="py-3 px-4">Source</th>
                    <th className="py-3 px-4 text-right">Validation Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {empLoading && (
                    <tr>
                      <td colSpan="7" className="py-12 text-center text-slate-400 font-mono">
                        Loading employer demand requirements...
                      </td>
                    </tr>
                  )}

                  {!empLoading && employerDemands.length === 0 && (
                    <tr>
                      <td colSpan="7" className="py-12 text-center text-slate-400 font-mono">
                        No employer hiring requirements found matching current filters.
                      </td>
                    </tr>
                  )}

                  {!empLoading &&
                    employerDemands.map((d) => {
                      const statusUpper = (d.validation_status || d.status || 'pending').toUpperCase();
                      const isValidated = statusUpper === 'VALIDATED' || d.status === 'active';
                      const isRejected = statusUpper === 'REJECTED';

                      return (
                        <tr key={d.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                          <td className="py-3 px-4">
                            <div className="font-bold text-slate-900 dark:text-white">
                              {d.company_name || d.employer_name}
                            </div>
                            <div className="text-slate-500 text-[11px]">📍 {d.district}</div>
                            <div className="font-mono text-[10px] text-slate-400">{d.id}</div>
                          </td>

                          <td className="py-3 px-4">
                            <div className="font-bold text-slate-900 dark:text-white">{d.job_role || d.role_title}</div>
                            <div className="text-slate-500 text-[11px]">{d.industry}</div>
                            <div className="text-[10px] text-teal-600 font-mono">{d.experience_level || 'Entry-Mid'}</div>
                          </td>

                          <td className="py-3 px-4 font-mono font-bold text-slate-800 dark:text-slate-200">
                            <span className="px-2 py-0.5 rounded bg-purple-50 dark:bg-purple-950 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                              {d.openings_count || d.positions_count || 1} seats
                            </span>
                          </td>

                          <td className="py-3 px-4">
                            <div className="flex flex-wrap gap-1 max-w-xs">
                              {(d.required_skills || d.skills || []).slice(0, 4).map((sk, idx) => (
                                <span
                                  key={idx}
                                  className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-[10px] font-medium border border-slate-200 dark:border-slate-700"
                                >
                                  {typeof sk === 'object' ? sk.name : sk}
                                </span>
                              ))}
                              {(d.required_skills || d.skills || []).length > 4 && (
                                <span className="text-[10px] text-slate-400 self-center">
                                  +{(d.required_skills || d.skills || []).length - 4} more
                                </span>
                              )}
                            </div>
                          </td>

                          <td className="py-3 px-4">
                            <span
                              className={`font-mono text-[10px] font-bold px-2.5 py-1 rounded-full uppercase inline-flex items-center gap-1 ${
                                isValidated
                                  ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800'
                                  : isRejected
                                  ? 'bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-800'
                                  : 'bg-amber-100 dark:bg-amber-950 text-amber-900 dark:text-amber-300 border border-amber-300 dark:border-amber-800'
                              }`}
                            >
                              {isValidated ? '✓ Validated' : isRejected ? '✕ Rejected' : '⏳ Pending Validation'}
                            </span>
                          </td>

                          <td className="py-3 px-4">
                            <span
                              className={`font-mono text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                                d.source === 'EMPLOYER_SUBMITTED'
                                  ? 'bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800'
                                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700'
                              }`}
                            >
                              {d.source === 'EMPLOYER_SUBMITTED' ? 'Employer Direct' : 'Demo Benchmark'}
                            </span>
                          </td>

                          <td className="py-3 px-4 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              {/* Quick Validate Button */}
                              {!isValidated && (
                                <button
                                  onClick={() => handleUpdateDemandStatus(d.id, 'VALIDATED', 'Validated via quick admin action')}
                                  className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-lg text-[11px] transition-colors cursor-pointer"
                                  title="Approve & Validate for Skill Gap Engine"
                                >
                                  Validate ✓
                                </button>
                              )}

                              {/* Quick Reject Button */}
                              {!isRejected && (
                                <button
                                  onClick={() => handleUpdateDemandStatus(d.id, 'REJECTED', 'Marked as rejected by admin')}
                                  className="px-2 py-1 bg-rose-100 hover:bg-rose-200 text-rose-700 dark:bg-rose-950 dark:hover:bg-rose-900 dark:text-rose-300 font-bold rounded-lg text-[11px] transition-colors cursor-pointer"
                                  title="Reject Submission"
                                >
                                  Reject ✕
                                </button>
                              )}

                              {/* Inspect & Notes Button */}
                              <button
                                onClick={() => {
                                  setSelectedDemand(d);
                                  setAdminNotesInput(d.admin_notes || '');
                                  setInspectDemandModalOpen(true);
                                }}
                                className="px-2.5 py-1 bg-slate-100 dark:bg-slate-800 hover:bg-teal-50 dark:hover:bg-teal-950 hover:text-teal-700 text-slate-700 dark:text-slate-300 rounded-lg font-bold text-[11px] transition-colors cursor-pointer"
                              >
                                Audit 🔍
                              </button>

                              {/* Delete Button */}
                              <button
                                onClick={() => handleDeleteDemand(d.id, d.company_name || d.employer_name, d.job_role || d.role_title)}
                                className="p-1 text-slate-400 hover:text-rose-600 rounded transition-colors cursor-pointer"
                                title="Delete Requirement"
                              >
                                ✕
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 1: STUDENT RECORD INSPECTION (PHASE 13) */}
      {/* ========================================================================= */}
      {inspectModalOpen && selectedRecord && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs animate-fadeIn">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto space-y-5 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-extrabold text-slate-900 dark:text-white text-lg">
                    {selectedRecord.name}
                  </h3>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded font-mono uppercase ${
                      selectedRecord.source === 'USER_SUBMITTED'
                        ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                        : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700'
                    }`}
                  >
                    {selectedRecord.source === 'USER_SUBMITTED' ? 'User-Submitted Assessment' : 'Demo Benchmark Profile'}
                  </span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  ID: {selectedRecord.id} • {selectedRecord.education} • {selectedRecord.district}
                </p>
              </div>
              <button
                onClick={() => setInspectModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-2 text-base cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Top Score Summary */}
            <div className="grid grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                <span className="text-[10px] text-slate-400 font-mono uppercase block">Target Role</span>
                <span className="font-bold text-slate-900 dark:text-white text-sm">{selectedRecord.career_goal}</span>
              </div>
              <div className="p-3 rounded-xl bg-teal-50/60 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-900/60">
                <span className="text-[10px] text-teal-700 dark:text-teal-400 font-mono uppercase block">Quiz Aptitude</span>
                <span className="font-extrabold text-teal-800 dark:text-teal-300 text-sm">{selectedRecord.quiz_score_pct}%</span>
              </div>
              <div className="p-3 rounded-xl bg-blue-50/60 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900/60">
                <span className="text-[10px] text-blue-700 dark:text-blue-400 font-mono uppercase block">Skill Match</span>
                <span className="font-extrabold text-blue-800 dark:text-blue-300 text-sm">{selectedRecord.skill_match_pct}%</span>
              </div>
            </div>

            {/* Candidate Self-Reported Competencies */}
            <div className="space-y-2 text-xs">
              <h4 className="font-bold text-slate-900 dark:text-white uppercase tracking-wider text-[11px] font-mono text-slate-500">
                Verified Candidate Skills
              </h4>
              <div className="flex flex-wrap gap-1.5 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700">
                {selectedRecord.skills?.map((sk, idx) => (
                  <span
                    key={idx}
                    className="px-2.5 py-1 rounded-lg bg-teal-100 dark:bg-teal-950 text-teal-900 dark:text-teal-200 font-medium text-xs border border-teal-200 dark:border-teal-800"
                  >
                    {sk}
                  </span>
                ))}
              </div>
            </div>

            {/* Identified Skill Deficits */}
            {Array.isArray(selectedRecord.evaluation_summary?.missing_skills) && selectedRecord.evaluation_summary.missing_skills.length > 0 && (
              <div className="space-y-2 text-xs">
                <h4 className="font-bold text-slate-900 dark:text-white uppercase tracking-wider text-[11px] font-mono text-rose-600 dark:text-rose-400">
                  Target Role Skill Deficits (Gaps)
                </h4>
                <div className="grid grid-cols-2 gap-2">
                  {selectedRecord.evaluation_summary.missing_skills.map((m, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 flex items-center justify-between"
                    >
                      <div>
                        <span className="font-bold text-slate-900 dark:text-white block">{m?.name || 'Skill Deficit'}</span>
                        <span className="text-[10px] text-slate-400">{m?.category || 'General'}</span>
                      </div>
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase font-mono bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300">
                        {m?.priority || 'HIGH'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommended Learning Steps */}
            {Array.isArray(selectedRecord.evaluation_summary?.recommended_next_steps) && selectedRecord.evaluation_summary.recommended_next_steps.length > 0 && (
              <div className="space-y-2 text-xs">
                <h4 className="font-bold text-slate-900 dark:text-white uppercase tracking-wider text-[11px] font-mono text-teal-600 dark:text-teal-400">
                  Recommended Curriculum Track
                </h4>
                <ul className="space-y-1.5 bg-slate-50 dark:bg-slate-800/40 p-3 rounded-xl border border-slate-200 dark:border-slate-700">
                  {selectedRecord.evaluation_summary.recommended_next_steps.map((st, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-slate-700 dark:text-slate-300">
                      <span className="w-4 h-4 rounded-full bg-teal-600 text-white font-bold text-[9px] flex items-center justify-center shrink-0 mt-0.5">
                        {idx + 1}
                      </span>
                      <span>{st}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-slate-800 text-xs">
              <button
                onClick={() => handleDelete(selectedRecord.id, selectedRecord.name)}
                className="text-rose-600 hover:text-rose-700 font-bold cursor-pointer"
              >
                Delete Record ✕
              </button>
              <button
                onClick={() => setInspectModalOpen(false)}
                className="px-4 py-2 bg-slate-900 dark:bg-teal-600 text-white font-bold rounded-xl transition-colors cursor-pointer"
              >
                Close Audit View
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 2: EMPLOYER DEMAND AUDIT & VALIDATION MODAL (PHASE 14) */}
      {/* ========================================================================= */}
      {inspectDemandModalOpen && selectedDemand && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs animate-fadeIn">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto space-y-5 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-extrabold text-slate-900 dark:text-white text-lg">
                    {selectedDemand.job_role || selectedDemand.role_title}
                  </h3>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded font-mono uppercase ${
                      (selectedDemand.validation_status || selectedDemand.status || '').toUpperCase() === 'VALIDATED'
                        ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-300'
                        : (selectedDemand.validation_status || selectedDemand.status || '').toUpperCase() === 'REJECTED'
                        ? 'bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 border border-rose-300'
                        : 'bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-300'
                    }`}
                  >
                    Status: {selectedDemand.validation_status || selectedDemand.status || 'PENDING'}
                  </span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  {selectedDemand.company_name || selectedDemand.employer_name} • 📍 {selectedDemand.district} • {selectedDemand.industry}
                </p>
              </div>
              <button
                onClick={() => setInspectDemandModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-2 text-base cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Demand Metadata Badges */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                <span className="text-[10px] text-slate-400 font-mono uppercase block">Open Vacancies</span>
                <span className="font-bold text-slate-900 dark:text-white text-sm">
                  {selectedDemand.openings_count || selectedDemand.positions_count || 1} Seats
                </span>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                <span className="text-[10px] text-slate-400 font-mono uppercase block">Experience</span>
                <span className="font-bold text-slate-900 dark:text-white text-sm">
                  {selectedDemand.experience_level || 'Entry-Mid'}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                <span className="text-[10px] text-slate-400 font-mono uppercase block">Proficiency</span>
                <span className="font-bold text-slate-900 dark:text-white text-sm capitalize">
                  {selectedDemand.preferred_proficiency || selectedDemand.proficiency_required || 'Intermediate'}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                <span className="text-[10px] text-slate-400 font-mono uppercase block">Timeline</span>
                <span className="font-bold text-slate-900 dark:text-white text-sm">
                  {selectedDemand.hiring_timeline || selectedDemand.urgency || 'Immediate'}
                </span>
              </div>
            </div>

            {/* Required Skills Chips */}
            <div className="space-y-2 text-xs">
              <h4 className="font-bold text-slate-900 dark:text-white uppercase tracking-wider text-[11px] font-mono text-slate-500">
                Required Industry Competencies & Skills
              </h4>
              <div className="flex flex-wrap gap-1.5 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700">
                {(selectedDemand.required_skills || selectedDemand.skills || []).map((sk, idx) => (
                  <span
                    key={idx}
                    className="px-2.5 py-1 rounded-lg bg-teal-100 dark:bg-teal-950 text-teal-900 dark:text-teal-200 font-medium text-xs border border-teal-200 dark:border-teal-800"
                  >
                    {typeof sk === 'object' ? sk.name : sk}
                  </span>
                ))}
              </div>
            </div>

            {/* Hiring Challenges / Additional Requirements */}
            {(selectedDemand.additional_requirements || selectedDemand.hiring_challenge) && (
              <div className="space-y-1.5 text-xs">
                <h4 className="font-bold text-slate-900 dark:text-white uppercase tracking-wider text-[11px] font-mono text-slate-500">
                  Employer Context / Bottleneck Note
                </h4>
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 italic text-slate-700 dark:text-slate-300">
                  "{selectedDemand.additional_requirements || selectedDemand.hiring_challenge}"
                </div>
              </div>
            )}

            {/* Provenance Stamp */}
            <div className="p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs space-y-1">
              <div className="flex justify-between font-mono text-[11px] text-slate-600 dark:text-slate-300">
                <span>Data Provenance Source:</span>
                <span className="font-bold">{selectedDemand.source || 'EMPLOYER_SUBMITTED'}</span>
              </div>
              <div className="flex justify-between font-mono text-[11px] text-slate-600 dark:text-slate-300">
                <span>Unique Demand Identifier:</span>
                <span>{selectedDemand.id}</span>
              </div>
              <div className="flex justify-between font-mono text-[11px] text-slate-600 dark:text-slate-300">
                <span>Recorded Timestamp:</span>
                <span>{selectedDemand.submitted_at || selectedDemand.submitted_date || 'Baseline'}</span>
              </div>
            </div>

            {/* Administrative Validation Notes & Action Panel */}
            <div className="space-y-3 pt-2 border-t border-slate-100 dark:border-slate-800 text-xs">
              <label className="font-bold text-slate-700 dark:text-slate-300 block">
                Administrative Calibration Notes / Audit Remarks:
              </label>
              <textarea
                value={adminNotesInput}
                onChange={(e) => setAdminNotesInput(e.target.value)}
                placeholder="e.g. Verified with HR director; valid 2026 apprenticeship intake for Pune plant..."
                className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-teal-500 h-16"
              />

              <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => handleDeleteDemand(selectedDemand.id, selectedDemand.company_name || selectedDemand.employer_name, selectedDemand.job_role || selectedDemand.role_title)}
                  className="text-rose-600 hover:text-rose-700 font-bold cursor-pointer text-xs"
                >
                  Delete Demand ✕
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleUpdateDemandStatus(selectedDemand.id, 'REJECTED', adminNotesInput)}
                    className="px-3 py-2 bg-rose-100 hover:bg-rose-200 dark:bg-rose-950 dark:hover:bg-rose-900 text-rose-700 dark:text-rose-300 font-bold rounded-xl text-xs transition-colors cursor-pointer"
                  >
                    Mark as Rejected ✕
                  </button>
                  <button
                    type="button"
                    onClick={() => handleUpdateDemandStatus(selectedDemand.id, 'VALIDATED', adminNotesInput)}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl text-xs transition-colors cursor-pointer shadow-xs"
                  >
                    Validate Requirement ✓
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* VIEW 2.5: INSTITUTE COURSES & VOCATIONAL PROGRAMS (PHASE 25) */}
      {/* ========================================================================= */}
      {adminTab === 'institutes' && (
        <div data-demo="admin-institutes-section">
          {/* Top Aggregate KPI Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
            <StatCard
              title="Total Courses"
              value={courseStats.total}
              subtitle="All accredited curriculum records"
              icon="📚"
            />
            <StatCard
              title="First-Party Reported"
              value={courseStats.user_submitted_count}
              subtitle="Direct institute submissions"
              icon="🏛️"
              color="teal"
            />
            <StatCard
              title="State Benchmark"
              value={courseStats.demo_synthetic_count}
              subtitle="Baseline curriculum profiles"
              icon="🔬"
              color="slate"
            />
            <StatCard
              title="Monitored Trades"
              value={adminCourses.length}
              subtitle="Matching current filters"
              icon="⚙️"
              color="amber"
            />
          </div>

          {/* Filter Bar */}
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 mb-6 shadow-xs">
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  District
                </label>
                <select
                  value={courseDistrictFilter}
                  onChange={(e) => setCourseDistrictFilter(e.target.value)}
                  className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 cursor-pointer"
                >
                  <option value="All Districts">All Districts</option>
                  {DISTRICTS.filter((d) => d !== 'All Districts').map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Data Provenance
                </label>
                <select
                  value={courseSourceFilter}
                  onChange={(e) => setCourseSourceFilter(e.target.value)}
                  className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 cursor-pointer"
                >
                  <option value="all">All Sources</option>
                  <option value="USER_SUBMITTED">First-Party Submitted</option>
                  <option value="DEMO_SYNTHETIC">State Benchmark</option>
                </select>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Alignment Status
                </label>
                <select
                  value={courseStatusFilter}
                  onChange={(e) => setCourseStatusFilter(e.target.value)}
                  className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 cursor-pointer"
                >
                  <option value="all">All Statuses</option>
                  <option value="active">Aligned / Active</option>
                  <option value="needs_attention">Curriculum Gap Flagged</option>
                  <option value="review_oversupply">Oversupply Flagged</option>
                </select>
              </div>

              <div className="flex flex-col gap-1 flex-1 min-w-[200px]">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Search
                </label>
                <input
                  type="text"
                  value={courseSearchTerm}
                  onChange={(e) => setCourseSearchTerm(e.target.value)}
                  placeholder="Search course title, institute, or skills..."
                  className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 placeholder-slate-400"
                />
              </div>
            </div>
          </div>

          {/* Courses Table */}
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden mb-6">
            {coursesLoading ? (
              <div className="py-12 text-center">
                <div className="w-6 h-6 border-2 border-teal-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                <p className="text-xs text-slate-500">Loading institute curriculum directory...</p>
              </div>
            ) : adminCourses.length === 0 ? (
              <div className="py-12 text-center">
                <p className="text-xs text-slate-500">No institute programs match the current filters.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 font-semibold border-b border-slate-200 dark:border-slate-700">
                    <tr>
                      <th className="p-3">Course Title</th>
                      <th className="p-3">Institute & District</th>
                      <th className="p-3">Provenance</th>
                      <th className="p-3">Capacity</th>
                      <th className="p-3">Placement Rate</th>
                      <th className="p-3">Alignment Status</th>
                      <th className="p-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {adminCourses.map((c) => {
                      const isUserSubmitted = c.source === 'USER_SUBMITTED';
                      const isOversupply = c.status === 'review_oversupply';
                      const isGap = c.status === 'needs_attention';

                      return (
                        <tr key={c.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/50 transition-colors">
                          <td className="p-3 font-bold text-slate-900 dark:text-white max-w-xs">
                            <div className="flex items-center gap-1.5">
                              <span>{c.name || c.course_name}</span>
                            </div>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-normal mt-0.5 line-clamp-1">
                              {c.description || '—'}
                            </p>
                          </td>
                          <td className="p-3 text-slate-600 dark:text-slate-300">
                            <div className="font-medium text-slate-800 dark:text-slate-200">
                              {c.institute || c.institute_name}
                            </div>
                            <div className="text-[11px] text-slate-400 font-mono">
                              📍 {c.district}
                            </div>
                          </td>
                          <td className="p-3">
                            {isUserSubmitted ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 dark:bg-purple-950 text-purple-800 dark:text-purple-300 border border-purple-300 dark:border-purple-800 font-mono">
                                USER SUBMITTED
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700 font-mono">
                                DEMO SYNTHETIC
                              </span>
                            )}
                          </td>
                          <td className="p-3 font-mono font-semibold text-slate-700 dark:text-slate-300">
                            {c.enrolment_count || c.enrolment_capacity || 0} seats
                          </td>
                          <td className="p-3 font-mono font-bold">
                            <span
                              className={
                                c.placement_rate >= 75
                                  ? 'text-emerald-600 dark:text-emerald-400'
                                  : c.placement_rate >= 50
                                  ? 'text-amber-600 dark:text-amber-400'
                                  : 'text-rose-600 dark:text-rose-400'
                              }
                            >
                              {c.placement_rate ?? 70}%
                            </span>
                          </td>
                          <td className="p-3">
                            {isOversupply ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-800">
                                OVERSUPPLY
                              </span>
                            ) : isGap ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
                                CURRICULUM GAP
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
                                ALIGNED
                              </span>
                            )}
                          </td>
                          <td className="p-3 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => {
                                  setSelectedAdminCourse(c);
                                  setInspectCourseModalOpen(true);
                                }}
                                className="px-2.5 py-1 bg-slate-100 dark:bg-slate-800 hover:bg-teal-50 dark:hover:bg-teal-950 text-slate-700 dark:text-slate-300 rounded font-semibold text-[11px] border border-slate-200 dark:border-slate-700 transition-colors cursor-pointer"
                              >
                                Audit 🔍
                              </button>
                              <button
                                onClick={() => handleDeleteAdminCourse(c.id, c.name || c.course_name)}
                                className="p-1 text-slate-400 hover:text-rose-600 rounded transition-colors cursor-pointer"
                                title="Delete Course"
                              >
                                ✕
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* INSPECT INSTITUTE COURSE MODAL (Phase 25) */}
      {inspectCourseModalOpen && selectedAdminCourse && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs animate-fadeIn">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl overflow-y-auto max-h-[85vh]">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
              <h3 className="font-extrabold text-slate-900 dark:text-white text-base">
                🎓 Course Program Audit
              </h3>
              <button
                onClick={() => setInspectCourseModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-lg cursor-pointer"
              >
                ✕
              </button>
            </div>
            <div className="space-y-3 text-xs">
              <div>
                <span className="font-bold text-slate-700 dark:text-slate-300">Course Name:</span>{' '}
                <span className="text-slate-900 dark:text-white">{selectedAdminCourse.name}</span>
              </div>
              <div>
                <span className="font-bold text-slate-700 dark:text-slate-300">Institute:</span>{' '}
                <span className="text-slate-900 dark:text-white">{selectedAdminCourse.institute || selectedAdminCourse.institute_name}</span>
              </div>
              <div>
                <span className="font-bold text-slate-700 dark:text-slate-300">District:</span>{' '}
                <span>{selectedAdminCourse.district}</span>
              </div>
              <div>
                <span className="font-bold text-slate-700 dark:text-slate-300">Category:</span>{' '}
                <span>{selectedAdminCourse.category}</span>
              </div>
              <div>
                <span className="font-bold text-slate-700 dark:text-slate-300">Intake / Placed:</span>{' '}
                <span className="font-mono">
                  {selectedAdminCourse.enrolment_count || selectedAdminCourse.enrolment_capacity || 0} intake / {selectedAdminCourse.placed_count || 0} placed ({selectedAdminCourse.placement_rate || 0}%)
                </span>
              </div>
              <div>
                <span className="font-bold text-slate-700 dark:text-slate-300">Skills Taught:</span>{' '}
                <span>{(selectedAdminCourse.skills || selectedAdminCourse.skills_taught || []).join(', ') || '—'}</span>
              </div>
              <div>
                <span className="font-bold text-slate-700 dark:text-slate-300">Description:</span>{' '}
                <p className="text-slate-600 dark:text-slate-300 mt-1 p-2 bg-slate-50 dark:bg-slate-800/40 rounded-lg">
                  {selectedAdminCourse.description || '—'}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <div>
                  <span className="font-bold text-slate-700 dark:text-slate-300">Source:</span>{' '}
                  <span className="font-mono text-[10px] px-1 py-0.5 rounded bg-slate-100 dark:bg-slate-800">
                    {selectedAdminCourse.source || 'DEMO_SYNTHETIC'}
                  </span>
                </div>
                <div>
                  <span className="font-bold text-slate-700 dark:text-slate-300">NSQF:</span>{' '}
                  <span className="font-mono text-[10px]">Level {selectedAdminCourse.nsqf_level || 5}</span>
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center gap-2">
              <button
                onClick={() => handleDeleteAdminCourse(selectedAdminCourse.id, selectedAdminCourse.name)}
                className="px-3 py-1.5 text-xs font-bold text-rose-600 bg-rose-50 dark:bg-rose-950 border border-rose-200 dark:border-rose-800 rounded-xl hover:bg-rose-100 cursor-pointer"
              >
                Delete Course
              </button>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleUpdateAdminCourseStatus(selectedAdminCourse.id, 'active')}
                  className="px-3 py-1.5 text-xs font-bold text-emerald-700 bg-emerald-50 dark:bg-emerald-950 border border-emerald-300 dark:border-emerald-800 rounded-xl hover:bg-emerald-100 cursor-pointer"
                >
                  Mark Aligned
                </button>
                <button
                  onClick={() => handleUpdateAdminCourseStatus(selectedAdminCourse.id, 'needs_attention')}
                  className="px-3 py-1.5 text-xs font-bold text-amber-700 bg-amber-50 dark:bg-amber-950 border border-amber-300 dark:border-amber-800 rounded-xl hover:bg-amber-100 cursor-pointer"
                >
                  Flag Gap
                </button>
                <button
                  onClick={() => setInspectCourseModalOpen(false)}
                  className="px-3 py-1.5 text-xs font-bold text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* VIEW 3: GOVERNMENT OPPORTUNITIES MANAGEMENT (PHASE 15) */}
      {/* ========================================================================= */}
      {adminTab === 'gov' && (
        <div data-demo="admin-gov-section">
          {/* KPI Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
            <StatCard
              title="Total Opportunities"
              value={govStats.total}
              description="All government opportunity records"
            />
            <StatCard
              title="Active"
              value={govStats.active_count}
              description="Currently active programs"
            />
            <StatCard
              title="Inactive / Expired"
              value={govStats.inactive_count}
              description="Paused or expired records"
            />
            <StatCard
              title="Demo / Synthetic"
              value={govStats.demo_count}
              description="Records from demo dataset"
            />
          </div>

          {/* Filters Bar */}
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 mb-6 shadow-xs">
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">District</label>
                <select
                  value={govDistrictFilter}
                  onChange={(e) => setGovDistrictFilter(e.target.value)}
                  className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 cursor-pointer"
                >
                  <option value="all">All Districts</option>
                  {DISTRICTS.filter((d) => d !== 'All Districts').map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Type</label>
                <select
                  value={govTypeFilter}
                  onChange={(e) => setGovTypeFilter(e.target.value)}
                  className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 cursor-pointer"
                >
                  <option value="all">All Types</option>
                  <option value="apprenticeship">Apprenticeship</option>
                  <option value="training_program">Training Program</option>
                  <option value="employment">Employment</option>
                  <option value="internship">Internship</option>
                  <option value="entrepreneurship">Entrepreneurship</option>
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Status</label>
                <select
                  value={govStatusFilter}
                  onChange={(e) => setGovStatusFilter(e.target.value)}
                  className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 cursor-pointer"
                >
                  <option value="all">All Statuses</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="expired">Expired</option>
                </select>
              </div>
              <div className="flex flex-col gap-1 flex-1 min-w-[200px]">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Search</label>
                <input
                  type="text"
                  value={govSearchTerm}
                  onChange={(e) => setGovSearchTerm(e.target.value)}
                  placeholder="Search by name, department, or description..."
                  className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 placeholder-slate-400"
                />
              </div>
              <button
                onClick={() => setGovAddModalOpen(true)}
                className="px-4 py-1.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-lg transition-colors cursor-pointer whitespace-nowrap"
              >
                + Add Opportunity
              </button>
            </div>
          </div>

          {/* Table */}
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
            {govLoading ? (
              <div className="py-12 text-center">
                <div className="w-6 h-6 border-2 border-teal-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                <p className="text-xs text-slate-500">Loading government opportunities...</p>
              </div>
            ) : govOpportunities.length === 0 ? (
              <div className="py-12 text-center">
                <p className="text-xs text-slate-500">No government opportunities match the current filters.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40">
                      <th className="px-3 py-2.5 font-bold text-slate-700 dark:text-slate-300">Name</th>
                      <th className="px-3 py-2.5 font-bold text-slate-700 dark:text-slate-300">Department</th>
                      <th className="px-3 py-2.5 font-bold text-slate-700 dark:text-slate-300">Type</th>
                      <th className="px-3 py-2.5 font-bold text-slate-700 dark:text-slate-300">District</th>
                      <th className="px-3 py-2.5 font-bold text-slate-700 dark:text-slate-300">Status</th>
                      <th className="px-3 py-2.5 font-bold text-slate-700 dark:text-slate-300">Source</th>
                      <th className="px-3 py-2.5 font-bold text-slate-700 dark:text-slate-300">Updated</th>
                      <th className="px-3 py-2.5 font-bold text-slate-700 dark:text-slate-300">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {govOpportunities.map((opp) => (
                      <tr key={opp.id} className="border-b border-slate-100 dark:border-slate-800/60 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                        <td className="px-3 py-2.5 font-semibold text-slate-900 dark:text-white max-w-[200px] truncate" title={opp.name}>
                          {opp.name}
                        </td>
                        <td className="px-3 py-2.5 text-slate-600 dark:text-slate-300 max-w-[180px] truncate" title={opp.department}>
                          {opp.department}
                        </td>
                        <td className="px-3 py-2.5">
                          <span className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 uppercase font-mono font-semibold text-[9px]">
                            {(opp.opportunity_type || '').replace('_', ' ')}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-slate-600 dark:text-slate-300">
                          {typeof opp.district_coverage === 'object' ? (opp.district_coverage || []).join(', ') : (opp.district_coverage || '')}
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase font-mono ${
                            opp.status === 'active' ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300' :
                            opp.status === 'inactive' ? 'bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300' :
                            'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                          }`}>
                            {opp.status || 'active'}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
                            {opp.source || 'DEMO_SYNTHETIC'}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-slate-500 dark:text-slate-400 font-mono text-[9px]">
                          {opp.last_updated || '—'}
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-1.5">
                            <button
                              onClick={() => { setSelectedGovOpp(opp); setInspectGovModalOpen(true); }}
                              className="px-2 py-1 text-[10px] font-bold bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg transition-colors cursor-pointer"
                            >
                              View
                            </button>
                            {opp.status === 'active' ? (
                              <button
                                onClick={() => handleUpdateGovStatus(opp.id, 'inactive')}
                                className="px-2 py-1 text-[10px] font-bold bg-amber-50 dark:bg-amber-950 hover:bg-amber-100 dark:hover:bg-amber-900 text-amber-700 dark:text-amber-300 rounded-lg transition-colors cursor-pointer"
                              >
                                Deactivate
                              </button>
                            ) : (
                              <button
                                onClick={() => handleUpdateGovStatus(opp.id, 'active')}
                                className="px-2 py-1 text-[10px] font-bold bg-emerald-50 dark:bg-emerald-950 hover:bg-emerald-100 dark:hover:bg-emerald-900 text-emerald-700 dark:text-emerald-300 rounded-lg transition-colors cursor-pointer"
                              >
                                Activate
                              </button>
                            )}
                            <button
                              onClick={() => handleDeleteGov(opp.id, opp.name)}
                              className="px-2 py-1 text-[10px] font-bold bg-rose-50 dark:bg-rose-950 hover:bg-rose-100 dark:hover:bg-rose-900 text-rose-600 dark:text-rose-400 rounded-lg transition-colors cursor-pointer"
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 5. INDUSTRY INTELLIGENCE & AUTOMATED INGESTION TAB (Phase 26)             */}
      {/* ========================================================================= */}
      {adminTab === 'industry' && (
        <div data-demo="admin-signals-section">
          {/* Header & Ingestion Trigger Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-extrabold text-slate-900 dark:text-white text-lg">
                  📡 Industry Intelligence & Automated Ingestion
                </h3>
                <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                  Phase 26 Pipeline
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Continuous ingestion pipeline across trusted government, industry association, and tech documentation registries.
              </p>
            </div>

            <button
              onClick={handleTriggerIndustryIngest}
              disabled={ingestRunning}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-bold rounded-xl shadow-xs transition-all cursor-pointer shrink-0"
            >
              {ingestRunning ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Running Ingestion Sync...</span>
                </>
              ) : (
                <>
                  <span>🔄</span>
                  <span>Ingest Industry Intelligence Now</span>
                </>
              )}
            </button>
          </div>

          {/* KPI Statistics Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
            <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
              <span className="text-[10px] uppercase font-mono font-bold text-slate-400 block mb-1">Total Ingested Signals</span>
              <span className="text-2xl font-extrabold text-slate-900 dark:text-white">{signalStats.total}</span>
              <span className="text-[10px] text-slate-400 block mt-0.5 font-mono">Deduplicated pool</span>
            </div>

              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-emerald-200 dark:border-emerald-900/40 shadow-xs">
                <span className="text-[10px] uppercase font-mono font-bold text-emerald-600 dark:text-emerald-400 block mb-1">Fresh Signals (&lt; 7 Days)</span>
                <span className="text-2xl font-extrabold text-emerald-600 dark:text-emerald-400">{signalStats.fresh_count}</span>
                <span className="text-[10px] text-emerald-700/70 dark:text-emerald-400/70 block mt-0.5 font-mono">High priority feed</span>
              </div>

              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
                <span className="text-[10px] uppercase font-mono font-bold text-slate-400 block mb-1">Approved &amp; Active</span>
                <span className="text-2xl font-extrabold text-indigo-600 dark:text-indigo-400">
                  {signalStats.approved_count} <span className="text-xs text-slate-400">/ {signalStats.active_count} active</span>
                </span>
                <span className="text-[10px] text-slate-400 block mt-0.5 font-mono">Visible to students</span>
              </div>

              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-900/40 shadow-xs">
                <span className="text-[10px] uppercase font-mono font-bold text-amber-600 dark:text-amber-400 block mb-1">Pending Calibration</span>
                <span className="text-2xl font-extrabold text-amber-600 dark:text-amber-400">{signalStats.pending_count}</span>
                <span className="text-[10px] text-amber-700/70 dark:text-amber-400/70 block mt-0.5 font-mono">Requires admin review</span>
              </div>

              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs col-span-2 lg:col-span-1">
                <span className="text-[10px] uppercase font-mono font-bold text-slate-400 block mb-1">Trusted Source Registries</span>
                <span className="text-2xl font-extrabold text-slate-900 dark:text-white">
                  {ingestionStatus?.registered_sources_count || 8}
                </span>
                <span className="text-[10px] text-slate-400 block mt-0.5 font-mono">Gov, NASSCOM, SIAM, CNCF</span>
              </div>
            </div>

            {/* Ingestion Engine Audit Status Card */}
            {ingestionStatus?.last_ingestion && (
              <div className="mb-6 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-xs">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-200 dark:border-slate-700">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-slate-800 dark:text-slate-200">Ingestion Status:</span>
                    <span className="font-mono px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-bold uppercase text-[10px]">
                      {ingestionStatus.last_ingestion.status}
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-slate-500">
                    Last Sync Run: {ingestionStatus.last_ingestion.last_run ? new Date(ingestionStatus.last_ingestion.last_run).toLocaleString() : 'Idle'}
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 text-[11px] font-mono">
                  <div>Fetched: <strong className="text-slate-900 dark:text-white">{ingestionStatus.last_ingestion.records_fetched}</strong></div>
                  <div>Added: <strong className="text-emerald-600 dark:text-emerald-400">{ingestionStatus.last_ingestion.records_added}</strong></div>
                  <div>Updated: <strong className="text-indigo-600 dark:text-indigo-400">{ingestionStatus.last_ingestion.records_updated}</strong></div>
                  <div>Deduplicated: <strong className="text-slate-500">{ingestionStatus.last_ingestion.records_duplicated}</strong></div>
                </div>
              </div>
            )}

            {/* Multi-Parameter Filters */}
            <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 mb-4 shadow-xs space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block mb-1">
                    Category
                  </label>
                  <select
                    value={signalCategoryFilter}
                    onChange={(e) => setSignalCategoryFilter(e.target.value)}
                    className="w-full text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white cursor-pointer"
                  >
                    <option value="all">All Categories</option>
                    <option value="NEW_TECHNOLOGY">New Technology</option>
                    <option value="EMERGING_SKILL">Emerging Skill</option>
                    <option value="INDUSTRY_DEMAND">Industry Demand</option>
                    <option value="JOB_MARKET">Job Market</option>
                    <option value="GOVERNMENT_UPDATE">Government Update</option>
                    <option value="CERTIFICATION">Certification</option>
                    <option value="TRAINING">Training</option>
                    <option value="TOOL_RELEASE">Tool Release</option>
                  </select>
                </div>

                <div>
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block mb-1">
                    Validation Status
                  </label>
                  <select
                    value={signalStatusFilter}
                    onChange={(e) => setSignalStatusFilter(e.target.value)}
                    className="w-full text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white cursor-pointer"
                  >
                    <option value="all">All Statuses</option>
                    <option value="APPROVED">Approved</option>
                    <option value="PENDING">Pending Review</option>
                    <option value="REJECTED">Rejected</option>
                    <option value="ARCHIVED">Archived</option>
                  </select>
                </div>

                <div>
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block mb-1">
                    Freshness Classification
                  </label>
                  <select
                    value={signalFreshnessFilter}
                    onChange={(e) => setSignalFreshnessFilter(e.target.value)}
                    className="w-full text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white cursor-pointer"
                  >
                    <option value="all">All Freshness</option>
                    <option value="NEW">NEW (&lt; 7 Days)</option>
                    <option value="RECENT">RECENT (7–30 Days)</option>
                    <option value="OLDER">OLDER (30–180 Days)</option>
                    <option value="EXPIRED">EXPIRED / ARCHIVED</option>
                  </select>
                </div>

                <div>
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block mb-1">
                    Search Keywords
                  </label>
                  <input
                    type="text"
                    value={signalSearchTerm}
                    onChange={(e) => setSignalSearchTerm(e.target.value)}
                    placeholder="Search title, skills, tools, source..."
                    className="w-full text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                  />
                </div>
              </div>
            </div>

            {/* Signals Table */}
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
              {signalsLoading ? (
                <div className="py-12 text-center">
                  <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                  <p className="text-xs text-slate-500">Loading industry signals...</p>
                </div>
              ) : adminSignals.length === 0 ? (
                <div className="py-12 text-center space-y-3">
                  <p className="text-xs text-slate-500">No industry signals match the current filters.</p>
                  <button
                    onClick={handleTriggerIndustryIngest}
                    className="px-3 py-1.5 bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-bold text-xs rounded-lg border border-indigo-200 dark:border-indigo-800"
                  >
                    Trigger Fresh Ingestion Run
                  </button>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        <th className="py-3 px-4">Title &amp; Category</th>
                        <th className="py-3 px-4">Source &amp; Provenance</th>
                        <th className="py-3 px-4">Skills &amp; Tools</th>
                        <th className="py-3 px-4">Published &amp; Freshness</th>
                        <th className="py-3 px-4">Status &amp; Visibility</th>
                        <th className="py-3 px-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {adminSignals.map((sig) => (
                        <tr key={sig.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                          <td className="py-3 px-4 max-w-xs">
                            <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 block mb-1 w-fit">
                              {sig.category}
                            </span>
                            <span className="font-bold text-slate-900 dark:text-white block leading-snug">
                              {sig.title}
                            </span>
                            <span className="text-[11px] text-slate-500 truncate block mt-0.5">
                              {sig.industry}
                            </span>
                          </td>

                          <td className="py-3 px-4">
                            <span className="font-semibold text-slate-800 dark:text-slate-200 block">
                              {sig.source_name}
                            </span>
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 mt-1 inline-block">
                              {sig.data_provenance}
                            </span>
                          </td>

                          <td className="py-3 px-4 max-w-[180px]">
                            <div className="flex flex-wrap gap-1">
                              {(sig.skills || []).slice(0, 3).map((sk, idx) => (
                                <span key={idx} className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium">
                                  {sk}
                                </span>
                              ))}
                              {(sig.skills || []).length > 3 && (
                                <span className="text-[10px] text-slate-400 font-mono">+{sig.skills.length - 3}</span>
                              )}
                            </div>
                          </td>

                          <td className="py-3 px-4">
                            <span className="font-mono text-[11px] text-slate-700 dark:text-slate-300 block">
                              {sig.published_at ? sig.published_at.slice(0, 10) : '—'}
                            </span>
                            <span
                              className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-full inline-block mt-1 ${
                                sig.freshness === 'NEW'
                                  ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                                  : sig.freshness === 'RECENT'
                                  ? 'bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800'
                                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                              }`}
                            >
                              {sig.freshness}
                            </span>
                          </td>

                          <td className="py-3 px-4">
                            <div className="flex items-center gap-2">
                              <span
                                className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full ${
                                  sig.validation_status === 'APPROVED'
                                    ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                                    : sig.validation_status === 'PENDING'
                                    ? 'bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800'
                                    : 'bg-rose-50 dark:bg-rose-950 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800'
                                }`}
                              >
                                {sig.validation_status}
                              </span>
                              <span className={`text-[10px] font-bold ${sig.is_active ? 'text-emerald-600' : 'text-slate-400'}`}>
                                {sig.is_active ? 'Active' : 'Inactive'}
                              </span>
                            </div>
                          </td>

                          <td className="py-3 px-4 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => {
                                  setSelectedSignal(sig);
                                  setSignalAdminNotesInput(sig.admin_notes || '');
                                  setInspectSignalModalOpen(true);
                                }}
                                className="px-2.5 py-1 text-[11px] font-bold text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg transition-colors cursor-pointer"
                              >
                                Audit / Edit
                              </button>
                              <button
                                onClick={() => handleToggleSignalActive(sig.id, sig.is_active)}
                                className={`px-2 py-1 text-[10px] font-bold rounded-lg transition-colors cursor-pointer ${
                                  sig.is_active
                                    ? 'bg-slate-100 dark:bg-slate-800 text-slate-600 hover:bg-slate-200'
                                    : 'bg-emerald-50 dark:bg-emerald-950 text-emerald-700 hover:bg-emerald-100'
                                }`}
                              >
                                {sig.is_active ? 'Deactivate' : 'Activate'}
                              </button>
                              <button
                                onClick={() => handleDeleteSignal(sig.id, sig.title)}
                                className="px-2 py-1 text-[10px] font-bold bg-rose-50 dark:bg-rose-950 hover:bg-rose-100 dark:hover:bg-rose-900 text-rose-600 dark:text-rose-400 rounded-lg transition-colors cursor-pointer"
                              >
                                ✕
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* INDUSTRY SIGNAL DETAIL & MODERATION MODAL (Phase 26)                       */}
        {/* ========================================================================= */}
        {inspectSignalModalOpen && selectedSignal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs animate-fadeIn">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-xl w-full p-6 space-y-4 shadow-2xl overflow-y-auto max-h-[90vh]">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center gap-2">
                  <span className="text-xl">📡</span>
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-bold block">
                      {selectedSignal.category} • {selectedSignal.data_provenance}
                    </span>
                    <h3 className="font-extrabold text-slate-900 dark:text-white text-base">
                      {selectedSignal.title}
                    </h3>
                  </div>
                </div>
                <button
                  onClick={() => setInspectSignalModalOpen(false)}
                  className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-lg cursor-pointer"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <span className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Signal Summary &amp; Description:</span>
                  <p className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 leading-relaxed">
                    {selectedSignal.description || selectedSignal.summary}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <span className="font-bold text-slate-700 dark:text-slate-300 block">Industry Sector:</span>
                    <span className="text-slate-900 dark:text-white font-semibold">{selectedSignal.industry}</span>
                  </div>
                  <div>
                    <span className="font-bold text-slate-700 dark:text-slate-300 block">Freshness Grade:</span>
                    <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">{selectedSignal.freshness}</span>
                  </div>
                </div>

                <div>
                  <span className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Target Competencies / Skills:</span>
                  <div className="flex flex-wrap gap-1">
                    {(selectedSignal.skills || []).map((sk, idx) => (
                      <span key={idx} className="px-2 py-0.5 rounded-md bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-medium text-xs border border-indigo-200 dark:border-indigo-800">
                        {sk}
                      </span>
                    ))}
                  </div>
                </div>

                {Array.isArray(selectedSignal.tools) && selectedSignal.tools.length > 0 && (
                  <div>
                    <span className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Technology Tools / Frameworks:</span>
                    <div className="flex flex-wrap gap-1">
                      {selectedSignal.tools.map((t, idx) => (
                        <span key={idx} className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono text-xs">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 space-y-1.5">
                  <div className="flex justify-between font-mono text-[11px]">
                    <span>Originating Source:</span>
                    <strong className="text-slate-900 dark:text-white">{selectedSignal.source_name}</strong>
                  </div>
                  {selectedSignal.source_url && (
                    <div className="flex justify-between font-mono text-[11px] truncate">
                      <span>Canonical URL:</span>
                      <a href={selectedSignal.source_url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 dark:text-indigo-400 underline truncate max-w-[65%]">
                        {selectedSignal.source_url}
                      </a>
                    </div>
                  )}
                  <div className="flex justify-between font-mono text-[11px]">
                    <span>Published Date:</span>
                    <span>{selectedSignal.published_at ? selectedSignal.published_at.slice(0, 10) : '—'}</span>
                  </div>
                </div>

                {/* Moderation Controls */}
                <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                  <label className="font-bold text-slate-700 dark:text-slate-300 block">
                    Admin Verification Notes &amp; Calibration:
                  </label>
                  <textarea
                    value={signalAdminNotesInput}
                    onChange={(e) => setSignalAdminNotesInput(e.target.value)}
                    placeholder="e.g. Verified with state curriculum board; priority elective for Pune polytechnics..."
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-indigo-500 h-16"
                  />

                  <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => handleDeleteSignal(selectedSignal.id, selectedSignal.title)}
                      className="text-rose-600 hover:text-rose-700 font-bold cursor-pointer text-xs"
                    >
                      Delete Signal ✕
                    </button>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleUpdateSignalStatus(selectedSignal.id, 'REJECTED', signalAdminNotesInput)}
                        className="px-3 py-1.5 bg-rose-100 hover:bg-rose-200 dark:bg-rose-950 dark:hover:bg-rose-900 text-rose-700 dark:text-rose-300 font-bold rounded-xl text-xs transition-colors cursor-pointer"
                      >
                        Reject ✕
                      </button>
                      <button
                        type="button"
                        onClick={() => handleUpdateSignalStatus(selectedSignal.id, 'ARCHIVED', signalAdminNotesInput)}
                        className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-bold rounded-xl text-xs transition-colors cursor-pointer"
                      >
                        Archive 📁
                      </button>
                      <button
                        type="button"
                        onClick={() => handleUpdateSignalStatus(selectedSignal.id, 'APPROVED', signalAdminNotesInput)}
                        className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl text-xs transition-colors cursor-pointer shadow-xs"
                      >
                        Approve &amp; Publish ✓
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ADD GOV OPPORTUNITY MODAL (Phase 15) */}
        {govAddModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs animate-fadeIn">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl overflow-y-auto max-h-[85vh]">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                <h3 className="font-extrabold text-slate-900 dark:text-white text-base">🏛️ Add Government Opportunity</h3>
                <button onClick={() => setGovAddModalOpen(false)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-lg cursor-pointer">✕</button>
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const fd = new FormData(e.target);
                  handleAddGovOpportunity({
                    name: fd.get('name'),
                    department: fd.get('department'),
                    description: fd.get('description'),
                    eligibility_criteria: fd.get('eligibility'),
                    target_skills: (fd.get('skills') || '').split(',').map((s) => s.trim()).filter(Boolean),
                    district_coverage: fd.get('district') || 'State-wide (Maharashtra)',
                    opportunity_type: fd.get('type'),
                    application_url: fd.get('url') || null,
                    deadline: fd.get('deadline') || null,
                    status: 'active',
                  });
                }}
                className="space-y-3"
              >
              <div><label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Name *</label><input name="name" required minLength={3} className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white" /></div>
              <div><label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Department *</label><input name="department" required minLength={3} className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white" /></div>
              <div><label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Description</label><textarea name="description" rows={2} className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white" /></div>
              <div><label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Eligibility Criteria</label><input name="eligibility" className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white" /></div>
              <div><label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Target Skills (comma-separated)</label><input name="skills" placeholder="e.g. IT, Mechanical, Electrical" className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">District</label><input name="district" defaultValue="State-wide (Maharashtra)" className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white" /></div>
                <div><label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Opportunity Type</label><select name="type" defaultValue="training_program" className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white cursor-pointer"><option value="apprenticeship">Apprenticeship</option><option value="training_program">Training Program</option><option value="employment">Employment</option><option value="internship">Internship</option><option value="entrepreneurship">Entrepreneurship</option></select></div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Application URL</label><input name="url" type="url" className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white" /></div>
                <div><label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Deadline</label><input name="deadline" type="date" className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white" /></div>
              </div>
              <p className="text-[10px] text-slate-500 dark:text-slate-400 italic">Note: This record will be created as ADMIN_CREATED source, not claimed as official or verified.</p>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setGovAddModalOpen(false)} className="px-4 py-2 text-xs font-bold text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer">Cancel</button>
                <button type="submit" className="px-5 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-xl cursor-pointer transition-colors">Create Opportunity</button>
              </div>
            </form>
          </div>
        </div>
      )}

      </div>
    </Layout>
  );
}

