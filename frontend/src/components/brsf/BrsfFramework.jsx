import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Textarea } from '../ui/textarea';
import { MonthPicker } from '../ui/month-picker';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../ui/dialog';
import { ChevronDown, ChevronRight, RefreshCw, Loader2, Pencil, RotateCcw, Plus, Trash2, History, Star, TrendingDown, Sigma } from 'lucide-react';
import { BrsfChildTable, EXPANDABLE, childRowsFor } from './BrsfChildTable';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const statusOf = (line) => {
  if (line.override_value !== null && line.override_value !== undefined) return 'Overridden';
  if (line.type === 'automated') return (line.system_value === null || line.system_value === undefined) ? 'No Data' : 'Auto';
  return 'Manual';
};

const STATUS_STYLE = {
  Overridden: 'bg-amber-100 text-amber-700 border-amber-200',
  Auto: 'bg-blue-50 text-blue-700 border-blue-200',
  Manual: 'bg-violet-50 text-violet-700 border-violet-200',
  'No Data': 'bg-slate-100 text-slate-500 border-slate-200',
  'Not Applicable': 'bg-slate-100 text-slate-500 border-slate-200',
};

const fmt = (v) => (v === null || v === undefined || v === '' ? '--' : (Number(v) > 0 ? `+${v}` : `${v}`));

const BrsfFramework = () => {
  const { getAuthHeaders, user } = useAuth();
  const isHrAdmin = user?.role === 'hr';
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [employees, setEmployees] = useState([]);
  const [employeeId, setEmployeeId] = useState('');
  const [data, setData] = useState(null);
  const [loadingEmp, setLoadingEmp] = useState(false);
  const [loading, setLoading] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [expanded, setExpanded] = useState({});
  const [overrideLine, setOverrideLine] = useState(null);
  const [manualLine, setManualLine] = useState(null);
  const [instanceLine, setInstanceLine] = useState(null);
  const [auditOpen, setAuditOpen] = useState(false);
  const [audit, setAudit] = useState([]);

  const loadEmployees = useCallback(async () => {
    setLoadingEmp(true);
    try {
      const res = await axios.get(`${API}/brsf/eligible-employees`, { params: { month }, headers: getAuthHeaders() });
      const list = res.data.employees || [];
      setEmployees(list);
      setEmployeeId((prev) => (list.some((e) => e.id === prev) ? prev : ''));
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load eligible employees');
      setEmployees([]);
    } finally {
      setLoadingEmp(false);
    }
  }, [month, getAuthHeaders]);

  const loadStars = useCallback(async () => {
    if (!employeeId) { setData(null); return; }
    setLoading(true);
    try {
      const res = await axios.get(`${API}/brsf/stars`, { params: { employee_id: employeeId, month }, headers: getAuthHeaders() });
      setData(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load BRSF stars');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [employeeId, month, getAuthHeaders]);

  useEffect(() => { loadEmployees(); }, [loadEmployees]);
  useEffect(() => { loadStars(); }, [loadStars]);

  const patchLine = (line) => setData((d) => {
    if (!d) return d;
    const lines = d.lines.map((l) => (l.id === line.id ? line : l));
    const pos = lines.filter((l) => l.sign > 0).reduce((s, l) => s + (l.final_value || 0), 0);
    const neg = lines.filter((l) => l.sign < 0).reduce((s, l) => s + (l.final_value || 0), 0);
    return { ...d, lines, totals: { positive_total: +pos.toFixed(2), negative_total: +neg.toFixed(2), net_total: +(pos + neg).toFixed(2) } };
  });

  const recalculate = async () => {
    setRecalculating(true);
    try {
      const res = await axios.post(`${API}/brsf/recalculate`, { month, employee_id: employeeId || undefined }, { headers: getAuthHeaders() });
      toast.success(res.data.message || 'Recalculated');
      await loadStars();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Recalculation failed');
    } finally {
      setRecalculating(false);
    }
  };

  const openAudit = async () => {
    setAuditOpen(true);
    try {
      const res = await axios.get(`${API}/brsf/audit`, { params: { employee_id: employeeId, month }, headers: getAuthHeaders() });
      setAudit(res.data.audit || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load audit trail');
    }
  };

  const resetOverride = async (line) => {
    try {
      const res = await axios.post(`${API}/brsf/stars/${line.id}/reset-override`, {}, { headers: getAuthHeaders() });
      patchLine(res.data);
      toast.success(`${line.code} reset to system calculated value`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Reset failed');
    }
  };

  const totals = data?.totals || { positive_total: 0, negative_total: 0, net_total: 0 };

  const summary = useMemo(() => ([
    { label: 'Positive Stars', value: fmt(totals.positive_total), icon: Star, cls: 'from-emerald-500 to-teal-500' },
    { label: 'Negative Stars', value: fmt(totals.negative_total), icon: TrendingDown, cls: 'from-rose-500 to-red-500' },
    { label: 'Net Stars', value: fmt(totals.net_total), icon: Sigma, cls: 'from-[#063c88] to-blue-600' },
  ]), [totals]);

  if (!isHrAdmin) {
    return (
      <div className="card-flat p-10 text-center text-slate-500" data-testid="brsf-not-authorized">
        The BluBridge Research Star Framework is available to HR Admin only.
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="brsf-framework">
      {/* Selectors */}
      <div className="card-flat p-6">
        <div className="flex flex-wrap items-end gap-4">
          <div data-testid="brsf-month-picker">
            <Label className="text-sm text-slate-600 mb-1.5 block">Month</Label>
            <MonthPicker value={month} onChange={setMonth} className="w-36" />
          </div>
          <div>
            <Label className="text-sm text-slate-600 mb-1.5 block">Employee (Research Unit · Confirmed)</Label>
            <Select value={employeeId} onValueChange={setEmployeeId} disabled={loadingEmp || !employees.length}>
              <SelectTrigger className="w-72 rounded-lg" data-testid="brsf-employee-select">
                <SelectValue placeholder={loadingEmp ? 'Loading...' : (employees.length ? 'Select employee' : 'No eligible employees')} />
              </SelectTrigger>
              <SelectContent>
                {employees.map((e) => (
                  <SelectItem key={e.id} value={e.id}>
                    {e.full_name} {e.custom_employee_id ? `(${e.custom_employee_id})` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={recalculate} disabled={recalculating} className="bg-[#063c88] hover:bg-[#052f6b] text-white rounded-lg" data-testid="brsf-recalculate-btn">
            {recalculating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
            {employeeId ? 'Recalculate Automated Stars' : 'Recalculate All (Month)'}
          </Button>
          {employeeId && (
            <Button variant="outline" onClick={openAudit} className="rounded-lg" data-testid="brsf-audit-btn">
              <History className="w-4 h-4 mr-2" /> Audit Trail
            </Button>
          )}
        </div>
        <p className="text-xs text-slate-500 mt-3">
          Eligibility: Research Unit · Full-time (non-intern) · Confirmed — available from the confirmation month onwards.
        </p>
      </div>

      {loading && (
        <div className="card-flat p-10 flex items-center justify-center text-slate-500" data-testid="brsf-loading">
          <Loader2 className="w-5 h-5 mr-2 animate-spin" /> Loading star framework...
        </div>
      )}

      {!loading && !employeeId && (
        <div className="card-flat p-10 text-center text-slate-500" data-testid="brsf-empty-state">
          Select a month and an eligible employee to view the 14 BRSF star criteria.
        </div>
      )}

      {!loading && data && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4" data-testid="brsf-totals">
            {summary.map((s) => (
              <div key={s.label} className="card-flat p-5 flex items-center gap-4">
                <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${s.cls} flex items-center justify-center`}>
                  <s.icon className="w-5 h-5 text-white" strokeWidth={1.5} />
                </div>
                <div>
                  <p className="text-2xl font-bold text-slate-900 number-display" data-testid={`brsf-total-${s.label.split(' ')[0].toLowerCase()}`}>{s.value}</p>
                  <p className="text-xs text-slate-500">{s.label}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="card-premium overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="brsf-grid">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-3 py-3 w-10"></th>
                    <th className="px-3 py-3">Code</th>
                    <th className="px-3 py-3">Criteria</th>
                    <th className="px-3 py-3">Type</th>
                    <th className="px-3 py-3">Frequency</th>
                    <th className="px-3 py-3 text-right">System Value</th>
                    <th className="px-3 py-3 text-right">Manual / Override</th>
                    <th className="px-3 py-3 text-right">Final Stars</th>
                    <th className="px-3 py-3">Status</th>
                    <th className="px-3 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {data.lines.map((line) => {
                    const status = statusOf(line);
                    const children = childRowsFor(line, data.weeks || []);
                    const canExpand = EXPANDABLE.has(line.code) && children.length > 0;
                    const isOpen = !!expanded[line.code];
                    const manualCol = line.type === 'automated'
                      ? (line.override_value !== null && line.override_value !== undefined ? fmt(line.override_value) : '--')
                      : (line.override_value !== null && line.override_value !== undefined
                        ? fmt(line.override_value)
                        : (line.entry_mode === 'weekly'
                          ? fmt((line.weekly || []).reduce((s, w) => s + (Number(w.value) || 0), 0))
                          : (line.code === 'N07' || line.code === 'N08'
                            ? fmt((line.instances || []).reduce((s, i) => s + (Number(i.value) || 0), 0))
                            : fmt(line.manual_value))));
                    return (
                      <React.Fragment key={line.code}>
                        <tr className={`border-b border-slate-100 hover:bg-slate-50/60 ${line.sign > 0 ? '' : 'bg-rose-50/20'}`} data-testid={`brsf-row-${line.code}`}>
                          <td className="px-3 py-3">
                            {canExpand ? (
                              <button
                                onClick={() => setExpanded((p) => ({ ...p, [line.code]: !p[line.code] }))}
                                className="text-slate-400 hover:text-slate-700"
                                data-testid={`brsf-expand-${line.code}`}
                              >
                                {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                              </button>
                            ) : <span className="inline-block w-4" />}
                          </td>
                          <td className="px-3 py-3 font-semibold text-slate-700">{line.code}</td>
                          <td className="px-3 py-3 text-slate-900">
                            {line.name}
                            {line.system_note && <span className="block text-xs text-slate-400">{line.system_note}</span>}
                          </td>
                          <td className="px-3 py-3 text-slate-600 capitalize">{line.type === 'automated' ? 'Auto' : 'Manual'}</td>
                          <td className="px-3 py-3 text-slate-600 capitalize">
                            {line.frequency}
                            {(line.code === 'P02' || line.code === 'P04') && (
                              <span className="ml-1 text-xs text-slate-400">({line.entry_mode})</span>
                            )}
                          </td>
                          <td className="px-3 py-3 text-right number-display text-slate-700">
                            {line.type === 'automated' ? fmt(line.system_value) : '--'}
                          </td>
                          <td className="px-3 py-3 text-right number-display text-slate-700">{manualCol}</td>
                          <td className={`px-3 py-3 text-right number-display font-bold ${line.final_value > 0 ? 'text-emerald-600' : line.final_value < 0 ? 'text-rose-600' : 'text-slate-400'}`} data-testid={`brsf-final-${line.code}`}>
                            {fmt(line.final_value)}
                          </td>
                          <td className="px-3 py-3">
                            <Badge variant="outline" className={`text-xs ${STATUS_STYLE[status]}`} data-testid={`brsf-status-${line.code}`}>{status}</Badge>
                          </td>
                          <td className="px-3 py-3">
                            <div className="flex items-center justify-end gap-1">
                              {line.type === 'automated' && (
                                <Button size="sm" variant="ghost" onClick={() => setOverrideLine(line)} title="Override" data-testid={`brsf-override-${line.code}`}>
                                  <Pencil className="w-3.5 h-3.5" />
                                </Button>
                              )}
                              {line.type === 'manual' && !['N07', 'N08'].includes(line.code) && (
                                <Button size="sm" variant="ghost" onClick={() => setManualLine(line)} title="Manual entry" data-testid={`brsf-manual-${line.code}`}>
                                  <Pencil className="w-3.5 h-3.5" />
                                </Button>
                              )}
                              {['N07', 'N08'].includes(line.code) && (
                                <Button size="sm" variant="ghost" onClick={() => setInstanceLine({ line, instance: null })} title="Add instance" data-testid={`brsf-add-instance-${line.code}`}>
                                  <Plus className="w-3.5 h-3.5" />
                                </Button>
                              )}
                              {line.override_value !== null && line.override_value !== undefined && (
                                <Button size="sm" variant="ghost" onClick={() => resetOverride(line)} title="Reset override" data-testid={`brsf-reset-${line.code}`}>
                                  <RotateCcw className="w-3.5 h-3.5" />
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                        {canExpand && isOpen && (
                          <tr data-testid={`brsf-children-${line.code}`}>
                            <td colSpan={10} className="bg-slate-50/70 px-6 py-4">
                              <BrsfChildTable
                                line={line}
                                rows={children}
                                onEditInstance={(inst) => setInstanceLine({ line, instance: inst })}
                                onDeleteInstance={async (inst) => {
                                  try {
                                    const res = await axios.delete(`${API}/brsf/stars/${line.id}/instances/${inst.id}`, { headers: getAuthHeaders() });
                                    patchLine(res.data);
                                    toast.success('Instance deleted');
                                  } catch (e) {
                                    toast.error(e.response?.data?.detail || 'Delete failed');
                                  }
                                }}
                              />
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {overrideLine && (
        <OverrideDialog line={overrideLine} onClose={() => setOverrideLine(null)} onSaved={patchLine} headers={getAuthHeaders()} />
      )}
      {manualLine && (
        <ManualDialog line={manualLine} weeks={data?.weeks || []} onClose={() => setManualLine(null)} onSaved={patchLine} headers={getAuthHeaders()} />
      )}
      {instanceLine && (
        <InstanceDialog {...instanceLine} onClose={() => setInstanceLine(null)} onSaved={patchLine} headers={getAuthHeaders()} />
      )}

      <Dialog open={auditOpen} onOpenChange={setAuditOpen}>
        <DialogContent className="max-w-3xl" data-testid="brsf-audit-dialog">
          <DialogHeader>
            <DialogTitle>Audit Trail — {data?.employee?.full_name} · {month}</DialogTitle>
            <DialogDescription>Every manual adjustment recorded for this employee and month.</DialogDescription>
          </DialogHeader>
          <div className="max-h-[60vh] overflow-auto">
            {audit.length === 0 ? (
              <p className="text-sm text-slate-500 py-6 text-center">No manual adjustments recorded yet.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                  <tr className="text-left">
                    <th className="px-3 py-2">When</th>
                    <th className="px-3 py-2">Criteria</th>
                    <th className="px-3 py-2">Action</th>
                    <th className="px-3 py-2 text-right">Prev</th>
                    <th className="px-3 py-2 text-right">New</th>
                    <th className="px-3 py-2">Reason</th>
                    <th className="px-3 py-2">By</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.map((a) => (
                    <tr key={a.id} className="border-b border-slate-100">
                      <td className="px-3 py-2 text-slate-500">{String(a.updated_at || '').slice(0, 16).replace('T', ' ')}</td>
                      <td className="px-3 py-2">{a.code} · {a.criteria}</td>
                      <td className="px-3 py-2">{a.action}</td>
                      <td className="px-3 py-2 text-right number-display">{fmt(a.previous_value)}</td>
                      <td className="px-3 py-2 text-right number-display">{fmt(a.new_value)}</td>
                      <td className="px-3 py-2 text-slate-600">{a.reason || '--'}</td>
                      <td className="px-3 py-2 text-slate-600">{a.updated_by_name || '--'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const OverrideDialog = ({ line, onClose, onSaved, headers }) => {
  const [value, setValue] = useState(line.override_value ?? line.system_value ?? 0);
  const [reason, setReason] = useState(line.override_reason || '');
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      const res = await axios.put(`${API}/brsf/stars/${line.id}/override`, { value: Number(value), reason }, { headers });
      onSaved(res.data);
      toast.success(`${line.code} override saved`);
      onClose();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Override failed');
    } finally {
      setSaving(false);
    }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-md" data-testid="brsf-override-dialog">
        <DialogHeader>
          <DialogTitle>Override — {line.code} {line.name}</DialogTitle>
          <DialogDescription>
            System calculated: <b>{fmt(line.system_value)}</b>
            {line.cap ? ` · Allowed up to ${line.sign > 0 ? '+' : '-'}${line.cap}` : ''}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label className="mb-1.5 block">Override star value</Label>
            <Input type="number" step="0.5" value={value} onChange={(e) => setValue(e.target.value)} data-testid="brsf-override-value" />
          </div>
          <div>
            <Label className="mb-1.5 block">Reason</Label>
            <Textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} data-testid="brsf-override-reason" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={saving} className="bg-[#063c88] text-white" data-testid="brsf-override-save">
            {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />} Save Override
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const ManualDialog = ({ line, weeks, onClose, onSaved, headers }) => {
  const weeklyAllowed = line.frequency === 'weekly';
  const [mode, setMode] = useState(weeklyAllowed ? (line.entry_mode || 'monthly') : 'monthly');
  const [monthlyValue, setMonthlyValue] = useState(line.manual_value ?? 0);
  const [weekly, setWeekly] = useState(() => weeks.map((w) => {
    const existing = (line.weekly || []).find((x) => x.week === w.week);
    return { ...w, value: existing ? Number(existing.value) || 0 : 0 };
  }));
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      const payload = mode === 'monthly'
        ? { entry_mode: 'monthly', monthly_value: Number(monthlyValue), reason }
        : { entry_mode: 'weekly', weekly: weekly.map((w) => ({ week: w.week, start: w.start, end: w.end, value: Number(w.value) || 0 })), reason };
      const res = await axios.put(`${API}/brsf/stars/${line.id}/manual`, payload, { headers });
      onSaved(res.data);
      toast.success(`${line.code} updated`);
      onClose();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-lg" data-testid="brsf-manual-dialog">
        <DialogHeader>
          <DialogTitle>Manual Entry — {line.code} {line.name}</DialogTitle>
          <DialogDescription>Maximum {line.cap} star(s) per month for this criteria.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {weeklyAllowed && (
            <div>
              <Label className="mb-1.5 block">Entry mode</Label>
              <Select value={mode} onValueChange={setMode}>
                <SelectTrigger data-testid="brsf-manual-mode"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="monthly">Monthly (single value)</SelectItem>
                  <SelectItem value="weekly">Weekly (0 or +1 per week)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
          {mode === 'monthly' ? (
            <div>
              <Label className="mb-1.5 block">Monthly star value</Label>
              <Input type="number" min="0" max={line.cap ?? undefined} step="1" value={monthlyValue}
                onChange={(e) => setMonthlyValue(e.target.value)} data-testid="brsf-manual-monthly-value" />
            </div>
          ) : (
            <div className="space-y-2">
              {weekly.map((w, i) => (
                <div key={w.week} className="flex items-center justify-between gap-3 border border-slate-200 rounded-lg px-3 py-2">
                  <span className="text-sm text-slate-700">Week {w.week} <span className="text-xs text-slate-400">({w.start} → {w.end})</span></span>
                  <Select value={String(w.value)} onValueChange={(v) => setWeekly((p) => p.map((x, j) => (j === i ? { ...x, value: Number(v) } : x)))}>
                    <SelectTrigger className="w-24" data-testid={`brsf-manual-week-${w.week}`}><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="0">0</SelectItem>
                      <SelectItem value="1">+1</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              ))}
            </div>
          )}
          <div>
            <Label className="mb-1.5 block">Reason / remarks</Label>
            <Textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} data-testid="brsf-manual-reason" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={saving} className="bg-[#063c88] text-white" data-testid="brsf-manual-save">
            {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />} Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const InstanceDialog = ({ line, instance, onClose, onSaved, headers }) => {
  const [form, setForm] = useState({
    date: instance?.date || new Date().toISOString().slice(0, 10),
    time: instance?.time || '',
    remarks: instance?.remarks || '',
    value: instance?.value ?? (line.code === 'N07' ? -3 : -4),
  });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      const body = { ...form, value: Number(form.value) };
      const res = instance
        ? await axios.put(`${API}/brsf/stars/${line.id}/instances/${instance.id}`, body, { headers })
        : await axios.post(`${API}/brsf/stars/${line.id}/instances`, body, { headers });
      onSaved(res.data);
      toast.success(instance ? 'Instance updated' : 'Instance added');
      onClose();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-md" data-testid="brsf-instance-dialog">
        <DialogHeader>
          <DialogTitle>{instance ? 'Edit' : 'Add'} Instance — {line.code} {line.name}</DialogTitle>
          <DialogDescription>Negative criteria — the star value must be zero or negative.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="mb-1.5 block">Date</Label>
              <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} data-testid="brsf-instance-date" />
            </div>
            <div>
              <Label className="mb-1.5 block">Time</Label>
              <Input type="time" value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })} data-testid="brsf-instance-time" />
            </div>
          </div>
          <div>
            <Label className="mb-1.5 block">Star value</Label>
            <Input type="number" step="1" max="0" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} data-testid="brsf-instance-value" />
          </div>
          <div>
            <Label className="mb-1.5 block">Remarks</Label>
            <Textarea value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} rows={3} data-testid="brsf-instance-remarks" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={saving} className="bg-[#063c88] text-white" data-testid="brsf-instance-save">
            {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />} Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default BrsfFramework;
