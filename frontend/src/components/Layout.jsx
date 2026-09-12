import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { api } from '../services/api';
import { useTheme } from '../context/ThemeContext';
import { useTour } from '../context/TourContext';
import { useAuth } from '../context/AuthContext';

export default function Layout({ children }) {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const { startTour } = useTour();
  const { user, role, isAuthenticated, logout } = useAuth();
  const [health, setHealth] = useState({ status: 'connecting', demo_mode: true });
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer = null;

    const fetchHealth = (attempt = 1) => {
      api.getHealth()
        .then((res) => {
          if (!cancelled && res) {
            setHealth(res);
          }
        })
        .catch(() => {
          if (!cancelled) {
            if (attempt < 4) {
              timer = setTimeout(() => fetchHealth(attempt + 1), 3000);
            } else {
              setHealth({ status: 'offline', demo_mode: true });
            }
          }
        });
    };

    fetchHealth(1);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  // Global Cmd+K / Ctrl+K shortcut to open AI Copilot
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        window.location.href = '/student/copilot';
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Role-focused navigation items with clean separation
  const getNavLinksForRole = (userRole, isAuth) => {
    if (!isAuth) {
      return [
        { path: '/student', label: 'Student Passport', desc: 'Personal Skill Pathway' },
        { path: '/institute', label: 'Institutes', desc: 'Curriculum & Course Health' },
        { path: '/government', label: 'Government', desc: 'State & District Intelligence' },
        { path: '/employer', label: 'Employer Hub', desc: 'Signal Validation' },
        { path: '/student/copilot', label: 'AI Copilot', desc: 'Evidence-Based Q&A' },
      ];
    }
    switch (userRole) {
      case 'STUDENT':
        return [
          { path: '/student', label: 'Student Passport', desc: 'Personal Skill Pathway & Roadmap' },
          { path: '/student/profile', label: 'Edit Passport', desc: 'Manage Skills, Projects & Certs' },
          { path: '/student/copilot', label: 'AI Career Copilot', desc: 'Evidence-Based Q&A & Guidance' },
        ];
      case 'EMPLOYEE':
        return [
          { path: '/employee/profile', label: 'Career Passport', desc: 'Experience, Skills & Transition Target' },
          { path: '/student/copilot?role=employee', label: 'AI Career Copilot', desc: 'Transition Insights & Guidance' },
        ];
      case 'EMPLOYER':
        return [
          { path: '/employer', label: 'Employer Hub', desc: 'Post Demands & Validate Signals' },
          { path: '/student/copilot', label: 'AI Copilot', desc: 'Talent Market Insights' },
        ];
      case 'INSTITUTE':
        return [
          { path: '/institute', label: 'Institute Portal', desc: 'Curriculum Modernization & Course Health' },
          { path: '/student/copilot', label: 'AI Copilot', desc: 'Syllabus & NSQF Insights' },
        ];
      case 'GOVERNMENT':
        return [
          { path: '/government', label: 'Government Command', desc: 'State & District Intelligence' },
          { path: '/student/copilot', label: 'AI Copilot', desc: 'Policy & Workforce Guidance' },
        ];
      case 'ADMIN':
        return [
          { path: '/admin', label: 'Admin Board', desc: 'Assessment & Moderation Center' },
          { path: '/government', label: 'Government', desc: 'State Intelligence' },
          { path: '/institute', label: 'Institutes', desc: 'Curriculum Modernization' },
          { path: '/employer', label: 'Employer Hub', desc: 'Signal Validation' },
          { path: '/student', label: 'Student Registry', desc: 'Personal Skill Pathways' },
          { path: '/student/copilot', label: 'AI Copilot', desc: 'Evidence-Based Q&A' },
        ];
      default:
        return [
          { path: '/student', label: 'Student Passport', desc: 'Personal Skill Pathway' },
          { path: '/institute', label: 'Institutes', desc: 'Curriculum & Course Health' },
          { path: '/government', label: 'Government', desc: 'State & District Intelligence' },
          { path: '/employer', label: 'Employer Hub', desc: 'Signal Validation' },
        ];
    }
  };

  const getFooterLinksForRole = (userRole, isAuth) => {
    if (!isAuth) {
      return {
        col2Title: 'Stakeholder Portals',
        col2Links: [
          { path: '/login', label: 'Sign In to Portal' },
          { path: '/register', label: 'Register New Account' },
          { path: '/student', label: 'Candidate Passport Preview' },
          { path: '/institute', label: 'Institute Portal Preview' },
        ],
        col3Title: 'Intelligence Tools',
        col3Links: [
          { path: '/student/copilot', label: 'AI Intelligence Copilot' },
          { path: '/login', label: 'District Workforce Plans (Sign in)' },
        ],
      };
    }
    switch (userRole) {
      case 'STUDENT':
        return {
          col2Title: 'Student Console',
          col2Links: [
            { path: '/student', label: 'My Skill Passport' },
            { path: '/student?tab=assessment', label: 'Diagnostic Skill Assessment' },
            { path: '/student?tab=recommendations', label: 'Target Career Recommendations' },
            { path: '/student?tab=roadmap', label: 'Learning Roadmap' },
          ],
          col3Title: 'Student Intelligence',
          col3Links: [
            { path: '/student/copilot?role=student', label: 'AI Career Copilot' },
            { path: '/student?tab=signals', label: 'Industry & Technology Alerts' },
            { path: '/student?tab=forecast', label: 'Future Rising Skills' },
          ],
        };
      case 'EMPLOYEE':
        return {
          col2Title: 'Career Console',
          col2Links: [
            { path: '/employee/profile', label: 'My Career Passport' },
            { path: '/student/copilot?role=employee', label: 'Career Transition Copilot' },
          ],
          col3Title: 'Workforce Intelligence',
          col3Links: [
            { path: '/student/copilot?role=employee', label: 'Skill Intelligence' },
            { path: '/employee/profile', label: 'Industry & Technology Alerts' },
            { path: '/student/copilot?role=employee&q=What+is+the+12-to-24+month+skill+forecast+for+emerging+roles+in+Maharashtra%3F', label: 'Future Skill Forecasts' },
          ],
        };
      case 'EMPLOYER':
        return {
          col2Title: 'Employer Console',
          col2Links: [
            { path: '/employer', label: 'Employer Hub Overview' },
            { path: '/employer', label: 'Post Hiring Demands' },
            { path: '/employer', label: 'Validate AI Labor Signals' },
            { path: '/employer', label: 'Difficult-to-Hire Shortages' },
          ],
          col3Title: 'Workforce Intelligence',
          col3Links: [
            { path: '/student/copilot?role=employer', label: 'Talent Market Copilot' },
            { path: '/employer', label: 'Regional Candidate Availability' },
          ],
        };
      case 'INSTITUTE':
        return {
          col2Title: 'Institute Console',
          col2Links: [
            { path: '/institute', label: 'Accredited Course Catalog' },
            { path: '/institute', label: 'Course Health & Placement Conversion' },
            { path: '/institute', label: 'Curriculum Modernization Blueprints' },
            { path: '/institute', label: 'Lab Equipment Budgeting' },
          ],
          col3Title: 'Academic Intelligence',
          col3Links: [
            { path: '/student/copilot?role=institute', label: 'Academic & NSQF Copilot' },
            { path: '/institute', label: 'Faculty Upskilling Programs' },
          ],
        };
      case 'GOVERNMENT':
        return {
          col2Title: 'State Command Console',
          col2Links: [
            { path: '/government', label: 'Maharashtra Macro Overview' },
            { path: '/government', label: '36-District Spatial Heatmap' },
            { path: '/government', label: 'Policy What-If Simulator' },
            { path: '/government/district/Pune', label: 'District Training Micro-Plans' },
          ],
          col3Title: 'State Intelligence',
          col3Links: [
            { path: '/student/copilot?role=government', label: 'Policy Decision-Support Copilot' },
            { path: '/government', label: 'Welfare Schemes & Apprenticeships' },
          ],
        };
      case 'ADMIN':
        return {
          col2Title: 'Governance Console',
          col2Links: [
            { path: '/admin', label: 'Admin Board & Executive Overview' },
            { path: '/admin', label: 'Student Assessment Registry' },
            { path: '/admin', label: 'Employer Demands Moderation' },
            { path: '/admin', label: 'Industry Signals Ingestion' },
          ],
          col3Title: 'Cross-Domain Tools',
          col3Links: [
            { path: '/government', label: 'Government State Command' },
            { path: '/institute', label: 'Institute Modernization' },
            { path: '/employer', label: 'Employer Validation Hub' },
            { path: '/student/copilot', label: 'Platform AI Copilot' },
          ],
        };
      default:
        return {
          col2Title: 'Stakeholder Portals',
          col2Links: [
            { path: '/student', label: 'Candidate Skill Passport' },
            { path: '/institute', label: 'Training Institutes & ITIs' },
            { path: '/government', label: 'State Government Overview' },
            { path: '/employer', label: 'Employer Validation Hub' },
          ],
          col3Title: 'Intelligence Tools',
          col3Links: [
            { path: '/student/copilot', label: 'Evidence-Based AI Copilot' },
            { path: '/login', label: 'District Workforce Plans' },
          ],
        };
    }
  };

  const navLinks = getNavLinksForRole(role, isAuthenticated);
  const footerConfig = getFooterLinksForRole(role, isAuthenticated);

  const isActive = (path) => {
    if (path.includes('copilot')) return location.pathname.includes('copilot');
    if (path === '/student') return location.pathname === '/student';
    if (path === '/admin') return location.pathname === '/admin';
    return location.pathname === path || (path !== '/' && location.pathname.startsWith(path) && path !== '/student');
  };

  const getRoleBadgeStyle = (userRole) => {
    switch (userRole) {
      case 'ADMIN':
        return 'bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border-rose-300 dark:border-rose-800';
      case 'STUDENT':
        return 'bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border-blue-300 dark:border-blue-800';
      case 'EMPLOYEE':
        return 'bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-800';
      case 'EMPLOYER':
        return 'bg-purple-100 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 border-purple-300 dark:border-purple-800';
      case 'INSTITUTE':
        return 'bg-teal-100 dark:bg-teal-950/60 text-teal-700 dark:text-teal-400 border-teal-300 dark:border-teal-800';
      case 'GOVERNMENT':
        return 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800';
      default:
        return 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700';
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col font-sans selection:bg-teal-500 selection:text-white transition-colors duration-200">
      {/* Main Header */}
      <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 sticky top-0 z-40 shadow-xs transition-colors duration-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-14">
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center gap-2.5 group">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-slate-900 to-teal-700 dark:from-teal-800 dark:to-slate-800 flex items-center justify-center text-white font-bold text-lg shadow-sm group-hover:scale-105 transition-transform">
                S
              </div>
              <div>
                <span className="font-bold text-lg tracking-tight text-slate-900 dark:text-white flex items-center gap-1.5">
                  SkillSetuAI
                  <span className="text-[10px] uppercase px-1.5 py-0.5 bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-400 font-semibold rounded border border-teal-200 dark:border-teal-800">
                    Maha-Intel
                  </span>
                </span>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-tight hidden sm:block">Labour-Market Intelligence & Curriculum Alignment</p>
              </div>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden lg:flex items-center gap-0.5">
            {navLinks.map((link) => (
              <Link
                key={link.path}
                to={link.path}
                className={`px-3 py-1.5 rounded-lg text-[13px] font-medium transition-colors ${
                  isActive(link.path)
                    ? 'bg-slate-900 dark:bg-teal-700 text-white'
                    : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                {link.label}
              </Link>
            ))}
          </nav>

          {/* Right actions */}
          <div className="flex items-center gap-2">
            {health.status === 'connecting' ? (
              <span className="hidden xl:inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-amber-500/15 dark:bg-amber-500/20 text-amber-800 dark:text-amber-300 border border-amber-500/30 text-[11px] font-mono font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                <span>WARMING UP</span>
              </span>
            ) : health.status === 'offline' ? (
              <span className="hidden xl:inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-rose-500/15 dark:bg-rose-500/20 text-rose-800 dark:text-rose-300 border border-rose-500/30 text-[11px] font-mono font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                <span>OFFLINE CACHE</span>
              </span>
            ) : (
              <span className="hidden xl:inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/15 dark:bg-emerald-500/20 text-emerald-800 dark:text-emerald-300 border border-emerald-500/30 text-[11px] font-mono font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span>{health.demo_mode ? 'DEMO OVERLAY' : 'LIVE DB'}</span>
              </span>
            )}

            <button
              onClick={startTour}
              className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-700 hover:to-emerald-700 text-white text-xs font-bold shadow-xs transition-all cursor-pointer"
            >
              <span>✨</span>
              <span>Tour</span>
            </button>

            <button
              onClick={toggleTheme}
              aria-label="Toggle Light and Dark Theme"
              className="p-1.5 sm:p-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors text-xs"
              title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} Mode`}
            >
              {theme === 'light' ? '🌙' : '☀️'}
            </button>

            {/* Auth Session Profile Badge or Login/Register CTAs */}
            {isAuthenticated ? (
              <div className="flex items-center gap-2">
                <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-xs">
                  <span className="font-semibold text-slate-800 dark:text-slate-200 max-w-[100px] truncate">
                    {user?.full_name?.split(' ')[0] || user?.email?.split('@')[0]}
                  </span>
                  <span className={`text-[10px] font-mono font-bold uppercase px-1.5 py-0.2 rounded border ${getRoleBadgeStyle(role)}`}>
                    {role}
                  </span>
                </div>
                <button
                  onClick={logout}
                  className="px-2.5 py-1.5 bg-slate-200 hover:bg-rose-100 hover:text-rose-700 dark:bg-slate-800 dark:hover:bg-rose-950/60 dark:hover:text-rose-300 text-slate-700 dark:text-slate-300 rounded-lg text-xs font-bold transition-colors cursor-pointer"
                  title="Sign Out"
                >
                  Logout
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-1.5">
                <Link
                  to="/login"
                  className="px-3 py-1.5 bg-slate-900 dark:bg-teal-600 hover:bg-slate-800 dark:hover:bg-teal-700 text-white rounded-lg text-xs font-bold shadow-xs transition-colors"
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  className="hidden sm:inline-block px-2.5 py-1.5 border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg text-xs font-bold transition-colors"
                >
                  Register
                </Link>
              </div>
            )}

            {/* Mobile hamburger */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
              )}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Dropdown */}
        {mobileMenuOpen && (
          <div className="lg:hidden border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 animate-fade-in shadow-md">
            <nav className="max-w-7xl mx-auto px-4 py-3 space-y-1">
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100 dark:border-slate-800">
                <span className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Pipeline Status</span>
                <span className="px-2 py-0.5 rounded bg-amber-500/15 dark:bg-amber-500/20 text-amber-800 dark:text-amber-300 border border-amber-500/30 text-[10px] font-mono font-semibold">
                  {health.demo_mode ? 'DEMO DATA ACTIVE' : 'LIVE DB CONNECTED'}
                </span>
              </div>
              <button
                onClick={() => { setMobileMenuOpen(false); startTour(); }}
                className="w-full text-left px-3 py-2.5 rounded-lg bg-teal-50 dark:bg-teal-950/60 text-teal-800 dark:text-teal-300 font-bold text-sm flex items-center gap-2 border border-teal-200 dark:border-teal-800 mb-2 cursor-pointer"
              >
                <span>✨</span>
                <span>Launch SIH Demo Tour</span>
              </button>
              {navLinks.map((link) => (
                <Link
                  key={link.path}
                  to={link.path}
                  className={`block px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive(link.path)
                      ? 'bg-slate-900 dark:bg-teal-700 text-white'
                      : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  <span className="font-semibold">{link.label}</span>
                  <span className="text-xs text-slate-500 dark:text-slate-400 ml-2">{link.desc}</span>
                </Link>
              ))}
              <div className="pt-2 border-t border-slate-100 dark:border-slate-800 sm:hidden">
                <Link
                  to="/student/copilot"
                  className="flex items-center justify-center gap-1.5 w-full px-3 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold rounded-lg shadow-sm"
                >
                  <span>Ask AI Copilot</span>
                </Link>
              </div>
            </nav>
          </div>
        )}
      </header>

      {/* Body Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </main>

      {/* Professional Structured Footer */}
      <footer className="bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 py-10 mt-auto text-xs text-slate-500 dark:text-slate-400 transition-colors duration-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mb-8">
            {/* Col 1: Platform & Identity */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded bg-gradient-to-tr from-slate-900 to-teal-700 dark:from-teal-800 dark:to-slate-800 flex items-center justify-center text-white font-bold text-sm shadow-xs">
                  S
                </div>
                <span className="font-bold text-sm text-slate-900 dark:text-white">
                  SkillSetuAI Maha-Intel
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                Labour-Market Intelligence & Curriculum-Alignment Platform. Connecting Maharashtra's state agencies, vocational institutes, candidates, and industry partners.
              </p>
              <div className="inline-flex items-center gap-1.5 text-[11px] font-mono text-teal-700 dark:text-teal-400 bg-teal-50 dark:bg-teal-950/60 px-2 py-0.5 rounded border border-teal-200 dark:border-teal-800">
                <span className="w-1.5 h-1.5 rounded-full bg-teal-500"></span>
                <span>Active Intelligence Pipeline</span>
              </div>
            </div>

            {/* Col 2: Role-Specific Primary Console */}
            <div>
              <h4 className="font-bold text-slate-900 dark:text-white text-xs uppercase tracking-wider mb-3">
                {footerConfig.col2Title}
              </h4>
              <ul className="space-y-2 text-xs">
                {footerConfig.col2Links.map((l, idx) => (
                  <li key={idx}>
                    <Link to={l.path} className="hover:text-teal-600 dark:hover:text-teal-400 transition-colors">
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Col 3: Role-Specific Intelligence Tools */}
            <div>
              <h4 className="font-bold text-slate-900 dark:text-white text-xs uppercase tracking-wider mb-3">
                {footerConfig.col3Title}
              </h4>
              <ul className="space-y-2 text-xs">
                {footerConfig.col3Links.map((l, idx) => (
                  <li key={idx}>
                    <Link to={l.path} className="hover:text-teal-600 dark:hover:text-teal-400 transition-colors">
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Col 4: State Alignment */}
            <div>
              <h4 className="font-bold text-slate-900 dark:text-white text-xs uppercase tracking-wider mb-3">
                Governance & Alignment
              </h4>
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-2 leading-relaxed">
                Aligned with Dept. of Skills, Employment, Entrepreneurship & Innovation, Government of Maharashtra.
              </p>
              <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-800 text-[11px] text-slate-600 dark:text-slate-400 space-y-1">
                <div className="flex justify-between">
                  <span>Data Engine:</span>
                  <span className="font-mono text-slate-800 dark:text-slate-200">FastAPI + Async</span>
                </div>
                <div className="flex justify-between">
                  <span>System Status:</span>
                  <span className="font-semibold text-emerald-600 dark:text-emerald-400">Operational</span>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Bar */}
          <div className="pt-6 border-t border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px] text-slate-400 dark:text-slate-500">
            <div>
              © {new Date().getFullYear()} SkillSetuAI. Continuous evidence-based feedback loop: Labour Market → Gaps → Curriculum → Validation.
            </div>
            <div className="flex items-center gap-4">
              <span>District Micro-Plans</span>
              <span>•</span>
              <span>Predictive Horizons</span>
              <span>•</span>
              <span>Human-in-the-Loop</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
