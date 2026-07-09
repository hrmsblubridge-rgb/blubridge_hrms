import { useEffect, useState, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2, CheckCircle2, AlertTriangle, Camera } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Public landing page reached from the "Upload your profile picture" email.
 *
 *   /profile-upload?token=...
 *
 * Flow:
 *   1. Validate the token (no side effects) → show a friendly status while we work.
 *   2. POST /api/profile-upload/redeem → server returns a short-lived JWT and
 *      the employee object, plus a redirect target.
 *   3. We persist the JWT just like /auth/login does, hydrate AuthContext, and
 *      redirect to `/employee/profile?welcome=upload` where the existing
 *      AvatarUploader handles the rest.
 */
const ProfileUploadRedeem = () => {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const { refreshAvatars } = useAuth() || {};

  const [phase, setPhase] = useState('loading'); // loading | invalid | redirecting
  const [reason, setReason] = useState('');
  const [employeeEmail, setEmployeeEmail] = useState('');
  // Guard against React 18 dev-mode double effect causing a duplicate
  // redeem (and consuming the single-use token unnecessarily).
  const redeemedRef = useRef(false);

  useEffect(() => {
    if (!token) {
      setPhase('invalid');
      setReason('No token was provided in the link.');
      return;
    }
    if (redeemedRef.current) return;
    redeemedRef.current = true;

    (async () => {
      try {
        // 1) lightweight validate (so we can show email + nicer errors)
        const valResp = await axios.get(`${API}/profile-upload/validate?token=${encodeURIComponent(token)}`);
        if (!valResp.data?.valid) {
          setPhase('invalid');
          setReason(valResp.data?.reason || 'This link is no longer valid.');
          return;
        }
        setEmployeeEmail(valResp.data?.email || '');

        // 2) redeem (single-use)
        const redResp = await axios.post(`${API}/profile-upload/redeem`, { token });
        const { token: authToken, refresh_token: refreshToken, redirect } = redResp.data || {};
        if (!authToken) {
          setPhase('invalid');
          setReason('Server did not return a sign-in token.');
          return;
        }

        // 3) hydrate session — same shape AuthContext expects on init
        localStorage.setItem('blubridge_token', authToken);
        if (refreshToken) localStorage.setItem('blubridge_refresh_token', refreshToken);
        setPhase('redirecting');
        toast.success('Signed in. Taking you to your profile…');
        // Best-effort: prime the avatar cache for snappy UX once landed.
        refreshAvatars?.(authToken);
        // Hard reload to force AuthContext.initAuth to pick up the new
        // token (avoids stale React state on a freshly hydrated SPA).
        setTimeout(() => {
          window.location.replace(redirect || '/employee/profile?welcome=upload');
        }, 600);
      } catch (err) {
        const detail = err?.response?.data?.detail || 'Something went wrong. Please request a new link.';
        setPhase('invalid');
        setReason(detail);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#f4f5f7] via-[#fefefe] to-[#eef2f9] flex items-center justify-center px-4" data-testid="profile-upload-redeem">
      <div className="w-full max-w-md bg-white rounded-3xl shadow-xl ring-1 ring-slate-100 p-10 text-center">
        <div className="mx-auto w-14 h-14 rounded-2xl bg-[#063c88] flex items-center justify-center mb-6 shadow-lg">
          <Camera className="w-7 h-7 text-white" />
        </div>

        {phase === 'loading' && (
          <>
            <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>
              Verifying your link
            </h1>
            <p className="text-sm text-slate-500 mt-2">
              Just a moment while we sign you in securely…
            </p>
            <div className="mt-8 flex items-center justify-center">
              <Loader2 className="w-8 h-8 animate-spin text-[#063c88]" />
            </div>
          </>
        )}

        {phase === 'redirecting' && (
          <>
            <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>
              You're in!
            </h1>
            <p className="text-sm text-slate-500 mt-2">
              Hi {employeeEmail || 'there'} — taking you to your profile…
            </p>
            <div className="mt-8 flex items-center justify-center">
              <CheckCircle2 className="w-10 h-10 text-emerald-500" />
            </div>
          </>
        )}

        {phase === 'invalid' && (
          <>
            <div className="mx-auto w-12 h-12 rounded-full bg-amber-50 flex items-center justify-center mb-4">
              <AlertTriangle className="w-6 h-6 text-amber-600" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>
              Link unavailable
            </h1>
            <p className="text-sm text-slate-600 mt-2 leading-relaxed">{reason}</p>
            <button
              onClick={() => navigate('/login')}
              data-testid="profile-upload-go-login"
              className="mt-8 inline-flex items-center justify-center px-6 py-3 rounded-full bg-[#063c88] text-white font-medium hover:bg-[#0a5cba] transition"
            >
              Go to login
            </button>
            <p className="text-xs text-slate-400 mt-4">
              Need a fresh link? Contact your HR administrator.
            </p>
          </>
        )}
      </div>
    </div>
  );
};

export default ProfileUploadRedeem;
