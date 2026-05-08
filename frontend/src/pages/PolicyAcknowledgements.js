import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  FileText, Loader2, CheckCircle2, Clock, Search, Download,
  ShieldCheck, Users, ChevronRight, RefreshCw,
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const getAuth = () => ({ Authorization: `Bearer ${localStorage.getItem('blubridge_token')}` });

const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
};

const PolicyAcknowledgements = () => {
  const [summary, setSummary] = useState([]);
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [selectedPolicy, setSelectedPolicy] = useState(null);

  const [filters, setFilters] = useState({ status: 'all', department: 'all', role: 'all', search: '' });
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState({ total: 0, acknowledged: 0, pending: 0 });
  const [loadingDetail, setLoadingDetail] = useState(false);

  const fetchSummary = async () => {
    try {
      setLoadingSummary(true);
      const { data } = await axios.get(`${API}/admin/policy-acknowledgements/summary`, { headers: getAuth() });
      setSummary(data.summary || []);
      if (!selectedPolicy && data.summary?.length) setSelectedPolicy(data.summary[0].policy_id);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load policy summary');
    } finally {
      setLoadingSummary(false);
    }
  };

  useEffect(() => { fetchSummary(); /* eslint-disable-next-line */ }, []);

  const fetchDetail = async () => {
    if (!selectedPolicy) return;
    try {
      setLoadingDetail(true);
      const params = { policy_id: selectedPolicy };
      if (filters.status !== 'all') params.status = filters.status;
      if (filters.department !== 'all') params.department = filters.department;
      if (filters.role !== 'all') params.role = filters.role;
      if (filters.search.trim()) params.search = filters.search.trim();
      const { data } = await axios.get(`${API}/admin/policy-acknowledgements`, { headers: getAuth(), params });
      setRows(data.rows || []);
      setStats({ total: data.total || 0, acknowledged: data.acknowledged || 0, pending: data.pending || 0 });
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load acknowledgements');
    } finally {
      setLoadingDetail(false);
    }
  };

  useEffect(() => { fetchDetail(); /* eslint-disable-next-line */ }, [selectedPolicy, filters.status, filters.department, filters.role]);

  const departments = useMemo(() => {
    const set = new Set(rows.map((r) => r.department).filter(Boolean));
    return Array.from(set).sort();
  }, [rows]);

  const roles = useMemo(() => {
    const set = new Set(rows.map((r) => r.role).filter(Boolean));
    return Array.from(set).sort();
  }, [rows]);

  const exportCSV = () => {
    const policyName = summary.find((s) => s.policy_id === selectedPolicy)?.policy_name || selectedPolicy;
    const header = ['Employee Code', 'Employee Name', 'Department', 'Team', 'Role', 'Email', 'Status', 'Acknowledged At'];
    const csvRows = [header.join(',')];
    rows.forEach((r) => {
      csvRows.push([
        r.employee_code || '',
        `"${(r.employee_name || '').replace(/"/g, '""')}"`,
        r.department || '',
        r.team || '',
        r.role || '',
        r.official_email || '',
        r.is_acknowledged ? 'Acknowledged' : 'Pending',
        r.acknowledged_at ? fmtDate(r.acknowledged_at) : '',
      ].join(','));
    });
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `policy_acks_${policyName.replace(/[^a-z0-9]/gi, '_')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const selectedPolicyMeta = summary.find((s) => s.policy_id === selectedPolicy);

  return (
    <div className="space-y-6 pb-10" data-testid="policy-acks-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-[28px] font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>
            Policy Acknowledgements
          </h1>
          <p className="text-slate-500 text-[14px] mt-1">
            Track which employees have read &amp; agreed to each company policy.
          </p>
        </div>
        <Button variant="outline" onClick={() => { fetchSummary(); fetchDetail(); }} className="rounded-full" data-testid="ack-refresh-btn">
          <RefreshCw className="w-4 h-4 mr-1.5" /> Refresh
        </Button>
      </div>

      {/* Summary cards (per policy) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="ack-summary-grid">
        {loadingSummary ? (
          <div className="col-span-full flex justify-center py-12">
            <Loader2 className="w-7 h-7 animate-spin text-slate-400" />
          </div>
        ) : summary.length === 0 ? (
          <div className="col-span-full text-center py-10 text-slate-500 text-sm">No policies configured.</div>
        ) : summary.map((s) => {
          const active = s.policy_id === selectedPolicy;
          const fully = s.total_eligible > 0 && s.acknowledged === s.total_eligible;
          return (
            <button
              key={s.policy_id}
              onClick={() => setSelectedPolicy(s.policy_id)}
              className={`text-left rounded-xl border bg-white p-5 transition-all hover:shadow-md ${
                active ? 'border-[#063c88] ring-2 ring-[#063c88]/15 shadow-md' : 'border-slate-200'
              }`}
              data-testid={`ack-policy-card-${s.policy_id}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Badge variant="outline" className="text-[10px] uppercase tracking-wide">{s.category || 'Policy'}</Badge>
                    <Badge variant="outline" className="text-[10px]">v{s.version || '1.0'}</Badge>
                  </div>
                  <h3 className="text-[15px] font-semibold text-slate-900 leading-snug truncate">{s.policy_name}</h3>
                  <p className="text-[11px] text-slate-500 truncate mt-0.5">{s.applicable_to}</p>
                </div>
                <ChevronRight className={`w-4 h-4 mt-1 flex-shrink-0 ${active ? 'text-[#063c88]' : 'text-slate-300'}`} />
              </div>
              <div className="flex items-end justify-between mt-4">
                <div>
                  <div className="text-[28px] font-bold leading-none" style={{ color: fully ? '#10b981' : '#0f172a' }}>
                    {s.acknowledged}<span className="text-[14px] text-slate-400 font-medium"> / {s.total_eligible}</span>
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">{s.ack_rate}% acknowledged</div>
                </div>
                <div className="flex items-center gap-1.5">
                  {s.pending === 0 && s.total_eligible > 0 ? (
                    <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-emerald-50 text-emerald-700 text-[11px] font-medium border border-emerald-200">
                      <CheckCircle2 className="w-3 h-3" /> Complete
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-amber-50 text-amber-700 text-[11px] font-medium border border-amber-200">
                      <Clock className="w-3 h-3" /> {s.pending} pending
                    </span>
                  )}
                </div>
              </div>
              {/* Progress bar */}
              <div className="mt-3 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full transition-all"
                  style={{
                    width: `${s.ack_rate}%`,
                    background: fully ? '#10b981' : '#0ea5e9',
                  }}
                />
              </div>
            </button>
          );
        })}
      </div>

      {/* Detail panel */}
      <Card className="border-slate-200" data-testid="ack-detail-panel">
        <CardContent className="p-5 sm:p-6">
          <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
            <div>
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-slate-400" />
                <h2 className="text-[16px] font-semibold text-slate-900">{selectedPolicyMeta?.policy_name || 'Select a policy'}</h2>
              </div>
              <div className="text-[12px] text-slate-500 mt-0.5">
                Showing {stats.acknowledged} acknowledged · {stats.pending} pending · {stats.total} total
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button onClick={exportCSV} variant="outline" className="rounded-full" disabled={!rows.length} data-testid="ack-export-btn">
                <Download className="w-4 h-4 mr-1.5" /> Export CSV
              </Button>
            </div>
          </div>

          {/* Filters row */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                placeholder="Search name / code / email"
                value={filters.search}
                onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                onKeyDown={(e) => e.key === 'Enter' && fetchDetail()}
                onBlur={fetchDetail}
                className="pl-9"
                data-testid="ack-search-input"
              />
            </div>
            <Select value={filters.status} onValueChange={(v) => setFilters({ ...filters, status: v })}>
              <SelectTrigger data-testid="ack-status-filter"><SelectValue placeholder="Status" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="acknowledged">Acknowledged</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filters.department} onValueChange={(v) => setFilters({ ...filters, department: v })}>
              <SelectTrigger data-testid="ack-dept-filter"><SelectValue placeholder="Department" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All departments</SelectItem>
                {departments.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={filters.role} onValueChange={(v) => setFilters({ ...filters, role: v })}>
              <SelectTrigger data-testid="ack-role-filter"><SelectValue placeholder="Role" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All roles</SelectItem>
                {roles.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          {/* Table */}
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full text-[13px]">
              <thead className="bg-slate-50">
                <tr className="text-left text-slate-700">
                  <th className="px-3 py-2.5 font-semibold">Employee</th>
                  <th className="px-3 py-2.5 font-semibold">Code</th>
                  <th className="px-3 py-2.5 font-semibold">Department</th>
                  <th className="px-3 py-2.5 font-semibold">Role</th>
                  <th className="px-3 py-2.5 font-semibold">Status</th>
                  <th className="px-3 py-2.5 font-semibold">Acknowledged At</th>
                </tr>
              </thead>
              <tbody>
                {loadingDetail ? (
                  <tr><td colSpan={6} className="text-center py-10"><Loader2 className="w-6 h-6 animate-spin text-slate-400 inline" /></td></tr>
                ) : rows.length === 0 ? (
                  <tr><td colSpan={6} className="text-center py-10 text-slate-500">
                    <Users className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                    No employees match the current filters
                  </td></tr>
                ) : rows.map((r) => (
                  <tr key={r.employee_id} className="border-t border-slate-100 hover:bg-slate-50/60" data-testid={`ack-row-${r.employee_id}`}>
                    <td className="px-3 py-2.5">
                      <div className="font-medium text-slate-900">{r.employee_name || '—'}</div>
                      <div className="text-[11px] text-slate-500">{r.official_email || ''}</div>
                    </td>
                    <td className="px-3 py-2.5 text-slate-600">{r.employee_code || '—'}</td>
                    <td className="px-3 py-2.5 text-slate-600">
                      <div>{r.department || '—'}</div>
                      <div className="text-[11px] text-slate-400">{r.team || ''}</div>
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge variant="outline" className="text-[11px] capitalize">{r.role || 'employee'}</Badge>
                    </td>
                    <td className="px-3 py-2.5">
                      {r.is_acknowledged ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[11px] font-medium">
                          <CheckCircle2 className="w-3 h-3" /> Acknowledged
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 text-[11px] font-medium">
                          <Clock className="w-3 h-3" /> Pending
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-slate-600">{fmtDate(r.acknowledged_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-[11px] text-slate-400 mt-3 flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5" />
            Eligibility is computed against the same visibility rules used for /policies — global, department-restricted and hidden policies are honored.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default PolicyAcknowledgements;
