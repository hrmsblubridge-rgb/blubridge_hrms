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
  const { login, user, needsOnboarding } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    // If user is already logged in, redirect appropriately
    if (user) {
      if (user.role === 'employee') {
        if (needsOnboarding()) {
          navigate('/employee/onboarding');
        } else {
          navigate('/employee/dashboard');
        }
      } else {
        navigate('/dashboard');
      }
    }
  }, [user, navigate, needsOnboarding]);

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
      
      // Check if employee needs onboarding
      const userData = result.user;
      if (userData?.role === 'employee' && userData?.onboarding_status !== 'approved' && !userData?.onboarding_completed) {
        navigate('/employee/onboarding');
      } else if (userData?.role === 'employee') {
        navigate('/employee/dashboard');
      } else {
        navigate('/dashboard');
      }
    } else {
      toast.error(result.error);
    }
  };

  return (
    <div className="min-h-screen bg-[#e8e4dc] flex flex-col items-center justify-center px-4 py-8">
      {/* Logo at Top */}
      <div className="mb-12 animate-fade-in">
        <img src="/logo-black.png" alt="BluBridge" className="w-auto" />
      </div>

      {/* Login Card - Clean & Premium */}
      <div className="w-full max-w-[420px] animate-scale-in">
        <div className="bg-[#fffdf7] rounded-2xl shadow-[0_4px_24px_rgba(0,0,0,0.06)] p-8 sm:p-10">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-[26px] font-bold text-[#1a1a2e]" style={{ fontFamily: 'Outfit' }}>
              Welcome back
            </h1>
            <p className="text-[#6b7280] mt-2 text-[15px]">
              Sign in to your account to continue
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Username Field */}
            <div className="space-y-2">
              <Label htmlFor="username" className="text-sm font-medium text-[#374151]">
                Username
              </Label>
              <div className="relative">
                <User className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-[#9ca3af]" />
                <Input
                  id="username"
                  type="text"
                  placeholder="Enter your username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="pl-11 h-[52px] bg-[#f5f5f3] border-0 rounded-xl text-[15px] placeholder:text-[#9ca3af] focus:bg-white focus:ring-2 focus:ring-[#063c88]/20 transition-all"
                  data-testid="username-input"
                />
              </div>
            </div>

            {/* Password Field */}
            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium text-[#374151]">
                Password
              </Label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-[#9ca3af]" />
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-11 pr-11 h-[52px] bg-[#f5f5f3] border-0 rounded-xl text-[15px] placeholder:text-[#9ca3af] focus:bg-white focus:ring-2 focus:ring-[#063c88]/20 transition-all"
                  data-testid="password-input"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-[#9ca3af] hover:text-[#6b7280] transition-colors"
                >
                  {showPassword ? <EyeOff className="w-[18px] h-[18px]" /> : <Eye className="w-[18px] h-[18px]" />}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              disabled={loading || seeding}
              className="w-full h-[52px] bg-[#0f1d3d] hover:bg-[#1a2d5a] text-white font-semibold rounded-full text-[15px] shadow-lg shadow-[#0f1d3d]/20 transition-all duration-200 active:scale-[0.98] mt-2"
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
      <p className="text-center text-sm text-[#9ca3af] mt-10">
        © 2026 BluBridge HRMS. All rights reserved.
      </p>
    </div>
  );
};

export default Login;
