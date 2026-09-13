import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import StatCard from './StatCard';
import { api } from '../services/api';

export default function CareerRecommendationsView({ studentId, onOpenExplainability }) {
  const [recommendation, setRecommendation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiExplanation, setAiExplanation] = useState(null);
  const [selectedCareer, setSelectedCareer] = useState(null);

  const fetchRecommendations = () => {
    if (!studentId) return;
    setLoading(true);
    setError(null);
    api.getStudentCareerRecommendations(studentId)
      .then((res) => {
        if (res && res.status === 'success') {
          setRecommendation(res);
          setSelectedCareer(res.top_recommendation || (res.recommended_careers && res.recommended_careers[0]));
          setAiExplanation(res.ai_explanation?.summary || null);
        } else {
          setError(res?.detail || 'Failed to generate career recommendations.');
        }
      })
      .catch((err) => {
        setError(err?.message || 'Error connecting to recommendation service.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchRecommendations();
  }, [studentId]);

  const [customQuestion, setCustomQuestion] = useState('');
  const [aiProvenance, setAiProvenance] = useState('🛡️ Grounded Deterministic Intelligence');

  const handleAskAi = (promptText = null) => {
    setAiLoading(true);
    const query = promptText || customQuestion || null;
    api.explainStudentRecommendationsAi(studentId, query)
      .then((res) => {
        if (res?.status === 'success' && res.ai_explanation) {
          setAiExplanation(res.ai_explanation);
          setAiProvenance(res.is_live_ai ? `✨ Gemini AI Generated (${res.model})` : '🛡️ Grounded Deterministic Intelligence');
        }
      })
      .catch((err) => {
        console.warn('AI explanation fallback:', err);
      })
      .finally(() => {
        setAiLoading(false);
        setCustomQuestion('');
      });
  };

  if (loading) {
    return (
      <div className="py-16 text-center">
        <div className="w-8 h-8 border-3 border-teal-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
        <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">Synthesizing Career Recommendations...</h4>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Cross-referencing student assessment, validated employer demand, and government opportunities.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 text-center">
        <p className="text-xs font-bold text-rose-700 dark:text-rose-300 mb-2">{error}</p>
        <button
          onClick={fetchRecommendations}
          className="px-4 py-2 bg-rose-600 text-white rounded-xl text-xs font-bold hover:bg-rose-700 cursor-pointer"
        >
          Retry Engine Calculation
        </button>
      </div>
    );
  }

  if (!recommendation) return null;

  if (recommendation.status === 'unassessed' || recommendation.has_assessment === false || !recommendation.recommended_careers?.length) {
    return (
      <div className="p-8 rounded-2xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-center space-y-3 my-4">
        <div className="text-4xl">🎯</div>
        <h3 className="text-base font-bold text-amber-900 dark:text-amber-200">
          Personalized Career Recommendations Require Assessment
        </h3>
        <p className="text-xs text-amber-700 dark:text-amber-300 max-w-md mx-auto">
          {recommendation.message || 'Complete the 3-minute diagnostic quiz to see career opportunities dynamically matched with your skills, employer demand, and government apprenticeships.'}
        </p>
      </div>
    );
  }

  const top = selectedCareer || recommendation.top_recommendation;
  const readiness = recommendation.overall_readiness;

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* 1. Top Readiness Banner & Provenance Notice */}
      <div className="p-6 rounded-2xl bg-linear-to-r from-slate-900 via-slate-800 to-teal-950 text-white shadow-lg border border-slate-700/80">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-teal-500/20 text-teal-300 border border-teal-500/40 font-bold uppercase">
                Phase 16 Grounded Recommendation
              </span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                Candidate: {recommendation.candidate_name} ({recommendation.district})
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-extrabold tracking-tight">
              Top Recommended Pathway: <span className="text-teal-400">{top?.role_name}</span>
            </h2>
            <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
              {top?.description}
            </p>
          </div>

          {/* Readiness Gauge Card */}
          <div className="flex items-center gap-4 bg-slate-950/60 p-4 rounded-xl border border-slate-700 shrink-0">
            <div className="text-center">
              <div className="text-3xl font-extrabold text-teal-400 font-mono">
                {readiness?.score || 0}%
              </div>
              <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mt-0.5">
                Readiness Score
              </div>
            </div>
            <div className="h-10 w-px bg-slate-800"></div>
            <div>
              <div className="text-xs font-bold text-white flex items-center gap-1.5">
                <span>{readiness?.headline}</span>
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5 max-w-[200px] leading-tight">
                {readiness?.description}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 2. AI Grounded Explainability & Copilot Synthesis (Phase 17) */}
      <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-teal-200 dark:border-teal-900/60 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-teal-100 dark:bg-teal-950 text-teal-700 dark:text-teal-300 flex items-center justify-center font-bold text-sm">
              🤖
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-slate-900 dark:text-white text-sm">
                  AI Career Copilot & Explainability Layer
                </h3>
                <span className="text-[10px] font-mono px-2 py-0.2 rounded bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300 font-semibold">
                  Phase 17
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Deterministic recommendations explained in student-friendly language using strictly grounded data
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to={`/student/copilot?role=student&student_id=${studentId}`}
              className="px-3.5 py-1.5 bg-slate-900 dark:bg-teal-700 text-white rounded-lg text-xs font-bold transition-colors flex items-center gap-1.5 shadow-2xs hover:bg-slate-800"
            >
              <span>💬</span>
              <span>Full Copilot Chat →</span>
            </Link>
          </div>
        </div>

        {/* Quick Inquiry Pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mr-1">Ask AI:</span>
          {[
            'Why is this career recommended for me?',
            'Explain my biggest skill gaps and how to bridge them',
            'What validated employer demand exists for this role in Maharashtra?',
            'Which government schemes or apprenticeships can support my training?',
          ].map((promptText, idx) => (
            <button
              key={idx}
              onClick={() => handleAskAi(promptText)}
              disabled={aiLoading}
              className="px-3 py-1 bg-slate-100 dark:bg-slate-800 hover:bg-teal-50 dark:hover:bg-teal-950 text-slate-700 dark:text-slate-300 hover:text-teal-800 dark:hover:text-teal-300 rounded-full text-xs font-medium transition-colors border border-slate-200 dark:border-slate-700 cursor-pointer disabled:opacity-50"
            >
              {promptText}
            </button>
          ))}
        </div>

        {/* AI Explanation Output Box */}
        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 space-y-2">
          <div className="flex items-center justify-between text-[11px] pb-1 border-b border-slate-200/60 dark:border-slate-700/60">
            <span className="font-bold text-teal-800 dark:text-teal-300 flex items-center gap-1">
              <span>{aiProvenance.includes('Gemini') ? '✨' : '🛡️'}</span>
              <span>{aiProvenance}</span>
            </span>
            <span className="text-[10px] text-slate-400 font-mono">100% Grounded in SkillSetuAI Data</span>
          </div>

          {aiLoading ? (
            <div className="py-4 flex items-center gap-3 text-xs text-slate-500">
              <div className="w-4 h-4 border-2 border-teal-500 border-t-transparent rounded-full animate-spin"></div>
              <span>Generating grounded AI explanation...</span>
            </div>
          ) : (
            <p className="text-xs text-slate-700 dark:text-slate-200 leading-relaxed whitespace-pre-wrap">
              {aiExplanation || recommendation.ai_explanation?.summary}
            </p>
          )}
        </div>

        {/* Inline Query Box */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleAskAi();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={customQuestion}
            onChange={(e) => setCustomQuestion(e.target.value)}
            placeholder="Ask AI Copilot a specific question about your recommendations or roadmap..."
            className="flex-1 text-xs px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500"
          />
          <button
            type="submit"
            disabled={aiLoading || !customQuestion.trim()}
            className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-xl text-xs font-bold transition-colors cursor-pointer disabled:opacity-50 shrink-0"
          >
            {aiLoading ? 'Thinking...' : 'Ask Copilot ✨'}
          </button>
        </form>
      </div>

      {/* 3. Recommended Career Pathways (Selector & Cards) */}
      <div>
        <div className="mb-4 pb-2 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <div>
            <h3 className="font-extrabold text-slate-900 dark:text-white text-base">
              Career Role Rankings & Fit Breakdown
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Evaluated against standard Maharashtra labour market roles and validated employer openings
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {(recommendation.recommended_careers || []).map((career) => {
            const isSelected = selectedCareer?.role_name === career.role_name;
            return (
              <div
                key={career.role_name}
                onClick={() => setSelectedCareer(career)}
                className={`p-4 rounded-xl border transition-all cursor-pointer flex flex-col justify-between ${
                  isSelected
                    ? 'border-teal-500 bg-teal-50/50 dark:bg-teal-950/40 shadow-sm ring-1 ring-teal-500'
                    : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-teal-300 dark:hover:border-teal-700'
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <h4 className="font-bold text-slate-900 dark:text-white text-sm leading-snug">
                      {career.role_name}
                    </h4>
                    <span className="font-mono text-xs font-extrabold text-teal-600 dark:text-teal-400 shrink-0">
                      {career.match_pct}% Match
                    </span>
                  </div>

                  <p className="text-[11px] text-slate-500 dark:text-slate-400 line-clamp-2 mb-3">
                    {career.description}
                  </p>

                  <div className="space-y-1.5 mb-3">
                    <div className="text-[10px] text-slate-600 dark:text-slate-300">
                      <span className="font-bold">Matching ({career.matching_skills.length}):</span>{' '}
                      <span className="text-emerald-700 dark:text-emerald-400 font-medium">
                        {career.matching_skills.slice(0, 2).join(', ') || 'None'}
                      </span>
                    </div>
                    <div className="text-[10px] text-slate-600 dark:text-slate-300">
                      <span className="font-bold">Gaps ({career.missing_skills.length}):</span>{' '}
                      <span className="text-rose-600 dark:text-rose-400 font-medium">
                        {career.missing_skills.slice(0, 2).join(', ') || 'Fully acquired'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-[10px]">
                  <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 font-bold text-slate-600 dark:text-slate-300 font-mono">
                    {career.validated_openings_count} Openings
                  </span>
                  <span className="text-teal-600 dark:text-teal-400 font-bold hover:underline">
                    {isSelected ? 'Viewing Details ✓' : 'Select Role →'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. Deep-Dive Section for Selected Career */}
      {top && (
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-6 shadow-xs">
          <div className="pb-4 border-b border-slate-100 dark:border-slate-800">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <span className="text-[10px] font-mono font-bold uppercase text-teal-600 dark:text-teal-400 tracking-wider">
                  Detailed Explainability Breakdown
                </span>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                  Why {top.role_name} is Recommended
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded-full text-xs font-bold font-mono bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300">
                  {top.match_pct}% Competency Match
                </span>
                <span className="px-2.5 py-1 rounded-full text-xs font-bold font-mono bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                  NSQF Level {top.nsqf_level}
                </span>
              </div>
            </div>

            {/* Why Reasons */}
            <div className="mt-3 flex flex-wrap gap-2">
              {(top.explanation_reasons || []).map((reason, idx) => (
                <div
                  key={idx}
                  className="px-3 py-1 rounded-lg bg-teal-50 dark:bg-teal-950/50 border border-teal-200 dark:border-teal-800 text-xs text-teal-900 dark:text-teal-200 font-medium flex items-center gap-1.5"
                >
                  <span>✓</span>
                  <span>{reason}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Two-Column Grid: Validated Employer Demands & Matched Government Programs */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Column A: Validated Employer Demand Signals (Phase 14) */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                  <span>🏢</span>
                  <span>Validated Employer Openings (Phase 14)</span>
                </h4>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                  Verified Submissions Only
                </span>
              </div>

              {top.validated_employer_signals && top.validated_employer_signals.length > 0 ? (
                <div className="space-y-2.5">
                  {top.validated_employer_signals.map((emp, idx) => (
                    <div
                      key={emp.id || idx}
                      className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/70"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h5 className="font-bold text-slate-900 dark:text-white text-xs">{emp.company_name}</h5>
                          <p className="text-[11px] text-slate-500 dark:text-slate-400">
                            {emp.job_role} • <span className="font-semibold text-slate-700 dark:text-slate-300">{emp.district}</span>
                          </p>
                        </div>
                        <span className="text-xs font-mono font-bold text-emerald-600 dark:text-emerald-400 shrink-0">
                          {emp.openings_count} Openings
                        </span>
                      </div>
                      <div className="mt-2 flex items-center justify-between text-[10px] text-slate-500 pt-1.5 border-t border-slate-200/60 dark:border-slate-700/60">
                        <span>Timeline: {emp.hiring_timeline || 'Immediate'}</span>
                        <span className="font-mono text-emerald-700 dark:text-emerald-400 font-bold uppercase">
                          ✓ {emp.validation_status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 py-6 text-center border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
                  No active employer demand submissions directly tagged for this role.
                </p>
              )}
            </div>

            {/* Column B: Matched Government Opportunities & Schemes (Phase 15) */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                  <span>🏛️</span>
                  <span>Matched Government Programs (Phase 15)</span>
                </h4>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                  DVET / MSBTE / MahaDBT
                </span>
              </div>

              {top.matched_government_opportunities && top.matched_government_opportunities.length > 0 ? (
                <div className="space-y-2.5">
                  {top.matched_government_opportunities.map((gov, idx) => (
                    <div
                      key={gov.id || idx}
                      className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/70"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h5 className="font-bold text-slate-900 dark:text-white text-xs">{gov.name}</h5>
                          <p className="text-[11px] text-slate-500 dark:text-slate-400">
                            {gov.department}
                          </p>
                        </div>
                        <span className="text-[9px] font-mono font-bold uppercase px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300 shrink-0">
                          {(gov.opportunity_type || 'scheme').replace('_', ' ')}
                        </span>
                      </div>
                      <div className="mt-2 flex items-center justify-between text-[10px] pt-1.5 border-t border-slate-200/60 dark:border-slate-700/60">
                        <span className="text-slate-500">Coverage: {typeof gov.district_coverage === 'object' ? gov.district_coverage.join(', ') : gov.district_coverage}</span>
                        {gov.application_url && (
                          <a
                            href={gov.application_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-teal-600 dark:text-teal-400 font-bold hover:underline"
                          >
                            Apply on Portal →
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 py-6 text-center border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
                  General state welfare scholarships apply for this domain.
                </p>
              )}
            </div>
          </div>

          {/* Step-by-Step Learning Roadmap */}
          <div className="pt-4 border-t border-slate-100 dark:border-slate-800">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-3 flex items-center gap-1.5">
              <span>🚀</span>
              <span>Personalized Learning Roadmap to Bridge Skill Gaps</span>
            </h4>

            <div className="space-y-3">
              {(recommendation.personalized_roadmap || []).map((step) => (
                <div
                  key={step.step}
                  className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-lg bg-slate-900 dark:bg-teal-600 text-white font-bold text-xs flex items-center justify-center shrink-0">
                      {step.step}
                    </div>
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <h5 className="font-bold text-slate-900 dark:text-white text-xs">{step.skill_name}</h5>
                        <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 font-bold font-mono">
                          {step.priority} PRIORITY
                        </span>
                        <span className="text-[9px] text-slate-500 dark:text-slate-400 font-mono">
                          {step.demand_confidence}% Confidence
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-600 dark:text-slate-300 mt-1">
                        {step.why_learn}
                      </p>
                    </div>
                  </div>

                  {onOpenExplainability && (
                    <button
                      onClick={() => onOpenExplainability(step.skill_name, step.skill_name)}
                      className="text-[11px] font-bold text-teal-700 dark:text-teal-300 bg-teal-50 dark:bg-teal-950/60 px-3 py-1.5 rounded-lg border border-teal-200 dark:border-teal-800 shrink-0 hover:bg-teal-100 transition-colors cursor-pointer"
                    >
                      5D Evidence ⓘ
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Data Provenance Footer */}
          <div className="p-3 rounded-xl bg-slate-100 dark:bg-slate-800/40 text-[10px] text-slate-500 dark:text-slate-400 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <span>
              <strong>Data Provenance:</strong> Candidate Profile ({recommendation.data_provenance?.student_profile_source}) • Employer Demand ({recommendation.data_provenance?.employer_demand_source}) • Government Opportunities ({recommendation.data_provenance?.government_opportunities_source})
            </span>
            <span className="italic">Grounded Deterministic Engine</span>
          </div>
        </div>
      )}
    </div>
  );
}
