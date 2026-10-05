import { useState, useEffect, useCallback, useMemo, Fragment } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Plus, Trash2, Pencil, Receipt, Users, Calculator, X, CheckCircle2, Download, RefreshCw, Eye, FileCheck2, Copy, Search, Filter, MinusCircle, PlusCircle, History, Sparkles } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Checkbox } from '../components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { MonthPicker } from '../components/ui/month-picker';
import { DatePicker } from '../components/ui/date-picker';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const inr = (n) => '₹' + Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// Display any ISO / date-like value as DD-MM-YYYY. Empty inputs return "".
const fmtDMY = (v) => {
  if (!v) return '';
  const s = typeof v === 'string' ? v : String(v);
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return `${m[3]}-${m[2]}-${m[1]}`;
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  return `${dd}-${mm}-${d.getFullYear()}`;
};

const emptyComponent = (order) => ({
  name: '', component_type: 'earning', operation: 'add', calc_type: 'percentage',
  percentage_value: '', fixed_amount: '', calc_base: 'monthly_pay',
  proratable: true, active: true, display_order: order,
});

const CALC_LABEL = { percentage: '% of Base', fixed: 'Fixed Amount', payroll_extra_pay: 'Extra Pay (Payroll)' };

// ---------- Shared calculation breakdown ----------
export const CalcBreakdown = ({ calc }) => {
  // Group components by category, preserving display order within each group
  const grouped = {};
  const groupOrder = [];
  (calc.components || []).forEach((c) => {
    const cat = c.category || 'Uncategorized';
    if (!grouped[cat]) { grouped[cat] = []; groupOrder.push(cat); }
    grouped[cat].push(c);
  });
  const catSubtotal = (rows) => rows.reduce((acc, r) => acc + (Number(r.amount) || 0), 0);
  const catMonthlySubtotal = (rows) => rows.reduce((acc, r) => acc + (Number(r.monthly_amount) || 0), 0);

  return (
    <div className="space-y-4" data-testid="calc-breakdown">
      <div className="grid grid-cols-2 sm:grid-cols-6 gap-3 text-center">
        {[
          ['Month', calc.month],
          ['Calendar Days', calc.calendar_days],
          ['Payable Days', calc.payable_days],
          ['Extra Pay Days', calc.extra_pay_days],
          ['Per-Day Salary', inr(calc.per_day_salary)],
          ['Attendance Payable', inr(calc.attendance_payable)],
        ].map(([l, v]) => (
          <div key={l} className="bg-slate-50 rounded-lg p-3">
            <div className="text-xs text-slate-400">{l}</div>
            <div className="font-semibold text-slate-800">{v}</div>
          </div>
        ))}
      </div>
      <table className="w-full text-sm">
        <thead className="text-xs text-slate-500 uppercase border-b">
          <tr><th className="text-left py-2">Component</th><th className="text-left py-2">Basis</th><th className="text-right py-2">Full Month</th><th className="text-right py-2">This Month</th></tr>
        </thead>
        <tbody>
          {groupOrder.map((cat) => (
            <Fragment key={`grp-${cat}`}>
              <tr className="bg-slate-50">
                <td colSpan="4" className="py-1.5 px-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500" data-testid={`group-header-${cat}`}>{cat}</td>
              </tr>
              {grouped[cat].map((c, i) => (
                <tr key={`${cat}-${i}`} className="border-b border-slate-100">
                  <td className="py-2 pl-3 font-medium">
                    {c.name}
                    {c.operation === 'deduct' && (
                      <span className="ml-1 text-[10px] uppercase tracking-wide text-slate-400">
                        {c.include_in_gross ? '(CTC · deducted)' : '(deduction)'}
                      </span>
                    )}
                    {c.capped && c.deduct_amount != null && c.deduct_amount !== c.amount && (
                      <span className="ml-1 text-[10px] uppercase tracking-wide text-amber-600" title={`Statutory monthly cap: ₹${Number(c.deduct_amount).toLocaleString('en-IN')} is deducted regardless of payable-day proration on CTC line.`}>
                        · deducted {inr(c.deduct_amount)} (cap)
                      </span>
                    )}
                  </td>
                  <td className="py-2 text-xs text-slate-500">
                    {c.auto_note
                      ? c.auto_note
                      : (c.calc_type === 'percentage'
                          ? `${c.percentage_value}% of ${c.calc_base && c.calc_base !== 'monthly_pay' ? c.calc_base : 'base'}`
                          : CALC_LABEL[c.calc_type])}
                    {c.proratable === false ? ' · not prorated' : ''}
                  </td>
                  <td className="py-2 text-right">{inr(c.monthly_amount)}</td>
                  <td className="py-2 text-right font-medium text-slate-800">{inr(c.amount)}</td>
                </tr>
              ))}
              <tr className="border-b bg-slate-50/60">
                <td colSpan="2" className="py-1.5 pl-3 text-xs text-slate-500 font-semibold">Subtotal · {cat}</td>
                <td className="py-1.5 text-right text-xs font-semibold text-slate-600">{inr(catMonthlySubtotal(grouped[cat]))}</td>
                <td className="py-1.5 text-right text-xs font-semibold text-slate-700" data-testid={`group-subtotal-${cat}`}>{inr(catSubtotal(grouped[cat]))}</td>
              </tr>
            </Fragment>
          ))}
          {calc.other_allowance > 0 && (
            <tr className="border-b border-slate-100">
              <td className="py-2 font-medium">Other Allowance (Extra Pay)</td>
              <td className="py-2 text-xs text-slate-500">{calc.extra_pay_days} day(s) × per-day</td>
              <td className="py-2 text-right">—</td>
              <td className="py-2 text-right font-medium">{inr(calc.other_allowance)}</td>
            </tr>
          )}
        </tbody>
        <tfoot>
          <tr className="text-sm border-t">
            <td colSpan="3" className="py-2 text-right text-slate-500">Template Earnings <span className="text-[10px] text-slate-400">(= Attendance Payable)</span></td>
            <td className="py-2 text-right font-semibold" data-testid="preview-template-earnings">{inr(calc.attendance_payable)}</td>
          </tr>
          <tr className="text-sm">
            <td colSpan="3" className="py-2 text-right text-slate-500">Gross Earnings <span className="text-[10px] text-slate-400">(Template + Other Allowance)</span></td>
            <td className="py-2 text-right font-semibold" data-testid="preview-gross">{inr(calc.gross_earnings)}</td>
          </tr>
          <tr className="text-sm">
            <td colSpan="3" className="py-2 text-right text-slate-500">Total Deductions <span className="text-[10px] text-slate-400">(PF + Gratuity)</span></td>
            <td className="py-2 text-right font-semibold text-red-600" data-testid="preview-deductions">−{inr(calc.total_deductions)}</td>
          </tr>
          <tr className="text-base border-t">
            <td colSpan="3" className="py-3 text-right font-semibold">NET PAY</td>
            <td className="py-3 text-right font-bold text-emerald-700" data-testid="preview-net">{inr(calc.net_pay)}</td>
          </tr>
          {calc.net_pay_rounded != null && Math.abs(calc.net_pay_rounded - calc.net_pay) > 0.01 && (
            <tr className="text-xs">
              <td colSpan="3" className="py-1 text-right text-slate-400">Rounded Payable</td>
              <td className="py-1 text-right font-medium text-slate-500">₹{Number(calc.net_pay_rounded).toLocaleString('en-IN')}</td>
            </tr>
          )}
        </tfoot>
      </table>
    </div>
  );
};

// ---------- Template form ----------
const TemplateForm = ({ initial, onSaved, onClose, headers }) => {
  const [name, setName] = useState(initial?.name || '');
  const [description, setDescription] = useState(initial?.description || '');
  const [status, setStatus] = useState(initial?.status || 'Active');
  const [components, setComponents] = useState(
    initial?.components?.map((c, i) => ({ ...c, display_order: i })) || [emptyComponent(0)]
  );
  const [saving, setSaving] = useState(false);

  const setComp = (i, patch) => setComponents((prev) => prev.map((c, idx) => {
    if (idx !== i) return c;
    const next = { ...c, ...patch };
    if (patch.component_type) {
      next.operation = patch.component_type === 'earning' ? 'add' : 'deduct';
    }
    return next;
  }));

  const save = async () => {
    if (!name.trim()) return toast.error('Template name is required');
    const payload = {
      name: name.trim(), description, status,
      components: components.map((c, i) => ({
        ...c, display_order: i,
        percentage_value: c.calc_type === 'percentage' ? Number(c.percentage_value || 0) : null,
        fixed_amount: c.calc_type === 'fixed' ? Number(c.fixed_amount || 0) : null,
        calc_base: c.calc_type === 'percentage' ? (c.calc_base || 'monthly_pay') : null,
        base_percentage: (c.base_percentage === '' || c.base_percentage == null) ? null : Number(c.base_percentage),
        // PF & Gratuity are auto-recognised CTC lines by name — always include in gross.
        // Regular earnings are always in gross. Non-CTC deductions are handled by the backend.
        include_in_gross: c.component_type === 'earning'
          || /pf|provident|gratuity/i.test(c.name || ''),
      })),
    };
    setSaving(true);
    try {
      if (initial?.id) await axios.put(`${API}/payslips/templates/${initial.id}`, payload, { headers });
      else await axios.post(`${API}/payslips/templates`, payload, { headers });
      toast.success(initial?.id ? 'Template updated' : 'Template created');
      onSaved();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save template');
    } finally { setSaving(false); }
  };

  const baseOptions = (idx) => ['monthly_pay', ...components.slice(0, idx).map((c) => c.name).filter(Boolean)];

  return (
    <div className="space-y-4" data-testid="template-form">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="sm:col-span-2">
          <label className="text-xs font-medium text-slate-500">Template Name *</label>
          <Input data-testid="template-name-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Full-Time Standard" />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-500">Status</label>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger data-testid="template-status-select"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="Active">Active</SelectItem>
              <SelectItem value="Inactive">Inactive</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div>
        <label className="text-xs font-medium text-slate-500">Description</label>
        <Input data-testid="template-description-input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold">Salary Components</h4>
          <Button data-testid="add-component-btn" size="sm" variant="outline" onClick={() => setComponents((p) => [...p, emptyComponent(p.length)])}>
            <Plus className="w-4 h-4 mr-1" /> Add Component
          </Button>
        </div>
        {components.map((c, i) => (
          <div key={i} className="border rounded-lg p-3 bg-slate-50 space-y-2" data-testid={`component-row-${i}`}>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <div className="col-span-2 sm:col-span-1">
                <label className="text-xs text-slate-500">Name *</label>
                <Input data-testid={`component-name-${i}`} value={c.name} onChange={(e) => setComp(i, { name: e.target.value })} placeholder="e.g. Basic" />
              </div>
              <div>
                <label className="text-xs text-slate-500">Type</label>
                <Select value={c.component_type} onValueChange={(v) => setComp(i, { component_type: v })}>
                  <SelectTrigger data-testid={`component-type-${i}`}><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="earning">Earning (ADD)</SelectItem>
                    <SelectItem value="deduction">Deduction (DEDUCT)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs text-slate-500">Calculation</label>
                <Select value={c.calc_type} onValueChange={(v) => setComp(i, { calc_type: v })}>
                  <SelectTrigger data-testid={`component-calc-${i}`}><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="percentage">% of Base</SelectItem>
                    <SelectItem value="fixed">Fixed Amount</SelectItem>
                    <SelectItem value="payroll_extra_pay">Extra Pay (Payroll)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {c.calc_type === 'percentage' && (
                <div>
                  <label className="text-xs text-slate-500">Percentage %</label>
                  <Input data-testid={`component-pct-${i}`} type="number" min="0" max="100" value={c.percentage_value ?? ''} onChange={(e) => setComp(i, { percentage_value: e.target.value })} />
                </div>
              )}
              {c.calc_type === 'fixed' && (
                <div>
                  <label className="text-xs text-slate-500">Amount ₹</label>
                  <Input data-testid={`component-fixed-${i}`} type="number" min="0" value={c.fixed_amount ?? ''} onChange={(e) => setComp(i, { fixed_amount: e.target.value })} />
                </div>
              )}
              {c.component_type === 'deduction' && /pf|provident/i.test(c.name || '') && (
                <div>
                  <label className="text-xs text-slate-500" title="What % of Attendance Payable becomes the PF base (default 100%)">PF Base %</label>
                  <Input data-testid={`component-pf-base-${i}`} type="number" min="0" max="100" value={c.base_percentage ?? ''} onChange={(e) => setComp(i, { base_percentage: e.target.value })} placeholder="e.g. 50" />
                </div>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-4">
              {c.calc_type === 'percentage' && (
                <div className="flex items-center gap-2">
                  <label className="text-xs text-slate-500">Base:</label>
                  <Select value={c.calc_base || 'monthly_pay'} onValueChange={(v) => setComp(i, { calc_base: v })}>
                    <SelectTrigger className="h-8 w-44" data-testid={`component-base-${i}`}><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {baseOptions(i).map((b) => (
                        <SelectItem key={b} value={b}>{b === 'monthly_pay' ? 'Monthly Pay' : b}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              {c.calc_type !== 'payroll_extra_pay' && (
                <label className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer">
                  <input data-testid={`component-proratable-${i}`} type="checkbox" checked={c.proratable !== false} onChange={(e) => setComp(i, { proratable: e.target.checked })} />
                  Prorate by payable days
                </label>
              )}
              <button data-testid={`component-remove-${i}`} className="ml-auto text-red-500 hover:text-red-700" onClick={() => setComponents((p) => p.filter((_, idx) => idx !== i))} disabled={components.length === 1}>
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end gap-2 pt-2">
        <Button variant="outline" onClick={onClose} data-testid="template-cancel-btn">Cancel</Button>
        <Button onClick={save} disabled={saving} data-testid="template-save-btn">{saving ? 'Saving…' : (initial?.id ? 'Update Template' : 'Create Template')}</Button>
      </div>
    </div>
  );
};

// ---------- Main page ----------
export default function Payslips() {
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();
  const [tab, setTab] = useState('templates');
  const [templates, setTemplates] = useState([]);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  // template dialog
  const [tplDialog, setTplDialog] = useState(false);
  const [editingTpl, setEditingTpl] = useState(null);

  // assignment filters + selection
  const [search, setSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [tplFilter, setTplFilter] = useState('all'); // template filter: 'all' | 'none' | <template_id>
  const [selected, setSelected] = useState({});

  // assign dialog (single or bulk)
  const [assignDialog, setAssignDialog] = useState(null); // {employees:[...]}
  const [assignTpl, setAssignTpl] = useState('');
  const [assignEffType, setAssignEffType] = useState('custom_date');
  const [assignDate, setAssignDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [assignEWC, setAssignEWC] = useState('extra_pay');
  const [assignPay, setAssignPay] = useState({});
  const [assignSaving, setAssignSaving] = useState(false);

  // preview
  const [prevEmp, setPrevEmp] = useState('');
  const [prevMonth, setPrevMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [preview, setPreview] = useState(null);
  const [prevLoading, setPrevLoading] = useState(false);

  // monthly payslips
  const [genMonth, setGenMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [slips, setSlips] = useState([]);
  const [slipsLoading, setSlipsLoading] = useState(false);
  const [genLoading, setGenLoading] = useState(false);
  const [viewSlip, setViewSlip] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [t, a] = await Promise.all([
        axios.get(`${API}/payslips/templates`, { headers }),
        axios.get(`${API}/payslips/assignments`, { headers }),
      ]);
      setTemplates(t.data);
      setRows(a.data);
    } catch (e) {
      toast.error('Failed to load payslip data');
    } finally { setLoading(false); }
  }, []); // eslint-disable-line

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const departments = useMemo(() => [...new Set(rows.map((r) => r.department).filter(Boolean))].sort(), [rows]);
  const empTypes = useMemo(() => [...new Set(rows.map((r) => r.employment_type).filter(Boolean))].sort(), [rows]);

  const filtered = useMemo(() => rows.filter((r) => {
    if (deptFilter !== 'all' && r.department !== deptFilter) return false;
    if (typeFilter !== 'all' && r.employment_type !== typeFilter) return false;
    if (tplFilter !== 'all') {
      if (tplFilter === 'none') { if (r.assignment) return false; }
      else if (!r.assignment || r.assignment.template_id !== tplFilter) return false;
    }
    if (search) {
      const s = search.toLowerCase();
      if (!(`${r.full_name} ${r.custom_employee_id || ''}`.toLowerCase().includes(s))) return false;
    }
    return true;
  }), [rows, deptFilter, typeFilter, tplFilter, search]);

  const selectedIds = Object.keys(selected).filter((k) => selected[k]);
  const activeTemplates = templates.filter((t) => t.status === 'Active');

  const openAssign = (emps) => {
    const pay = {};
    emps.forEach((e) => { pay[e.id] = e.assignment?.monthly_pay || ''; });
    setAssignPay(pay);
    const single = emps.length === 1 ? emps[0] : null;
    const existing = single?.assignment;
    setAssignTpl(existing?.template_id || '');
    // Pre-populate Effective From from existing assignment when changing template for a single employee
    const existingType = existing?.effective_from_type || 'custom_date';
    setAssignEffType(existing ? existingType : 'custom_date');
    const existingDate = (existing?.effective_from || '').slice(0, 10);
    setAssignDate(existingDate || new Date().toISOString().slice(0, 10));
    setAssignEWC(existing?.extra_work_compensation || 'extra_pay');
    setAssignDialog({ employees: emps });
  };

  const resolvedEffFrom = (emp) => {
    if (assignEffType === 'joining_date') {
      const d = emp?.date_of_joining || '';
      return typeof d === 'string' ? fmtDMY(d.slice(0, 10)) : '';
    }
    if (assignEffType === 'confirmation_date') {
      const d = emp?.confirmation_date || '';
      return typeof d === 'string' ? fmtDMY(d.slice(0, 10)) : '';
    }
    return fmtDMY(assignDate);
  };

  // Interns don't have a Confirmation Date; if any selected employee lacks it,
  // still let the admin pick it — the backend will error and we'll show a friendly message.
  const anySelectedHasConfirmation = assignDialog?.employees?.some((e) => !!e.confirmation_date);

  const submitAssign = async () => {
    if (!assignTpl) return toast.error('Select a template');
    const items = assignDialog.employees.map((e) => ({ employee_id: e.id, monthly_pay: Number(assignPay[e.id] || 0) }));
    if (items.some((it) => it.monthly_pay <= 0)) return toast.error('Enter Monthly Pay for every employee');
    if (assignEffType === 'custom_date' && !assignDate) return toast.error('Custom Date requires an Effective From date');
    if (assignEffType === 'confirmation_date' && assignDialog.employees.some((e) => !e.confirmation_date))
      return toast.error('Some employees have no Confirmation Date on record');
    if (assignEffType === 'joining_date' && assignDialog.employees.some((e) => !e.date_of_joining))
      return toast.error('Some employees have no Joining Date on record');
    setAssignSaving(true);
    try {
      const commonPayload = { template_id: assignTpl, effective_from_type: assignEffType,
                               effective_from: assignDate, extra_work_compensation: assignEWC };
      if (items.length === 1) {
        await axios.post(`${API}/payslips/assignments`, { ...items[0], ...commonPayload }, { headers });
        toast.success('Template assigned');
      } else {
        const res = await axios.post(`${API}/payslips/assignments/bulk`, { ...commonPayload, items }, { headers });
        toast.success(`Assigned to ${res.data.assigned} employee(s)`);
        if (res.data.errors?.length) toast.error(`${res.data.errors.length} failed: ${res.data.errors.map((x) => x.name || x.employee_id).join(', ')}`);
      }
      setAssignDialog(null); setSelected({});
      fetchAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Assignment failed');
    } finally { setAssignSaving(false); }
  };

  const deleteTemplate = async (t) => {
    if (!window.confirm(`Delete template "${t.name}"?`)) return;
    try {
      await axios.delete(`${API}/payslips/templates/${t.id}`, { headers });
      toast.success('Template deleted');
      fetchAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Delete failed');
    }
  };

  // Duplicate template: copy components, auto-suggest a unique name, open Edit dialog as new template.
  const duplicateTemplate = (t) => {
    const existingNames = new Set(templates.map((x) => (x.name || '').toLowerCase()));
    let suggested = `${t.name} (Copy)`;
    let i = 2;
    while (existingNames.has(suggested.toLowerCase())) {
      suggested = `${t.name} (Copy ${i})`;
      i++;
    }
    // Strip id + audit fields so the save flow POSTs a new template.
    const cleanComps = (t.components || []).map((c) => {
      const { _id, ...rest } = c;
      return { ...rest };
    });
    setEditingTpl({
      ...t,
      id: undefined,
      _id: undefined,
      name: suggested,
      components: cleanComps,
      created_at: undefined,
      updated_at: undefined,
    });
    setTplDialog(true);
    toast.success(`Duplicated as "${suggested}" — edit and save`);
  };

  const runPreview = async () => {
    if (!prevEmp) return toast.error('Select an employee');
    setPrevLoading(true); setPreview(null);
    try {
      const res = await axios.post(`${API}/payslips/calculate`, { employee_id: prevEmp, month: prevMonth }, { headers });
      setPreview(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Calculation failed');
    } finally { setPrevLoading(false); }
  };

  const assignedRows = rows.filter((r) => r.assignment);

  // ----- monthly payslips handlers -----
  const fetchSlips = useCallback(async (m) => {
    setSlipsLoading(true);
    try {
      const res = await axios.get(`${API}/payslips/generated`, { headers, params: { month: m } });
      setSlips(res.data);
    } catch { toast.error('Failed to load payslips'); }
    finally { setSlipsLoading(false); }
  }, []); // eslint-disable-line

  useEffect(() => { if (tab === 'monthly') fetchSlips(genMonth); }, [tab, genMonth, fetchSlips]);

  const generateSlips = async () => {
    setGenLoading(true);
    try {
      const res = await axios.post(`${API}/payslips/generate`, { month: genMonth }, { headers });
      const { generated, skipped_confirmed, errors } = res.data;
      toast.success(`Generated ${generated} payslip(s)${skipped_confirmed ? `, ${skipped_confirmed} already confirmed (skipped)` : ''}`);
      if (errors?.length) toast.error(`${errors.length} failed: ${errors.slice(0, 3).map((x) => `${x.name} — ${x.error}`).join('; ')}${errors.length > 3 ? '…' : ''}`, { duration: 8000 });
      fetchSlips(genMonth);
    } catch (e) { toast.error(e.response?.data?.detail || 'Generation failed'); }
    finally { setGenLoading(false); }
  };

  const confirmSlip = async (s) => {
    try {
      await axios.post(`${API}/payslips/${s.id}/confirm`, {}, { headers });
      toast.success(`Confirmed payslip for ${s.employee_name}`);
      fetchSlips(genMonth);
    } catch (e) { toast.error(e.response?.data?.detail || 'Confirm failed'); }
  };

  const unconfirmSlip = async (s) => {
    if (!window.confirm(`Revert ${s.employee_name}'s payslip to draft? It will be hidden from the employee.`)) return;
    try {
      await axios.post(`${API}/payslips/${s.id}/unconfirm`, {}, { headers });
      toast.success('Reverted to draft');
      fetchSlips(genMonth);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const confirmAll = async () => {
    // "Confirm All" honours current filters — only visible drafts are confirmed
    const draftIds = filteredSlips.filter((s) => s.status === 'draft').map((s) => s.id);
    if (draftIds.length === 0) { toast.error('No drafts to confirm in current view'); return; }
    const scoped = draftIds.length !== slips.filter((s) => s.status === 'draft').length;
    const msg = scoped
      ? `Confirm ${draftIds.length} filtered draft payslip(s) for ${genMonth}?`
      : `Confirm ALL draft payslips for ${genMonth}? Employees will see them from the 5th of the following month.`;
    if (!window.confirm(msg)) return;
    try {
      const body = scoped ? { month: genMonth, ids: draftIds } : { month: genMonth };
      const res = await axios.post(`${API}/payslips/confirm-all`, body, { headers });
      toast.success(`Confirmed ${res.data.confirmed} payslip(s)`);
      setSlipSelectedIds(new Set());
      fetchSlips(genMonth);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const confirmSelected = async () => {
    const draftIds = [...slipSelectedIds].filter((id) => slips.find((s) => s.id === id && s.status === 'draft'));
    if (draftIds.length === 0) { toast.error('Select at least one draft to confirm'); return; }
    if (!window.confirm(`Confirm ${draftIds.length} selected payslip(s) for ${genMonth}?`)) return;
    try {
      const res = await axios.post(`${API}/payslips/confirm-all`, { month: genMonth, ids: draftIds }, { headers });
      toast.success(`Confirmed ${res.data.confirmed} payslip(s)`);
      setSlipSelectedIds(new Set());
      fetchSlips(genMonth);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const deleteSlip = async (s) => {
    if (!window.confirm(`Delete draft payslip for ${s.employee_name}?`)) return;
    try {
      await axios.delete(`${API}/payslips/${s.id}`, { headers });
      toast.success('Draft deleted');
      fetchSlips(genMonth);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const downloadPdf = async (s) => {
    try {
      const res = await axios.get(`${API}/payslips/${s.id}/pdf`, { headers, responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url; a.download = `Payslip_${s.employee_name.replace(/ /g, '_')}_${s.month}.pdf`;
      a.click(); URL.revokeObjectURL(url);
    } catch { toast.error('PDF download failed'); }
  };

  const previewPdf = async (s) => {
    try {
      const res = await axios.get(`${API}/payslips/${s.id}/pdf`, { headers, responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch { toast.error('PDF preview failed'); }
  };

  // ---- Filters + Selection for Monthly Payslips table ----
  const [slipSearch, setSlipSearch] = useState('');
  const [slipEmpType, setSlipEmpType] = useState('all');
  const [slipDept, setSlipDept] = useState('all');
  const [slipTemplate, setSlipTemplate] = useState('all');
  const [slipStatusFilter, setSlipStatusFilter] = useState('all');
  const [slipSelectedIds, setSlipSelectedIds] = useState(new Set());

  // ---- Manual Adjustment state ----
  const [adjDialog, setAdjDialog] = useState(null); // { slips: [], month }
  const [adjType, setAdjType] = useState('DEDUCTION');
  const [adjAmount, setAdjAmount] = useState('');
  const [adjDesc, setAdjDesc] = useState('');
  const [adjRemarks, setAdjRemarks] = useState('');
  const [adjSaving, setAdjSaving] = useState(false);
  const [viewAdjSlip, setViewAdjSlip] = useState(null); // slip whose adjustments are being viewed

  const openAdjDialog = (slipsForAdj) => {
    setAdjType('DEDUCTION'); setAdjAmount(''); setAdjDesc(''); setAdjRemarks('');
    setAdjDialog({ slips: slipsForAdj, month: genMonth });
  };
  const submitAdjustment = async () => {
    const amt = Number(adjAmount);
    if (!amt || amt <= 0) { toast.error('Amount must be > 0'); return; }
    if (!adjDesc.trim()) { toast.error('Description is required'); return; }
    setAdjSaving(true);
    try {
      const res = await axios.post(`${API}/payslips/adjustments`, {
        payslip_ids: adjDialog.slips.map((s) => s.id),
        adjustment_type: adjType,
        amount: amt,
        description: adjDesc.trim(),
        remarks: adjRemarks.trim(),
      }, { headers });
      const okN = res.data.created.length;
      const errN = res.data.errors.length;
      if (okN) toast.success(`${okN} adjustment(s) created and payslip(s) recalculated`);
      if (errN) toast.error(`${errN} failed: ${res.data.errors.slice(0, 2).map((e) => e.error).join('; ')}`, { duration: 6000 });
      setAdjDialog(null);
      setSlipSelectedIds(new Set());
      fetchSlips(genMonth);
    } catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
    finally { setAdjSaving(false); }
  };

  // Distinct dropdown options built from current month's slips
  const slipDepartments = useMemo(
    () => Array.from(new Set(slips.map((s) => s.employee?.department).filter(Boolean))).sort(),
    [slips]
  );
  const slipEmpTypes = useMemo(
    () => Array.from(new Set(slips.map((s) => s.employee?.employment_type).filter(Boolean))).sort(),
    [slips]
  );
  const slipTemplateNames = useMemo(
    () => Array.from(new Set(slips.map((s) => s.template_name).filter(Boolean))).sort(),
    [slips]
  );

  const filteredSlips = useMemo(() => {
    const q = slipSearch.trim().toLowerCase();
    return slips.filter((s) => {
      if (slipEmpType !== 'all' && s.employee?.employment_type !== slipEmpType) return false;
      if (slipDept !== 'all' && s.employee?.department !== slipDept) return false;
      if (slipTemplate !== 'all' && s.template_name !== slipTemplate) return false;
      if (slipStatusFilter !== 'all' && s.status !== slipStatusFilter) return false;
      if (!q) return true;
      return (
        (s.employee_name || '').toLowerCase().includes(q) ||
        (s.employee?.custom_employee_id || '').toLowerCase().includes(q) ||
        (s.employee?.email || '').toLowerCase().includes(q)
      );
    });
  }, [slips, slipSearch, slipEmpType, slipDept, slipTemplate, slipStatusFilter]);

  const clearSlipFilters = () => {
    setSlipSearch(''); setSlipEmpType('all'); setSlipDept('all');
    setSlipTemplate('all'); setSlipStatusFilter('all');
  };
  const filtersActive = slipSearch || slipEmpType !== 'all' || slipDept !== 'all' || slipTemplate !== 'all' || slipStatusFilter !== 'all';

  // ---- Sorting for Monthly Payslips table ----
  const [slipSort, setSlipSort] = useState({ key: 'employee_name', dir: 'asc' });
  const toggleSort = (key) => setSlipSort((s) => ({ key, dir: s.key === key && s.dir === 'asc' ? 'desc' : 'asc' }));
  const sortedSlips = [...filteredSlips].sort((a, b) => {
    const dir = slipSort.dir === 'asc' ? 1 : -1;
    const get = (row, k) => {
      if (k === 'employee_name') return row.employee_name || '';
      if (k === 'template_name') return row.template_name || '';
      if (k === 'payable_days') return Number(row.calc?.payable_days || 0);
      if (k === 'gross_earnings') return Number(row.calc?.gross_earnings || 0);
      if (k === 'total_deductions') return Number(row.calc?.total_deductions || 0);
      if (k === 'net_pay') return Number(row.calc?.net_pay || 0);
      if (k === 'status') return row.status || '';
      return '';
    };
    const va = get(a, slipSort.key), vb = get(b, slipSort.key);
    if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir;
    return String(va).localeCompare(String(vb)) * dir;
  });
  const sortIcon = (k) => slipSort.key === k ? (slipSort.dir === 'asc' ? '↑' : '↓') : '↕';

  const draftCount = slips.filter((s) => s.status === 'draft').length;
  const confirmedCount = slips.filter((s) => s.status === 'confirmed').length;

  return (
    <div className="space-y-6" data-testid="payslips-page">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-emerald-100 text-emerald-700"><Receipt className="w-6 h-6" /></div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Payslips</h1>
          <p className="text-sm text-slate-500">Template management, employee assignment & salary calculation</p>
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="templates" data-testid="tab-templates"><Receipt className="w-4 h-4 mr-1.5" />Templates</TabsTrigger>
          <TabsTrigger value="assignments" data-testid="tab-assignments"><Users className="w-4 h-4 mr-1.5" />Assignments</TabsTrigger>
          <TabsTrigger value="monthly" data-testid="tab-monthly"><FileCheck2 className="w-4 h-4 mr-1.5" />Monthly Payslips</TabsTrigger>
          <TabsTrigger value="preview" data-testid="tab-preview"><Calculator className="w-4 h-4 mr-1.5" />Calculation Preview</TabsTrigger>
        </TabsList>

        {/* ---------- Templates ---------- */}
        <TabsContent value="templates" className="space-y-4">
          <div className="flex justify-end">
            <Button data-testid="new-template-btn" onClick={() => { setEditingTpl(null); setTplDialog(true); }}>
              <Plus className="w-4 h-4 mr-1" /> New Template
            </Button>
          </div>
          <div className="bg-white rounded-xl border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
                <tr>
                  <th className="text-left px-4 py-3">Template</th>
                  <th className="text-left px-4 py-3">Components</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-left px-4 py-3">Assigned To</th>
                  <th className="text-right px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan="5" className="px-4 py-8 text-center text-slate-400">Loading…</td></tr>
                ) : templates.length === 0 ? (
                  <tr><td colSpan="5" className="px-4 py-8 text-center text-slate-400" data-testid="no-templates-msg">No templates yet. Create your first payslip template.</td></tr>
                ) : templates.map((t) => {
                  const count = assignedRows.filter((r) => r.assignment.template_id === t.id).length;
                  return (
                    <tr key={t.id} className="border-t hover:bg-slate-50" data-testid={`template-row-${t.name}`}>
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-800">{t.name}</div>
                        {t.description && <div className="text-xs text-slate-400">{t.description}</div>}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {t.components.map((c, i) => (
                            <Badge key={i} variant="outline" className={c.operation === 'add' ? 'text-emerald-700 border-emerald-200' : 'text-red-600 border-red-200'}>
                              {c.name} · {c.calc_type === 'percentage' ? `${c.percentage_value}%` : c.calc_type === 'fixed' ? inr(c.fixed_amount) : CALC_LABEL[c.calc_type]}
                            </Badge>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3"><Badge className={t.status === 'Active' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}>{t.status}</Badge></td>
                      <td className="px-4 py-3">{count} employee(s)</td>
                      <td className="px-4 py-3 text-right">
                        <Button data-testid={`edit-template-${t.name}`} size="sm" variant="ghost" title="Edit" onClick={() => { setEditingTpl(t); setTplDialog(true); }}><Pencil className="w-4 h-4" /></Button>
                        <Button data-testid={`duplicate-template-${t.name}`} size="sm" variant="ghost" title="Duplicate template" onClick={() => duplicateTemplate(t)}><Copy className="w-4 h-4" /></Button>
                        <Button data-testid={`delete-template-${t.name}`} size="sm" variant="ghost" className="text-red-500" title="Delete" onClick={() => deleteTemplate(t)}><Trash2 className="w-4 h-4" /></Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </TabsContent>

        {/* ---------- Assignments ---------- */}
        <TabsContent value="assignments" className="space-y-4">
          <div className="flex flex-wrap gap-2 items-center">
            <Input data-testid="assignment-search" placeholder="Search name / employee ID…" value={search} onChange={(e) => setSearch(e.target.value)} className="w-60" />
            <Select value={deptFilter} onValueChange={setDeptFilter}>
              <SelectTrigger className="w-48" data-testid="assignment-dept-filter"><SelectValue placeholder="Department" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Departments</SelectItem>
                {departments.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-44" data-testid="assignment-type-filter"><SelectValue placeholder="Employee Type" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {empTypes.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={tplFilter} onValueChange={setTplFilter}>
              <SelectTrigger className="w-52" data-testid="assignment-template-filter"><SelectValue placeholder="Template" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Templates</SelectItem>
                <SelectItem value="none">Unassigned</SelectItem>
                {templates.map((t) => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
              </SelectContent>
            </Select>
            {selectedIds.length > 0 && (
              <Button data-testid="bulk-assign-btn" onClick={() => openAssign(filtered.filter((r) => selected[r.id]))}>
                Assign Template to {selectedIds.length} selected
              </Button>
            )}
          </div>
          <div className="bg-white rounded-xl border overflow-x-auto">
            <table className="w-full text-sm min-w-[900px]">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
                <tr>
                  <th className="px-3 py-3">
                    <input data-testid="select-all-checkbox" type="checkbox"
                      checked={filtered.length > 0 && filtered.every((r) => selected[r.id])}
                      onChange={(e) => {
                        const next = { ...selected };
                        filtered.forEach((r) => { next[r.id] = e.target.checked; });
                        setSelected(next);
                      }} />
                  </th>
                  <th className="text-left px-4 py-3">Employee</th>
                  <th className="text-left px-4 py-3">Type</th>
                  <th className="text-left px-4 py-3">Department</th>
                  <th className="text-left px-4 py-3">Template</th>
                  <th className="text-right px-4 py-3">Monthly Pay</th>
                  <th className="text-left px-4 py-3">Effective From</th>
                  <th className="text-right px-4 py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan="8" className="px-4 py-8 text-center text-slate-400">Loading…</td></tr>
                ) : filtered.map((r) => (
                  <tr key={r.id} className="border-t hover:bg-slate-50" data-testid={`assignment-row-${r.full_name}`}>
                    <td className="px-3 py-3 text-center">
                      <input type="checkbox" data-testid={`select-emp-${r.full_name}`} checked={!!selected[r.id]} onChange={(e) => setSelected((p) => ({ ...p, [r.id]: e.target.checked }))} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-800">{r.full_name}</div>
                      <div className="text-xs text-slate-400">{r.custom_employee_id} · {r.designation}</div>
                    </td>
                    <td className="px-4 py-3"><Badge variant="outline">{r.employment_type || '—'}</Badge></td>
                    <td className="px-4 py-3">{r.department || '—'}</td>
                    <td className="px-4 py-3">
                      {r.assignment ? <Badge className="bg-blue-100 text-blue-700">{r.assignment.template_name}</Badge> : <span className="text-slate-400 text-xs">Not assigned</span>}
                    </td>
                    <td className="px-4 py-3 text-right font-medium">{r.assignment ? inr(r.assignment.monthly_pay) : '—'}</td>
                    <td className="px-4 py-3">{fmtDMY(r.assignment?.effective_from) || '—'}</td>
                    <td className="px-4 py-3 text-right">
                      <Button data-testid={`assign-btn-${r.full_name}`} size="sm" variant={r.assignment ? 'outline' : 'default'} onClick={() => openAssign([r])}>
                        {r.assignment ? 'Change' : 'Assign'}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </TabsContent>

        {/* ---------- Monthly Payslips ---------- */}
        <TabsContent value="monthly" className="space-y-4">
          <div className="flex flex-wrap gap-2 items-center">
            <MonthPicker value={genMonth} onChange={setGenMonth} />
            <Button data-testid="generate-payslips-btn" onClick={generateSlips} disabled={genLoading}>
              <RefreshCw className={`w-4 h-4 mr-1 ${genLoading ? 'animate-spin' : ''}`} />
              {genLoading ? 'Generating…' : slips.length ? 'Regenerate Drafts' : 'Generate Payslips'}
            </Button>
            {slipSelectedIds.size > 0 && (
              <>
                <Button data-testid="confirm-selected-btn" variant="outline" className="text-emerald-700 border-emerald-300" onClick={confirmSelected}>
                  <CheckCircle2 className="w-4 h-4 mr-1" /> Confirm Selected ({[...slipSelectedIds].filter((id) => slips.find((s) => s.id === id && s.status === 'draft')).length})
                </Button>
                <Button
                  data-testid="adjust-selected-btn"
                  variant="outline"
                  className="text-[#063c88] border-[#063c88]/40"
                  onClick={() => {
                    const eligible = [...slipSelectedIds]
                      .map((id) => slips.find((s) => s.id === id))
                      .filter((s) => s && s.status === 'draft');
                    if (eligible.length === 0) { toast.error('Select at least one draft payslip'); return; }
                    openAdjDialog(eligible);
                  }}
                >
                  <Sparkles className="w-4 h-4 mr-1" /> Add Adjustment ({[...slipSelectedIds].filter((id) => slips.find((s) => s.id === id && s.status === 'draft')).length})
                </Button>
              </>
            )}
            {draftCount > 0 && slipSelectedIds.size === 0 && (
              <Button data-testid="confirm-all-btn" variant="outline" className="text-emerald-700 border-emerald-300" onClick={confirmAll}>
                <CheckCircle2 className="w-4 h-4 mr-1" />
                {filtersActive ? `Confirm Filtered (${filteredSlips.filter((s) => s.status === 'draft').length})` : `Confirm All (${draftCount})`}
              </Button>
            )}
            <div className="ml-auto flex gap-2">
              <Badge variant="outline" data-testid="draft-count-badge">Draft: {draftCount}</Badge>
              <Badge className="bg-emerald-100 text-emerald-700" data-testid="confirmed-count-badge">Confirmed: {confirmedCount}</Badge>
            </div>
          </div>

          {/* Filter row */}
          {slips.length > 0 && (
            <div className="bg-white rounded-xl border p-3 flex flex-wrap gap-2 items-center" data-testid="slip-filters">
              <div className="relative flex-1 min-w-[220px] max-w-sm">
                <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  className="pl-8"
                  placeholder="Search by name, EMP ID, email…"
                  value={slipSearch}
                  onChange={(e) => setSlipSearch(e.target.value)}
                  data-testid="slip-filter-search"
                />
              </div>
              <Select value={slipEmpType} onValueChange={setSlipEmpType}>
                <SelectTrigger className="w-40" data-testid="slip-filter-emp-type"><SelectValue placeholder="Type" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  {slipEmpTypes.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={slipDept} onValueChange={setSlipDept}>
                <SelectTrigger className="w-48" data-testid="slip-filter-dept"><SelectValue placeholder="Department" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Departments</SelectItem>
                  {slipDepartments.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={slipTemplate} onValueChange={setSlipTemplate}>
                <SelectTrigger className="w-48" data-testid="slip-filter-template"><SelectValue placeholder="Template" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Templates</SelectItem>
                  {slipTemplateNames.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={slipStatusFilter} onValueChange={setSlipStatusFilter}>
                <SelectTrigger className="w-36" data-testid="slip-filter-status"><SelectValue placeholder="Status" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="draft">Draft</SelectItem>
                  <SelectItem value="confirmed">Confirmed</SelectItem>
                </SelectContent>
              </Select>
              {filtersActive && (
                <Button variant="ghost" size="sm" onClick={clearSlipFilters} data-testid="slip-filter-clear">
                  <X className="w-3.5 h-3.5 mr-1" /> Clear
                </Button>
              )}
              <span className="ml-auto text-xs text-slate-500">
                Showing <b>{filteredSlips.length}</b> of {slips.length}
              </span>
            </div>
          )}

          <p className="text-xs text-slate-400">Confirmed payslips become visible to employees from the <b>5th of the following month</b>. Regenerating only updates drafts — confirmed payslips are never overwritten.</p>
          <div className="bg-white rounded-xl border overflow-x-auto">
            <table className="w-full text-sm min-w-[1000px]">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
                <tr>
                  <th className="px-3 py-3 w-10">
                    {(() => {
                      const visibleDraftIds = sortedSlips.filter((s) => s.status === 'draft').map((s) => s.id);
                      const allSelected = visibleDraftIds.length > 0 && visibleDraftIds.every((id) => slipSelectedIds.has(id));
                      const someSelected = visibleDraftIds.some((id) => slipSelectedIds.has(id));
                      return (
                        <Checkbox
                          checked={allSelected ? true : (someSelected ? 'indeterminate' : false)}
                          onCheckedChange={(v) => {
                            setSlipSelectedIds((prev) => {
                              const next = new Set(prev);
                              if (v) visibleDraftIds.forEach((id) => next.add(id));
                              else visibleDraftIds.forEach((id) => next.delete(id));
                              return next;
                            });
                          }}
                          disabled={visibleDraftIds.length === 0}
                          data-testid="slip-select-all"
                          aria-label="Select all drafts"
                        />
                      );
                    })()}
                  </th>
                  <th className="text-left px-4 py-3 cursor-pointer select-none" onClick={() => toggleSort('employee_name')}>Employee <span className="text-slate-300">{sortIcon('employee_name')}</span></th>
                  <th className="text-left px-4 py-3 cursor-pointer select-none" onClick={() => toggleSort('template_name')}>Template <span className="text-slate-300">{sortIcon('template_name')}</span></th>
                  <th className="text-right px-4 py-3 cursor-pointer select-none" onClick={() => toggleSort('payable_days')}>Payable Days <span className="text-slate-300">{sortIcon('payable_days')}</span></th>
                  <th className="text-right px-4 py-3 cursor-pointer select-none" onClick={() => toggleSort('gross_earnings')}>Gross <span className="text-slate-300">{sortIcon('gross_earnings')}</span></th>
                  <th className="text-right px-4 py-3 cursor-pointer select-none" onClick={() => toggleSort('total_deductions')}>Deductions <span className="text-slate-300">{sortIcon('total_deductions')}</span></th>
                  <th className="text-right px-4 py-3 cursor-pointer select-none" onClick={() => toggleSort('net_pay')}>Net Pay <span className="text-slate-300">{sortIcon('net_pay')}</span></th>
                  <th className="text-left px-4 py-3 cursor-pointer select-none" onClick={() => toggleSort('status')}>Status <span className="text-slate-300">{sortIcon('status')}</span></th>
                  <th className="text-right px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {slipsLoading ? (
                  <tr><td colSpan="9" className="px-4 py-8 text-center text-slate-400">Loading…</td></tr>
                ) : sortedSlips.length === 0 ? (
                  <tr><td colSpan="9" className="px-4 py-8 text-center text-slate-400" data-testid="no-slips-msg">
                    {slips.length === 0 ? `No payslips generated for ${genMonth} yet.` : 'No payslips match the current filters.'}
                  </td></tr>
                ) : sortedSlips.map((s) => (
                  <tr key={s.id} className="border-t hover:bg-slate-50" data-testid={`slip-row-${s.employee_name}`}>
                    <td className="px-3 py-3">
                      <Checkbox
                        checked={slipSelectedIds.has(s.id)}
                        onCheckedChange={(v) => {
                          setSlipSelectedIds((prev) => {
                            const next = new Set(prev);
                            if (v) next.add(s.id); else next.delete(s.id);
                            return next;
                          });
                        }}
                        disabled={s.status !== 'draft'}
                        data-testid={`slip-select-${s.employee_name}`}
                        aria-label={`Select ${s.employee_name}`}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-800">{s.employee_name}</div>
                      <div className="text-xs text-slate-400">{s.employee?.custom_employee_id} · {s.employee?.employment_type || '—'}</div>
                    </td>
                    <td className="px-4 py-3">{s.template_name}</td>
                    <td className="px-4 py-3 text-right">{s.calc?.payable_days}</td>
                    <td className="px-4 py-3 text-right">
                      {inr(s.calc?.gross_earnings)}
                      {(s.calc?.manual_additions_total || 0) > 0 && (
                        <div className="text-[10px] text-emerald-600 mt-0.5" title="Manual Additions applied">
                          +{inr(s.calc.manual_additions_total)}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right text-red-600">
                      −{inr(s.calc?.total_deductions)}
                      {(s.calc?.manual_deductions_total || 0) > 0 && (
                        <div className="text-[10px] text-red-500 mt-0.5" title="Manual Deductions applied">
                          incl. −{inr(s.calc.manual_deductions_total)}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold">{inr(s.calc?.net_pay)}</td>
                    <td className="px-4 py-3">
                      <Badge className={s.status === 'confirmed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'} data-testid={`slip-status-${s.employee_name}`}>
                        {s.status === 'confirmed' ? 'Confirmed' : 'Draft'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <Button data-testid={`view-slip-${s.employee_name}`} size="sm" variant="ghost" title="View breakdown" onClick={() => setViewSlip(s)}><Eye className="w-4 h-4" /></Button>
                      <Button data-testid={`preview-pdf-${s.employee_name}`} size="sm" variant="ghost" title="Preview PDF" onClick={() => previewPdf(s)}><FileCheck2 className="w-4 h-4" /></Button>
                      <Button data-testid={`pdf-slip-${s.employee_name}`} size="sm" variant="ghost" title="Download PDF" onClick={() => downloadPdf(s)}><Download className="w-4 h-4" /></Button>
                      <Button
                        data-testid={`adjust-slip-${s.employee_name}`}
                        size="sm" variant="ghost"
                        className="text-[#063c88]"
                        title={s.status === 'draft' ? 'Add Adjustment' : 'Payslip is confirmed — cannot add adjustment'}
                        onClick={() => openAdjDialog([s])}
                        disabled={s.status !== 'draft'}
                      ><Sparkles className="w-4 h-4" /></Button>
                      <Button
                        data-testid={`view-adjustments-${s.employee_name}`}
                        size="sm" variant="ghost"
                        title="View Adjustments & History"
                        onClick={() => setViewAdjSlip(s)}
                      ><History className="w-4 h-4" /></Button>
                      {s.status === 'draft' ? (
                        <>
                          <Button data-testid={`confirm-slip-${s.employee_name}`} size="sm" variant="ghost" className="text-emerald-600" title="Confirm" onClick={() => confirmSlip(s)}><CheckCircle2 className="w-4 h-4" /></Button>
                          <Button data-testid={`delete-slip-${s.employee_name}`} size="sm" variant="ghost" className="text-red-500" title="Delete draft" onClick={() => deleteSlip(s)}><Trash2 className="w-4 h-4" /></Button>
                        </>
                      ) : (
                        <Button data-testid={`unconfirm-slip-${s.employee_name}`} size="sm" variant="ghost" className="text-amber-600" title="Revert to draft" onClick={() => unconfirmSlip(s)}><X className="w-4 h-4" /></Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </TabsContent>

        {/* ---------- Preview ---------- */}
        <TabsContent value="preview" className="space-y-4">
          <div className="flex flex-wrap gap-2 items-end">
            <div>
              <label className="text-xs font-medium text-slate-500">Employee</label>
              <Select value={prevEmp} onValueChange={setPrevEmp}>
                <SelectTrigger className="w-72" data-testid="preview-employee-select"><SelectValue placeholder="Select employee" /></SelectTrigger>
                <SelectContent>
                  {assignedRows.map((r) => <SelectItem key={r.id} value={r.id}>{r.full_name} ({r.custom_employee_id})</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500">Month</label>
              <MonthPicker value={prevMonth} onChange={setPrevMonth} />
            </div>
            <Button data-testid="preview-calculate-btn" onClick={runPreview} disabled={prevLoading}>
              <Calculator className="w-4 h-4 mr-1" /> {prevLoading ? 'Calculating…' : 'Calculate'}
            </Button>
          </div>
          {assignedRows.length === 0 && !loading && (
            <p className="text-sm text-slate-400">No employees have templates assigned yet — assign a template first.</p>
          )}

          {preview && (
            <div className="bg-white rounded-xl border p-6 max-w-3xl" data-testid="preview-result">
              <CalcBreakdown calc={preview} />
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Template dialog */}
      <Dialog open={tplDialog} onOpenChange={setTplDialog}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{editingTpl ? 'Edit Template' : 'New Payslip Template'}</DialogTitle></DialogHeader>
          <TemplateForm initial={editingTpl} headers={headers} onClose={() => setTplDialog(false)} onSaved={() => { setTplDialog(false); fetchAll(); }} />
        </DialogContent>
      </Dialog>

      {/* Slip breakdown dialog */}
      <Dialog open={!!viewSlip} onOpenChange={(o) => !o && setViewSlip(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{viewSlip?.employee_name} — {viewSlip?.month}</DialogTitle></DialogHeader>
          {viewSlip && <CalcBreakdown calc={viewSlip.calc} />}
        </DialogContent>
      </Dialog>

      {/* Assign dialog */}
      <Dialog open={!!assignDialog} onOpenChange={(o) => !o && setAssignDialog(null)}>
        <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Assign Template {assignDialog?.employees.length > 1 ? `(${assignDialog.employees.length} employees)` : ''}</DialogTitle></DialogHeader>
          {assignDialog && (
            <div className="space-y-4" data-testid="assign-dialog">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-slate-500">Template *</label>
                  <Select value={assignTpl} onValueChange={setAssignTpl}>
                    <SelectTrigger data-testid="assign-template-select"><SelectValue placeholder="Select template" /></SelectTrigger>
                    <SelectContent>
                      {activeTemplates.map((t) => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-500">Effective From *</label>
                  <Select value={assignEffType} onValueChange={setAssignEffType}>
                    <SelectTrigger data-testid="assign-eff-type"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="joining_date">Joining Date</SelectItem>
                      {anySelectedHasConfirmation && (
                        <SelectItem value="confirmation_date">Confirmation Date</SelectItem>
                      )}
                      <SelectItem value="custom_date">Custom Date</SelectItem>
                    </SelectContent>
                  </Select>
                  {!anySelectedHasConfirmation && assignDialog.employees.some((e) => (e.employment_type || '').toLowerCase().includes('intern')) && (
                    <div className="text-[10px] text-slate-400 mt-1">Interns have no Confirmation Date — that option is hidden.</div>
                  )}
                </div>
                {assignEffType === 'custom_date' && (
                  <div className="col-span-2">
                    <label className="text-xs font-medium text-slate-500">Custom Effective Date *</label>
                    <DatePicker
                      value={assignDate}
                      onChange={(val) => setAssignDate(val)}
                      className="mt-1.5"
                      data-testid="assign-effective-date"
                    />
                  </div>
                )}
                {assignEffType !== 'custom_date' && (
                  <div className="col-span-2 text-xs bg-slate-50 rounded p-2 space-y-1">
                    {assignDialog.employees.map((e) => {
                      const r = resolvedEffFrom(e);
                      return (
                        <div key={e.id} className={r ? 'text-slate-600' : 'text-amber-600'}>
                          <span className="font-medium">{e.full_name}</span> → {r || 'MISSING — pick Custom Date instead'}
                        </div>
                      );
                    })}
                  </div>
                )}
                <div className="col-span-2">
                  <label className="text-xs font-medium text-slate-500">Extra Work Compensation *</label>
                  <Select value={assignEWC} onValueChange={setAssignEWC}>
                    <SelectTrigger data-testid="assign-ewc"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="extra_pay">Extra Pay (monetary — from Payroll)</SelectItem>
                      <SelectItem value="comp_off">Comp Off (no monetary extra)</SelectItem>
                      <SelectItem value="not_applicable">Not Applicable</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium text-slate-500">Monthly Pay (per employee) *</label>
                {assignDialog.employees.map((e) => (
                  <div key={e.id} className="flex items-center gap-3">
                    <span className="text-sm flex-1 truncate">{e.full_name} <span className="text-xs text-slate-400">({e.custom_employee_id})</span></span>
                    <Input data-testid={`assign-pay-${e.full_name}`} type="number" min="0" className="w-40" placeholder="₹ / month"
                      value={assignPay[e.id] ?? ''} onChange={(ev) => setAssignPay((p) => ({ ...p, [e.id]: ev.target.value }))} />
                  </div>
                ))}
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setAssignDialog(null)} data-testid="assign-cancel-btn"><X className="w-4 h-4 mr-1" />Cancel</Button>
                <Button onClick={submitAssign} disabled={assignSaving} data-testid="assign-submit-btn">{assignSaving ? 'Assigning…' : 'Assign'}</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ---------------- Add Adjustment Dialog ---------------- */}
      <Dialog open={!!adjDialog} onOpenChange={(o) => !o && setAdjDialog(null)}>
        <DialogContent className="max-w-lg" data-testid="adj-dialog">
          <DialogHeader>
            <DialogTitle>
              Add Manual Adjustment {adjDialog?.slips?.length > 1 ? `(${adjDialog.slips.length} employees)` : ''}
            </DialogTitle>
          </DialogHeader>
          {adjDialog && (
            <div className="space-y-4">
              <div className="text-xs bg-slate-50 rounded p-2 max-h-24 overflow-y-auto">
                <div className="font-medium text-slate-600 mb-1">Employee(s):</div>
                {adjDialog.slips.map((s) => (
                  <div key={s.id} className="text-slate-500">{s.employee_name} <span className="text-[10px]">({s.employee?.custom_employee_id || '—'})</span></div>
                ))}
                <div className="mt-1 text-slate-500">Payroll Month: <b>{adjDialog.month}</b></div>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-500 block mb-1">Adjustment Type *</label>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant={adjType === 'ADDITION' ? 'default' : 'outline'}
                    onClick={() => setAdjType('ADDITION')}
                    className={adjType === 'ADDITION' ? 'bg-emerald-600 hover:bg-emerald-700' : ''}
                    data-testid="adj-type-addition"
                  >
                    <PlusCircle className="w-4 h-4 mr-1" /> Addition
                  </Button>
                  <Button
                    type="button"
                    variant={adjType === 'DEDUCTION' ? 'default' : 'outline'}
                    onClick={() => setAdjType('DEDUCTION')}
                    className={adjType === 'DEDUCTION' ? 'bg-red-600 hover:bg-red-700' : ''}
                    data-testid="adj-type-deduction"
                  >
                    <MinusCircle className="w-4 h-4 mr-1" /> Deduction
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-slate-500">Amount (₹) *</label>
                  <Input
                    type="number" min="0" step="0.01" placeholder="e.g., 1000"
                    value={adjAmount} onChange={(e) => setAdjAmount(e.target.value)}
                    data-testid="adj-amount"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-500">Description / Reason *</label>
                  <Input
                    placeholder={adjType === 'ADDITION' ? 'e.g., Performance Incentive' : 'e.g., Advance Recovery'}
                    value={adjDesc} onChange={(e) => setAdjDesc(e.target.value)}
                    data-testid="adj-description"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-500">Remarks (optional)</label>
                <Input
                  placeholder="Any internal note…"
                  value={adjRemarks} onChange={(e) => setAdjRemarks(e.target.value)}
                  data-testid="adj-remarks"
                />
              </div>

              <div className="text-xs bg-amber-50 border border-amber-200 rounded p-2 text-amber-800">
                A separate adjustment record is created per employee. Payslips will be recalculated immediately.
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setAdjDialog(null)} data-testid="adj-cancel"><X className="w-4 h-4 mr-1" />Cancel</Button>
                <Button onClick={submitAdjustment} disabled={adjSaving} data-testid="adj-save">
                  {adjSaving ? 'Saving…' : 'Save Adjustment'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ---------------- View Adjustments + History Dialog ---------------- */}
      {viewAdjSlip && (
        <AdjustmentsDialog
          slip={viewAdjSlip}
          headers={headers}
          onClose={() => setViewAdjSlip(null)}
          onRefresh={() => fetchSlips(genMonth)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
//  Adjustments / History dialog
// ---------------------------------------------------------------------------
const AdjustmentsDialog = ({ slip, headers, onClose, onRefresh }) => {
  const [rows, setRows] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [editAmount, setEditAmount] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const isConfirmed = slip.status === 'confirmed';

  const load = async () => {
    setLoading(true);
    try {
      const [a, h] = await Promise.all([
        axios.get(`${API}/payslips/${slip.id}/adjustments`, { headers, params: { include_deleted: true } }),
        axios.get(`${API}/payslips/${slip.id}/adjustments/history`, { headers }),
      ]);
      setRows(a.data || []);
      setHistory(h.data || []);
    } catch { toast.error('Failed to load adjustments'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []); // eslint-disable-line

  const saveEdit = async (adj) => {
    const amt = Number(editAmount);
    if (!amt || amt <= 0) { toast.error('Amount must be > 0'); return; }
    if (!editDesc.trim()) { toast.error('Description required'); return; }
    try {
      await axios.patch(`${API}/payslips/adjustments/${adj.id}`, { amount: amt, description: editDesc.trim() }, { headers });
      toast.success('Adjustment updated');
      setEditingId(null);
      await load();
      onRefresh();
    } catch (e) { toast.error(e.response?.data?.detail || 'Update failed'); }
  };

  const removeAdj = async (adj) => {
    if (!window.confirm(`Delete this ${adj.adjustment_type.toLowerCase()} of ₹${adj.amount}? History will be preserved.`)) return;
    try {
      await axios.delete(`${API}/payslips/adjustments/${adj.id}`, { headers });
      toast.success('Adjustment deleted');
      await load();
      onRefresh();
    } catch (e) { toast.error(e.response?.data?.detail || 'Delete failed'); }
  };

  const active = rows.filter((r) => r.status === 'active');
  const deleted = rows.filter((r) => r.status !== 'active');

  return (
    <Dialog open={true} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="adj-history-dialog">
        <DialogHeader>
          <DialogTitle>Adjustments — {slip.employee_name} · {slip.month}</DialogTitle>
        </DialogHeader>

        {isConfirmed && (
          <div className="text-xs bg-amber-50 border border-amber-200 rounded p-2 text-amber-800">
            This payslip is confirmed — editing and deletion are disabled. Unconfirm to make changes.
          </div>
        )}

        <div className="space-y-4">
          <div>
            <div className="text-sm font-semibold text-slate-700 mb-2">Active Adjustments ({active.length})</div>
            {loading ? <div className="text-xs text-slate-400">Loading…</div> :
             active.length === 0 ? <div className="text-xs text-slate-400 italic">No active adjustments.</div> :
             <div className="space-y-2">
               {active.map((a) => (
                 <div key={a.id} className="flex items-center gap-2 border rounded-lg p-2 bg-white" data-testid={`adj-row-${a.id}`}>
                   <Badge className={a.adjustment_type === 'ADDITION' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}>
                     {a.adjustment_type === 'ADDITION' ? <PlusCircle className="w-3 h-3 mr-1" /> : <MinusCircle className="w-3 h-3 mr-1" />}
                     {a.adjustment_type}
                   </Badge>
                   {editingId === a.id ? (
                     <>
                       <Input type="number" min="0" className="w-28" value={editAmount} onChange={(e) => setEditAmount(e.target.value)} />
                       <Input className="flex-1" value={editDesc} onChange={(e) => setEditDesc(e.target.value)} />
                       <Button size="sm" onClick={() => saveEdit(a)}><CheckCircle2 className="w-3.5 h-3.5" /></Button>
                       <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}><X className="w-3.5 h-3.5" /></Button>
                     </>
                   ) : (
                     <>
                       <div className="text-sm font-semibold w-28">₹{Number(a.amount).toLocaleString('en-IN')}</div>
                       <div className="flex-1 min-w-0">
                         <div className="text-sm text-slate-800 truncate">{a.description}</div>
                         {a.remarks && <div className="text-[10px] text-slate-400 truncate">{a.remarks}</div>}
                         <div className="text-[10px] text-slate-400">by {a.created_by} · {a.created_at?.slice(0, 16).replace('T', ' ')}</div>
                       </div>
                       <Button size="sm" variant="ghost" disabled={isConfirmed}
                         onClick={() => { setEditingId(a.id); setEditAmount(String(a.amount)); setEditDesc(a.description || ''); }}
                         data-testid={`adj-edit-${a.id}`}
                       ><Pencil className="w-3.5 h-3.5" /></Button>
                       <Button size="sm" variant="ghost" className="text-red-500" disabled={isConfirmed} onClick={() => removeAdj(a)} data-testid={`adj-delete-${a.id}`}>
                         <Trash2 className="w-3.5 h-3.5" />
                       </Button>
                     </>
                   )}
                 </div>
               ))}
             </div>
            }
          </div>

          {deleted.length > 0 && (
            <div>
              <div className="text-sm font-semibold text-slate-500 mb-2">Deleted / Inactive ({deleted.length})</div>
              <div className="space-y-1">
                {deleted.map((a) => (
                  <div key={a.id} className="flex items-center gap-2 border rounded p-2 bg-slate-50 opacity-70">
                    <Badge variant="outline">{a.adjustment_type}</Badge>
                    <span className="text-sm line-through">₹{Number(a.amount).toLocaleString('en-IN')} — {a.description}</span>
                    <span className="text-[10px] text-slate-400 ml-auto">deleted by {a.deleted_by}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <div className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-1"><History className="w-3.5 h-3.5" /> Change History ({history.length})</div>
            {history.length === 0 ? <div className="text-xs text-slate-400 italic">No history yet.</div> :
             <div className="text-xs space-y-1 max-h-60 overflow-y-auto">
               {history.map((h) => (
                 <div key={h.id} className="border-l-2 border-slate-200 pl-2 py-1">
                   <div className="text-slate-500">
                     <b>{h.action.toUpperCase()}</b> · by {h.actor} · {h.at?.slice(0, 16).replace('T', ' ')}
                   </div>
                   {h.action === 'updated' && (
                     <div className="text-slate-700">
                       Amount: ₹{h.old_amount} → <b>₹{h.new_amount}</b>
                       {h.old_description !== h.new_description && <div>Desc: &quot;{h.old_description}&quot; → &quot;{h.new_description}&quot;</div>}
                     </div>
                   )}
                   {h.action === 'created' && <div className="text-emerald-700">Amount: ₹{h.new_amount} · {h.new_description}</div>}
                   {h.action === 'deleted' && <div className="text-red-600">Removed: ₹{h.old_amount} · {h.old_description}</div>}
                 </div>
               ))}
             </div>
            }
          </div>
        </div>

        <div className="flex justify-end mt-4">
          <Button variant="outline" onClick={onClose}>Close</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
