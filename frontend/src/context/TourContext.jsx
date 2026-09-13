import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';

// =========================================================================
// 1. STUDENT DEMO TOUR (Role: STUDENT)
// =========================================================================
export const STUDENT_TOUR_STEPS = [
  {
    step: 1,
    route: '/student?tab=passport',
    targetSelector: '[data-demo="student-passport-radar"]',
    stage: '01. Skill Passport',
    title: 'Personalized Dynamic Skill Passport',
    description: 'Displays verified competencies, baseline strengths, and direct comparison against required target role standards.',
    whyItMatters: 'Gives youth full transparency into their current market readiness and skill gaps.',
    badge: 'Competency Radar',
  },
  {
    step: 2,
    route: '/student?tab=assessment',
    targetSelector: '[data-demo="student-assessment-section"]',
    stage: '02. Diagnostic Assessment',
    title: 'Adaptive Problem-Solving & Domain Quiz',
    description: '4-question diagnostic testing algorithmic, domain, and aptitude problem-solving with automated scoring.',
    whyItMatters: 'Calibrates candidate readiness score based on real problem-solving rather than self-reported claims.',
    badge: 'Diagnostic Quiz',
  },
  {
    step: 3,
    route: '/student?tab=recommendations',
    targetSelector: '[data-demo="career-recommendations-section"]',
    stage: '03. Career Recommendations',
    title: 'Grounded Career Pathways & Job Demand',
    description: 'Personalized career recommendations ranked by competency match %, validated employer vacancies, and salary benchmarks.',
    whyItMatters: 'Connects individual skills directly to live hiring demand across Maharashtra industrial corridors.',
    badge: 'Career Pathways',
  },
  {
    step: 4,
    route: '/student?tab=roadmap',
    targetSelector: '[data-demo="student-roadmap-list"]',
    stage: '04. Learning Roadmap',
    title: 'Sequential Learning Roadmap',
    description: 'Progressive, NSQF-aligned milestones bridging your identified skill gaps step-by-step.',
    whyItMatters: 'Converts abstract skill requirements into an actionable study plan with verified courses.',
    badge: 'NSQF Learning Path',
  },
  {
    step: 5,
    route: '/student?tab=signals',
    targetSelector: '[data-demo="student-industry-alerts"]',
    stage: '05. Industry Alerts',
    title: 'Future Demand & Emerging Tech Alerts',
    description: 'Live technological alerts, breakthrough tools, and vacancy surges across Maharashtra industrial hubs.',
    whyItMatters: 'Keeps candidates ahead of obsolescence with early notification of rising technologies.',
    badge: '7 Growth Sectors',
  },
  {
    step: 6,
    route: '/student/copilot',
    targetSelector: '[data-demo="copilot-chat-container"]',
    stage: '06. AI Career Copilot',
    title: 'Evidence-Based AI Career Copilot',
    description: 'Ask questions about prerequisite competencies, curriculum advice, and state welfare schemes with verified citations.',
    whyItMatters: 'Your personal 24/7 career mentor grounded in real labor market telemetry.',
    badge: 'Grounded AI Copilot',
  },
];

// =========================================================================
// 2. EMPLOYER DEMO TOUR (Role: EMPLOYER)
// =========================================================================
export const EMPLOYER_TOUR_STEPS = [
  {
    step: 1,
    route: '/employer',
    targetSelector: '[data-demo="employer-dashboard-container"]',
    stage: '01. Employer Hub',
    title: 'Industry Demand & Hiring Command',
    description: 'Publish first-party hiring requirements and evaluate regional candidate availability across Maharashtra.',
    whyItMatters: 'Directly calibrates the state skill pipeline with real-time industry needs.',
    badge: 'Employer Command',
  },
  {
    step: 2,
    route: '/employer',
    targetSelector: '[data-demo="employer-post-demand-btn"]',
    stage: '02. Post Hiring Demands',
    title: 'Submit Verified Job Requirements',
    description: 'Specify required job roles, critical skills, proficiency levels, and hiring timelines.',
    whyItMatters: 'Ensures government and ITI training curriculums update to match your specific toolsets.',
    badge: 'Demand Submission',
  },
  {
    step: 3,
    route: '/employer',
    targetSelector: '[data-demo="employer-validation-queue"]',
    stage: '03. Human-in-the-Loop Validation',
    title: 'Validate AI Labor Market Trends',
    description: 'Confirm, correct, or reject AI-generated skill demand estimates to keep the intelligence loop grounded.',
    whyItMatters: 'Eliminates AI hallucinations by incorporating domain expert human consensus.',
    badge: 'Human-in-the-Loop',
  },
  {
    step: 4,
    route: '/employer',
    targetSelector: '[data-demo="employer-difficult-skills"]',
    stage: '04. Talent Bottlenecks',
    title: 'Difficult-to-Hire Shortage Tracker',
    description: 'Track critical talent bottlenecks across Pune, Mumbai, Nashik, and Nagpur industrial belts.',
    whyItMatters: 'Identifies where institutional training capacity must expand to solve workforce deficits.',
    badge: 'Talent Shortages',
  },
  {
    step: 5,
    route: '/employer/copilot',
    targetSelector: '[data-demo="copilot-chat-container"]',
    stage: '05. Talent Intelligence Copilot',
    title: 'Conversational Labour Intelligence',
    description: 'Query graduate placement conversion, technician availability, and salary benchmarks.',
    whyItMatters: 'Assists in data-backed workforce planning and hiring strategy.',
    badge: 'Talent Intelligence',
  },
];

// =========================================================================
// 3. INSTITUTE DEMO TOUR (Role: INSTITUTE)
// =========================================================================
export const INSTITUTE_TOUR_STEPS = [
  {
    step: 1,
    route: '/institute',
    targetSelector: '[data-demo="institute-dashboard-container"]',
    stage: '01. Institute Portal',
    title: 'Curriculum Modernization & Course Health',
    description: 'Manage accredited vocational trades, monitor graduate placement conversion, and audit curriculum modernity.',
    whyItMatters: 'Prevents training institutions from graduating youth into saturated or obsolete trades.',
    badge: 'Curriculum Health',
  },
  {
    step: 2,
    route: '/institute',
    targetSelector: '[data-demo="course-health-grid"]',
    stage: '02. Course Health & Obsolescence',
    title: 'Placement Efficiency & Obsolescence Flags',
    description: 'Automated detection of course health scores, modernity index, and oversupply warnings (<30% placement with high intake).',
    whyItMatters: 'Provides early warning to institutional deans before accreditation reviews.',
    badge: 'Obsolescence Alerts',
  },
  {
    step: 3,
    route: '/institute',
    targetSelector: '[data-demo="curriculum-recommendations-grid"]',
    stage: '03. Modernization Blueprints',
    title: '5-Point Curriculum Overhaul Blueprints',
    description: 'Specific module pruning recommendations, NSQF-aligned competency additions, and target placement lift estimates.',
    whyItMatters: 'Delivers turn-key syllabus revision packages ready for MSBTE / ITI council submission.',
    badge: 'Syllabus Blueprints',
  },
  {
    step: 4,
    route: '/institute/copilot',
    targetSelector: '[data-demo="copilot-chat-container"]',
    stage: '04. Academic Copilot',
    title: 'Academic & NSQF Decision Support',
    description: 'Query syllabus modernization best practices, credit frameworks, and regional industry demand.',
    whyItMatters: 'Instant pedagogical advice tailored to Maharashtra vocational training regulations.',
    badge: 'Academic Copilot',
  },
];

// =========================================================================
// 4. GOVERNMENT DEMO TOUR (Role: GOVERNMENT)
// =========================================================================
export const GOVERNMENT_TOUR_STEPS = [
  {
    step: 1,
    route: '/government',
    targetSelector: '[data-demo="government-kpis"]',
    stage: '01. State Command',
    title: 'Maharashtra Workforce Command Center',
    description: 'Macro overview of 36 districts, active job demand velocity, training supply, and net skill deficits.',
    whyItMatters: 'Provides top leadership with a single unified evidence base for state-wide skill policy.',
    badge: 'Live State KPIs',
  },
  {
    step: 2,
    route: '/government',
    targetSelector: '[data-demo="district-heatmap"]',
    stage: '02. District Heatmap',
    title: '36-District Spatial Intelligence',
    description: 'Compare regional talent surpluses and deficits across Western Maharashtra, Marathwada, and Vidarbha.',
    whyItMatters: 'Target public investments where local industrial corridors face critical worker shortages.',
    badge: 'District Heatmap',
  },
  {
    step: 3,
    route: '/government',
    targetSelector: '[data-demo="skill-gaps-table"]',
    stage: '03. Automated Skill Gap Engine',
    title: 'Formula-Driven Talent Deficit Detection',
    description: 'Identifies high-priority gaps: (Demand Frequency % − Curriculum Coverage % = Net Talent Deficit).',
    whyItMatters: 'Directly guides annual ITI trade seat reallocation quotas.',
    badge: 'Demand - Coverage = Gap',
  },
  {
    step: 4,
    route: '/government/district/Pune',
    targetSelector: '[data-demo="district-micro-plan"]',
    stage: '04. District Micro-Plans',
    title: 'Actionable District Workforce Action Plans',
    description: 'Concrete operational blueprints with seat allocations, equipment grants, and instructor counts for Pune district.',
    whyItMatters: 'Converts state-level policy goals into local execution.',
    badge: 'Pune Micro-Plan',
  },
  {
    step: 5,
    route: '/government',
    targetSelector: '[data-demo="policy-whatif-simulator"]',
    stage: '05. Policy What-If Simulator',
    title: 'Policy Simulation & Impact Modeling',
    description: 'Simulate the effect of increasing seat capacity by 30% or curriculum stagnation over 1-5 years (clearly tagged SIMULATED ESTIMATE).',
    whyItMatters: 'Forecast placement outcomes and budget requirements before investing public funds.',
    badge: 'Policy Simulator',
  },
  {
    step: 6,
    route: '/government/copilot',
    targetSelector: '[data-demo="copilot-chat-container"]',
    stage: '06. Policy AI Copilot',
    title: 'Government Decision-Support Copilot',
    description: 'Query district budget optimization, regional demand shifts, and policy recommendations.',
    whyItMatters: 'Evidence-based policy assistant grounded in multi-source Maharashtra data.',
    badge: 'Policy AI Copilot',
  },
];

// =========================================================================
// 5. ADMIN DEMO TOUR (Role: ADMIN)
// =========================================================================
export const ADMIN_TOUR_STEPS = [
  {
    step: 1,
    route: '/admin?tab=overview',
    targetSelector: '[data-demo="admin-overview-section"]',
    stage: '01. Executive Governance',
    title: 'Administrative Command Center',
    description: 'Complete oversight across Student, Employer, Institute, Government, and Industry telemetry pipelines.',
    whyItMatters: 'Single control center for multi-stakeholder platform administration.',
    badge: 'Cross-Domain Oversight',
  },
  {
    step: 2,
    route: '/admin?tab=students',
    targetSelector: '[data-demo="admin-students-section"]',
    stage: '02. Assessment Telemetry',
    title: 'Student Assessment Registry & Provenance',
    description: 'Real-time candidate telemetry partitioned into USER_SUBMITTED (live assessments) and DEMO_SYNTHETIC (baseline benchmarks).',
    whyItMatters: 'Maintains complete auditability and data provenance separation.',
    badge: 'Provenance Partitioning',
  },
  {
    step: 3,
    route: '/admin?tab=employers',
    targetSelector: '[data-demo="admin-employers-section"]',
    stage: '03. Employer Validation Gate',
    title: 'First-Party Employer Demands Moderation',
    description: 'Review, validate, or reject incoming industry hiring demand orders before inclusion in recommendation models.',
    whyItMatters: 'Guarantees zero spam or fraudulent job postings in the candidate recommendation loop.',
    badge: 'Validation Gate',
  },
  {
    step: 4,
    route: '/admin?tab=industry',
    targetSelector: '[data-demo="admin-signals-section"]',
    stage: '04. Industry Intelligence Moderation',
    title: 'Continuous Signal Ingestion & Moderation',
    description: 'Audit automated technology signals, manage source credibility scores, and trigger manual web ingestion runs.',
    whyItMatters: 'Ensures freshness and accuracy of market intelligence feeds.',
    badge: 'Ingestion Pipeline',
  },
  {
    step: 5,
    route: '/admin/copilot',
    targetSelector: '[data-demo="copilot-chat-container"]',
    stage: '05. Cross-Platform Copilot',
    title: 'Platform-Wide Conversational AI',
    description: 'Query cross-domain metrics, moderation pipelines, and systemic workforce patterns.',
    whyItMatters: 'Comprehensive analytical assistant for platform administrators.',
    badge: 'Platform Intelligence',
  },
];

// =========================================================================
// 6. PUBLIC / UNINITIALIZED TOUR (Not Authenticated)
// =========================================================================
export const PUBLIC_TOUR_STEPS = [
  {
    step: 1,
    route: '/',
    targetSelector: '[data-demo="hero-section"]',
    stage: '01. Overview',
    title: 'SkillSetuAI — Maharashtra Workforce Intelligence',
    description: 'An evidence-based closed-loop platform connecting Government, Industry, Institutes, and Students.',
    whyItMatters: 'Select any demo role to experience a tailored, domain-specific platform.',
    badge: 'One Platform • Five Experiences',
  },
  {
    step: 2,
    route: '/login',
    targetSelector: null,
    stage: '02. Stakeholder Portals',
    title: 'Select a Stakeholder Demo Account',
    description: 'Sign in as a Student, Employer, Training Institute, State Government Official, or Platform Administrator.',
    whyItMatters: 'Each login unlocks a dedicated, role-specific console with zero cross-role clutter.',
    badge: 'Quick Sign-In',
  },
];

const TourContext = createContext(null);

export function TourProvider({ children }) {
  const { role, isAuthenticated } = useAuth();
  const [isTourOpen, setIsTourOpen] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const navigate = useNavigate();
  const location = useLocation();

  // Dynamically select the active tour steps array based on authenticated role
  const activeSteps = useMemo(() => {
    if (!isAuthenticated) return PUBLIC_TOUR_STEPS;
    switch (role) {
      case 'STUDENT':
        return STUDENT_TOUR_STEPS;
      case 'EMPLOYER':
        return EMPLOYER_TOUR_STEPS;
      case 'INSTITUTE':
        return INSTITUTE_TOUR_STEPS;
      case 'GOVERNMENT':
        return GOVERNMENT_TOUR_STEPS;
      case 'ADMIN':
        return ADMIN_TOUR_STEPS;
      default:
        return PUBLIC_TOUR_STEPS;
    }
  }, [role, isAuthenticated]);

  const totalSteps = activeSteps.length;
  const currentStep = activeSteps[currentStepIndex] || activeSteps[0];

  const startTour = useCallback(() => {
    setCurrentStepIndex(0);
    setIsTourOpen(true);
    const firstStep = activeSteps[0];
    const currentFull = location.pathname + location.search;
    if (firstStep && currentFull !== firstStep.route) {
      navigate(firstStep.route);
    }
  }, [activeSteps, location.pathname, location.search, navigate]);

  const exitTour = useCallback(() => {
    setIsTourOpen(false);
  }, []);

  const goToStep = useCallback(
    (stepNumber) => {
      const idx = Math.max(0, Math.min(totalSteps - 1, stepNumber - 1));
      setCurrentStepIndex(idx);
      const targetStep = activeSteps[idx];
      if (targetStep) {
        const currentFull = location.pathname + location.search;
        if (currentFull !== targetStep.route) {
          navigate(targetStep.route);
        }
      }
    },
    [activeSteps, totalSteps, location.pathname, location.search, navigate]
  );

  const nextStep = useCallback(() => {
    if (currentStepIndex < totalSteps - 1) {
      goToStep(currentStepIndex + 2); // 1-indexed
    } else {
      exitTour();
    }
  }, [currentStepIndex, totalSteps, goToStep, exitTour]);

  const prevStep = useCallback(() => {
    if (currentStepIndex > 0) {
      goToStep(currentStepIndex); // 1-indexed
    }
  }, [currentStepIndex, goToStep]);

  // Global Keyboard Navigation (Escape, ArrowLeft, ArrowRight)
  useEffect(() => {
    if (!isTourOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        exitTour();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        nextStep();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        prevStep();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isTourOpen, nextStep, prevStep, exitTour]);

  const value = {
    isTourOpen,
    currentStepIndex,
    currentStep,
    totalSteps,
    activeSteps,
    startTour,
    exitTour,
    nextStep,
    prevStep,
    goToStep,
  };

  return <TourContext.Provider value={value}>{children}</TourContext.Provider>;
}

export function useTour() {
  const context = useContext(TourContext);
  if (!context) {
    throw new Error('useTour must be used within a TourProvider');
  }
  return context;
}
