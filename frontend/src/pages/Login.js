import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { Lock, User, Eye, EyeOff, Loader2, ArrowRight } from 'lucide-react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const { login, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) {
      navigate('/dashboard');
    }
  }, [user, navigate]);

  useEffect(() => {
    const seedDb = async () => {
      try {
        setSeeding(true);
        await axios.post(`${API}/seed`);
      } catch (error) {
        console.log('Seed completed or already seeded');
      } finally {
        setSeeding(false);
      }
    };
    seedDb();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!username || !password) {
      toast.error('Please enter username and password');
      return;
    }

    setLoading(true);
    const result = await login(username, password);
    setLoading(false);

    if (result.success) {
      toast.success('Welcome to BluBridge HRMS');
      navigate('/dashboard');
    } else {
      toast.error(result.error);
    }
  };

  return (
    <div className="min-h-screen bg-[#FFFDF6] flex items-center justify-center p-6">
      {/* Main Container */}
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <img src="/logo-black.png" alt="BluBridge" className="h-10 mx-auto" />
        </div>

        {/* Login Card with Animated Border */}
        <div className="login-card-wrapper">
          <div className="login-card-animated-border"></div>
          <div className="login-card-content">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>
                Welcome back
              </h2>
              <p className="text-slate-500 mt-2 text-sm">
                Sign in to your account to continue
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="username" className="text-sm font-medium text-slate-700">
                  Username
                </Label>
                <div className="relative">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                  <Input
                    id="username"
                    type="text"
                    placeholder="Enter your username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="pl-12 h-12 bg-[#F8F7F4] border-slate-200 rounded-xl focus:bg-white focus:border-[#063c88] transition-all"
                    data-testid="username-input"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-sm font-medium text-slate-700">
                  Password
                </Label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pl-12 pr-12 h-12 bg-[#F8F7F4] border-slate-200 rounded-xl focus:bg-white focus:border-[#063c88] transition-all"
                    data-testid="password-input"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                    data-testid="toggle-password-btn"
                  >
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                disabled={loading || seeding}
                className="w-full h-12 bg-[#063c88] hover:bg-[#052d66] text-white font-semibold rounded-xl shadow-lg shadow-[#063c88]/25 transition-all duration-200 active:scale-[0.98] mt-2"
                data-testid="login-submit-btn"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    Signing in...
                  </>
                ) : seeding ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    Initializing...
                  </>
                ) : (
                  <>
                    Sign In
                    <ArrowRight className="w-5 h-5 ml-2" />
                  </>
                )}
              </Button>
            </form>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-sm text-slate-400 mt-8">
          © 2026 BluBridge HRMS. All rights reserved.
        </p>
      </div>
    </div>
  );
};

export default Login;
