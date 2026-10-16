'use client';

import { useState } from 'react';
import type { JSX } from 'react';
import { useRouter } from 'next/navigation';
import clsx from 'clsx';
import { getBackendHttpUrl } from '@/lib/api';

interface RegistrationData {
  email: string;
  name: string;
  camera_name: string;
}

export default function RegistrationForm(): Readonly<JSX.Element> {
  const router = useRouter();
  const [formData, setFormData] = useState<RegistrationData>({
    email: '',
    name: '',
    camera_name: 'Camera_1',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.currentTarget;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${getBackendHttpUrl()}/users/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error('Failed to register');
      }

      const user = await response.json();
      setSuccess(true);

      // Store email in localStorage for auto-fill when starting camera
      if (typeof globalThis !== 'undefined' && globalThis.localStorage) {
        globalThis.localStorage.setItem('userEmail', formData.email);
        globalThis.localStorage.setItem('userName', formData.name);
      }

      // Redirect to dashboard after 2 seconds
      setTimeout(() => {
        router.push('/');
      }, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-card p-8 space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold text-white">Register</h1>
        <p className="text-sm text-gray-400">
          Create your profile to receive threat alerts
        </p>
      </div>

      {success && (
        <div className="p-4 bg-emerald-500/20 border border-emerald-500/30 rounded-lg">
          <p className="text-emerald-300 text-sm">
            ✓ Registration successful! Redirecting to dashboard...
          </p>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-500/20 border border-red-500/30 rounded-lg">
          <p className="text-red-300 text-sm">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-1">
            Email Address
          </label>
          <input
            id="email"
            name="email"
            type="email"
            required
            value={formData.email}
            onChange={handleChange}
            placeholder="your-email@example.com"
            className="w-full px-4 py-2 bg-slate-900/50 border border-slate-700 text-white placeholder-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-cyan-500"
          />
          <p className="text-xs text-gray-500 mt-1">
            You&apos;ll receive threat alerts at this email
          </p>
        </div>

        <div>
          <label htmlFor="name" className="block text-sm font-medium text-gray-300 mb-1">
            Your Name
          </label>
          <input
            id="name"
            name="name"
            type="text"
            required
            value={formData.name}
            onChange={handleChange}
            placeholder="John Doe"
            className="w-full px-4 py-2 bg-slate-900/50 border border-slate-700 text-white placeholder-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-cyan-500"
          />
        </div>

        <div>
          <label htmlFor="camera_name" className="block text-sm font-medium text-gray-300 mb-1">
            Camera Name
          </label>
          <input
            id="camera_name"
            name="camera_name"
            type="text"
            value={formData.camera_name}
            onChange={handleChange}
            placeholder="Camera_1"
            className="w-full px-4 py-2 bg-slate-900/50 border border-slate-700 text-white placeholder-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-cyan-500"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className={clsx(
            'w-full py-2 px-4 rounded-lg font-medium transition-all duration-200',
            'bg-cyan-600 hover:bg-cyan-700 text-white',
            'focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-slate-900',
            loading && 'opacity-50 cursor-not-allowed'
          )}
        >
          {loading ? 'Registering...' : 'Register'}
        </button>
      </form>

      <div className="pt-4 border-t border-slate-700">
        <p className="text-sm text-gray-400">
          Already registered?{' '}
          <a href="/" className="text-cyan-400 hover:text-cyan-300 font-medium">
            Go to Dashboard
          </a>
        </p>
      </div>
    </div>
  );
}
