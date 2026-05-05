import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Mail, Loader2, ArrowLeft, CheckCircle2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ForgotPassword = () => {
  const [identifier, setIdentifier] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(null); // { sent_to } once link is dispatched
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    const id = identifier.trim();
    if (!id) {
      toast.error('Please enter your username or email');
      return;
    }
    setLoading(true);
    try {
      const { data } = await axios.post(`${API}/auth/forgot-password`, { identifier: id });
      setDone(data);
      toast.success('Reset link sent to your registered email');
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Could not send reset link. Please try again.';
      toast.error(typeof msg === 'string' ? msg : 'Could not send reset link');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f5f3ee] px-4" data-testid="forgot-password-page">
      <div className="w-full max-w-[440px]">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold tracking-[3px] text-[#0f1d3d]" style={{ fontFamily: 'Outfit' }}>
            BLU<span className="text-[#f59e0b]">B</span>RIDGE
          </h1>
          <p className="text-xs text-[#9ca3af] tracking-[2px] mt-1">HRMS PLATFORM</p>
        </div>

        <div className="bg-[#fffdf7] rounded-2xl shadow-xl p-8 sm:p-10">
          {!done ? (
            <>
              <h2 className="text-2xl font-bold text-[#0f1d3d] mb-1" style={{ fontFamily: 'Outfit' }}>Forgot password?</h2>
              <p className="text-sm text-[#6b7280] mb-7">Enter your username or registered email and we'll email you a secure reset link.</p>
              <form onSubmit={submit} className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="identifier" className="text-[#374151] text-[13px] font-medium">Username or Email</Label>
                  <div className="relative">
                    <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-[#9ca3af]" />
                    <Input
                      id="identifier"
                      autoFocus
                      placeholder="e.g. john.doe or john@company.com"
                      value={identifier}
                      onChange={(e) => setIdentifier(e.target.value)}
                      className="pl-11 h-[52px] bg-[#f5f5f3] border-0 rounded-xl text-[15px] focus:bg-white focus:ring-2 focus:ring-[#063c88]/20"
                      data-testid="forgot-identifier-input"
                    />
                  </div>
                </div>
                <Button
                  type="submit"
                  disabled={loading}
                  className="w-full h-[52px] bg-[#0f1d3d] hover:bg-[#1a2d5a] text-white font-semibold rounded-full"
                  data-testid="forgot-submit-btn"
                >
                  {loading ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Sending…</> : 'Send Reset Link'}
                </Button>
                <button
                  type="button"
                  onClick={() => navigate('/login')}
                  className="w-full flex items-center justify-center gap-2 text-sm text-[#6b7280] hover:text-[#0f1d3d] transition-colors mt-2"
                  data-testid="forgot-back-to-login"
                >
                  <ArrowLeft className="w-4 h-4" /> Back to login
                </button>
              </form>
            </>
          ) : (
            <div className="text-center" data-testid="forgot-done">
              <div className="w-16 h-16 mx-auto rounded-full bg-emerald-50 flex items-center justify-center mb-4">
                <CheckCircle2 className="w-8 h-8 text-emerald-600" />
              </div>
              <h2 className="text-xl font-bold text-[#0f1d3d] mb-2" style={{ fontFamily: 'Outfit' }}>Check your email</h2>
              <p className="text-sm text-[#6b7280] mb-1">We sent a reset link to</p>
              <p className="text-sm font-semibold text-[#0f1d3d] mb-5">{done.sent_to}</p>
              <p className="text-xs text-[#9ca3af] mb-6">The link expires in 30 minutes and can only be used once. Please check your spam folder if you don't see it.</p>
              <Link to="/login">
                <Button variant="outline" className="rounded-full" data-testid="forgot-done-back-btn">
                  <ArrowLeft className="w-4 h-4 mr-2" /> Back to login
                </Button>
              </Link>
            </div>
          )}
        </div>

        <p className="text-center text-xs text-[#9ca3af] mt-6">© 2026 BluBridge HRMS. All rights reserved.</p>
      </div>
    </div>
  );
};

export default ForgotPassword;
