import React from 'react';
import { Navigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Layout from './Layout';

export default function ProtectedRoute({ allowedRoles, children }) {
  const { user, role, isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <Layout>
        <div className="min-h-[60vh] flex flex-col items-center justify-center p-6 text-center">
          <div className="w-12 h-12 rounded-full border-4 border-teal-500/20 border-t-teal-600 animate-spin mb-4"></div>
          <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
            Verifying SkillSetuAI security credentials...
          </p>
        </div>
      </Layout>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && allowedRoles.length > 0) {
    const normalizedAllowed = allowedRoles.map((r) => r.toUpperCase());
    const userRole = (role || '').toUpperCase();

    if (!normalizedAllowed.includes(userRole) && userRole !== 'ADMIN') {
      return (
        <Layout>
          <div className="max-w-xl mx-auto my-16 p-8 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl text-center">
            <div className="w-16 h-16 rounded-2xl bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 flex items-center justify-center text-3xl mx-auto mb-4">
              🛡️
            </div>
            <span className="inline-block px-3 py-1 rounded-full text-xs font-mono font-bold bg-rose-100 dark:bg-rose-900/60 text-rose-700 dark:text-rose-300 border border-rose-300 dark:border-rose-800 mb-3">
              HTTP 403 FORBIDDEN
            </span>
            <h2 className="text-xl font-black text-slate-900 dark:text-white tracking-tight mb-2">
              Role Access Restricted
            </h2>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-6 leading-relaxed">
              Your account is registered as <strong className="text-slate-800 dark:text-slate-200 uppercase font-mono">{userRole || 'ANONYMOUS'}</strong>.
              This area requires one of the following authorized roles:{' '}
              <strong className="text-teal-700 dark:text-teal-400 font-mono">{normalizedAllowed.join(', ')}</strong>.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link
                to={
                  userRole === 'STUDENT'
                    ? '/student'
                    : userRole === 'EMPLOYER'
                    ? '/employer'
                    : userRole === 'INSTITUTE'
                    ? '/institute'
                    : userRole === 'GOVERNMENT'
                    ? '/government'
                    : '/'
                }
                className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold shadow-sm transition-all"
              >
                Go to My Dashboard
              </Link>
              <Link
                to="/"
                className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-bold transition-all"
              >
                Platform Home
              </Link>
            </div>
          </div>
        </Layout>
      );
    }
  }

  return children;
}
