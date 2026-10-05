import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Lock, Eye, EyeOff, Loader2, CheckCircle2, AlertTriangle } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ResetPassword = () => {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const navigate = useNavigate();

  const [validating, setValidating] = useState(true);
  const [valid, setValid] = useState(false);
  const [validationError, setValidationError] = useState('');
  const [username, setUsername] = useState('');

  const [pw, setPw] = useState('');
  const [pw2, setPw2] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const run = async () => {
      if (!token) {
        setValidationError('Missing reset token. Please request a new reset link.');
        setValidating(false);
        return;
      }
      try {
        const { data } = await axios.get(`${API}/auth/reset-password/validate`, { params: { token } });
        setValid(true);
        setUsername(data.username || '');
      } catch (err) {
        setValidationError(err?.response?.data?.detail || 'This reset link is invalid or expired.');
      } finally {
        setValidating(false);
      }
    };
    run();
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    if (pw.length < 8) { toast.error('Password must be at least 8 characters long'); return; }
    if (pw !== pw2) { toast.error('Passwords do not match'); return; }
    setSubmitting(true);
    try {
      await axios.post(`${API}/auth/reset-password`, { token, new_password: pw, confirm_password: pw2 });
      setDone(true);
      toast.success('Password reset successfully. Please login.');
      setTimeout(() => navigate('/login'), 1800);
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Could not reset password. Please try again.';
      toast.error(typeof msg === 'string' ? msg : 'Could not reset password');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f5f3ee] px-4" data-testid="reset-password-page">
      <div className="w-full max-w-[440px]">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold tracking-[3px] text-[#0f1d3d]" style={{ fontFamily: 'Outfit' }}>
            BLU<span className="text-[#f59e0b]">B</span>RIDGE
          </h1>
          <p className="text-xs text-[#9ca3af] tracking-[2px] mt-1">HRMS PLATFORM</p>
        </div>

        <div className="bg-[#fffdf7] rounded-2xl shadow-xl p-8 sm:p-10">
          {validating ? (
            <div className="flex flex-col items-center py-10" data-testid="reset-validating">
              <Loader2 className="w-8 h-8 animate-spin text-[#063c88] mb-3" />
              <p className="text-sm text-[#6b7280]">Validating reset link…</p>
            </div>
          ) : !valid ? (
            <div className="text-center py-6" data-testid="reset-invalid">
              <div className="w-16 h-16 mx-auto rounded-full bg-rose-50 flex items-center justify-center mb-4">
                <AlertTriangle className="w-8 h-8 text-rose-600" />
              </div>
              <h2 className="text-xl font-bold text-[#0f1d3d] mb-2" style={{ fontFamily: 'Outfit' }}>Link unavailable</h2>
              <p className="text-sm text-[#6b7280] mb-6">{validationError}</p>
              <div className="flex flex-col gap-2">
                <Link to="/forgot-password">
                  <Button className="rounded-full bg-[#0f1d3d] hover:bg-[#1a2d5a] text-white" data-testid="reset-request-new-btn">
                    Request a new link
                  </Button>
                </Link>
                <Link to="/login">
                  <Button variant="outline" className="rounded-full" data-testid="reset-back-login-btn">Back to login</Button>
                </Link>
              </div>
            </div>
          ) : done ? (
            <div className="text-center py-6" data-testid="reset-done">
              <div className="w-16 h-16 mx-auto rounded-full bg-emerald-50 flex items-center justify-center mb-4">
                <CheckCircle2 className="w-8 h-8 text-emerald-600" />
              </div>
              <h2 className="text-xl font-bold text-[#0f1d3d] mb-2" style={{ fontFamily: 'Outfit' }}>Password reset</h2>
              <p className="text-sm text-[#6b7280]">Redirecting you to login…</p>
            </div>
          ) : (
            <>
              <h2 className="text-2xl font-bold text-[#0f1d3d] mb-1" style={{ fontFamily: 'Outfit' }}>Reset your password</h2>
              <p className="text-sm text-[#6b7280] mb-6">
                {username ? <>Setting a new password for <b>{username}</b>.</> : 'Choose a strong new password.'}
              </p>
              <form onSubmit={submit} className="space-y-5">
                <div className="space-y-2">
                  <Label className="text-[#374151] text-[13px] font-medium">New password</Label>
                  <div className="relative">
                    <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-[#9ca3af]" />
                    <Input
                      type={showPw ? 'text' : 'password'}
                      placeholder="Min 8 chars, with letter and digit"
                      value={pw}
                      onChange={(e) => setPw(e.target.value)}
                      className="pl-11 pr-11 h-[52px] bg-[#f5f5f3] border-0 rounded-xl"
                      data-testid="reset-new-password-input"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPw(!showPw)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 text-[#9ca3af] hover:text-[#6b7280]"
                    >
                      {showPw ? <EyeOff className="w-[18px] h-[18px]" /> : <Eye className="w-[18px] h-[18px]" />}
                    </button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label className="text-[#374151] text-[13px] font-medium">Confirm new password</Label>
                  <div className="relative">
                    <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-[#9ca3af]" />
                    <Input
                      type={showPw ? 'text' : 'password'}
                      placeholder="Re-enter password"
                      value={pw2}
                      onChange={(e) => setPw2(e.target.value)}
                      className="pl-11 h-[52px] bg-[#f5f5f3] border-0 rounded-xl"
                      data-testid="reset-confirm-password-input"
                    />
                  </div>
                </div>
                <Button
                  type="submit"
                  disabled={submitting}
                  className="w-full h-[52px] bg-[#0f1d3d] hover:bg-[#1a2d5a] text-white font-semibold rounded-full"
                  data-testid="reset-submit-btn"
                >
                  {submitting ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Resetting…</> : 'Reset password'}
                </Button>
              </form>
            </>
          )}
        </div>
        <p className="text-center text-xs text-[#9ca3af] mt-6">© 2026 BluBridge HRMS. All rights reserved.</p>
      </div>
    </div>
  );
};

export default ResetPassword;
