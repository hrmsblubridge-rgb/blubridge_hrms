/**
 * BirthdayWidget — Today's + upcoming birthdays for the dashboard.
 *
 * Pulls live data from `GET /api/dashboard/birthdays` (admin + employee
 * both authorized). Auto-refreshes once per minute so the widget rolls
 * over at midnight without a manual reload.
 */
import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { Cake, PartyPopper, CalendarDays } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import EmployeeAvatar from './EmployeeAvatar';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const BirthdayWidget = ({ windowDays = 7 }) => {
  const { getAuthHeaders } = useAuth();
  const [data, setData] = useState({ today: [], upcoming: [] });
  const [loading, setLoading] = useState(true);

  const fetchBirthdays = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/dashboard/birthdays`, {
        headers: getAuthHeaders(),
        params: { window_days: windowDays },
      });
      setData(res.data || { today: [], upcoming: [] });
    } catch {
      // Silent — widget should never break the dashboard
      setData({ today: [], upcoming: [] });
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders, windowDays]);

  useEffect(() => {
    fetchBirthdays();
    // Auto-refresh at the top of each minute so midnight roll-over is automatic
    const id = setInterval(fetchBirthdays, 60_000);
    return () => clearInterval(id);
  }, [fetchBirthdays]);

  const todays = data.today || [];
  const upcoming = data.upcoming || [];
  const totalCount = todays.length + upcoming.length;

  return (
    <div className="card-premium p-6 h-full" data-testid="birthday-widget">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-pink-100 to-rose-50 flex items-center justify-center">
            <Cake className="w-5 h-5 text-rose-500" strokeWidth={1.7} />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-900" style={{ fontFamily: 'Outfit' }}>Upcoming Birthdays</h3>
            <p className="text-xs text-slate-500">Today + next {windowDays} days</p>
          </div>
        </div>
        {totalCount > 0 && (
          <span className="text-xs font-medium text-rose-600 bg-rose-50 px-2.5 py-1 rounded-full" data-testid="birthday-count">
            {totalCount}
          </span>
        )}
      </div>

      {loading ? (
        <div className="text-center py-8 text-sm text-slate-400">Loading…</div>
      ) : totalCount === 0 ? (
        <div className="text-center py-8 text-sm text-slate-400">
          <CalendarDays className="w-8 h-8 mx-auto mb-2 text-slate-300" strokeWidth={1.5} />
          No birthdays in the next {windowDays} days
        </div>
      ) : (
        <div className="space-y-3 max-h-[280px] overflow-y-auto pr-1">
          {todays.map((e) => (
            <div
              key={e.id}
              className="flex items-center gap-3 p-3 rounded-xl bg-gradient-to-r from-rose-50 to-amber-50 border border-rose-100"
              data-testid={`birthday-today-${e.id}`}
            >
              <EmployeeAvatar employeeId={e.id} name={e.full_name} size="sm" shape="circle" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <p className="text-sm font-semibold text-slate-900 truncate">{e.full_name}</p>
                  <PartyPopper className="w-3.5 h-3.5 text-rose-500 flex-shrink-0" />
                </div>
                <p className="text-xs text-slate-500 truncate">
                  {[e.team, e.department].filter(Boolean).join(' · ') || e.designation || ''}
                </p>
              </div>
              <span className="text-[11px] font-semibold text-rose-600 bg-white px-2 py-1 rounded-md whitespace-nowrap">
                🎂 Today
              </span>
            </div>
          ))}
          {upcoming.map((e) => (
            <div
              key={e.id}
              className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-slate-50 transition-colors"
              data-testid={`birthday-upcoming-${e.id}`}
            >
              <EmployeeAvatar employeeId={e.id} name={e.full_name} size="sm" shape="circle" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900 truncate">{e.full_name}</p>
                <p className="text-xs text-slate-500 truncate">
                  {[e.team, e.department].filter(Boolean).join(' · ') || e.designation || ''}
                </p>
              </div>
              <div className="text-right whitespace-nowrap">
                <div className="text-xs font-semibold text-slate-700">{e.next_date_display || e.dob_display}</div>
                <div className="text-[10px] text-slate-400">
                  {e.days_until === 1 ? 'in 1 day' : `in ${e.days_until} days`}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default BirthdayWidget;
