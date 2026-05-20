import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Mail,
  Send,
  Loader2,
  ShieldAlert,
  CheckCircle2,
  Clock,
  Camera,
  Search,
  RefreshCw,
} from 'lucide-react';
import EmployeeAvatar from '../components/EmployeeAvatar';
import { Input } from '../components/ui/input';
import { Switch } from '../components/ui/switch';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const FILTERS = [
  { key: 'all', label: 'All Employees' },
  { key: 'incomplete', label: 'Incomplete' },
  { key: 'completed', label: '100% Completed' },
  { key: 'no_photo', label: 'No Profile Photo' },
  { key: 'reminder_pending', label: 'Reminder Pending' },
  { key: 'success_mail_pending', label: 'Success Mail Pending' },
];

const ProgressBar = ({ percent }) => {
  const color =
    percent >= 100 ? 'bg-emerald-500'
      : percent >= 75 ? 'bg-emerald-400'
      : percent >= 40 ? 'bg-amber-500'
      : 'bg-rose-500';
  return (
    <div className="w-full">
      <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
        <div className={`h-2 ${color} rounded-full transition-all`} style={{ width: `${percent}%` }} />
      </div>
      <div className="mt-1 text-xs text-slate-500">{percent}%</div>
    </div>
  );
};

const StatusPill = ({ row }) => {
  if (row.is_complete) {
    return (
      <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200" data-testid="oc-status-complete">
        <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Completed
      </Badge>
    );
  }
  return (
    <Badge className="bg-amber-100 text-amber-700 border-amber-200" data-testid="oc-status-pending">
      <Clock className="w-3.5 h-3.5 mr-1" /> Pending
    </Badge>
  );
};

const fmtDate = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
  } catch {
    return iso;
  }
};

const OnboardingCompletion = () => {
  const { getAuthHeaders } = useAuth();
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('incomplete');
  const [search, setSearch] = useState('');

  const [settings, setSettings] = useState({
    enable_bulk_onboarding_mail: false,
    pilot_email: 'rishi.nayak@blubridge.com',
  });
  const [savingSettings, setSavingSettings] = useState(false);
  const [running, setRunning] = useState(false);
  const [sendingRow, setSendingRow] = useState(null); // employee_id being sent

  const fetchRows = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      if (filter && filter !== 'all') params.status = filter;
      if (search.trim()) params.search = search.trim();
      const res = await axios.get(`${API}/admin/onboarding-completion/dashboard`, {
        headers: getAuthHeaders(),
        params,
      });
      setRows(res.data?.rows || []);
      setSummary(res.data?.summary || null);
    } catch (e) {
      toast.error('Failed to load completion dashboard');
    } finally {
      setLoading(false);
    }
  }, [filter, search, getAuthHeaders]);

  const fetchSettings = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/admin/onboarding-completion/settings`, {
        headers: getAuthHeaders(),
      });
      if (res.data) {
        setSettings({
          enable_bulk_onboarding_mail: !!res.data.enable_bulk_onboarding_mail,
          pilot_email: res.data.pilot_email || 'rishi.nayak@blubridge.com',
        });
      }
    } catch (e) {
      /* non-fatal */
    }
  }, [getAuthHeaders]);

  useEffect(() => {
    fetchRows();
  }, [fetchRows]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const saveSettings = useCallback(async (patch) => {
    try {
      setSavingSettings(true);
      const res = await axios.put(
        `${API}/admin/onboarding-completion/settings`,
        patch,
        { headers: getAuthHeaders() }
      );
      setSettings({
        enable_bulk_onboarding_mail: !!res.data.enable_bulk_onboarding_mail,
        pilot_email: res.data.pilot_email || 'rishi.nayak@blubridge.com',
      });
      toast.success('Settings updated');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to save settings');
    } finally {
      setSavingSettings(false);
    }
  }, [getAuthHeaders]);

  const onToggleBulk = (val) => {
    if (val) {
      const ok = window.confirm(
        'Enable BULK onboarding reminder emails to ALL incomplete employees?\n\n'
        + 'This will start sending reminder emails directly to each employee every 48 hours. '
        + 'Make sure your pilot run with ' + settings.pilot_email + ' was successful first.'
      );
      if (!ok) return;
    }
    saveSettings({ enable_bulk_onboarding_mail: val });
  };

  const runAllNow = async () => {
    try {
      setRunning(true);
      const res = await axios.post(
        `${API}/admin/onboarding-completion/run-now`,
        {},
        { headers: getAuthHeaders() }
      );
      const d = res.data || {};
      toast.success(
        `Scan complete — Reminders: ${d.reminders_sent || 0}, Success: ${d.success_sent || 0}, Skipped: ${d.skipped || 0} (${d.pilot_mode ? 'PILOT' : 'BULK'} mode)`,
        { duration: 6000 }
      );
      fetchRows();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Run failed');
    } finally {
      setRunning(false);
    }
  };

  const sendOne = async (row) => {
    try {
      setSendingRow(row.employee_id);
      const res = await axios.post(
        `${API}/admin/onboarding-completion/run-now`,
        { employee_id: row.employee_id },
        { headers: getAuthHeaders() }
      );
      const d = res.data || {};
      if (d.reminders_sent || d.success_sent) {
        toast.success(`Email dispatched (${d.pilot_mode ? 'PILOT → ' + settings.pilot_email : 'to employee'})`);
      } else {
        toast.info('No email sent (already complete or recently sent)');
      }
      fetchRows();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Send failed');
    } finally {
      setSendingRow(null);
    }
  };

  const filteredRows = useMemo(() => rows, [rows]);

  return (
    <div className="space-y-6 p-6" data-testid="onboarding-completion-page">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Onboarding &amp; Profile Completion</h1>
          <p className="text-sm text-slate-500 mt-1">
            Track onboarding documents and profile photo completion. Automated reminder emails fire every 48 hours per employee
            until both reach 100%, then a one-time success email is sent.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={fetchRows}
            data-testid="oc-refresh-btn"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            onClick={runAllNow}
            disabled={running}
            className="bg-[#063c88] hover:bg-[#04306d]"
            data-testid="oc-run-now-btn"
          >
            {running ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Send className="w-4 h-4 mr-2" />
            )}
            Run Now (Bypass 48h Cadence)
          </Button>
        </div>
      </div>

      {/* Pilot / Bulk control panel */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="p-5 border-b border-slate-100 flex items-center gap-2">
          <Mail className="w-4 h-4 text-[#063c88]" />
          <div className="font-semibold text-slate-800">Email Dispatch Configuration</div>
        </div>
        <div className="p-5 grid md:grid-cols-2 gap-6">
          <div className="space-y-3">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Phase 1 — Pilot Recipient
            </label>
            <Input
              type="email"
              value={settings.pilot_email}
              onChange={(e) => setSettings((s) => ({ ...s, pilot_email: e.target.value }))}
              onBlur={() => saveSettings({ pilot_email: settings.pilot_email })}
              placeholder="rishi.nayak@blubridge.com"
              disabled={savingSettings}
              data-testid="oc-pilot-email-input"
            />
            <p className="text-xs text-slate-500">
              While bulk is disabled, ALL reminder and success emails will be redirected to this address for safe testing.
            </p>
          </div>

          <div className="space-y-3">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Bulk Dispatch Toggle
            </label>
            <div className="flex items-center gap-3 p-3 rounded-lg border border-slate-200 bg-slate-50">
              <Switch
                checked={settings.enable_bulk_onboarding_mail}
                onCheckedChange={onToggleBulk}
                disabled={savingSettings}
                data-testid="oc-bulk-toggle"
              />
              <div className="flex-1">
                <div className="text-sm font-medium text-slate-800">
                  enable_bulk_onboarding_mail = {String(settings.enable_bulk_onboarding_mail)}
                </div>
                <div className="text-xs text-slate-500">
                  {settings.enable_bulk_onboarding_mail
                    ? 'LIVE — reminders deliver directly to each employee.'
                    : 'PILOT — all emails route to the pilot recipient only.'}
                </div>
              </div>
              {!settings.enable_bulk_onboarding_mail && (
                <ShieldAlert className="w-5 h-5 text-amber-500" />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Summary chips */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3" data-testid="oc-summary">
          <SummaryCard label="Total" value={summary.total} active={filter === 'all'} onClick={() => setFilter('all')} />
          <SummaryCard label="Incomplete" value={summary.incomplete} tone="amber" active={filter === 'incomplete'} onClick={() => setFilter('incomplete')} />
          <SummaryCard label="Completed" value={summary.completed} tone="emerald" active={filter === 'completed'} onClick={() => setFilter('completed')} />
          <SummaryCard label="No Photo" value={summary.no_photo} tone="rose" active={filter === 'no_photo'} onClick={() => setFilter('no_photo')} />
          <SummaryCard label="Reminder Due" value={summary.reminder_pending} tone="sky" active={filter === 'reminder_pending'} onClick={() => setFilter('reminder_pending')} />
          <SummaryCard label="Success Pending" value={summary.success_pending} tone="violet" active={filter === 'success_mail_pending'} onClick={() => setFilter('success_mail_pending')} />
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 justify-between">
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFilter(f.key)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                filter === f.key
                  ? 'bg-[#063c88] text-white border-[#063c88]'
                  : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
              }`}
              data-testid={`oc-filter-${f.key}`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name, EMP ID, email…"
            className="pl-9 w-72"
            data-testid="oc-search-input"
          />
        </div>
      </div>

      {/* Table */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left px-4 py-3">Employee</th>
                <th className="text-left px-4 py-3">Overall</th>
                <th className="text-left px-4 py-3">Onboarding</th>
                <th className="text-left px-4 py-3">Profile Photo</th>
                <th className="text-left px-4 py-3">Last Reminder</th>
                <th className="text-center px-4 py-3">Sent</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Success Mail</th>
                <th className="text-right px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-slate-400" data-testid="oc-loading">
                    <Loader2 className="inline w-4 h-4 mr-2 animate-spin" />
                    Loading…
                  </td>
                </tr>
              )}
              {!loading && filteredRows.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-slate-400" data-testid="oc-empty">
                    No employees match this filter.
                  </td>
                </tr>
              )}
              {!loading && filteredRows.map((row) => (
                <tr key={row.employee_id} className="hover:bg-slate-50/60" data-testid={`oc-row-${row.emp_id || row.employee_id}`}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <EmployeeAvatar
                        employeeId={row.employee_id}
                        displayName={row.full_name}
                        src={row.avatar}
                        size="sm"
                      />
                      <div>
                        <div className="font-medium text-slate-800">{row.full_name}</div>
                        <div className="text-xs text-slate-500">{row.emp_id} · {row.department}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 min-w-[140px]"><ProgressBar percent={row.overall_percent} /></td>
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium text-slate-800">{row.onboarding_percent}%</div>
                    <div className="text-xs text-slate-500 capitalize">{row.onboarding_status}</div>
                    {row.missing_sections?.length > 0 && (
                      <div className="text-[11px] text-rose-600 mt-1">
                        Missing: {row.missing_sections.map((m) => m.label).join(', ')}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {row.profile_photo_uploaded ? (
                      <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200">
                        <Camera className="w-3.5 h-3.5 mr-1" /> Uploaded
                      </Badge>
                    ) : (
                      <Badge className="bg-slate-100 text-slate-600 border-slate-200">
                        <Camera className="w-3.5 h-3.5 mr-1" /> Not uploaded
                      </Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {fmtDate(row.last_reminder_sent_at)}
                    {row.hours_since_last_reminder != null && (
                      <div className="text-[11px] text-slate-400">{row.hours_since_last_reminder}h ago</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center font-semibold text-slate-800">{row.reminder_count}</td>
                  <td className="px-4 py-3"><StatusPill row={row} /></td>
                  <td className="px-4 py-3 text-xs">
                    {row.completion_success_mail_sent ? (
                      <span className="text-emerald-700">✓ {fmtDate(row.completion_success_mail_sent_at)}</span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => sendOne(row)}
                      disabled={sendingRow === row.employee_id}
                      data-testid={`oc-send-${row.emp_id || row.employee_id}`}
                    >
                      {sendingRow === row.employee_id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Send className="w-3.5 h-3.5" />
                      )}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

const SummaryCard = ({ label, value, tone = 'slate', active, onClick }) => {
  const toneClasses = {
    slate: 'border-slate-200 bg-white',
    amber: 'border-amber-200 bg-amber-50',
    emerald: 'border-emerald-200 bg-emerald-50',
    rose: 'border-rose-200 bg-rose-50',
    sky: 'border-sky-200 bg-sky-50',
    violet: 'border-violet-200 bg-violet-50',
  }[tone] || 'border-slate-200 bg-white';

  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl border p-4 text-left transition-all ${toneClasses} ${
        active ? 'ring-2 ring-[#063c88]/50' : 'hover:shadow-sm'
      }`}
      data-testid={`oc-summary-${label.toLowerCase().replace(/ /g, '-')}`}
    >
      <div className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-bold text-slate-800">{value ?? 0}</div>
    </button>
  );
};

export default OnboardingCompletion;
