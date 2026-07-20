import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { CalendarDays, RotateCcw, FileText, Search, Loader2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { DatePicker } from '../components/ui/date-picker';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { Pagination } from '../components/Pagination';
import { formatDate } from '../lib/dateFormat';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const LEAVE_TYPES = ['All', 'Sick', 'Casual', 'Optional', 'Paid', 'Other'];
const LEAVE_STATUSES = ['All', 'pending', 'approved', 'rejected', 'cancelled'];
const PAGE_SIZE_OPTIONS = [30, 60, 100, 250, 500];

// Quick date filters. Each returns [fromDate, toDate] in YYYY-MM-DD.
const QUICK_FILTERS = [
  { key: 'today', label: 'Today', days: 0 },
  { key: 'yesterday', label: 'Yesterday', days: 1, single: true },
  { key: 'last7', label: 'Last 7 Days', days: 7 },
  { key: 'last14', label: 'Last 14 Days', days: 14 },
  { key: 'last30', label: 'Last 30 Days', days: 30 },
  { key: 'last3m', label: 'Last 3 Months', months: 3 },
  { key: 'last6m', label: 'Last 6 Months', months: 6 },
  { key: 'last1y', label: 'Last 1 Year', years: 1 },
];

const toISODate = (d) => {
  if (!d) return '';
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
};

const applyQuickFilter = (key) => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const cfg = QUICK_FILTERS.find(q => q.key === key);
  if (!cfg) return { fromDate: '', toDate: '' };
  if (cfg.single) {
    const y = new Date(today);
    y.setDate(y.getDate() - cfg.days);
    return { fromDate: toISODate(y), toDate: toISODate(y) };
  }
  if (cfg.days === 0) {
    return { fromDate: toISODate(today), toDate: toISODate(today) };
  }
  if (cfg.days) {
    const from = new Date(today);
    from.setDate(from.getDate() - (cfg.days - 1));
    return { fromDate: toISODate(from), toDate: toISODate(today) };
  }
  if (cfg.months) {
    const from = new Date(today);
    from.setMonth(from.getMonth() - cfg.months);
    return { fromDate: toISODate(from), toDate: toISODate(today) };
  }
  if (cfg.years) {
    const from = new Date(today);
    from.setFullYear(from.getFullYear() - cfg.years);
    return { fromDate: toISODate(from), toDate: toISODate(today) };
  }
  return { fromDate: '', toDate: '' };
};

const StatusBadge = ({ status }) => {
  const map = {
    approved: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    pending: 'bg-amber-100 text-amber-700 border-amber-200',
    rejected: 'bg-rose-100 text-rose-700 border-rose-200',
    cancelled: 'bg-slate-100 text-slate-600 border-slate-300',
  };
  const cls = map[status?.toLowerCase()] || map.pending;
  const label = status ? status[0].toUpperCase() + status.slice(1) : '—';
  return <Badge className={`${cls} border rounded-full font-medium capitalize`}>{label}</Badge>;
};

const ReasonCell = ({ reason }) => {
  if (!reason) return <span className="text-slate-400 italic">—</span>;
  const trimmed = reason.length > 60 ? reason.slice(0, 60) + '…' : reason;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          className="text-left text-slate-700 hover:text-[#063c88] underline decoration-dotted underline-offset-4 max-w-[280px] truncate"
          data-testid="reason-preview"
          title="Click to view full reason"
        >
          {trimmed}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-96 max-h-72 overflow-y-auto text-sm" data-testid="reason-popover">
        <div className="font-semibold text-slate-600 text-xs uppercase tracking-wider mb-1.5">Reason</div>
        <div className="whitespace-pre-wrap text-slate-800 leading-relaxed">{reason}</div>
      </PopoverContent>
    </Popover>
  );
};

const formatLeaveDate = (row) => {
  const s = row.start_date;
  const e = row.end_date;
  if (!s) return '—';
  if (!e || s === e) return formatDate(s);
  return `${formatDate(s)} – ${formatDate(e)}`;
};

export default function LeaveReport() {
  const { getAuthHeaders } = useAuth();
  const [filters, setFilters] = useState({
    fromDate: '',
    toDate: '',
    search: '',
    team: 'All',
    leaveType: 'All',
    status: 'All',
  });
  const [teams, setTeams] = useState([]);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(30);
  const [loading, setLoading] = useState(false);
  const [activeQuick, setActiveQuick] = useState('');

  // Load teams once for the Team filter.
  useEffect(() => {
    axios.get(`${API}/teams`, { headers: getAuthHeaders() })
      .then(res => setTeams(Array.isArray(res.data) ? res.data : []))
      .catch(() => setTeams([]));
  }, [getAuthHeaders]);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        page,
        page_size: pageSize,
      };
      if (filters.fromDate) params.from_date = filters.fromDate;
      if (filters.toDate) params.to_date = filters.toDate;
      if (filters.search) params.search = filters.search;
      if (filters.team && filters.team !== 'All') params.team = filters.team;
      if (filters.leaveType && filters.leaveType !== 'All') params.leave_type = filters.leaveType;
      if (filters.status && filters.status !== 'All') params.status = filters.status;
      const res = await axios.get(`${API}/leaves/report`, {
        params,
        headers: getAuthHeaders(),
      });
      setRows(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load leave report');
      setRows([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [filters, page, pageSize, getAuthHeaders]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  const handleQuick = (key) => {
    const { fromDate, toDate } = applyQuickFilter(key);
    setFilters(f => ({ ...f, fromDate, toDate }));
    setActiveQuick(key);
    setPage(1);
  };

  const handleReset = () => {
    setFilters({ fromDate: '', toDate: '', search: '', team: 'All', leaveType: 'All', status: 'All' });
    setActiveQuick('');
    setPage(1);
  };

  const teamOptions = useMemo(() => (
    ['All', ...teams.map(t => t.name || t).filter(Boolean)]
  ), [teams]);

  return (
    <div className="max-w-[1400px] mx-auto p-4 md:p-6 space-y-5" data-testid="leave-report-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-slate-800 flex items-center gap-2">
            <FileText className="w-7 h-7 text-[#063c88]" />
            Leave Management Report
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Filter, review and paginate leave records across the organisation.
          </p>
        </div>
        <div className="text-sm text-slate-500">
          <span className="font-medium text-slate-700">{total.toLocaleString()}</span> record{total === 1 ? '' : 's'} match filters
        </div>
      </div>

      {/* Filters card */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 md:p-5 space-y-4" data-testid="filters-card">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <Label className="text-xs font-semibold text-slate-600">From Date</Label>
            <DatePicker
              value={filters.fromDate}
              onChange={(v) => { setFilters(f => ({ ...f, fromDate: v || '' })); setActiveQuick(''); setPage(1); }}
              placeholder="Pick from date"
              data-testid="from-date"
            />
          </div>
          <div>
            <Label className="text-xs font-semibold text-slate-600">To Date</Label>
            <DatePicker
              value={filters.toDate}
              onChange={(v) => { setFilters(f => ({ ...f, toDate: v || '' })); setActiveQuick(''); setPage(1); }}
              placeholder="Pick to date"
              data-testid="to-date"
            />
          </div>
          <div>
            <Label className="text-xs font-semibold text-slate-600">Name / Email</Label>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              <Input
                value={filters.search}
                onChange={(e) => { setFilters(f => ({ ...f, search: e.target.value })); setPage(1); }}
                placeholder="Search by name or email"
                className="pl-8 rounded-lg"
                data-testid="search-input"
              />
            </div>
          </div>
          <div>
            <Label className="text-xs font-semibold text-slate-600">Team</Label>
            <Select value={filters.team} onValueChange={(v) => { setFilters(f => ({ ...f, team: v })); setPage(1); }}>
              <SelectTrigger className="rounded-lg" data-testid="team-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                {teamOptions.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs font-semibold text-slate-600">Leave Type</Label>
            <Select value={filters.leaveType} onValueChange={(v) => { setFilters(f => ({ ...f, leaveType: v })); setPage(1); }}>
              <SelectTrigger className="rounded-lg" data-testid="leave-type-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                {LEAVE_TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs font-semibold text-slate-600">Leave Status</Label>
            <Select value={filters.status} onValueChange={(v) => { setFilters(f => ({ ...f, status: v })); setPage(1); }}>
              <SelectTrigger className="rounded-lg" data-testid="status-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                {LEAVE_STATUSES.map(s => (
                  <SelectItem key={s} value={s}>
                    {s === 'All' ? 'All' : s[0].toUpperCase() + s.slice(1)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="md:col-span-2 flex items-end justify-end gap-2">
            <Button variant="outline" onClick={handleReset} className="rounded-lg" data-testid="reset-filters">
              <RotateCcw className="w-4 h-4 mr-1.5" /> Reset
            </Button>
          </div>
        </div>

        {/* Quick date filters */}
        <div>
          <div className="text-xs font-semibold text-slate-600 mb-2 flex items-center gap-1.5">
            <CalendarDays className="w-3.5 h-3.5" /> Quick Date Filters
          </div>
          <div className="flex flex-wrap gap-2">
            {QUICK_FILTERS.map(q => (
              <button
                key={q.key}
                onClick={() => handleQuick(q.key)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition ${
                  activeQuick === q.key
                    ? 'bg-[#063c88] text-white border-[#063c88]'
                    : 'bg-white text-slate-600 border-slate-200 hover:border-[#063c88] hover:text-[#063c88]'
                }`}
                data-testid={`quick-${q.key}`}
              >
                {q.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden" data-testid="report-table-card">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-slate-600">Name</th>
                <th className="text-left px-4 py-3 font-semibold text-slate-600">Team</th>
                <th className="text-left px-4 py-3 font-semibold text-slate-600">Leave Date</th>
                <th className="text-left px-4 py-3 font-semibold text-slate-600">Leave Type</th>
                <th className="text-left px-4 py-3 font-semibold text-slate-600">Leave Duration</th>
                <th className="text-left px-4 py-3 font-semibold text-slate-600">Leave Status</th>
                <th className="text-left px-4 py-3 font-semibold text-slate-600">Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="text-center py-16 text-slate-400">
                    <Loader2 className="w-6 h-6 animate-spin inline mr-2" />
                    Loading leave records…
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-16 text-slate-400" data-testid="empty-state">
                    No leave records match the current filters.
                  </td>
                </tr>
              ) : (
                rows.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/60" data-testid={`row-${r.id}`}>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-800">{r.emp_name || '—'}</div>
                      {r.email && <div className="text-xs text-slate-500 mt-0.5">{r.email}</div>}
                    </td>
                    <td className="px-4 py-3 text-slate-700">{r.team || '—'}</td>
                    <td className="px-4 py-3 text-slate-700 tabular-nums">{formatLeaveDate(r)}</td>
                    <td className="px-4 py-3 text-slate-700">{r.leave_type || '—'}</td>
                    <td className="px-4 py-3 text-slate-700">{r.duration || r.leave_split || '—'}</td>
                    <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                    <td className="px-4 py-3"><ReasonCell reason={r.reason} /></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <Pagination
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={(p) => setPage(p)}
          onPageSizeChange={(s) => { setPageSize(s); setPage(1); }}
          pageSizeOptions={PAGE_SIZE_OPTIONS}
          testid="leave-report-pagination"
        />
      </div>
    </div>
  );
}
