import React from 'react';
import { useSearchParams, useLocation } from 'react-router-dom';
import Layout from '../components/Layout';
import CopilotChat from '../components/CopilotChat';
import { useAuth } from '../context/AuthContext';

import { resolveEffectiveCopilotRole } from '../utils/copilotRole';

export default function CopilotPage({ roleOverride }) {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const { role: authRole, isAuthenticated } = useAuth();
  const urlRole = searchParams.get('role');
  const initialRole = resolveEffectiveCopilotRole({
    authRole,
    isAuthenticated,
    urlRole,
    roleOverride,
  });

  const initialPrompt = searchParams.get('q') || searchParams.get('prompt') || '';
  const urlDistrict = searchParams.get('district') || '';
  const urlStudentId = searchParams.get('student_id') || searchParams.get('student') || '';
  const urlTopic = searchParams.get('topic') || '';
  const recommendationContext = location.state?.recommendationContext || null;
  const initialStudentId = recommendationContext?.student_id || location.state?.student_id || urlStudentId || '';
  const autoSend = location.state?.autoSend ?? Boolean(urlTopic && !initialPrompt);

  return (
    <Layout>
      <div className="max-w-5xl mx-auto py-2">
        <div className="mb-6 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-50 dark:bg-teal-950 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800 text-xs font-semibold mb-2">
            Multi-Stakeholder Conversational Decision Support
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            SkillSetuAI Intelligence Copilot
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-xl mx-auto">
            Query labour-market intelligence, verify district skill supply gaps, assess curriculum alignment, and guide career choices.
          </p>
        </div>

        <div data-demo="copilot-chat-container">
          <CopilotChat
            defaultRole={initialRole}
            initialPrompt={initialPrompt}
            initialDistrict={urlDistrict}
            initialStudentId={initialStudentId}
            initialTopic={urlTopic}
            recommendationContext={recommendationContext}
            autoSend={autoSend}
          />
        </div>
      </div>
    </Layout>
  );
}
