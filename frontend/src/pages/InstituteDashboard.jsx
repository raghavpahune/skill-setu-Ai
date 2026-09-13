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
} from 'recharts';
import Layout from '../components/Layout';
import StatCard from '../components/StatCard';
import RecommendationCard from '../components/RecommendationCard';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

const DISTRICTS = [
  'All Districts',
  'Pune',
  'Mumbai',
  'Nagpur',
  'Nashik',
  'Chhatrapati Sambhajinagar',
  'Kolhapur',
  'Solapur',
  'Amravati',
  'Thane',
];

const CATEGORIES = [
  'Vocational & Emerging Tech',
  'Computer & Emerging Tech',
  'Information Technology',
  'Analytics & Data',
  'Cloud Infrastructure',
  'Automotive & Clean Energy',
  'Advanced Manufacturing',
  'Mechanical Design',
  'Electronics & IoT',
];

export default function InstituteDashboard() {
  const { user } = useAuth();
  const [courses, setCourses] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedDistrict, setSelectedDistrict] = useState('All Districts');
  const [provenanceFilter, setProvenanceFilter] = useState('all'); // 'all' | 'user' | 'demo'
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCourse, setSelectedCourse] = useState(null);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(null);

  // Submit Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);

  const [formState, setFormState] = useState({
    name: '',
    institute_name: user?.organization_id || user?.full_name || 'Government Polytechnic Pune',
    district: user?.district || 'Pune',
    category: 'Vocational & Emerging Tech',
    description: '',
    skillsInput: '',
    nsqf_level: 5,
    enrolment_capacity: 60,
    placed_count: 45,
    duration_weeks: 16,
    certifications: 'MSBTE & DGT Certificate',
  });

  // Phase 34: Syllabus Ingestion State & Handlers
  const [syllabusText, setSyllabusText] = useState('');
  const [extractingSyllabus, setExtractingSyllabus] = useState(false);

  const handleExtractSyllabus = async () => {
    if (!syllabusText.trim()) return;
    setExtractingSyllabus(true);
    try {
      const res = await api.extractInstituteSyllabus({
        syllabus_text: syllabusText.trim(),
        course_name: formState.name,
      });
      if (res?.extracted_skills?.length > 0) {
        setFormState((prev) => ({
          ...prev,
          name: prev.name.trim() || res.suggested_course_name,
          skillsInput: res.extracted_skills.join(', '),
          nsqf_level: res.suggested_nsqf_level || prev.nsqf_level,
          category: res.suggested_category || prev.category,
        }));
        showToast('success', res.summary);
      } else {
        showToast('error', 'No standard taxonomy skills recognized from syllabus text.');
      }
    } catch (err) {
      console.error('Syllabus extraction error:', err);
      showToast('error', `Failed to analyze syllabus: ${err?.message || 'Server error'}`);
    } finally {
      setExtractingSyllabus(false);
    }
  };

  const handleSyllabusFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      const content = evt.target?.result;
      if (typeof content === 'string') {
        setSyllabusText(content.slice(0, 10000));
        showToast('success', `Loaded "${file.name}" into syllabus assistant. Click "Auto-Extract Skills".`);
      }
    };
    reader.readAsText(file);
  };

  const showToast = (type, message) => {
    setToastMessage({ type, message });
    setTimeout(() => {
      setToastMessage(null);
    }, 4000);
  };

  const fetchCourses = async () => {
    setLoading(true);
    setApiError(null);
    try {
      const [coursesRes, recsRes] = await Promise.all([
        api.getInstituteCourses(),
        api.getCourseRecommendations(),
      ]);
      if (Array.isArray(coursesRes)) {
        setCourses(coursesRes);
      }
      if (Array.isArray(recsRes)) {
        setRecommendations(recsRes);
      }
    } catch (err) {
      console.warn('Failed loading institute live data:', err);
      setApiError(err?.message || 'Could not connect to live backend API.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCourses();
  }, []);

  const handleCreateCourse = async (e) => {
    e.preventDefault();
    if (!formState.name.trim()) {
      showToast('error', 'Please enter a course program name.');
      return;
    }
    const skillsList = formState.skillsInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    if (skillsList.length === 0) {
      showToast('error', 'Please specify at least one skill taught in the syllabus.');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        name: formState.name.trim(),
        institute_name: formState.institute_name.trim(),
        district: formState.district,
        category: formState.category,
        description: formState.description.trim() || `Vocational training program covering ${skillsList.join(', ')}.`,
        skills: skillsList,
        nsqf_level: Number(formState.nsqf_level) || 5,
        enrolment_capacity: Number(formState.enrolment_capacity) || 60,
        placed_count: Number(formState.placed_count) || 0,
        duration_weeks: Number(formState.duration_weeks) || 12,
        certifications: formState.certifications.trim(),
      };

      const res = await api.submitInstituteCourse(payload);
      showToast('success', 'Course program registered into state registry!');
      setIsModalOpen(false);
      setFormState({
        name: '',
        institute_name: user?.organization_id || user?.full_name || 'Government Polytechnic Pune',
        district: user?.district || 'Pune',
        category: 'Vocational & Emerging Tech',
        description: '',
        skillsInput: '',
        nsqf_level: 5,
        enrolment_capacity: 60,
        placed_count: 45,
        duration_weeks: 16,
        certifications: 'MSBTE & DGT Certificate',
      });

      if (res?.course) {
        setCourses((prev) => [res.course, ...prev]);
      } else {
        fetchCourses();
      }
    } catch (err) {
      showToast('error', err.message || 'Failed to submit course program.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteCourse = async (courseId, e) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to remove this course offering?')) return;
    try {
      await api.deleteInstituteCourse(courseId);
      setCourses((prev) => prev.filter((c) => c.id !== courseId));
      if (selectedCourse?.id === courseId) setSelectedCourse(null);
      showToast('success', 'Course program removed.');
    } catch (err) {
      showToast('error', err.message || 'Could not delete course.');
    }
  };

  // Filtered courses
  const filteredCourses = useMemo(() => {
    return courses.filter((c) => {
      // Status filter
      if (statusFilter === 'oversupply' && c.status !== 'review_oversupply') return false;
      if (statusFilter === 'attention' && c.status !== 'needs_attention') return false;
      if (statusFilter === 'healthy' && c.status !== 'active') return false;

      // Provenance filter
      if (provenanceFilter === 'user' && c.source !== 'USER_SUBMITTED') return false;
      if (provenanceFilter === 'demo' && c.source === 'USER_SUBMITTED') return false;

      // District filter
      if (selectedDistrict !== 'All Districts' && c.district?.toLowerCase() !== selectedDistrict.toLowerCase()) {
        return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const nameMatch = c.name?.toLowerCase().includes(q);
        const instMatch = (c.institute || c.institute_name || '').toLowerCase().includes(q);
        const descMatch = c.description?.toLowerCase().includes(q);
        const distMatch = c.district?.toLowerCase().includes(q);
        const skillMatch = Array.isArray(c.skills) && c.skills.some((s) => s.toLowerCase().includes(q));
        if (!nameMatch && !instMatch && !descMatch && !distMatch && !skillMatch) {
          return false;
        }
      }

      return true;
    });
  }, [courses, statusFilter, provenanceFilter, selectedDistrict, searchQuery]);

  // Executive Metrics
  const userSubmittedCount = useMemo(() => courses.filter((c) => c.source === 'USER_SUBMITTED').length, [courses]);
  const oversupplyCount = useMemo(() => courses.filter((c) => c.status === 'review_oversupply').length, [courses]);
  const attentionCount = useMemo(() => courses.filter((c) => c.status === 'needs_attention').length, [courses]);
  const alignedCount = useMemo(() => courses.filter((c) => c.status === 'active').length, [courses]);

  const avgPlacement = useMemo(() => {
    if (!courses.length) return 0;
    const total = courses.reduce((acc, c) => acc + (c.placement_rate || 0), 0);
    return Math.round(total / courses.length);
  }, [courses]);

  const totalEnrolment = useMemo(() => {
    return courses.reduce((acc, c) => acc + (c.enrolment_count || c.enrolment_capacity || 0), 0);
  }, [courses]);

  const totalPlaced = useMemo(() => {
    return courses.reduce((acc, c) => acc + (c.placed_count || 0), 0);
  }, [courses]);

  // Chart Data
  const chartData = useMemo(() => {
    return [...courses]
      .sort((a, b) => (b.enrolment_count || 0) - (a.enrolment_count || 0))
      .slice(0, 7)
      .map((c) => ({
        name: c.name.length > 22 ? `${c.name.slice(0, 20)}...` : c.name,
        fullName: c.name,
        enrolment: c.enrolment_count || c.enrolment_capacity || 0,
        placed: c.placed_count || 0,
        rate: c.placement_rate || 0,
        institute: c.institute || c.institute_name,
      }));
  }, [courses]);

  return (
    <Layout>
      {/* Toast Notification */}
      {toastMessage && (
        <div
          className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-xl shadow-xl text-xs font-bold flex items-center gap-2 border transition-all animate-bounce ${
            toastMessage.type === 'error'
              ? 'bg-rose-900 text-rose-100 border-rose-700'
              : 'bg-emerald-900 text-emerald-100 border-emerald-700'
          }`}
        >
          <span>{toastMessage.type === 'error' ? '❌' : '✅'}</span>
          <span>{toastMessage.message}</span>
        </div>
      )}

      {/* Header Banner */}
      <div data-demo="institute-dashboard-container" className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
              Training Institutes & Curriculum Alignment Hub
            </h1>
            <span className="text-[11px] font-mono px-2 py-0.5 bg-teal-50 dark:bg-teal-950 text-teal-800 dark:text-teal-300 font-semibold rounded border border-teal-200 dark:border-teal-800">
              MSBTE & DGT Aligned
            </span>
            {userSubmittedCount > 0 && (
              <span className="text-[11px] font-mono px-2 py-0.5 bg-purple-50 dark:bg-purple-950 text-purple-800 dark:text-purple-300 font-semibold rounded border border-purple-200 dark:border-purple-800">
                {userSubmittedCount} First-Party Program{userSubmittedCount > 1 ? 's' : ''}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Audit vocational courses across Maharashtra ITIs and polytechnics, submit accredited courses, and align modules with real-time employer demand.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start md:self-auto flex-wrap">
          {(user?.role === 'INSTITUTE' || user?.role === 'ADMIN') && (
            <button
              onClick={() => setIsModalOpen(true)}
              className="px-4 py-2 bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-700 hover:to-emerald-700 text-white rounded-lg text-xs font-bold shadow-md flex items-center gap-1.5 transition-all cursor-pointer"
            >
              <span>➕</span>
              <span>Submit Training Program</span>
            </button>
          )}
          <Link
            to="/curriculum"
            className="px-3.5 py-2 bg-slate-900 dark:bg-teal-700 hover:bg-slate-800 dark:hover:bg-teal-600 text-white rounded-lg text-xs font-bold border border-slate-700 dark:border-teal-600 flex items-center gap-1.5 transition-colors"
          >
            <span>📊</span>
            <span>Curriculum Hub</span>
          </Link>
          <Link
            to="/student/copilot"
            className="px-3.5 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-800 dark:text-slate-200 rounded-lg text-xs font-bold border border-slate-200 dark:border-slate-700 flex items-center gap-1.5 transition-colors"
          >
            <span>✨</span>
            <span>Ask Copilot</span>
          </Link>
        </div>
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
            onClick={fetchCourses}
            className="px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-bold transition-colors cursor-pointer self-start sm:self-auto"
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-5 gap-3.5 mb-6">
        <StatCard
          title="Monitored Courses"
          value={courses.length.toString()}
          subtitle={`${userSubmittedCount} user-submitted`}
          icon="📚"
        />
        <StatCard
          title="Average Placement"
          value={`${avgPlacement}%`}
          subtitle={`${totalPlaced.toLocaleString()} placed of ${totalEnrolment.toLocaleString()}`}
          icon="🎓"
          color="teal"
        />
        <StatCard
          title="Annual Intake Capacity"
          value={totalEnrolment.toLocaleString()}
          subtitle="Sanctioned student seats"
          icon="👥"
          color="blue"
        />
        <StatCard
          title="Curriculum Upgrades"
          value={recommendations.length.toString()}
          subtitle="High-priority revisions"
          icon="💡"
          color="amber"
        />
        <StatCard
          title="Oversupply Flags"
          value={oversupplyCount.toString()}
          subtitle="Requires trade modernization"
          icon="⚠️"
          color="rose"
        />
      </div>

      {/* Visual Analytics Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2 bg-white dark:bg-slate-900 p-5 sm:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-slate-100 dark:border-slate-800">
            <div>
              <h3 className="font-bold text-slate-900 dark:text-white text-base">
                Intake Capacity vs Verified Placement Performance
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Top vocational trades ranked by student capacity and placement conversion
              </p>
            </div>
            <span className="text-[11px] font-mono px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 rounded font-semibold self-start sm:self-auto">
              Accredited Course Metrics
            </span>
          </div>

          <div className="h-64 sm:h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.5} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748b' }} angle={-15} textAnchor="end" interval={0} />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-slate-900 text-white p-3 rounded-lg shadow-xl text-xs border border-slate-700">
                          <p className="font-bold text-teal-400 text-sm mb-1">{data.fullName}</p>
                          <p className="text-slate-300 mb-1">{data.institute}</p>
                          <div className="border-t border-slate-800 pt-1.5 space-y-0.5">
                            <p>Enrolment Intake: <strong className="text-white font-mono">{data.enrolment} seats</strong></p>
                            <p>Placed Graduates: <strong className="text-emerald-400 font-mono">{data.placed} students</strong></p>
                            <p>Placement Conversion: <strong className="text-teal-300 font-mono">{data.rate}%</strong></p>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                <Bar dataKey="enrolment" name="Annual Intake" fill="#0d9488" radius={[4, 4, 0, 0]} />
                <Bar dataKey="placed" name="Placed Graduates" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Alignment Health Breakdown */}
        <div className="bg-white dark:bg-slate-900 p-5 sm:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col justify-between">
          <div>
            <h3 className="font-bold text-slate-900 dark:text-white text-base mb-1">
              Curriculum Health Distribution
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
              Breakdown of {courses.length} accredited trades by labor-market alignment
            </p>

            <div className="space-y-3">
              <div className="p-3 rounded-lg bg-emerald-50/80 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900/60">
                <div className="flex items-center justify-between text-xs font-bold text-emerald-900 dark:text-emerald-300 mb-1">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                    High Demand Aligned
                  </span>
                  <span className="font-mono">{alignedCount} Courses ({Math.round((alignedCount / maxOne(courses.length)) * 100)}%)</span>
                </div>
                <p className="text-[11px] text-emerald-800/80 dark:text-emerald-400/80 leading-relaxed">
                  Placement rate &gt;75% with active hiring signals in Pune, Mumbai, and Nagpur clusters.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-amber-50/80 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/60">
                <div className="flex items-center justify-between text-xs font-bold text-amber-900 dark:text-amber-300 mb-1">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                    Curriculum Gap Detected
                  </span>
                  <span className="font-mono">{attentionCount} Courses ({Math.round((attentionCount / maxOne(courses.length)) * 100)}%)</span>
                </div>
                <p className="text-[11px] text-amber-800/80 dark:text-amber-400/80 leading-relaxed">
                  50–74% placement. Modern syllabus modules required to meet updated employer specs.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-rose-50/80 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/60">
                <div className="flex items-center justify-between text-xs font-bold text-rose-900 dark:text-rose-300 mb-1">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
                    Oversupply / Low Placement
                  </span>
                  <span className="font-mono">{oversupplyCount} Courses ({Math.round((oversupplyCount / maxOne(courses.length)) * 100)}%)</span>
                </div>
                <p className="text-[11px] text-rose-800/80 dark:text-rose-400/80 leading-relaxed">
                  Placement &lt;50% with high intake. Candidates risk structural unemployment without pivot.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Courses Catalog & Search Workbench */}
      <div data-demo="course-health-grid" className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs mb-8 p-5">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-4 pb-4 border-b border-slate-100 dark:border-slate-800">
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">
              Accredited Vocational Courses Directory
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Showing {filteredCourses.length} of {courses.length} registered programs
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {/* Search */}
            <div className="relative min-w-[200px]">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs">🔍</span>
              <input
                type="text"
                placeholder="Search course or skill..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-teal-500"
              />
            </div>

            {/* District */}
            <select
              value={selectedDistrict}
              onChange={(e) => setSelectedDistrict(e.target.value)}
              className="px-3 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs font-semibold text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-teal-500"
            >
              {DISTRICTS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>

            {/* Provenance Filter */}
            <select
              value={provenanceFilter}
              onChange={(e) => setProvenanceFilter(e.target.value)}
              className="px-3 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs font-semibold text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-teal-500"
            >
              <option value="all">All Sources ({courses.length})</option>
              <option value="user">First-Party Submitted ({userSubmittedCount})</option>
              <option value="demo">State Baseline Catalog</option>
            </select>

            {/* Status Pills */}
            <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg border border-slate-200 dark:border-slate-700 text-xs">
              <button
                onClick={() => setStatusFilter('all')}
                className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                  statusFilter === 'all'
                    ? 'bg-white dark:bg-slate-700 shadow-2xs font-bold text-slate-900 dark:text-white'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                }`}
              >
                All
              </button>
              <button
                onClick={() => setStatusFilter('healthy')}
                className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                  statusFilter === 'healthy'
                    ? 'bg-emerald-600 text-white shadow-2xs font-bold'
                    : 'text-slate-600 dark:text-slate-400 hover:text-emerald-700'
                }`}
              >
                Aligned
              </button>
              <button
                onClick={() => setStatusFilter('attention')}
                className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                  statusFilter === 'attention'
                    ? 'bg-amber-500 text-white shadow-2xs font-bold'
                    : 'text-slate-600 dark:text-slate-400 hover:text-amber-700'
                }`}
              >
                Gaps
              </button>
              <button
                onClick={() => setStatusFilter('oversupply')}
                className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                  statusFilter === 'oversupply'
                    ? 'bg-rose-600 text-white shadow-2xs font-bold'
                    : 'text-rose-700 dark:text-rose-400 hover:text-rose-900'
                }`}
              >
                Oversupply
              </button>
            </div>
          </div>
        </div>

        {/* Table Content */}
        {loading ? (
          <div className="py-12 text-center text-slate-400 text-xs space-y-2">
            <div className="inline-block w-6 h-6 border-2 border-teal-500 border-t-transparent rounded-full animate-spin"></div>
            <p>Loading accredited vocational course data...</p>
          </div>
        ) : filteredCourses.length === 0 ? (
          <div className="py-12 text-center text-slate-500 dark:text-slate-400 text-xs bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-dashed border-slate-200 dark:border-slate-800">
            <p className="text-lg mb-1">🔍</p>
            <p className="font-semibold text-slate-800 dark:text-slate-200">No courses match your filter criteria</p>
            <button
              onClick={() => {
                setStatusFilter('all');
                setProvenanceFilter('all');
                setSelectedDistrict('All Districts');
                setSearchQuery('');
              }}
              className="mt-3 px-3 py-1.5 bg-teal-50 dark:bg-teal-950 text-teal-800 dark:text-teal-300 rounded-lg font-bold text-xs border border-teal-200 dark:border-teal-800 hover:bg-teal-100 cursor-pointer"
            >
              Reset All Filters
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 font-semibold border-b border-slate-200 dark:border-slate-700">
                <tr>
                  <th className="p-3">Course & Trade Focus</th>
                  <th className="p-3">Institute & District</th>
                  <th className="p-3">Provenance</th>
                  <th className="p-3">Intake</th>
                  <th className="p-3">Placement Rate</th>
                  <th className="p-3">Alignment Status</th>
                  <th className="p-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredCourses.map((c) => {
                  const isOversupply = c.status === 'review_oversupply';
                  const isGap = c.status === 'needs_attention';
                  const isUserSubmitted = c.source === 'USER_SUBMITTED';
                  const canDelete =
                    user?.role === 'ADMIN' ||
                    (user?.role === 'INSTITUTE' && (c.user_id === user?.id || (user?.organization_id && c.institute_id === user?.organization_id)));

                  return (
                    <tr
                      key={c.id}
                      onClick={() => setSelectedCourse(c)}
                      className={`cursor-pointer transition-colors ${
                        isOversupply
                          ? 'bg-rose-50/40 dark:bg-rose-950/20 hover:bg-rose-50'
                          : isGap
                          ? 'bg-amber-50/30 dark:bg-amber-950/15 hover:bg-amber-50'
                          : 'hover:bg-slate-50/80 dark:hover:bg-slate-800/50'
                      }`}
                    >
                      <td className="p-3 font-bold text-slate-900 dark:text-white max-w-xs">
                        <div className="flex items-center gap-1.5">
                          {isOversupply && <span className="text-rose-600 dark:text-rose-400" title="Oversupply">⚠️</span>}
                          {isGap && <span className="text-amber-500" title="Curriculum Gap">⚡</span>}
                          <span>{c.name}</span>
                        </div>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 font-normal mt-0.5 line-clamp-1">
                          {c.description}
                        </p>
                      </td>
                      <td className="p-3 text-slate-600 dark:text-slate-300">
                        <div className="font-medium text-slate-800 dark:text-slate-200">{c.institute || c.institute_name}</div>
                        <div className="text-[11px] text-slate-400 font-mono flex items-center gap-1">
                          <span>📍</span>
                          <span>{c.district}</span>
                        </div>
                      </td>
                      <td className="p-3">
                        {isUserSubmitted ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 dark:bg-purple-950/80 text-purple-800 dark:text-purple-300 border border-purple-300 dark:border-purple-800">
                            FIRST-PARTY
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700">
                            STATE BENCHMARK
                          </span>
                        )}
                      </td>
                      <td className="p-3 font-mono font-semibold text-slate-700 dark:text-slate-300">
                        {c.enrolment_count || c.enrolment_capacity || 0} seats
                      </td>
                      <td className="p-3">
                        <div className="flex items-center gap-2">
                          <span
                            className={`font-bold font-mono ${
                              c.placement_rate >= 75
                                ? 'text-emerald-700 dark:text-emerald-400'
                                : c.placement_rate >= 50
                                ? 'text-amber-700 dark:text-amber-400'
                                : 'text-rose-700 dark:text-rose-400'
                            }`}
                          >
                            {c.placement_rate}%
                          </span>
                        </div>
                      </td>
                      <td className="p-3">
                        {isOversupply ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-800">
                            OVERSUPPLY
                          </span>
                        ) : isGap ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
                            GAP
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
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedCourse(c);
                            }}
                            className="px-2.5 py-1 bg-slate-100 dark:bg-slate-800 hover:bg-teal-50 text-slate-700 dark:text-slate-300 rounded font-semibold text-[11px] border border-slate-200 dark:border-slate-700 transition-colors shadow-2xs cursor-pointer"
                          >
                            Inspect →
                          </button>
                          {canDelete && isUserSubmitted && (
                            <button
                              onClick={(e) => handleDeleteCourse(c.id, e)}
                              className="px-2 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 rounded font-bold text-[11px] border border-rose-200 transition-colors cursor-pointer"
                              title="Delete Course Program"
                            >
                              🗑️
                            </button>
                          )}
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

      {/* Curriculum Recommendations */}
      <div data-demo="curriculum-recommendations-grid" className="mb-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h3 className="font-bold text-slate-900 dark:text-white text-lg">
              Actionable Curriculum Revisions for MSBTE / ITI Syllabus Council
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Evidence-based recommendations derived from real-time employer signals and gap computations.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {recommendations.map((rec, idx) => (
            <RecommendationCard key={idx} rec={rec} />
          ))}
        </div>
      </div>

      {/* Submit Course Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs animate-fadeIn">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl overflow-y-auto max-h-[90vh]">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800 mb-4">
              <div>
                <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
                  Register Vocational Course / Training Program
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Publish your institute's accredited curriculum into Maharashtra's intelligence registry.
                </p>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 text-lg leading-none cursor-pointer"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateCourse} className="space-y-3.5 text-xs">
              {/* AI Syllabus Ingestion Assistant (Phase 34) */}
              <div className="p-3 rounded-xl bg-teal-50/60 dark:bg-teal-950/20 border border-teal-200 dark:border-teal-800/40">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-bold text-teal-950 dark:text-teal-200 text-xs flex items-center gap-1.5">
                    <span>✨ AI Syllabus Ingestion Assistant</span>
                  </span>
                  <span className="text-[10px] text-teal-600 dark:text-teal-400 font-medium">Auto-fills skills & NSQF</span>
                </div>
                <textarea
                  rows={2}
                  placeholder="Paste syllabus modules or text here (e.g. Module 1: Python, ML, Neural Networks. Module 2: EV Battery Technology & BMS...)"
                  value={syllabusText}
                  onChange={(e) => setSyllabusText(e.target.value)}
                  className="w-full px-2.5 py-1.5 bg-white dark:bg-slate-900 border border-teal-200 dark:border-teal-800 rounded-lg text-slate-800 dark:text-slate-200 text-xs outline-none focus:ring-1 focus:ring-teal-500 font-normal"
                />
                <div className="flex items-center justify-between mt-2">
                  <label className="text-[10px] text-slate-500 dark:text-slate-400 cursor-pointer flex items-center gap-1 hover:text-teal-600">
                    <span>📎 Upload Document (.txt, .md)</span>
                    <input
                      type="file"
                      accept=".txt,.md"
                      className="hidden"
                      onChange={handleSyllabusFileUpload}
                    />
                  </label>
                  <button
                    type="button"
                    disabled={extractingSyllabus || !syllabusText.trim()}
                    onClick={handleExtractSyllabus}
                    className="px-2.5 py-1 text-xs font-semibold rounded-md bg-teal-600 hover:bg-teal-700 text-white cursor-pointer disabled:opacity-50 transition"
                  >
                    {extractingSyllabus ? 'Extracting...' : 'Auto-Extract Skills'}
                  </button>
                </div>
              </div>

              <div>
                <label className="font-bold text-slate-800 dark:text-slate-200 block mb-1">
                  Course Program Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Advanced EV Battery Diagnostics & BMS Testing"
                  value={formState.name}
                  onChange={(e) => setFormState({ ...formState, name: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:ring-1 focus:ring-teal-500 outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-800 dark:text-slate-200 block mb-1">
                    Institute Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formState.institute_name}
                    onChange={(e) => setFormState({ ...formState, institute_name: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:ring-1 focus:ring-teal-500 outline-none"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-800 dark:text-slate-200 block mb-1">
                    District *
                  </label>
                  <select
                    value={formState.district}
                    onChange={(e) => setFormState({ ...formState, district: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:ring-1 focus:ring-teal-500 outline-none"
                  >
                    {DISTRICTS.filter((d) => d !== 'All Districts').map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-800 dark:text-slate-200 block mb-1">
                    Discipline Category
                  </label>
                  <select
                    value={formState.category}
                    onChange={(e) => setFormState({ ...formState, category: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:ring-1 focus:ring-teal-500 outline-none"
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="font-bold text-slate-800 dark:text-slate-200 block mb-1">
                    NSQF Level (1 - 10)
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={formState.nsqf_level}
                    onChange={(e) => setFormState({ ...formState, nsqf_level: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:ring-1 focus:ring-teal-500 outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="font-bold text-slate-800 dark:text-slate-200 block mb-1">
                  Skills Taught in Syllabus (Comma separated) *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Battery Management, CAN Bus, High-Voltage Diagnostics"
                  value={formState.skillsInput}
                  onChange={(e) => setFormState({ ...formState, skillsInput: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:ring-1 focus:ring-teal-500 outline-none"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="font-bold text-slate-800 dark:text-slate-200 block mb-1">
                    Annual Capacity
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={formState.enrolment_capacity}
                    onChange={(e) => setFormState({ ...formState, enrolment_capacity: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:ring-1 focus:ring-teal-500 outline-none"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-800 dark:text-slate-200 block mb-1">
                    Placed Graduates
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={formState.placed_count}
                    onChange={(e) => setFormState({ ...formState, placed_count: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:ring-1 focus:ring-teal-500 outline-none"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-800 dark:text-slate-200 block mb-1">
                    Duration (Weeks)
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={formState.duration_weeks}
                    onChange={(e) => setFormState({ ...formState, duration_weeks: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:ring-1 focus:ring-teal-500 outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="font-bold text-slate-800 dark:text-slate-200 block mb-1">
                  Certifications Awarded
                </label>
                <input
                  type="text"
                  placeholder="e.g. MSBTE State Certificate / NCVT Certification"
                  value={formState.certifications}
                  onChange={(e) => setFormState({ ...formState, certifications: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:ring-1 focus:ring-teal-500 outline-none"
                />
              </div>

              <div>
                <label className="font-bold text-slate-800 dark:text-slate-200 block mb-1">
                  Course Scope & Syllabus Summary
                </label>
                <textarea
                  rows={3}
                  placeholder="Describe the laboratory practicals, industry internships, and learning outcomes..."
                  value={formState.description}
                  onChange={(e) => setFormState({ ...formState, description: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:ring-1 focus:ring-teal-500 outline-none"
                />
              </div>

              <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg font-semibold cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-bold shadow-md flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  {submitting ? 'Submitting...' : 'Register Program'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Course Detail Modal */}
      {selectedCourse && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs animate-fadeIn">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl overflow-y-auto max-h-[90vh]">
            <div className="flex items-start justify-between gap-4 mb-4 pb-3 border-b border-slate-100 dark:border-slate-800">
              <div>
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-teal-50 dark:bg-teal-950 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800 uppercase">
                    {selectedCourse.category || 'Vocational Trade'}
                  </span>
                  {selectedCourse.source === 'USER_SUBMITTED' ? (
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-purple-50 dark:bg-purple-950 text-purple-800 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                      FIRST-PARTY DATA
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                      STATE BENCHMARK
                    </span>
                  )}
                  {selectedCourse.nsqf_level && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                      NSQF Level {selectedCourse.nsqf_level}
                    </span>
                  )}
                </div>
                <h3 className="text-xl font-extrabold text-slate-900 dark:text-white">
                  {selectedCourse.name}
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  {selectedCourse.institute || selectedCourse.institute_name} • {selectedCourse.district} District
                </p>
              </div>
              <button
                onClick={() => setSelectedCourse(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 text-lg leading-none cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-3 gap-3 mb-5">
              <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-100 dark:border-slate-700/60 text-center">
                <span className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-semibold block">Intake Capacity</span>
                <span className="text-base font-extrabold font-mono text-slate-900 dark:text-white">
                  {selectedCourse.enrolment_count || selectedCourse.enrolment_capacity} seats
                </span>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-100 dark:border-slate-700/60 text-center">
                <span className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-semibold block">Placed Graduates</span>
                <span className="text-base font-extrabold font-mono text-emerald-600 dark:text-emerald-400">
                  {selectedCourse.placed_count || 0}
                </span>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-100 dark:border-slate-700/60 text-center">
                <span className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-semibold block">Placement Rate</span>
                <span className={`text-base font-extrabold font-mono ${
                  selectedCourse.placement_rate >= 75 ? 'text-emerald-600 dark:text-emerald-400' :
                  selectedCourse.placement_rate >= 50 ? 'text-amber-600 dark:text-amber-400' : 'text-rose-600 dark:text-rose-400'
                }`}>
                  {selectedCourse.placement_rate}%
                </span>
              </div>
            </div>

            <div className="mb-4">
              <h4 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider mb-1">
                Course Syllabus & Scope
              </h4>
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed bg-slate-50 dark:bg-slate-800/40 p-3 rounded-lg border border-slate-100 dark:border-slate-800">
                {selectedCourse.description}
              </p>
            </div>

            {Array.isArray(selectedCourse.skills) && selectedCourse.skills.length > 0 && (
              <div className="mb-5">
                <h4 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider mb-2">
                  Integrated Competencies (NSQF Mapped)
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {selectedCourse.skills.map((s, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 rounded-md bg-teal-50 dark:bg-teal-950 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800 text-xs font-medium"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-end gap-2">
              <button
                onClick={() => setSelectedCourse(null)}
                className="px-4 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-700 dark:text-slate-300 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}

function maxOne(num) {
  return num <= 0 ? 1 : num;
}
