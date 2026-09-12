import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';

export default function SkillExplainabilityModal({
  isOpen,
  onClose,
  skillQuery,
  studentId,
  skillNameFallback,
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen || !skillQuery) {
      setData(null);
      setError(null);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    api.getSkillExplainability(skillQuery, studentId)
      .then((res) => {
        if (!isMounted) return;
        if (res.error) {
          setError(res.error);
        } else {
          setData(res);
        }
        setLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err.message || 'Failed to retrieve skill explainability telemetry');
        setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, skillQuery, studentId]);

  // Handle ESC key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const expl = data?.explainability;
  const skill = data?.skill;
  const studentAlign = data?.student_alignment;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs overflow-y-auto">
      <div
        className="relative w-full max-w-2xl max-h-[90vh] flex flex-col bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-start justify-between bg-slate-50/80 dark:bg-slate-800/40">
          <div>
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-teal-50 dark:bg-teal-950 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
                Labour-Market Grounded Evidence
              </span>
              {skill?.category && (
                <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                  {skill.category}
                </span>
              )}
              {skill?.nsqf_level && (
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                  NSQF L{skill.nsqf_level}
                </span>
              )}
            </div>
            <h2 className="text-xl font-black text-slate-900 dark:text-white tracking-tight">
              Why Learn {skill?.name || skillNameFallback || 'This Competency'}?
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              5-Dimension justification grounded in Maharashtra job postings, employer feedback, and curriculum coverage.
            </p>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="Close modal"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 overflow-y-auto space-y-5 text-sm">
          {loading ? (
            <div className="py-12 text-center space-y-3">
              <div className="inline-block w-8 h-8 border-3 border-teal-500 border-t-transparent rounded-full animate-spin"></div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Fetching grounded labour-market metrics and curriculum gap telemetry...
              </p>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-300">
              <div className="font-bold text-xs mb-1">Telemetry Notice</div>
              <p className="text-xs">{error}</p>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-2">
                Showing rule-based recommendations. Verified statistical telemetry may still be indexing for this competency alias.
              </p>
            </div>
          ) : expl ? (
            <>
              {/* Student Alignment Badge */}
              {studentAlign && (
                <div className="p-3 rounded-xl bg-teal-50/70 dark:bg-teal-950/30 border border-teal-200 dark:border-teal-800/80 flex items-center justify-between gap-3 text-xs">
                  <div>
                    <span className="text-[10px] font-mono font-semibold text-teal-800 dark:text-teal-300 uppercase block">
                      Candidate Pathway Alignment • {studentAlign.target_role}
                    </span>
                    <span className="font-bold text-slate-900 dark:text-white">
                      Status for {studentAlign.student_name}:
                    </span>{' '}
                    <span className="font-medium text-teal-900 dark:text-teal-200">
                      {studentAlign.status_label}
                    </span>
                  </div>
                  <span
                    className={`px-2.5 py-1 rounded-full text-[10px] font-bold shrink-0 ${
                      studentAlign.is_acquired
                        ? 'bg-emerald-100 dark:bg-emerald-900 text-emerald-800 dark:text-emerald-200'
                        : studentAlign.is_required_for_target
                        ? 'bg-rose-100 dark:bg-rose-900 text-rose-800 dark:text-rose-200'
                        : 'bg-teal-100 dark:bg-teal-900 text-teal-800 dark:text-teal-200'
                    }`}
                  >
                    {studentAlign.is_acquired ? '✓ Acquired' : '⚠️ Missing Prerequisite'}
                  </span>
                </div>
              )}

              {/* 5-Dimension Justification Grid */}
              <div className="space-y-4">
                {/* 1. Demand Surge */}
                <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/80">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                      <span>📊</span> 1. Demand Surge & Active Hiring Signal
                    </span>
                    <span className="text-[11px] font-mono font-bold text-teal-700 dark:text-teal-300 bg-teal-50 dark:bg-teal-950/60 px-2 py-0.5 rounded border border-teal-200 dark:border-teal-800">
                      {expl.dimension_1_demand_surge.demand_surge_label}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-300 mb-2">
                    Found in <strong>{expl.dimension_1_demand_surge.active_vacancies_count} active job listings</strong> across Maharashtra industrial hubs.
                  </p>
                  <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500 dark:text-slate-400">
                    <span>Key Hiring Districts:</span>
                    {expl.dimension_1_demand_surge.top_hiring_districts.map((d, i) => (
                      <span key={i} className="px-1.5 py-0.5 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-medium">
                        {d}
                      </span>
                    ))}
                  </div>
                  {expl.dimension_1_demand_surge.relevant_roles.length > 0 && (
                    <div className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
                      <span className="font-semibold text-slate-600 dark:text-slate-300">Target Job Titles: </span>
                      {expl.dimension_1_demand_surge.relevant_roles.join(', ')}
                    </div>
                  )}
                </div>

                {/* 2. Future Horizon */}
                <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/80">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                      <span>🚀</span> 2. Future Horizon & Forecast Trajectory
                    </span>
                    {expl.dimension_2_future_forecast.verified ? (
                      <span className="text-[11px] font-mono font-bold text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-200 dark:border-indigo-800">
                        {expl.dimension_2_future_forecast.future_demand} ({expl.dimension_2_future_forecast.period})
                      </span>
                    ) : (
                      <span className="text-[10px] font-mono text-slate-400 italic">
                        Forecast Unavailable
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-300">
                    {expl.dimension_2_future_forecast.summary}
                  </p>
                  {expl.dimension_2_future_forecast.confidence_pct && (
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-[10px] font-mono text-slate-500">Model Confidence:</span>
                      <div className="h-1.5 w-24 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-indigo-500 rounded-full"
                          style={{ width: `${expl.dimension_2_future_forecast.confidence_pct}%` }}
                        ></div>
                      </div>
                      <span className="text-[10px] font-mono font-bold text-indigo-600 dark:text-indigo-400">
                        {expl.dimension_2_future_forecast.confidence_pct}%
                      </span>
                    </div>
                  )}
                </div>

                {/* 3. Employer Demand & Bottleneck Consensus */}
                <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/80">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                      <span>💼</span> 3. Employer Demand & Shortage Consensus
                    </span>
                    <span
                      className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                        expl.dimension_3_employer_consensus.demand_rating === 'CRITICAL SHORTAGE'
                          ? 'bg-rose-50 dark:bg-rose-950 text-rose-800 dark:text-rose-300 border-rose-200 dark:border-rose-800'
                          : 'bg-teal-50 dark:bg-teal-950 text-teal-800 dark:text-teal-300 border-teal-200 dark:border-teal-800'
                      }`}
                    >
                      {expl.dimension_3_employer_consensus.demand_rating}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-300 mb-2">
                    {expl.dimension_3_employer_consensus.hiring_challenge}
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px] pt-1">
                    <div className="p-2 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
                      <span className="text-[10px] text-slate-400 block font-mono">Avg Time to Fill</span>
                      <span className="font-bold text-slate-900 dark:text-white">
                        {expl.dimension_3_employer_consensus.avg_days_to_fill} Days
                      </span>
                    </div>
                    {expl.dimension_3_employer_consensus.deficit_score != null && (
                      <div className="p-2 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
                        <span className="text-[10px] text-slate-400 block font-mono">Deficit Score</span>
                        <span className="font-bold text-rose-600 dark:text-rose-400">
                          {expl.dimension_3_employer_consensus.deficit_score}/100
                        </span>
                      </div>
                    )}
                    <div className="p-2 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 col-span-2 sm:col-span-1">
                      <span className="text-[10px] text-slate-400 block font-mono">Industry Sign-Offs</span>
                      <span className="font-bold text-slate-900 dark:text-white">
                        {expl.dimension_3_employer_consensus.employer_validations.confirmed} Confirmed
                      </span>
                    </div>
                  </div>
                </div>

                {/* 4. Curriculum Deficit */}
                <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/80">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                      <span>🏫</span> 4. Curriculum Deficit & Training Capacity
                    </span>
                    <span className="text-[10px] font-mono font-bold text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/60 px-2 py-0.5 rounded border border-amber-200 dark:border-amber-800">
                      Deficit: {expl.dimension_4_curriculum_deficit.skill_gap_pct}%
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-300 mb-2">
                    {expl.dimension_4_curriculum_deficit.coverage_summary}
                  </p>
                  {expl.dimension_4_curriculum_deficit.teaching_courses.length > 0 ? (
                    <div>
                      <span className="text-[11px] font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                        Accredited Courses Teaching This Skill ({expl.dimension_4_curriculum_deficit.courses_count}):
                      </span>
                      <div className="space-y-1">
                        {expl.dimension_4_curriculum_deficit.teaching_courses.map((c) => (
                          <div
                            key={c.id}
                            className="p-1.5 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 flex items-center justify-between text-xs"
                          >
                            <span className="font-medium text-slate-800 dark:text-slate-200">{c.name}</span>
                            <span className="text-[10px] text-slate-400">{c.institute} • {c.district}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="text-[11px] text-slate-400 italic">
                      No standardized ITI vocational courses currently include formal modules for this emerging skill in Maharashtra.
                    </p>
                  )}
                </div>

                {/* 5. Academic Rationale */}
                <div className="p-3.5 rounded-xl bg-teal-50/50 dark:bg-teal-950/20 border border-teal-200 dark:border-teal-800">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-teal-900 dark:text-teal-200 flex items-center gap-1.5">
                      <span>📜</span> 5. Official Vocational Council Rationale
                    </span>
                    <span className="text-[10px] font-mono font-bold text-teal-800 dark:text-teal-300 uppercase">
                      {expl.dimension_5_academic_rationale.recommendation_level}
                    </span>
                  </div>
                  <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed italic">
                    "{expl.dimension_5_academic_rationale.formal_statement}"
                  </p>
                  {expl.dimension_5_academic_rationale.associated_signal_title && (
                    <div className="mt-2 text-[11px] text-teal-800 dark:text-teal-400 flex items-center gap-1 font-medium">
                      <span>⚡ Linked Signal:</span>
                      <span>{expl.dimension_5_academic_rationale.associated_signal_title}</span>
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : null}
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-800/40 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-500 dark:text-slate-400">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span>DATA PROVENANCE: SKILLSETUAI GROUNDED LABOUR INTELLIGENCE</span>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            <Link
              to={{
                pathname: '/student/copilot',
                search: `?topic=${encodeURIComponent(skill?.name || skillNameFallback || 'This Competency')}`,
              }}
              state={{
                fromRecommendation: true,
                autoSend: true,
                recommendationContext: {
                  topic: skill?.name || skillNameFallback || 'This Competency',
                  recommendation_title: `Why Learn ${skill?.name || skillNameFallback || 'This Competency'}?`,
                  target_role: studentAlign?.target_role || '',
                  student_name: studentAlign?.student_name || '',
                  student_id: studentId || '',
                  missing_prerequisites: !studentAlign?.is_acquired ? [skill?.name || skillNameFallback || 'This Competency'] : [],
                  demand_signals: expl?.dimension_1_demand_surge ? {
                    demand_pct: expl.dimension_1_demand_surge.demand_pct,
                    active_vacancies_count: expl.dimension_1_demand_surge.active_vacancies_count,
                    top_hiring_districts: expl.dimension_1_demand_surge.top_hiring_districts,
                    relevant_roles: expl.dimension_1_demand_surge.relevant_roles,
                  } : null,
                  future_forecast: expl?.dimension_2_future_forecast || null,
                  employer_consensus: expl?.dimension_3_employer_consensus || null,
                  relevant_courses: (expl?.dimension_4_curriculum_deficit?.teaching_courses || []).map((c) => ({
                    id: c.id,
                    name: c.name,
                    institute: c.institute,
                    district: c.district,
                  })),
                  source: 'SkillSetuAI Grounded Labour Intelligence',
                },
              }}
              onClick={onClose}
              className="px-3 py-1.5 bg-slate-900 dark:bg-teal-600 hover:bg-slate-800 dark:hover:bg-teal-700 text-white text-xs font-bold rounded-lg transition-colors inline-block"
            >
              Ask Copilot About {skill?.name || skillNameFallback || 'This Skill'} →
            </Link>
            <button
              onClick={onClose}
              className="px-3 py-1.5 border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-medium rounded-lg transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
