import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { CheckCircle2, XCircle, Clock3, RefreshCw, Mail, ShieldAlert, X } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const RESULT_STYLES = {
  success: { icon: CheckCircle2, cls: 'bg-emerald-50 text-emerald-700 border border-emerald-200', label: 'Success' },
  failed: { icon: XCircle, cls: 'bg-rose-50 text-rose-700 border border-rose-200', label: 'Failed' },
  skipped: { icon: Clock3, cls: 'bg-slate-100 text-slate-600 border border-slate-200', label: 'Skipped' },
};

const formatRunAt = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
};

const ResultPill = ({ result }) => {
  if (!result) return <span className="text-slate-400 text-sm">—</span>;
  const cfg = RESULT_STYLES[result] || { icon: Clock3, cls: 'bg-slate-100 text-slate-600 border border-slate-200', label: result };
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.cls}`} data-testid={`cron-result-${result}`}>
      <Icon className="w-3.5 h-3.5" />
      {cfg.label}
    </span>
  );
};

const EMAIL_RE = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

const CCEmailEditor = ({ jobName, initial, onSave }) => {
  const [tags, setTags] = useState(initial || []);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => { setTags(initial || []); }, [initial]);

  const dirty = JSON.stringify(tags) !== JSON.stringify(initial || []);

  const addTag = (raw) => {
    const e = String(raw || '').trim();
    if (!e) return;
    if (!EMAIL_RE.test(e)) { toast.error(`Invalid email: ${e}`); return; }
    if (tags.some((t) => t.toLowerCase() === e.toLowerCase())) { toast.error('Already added'); return; }
    setTags([...tags, e]);
    setDraft('');
  };

  const onKey = (ev) => {
    if (ev.key === 'Enter' || ev.key === ',' || ev.key === ';' || ev.key === ' ') {
      ev.preventDefault();
      addTag(draft);
    } else if (ev.key === 'Backspace' && !draft && tags.length) {
      setTags(tags.slice(0, -1));
    }
  };

  const onPaste = (ev) => {
    const text = ev.clipboardData?.getData('text');
    if (text && /[,;\s]/.test(text)) {
      ev.preventDefault();
      const parts = text.split(/[,;\s]+/).map((s) => s.trim()).filter(Boolean);
      const next = [...tags];
      parts.forEach((p) => {
        if (EMAIL_RE.test(p) && !next.some((t) => t.toLowerCase() === p.toLowerCase())) {
          next.push(p);
        }
      });
      setTags(next);
    }
  };

  const removeTag = (i) => setTags(tags.filter((_, idx) => idx !== i));

  const save = async () => {
    setSaving(true);
    try {
      await onSave(tags);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-w-[260px]">
      <div className="flex flex-wrap items-center gap-1.5 px-2 py-1.5 border border-slate-200 rounded-lg bg-white focus-within:border-[#063c88] focus-within:ring-1 focus-within:ring-[#063c88]/30 transition">
        {tags.length === 0 && !draft && (
          <span className="text-slate-400 text-xs">—</span>
        )}
        {tags.map((t, i) => (
          <span key={`${t}-${i}`} className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-md text-xs" data-testid={`cc-tag-${jobName}-${i}`}>
            {t}
            <button type="button" onClick={() => removeTag(i)} className="hover:text-rose-600" data-testid={`cc-remove-${jobName}-${i}`}><X className="w-3 h-3" /></button>
          </span>
        ))}
        <input
          type="text"
          className="flex-1 min-w-[140px] outline-none bg-transparent text-xs py-0.5"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKey}
          onBlur={() => draft && addTag(draft)}
          onPaste={onPaste}
          placeholder={tags.length === 0 ? 'Enter CC emails (comma separated)' : 'Add another'}
          data-testid={`cc-input-${jobName}`}
        />
      </div>
      {dirty && (
        <div className="mt-1.5 flex justify-end gap-2">
          <button type="button" onClick={() => setTags(initial || [])} className="text-xs text-slate-500 hover:text-slate-700">Cancel</button>
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="text-xs bg-[#063c88] text-white px-2.5 py-0.5 rounded-md hover:bg-[#0a4ea8] disabled:opacity-50"
            data-testid={`cc-save-${jobName}`}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      )}
    </div>
  );
};

const CronManagement = () => {
  const { getAuthHeaders, user } = useAuth();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState({});  // job_name -> bool (in-flight)

  const isAdmin = user?.role === 'hr' || user?.role === 'system_admin';

  const fetchJobs = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/admin/cron-settings`, { headers: getAuthHeaders() });
      setJobs(res.data?.jobs || []);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load cron settings');
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  useEffect(() => { fetchJobs(); }, [fetchJobs]);

  const toggleJob = async (job, nextEnabled) => {
    // Optimistic UI — flip immediately, revert on failure
    setJobs((prev) => prev.map((j) => (j.job_name === job.job_name ? { ...j, enabled: nextEnabled } : j)));
    setPending((p) => ({ ...p, [job.job_name]: true }));
    try {
      await axios.put(
        `${API}/admin/cron-settings/${job.job_name}`,
        { enabled: nextEnabled },
        { headers: getAuthHeaders() }
      );
      toast.success(nextEnabled ? 'Cron Enabled Successfully' : 'Cron Disabled Successfully');
    } catch (err) {
      setJobs((prev) => prev.map((j) => (j.job_name === job.job_name ? { ...j, enabled: !nextEnabled } : j)));
      toast.error(err.response?.data?.detail || 'Failed to update cron');
    } finally {
      setPending((p) => ({ ...p, [job.job_name]: false }));
    }
  };

  const runJob = async (job) => {
    try {
      await axios.post(`${API}/email-jobs/${job.job_name}/run`, {}, { headers: getAuthHeaders() });
      toast.success(`Triggered ${job.label}`);
      // Refresh after a beat to capture last-run state
      setTimeout(fetchJobs, 4000);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to trigger');
    }
  };

  const saveCC = async (job, cc_emails) => {
    try {
      const res = await axios.put(
        `${API}/admin/cron-settings/${job.job_name}/cc`,
        { cc_emails },
        { headers: getAuthHeaders() }
      );
      toast.success('CC emails updated successfully');
      // Update local state without full refresh
      setJobs((prev) => prev.map((j) => (j.job_name === job.job_name ? { ...j, cc_emails: res.data.cc_emails || [] } : j)));
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save CC emails');
    }
  };

  if (!isAdmin) {
    return (
      <div className="card-premium p-12 flex flex-col items-center justify-center text-center" data-testid="cron-mgmt-no-access">
        <ShieldAlert className="w-12 h-12 text-rose-500 mb-3" />
        <h2 className="text-lg font-semibold text-slate-900">Access Denied</h2>
        <p className="text-sm text-slate-500 mt-1">Only administrators can view this page.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="cron-management-page">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Cron Management</h1>
          <p className="text-sm text-slate-500 mt-1">Control automated email cron jobs. Disabling stops emails immediately; enabling resumes without delay.</p>
        </div>
        <Button variant="outline" onClick={fetchJobs} data-testid="cron-refresh-btn">
          <RefreshCw className="w-4 h-4 mr-2" /> Refresh
        </Button>
      </div>

      <div className="card-premium overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-10 h-10 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-premium">
              <thead>
                <tr>
                  <th>Cron Name</th>
                  <th>Schedule</th>
                  <th className="text-center">Status</th>
                  {/* CC column DISABLED per policy (task id=r9m2kq). Kept commented
                      so it can be restored without reconstructing the JSX. */}
                  {/* <th>CC Emails</th> */}
                  <th>Last Execution</th>
                  <th>Last Result</th>
                  <th className="text-right pr-6">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.length === 0 ? (
                  <tr><td colSpan="6" className="text-center py-12 text-slate-500">No cron jobs configured</td></tr>
                ) : jobs.map((j) => (
                  <tr key={j.job_name} data-testid={`cron-row-${j.job_name}`}>
                    <td>
                      <div className="flex items-center gap-3">
                        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${j.enabled ? 'bg-[#063c88]/10 text-[#063c88]' : 'bg-slate-100 text-slate-400'}`}>
                          <Mail className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="font-semibold text-slate-900">{j.label}</div>
                          <div className="text-xs text-slate-500">{j.scope === 'today' ? "Runs on today's data" : "Runs on yesterday's data"}</div>
                        </div>
                      </div>
                    </td>
                    <td className="text-slate-600 text-sm">{j.schedule}</td>
                    <td className="text-center">
                      <div className="flex items-center justify-center gap-2">
                        <Switch
                          checked={!!j.enabled}
                          disabled={!!pending[j.job_name]}
                          onCheckedChange={(v) => toggleJob(j, v)}
                          data-testid={`cron-toggle-${j.job_name}`}
                        />
                        <Badge className={j.enabled ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-500 border border-slate-200'}>
                          {j.enabled ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </div>
                    </td>
                    {/* CC Emails cell DISABLED per policy (task id=r9m2kq).
                        Editor component preserved for easy restoration. */}
                    {/* <td>
                      <CCEmailEditor
                        jobName={j.job_name}
                        initial={j.cc_emails || []}
                        onSave={(emails) => saveCC(j, emails)}
                      />
                    </td> */}
                    <td className="text-slate-600 text-sm">{formatRunAt(j.last_run_at)}</td>
                    <td>
                      <ResultPill result={j.last_result} />
                      {j.last_error ? (
                        <div className="text-xs text-rose-500 mt-1 max-w-[260px] truncate" title={j.last_error}>{j.last_error}</div>
                      ) : null}
                    </td>
                    <td className="text-right pr-6">
                      <Button size="sm" variant="outline" onClick={() => runJob(j)} disabled={!j.enabled} data-testid={`cron-run-${j.job_name}`}>
                        Run Now
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default CronManagement;
