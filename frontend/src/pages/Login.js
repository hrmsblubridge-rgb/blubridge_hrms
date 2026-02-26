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
    <div className="min-h-screen bg-[#efede5] flex">
      {/* Left Panel - Premium Branding */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden bg-[#063c88]">
        {/* Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-br from-[#063c88] via-[#052d66] to-[#041d44]" />
        
        {/* Subtle Grid Pattern */}
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.1) 1px, transparent 1px)`,
          backgroundSize: '60px 60px'
        }} />
        
        {/* Floating Orbs */}
        <div className="absolute top-20 right-20 w-72 h-72 bg-white/5 rounded-full blur-3xl" />
        <div className="absolute bottom-40 left-10 w-96 h-96 bg-blue-400/5 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/3 w-48 h-48 bg-white/3 rounded-full blur-2xl" />
        
        {/* Content */}
        <div className="relative z-10 flex flex-col justify-between p-12 w-full h-full">
          {/* Logo */}
          <div>
            <img src="/logo-white.png" alt="BluBridge" className="w-auto" />
          </div>

          {/* Main Content - Centered */}
          <div className="flex-1 flex flex-col justify-center max-w-lg">
            <h1 className="text-5xl lg:text-6xl font-bold text-white leading-[1.1] tracking-tight" style={{ fontFamily: 'Outfit' }}>
              Elevate your
              <br />
              <span className="text-white/60">workforce</span>
              <br />
              management
            </h1>
            <p className="mt-8 text-lg text-white/50 leading-relaxed">
              Streamline HR operations with an intelligent platform built for modern enterprises.
            </p>
            
            {/* Stats Row */}
            <div className="mt-12 flex gap-12">
              <div>
                <p className="text-3xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>500+</p>
                <p className="text-sm text-white/40 mt-1">Enterprises</p>
              </div>
              <div>
                <p className="text-3xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>50K+</p>
                <p className="text-sm text-white/40 mt-1">Employees</p>
              </div>
              <div>
                <p className="text-3xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>99.9%</p>
                <p className="text-sm text-white/40 mt-1">Uptime</p>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between">
            <p className="text-white/30 text-sm">© 2026 BluBridge HRMS.</p>
          </div>
        </div>
      </div>

      {/* Right Panel - Login Form */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-md">
          {/* Mobile Logo */}
          <div className="lg:hidden text-center mb-10">
            <img src="/logo-black.png" alt="BluBridge" className="w-auto mx-auto" />
          </div>

          {/* Login Card with Animated Border */}
          <div className="login-card-wrapper animate-scale-in">
            <div className="login-card-animated-border">
              <div className="login-card-animated-border-inner"></div>
            </div>
            <div className="login-card-content">
              <div className="text-center mb-8">
                <h2 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>
                  Welcome back
                </h2>
                <p className="text-slate-500 mt-2">Sign in to your account to continue</p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-6">
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
                      className="pl-12 h-12 bg-slate-50 border-slate-200 rounded-xl focus:bg-white transition-colors"
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
                      className="pl-12 pr-12 h-12 bg-slate-50 border-slate-200 rounded-xl focus:bg-white transition-colors"
                      data-testid="password-input"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                </div>

                <Button
                  type="submit"
                  disabled={loading || seeding}
                  className="w-full h-12 bg-[#063c88] hover:bg-[#052d66] text-white font-semibold rounded-xl shadow-lg shadow-[#063c88]/30 transition-all duration-200 active:scale-[0.98]"
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

          <p className="text-center text-sm text-slate-400 mt-8">
            © 2026 BluBridge HRMS. All rights reserved.
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
