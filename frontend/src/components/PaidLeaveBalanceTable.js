import { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { Search, ArrowUpDown, ChevronLeft, ChevronRight, RefreshCw, Users } from 'lucide-react';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const PAGE_SIZE = 15;

const fmt = (v) => {
  const n = Number(v || 0);
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
};

export const PaidLeaveBalanceTable = ({ refreshKey }) => {
  const { getAuthHeaders } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState({ key: 'emp_name', dir: 'asc' });
  const [page, setPage] = useState(1);

  const fetchRows = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/admin/paid-leave/balances`, { headers: getAuthHeaders() });
      setRows(Array.isArray(r.data) ? r.data : []);
    } catch { setRows([]); }
    finally { setLoading(false); }
  }, [getAuthHeaders]);

  useEffect(() => { fetchRows(); }, [fetchRows, refreshKey]);

  const view = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = q ? rows.filter(r => r.emp_name.toLowerCase().includes(q) || r.team.toLowerCase().includes(q)) : [...rows];
    const { key, dir } = sort;
    list.sort((a, b) => {
      const av = a[key], bv = b[key];
      const c = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv));
      return dir === 'asc' ? c : -c;
    });
    return list;
  }, [rows, search, sort]);

  const pages = Math.max(1, Math.ceil(view.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const pageRows = view.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);
  const toggleSort = (key) => setSort(s => ({ key, dir: s.key === key && s.dir === 'asc' ? 'desc' : 'asc' }));

  const SortTh = ({ k, label, className = '' }) => (
    <th className={className}>
      <button type="button" onClick={() => toggleSort(k)} className="inline-flex items-center gap-1 hover:text-slate-900" data-testid={`pl-bal-sort-${k}`}>
        {label} <ArrowUpDown className="w-3 h-3 opacity-60" />
      </button>
    </th>
  );

  return (
    <div className="rounded-xl border border-slate-200 bg-white" data-testid="pl-balance-section">
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 p-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-[#063c88]" />
          <h3 className="text-sm font-semibold text-slate-900">Employee Paid Leave Balances</h3>
          <span className="text-xs text-slate-500" data-testid="pl-bal-count">({view.length})</span>
        </div>
        <div className="flex items-center gap-2 sm:ml-auto">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <Input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Search employee or team" className="pl-9 rounded-lg w-64 h-9" data-testid="pl-bal-search" />
          </div>
          <Button variant="outline" size="sm" onClick={fetchRows} disabled={loading} className="rounded-lg h-9" data-testid="pl-bal-refresh">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="table-premium w-full text-sm" data-testid="pl-balance-table">
          <thead><tr>
            <SortTh k="emp_name" label="Employee Name" className="text-left" />
            <SortTh k="team" label="Team" className="text-left" />
            <SortTh k="available_paid_leave" label="Available Paid Leave" className="text-center" />
          </tr></thead>
          <tbody>
            {loading && rows.length === 0 ? (
              <tr><td colSpan="3" className="text-center py-8 text-slate-500">Loading…</td></tr>
            ) : pageRows.length === 0 ? (
              <tr><td colSpan="3" className="text-center py-8 text-slate-500" data-testid="pl-bal-empty">No active confirmed employees found</td></tr>
            ) : pageRows.map((r) => (
              <tr key={r.employee_id} data-testid={`pl-bal-row-${r.employee_id}`}>
                <td className="text-left font-medium text-slate-800">{r.emp_name}</td>
                <td className="text-left text-slate-600">{r.team || '-'}</td>
                <td className={`text-center font-semibold ${r.available_paid_leave < 0 ? 'text-red-600' : 'text-slate-900'}`} data-testid={`pl-bal-value-${r.employee_id}`}>{fmt(r.available_paid_leave)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="flex items-center justify-end gap-2 p-3 border-t border-slate-100 text-xs text-slate-500">
          <span data-testid="pl-bal-page">Page {current} of {pages}</span>
          <Button variant="outline" size="sm" className="h-8 rounded-lg" disabled={current <= 1} onClick={() => setPage(current - 1)} data-testid="pl-bal-prev"><ChevronLeft className="w-4 h-4" /></Button>
          <Button variant="outline" size="sm" className="h-8 rounded-lg" disabled={current >= pages} onClick={() => setPage(current + 1)} data-testid="pl-bal-next"><ChevronRight className="w-4 h-4" /></Button>
        </div>
      )}
    </div>
  );
};

export default PaidLeaveBalanceTable;
