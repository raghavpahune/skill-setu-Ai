import React, { useState, useRef, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '../services/api';
import { generateClientFallback } from '../services/copilotFallback';
import { useAuth } from '../context/AuthContext';

const ROLE_DEFINITIONS = [
  {
    id: 'student',
    label: 'Students',
    badge: 'Career Pathways & Gaps',
    icon: '🎓',
    placeholder: 'Ask about career roadmaps, prerequisite skills, or job eligibility (e.g., Which skills should I learn for an AI Engineer role?)...',
  },
  {
    id: 'employer',
    label: 'Employers',
    badge: 'Validation & Bottlenecks',
    icon: '💼',
    placeholder: 'Ask about industry hiring bottlenecks, technician shortages, or curriculum feedback (e.g., Which technical skills report the highest hiring bottlenecks?)...',
  },
  {
    id: 'institute',
    label: 'Institutes',
    badge: 'Curriculum & Course Health',
    icon: '🏫',
    placeholder: 'Ask about curriculum updates, low-placement course risks, or NSQF alignment (e.g., Which courses address highest-priority gaps?)...',
  },
  {
    id: 'government',
    label: 'Government',
    badge: 'Policy & ITI Allocation',
    icon: '🏛️',
    placeholder: 'Ask about district labour deficits, ITI seat allocations, or scheme budgets (e.g., What are the biggest skill gaps in Pune?)...',
  },
  {
    id: 'employee',
    label: 'Employees',
    badge: 'Career Transition & Reskilling',
    icon: '⚡',
    placeholder: 'Ask about career transitions, upskilling paths, or transferable competencies (e.g., How do I transition to an Automation Specialist?)...',
  },
  {
    id: 'admin',
    label: 'Admin',
    badge: 'Governance & Provenance',
    icon: '⚙️',
    placeholder: 'Ask about platform ingestion telemetry, employer validation pipeline, or cross-domain metrics...',
  },
];

const CONTEXTUAL_PROMPTS = {
  student: [
    'Why is my target career role recommended for me?',
    'What verified employer vacancies match my skills in Maharashtra?',
    'Which government schemes and apprenticeships can fund my training?',
    'What step-by-step learning roadmap should I follow to bridge my skill gaps?',
    'Which skills should I learn for an AI Engineer role?',
    'What is the requirement for EV Battery Technician in Pune?',
  ],
  employee: [
    'How can I transition from my current role to an advanced technology role in Maharashtra?',
    'Which skills from my experience are transferable to Electric Vehicle manufacturing?',
    'What certified upskilling courses are available for working professionals in Pune?',
    'Which high-growth industries in Maharashtra value my existing skill background?',
  ],
  employer: [
    'Which technical competencies are currently reporting the highest hiring bottlenecks?',
    'How can our industry feedback adjust the state-wide curriculum priority score?',
    'What are the emerging skill trends in Smart Manufacturing and Robotics?',
    'What is the verified placement rate for CNC and Welder graduates in Pune?',
  ],
  institute: [
    'Which courses address the highest-priority gaps in Pune?',
    'What modules should we immediately update in our AI & CS syllabus?',
    'Which mechanical and industrial courses show low placement risk?',
    'How should Government ITI Pune adjust CNC machining intake capacity?',
  ],
  government: [
    'What are the biggest skill gaps in Pune?',
    'What government action is recommended for Pune and Nagpur?',
    'What is the projected labour deficit in Electric Vehicle manufacturing?',
    'Which districts have the highest vocational job demand across Maharashtra?',
  ],
  admin: [
    'What is the current status of employer hiring demand validations?',
    'Show the data provenance breakdown across all assessment records',
    'How many technology signals were ingested in the last cycle?',
    'Which training institutes have pending curriculum audit flags?',
  ],
};

export default function CopilotChat({
  defaultRole = 'student',
  initialPrompt = '',
  initialDistrict = '',
  initialStudentId = '',
  initialTopic = '',
  recommendationContext = null,
  autoSend = false,
}) {
  const { role: authRole, isAuthenticated } = useAuth();
  const hasAutoSentRef = useRef(false);

  const effectiveDefaultRole = useMemo(() => {
    if (isAuthenticated && authRole) {
      const lowerAuth = authRole.toLowerCase();
      if (lowerAuth !== 'admin') {
        const valid = ['government', 'institute', 'student', 'employer', 'employee'];
        if (valid.includes(lowerAuth)) {
          return lowerAuth;
        }
        return 'student';
      }
      return defaultRole || 'admin';
    }
    return defaultRole || 'student';
  }, [authRole, isAuthenticated, defaultRole]);

  const [role, setRole] = useState(effectiveDefaultRole);

  useEffect(() => {
    setRole(effectiveDefaultRole);
  }, [effectiveDefaultRole]);

  const visibleRoleDefs = useMemo(() => {
    if (!isAuthenticated || authRole === 'ADMIN') {
      return ROLE_DEFINITIONS;
    }
    const roleKey = authRole.toLowerCase();
    const match = ROLE_DEFINITIONS.filter((r) => r.id === roleKey);
    return match.length > 0 ? match : ROLE_DEFINITIONS;
  }, [authRole, isAuthenticated]);
  const [district, setDistrict] = useState(initialDistrict);
  const [studentId, setStudentId] = useState(initialStudentId);
  const [students, setStudents] = useState([]);
  const [question, setQuestion] = useState(initialPrompt);
  const [loading, setLoading] = useState(false);
  const [errorState, setErrorState] = useState(null);
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [lastQuery, setLastQuery] = useState('');
  const [systemHealth, setSystemHealth] = useState({ ai_available: false, demo_mode: false });

  const [messages, setMessages] = useState([
    {
      id: 'welcome-1',
      sender: 'copilot',
      text: `### Namaste! Welcome to SkillSetuAI Intelligence Copilot

I am your official **Maharashtra Labour-Market Intelligence & Evidence-Based Decision Assistant**, directly grounded in verified state datasets:

* **Authoritative Job Postings** across key Maharashtra industrial districts.
* **NSQF-Aligned Competencies** spanning AI/ML, Cloud, EV Tech, Advanced Manufacturing, and Healthcare.
* **Accredited Training Courses** across government ITIs, polytechnics, and engineering universities.
* **Active Ingestion Feeds & Telemetry** (NAPS apprenticeships, PMKVY certifications, and MahaDBT schemes).

Select your stakeholder role above or explore one of the verified inquiries below to begin.`,
      isGrounded: true,
      model: 'SkillSetuAI Intelligence / RAG Grounded',
      demoMode: false,
      time: 'Just now',
    },
  ]);

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Check system health on mount
  useEffect(() => {
    api.getHealth()
      .then((h) => {
        if (h) setSystemHealth(h);
      })
      .catch(() => {});
  }, []);


  // If initialDistrict provided, update district state and welcome message
  useEffect(() => {
    if (initialDistrict) {
      setDistrict(initialDistrict);
      setMessages([
        {
          id: `welcome-district-${initialDistrict}`,
          sender: 'copilot',
          text: `### 📍 District Workforce Intelligence Context: **${initialDistrict}**\n\nI am configured with verified district-level telemetry for **${initialDistrict}** (industrial clusters, active job openings, local ITI/polytechnic capacity, and skill gap deficits).\n\nAsk any question regarding **${initialDistrict}**'s labour market, seat allocations, or training priorities below.`,
          isGrounded: true,
          model: 'SkillSetuAI Intelligence / RAG Grounded',
          demoMode: false,
          time: 'Just now',
        },
      ]);
    }
  }, [initialDistrict]);

  // Load student list for candidate selector context
  useEffect(() => {
    api.getStudents()
      .then((res) => {
        if (Array.isArray(res) && res.length > 0) {
          setStudents(res);
          if (!studentId && role === 'student') {
            setStudentId(res[0].user_id);
          }
        }
      })
      .catch(() => {});
  }, []);

  // If initialStudentId provided, update state
  useEffect(() => {
    if (initialStudentId) {
      setStudentId(initialStudentId);
    }
  }, [initialStudentId]);

  // If initialPrompt provided, auto-populate
  useEffect(() => {
    if (initialPrompt) {
      setQuestion(initialPrompt);
    }
  }, [initialPrompt]);

  // Context-aware auto-submission from Career Recommendations (Phase 18)
  useEffect(() => {
    const topic = recommendationContext?.topic || initialTopic;
    if (!topic || hasAutoSentRef.current) return;

    // contextualQuery must NOT overwrite an explicit initialPrompt
    if (initialPrompt && initialPrompt.trim()) {
      return;
    }

    const targetRole =
      recommendationContext?.target_role ||
      (students.find((s) => s.user_id === (initialStudentId || studentId))?.target_role) ||
      'AI Engineer';

    const contextualQuery = `Explain why I should learn ${topic} based on my SkillSetuAI profile and current Maharashtra labour-market intelligence. My target role is ${targetRole}. Show the relevant demand signals, required competencies, my missing prerequisites, relevant SkillSetuAI courses/training, and a practical learning path.`;

    setQuestion(contextualQuery);

    if (autoSend || recommendationContext) {
      hasAutoSentRef.current = true;
      if (typeof window !== 'undefined' && window.history?.replaceState) {
        window.history.replaceState({}, document.title);
      }
      handleSend(contextualQuery, recommendationContext);
    }
  }, [initialTopic, recommendationContext, autoSend, students, initialStudentId, studentId, initialPrompt]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Auto-resize textarea based on input
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [question]);

  const activeRoleDef = ROLE_DEFINITIONS.find((r) => r.id === role) || ROLE_DEFINITIONS[0];

  const handleSend = async (queryText = question, contextData = null) => {
    const trimmed = queryText.trim();
    if (!trimmed || loading) return;

    setLastQuery(trimmed);
    setErrorState(null);

    const userMsg = {
      id: `usr-${Date.now()}`,
      sender: 'user',
      text: trimmed,
      role: role,
      district: district || undefined,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setQuestion('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    setLoading(true);

    try {
      const activeRole = (isAuthenticated && authRole && authRole.toLowerCase() !== 'admin')
        ? (['government', 'institute', 'student', 'employer', 'employee'].includes(authRole.toLowerCase()) ? authRole.toLowerCase() : 'student')
        : role;
      const res = await api.askCopilot(
        trimmed,
        activeRole,
        district || undefined,
        (activeRole === 'student' ? (studentId || initialStudentId) : undefined) || undefined,
        contextData || undefined
      );
      setErrorState(null);
      setMessages((prev) => [
        ...prev,
        {
          id: `cop-${Date.now()}`,
          sender: 'copilot',
          text: res.answer || 'No specific response was generated.',
          isGrounded: res.data_grounded !== false,
          demoMode: !!res.demo_mode,
          model: res.model || (res.demo_mode ? 'Rule-Based Offline Intelligence' : 'Gemini 3.6 Flash'),
          provenanceLabel: res.provenance_label || (res.demo_mode ? '🛡️ Grounded Offline Intelligence' : '✨ Generated by Gemini AI'),
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } catch (err) {
      console.warn('[Copilot] Live API call failed:', err);
      if (systemHealth.demo_mode) {
        setErrorState(null); // Clear blocking red banner in explicit demo mode since fallback is available
        const fallback = generateClientFallback(trimmed, role, district || undefined);
        setMessages((prev) => [
          ...prev,
          {
            id: `cop-${Date.now()}`,
            sender: 'copilot',
            text: fallback.answer,
            isGrounded: false,
            isFallback: true,
            demoMode: true,
            model: fallback.model || 'Offline Intelligence (Static Fallback)',
            provenanceLabel: '⚠️ Offline Static Fallback (Demo Mode)',
            notice: fallback.notice,
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      } else {
        const errMsg = err?.message || 'Service unreachable';
        setErrorState({
          message: `Copilot service temporarily unavailable (${errMsg})`,
          query: trimmed,
          contextData: contextData || null,
        });
        setMessages((prev) => [
          ...prev,
          {
            id: `cop-${Date.now()}`,
            sender: 'copilot',
            text: `⚠️ **Service Unavailable**: Unable to reach the SkillSetuAI Copilot service (${errMsg}). In Real Data mode, synthetic factual fallbacks are disabled to prevent inaccurate labour market intelligence.`,
            isGrounded: false,
            isFallback: false,
            isError: true,
            demoMode: false,
            model: 'Real Data Service (Offline)',
            provenanceLabel: '⚠️ Service Offline',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCopy = (text, idx) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(idx);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleClearChat = () => {
    setMessages([
      {
        id: 'welcome-reset',
        sender: 'copilot',
        text: `### Conversation Cleared

Ready for a new inquiry. You are currently consulting as **${activeRoleDef.label}** (${activeRoleDef.badge}). How can I assist you?`,
        isGrounded: true,
        model: 'SkillSetuAI Intelligence / RAG Grounded',
        demoMode: false,
        time: 'Just now',
      },
    ]);
    setErrorState(null);
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col h-[700px] max-h-[85vh] overflow-hidden transition-colors">
      {/* Header with Title, Role Switcher, and Actions */}
      <div className="p-4 bg-slate-900 dark:bg-slate-950 text-white flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-teal-600/30 border border-teal-500/40 flex items-center justify-center font-extrabold text-sm text-teal-300 shadow-xs shrink-0">
            AI
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-extrabold text-sm sm:text-base tracking-tight text-white flex items-center gap-1.5">
                SkillSetuAI Intelligence Copilot
              </h3>
              <span className="px-2 py-0.5 rounded-full bg-teal-500/20 text-teal-300 text-[10px] font-mono border border-teal-500/30 font-semibold">
                RAG Grounded
              </span>
              <span className="hidden sm:inline-block px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 text-[10px] font-mono border border-slate-700">
                NSQF Aligned
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Evidence-based labour-market intelligence & curriculum decision engine for Maharashtra
            </p>
          </div>
        </div>

        {/* Role Selector & Clear Chat Button */}
        <div className="flex items-center gap-2 self-start md:self-auto w-full md:w-auto justify-between md:justify-end">
          <div className="flex items-center gap-1 bg-slate-800/90 dark:bg-slate-900 p-1 rounded-xl text-xs border border-slate-700/60 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden max-w-full">
            {visibleRoleDefs.map((r) => (
              <button
                key={r.id}
                onClick={() => setRole(r.id)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all whitespace-nowrap flex items-center gap-1 cursor-pointer ${
                  role === r.id
                    ? 'bg-teal-600 text-white shadow-xs'
                    : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                }`}
                title={r.badge}
              >
                <span>{r.icon}</span>
                <span>{r.label}</span>
              </button>
            ))}
          </div>

          <button
            onClick={handleClearChat}
            title="Clear conversation history"
            className="p-1.5 px-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg text-xs border border-slate-800 transition-colors shrink-0 cursor-pointer"
          >
            Reset
          </button>
        </div>
      </div>

      {/* District Context Active Banner */}
      {district && (
        <div className="bg-teal-500/10 dark:bg-teal-950/50 px-4 py-2 border-b border-teal-500/20 flex items-center justify-between gap-2 text-xs shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-teal-800 dark:text-teal-300 font-bold flex items-center gap-1.5">
              <span>📍</span>
              <span>District Context: <strong>{district}</strong></span>
            </span>
            <span className="text-[11px] text-slate-500 dark:text-slate-400 hidden sm:inline">
              (Queries automatically ground to {district} labour-market telemetry)
            </span>
          </div>
          <button
            onClick={() => {
              setDistrict('');
              const params = new URLSearchParams(window.location.search);
              params.delete('district');
              params.delete('q');
              const newSearch = params.toString() ? `?${params.toString()}` : '';
              window.history.replaceState({}, '', `${window.location.pathname}${newSearch}`);
            }}
            className="px-2 py-0.5 rounded bg-teal-100 dark:bg-teal-900/60 hover:bg-teal-200 dark:hover:bg-teal-800 text-teal-800 dark:text-teal-200 text-[11px] font-semibold transition-colors cursor-pointer flex items-center gap-1"
            title="Clear District Context"
          >
            <span>Clear Context</span>
            <span>✕</span>
          </button>
        </div>
      )}

      {/* Student Candidate Context Active Banner (Phase 17) */}
      {role === 'student' && students.length > 0 && (
        <div className="bg-teal-500/10 dark:bg-teal-950/50 px-4 py-2 border-b border-teal-500/20 flex flex-wrap items-center justify-between gap-2 text-xs shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-teal-800 dark:text-teal-300 font-bold flex items-center gap-1.5">
              <span>🎓</span>
              <span>Candidate Recommendation Context:</span>
            </span>
            <select
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              className="px-2 py-0.5 rounded bg-white dark:bg-slate-800 border border-teal-300 dark:border-teal-700 text-xs font-bold text-slate-800 dark:text-white cursor-pointer"
            >
              {students.map((s) => (
                <option key={s.user_id} value={s.user_id}>
                  {s.name} ({s.target_role})
                </option>
              ))}
            </select>
          </div>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">
            Queries ground in candidate assessment, skill gaps, validated employer demand, and schemes.
          </span>
        </div>
      )}

      {/* Active Career Recommendation Handoff Context Banner (Phase 18) */}
      {recommendationContext && (
        <div className="bg-teal-50 dark:bg-teal-950/70 px-4 py-2 border-b border-teal-200 dark:border-teal-800/80 flex flex-wrap items-center justify-between gap-2 text-xs shrink-0 animate-in fade-in duration-200">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="w-2 h-2 rounded-full bg-teal-500 animate-pulse shrink-0"></span>
            <span className="font-bold text-teal-900 dark:text-teal-200">
              Active Recommendation Context:
            </span>
            <span className="px-2 py-0.5 rounded bg-white dark:bg-slate-900 border border-teal-200 dark:border-teal-700 text-teal-800 dark:text-teal-300 font-mono text-[11px] font-bold">
              {recommendationContext.topic}
            </span>
            {recommendationContext.target_role && (
              <span className="text-slate-600 dark:text-slate-300 text-[11px]">
                • Target: <strong className="text-slate-800 dark:text-white">{recommendationContext.target_role}</strong>
              </span>
            )}
            {recommendationContext.missing_prerequisites?.length > 0 && (
              <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300">
                Prerequisite Gap
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 text-[10px] font-mono text-teal-700 dark:text-teal-400">
            <span>🛡️ Grounded in Maharashtra Intelligence</span>
          </div>
        </div>
      )}

      {/* Role Context & Suggested Inquiries Bar */}
      <div className="bg-slate-50 dark:bg-slate-950/80 px-4 py-2.5 border-b border-slate-200 dark:border-slate-800 flex items-center gap-2 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden text-xs shrink-0">
        <span className="text-slate-500 dark:text-slate-400 font-bold shrink-0 text-[11px] uppercase tracking-wider flex items-center gap-1">
          <span>💡</span> {district ? `${district} Inquiries:` : 'Suggested Inquiries:'}
        </span>
        <div className="flex items-center gap-1.5 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden py-0.5">
          {(district
            ? [
                `Give me a detailed workforce intelligence briefing for ${district}.`,
                `What are the critical skill gaps in ${district}?`,
                `What is the accredited training capacity in ${district}?`,
                `Which industry sectors are hiring the most in ${district}?`,
              ]
            : CONTEXTUAL_PROMPTS[role] || []
          ).map((promptText, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(promptText)}
              disabled={loading}
              className="px-3 py-1 bg-white dark:bg-slate-800 hover:bg-teal-50 dark:hover:bg-teal-950 hover:text-teal-800 dark:hover:text-teal-300 text-slate-700 dark:text-slate-200 font-medium rounded-full border border-slate-200 dark:border-slate-700 shrink-0 transition-colors shadow-2xs text-[11px] cursor-pointer disabled:opacity-50"
            >
              {promptText}
            </button>
          ))}
        </div>
      </div>

      {/* Non-blocking Error Notice */}
      {errorState && (
        <div className="px-4 py-2 bg-rose-50 dark:bg-rose-950/40 border-b border-rose-200 dark:border-rose-900/60 text-rose-800 dark:text-rose-300 text-xs flex items-center justify-between gap-2 shrink-0">
          <div className="flex items-center gap-2">
            <span>⚠️</span>
            <span>{errorState.message}</span>
          </div>
          <button
            onClick={() => handleSend(errorState.query, errorState.contextData)}
            disabled={loading}
            className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded text-[11px] font-bold shadow-xs cursor-pointer disabled:opacity-50"
          >
            Retry
          </button>
        </div>
      )}

      {/* Messages Scroll Stream */}
      <div className="flex-1 p-4 sm:p-5 overflow-y-auto space-y-4 bg-slate-50/50 dark:bg-slate-950/40">
        {messages.map((m, idx) => (
          <div
            key={m.id || idx}
            className={`flex ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[92%] sm:max-w-[85%] rounded-2xl p-4 sm:p-5 text-xs sm:text-[13px] leading-relaxed shadow-2xs ${
                m.sender === 'user'
                  ? 'bg-slate-900 dark:bg-teal-700 text-white rounded-br-xs'
                  : 'bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 border border-slate-200 dark:border-slate-700/80 rounded-bl-xs'
              }`}
            >
              {/* Message Header */}
              <div className="flex items-center justify-between gap-3 mb-2.5 pb-1.5 border-b border-slate-100 dark:border-slate-700/50 opacity-75 text-[11px]">
                <div className="flex items-center gap-1.5 font-bold uppercase tracking-wider">
                  <span>{m.sender === 'user' ? '👤' : '✨'}</span>
                  <span>{m.sender === 'user' ? `You (${m.role || role})` : 'SkillSetuAI Intelligence Copilot'}</span>
                  {m.provenanceLabel && (
                    <span className={`text-[9px] font-mono font-semibold px-1.5 py-0.2 rounded normal-case ml-1 ${
                      m.isFallback
                        ? 'bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-200 border border-amber-300 dark:border-amber-700'
                        : 'bg-teal-100 dark:bg-teal-900 text-teal-800 dark:text-teal-200'
                    }`}>
                      {m.provenanceLabel}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 text-[10px] text-slate-400 dark:text-slate-400 font-mono">
                  <span>{m.time}</span>
                  {m.sender === 'copilot' && (
                    <button
                      onClick={() => handleCopy(m.text, idx)}
                      className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-0.5 rounded cursor-pointer"
                      title="Copy response text"
                    >
                      {copiedIndex === idx ? '✓ Copied' : '📋 Copy'}
                    </button>
                  )}
                </div>
              </div>

              {/* Message Body */}
              {m.sender === 'user' ? (
                <div className="leading-relaxed break-words whitespace-pre-wrap font-medium">
                  {m.text}
                </div>
              ) : (
                <div className="leading-relaxed overflow-hidden prose-sm dark:prose-invert max-w-none">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      h1: ({ node, ...props }) => (
                        <h1 className="text-sm sm:text-base font-extrabold text-slate-900 dark:text-white mt-3 mb-2 first:mt-0 tracking-tight" {...props} />
                      ),
                      h2: ({ node, ...props }) => (
                        <h2 className="text-xs sm:text-sm font-bold text-slate-900 dark:text-white mt-3 mb-1.5 first:mt-0 tracking-tight" {...props} />
                      ),
                      h3: ({ node, ...props }) => (
                        <h3 className="text-xs sm:text-sm font-bold text-slate-900 dark:text-white mt-2.5 mb-1.5 first:mt-0" {...props} />
                      ),
                      h4: ({ node, ...props }) => (
                        <h4 className="text-xs font-bold text-slate-900 dark:text-white mt-2 mb-1 first:mt-0" {...props} />
                      ),
                      p: ({ node, ...props }) => (
                        <p className="mb-2.5 last:mb-0 leading-relaxed break-words text-slate-800 dark:text-slate-200" {...props} />
                      ),
                      ul: ({ node, ...props }) => (
                        <ul className="list-disc list-outside pl-4 space-y-1.5 mb-3 text-xs sm:text-[13px]" {...props} />
                      ),
                      ol: ({ node, ...props }) => (
                        <ol className="list-decimal list-outside pl-4 space-y-1.5 mb-3 text-xs sm:text-[13px]" {...props} />
                      ),
                      li: ({ node, ...props }) => (
                        <li className="leading-relaxed pl-0.5 text-slate-800 dark:text-slate-200" {...props} />
                      ),
                      strong: ({ node, ...props }) => (
                        <strong className="font-bold text-slate-900 dark:text-white" {...props} />
                      ),
                      em: ({ node, ...props }) => (
                        <em className="italic" {...props} />
                      ),
                      hr: ({ node, ...props }) => (
                        <hr className="my-3.5 border-t border-slate-200 dark:border-slate-700" {...props} />
                      ),
                      a: ({ node, ...props }) => (
                        <a
                          className="text-teal-600 dark:text-teal-400 underline hover:text-teal-700 dark:hover:text-teal-300 font-medium break-all"
                          target="_blank"
                          rel="noopener noreferrer"
                          {...props}
                        />
                      ),
                      code: ({ node, inline, ...props }) => (
                        inline ? (
                          <code className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-900 text-teal-800 dark:text-teal-300 font-mono text-[11px] border border-slate-200 dark:border-slate-700 break-all" {...props} />
                        ) : (
                          <code className="block p-3 my-2 rounded-lg bg-slate-900 text-slate-100 font-mono text-[11px] overflow-x-auto border border-slate-800 leading-normal" {...props} />
                        )
                      ),
                      pre: ({ node, ...props }) => (
                        <pre className="overflow-x-auto my-2 rounded-lg max-w-full" {...props} />
                      ),
                      blockquote: ({ node, ...props }) => (
                        <blockquote className="border-l-3 border-teal-500 bg-teal-50/50 dark:bg-teal-950/20 p-2.5 px-3 rounded-r-lg my-2.5 text-slate-700 dark:text-slate-300 italic" {...props} />
                      ),
                      table: ({ node, ...props }) => (
                        <div className="overflow-x-auto my-3">
                          <table className="w-full text-left text-xs border border-slate-200 dark:border-slate-700 rounded-lg divide-y divide-slate-200 dark:divide-slate-700" {...props} />
                        </div>
                      ),
                      th: ({ node, ...props }) => (
                        <th className="p-2.5 bg-slate-100 dark:bg-slate-800/80 font-bold text-slate-900 dark:text-white" {...props} />
                      ),
                      td: ({ node, ...props }) => (
                        <td className="p-2.5 border-b border-slate-100 dark:border-slate-800 text-slate-800 dark:text-slate-200" {...props} />
                      ),
                    }}
                  >
                    {m.text}
                  </ReactMarkdown>
                </div>
              )}

              {m.sender === 'copilot' && !m.isError && (
                <div className="mt-3.5 pt-2 border-t border-slate-100 dark:border-slate-700/60 flex flex-wrap items-center justify-between gap-2 text-[10px] text-slate-500 dark:text-slate-400">
                  {m.isGrounded !== false ? (
                    <span className="text-emerald-700 dark:text-emerald-400 font-semibold flex items-center gap-1">
                      <span>✓</span> Verified against Maharashtra Labour Dataset
                    </span>
                  ) : (
                    <span className="text-amber-700 dark:text-amber-400 font-semibold flex items-center gap-1">
                      <span>⚠️</span> Not verified against Maharashtra Labour Dataset
                    </span>
                  )}
                  <div className="flex items-center gap-2">
                    {m.demoMode ? (
                      <span className="bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 px-2 py-0.5 rounded font-mono font-bold">
                        OFFLINE FALLBACK
                      </span>
                    ) : (
                      <span className="bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300 px-2 py-0.5 rounded font-mono font-bold border border-teal-200 dark:border-teal-800">
                        {m.model || 'Gemini 3.6 Flash'}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Dynamic Loading State */}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-4 text-xs text-slate-600 dark:text-slate-300 flex items-center gap-3 shadow-2xs">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-teal-600 dark:bg-teal-400 animate-bounce"></span>
                <span className="w-2.5 h-2.5 rounded-full bg-teal-600 dark:bg-teal-400 animate-bounce [animation-delay:0.2s]"></span>
                <span className="w-2.5 h-2.5 rounded-full bg-teal-600 dark:bg-teal-400 animate-bounce [animation-delay:0.4s]"></span>
              </div>
              <div className="space-y-0.5">
                <p className="font-bold text-slate-900 dark:text-white text-xs">
                  Synthesizing Labour Intelligence...
                </p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                  Querying district job demands, curriculum health, and Gemini 3.6 Flash inference
                </p>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-3 sm:p-4 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 shrink-0">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="space-y-2"
        >
          <div className="flex items-end gap-2 bg-slate-50 dark:bg-slate-800/80 p-2 rounded-xl border border-slate-300 dark:border-slate-700 focus-within:ring-2 focus-within:ring-teal-500 focus-within:border-teal-500">
            <textarea
              ref={textareaRef}
              rows={1}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
              placeholder={activeRoleDef.placeholder}
              className="flex-1 px-2 py-1 bg-transparent text-slate-900 dark:text-slate-100 text-xs sm:text-sm focus:outline-none resize-none max-h-32 disabled:opacity-50 leading-relaxed"
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="px-4 py-2 bg-slate-900 dark:bg-teal-600 hover:bg-slate-800 dark:hover:bg-teal-700 disabled:opacity-40 text-white text-xs sm:text-sm font-bold rounded-lg transition-colors shadow-xs shrink-0 flex items-center gap-1.5 cursor-pointer"
            >
              {loading ? (
                <>
                  <svg className="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Inquiring...</span>
                </>
              ) : (
                <>
                  <span>Send</span>
                  <span>↵</span>
                </>
              )}
            </button>
          </div>

          <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 px-1">
            <span className="hidden sm:inline">
              Press <strong>Enter ↵</strong> to send • <strong>Shift + Enter</strong> for a new line
            </span>
            <span className="font-mono text-[10px]">
              Grounded in Maharashtra OGD & NSDC Datasets
            </span>
          </div>
        </form>
      </div>
    </div>
  );
}
