/**
 * PayslipAuthGate — additional 6-digit authorization layer for the ADMIN
 * Payslip module.
 *
 * The gate is UX only: the backend rejects every /api/payslips request with
 * 403 { error: "payslip_auth_required" } until the current HRMS session has
 * been verified, so payslip data is never fetched behind this modal.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { ShieldCheck, Loader2, RefreshCw, Lock } from 'lucide-react';
import { Button } from './ui/button';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const RECIPIENT = 'hrrecruiter@blubridge.com';

const PayslipAuthGate = ({ children }) => {
  const { token } = useAuth();
  const inputRef = useRef(null);
  const [checking, setChecking] = useState(true);
  const [verified, setVerified] = useState(false);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [lockedUntil, setLockedUntil] = useState(null);
  const [canRegenerate, setCanRegenerate] = useState(false);
  const [confirmRegen, setConfirmRegen] = useState(false);
  const [regenBusy, setRegenBusy] = useState(false);

  const headers = { Authorization: `Bearer ${token}` };

  const loadStatus = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/payslip-security/status`, { headers });
      setVerified(!!r.data?.verified);
      setLockedUntil(r.data?.locked_until || null);
      setCanRegenerate(!!r.data?.can_regenerate);
    } catch (e) {
      setVerified(false);
    } finally {
      setChecking(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  // Any payslip API rejected mid-session (e.g. another admin regenerated the
  // code) immediately re-locks the module.
  useEffect(() => {
    const id = axios.interceptors.response.use(
      (r) => r,
      (err) => {
        if (err?.response?.status === 403 && err?.response?.data?.error === 'payslip_auth_required') {
          setVerified(false);
          setCode('');
        }
        return Promise.reject(err);
      }
    );
    return () => axios.interceptors.response.eject(id);
  }, []);

  useEffect(() => {
    if (!verified && !checking) setTimeout(() => inputRef.current?.focus(), 120);
  }, [verified, checking]);

  const submit = async () => {
    setError('');
    if (!/^\d{6}$/.test(code)) {
      setError('Enter a valid 6-digit authorization code.');
      return;
    }
    setBusy(true);
    try {
      await axios.post(`${API}/payslip-security/verify`, { code }, { headers });
      toast.success('Authorization successful.');
      setCode('');
      setVerified(true);
    } catch (e) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;
      if (status === 429) {
        setError(detail || 'Too many incorrect attempts. Payslip verification is temporarily locked.');
        setLockedUntil('locked');
      } else {
        setError(detail || 'Invalid authorization code. Please try again.');
      }
    } finally {
      setBusy(false);
    }
  };

  const regenerate = async () => {
    setRegenBusy(true);
    setError('');
    try {
      const r = await axios.post(`${API}/payslip-security/regenerate`, {}, { headers });
      setConfirmRegen(false);
      toast.success(r.data?.message || `A new authorization code has been sent to ${RECIPIENT}.`);
      setVerified(false);
      setCode('');
      loadStatus();
    } catch (e) {
      setConfirmRegen(false);
      setError(
        e?.response?.data?.detail ||
        'Unable to send the new authorization code. Your existing authorization code remains active.'
      );
    } finally {
      setRegenBusy(false);
    }
  };

  if (checking) {
    return (
      <div className="flex items-center justify-center py-32" data-testid="payslip-auth-checking">
        <Loader2 className="w-6 h-6 animate-spin text-[#063c88]" />
      </div>
    );
  }

  if (verified) return children;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm"
         data-testid="payslip-auth-modal">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl overflow-hidden">
        <div className="px-6 pt-6 pb-4 border-b border-slate-100 text-center">
          <div className="w-12 h-12 mx-auto rounded-xl bg-[#063c88] flex items-center justify-center mb-3">
            <ShieldCheck className="w-6 h-6 text-white" />
          </div>
          <h3 className="text-base font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>
            Payslip Security Verification
          </h3>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            This module contains confidential salary and payroll information.
            <br />Enter the 6-digit Authorization Code.
          </p>
        </div>

        <div className="p-6 space-y-4">
          <input
            ref={inputRef}
            type="password"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            value={code}
            onChange={(e) => { setCode(e.target.value.replace(/\D/g, '').slice(0, 6)); setError(''); }}
            onKeyDown={(e) => { if (e.key === 'Enter') submit(); }}
            placeholder="••••••"
            disabled={busy}
            className="w-full text-center tracking-[0.7em] text-2xl font-semibold py-3 rounded-xl
                       border border-slate-200 bg-slate-50 focus:outline-none focus:ring-2
                       focus:ring-[#063c88]/40 disabled:opacity-60"
            data-testid="payslip-auth-code-input"
          />

          {error && (
            <div className="text-xs text-rose-600 bg-rose-50 border border-rose-100 rounded-lg px-3 py-2"
                 data-testid="payslip-auth-error">
              {error}
            </div>
          )}
          {lockedUntil && (
            <div className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2 flex items-center gap-2">
              <Lock className="w-3.5 h-3.5" /> Verification is temporarily locked. Please try again later.
            </div>
          )}

          <Button
            onClick={submit}
            disabled={busy || code.length !== 6}
            className="w-full bg-[#063c88] hover:bg-[#04306d]"
            data-testid="payslip-auth-verify-btn"
          >
            {busy ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Verifying…</> : 'Verify Auth Code'}
          </Button>

          {canRegenerate && (
            <Button
              variant="outline"
              onClick={() => setConfirmRegen(true)}
              disabled={regenBusy}
              className="w-full"
              data-testid="payslip-auth-regenerate-btn"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-2" /> Regenerate Auth Code
            </Button>
          )}
        </div>
      </div>

      {confirmRegen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-slate-900/60"
             data-testid="payslip-auth-regen-confirm">
          <div className="w-full max-w-sm bg-white rounded-2xl shadow-2xl p-6 space-y-4">
            <h4 className="text-sm font-bold text-slate-900">Regenerate Payslip Authorization Code?</h4>
            <p className="text-xs text-slate-600 leading-relaxed">
              The existing authorization code will stop working and a new 6-digit code will be sent to:
              <span className="block font-semibold text-slate-900 mt-1">{RECIPIENT}</span>
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setConfirmRegen(false)} disabled={regenBusy}
                      data-testid="payslip-auth-regen-cancel">Cancel</Button>
              <Button onClick={regenerate} disabled={regenBusy} className="bg-[#063c88] hover:bg-[#04306d]"
                      data-testid="payslip-auth-regen-confirm-btn">
                {regenBusy ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Sending…</> : 'Regenerate'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PayslipAuthGate;
