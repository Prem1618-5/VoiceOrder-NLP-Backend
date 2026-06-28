import { useState, type FormEvent } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/lib/api';
import GradientBar from '@/components/ui/GradientBar';

export default function Auth() {
  const location = useLocation();
  const isRegister = location.pathname === '/register';
  const navigate = useNavigate();
  const { login, register } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [registerSuccess, setRegisterSuccess] = useState(false);

  const demoEmail = import.meta.env.VITE_DEMO_EMAIL;
  const demoPassword = import.meta.env.VITE_DEMO_PASSWORD;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      if (isRegister) {
        await register(email, password);
        setRegisterSuccess(true);
        // Auto-login after register
        await login(email, password);
        navigate('/');
      } else {
        await login(email, password);
        navigate('/');
      }
    } catch (err) {
      if (err instanceof ApiError) {
        switch (err.status) {
          case 401:
            setError('Incorrect email or password');
            break;
          case 409:
            setError('Email already registered');
            break;
          case 429:
            setError('Too many attempts — wait 60s');
            break;
          default:
            setError(err.detail);
        }
      } else {
        setError('An unexpected error occurred');
      }
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDemoLogin() {
    if (!demoEmail || !demoPassword) return;
    setEmail(demoEmail);
    setPassword(demoPassword);
    setError(null);
    setIsLoading(true);
    try {
      await login(demoEmail, demoPassword);
      navigate('/');
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Demo login failed');
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6"
         style={{
           background: 'linear-gradient(135deg, #FFD6E0 0%, #FFE4E4 25%, #DAE8F5 65%, #D0F5E5 100%)',
         }}>
      <div className="w-full max-w-[400px] glass-card-high p-8">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <span className="text-2xl">▌▌</span>
            <span className="text-xl font-bold text-[#111827]">VoiceOrder NLP</span>
          </div>
        </div>

        {registerSuccess && (
          <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700">
            Account created successfully! Logging you in...
          </div>
        )}

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-[#111827] mb-1">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="form-input"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-[#111827] mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="form-input"
              placeholder={isRegister ? 'Min 8 characters' : '••••••••'}
            />
          </div>

          <GradientBar height={3} />

          <button
            type="submit"
            disabled={isLoading}
            className="btn-primary w-full py-2.5"
          >
            {isLoading ? 'Please wait...' : isRegister ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        <div className="mt-4 text-center text-sm text-[#6B7280]">
          {isRegister ? (
            <>
              Already have an account?{' '}
              <Link to="/login" className="text-[#6366F1] hover:underline font-medium">
                Sign in →
              </Link>
            </>
          ) : (
            <>
              No account?{' '}
              <Link to="/register" className="text-[#6366F1] hover:underline font-medium">
                Register →
              </Link>
            </>
          )}
        </div>

        {demoEmail && demoPassword && (
          <>
            <div className="mt-6 flex items-center gap-3">
              <div className="flex-1 border-t border-[#E2E8F0]" />
              <span className="text-xs text-[#6B7280]">or</span>
              <div className="flex-1 border-t border-[#E2E8F0]" />
            </div>

            <button
              onClick={handleDemoLogin}
              disabled={isLoading}
              className="btn-ghost w-full py-2.5 mt-4"
            >
              Use Demo Account
            </button>
          </>
        )}
      </div>
    </div>
  );
}
