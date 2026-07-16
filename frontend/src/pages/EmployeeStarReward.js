import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Card } from '../components/ui/card';
import { toast } from 'sonner';
import { Star, Sparkles, TrendingUp, ShieldAlert, Award, Trophy } from 'lucide-react';
import { formatDate } from '../lib/dateFormat';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Employee-facing view of the star rewards an HR admin has awarded them.
 * Designed to feel celebratory (not just a data table) — big total, live
 * timeline, and a subtle month-trend strip. Handles the "no awards yet"
 * state with a warm empty-state message so the page never looks broken.
 */
const EmployeeStarReward = () => {
  const { token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API}/employee/star-rewards/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) setData(res.data);
      } catch (err) {
        toast.error(err?.response?.data?.detail || 'Failed to load rewards');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  if (loading) {
    return (
      <div className="p-6 text-slate-500 text-sm" data-testid="rewards-loading">Loading your rewards…</div>
    );
  }

  const totals = data?.totals || { stars: 0, unsafe: 0 };
  const history = data?.history || [];
  const monthly = data?.monthly || [];
  const maxMonthly = Math.max(1, ...monthly.map((m) => m.stars || 0));
  const firstName = (data?.employee?.full_name || 'there').split(' ')[0];

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6" data-testid="employee-star-reward-page">
        {/* Header — celebratory hero */}
        <div
          className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#063c88] via-[#0a5cba] to-[#1e88e5] p-6 sm:p-8 text-white shadow-lg"
          data-testid="rewards-hero"
        >
          <div className="absolute -top-16 -right-16 w-64 h-64 rounded-full bg-white/10 blur-3xl pointer-events-none" />
          <div className="absolute -bottom-20 -left-20 w-72 h-72 rounded-full bg-yellow-300/20 blur-3xl pointer-events-none" />
          <div className="relative flex flex-col sm:flex-row sm:items-center sm:justify-between gap-5">
            <div>
              <div className="flex items-center gap-2 text-white/80 text-xs uppercase tracking-[0.14em]">
                <Sparkles className="w-3.5 h-3.5" />
                My Star Rewards
              </div>
              <h1 className="mt-2 text-3xl sm:text-4xl font-bold leading-tight">
                {totals.stars > 0
                  ? <>Nicely done, {firstName}!</>
                  : <>Welcome, {firstName}</>}
              </h1>
              <p className="mt-1 text-white/80 text-sm">
                {totals.stars > 0
                  ? 'Here\'s every star HR has awarded you so far.'
                  : 'Rewards will appear here as soon as HR recognises your work.'}
              </p>
            </div>

            {/* Big star count */}
            <div className="flex items-center gap-4 sm:gap-6">
              <div className="text-center">
                <div className="text-[11px] uppercase tracking-wider text-white/70">Total Stars</div>
                <div className="mt-1 flex items-center justify-center gap-2">
                  <Star className="w-8 h-8 fill-yellow-300 text-yellow-300 drop-shadow" />
                  <span className="text-5xl font-black tabular-nums" data-testid="rewards-total-stars">{totals.stars}</span>
                </div>
              </div>
              {totals.unsafe > 0 && (
                <div className="text-center">
                  <div className="text-[11px] uppercase tracking-wider text-white/70">Unsafe Flags</div>
                  <div className="mt-1 flex items-center justify-center gap-2">
                    <ShieldAlert className="w-6 h-6 text-red-300" />
                    <span className="text-3xl font-bold tabular-nums" data-testid="rewards-unsafe-count">{totals.unsafe}</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Monthly trend strip — only if there's data */}
        {monthly.length > 0 && (
          <Card className="p-5 rounded-2xl border-slate-200/70" data-testid="rewards-monthly">
            <div className="flex items-center gap-2 text-slate-700">
              <TrendingUp className="w-4 h-4 text-[#063c88]" />
              <h2 className="text-sm font-semibold">Last {monthly.length} month{monthly.length === 1 ? '' : 's'}</h2>
            </div>
            <div className="mt-4 flex items-end gap-3 h-32">
              {monthly.map((m) => {
                const pct = Math.max(6, Math.round((m.stars / maxMonthly) * 100));
                const label = new Date(m.month + '-01').toLocaleString('en-IN', { month: 'short' });
                return (
                  <div key={m.month} className="flex-1 flex flex-col items-center gap-1.5">
                    <div className="w-full flex-1 flex items-end">
                      <div
                        className="w-full rounded-t-md bg-gradient-to-t from-[#063c88] to-[#4d8fe0] shadow-inner"
                        style={{ height: `${pct}%` }}
                        title={`${m.stars} star${m.stars === 1 ? '' : 's'} in ${label}`}
                      />
                    </div>
                    <div className="text-[11px] text-slate-500 font-medium">{label}</div>
                    <div className="text-xs text-slate-800 font-semibold tabular-nums">{m.stars}</div>
                  </div>
                );
              })}
            </div>
          </Card>
        )}

        {/* Timeline / history */}
        <Card className="p-5 rounded-2xl border-slate-200/70" data-testid="rewards-history">
          <div className="flex items-center gap-2 text-slate-700 mb-4">
            <Award className="w-4 h-4 text-[#063c88]" />
            <h2 className="text-sm font-semibold">Reward history</h2>
            <span className="ml-auto text-xs text-slate-400">{history.length} entr{history.length === 1 ? 'y' : 'ies'}</span>
          </div>

          {history.length === 0 ? (
            <div className="py-12 text-center" data-testid="rewards-empty">
              <div className="mx-auto w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center">
                <Trophy className="w-7 h-7 text-slate-400" />
              </div>
              <p className="mt-3 text-slate-600 text-sm font-medium">No rewards yet</p>
              <p className="mt-1 text-slate-400 text-xs max-w-xs mx-auto">
                Consistent great work gets recognised here. Rewards from your HR will show up automatically.
              </p>
            </div>
          ) : (
            <ol className="relative space-y-3">
              <div className="absolute left-4 top-2 bottom-2 w-px bg-slate-200" aria-hidden />
              {history.map((r) => {
                const isUnsafe = r.type === 'unsafe';
                const isWeekly = r.type === 'weekly';
                return (
                  <li
                    key={r.id}
                    className="relative pl-11 pr-3 py-3 rounded-xl bg-slate-50/70 hover:bg-slate-50 transition-colors"
                    data-testid={`reward-item-${r.id}`}
                  >
                    <div
                      className={`absolute left-2 top-3 w-5 h-5 rounded-full flex items-center justify-center ring-4 ring-white shadow ${
                        isUnsafe ? 'bg-red-500' : 'bg-gradient-to-br from-yellow-400 to-amber-500'
                      }`}
                    >
                      {isUnsafe ? (
                        <ShieldAlert className="w-3 h-3 text-white" />
                      ) : (
                        <Star className="w-3 h-3 fill-white text-white" />
                      )}
                    </div>
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`font-semibold tabular-nums text-sm ${isUnsafe ? 'text-red-600' : 'text-slate-800'}`}>
                            {isUnsafe ? 'Unsafe flag' : `+${r.stars} star${r.stars === 1 ? '' : 's'}`}
                          </span>
                          {isWeekly && r.week_number && (
                            <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-[#063c88]/10 text-[#063c88] tracking-wider">
                              Week {r.week_number}
                            </span>
                          )}
                        </div>
                        {r.reason && (
                          <p className="mt-0.5 text-sm text-slate-600 leading-snug">{r.reason}</p>
                        )}
                      </div>
                      <div className="text-right text-xs text-slate-500 shrink-0">
                        <div>{formatDate(r.created_at)}</div>
                        <div className="text-slate-400">by {r.awarded_by_name || 'HR'}</div>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </Card>
    </div>
  );
};

export default EmployeeStarReward;
