import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectTrigger, SelectContent, SelectValue, SelectItem } from '../components/ui/select';
import { toast } from 'sonner';
import { AlertTriangle, Plus, Download, Search, Send, ShieldAlert, XOctagon, CheckCircle2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const LEVEL_META = {
  first:       { label: 'Warning Notice 1',            cls: 'bg-amber-100 text-amber-800 border-amber-200' },
  final:       { label: 'Final Warning',                cls: 'bg-orange-100 text-orange-800 border-orange-200' },
  termination: { label: 'Termination Action',           cls: 'bg-red-100 text-red-800 border-red-200' },
};
const STATUS_META = {
  draft: 'Draft', pending_approval: 'Pending Approval', approved: 'Approved',
  rejected: 'Rejected', issued: 'Issued', sent: 'Sent', email_failed: 'Email Failed',
  awaiting_ack: 'Awaiting Ack', acknowledged: 'Acknowledged',
  response_received: 'Response Received', under_review: 'Under Review',
  closed: 'Closed', revoked: 'Revoked', cancelled: 'Cancelled',
};
const CATEGORIES = [
  ['leave_late', 'Leave request submitted after prescribed timeline'],
  ['leave_wrong_category', 'Incorrect leave category selected'],
  ['leave_docs_missing', 'Required leave documentation not submitted'],
  ['medical_cert_missing', 'Medical certificate not submitted'],
  ['leave_email_missing', 'Leave email not submitted'],
  ['leave_email_late', 'Leave email submitted late'],
  ['leave_not_in_hrms', 'Leave request not submitted in HRMS'],
  ['hrms_request_late', 'HRMS request submitted late'],
  ['manager_not_informed', 'Reporting manager not informed'],
  ['unauthorized_absence', 'Unauthorized absence'],
  ['regularization_missing', 'Attendance regularization not submitted'],
  ['missed_punch_not_reported', 'Missed punch not reported'],
  ['repeated_late_arrival', 'Repeated late arrival'],
  ['repeated_early_departure', 'Repeated early departure'],
  ['attendance_comm_failure', 'Failure to follow attendance communication process'],
  ['other_leave_policy', 'Other Leave Policy Non-Compliance'],
  ['other_attendance_policy', 'Other Attendance Policy Non-Compliance'],
];

const StatCard = ({ icon: Icon, label, value, tone, onClick, testid }) => (
  <button onClick={onClick} data-testid={testid} className="text-left w-full">
    <Card className={`p-4 rounded-2xl border-slate-200 hover:shadow-md transition-shadow ${tone||''}`}>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">{label}</div>
          <div className="mt-1 text-2xl font-bold text-slate-800 tabular-nums">{value ?? '—'}</div>
        </div>
        {Icon && <Icon className="w-6 h-6 text-slate-400" />}
      </div>
    </Card>
  </button>
);

const StatusBadge = ({ status }) => {
  const cls = {
    draft: 'bg-slate-100 text-slate-700', pending_approval: 'bg-blue-100 text-blue-800',
    approved: 'bg-emerald-100 text-emerald-800', rejected: 'bg-rose-100 text-rose-800',
    sent: 'bg-indigo-100 text-indigo-800', awaiting_ack: 'bg-amber-100 text-amber-800',
    acknowledged: 'bg-emerald-100 text-emerald-800', closed: 'bg-slate-100 text-slate-700',
    revoked: 'bg-slate-200 text-slate-700 line-through', email_failed: 'bg-rose-100 text-rose-800',
    response_received: 'bg-cyan-100 text-cyan-800',
  }[status] || 'bg-slate-100 text-slate-700';
  return <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${cls}`}>{STATUS_META[status] || status}</span>;
};

export default function Warnings() {
  const { token, user } = useAuth();
  const H = { Authorization: `Bearer ${token}` };
  const [stats, setStats] = useState(null);
  const [list, setList] = useState({ warnings: [], total: 0 });
  const [q, setQ] = useState({ search: '', status: 'All', level: 'All' });
  const [showCreate, setShowCreate] = useState(false);
  const [detail, setDetail] = useState(null);

  const reload = useCallback(async () => {
    try {
      const [s, l] = await Promise.all([
        axios.get(`${API}/warnings/stats`, { headers: H }),
        axios.get(`${API}/warnings`, { headers: H, params: {
          search: q.search || undefined, status: q.status !== 'All' ? q.status : undefined,
          level: q.level !== 'All' ? q.level : undefined,
        } }),
      ]);
      setStats(s.data); setList(l.data);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Failed to load'); }
  }, [q.search, q.status, q.level, token]); // eslint-disable-line

  useEffect(() => { reload(); }, [reload]);

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6" data-testid="warnings-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Warning Management</h1>
          <p className="text-sm text-slate-500">Track, issue and manage employee leave & attendance policy warnings.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="rounded-xl" onClick={() => window.open(`${API}/warnings/export/csv?_=${Date.now()}`, '_blank')} data-testid="warnings-export-btn">
            <Download className="w-4 h-4 mr-1.5"/>Export CSV
          </Button>
          <Button className="rounded-xl bg-[#063c88] hover:bg-[#052e6b]" onClick={() => setShowCreate(true)} data-testid="warnings-create-btn">
            <Plus className="w-4 h-4 mr-1.5"/>Create Warning
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard testid="stat-under-warning" icon={AlertTriangle} label="Under Warning" value={stats?.employees_under_warning} onClick={() => setQ(s => ({ ...s, status: 'awaiting_ack' }))}/>
        <StatCard testid="stat-warning1" icon={ShieldAlert} label="Warning Notice 1" value={stats?.warning_notice_1} onClick={() => setQ(s => ({ ...s, level: 'first' }))}/>
        <StatCard testid="stat-final" icon={ShieldAlert} label="Final Warnings" value={stats?.final_warnings} onClick={() => setQ(s => ({ ...s, level: 'final' }))}/>
        <StatCard testid="stat-termination" icon={XOctagon} label="Termination Actions" value={stats?.termination_actions} onClick={() => setQ(s => ({ ...s, level: 'termination' }))}/>
        <StatCard testid="stat-awaiting" icon={AlertTriangle} label="Awaiting Ack" value={stats?.awaiting_acknowledgement} onClick={() => setQ(s => ({ ...s, status: 'awaiting_ack' }))}/>
        <StatCard testid="stat-overdue" icon={AlertTriangle} label="Overdue" value={stats?.overdue_followups} onClick={() => setQ(s => ({ ...s, status: 'awaiting_ack' }))}/>
      </div>

      {/* Escalation banner */}
      <Card className="p-4 rounded-2xl border-slate-200 bg-gradient-to-r from-slate-50 to-white">
        <div className="flex items-center gap-3 flex-wrap text-sm">
          <span className="px-3 py-1 rounded-lg bg-amber-100 text-amber-800 font-semibold">1st · Warning Notice 1</span>
          <span className="text-slate-400">→</span>
          <span className="px-3 py-1 rounded-lg bg-orange-100 text-orange-800 font-semibold">2nd · Final Warning</span>
          <span className="text-slate-400">→</span>
          <span className="px-3 py-1 rounded-lg bg-red-100 text-red-800 font-semibold">3rd · Termination Action</span>
          <span className="ml-auto text-xs text-slate-500 italic">Framework applies to Leave & Attendance Policy non-compliance.</span>
        </div>
      </Card>

      {/* Filters */}
      <Card className="p-3 rounded-2xl border-slate-200">
        <div className="flex flex-wrap gap-2 items-center">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-slate-400"/>
            <Input placeholder="Search employee, ref, dept…" value={q.search} onChange={e => setQ(s => ({...s, search: e.target.value}))} className="pl-8 rounded-lg" data-testid="warnings-search"/>
          </div>
          <Select value={q.status} onValueChange={v => setQ(s => ({...s, status: v}))}>
            <SelectTrigger className="w-48 rounded-lg"><SelectValue/></SelectTrigger>
            <SelectContent><SelectItem value="All">All Statuses</SelectItem>
              {Object.entries(STATUS_META).map(([k,v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={q.level} onValueChange={v => setQ(s => ({...s, level: v}))}>
            <SelectTrigger className="w-48 rounded-lg"><SelectValue/></SelectTrigger>
            <SelectContent><SelectItem value="All">All Levels</SelectItem>
              {Object.entries(LEVEL_META).map(([k,v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}
            </SelectContent>
          </Select>
          {(q.search || q.status !== 'All' || q.level !== 'All') && (
            <Button variant="outline" size="sm" onClick={() => setQ({ search: '', status: 'All', level: 'All' })}>Clear</Button>
          )}
        </div>
      </Card>

      {/* Table */}
      <Card className="rounded-2xl border-slate-200 overflow-hidden">
        {list.warnings.length === 0 ? (
          <div className="py-16 text-center">
            <ShieldAlert className="w-10 h-10 text-slate-300 mx-auto"/>
            <p className="mt-3 text-slate-700 font-medium">No warning records found.</p>
            <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">Create a warning case when an employee has failed to follow the Leave and Attendance Policy.</p>
            <Button className="mt-4 rounded-xl bg-[#063c88] hover:bg-[#052e6b]" onClick={() => setShowCreate(true)}><Plus className="w-4 h-4 mr-1.5"/>Create Warning</Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wider">
                <tr>
                  <th className="text-left px-4 py-3">Reference</th>
                  <th className="text-left px-4 py-3">Employee</th>
                  <th className="text-left px-4 py-3">Department</th>
                  <th className="text-left px-4 py-3">Level</th>
                  <th className="text-left px-4 py-3">Incident Date</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-left px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {list.warnings.map(w => (
                  <tr key={w.id} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-xs text-slate-700">{w.warning_reference || <span className="text-slate-400">—</span>}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-800">{w.employee_snapshot?.full_name}</div>
                      <div className="text-xs text-slate-500">{w.employee_snapshot?.emp_id}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{w.employee_snapshot?.department} <span className="text-slate-400">·</span> <span className="text-slate-500">{w.employee_snapshot?.designation}</span></td>
                    <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${LEVEL_META[w.warning_level]?.cls || ''}`}>{LEVEL_META[w.warning_level]?.label}</span></td>
                    <td className="px-4 py-3 text-slate-700">{w.incident_date}</td>
                    <td className="px-4 py-3"><StatusBadge status={w.status}/></td>
                    <td className="px-4 py-3">
                      <Button size="sm" variant="outline" className="rounded-lg" onClick={() => setDetail(w.id)} data-testid={`view-warning-${w.id}`}>View</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {showCreate && <CreateWarningDialog onClose={() => setShowCreate(false)} onCreated={reload}/>}
      {detail && <WarningDetailDialog id={detail} onClose={() => setDetail(null)} onChanged={reload}/>}
    </div>
  );
}

function CreateWarningDialog({ onClose, onCreated }) {
  const { token } = useAuth();
  const H = { Authorization: `Bearer ${token}` };
  const [empSearch, setEmpSearch] = useState('');
  const [empResults, setEmpResults] = useState([]);
  const [emp, setEmp] = useState(null);
  const [history, setHistory] = useState(null);
  const [form, setForm] = useState({
    incident_date: '', incident_category: '', incident_description: '',
    corrective_action: '', warning_issue_date: new Date().toISOString().slice(0,10),
    acknowledgement_due_date: '', level_override_reason: '',
  });
  const [level, setLevel] = useState(null); // overrides suggestion

  const searchEmps = async (v) => {
    setEmpSearch(v);
    if (v.length < 2) return setEmpResults([]);
    try {
      const r = await axios.get(`${API}/employees`, { headers: H, params: { search: v, limit: 8 }});
      setEmpResults(r.data.employees || []);
    } catch {}
  };
  const pickEmp = async (e) => {
    setEmp(e); setEmpResults([]); setEmpSearch(e.full_name);
    const r = await axios.get(`${API}/warnings/employee-history/${e.id}`, { headers: H });
    setHistory(r.data);
  };
  const suggested = history?.suggested_level;
  const chosenLevel = level || suggested;

  const submit = async (asDraft) => {
    if (!emp) return toast.error('Select an employee');
    if (!form.incident_date || !form.incident_category || !form.incident_description)
      return toast.error('Fill incident date, category and description');
    if (level && level !== suggested && !form.level_override_reason)
      return toast.error('Level override requires a reason');
    try {
      const r = await axios.post(`${API}/warnings`, {
        employee_id: emp.id, warning_level: chosenLevel, ...form,
      }, { headers: H });
      if (!asDraft) {
        await axios.post(`${API}/warnings/${r.data.id}/submit`, {}, { headers: H });
      }
      toast.success(asDraft ? 'Draft saved' : 'Submitted for approval');
      onCreated(); onClose();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Create Warning</DialogTitle></DialogHeader>
        <div className="space-y-4">
          {/* Employee */}
          <div>
            <label className="text-xs font-semibold text-slate-600">Employee</label>
            <Input placeholder="Search by name, ID, email…" value={empSearch} onChange={e => searchEmps(e.target.value)} className="mt-1 rounded-lg" data-testid="create-emp-search"/>
            {empResults.length > 0 && (
              <div className="mt-1 border rounded-lg divide-y max-h-52 overflow-y-auto">
                {empResults.map(e => (
                  <button key={e.id} className="w-full text-left px-3 py-2 hover:bg-slate-50" onClick={() => pickEmp(e)}>
                    <div className="text-sm font-medium">{e.full_name}</div>
                    <div className="text-xs text-slate-500">{e.emp_id || e.custom_employee_id} · {e.department} · {e.designation}</div>
                  </button>
                ))}
              </div>
            )}
            {emp && history && (
              <div className="mt-2 p-3 rounded-lg bg-slate-50 text-sm">
                <div className="font-semibold">{emp.full_name} <span className="text-slate-500 font-normal">· {emp.department} · {emp.designation}</span></div>
                <div className="text-xs text-slate-600 mt-1">Prior valid warnings: <b>{history.valid_prior_count}</b> · System-suggested next level: <b className="text-amber-700">{LEVEL_META[history.suggested_level]?.label}</b></div>
              </div>
            )}
          </div>

          {/* Incident */}
          <div className="grid grid-cols-2 gap-3">
            <div><label className="text-xs font-semibold text-slate-600">Incident Date *</label>
              <Input type="date" value={form.incident_date} onChange={e => setForm({...form, incident_date: e.target.value})} className="mt-1 rounded-lg"/></div>
            <div><label className="text-xs font-semibold text-slate-600">Issue Date *</label>
              <Input type="date" value={form.warning_issue_date} onChange={e => setForm({...form, warning_issue_date: e.target.value})} className="mt-1 rounded-lg"/></div>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600">Incident Category *</label>
            <Select value={form.incident_category} onValueChange={v => setForm({...form, incident_category: v})}>
              <SelectTrigger className="mt-1 rounded-lg"><SelectValue placeholder="Choose…"/></SelectTrigger>
              <SelectContent>{CATEGORIES.map(([k, l]) => <SelectItem key={k} value={k}>{l}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600">Incident Description *</label>
            <textarea className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm" rows={3} value={form.incident_description} onChange={e => setForm({...form, incident_description: e.target.value})}/>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600">Required Corrective Action</label>
            <textarea className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm" rows={2} value={form.corrective_action} onChange={e => setForm({...form, corrective_action: e.target.value})}/>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600">Acknowledgement Due Date</label>
            <Input type="date" value={form.acknowledgement_due_date} onChange={e => setForm({...form, acknowledgement_due_date: e.target.value})} className="mt-1 rounded-lg"/>
          </div>

          {/* Level */}
          {suggested && (
            <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
              <label className="text-xs font-semibold text-slate-600">Warning Level</label>
              <Select value={level || suggested} onValueChange={setLevel}>
                <SelectTrigger className="mt-1 rounded-lg bg-white"><SelectValue/></SelectTrigger>
                <SelectContent>{Object.entries(LEVEL_META).map(([k,v]) => <SelectItem key={k} value={k}>{v.label}{k===suggested?' (suggested)':''}</SelectItem>)}</SelectContent>
              </Select>
              {level && level !== suggested && (
                <div className="mt-2"><label className="text-xs font-semibold">Override reason *</label>
                  <Input value={form.level_override_reason} onChange={e => setForm({...form, level_override_reason: e.target.value})} className="mt-1 rounded-lg bg-white"/></div>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 pt-4 border-t sticky bottom-0 bg-white">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button variant="outline" onClick={() => submit(true)}>Save Draft</Button>
          <Button className="bg-[#063c88] hover:bg-[#052e6b]" onClick={() => submit(false)} data-testid="create-submit">Submit for Approval</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function WarningDetailDialog({ id, onClose, onChanged }) {
  const { token } = useAuth();
  const H = { Authorization: `Bearer ${token}` };
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try { const r = await axios.get(`${API}/warnings/${id}`, { headers: H }); setData(r.data); }
    catch (e) { toast.error(e?.response?.data?.detail || 'Load failed'); onClose(); }
  }, [id]); // eslint-disable-line
  useEffect(() => { load(); }, [load]);

  const act = async (url, body, msg) => {
    setBusy(true);
    try { await axios.post(`${API}/warnings/${id}${url}`, body || {}, { headers: H }); toast.success(msg); await load(); onChanged(); }
    catch (e) { toast.error(e?.response?.data?.detail || 'Action failed'); }
    finally { setBusy(false); }
  };
  if (!data) return null;
  const e = data.employee_snapshot || {};
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="warning-detail">
        <DialogHeader><DialogTitle className="flex items-center gap-2">Warning · <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${LEVEL_META[data.warning_level]?.cls}`}>{LEVEL_META[data.warning_level]?.label}</span> <StatusBadge status={data.status}/></DialogTitle></DialogHeader>
        <div className="text-sm space-y-4">
          <Card className="p-4 rounded-xl">
            <div className="font-semibold">{e.full_name}</div>
            <div className="text-xs text-slate-500">{e.emp_id} · {e.department} · {e.designation} · {e.official_email}</div>
            <div className="text-xs text-slate-500 mt-1">Reference: <b className="text-slate-700">{data.warning_reference || '—'}</b></div>
          </Card>
          <div className="grid grid-cols-2 gap-4">
            <div><div className="text-xs text-slate-500">Incident Date</div><div className="font-medium">{data.incident_date}</div></div>
            <div><div className="text-xs text-slate-500">Issue Date</div><div className="font-medium">{data.warning_issue_date || '—'}</div></div>
            <div><div className="text-xs text-slate-500">Category</div><div className="font-medium">{data.incident_category?.replace(/_/g, ' ')}</div></div>
            <div><div className="text-xs text-slate-500">Ack Due</div><div className="font-medium">{data.acknowledgement_due_date || '—'}</div></div>
          </div>
          <div><div className="text-xs text-slate-500">Description</div><div className="mt-1 p-2 bg-slate-50 rounded-lg">{data.incident_description}</div></div>
          {data.corrective_action && <div><div className="text-xs text-slate-500">Corrective Action</div><div className="mt-1 p-2 bg-slate-50 rounded-lg">{data.corrective_action}</div></div>}

          {/* Actions row — role-gated by backend; we render optimistically */}
          <div className="flex flex-wrap gap-2 pt-2 border-t">
            {data.status === 'pending_approval' && <>
              <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" disabled={busy} onClick={() => act('/approve', {}, 'Approved')}><CheckCircle2 className="w-4 h-4 mr-1"/>Approve</Button>
              <Button size="sm" variant="outline" className="text-rose-600 border-rose-200" disabled={busy} onClick={() => { const c = prompt('Rejection reason:'); if (c) act('/reject', { comments: c }, 'Rejected'); }}>Reject</Button>
            </>}
            {(data.status === 'approved' || data.status === 'email_failed') &&
              <Button size="sm" className="bg-[#063c88] hover:bg-[#052e6b]" disabled={busy} onClick={() => act('/send-email', {}, 'Email sent')} data-testid="send-email-btn"><Send className="w-4 h-4 mr-1"/>Send Warning Email</Button>}
            {['sent','awaiting_ack','acknowledged','response_received'].includes(data.status) &&
              <Button size="sm" variant="outline" disabled={busy} onClick={() => { const c = prompt('Closure comments:'); if (c) act('/close', { comments: c }, 'Closed'); }}>Close Case</Button>}
            {!['revoked','cancelled','closed'].includes(data.status) &&
              <Button size="sm" variant="outline" className="text-slate-600" disabled={busy} onClick={() => { const c = prompt('Revocation reason:'); if (c) act('/revoke', { reason: c }, 'Revoked'); }}>Revoke</Button>}
          </div>

          {/* Timeline */}
          <div>
            <div className="text-sm font-semibold text-slate-700 mb-2">Timeline</div>
            <ol className="relative space-y-2 pl-5 border-l-2 border-slate-100">
              {(data.audit_log || []).slice().reverse().map(a => (
                <li key={a.id} className="relative">
                  <span className="absolute -left-[26px] top-1 w-3 h-3 rounded-full bg-[#063c88] ring-4 ring-white"/>
                  <div className="text-xs text-slate-500">{new Date(a.created_at).toLocaleString('en-IN')}</div>
                  <div className="font-medium text-slate-800 capitalize">{a.action.replace(/_/g, ' ')}</div>
                  {a.description && <div className="text-xs text-slate-600">{a.description}</div>}
                  <div className="text-[11px] text-slate-400">by {a.performed_by_name || 'system'} ({a.performed_by_role})</div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
