import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { KeyRound, Eye, EyeOff, Lock, CheckCircle, ShieldCheck } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ChangePassword = () => {
  const { getAuthHeaders } = useAuth();
  const [loading, setLoading] = useState(false);
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [form, setForm] = useState({ currentPassword: '', newPassword: '', confirmPassword: '' });
  const [errors, setErrors] = useState({});

  const validateForm = () => {
    const newErrors = {};
    if (!form.currentPassword) newErrors.currentPassword = 'Current password is required';
    if (!form.newPassword) newErrors.newPassword = 'New password is required';
    else if (form.newPassword.length < 6) newErrors.newPassword = 'Password must be at least 6 characters';
    if (!form.confirmPassword) newErrors.confirmPassword = 'Please confirm your new password';
    else if (form.newPassword !== form.confirmPassword) newErrors.confirmPassword = 'Passwords do not match';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;
    try {
      setLoading(true);
      await axios.post(`${API}/auth/change-password`, { current_password: form.currentPassword, new_password: form.newPassword }, { headers: getAuthHeaders() });
      toast.success('Password changed successfully');
      setForm({ currentPassword: '', newPassword: '', confirmPassword: '' });
      setErrors({});
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to change password');
    } finally {
      setLoading(false);
    }
  };

  const getPasswordStrength = (password) => {
    if (!password) return { strength: 0, label: '', color: '' };
    let strength = 0;
    if (password.length >= 6) strength++;
    if (password.length >= 8) strength++;
    if (/[A-Z]/.test(password)) strength++;
    if (/[0-9]/.test(password)) strength++;
    if (/[^A-Za-z0-9]/.test(password)) strength++;
    if (strength <= 2) return { strength, label: 'Weak', color: 'bg-red-500' };
    if (strength <= 3) return { strength, label: 'Medium', color: 'bg-amber-500' };
    return { strength, label: 'Strong', color: 'bg-emerald-500' };
  };

  const passwordStrength = getPasswordStrength(form.newPassword);

  return (
    <div className="space-y-6 animate-fade-in" data-testid="change-password-page">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
          <KeyRound className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Change Password</h1>
          <p className="text-sm text-slate-500">Update your account password</p>
        </div>
      </div>

      {/* Password Card */}
      <div className="max-w-xl mx-auto">
        <div className="card-premium overflow-hidden">
          <div className="bg-gradient-to-r from-[#063c88] to-[#0a5cba] p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-white/10 backdrop-blur-sm rounded-xl">
                <ShieldCheck className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white" style={{ fontFamily: 'Outfit' }}>Secure Your Account</h2>
                <p className="text-sm text-white/70">Create a strong, unique password</p>
              </div>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="p-6 space-y-5">
            {/* Current Password */}
            <div>
              <Label className="text-sm font-medium text-slate-700">Current Password</Label>
              <div className="relative mt-1.5">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <Input type={showCurrentPassword ? 'text' : 'password'} value={form.currentPassword} onChange={(e) => setForm({ ...form, currentPassword: e.target.value })} className={`pl-10 pr-10 rounded-lg bg-white ${errors.currentPassword ? 'border-red-500' : ''}`} placeholder="Enter current password" data-testid="current-password-input" />
                <button type="button" onClick={() => setShowCurrentPassword(!showCurrentPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                  {showCurrentPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.currentPassword && <p className="text-sm text-red-500 mt-1">{errors.currentPassword}</p>}
            </div>

            {/* New Password */}
            <div>
              <Label className="text-sm font-medium text-slate-700">New Password</Label>
              <div className="relative mt-1.5">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <Input type={showNewPassword ? 'text' : 'password'} value={form.newPassword} onChange={(e) => setForm({ ...form, newPassword: e.target.value })} className={`pl-10 pr-10 rounded-lg bg-white ${errors.newPassword ? 'border-red-500' : ''}`} placeholder="Enter new password" data-testid="new-password-input" />
                <button type="button" onClick={() => setShowNewPassword(!showNewPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                  {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.newPassword && <p className="text-sm text-red-500 mt-1">{errors.newPassword}</p>}
              {form.newPassword && (
                <div className="mt-2 flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div className={`h-full ${passwordStrength.color} transition-all duration-300`} style={{ width: `${(passwordStrength.strength / 5) * 100}%` }} />
                  </div>
                  <span className={`text-xs font-medium ${passwordStrength.label === 'Weak' ? 'text-red-500' : passwordStrength.label === 'Medium' ? 'text-amber-500' : 'text-emerald-500'}`}>
                    {passwordStrength.label}
                  </span>
                </div>
              )}
            </div>

            {/* Confirm Password */}
            <div>
              <Label className="text-sm font-medium text-slate-700">Confirm New Password</Label>
              <div className="relative mt-1.5">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <Input type={showConfirmPassword ? 'text' : 'password'} value={form.confirmPassword} onChange={(e) => setForm({ ...form, confirmPassword: e.target.value })} className={`pl-10 pr-10 rounded-lg bg-white ${errors.confirmPassword ? 'border-red-500' : ''}`} placeholder="Confirm new password" data-testid="confirm-password-input" />
                <button type="button" onClick={() => setShowConfirmPassword(!showConfirmPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                  {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.confirmPassword && <p className="text-sm text-red-500 mt-1">{errors.confirmPassword}</p>}
              {form.confirmPassword && form.newPassword === form.confirmPassword && !errors.confirmPassword && (
                <p className="text-sm text-emerald-500 mt-1 flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Passwords match</p>
              )}
            </div>

            {/* Requirements */}
            <div className="p-4 bg-slate-50 rounded-xl">
              <h4 className="text-sm font-medium text-slate-700 mb-3">Password Requirements:</h4>
              <ul className="space-y-2">
                {[
                  { met: form.newPassword.length >= 6, text: 'At least 6 characters' },
                  { met: /[A-Z]/.test(form.newPassword), text: 'One uppercase letter' },
                  { met: /[0-9]/.test(form.newPassword), text: 'One number' },
                ].map((req, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm">
                    <CheckCircle className={`w-4 h-4 ${req.met ? 'text-emerald-500' : 'text-slate-300'}`} />
                    <span className={req.met ? 'text-slate-700' : 'text-slate-500'}>{req.text}</span>
                  </li>
                ))}
              </ul>
            </div>

            <Button type="submit" disabled={loading} className="w-full bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg h-12 shadow-lg shadow-[#063c88]/20" data-testid="change-password-btn">
              {loading ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Change Password'}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ChangePassword;
