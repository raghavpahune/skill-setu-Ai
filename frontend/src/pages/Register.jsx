import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';

const ROLES = [
  { id: 'STUDENT', label: 'Student / Candidate', desc: 'Skill Passport, Gaps & AI Copilot', icon: '🎓' },
  { id: 'EMPLOYEE', label: 'Working Professional', desc: 'Career Passport, Skills & Upskilling', icon: '💼' },
  { id: 'EMPLOYER', label: 'Employer / Enterprise', desc: 'Demand Reporting & Signal Validation', icon: '🏢' },
  { id: 'INSTITUTE', label: 'Training Institute / ITI', desc: 'Curriculum & Placement Health', icon: '🏛️' },
  { id: 'GOVERNMENT', label: 'Policy / Government', desc: 'State & District Intelligence & Plans', icon: '🇮🇳' },
];

const DISTRICTS = [
  'Pune', 'Mumbai City', 'Mumbai Suburban', 'Thane', 'Nagpur', 'Nashik',
  'Chhatrapati Sambhajinagar (Aurangabad)', 'Kolhapur', 'Solapur', 'Amravati',
  'Nanded', 'Satara', 'Raigad', 'Palghar', 'Ahmednagar'
];

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    confirm_password: '',
    role: 'STUDENT',
    district: 'Pune',
    organization_id: '',
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (field, val) => {
    setForm((prev) => ({ ...prev, [field]: val }));
    setError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!form.full_name.trim()) {
      setError('Please enter your full name.');
      return;
    }
    if (!form.email.trim()) {
      setError('Please enter a valid email address.');
      return;
    }
    if (form.password.length < 6) {
      setError('Password must be at least 6 characters in length.');
      return;
    }
    if (form.password !== form.confirm_password) {
      setError('Passwords do not match. Please re-enter.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const user = await register({
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        password: form.password,
        role: form.role,
        district: form.district,
        organization_id: form.organization_id.trim() || undefined,
      });

      const role = (user.role || '').toUpperCase();
      if (role === 'STUDENT') navigate('/student/profile');
      else if (role === 'EMPLOYEE') navigate('/employee/profile');
      else if (role === 'EMPLOYER') navigate('/employer');
      else if (role === 'INSTITUTE') navigate('/institute');
      else if (role === 'GOVERNMENT') navigate('/government');
      else navigate('/');
    } catch (err) {
      setError(err.message || 'Registration failed. Please check inputs.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-xl mx-auto my-10 px-4">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl p-6 sm:p-8">
          {/* Header */}
          <div className="text-center mb-6">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-slate-900 to-teal-700 dark:from-teal-800 dark:to-slate-800 flex items-center justify-center text-white font-black text-xl shadow-md mx-auto mb-3">
              S
            </div>
            <h1 className="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
              Create Your SkillSetuAI Account
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Select your role to access customized labour-market intelligence and tools
            </p>
          </div>

          {/* Error Alert */}
          {error && (
            <div className="p-3.5 mb-5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-rose-800 dark:text-rose-300 text-xs flex items-center gap-2.5 shadow-2xs">
              <span className="text-base shrink-0">⚠️</span>
              <span className="font-semibold">{error}</span>
            </div>
          )}

          {/* Registration Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Role Selection */}
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-2">
                Select Your Role *
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {ROLES.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => handleChange('role', r.id)}
                    className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                      form.role === r.id
                        ? 'border-teal-500 bg-teal-50/60 dark:bg-teal-950/40 ring-1 ring-teal-500'
                        : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-lg">{r.icon}</span>
                      <span className="text-xs font-bold text-slate-900 dark:text-white">{r.label}</span>
                    </div>
                    <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-tight">{r.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Full Name & Email */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Full Name *
                </label>
                <input
                  type="text"
                  required
                  value={form.full_name}
                  onChange={(e) => handleChange('full_name', e.target.value)}
                  placeholder="e.g. Priya Deshmukh"
                  className="w-full px-3.5 py-2.5 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:ring-2 focus:ring-teal-500 focus:outline-none text-slate-900 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Email Address *
                </label>
                <input
                  type="email"
                  required
                  value={form.email}
                  onChange={(e) => handleChange('email', e.target.value)}
                  placeholder="priya@college.edu"
                  className="w-full px-3.5 py-2.5 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:ring-2 focus:ring-teal-500 focus:outline-none text-slate-900 dark:text-white"
                />
              </div>
            </div>

            {/* District & Organization */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  District (Maharashtra)
                </label>
                <select
                  value={form.district}
                  onChange={(e) => handleChange('district', e.target.value)}
                  className="w-full px-3.5 py-2.5 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:ring-2 focus:ring-teal-500 focus:outline-none text-slate-900 dark:text-white cursor-pointer"
                >
                  {DISTRICTS.map((d) => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  {form.role === 'STUDENT' ? 'College / ITI Name' : form.role === 'EMPLOYER' ? 'Company Name' : 'Organization Unit'}
                </label>
                <input
                  type="text"
                  value={form.organization_id}
                  onChange={(e) => handleChange('organization_id', e.target.value)}
                  placeholder="Optional identifier"
                  className="w-full px-3.5 py-2.5 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:ring-2 focus:ring-teal-500 focus:outline-none text-slate-900 dark:text-white"
                />
              </div>
            </div>

            {/* Password & Confirm Password */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Password (min 6 chars) *
                </label>
                <input
                  type="password"
                  required
                  value={form.password}
                  onChange={(e) => handleChange('password', e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-3.5 py-2.5 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:ring-2 focus:ring-teal-500 focus:outline-none text-slate-900 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Confirm Password *
                </label>
                <input
                  type="password"
                  required
                  value={form.confirm_password}
                  onChange={(e) => handleChange('confirm_password', e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-3.5 py-2.5 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:ring-2 focus:ring-teal-500 focus:outline-none text-slate-900 dark:text-white"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 mt-2 bg-gradient-to-r from-slate-900 to-teal-700 dark:from-teal-600 dark:to-teal-700 hover:opacity-95 text-white text-xs font-bold rounded-xl shadow-md cursor-pointer transition-all disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin"></div>
                  Creating Account...
                </>
              ) : (
                'Complete Registration →'
              )}
            </button>
          </form>

          {/* Footer Link */}
          <div className="mt-6 text-center text-xs text-slate-500 dark:text-slate-400">
            Already have an account?{' '}
            <Link to="/login" className="font-bold text-teal-600 dark:text-teal-400 hover:underline">
              Sign In Here
            </Link>
          </div>
        </div>
      </div>
    </Layout>
  );
}
