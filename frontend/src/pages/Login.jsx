import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';

const DEMO_USERS = [
  { label: 'Student', email: 'student@skillsetu.gov.in', pass: 'Password@123', role: 'STUDENT', icon: '🎓' },
  { label: 'Employee', email: 'employee@skillsetu.gov.in', pass: 'Password@123', role: 'EMPLOYEE', icon: '💼' },
  { label: 'Employer', email: 'employer@skillsetu.gov.in', pass: 'Password@123', role: 'EMPLOYER', icon: '🏢' },
  { label: 'Institute', email: 'institute@skillsetu.gov.in', pass: 'Password@123', role: 'INSTITUTE', icon: '🏛️' },
  { label: 'Government', email: 'government@skillsetu.gov.in', pass: 'Password@123', role: 'GOVERNMENT', icon: '🇮🇳' },
  { label: 'Administrator', email: 'admin@skillsetu.gov.in', pass: 'AdminPass@2026', role: 'ADMIN', icon: '⚙️' },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || '/';

  const [email, setEmail] = useState('student@skillsetu.gov.in');
  const [password, setPassword] = useState('Password@123');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please provide both email and password.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const user = await login(email, password);
      const role = (user?.role || '').toUpperCase();
      const roleDefaultRoute =
        {
          STUDENT: '/student',
          EMPLOYEE: '/employee/profile',
          EMPLOYER: '/employer',
          INSTITUTE: '/institute',
          GOVERNMENT: '/government',
          ADMIN: '/admin',
        }[role] || '/';

      // Route directly to the authenticated role's primary command center
      if (from === '/' || from === '/login' || !from) {
        navigate(roleDefaultRoute, { replace: true });
      } else {
        navigate(from, { replace: true });
      }
    } catch (err) {
      setError(err.message || 'Authentication failed. Please verify your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickFill = (demoUser) => {
    setEmail(demoUser.email);
    setPassword(demoUser.pass);
    setError(null);
  };

  return (
    <Layout>
      <div className="max-w-md mx-auto my-12 px-4">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl p-6 sm:p-8">
          {/* Header */}
          <div className="text-center mb-6">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-slate-900 to-teal-700 dark:from-teal-800 dark:to-slate-800 flex items-center justify-center text-white font-black text-xl shadow-md mx-auto mb-3">
              S
            </div>
            <h1 className="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
              Sign In to SkillSetuAI
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Labour-Market Intelligence & Curriculum Alignment Platform
            </p>
          </div>

          {/* Error Alert */}
          {error && (
            <div className="p-3.5 mb-5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-rose-800 dark:text-rose-300 text-xs flex items-center gap-2.5 shadow-2xs">
              <span className="text-base shrink-0">⚠️</span>
              <span className="font-semibold">{error}</span>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                Email Address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@organization.gov.in"
                className="w-full px-3.5 py-2.5 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:ring-2 focus:ring-teal-500 focus:outline-none text-slate-900 dark:text-white"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300">
                  Password
                </label>
              </div>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-3.5 py-2.5 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:ring-2 focus:ring-teal-500 focus:outline-none text-slate-900 dark:text-white"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-slate-900 to-teal-700 dark:from-teal-600 dark:to-teal-700 hover:opacity-95 text-white text-xs font-bold rounded-xl shadow-md cursor-pointer transition-all disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin"></div>
                  Authenticating...
                </>
              ) : (
                'Sign In →'
              )}
            </button>
          </form>

          {/* Quick Demo Fill Buttons */}
          <div className="mt-6 pt-5 border-t border-slate-100 dark:border-slate-800">
            <p className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2.5 text-center">
              Quick Demo Role Sign-In
            </p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {DEMO_USERS.map((d) => (
                <button
                  key={d.role}
                  type="button"
                  onClick={() => handleQuickFill(d)}
                  className={`p-2 rounded-lg border text-left text-[11px] font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${
                    email === d.email
                      ? 'border-teal-500 bg-teal-50 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300'
                      : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 text-slate-700 dark:text-slate-300'
                  }`}
                >
                  <span>{d.icon}</span>
                  <span className="truncate">{d.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Footer Link */}
          <div className="mt-6 text-center text-xs text-slate-500 dark:text-slate-400">
            Don't have an account?{' '}
            <Link to="/register" className="font-bold text-teal-600 dark:text-teal-400 hover:underline">
              Create an Account
            </Link>
          </div>
        </div>
      </div>
    </Layout>
  );
}
