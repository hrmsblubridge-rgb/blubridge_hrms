import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { MonthPicker } from '../ui/month-picker';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Loader2, FileSpreadsheet, Download, RotateCcw, Search, ArrowUpDown, IndianRupee } from 'lucide-react';
import BrsfExportImport from './BrsfExportImport';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const lastCompletedMonth = () => {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
};
const monthsBack = (n) => {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
};
const inr = (v) => `₹${Number(v || 0).toLocaleString('en-IN')}`;

const DEFAULTS = { from: monthsBack(5), to: lastCompletedMonth(), employeeId: '', team: '' };

const BrsfOverallStar = () => {
  const { getAuthHeaders, user } = useAuth();
  const isHrAdmin = user?.role === 'hr';
  const [filters, setFilters] = useState(DEFAULTS);
  const [applied, setApplied] = useState(DEFAULTS);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sort, setSort] = useState({ key: 'full_name', dir: 'asc' });

  const load = useCallback(async (f) => {
    if (f.from > f.to) { toast.error('From Month cannot be later than To Month.'); return; }
    setLoading(true);
    try {
      const res = await axios.get(`${API}/brsf/overall`, {
        params: {
          from_month: f.from, to_month: f.to,
          employee_id: f.employeeId || undefined, team: f.team || undefined,
        },
        headers: getAuthHeaders(),
      });
      setData(res.data);
      if (res.data.skipped_months?.length) {
        toast.info(`${res.data.skipped_months.join(', ')} skipped — Star Rewards are reported for completed months only`);
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load the Overall Star report');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  useEffect(() => { load(DEFAULTS); }, [load]);

  const download = async (format) => {
    try {
      const res = await axios.get(`${API}/brsf/overall/export`, {
        params: {
          from_month: applied.from, to_month: applied.to,
          employee_id: applied.employeeId || undefined, team: applied.team || undefined, format,
        },
        headers: getAuthHeaders(), responseType: 'blob',
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `BRSF_Overall_Star_${applied.from}_to_${applied.to}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`${format.toUpperCase()} exported`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Export failed');
    }
  };

  const rows = useMemo(() => {
    const list = [...(data?.rows || [])];
    const { key, dir } = sort;
    list.sort((a, b) => {
      const av = key === 'cash_total' ? a.cash_total : (a[key] || '');
      const bv = key === 'cash_total' ? b.cash_total : (b[key] || '');
      if (av === bv) return 0;
      return (av > bv ? 1 : -1) * (dir === 'asc' ? 1 : -1);
    });
    return list;
  }, [data, sort]);

  const employees = useMemo(() => (data?.rows || []).map((r) => ({ id: r.id, name: r.full_name })), [data]);
  const grandTotal = rows.reduce((s, r) => s + (r.cash_total || 0), 0);

  const sortBtn = (key, label) => (
    <button className="inline-flex items-center gap-1 hover:text-slate-900"
      onClick={() => setSort((p) => ({ key, dir: p.key === key && p.dir === 'asc' ? 'desc' : 'asc' }))}
      data-testid={`overall-sort-${key}`}>
      {label} <ArrowUpDown className="w-3 h-3 opacity-50" />
    </button>
  );

  if (!isHrAdmin) {
    return (
      <div className="card-flat p-10 text-center text-slate-500" data-testid="overall-not-authorized">
        The Overall Star report is available to HR Admin only.
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="brsf-overall-star">
      <div className="card-flat p-6">
        <div className="flex flex-wrap items-end gap-4">
          <div data-testid="overall-from-month">
            <Label className="text-sm text-slate-600 mb-1.5 block">From Month</Label>
            <MonthPicker value={filters.from} onChange={(v) => setFilters({ ...filters, from: v })} className="w-36" />
          </div>
          <div data-testid="overall-to-month">
            <Label className="text-sm text-slate-600 mb-1.5 block">To Month</Label>
            <MonthPicker value={filters.to} onChange={(v) => setFilters({ ...filters, to: v })} className="w-36" />
          </div>
          <div>
            <Label className="text-sm text-slate-600 mb-1.5 block">Employee</Label>
            <Select value={filters.employeeId || '__all__'}
              onValueChange={(v) => setFilters({ ...filters, employeeId: v === '__all__' ? '' : v })}>
              <SelectTrigger className="w-56 rounded-lg" data-testid="overall-employee-filter">
                <SelectValue placeholder="All Employees" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All Employees</SelectItem>
                {employees.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-sm text-slate-600 mb-1.5 block">Team</Label>
            <Select value={filters.team || '__all__'}
              onValueChange={(v) => setFilters({ ...filters, team: v === '__all__' ? '' : v })}>
              <SelectTrigger className="w-56 rounded-lg" data-testid="overall-team-filter">
                <SelectValue placeholder="All Teams" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All Teams</SelectItem>
                {(data?.teams || []).map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={() => { setApplied(filters); load(filters); }} disabled={loading}
            className="bg-[#063c88] hover:bg-[#052f6b] text-white rounded-lg" data-testid="overall-filter-btn">
            {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Search className="w-4 h-4 mr-2" />} Filter
          </Button>
          <Button variant="ghost" onClick={() => { setFilters(DEFAULTS); setApplied(DEFAULTS); load(DEFAULTS); }}
            className="rounded-lg" data-testid="overall-reset-btn">
            <RotateCcw className="w-4 h-4 mr-2" /> Reset
          </Button>
          <Button variant="outline" onClick={() => download('xlsx')} className="rounded-lg" data-testid="overall-export-xlsx">
            <FileSpreadsheet className="w-4 h-4 mr-2" /> Export Excel
          </Button>
          <Button variant="outline" onClick={() => download('csv')} className="rounded-lg" data-testid="overall-export-csv">
            <Download className="w-4 h-4 mr-2" /> Export CSV
          </Button>
          {applied.from === applied.to ? (
            <BrsfExportImport month={applied.from} headers={getAuthHeaders()}
              onImported={() => load(applied)} />
          ) : (
            <span className="text-xs text-slate-500 max-w-[15rem]" data-testid="overall-import-hint">
              Select the same From and To month to import BRSF values through the validated Employees-tab importer.
            </span>
          )}
        </div>
        <p className="text-xs text-slate-500 mt-3">
          Stars are the BRSF Final Total Stars already calculated in the Employees tab; cash rewards are derived
          from them. <b>-</b> = not eligible that month (before confirmation or from the inactive month onwards),
          <b> NC</b> = eligible but not calculated yet, <b>0</b> = calculated as zero.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[['Employees', rows.length], ['Months Reported', data?.months?.length || 0],
          ['Total Cash Reward', inr(grandTotal)]].map(([label, value], i) => (
          <div key={label} className="card-flat p-5 flex items-center gap-4">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-[#063c88] to-blue-600 flex items-center justify-center">
              <IndianRupee className="w-5 h-5 text-white" strokeWidth={1.5} />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900 number-display"
                data-testid={`overall-stat-${i}`}>{value}</p>
              <p className="text-xs text-slate-500">{label}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="card-premium overflow-hidden">
        <div className="overflow-x-auto">
          <table className="text-sm min-w-full" data-testid="overall-table">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3 sticky left-0 bg-slate-50 z-10 min-w-[13rem]">{sortBtn('full_name', 'Employee Name')}</th>
                <th className="px-4 py-3 min-w-[13rem]">{sortBtn('team', 'Team Name')}</th>
                <th className="px-4 py-3 whitespace-nowrap">{sortBtn('date_of_joining', 'Date Of Joining')}</th>
                <th className="px-4 py-3 whitespace-nowrap">{sortBtn('confirmation_date', 'Date Of Confirmation')}</th>
                {(data?.months || []).map((m) => (
                  <React.Fragment key={m.key}>
                    <th className="px-3 py-3 text-center whitespace-nowrap">{m.label}</th>
                    <th className="px-3 py-3 text-center whitespace-nowrap">{m.label.slice(0, 3).toUpperCase()} Cash</th>
                  </React.Fragment>
                ))}
                <th className="px-4 py-3 text-right whitespace-nowrap bg-blue-50/60">{sortBtn('cash_total', 'Cash Reward Total')}</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={5 + (data?.months?.length || 0) * 2} className="px-4 py-10 text-center text-slate-500">
                  <Loader2 className="w-5 h-5 mx-auto animate-spin" />
                </td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-10 text-center text-slate-500" data-testid="overall-empty">
                  No employees are eligible for any month in the selected range.
                </td></tr>
              )}
              {!loading && rows.map((r) => (
                <tr key={r.id} className="border-b border-slate-100 hover:bg-slate-50/70" data-testid={`overall-row-${r.id}`}>
                  <td className="px-4 py-3 font-medium text-slate-900 sticky left-0 bg-white z-10">
                    {r.full_name}
                    {r.inactive_date && (
                      <Badge variant="outline" className="ml-2 text-[10px] bg-slate-100 text-slate-500 border-slate-200">
                        inactive {r.inactive_date}
                      </Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{r.team || '--'}</td>
                  <td className="px-4 py-3 text-slate-600 whitespace-nowrap">{r.date_of_joining || '--'}</td>
                  <td className="px-4 py-3 text-slate-600 whitespace-nowrap">{r.confirmation_date || '--'}</td>
                  {r.cells.map((c) => (
                    <React.Fragment key={c.month}>
                      <td className="px-3 py-3 text-center number-display" data-testid={`overall-stars-${r.id}-${c.month}`}
                        title={c.state === 'value'
                          ? `${c.stars} stars · ${c.category} · ${inr(c.cash)} · ${c.action}`
                          : (c.state === 'not_eligible' ? 'Not eligible for this month' : 'Eligible — BRSF not calculated yet')}>
                        {c.state === 'value' ? c.stars : (c.state === 'not_eligible' ? '-' : 'NC')}
                      </td>
                      <td className="px-3 py-3 text-center number-display text-slate-700" data-testid={`overall-cash-${r.id}-${c.month}`}>
                        {c.state === 'value' ? inr(c.cash) : (c.state === 'not_eligible' ? '-' : 'NC')}
                      </td>
                    </React.Fragment>
                  ))}
                  <td className="px-4 py-3 text-right number-display font-bold text-[#063c88] bg-blue-50/40"
                    data-testid={`overall-total-${r.id}`}>{inr(r.cash_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card-flat p-5">
        <p className="text-sm font-semibold text-slate-900 mb-3">Cash Reward Bands</p>
        <div className="flex flex-wrap gap-2" data-testid="overall-reward-bands">
          {(data?.reward_bands || []).map((b) => (
            <Badge key={b.category} variant="outline" className="text-xs bg-slate-50">
              {b.stars} · {b.category} · {inr(b.cash)}
            </Badge>
          ))}
          <Badge variant="outline" className="text-xs bg-slate-50">≤0 · Unsafe Behavior · ₹0</Badge>
        </div>
      </div>
    </div>
  );
};

export default BrsfOverallStar;
