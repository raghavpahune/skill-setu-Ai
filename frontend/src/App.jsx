import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { TourProvider } from './context/TourContext';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import DemoTour from './components/DemoTour';
import AdminErrorBoundary from './components/AdminErrorBoundary';
import Layout from './components/Layout';

// Eagerly loaded initial entry routes for instant first paint
import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';

// Lazy-loaded heavy dashboard & analytics routes (Phase 35)
const GovernmentDashboard = lazy(() => import('./pages/GovernmentDashboard'));
const DistrictPlan = lazy(() => import('./pages/DistrictPlan'));
const InstituteDashboard = lazy(() => import('./pages/InstituteDashboard'));
const StudentDashboard = lazy(() => import('./pages/StudentDashboard'));
const CopilotPage = lazy(() => import('./pages/CopilotPage'));
const EmployerDashboard = lazy(() => import('./pages/EmployerDashboard'));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));
const CurriculumHub = lazy(() => import('./pages/CurriculumHub'));
const StudentProfile = lazy(() => import('./pages/StudentProfile'));
const EmployeeProfile = lazy(() => import('./pages/EmployeeProfile'));

function RouteLoadingFallback() {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col items-center justify-center p-6 transition-colors">
      <div className="relative w-16 h-16 flex items-center justify-center">
        <div className="absolute inset-0 rounded-full bg-teal-500/20 dark:bg-teal-400/20 blur-xl animate-pulse" />
        <div className="w-12 h-12 rounded-full border-3 border-slate-200 dark:border-slate-800 border-t-teal-600 dark:border-t-teal-400 animate-spin" />
        <div className="absolute w-2 h-2 rounded-full bg-teal-600 dark:bg-teal-400" />
      </div>
      <p className="mt-4 text-xs font-semibold text-slate-500 dark:text-slate-400 tracking-wide animate-pulse">
        Loading module...
      </p>
    </div>
  );
}

function NotFound() {
  return (
    <Layout>
      <div className="py-20 text-center">
        <p className="text-6xl font-black text-slate-300 dark:text-slate-700">404</p>
        <h1 className="text-xl font-bold text-slate-900 dark:text-white mt-4">Page Not Found</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">The requested route does not exist in SkillSetuAI.</p>
        <Link to="/" className="inline-block mt-6 px-5 py-2 bg-slate-900 dark:bg-teal-600 text-white text-sm font-semibold rounded-lg hover:bg-slate-800 dark:hover:bg-teal-700 transition-colors">
          Return to Home
        </Link>
      </div>
    </Layout>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <TourProvider>
            <DemoTour />
            <Suspense fallback={<RouteLoadingFallback />}>
              <Routes>
                <Route path="/" element={<Landing />} />
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route
                  path="/government"
                  element={
                    <ProtectedRoute allowedRoles={['GOVERNMENT', 'ADMIN']}>
                      <GovernmentDashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/government/district/:name"
                  element={
                    <ProtectedRoute allowedRoles={['GOVERNMENT', 'ADMIN']}>
                      <DistrictPlan />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/institute"
                  element={
                    <ProtectedRoute allowedRoles={['INSTITUTE', 'ADMIN']}>
                      <InstituteDashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/student"
                  element={
                    <ProtectedRoute allowedRoles={['STUDENT', 'ADMIN']}>
                      <StudentDashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/student/profile"
                  element={
                    <ProtectedRoute allowedRoles={['STUDENT', 'ADMIN']}>
                      <StudentProfile />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/employee/profile"
                  element={
                    <ProtectedRoute allowedRoles={['EMPLOYEE', 'EMPLOYER', 'ADMIN']}>
                      <EmployeeProfile />
                    </ProtectedRoute>
                  }
                />
                <Route path="/copilot" element={<CopilotPage />} />
                <Route path="/student/copilot" element={<CopilotPage roleOverride="student" />} />
                <Route path="/employer/copilot" element={<CopilotPage roleOverride="employer" />} />
                <Route path="/institute/copilot" element={<CopilotPage roleOverride="institute" />} />
                <Route path="/government/copilot" element={<CopilotPage roleOverride="government" />} />
                <Route path="/admin/copilot" element={<CopilotPage roleOverride="admin" />} />
                <Route
                  path="/employer"
                  element={
                    <ProtectedRoute allowedRoles={['EMPLOYER', 'ADMIN']}>
                      <EmployerDashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/curriculum"
                  element={
                    <ProtectedRoute allowedRoles={['INSTITUTE', 'GOVERNMENT', 'ADMIN']}>
                      <CurriculumHub />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/admin"
                  element={
                    <ProtectedRoute allowedRoles={['ADMIN']}>
                      <AdminErrorBoundary>
                        <AdminDashboard />
                      </AdminErrorBoundary>
                    </ProtectedRoute>
                  }
                />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </TourProvider>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}

