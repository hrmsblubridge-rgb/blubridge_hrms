import { useState, useEffect, useCallback, useMemo, Fragment } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Plus, Trash2, Pencil, Receipt, Users, Calculator, X, CheckCircle2, Download, RefreshCw, Eye, FileCheck2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { MonthPicker } from '../components/ui/month-picker';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const inr = (n) => '₹' + Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const emptyComponent = (order) => ({
  name: '', component_type: 'earning', operation: 'add', calc_type: 'percentage',
  percentage_value: '', fixed_amount: '', calc_base: 'monthly_pay',
  proratable: true, active: true, include_in_gross: true,
  category: '', max_amount: '', display_order: order,
});

const CALC_LABEL = { percentage: '% of Base', fixed: 'Fixed Amount', payroll_extra_pay: 'Extra Pay (Payroll)' };
const CATEGORIES = ['Base Components (A)', 'Basket of Allowances (B)', 'Retirement Benefits (C)'];

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
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-center">
        {[['Month', calc.month], ['Calendar Days', calc.calendar_days], ['Payable Days', calc.payable_days], ['Extra Pay Days', calc.extra_pay_days], ['Per-Day Salary', inr(calc.per_day_salary)]].map(([l, v]) => (
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
                    {c.capped && (
                      <span className="ml-1 text-[10px] uppercase tracking-wide text-amber-600" title={`Capped at ${inr(c.max_amount)}`}>· capped</span>
                    )}
                  </td>
                  <td className="py-2 text-xs text-slate-500">
                    {c.calc_type === 'percentage'
                      ? `${c.percentage_value}% of ${c.calc_base && c.calc_base !== 'monthly_pay' ? c.calc_base : 'base'}`
                      : CALC_LABEL[c.calc_type]}
                    {c.max_amount ? ` · cap ${inr(c.max_amount)}` : ''}
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
          <tr className="text-sm">
            <td colSpan="3" className="py-2 text-right text-slate-500">Gross Earnings</td>
            <td className="py-2 text-right font-semibold" data-testid="preview-gross">{inr(calc.gross_earnings)}</td>
          </tr>
          <tr className="text-sm">
            <td colSpan="3" className="py-2 text-right text-slate-500">Total Deductions</td>
            <td className="py-2 text-right font-semibold text-red-600" data-testid="preview-deductions">−{inr(calc.total_deductions)}</td>
          </tr>
          <tr className="text-base border-t">
            <td colSpan="3" className="py-3 text-right font-semibold">NET PAY</td>
            <td className="py-3 text-right font-bold text-emerald-700" data-testid="preview-net">{inr(calc.net_pay)}</td>
          </tr>
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
      // Earnings always in gross; deductions default to NOT in gross (user can flip on for CTC lines like PF Employer, Gratuity)
      next.include_in_gross = patch.component_type === 'earning';
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
        max_amount: (c.max_amount === '' || c.max_amount == null) ? null : Number(c.max_amount),
        category: c.category || '',
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
                <label className="text-xs text-slate-500">Category</label>
                <Select value={c.category || '__none__'} onValueChange={(v) => setComp(i, { category: v === '__none__' ? '' : v })}>
                  <SelectTrigger data-testid={`component-category-${i}`}><SelectValue placeholder="—" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">— None —</SelectItem>
                    {CATEGORIES.map((cat) => (<SelectItem key={cat} value={cat}>{cat}</SelectItem>))}
                  </SelectContent>
                </Select>
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
              {c.calc_type !== 'payroll_extra_pay' && (
                <div>
                  <label className="text-xs text-slate-500" title="Optional monthly cap. Full-month value never exceeds this (e.g. PF Employer capped at 1800).">Max Amount ₹ <span className="text-slate-300">(optional cap)</span></label>
                  <Input data-testid={`component-max-${i}`} type="number" min="0" value={c.max_amount ?? ''} onChange={(e) => setComp(i, { max_amount: e.target.value })} placeholder="e.g. 1800" />
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
              {c.component_type === 'deduction' && (
                <label className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer" title="Enable for employer contributions (PF Company, Gratuity) that appear on both Earnings and Deductions sides — they cancel out in Net Pay. Leave off for real employee deductions like TDS or Professional Tax.">
                  <input data-testid={`component-include-gross-${i}`} type="checkbox" checked={!!c.include_in_gross} onChange={(e) => setComp(i, { include_in_gross: e.target.checked })} />
                  Include in Gross (CTC line)
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
  const [selected, setSelected] = useState({});

  // assign dialog (single or bulk)
  const [assignDialog, setAssignDialog] = useState(null); // {employees:[...]}
  const [assignTpl, setAssignTpl] = useState('');
  const [assignDate, setAssignDate] = useState(() => new Date().toISOString().slice(0, 10));
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
    if (search) {
      const s = search.toLowerCase();
      if (!(`${r.full_name} ${r.custom_employee_id || ''}`.toLowerCase().includes(s))) return false;
    }
    return true;
  }), [rows, deptFilter, typeFilter, search]);

  const selectedIds = Object.keys(selected).filter((k) => selected[k]);
  const activeTemplates = templates.filter((t) => t.status === 'Active');

  const openAssign = (emps) => {
    const pay = {};
    emps.forEach((e) => { pay[e.id] = e.assignment?.monthly_pay || ''; });
    setAssignPay(pay);
    setAssignTpl(emps.length === 1 ? (emps[0].assignment?.template_id || '') : '');
    setAssignDate(new Date().toISOString().slice(0, 10));
    setAssignDialog({ employees: emps });
  };

  const submitAssign = async () => {
    if (!assignTpl) return toast.error('Select a template');
    const items = assignDialog.employees.map((e) => ({ employee_id: e.id, monthly_pay: Number(assignPay[e.id] || 0) }));
    if (items.some((it) => it.monthly_pay <= 0)) return toast.error('Enter Monthly Pay for every employee');
    setAssignSaving(true);
    try {
      if (items.length === 1) {
        await axios.post(`${API}/payslips/assignments`, { ...items[0], template_id: assignTpl, effective_from: assignDate }, { headers });
        toast.success('Template assigned');
      } else {
        const res = await axios.post(`${API}/payslips/assignments/bulk`, { template_id: assignTpl, effective_from: assignDate, items }, { headers });
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
    if (!window.confirm(`Confirm ALL draft payslips for ${genMonth}? Employees will see them from the 5th of the following month.`)) return;
    try {
      const res = await axios.post(`${API}/payslips/confirm-all`, { month: genMonth }, { headers });
      toast.success(`Confirmed ${res.data.confirmed} payslip(s)`);
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
                        <Button data-testid={`edit-template-${t.name}`} size="sm" variant="ghost" onClick={() => { setEditingTpl(t); setTplDialog(true); }}><Pencil className="w-4 h-4" /></Button>
                        <Button data-testid={`delete-template-${t.name}`} size="sm" variant="ghost" className="text-red-500" onClick={() => deleteTemplate(t)}><Trash2 className="w-4 h-4" /></Button>
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
                    <td className="px-4 py-3">{r.assignment?.effective_from || '—'}</td>
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
            {draftCount > 0 && (
              <Button data-testid="confirm-all-btn" variant="outline" className="text-emerald-700 border-emerald-300" onClick={confirmAll}>
                <CheckCircle2 className="w-4 h-4 mr-1" /> Confirm All ({draftCount})
              </Button>
            )}
            <div className="ml-auto flex gap-2">
              <Badge variant="outline" data-testid="draft-count-badge">Draft: {draftCount}</Badge>
              <Badge className="bg-emerald-100 text-emerald-700" data-testid="confirmed-count-badge">Confirmed: {confirmedCount}</Badge>
            </div>
          </div>
          <p className="text-xs text-slate-400">Confirmed payslips become visible to employees from the <b>5th of the following month</b>. Regenerating only updates drafts — confirmed payslips are never overwritten.</p>
          <div className="bg-white rounded-xl border overflow-x-auto">
            <table className="w-full text-sm min-w-[950px]">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
                <tr>
                  <th className="text-left px-4 py-3">Employee</th>
                  <th className="text-left px-4 py-3">Template</th>
                  <th className="text-right px-4 py-3">Payable Days</th>
                  <th className="text-right px-4 py-3">Gross</th>
                  <th className="text-right px-4 py-3">Deductions</th>
                  <th className="text-right px-4 py-3">Net Pay</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-right px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {slipsLoading ? (
                  <tr><td colSpan="8" className="px-4 py-8 text-center text-slate-400">Loading…</td></tr>
                ) : slips.length === 0 ? (
                  <tr><td colSpan="8" className="px-4 py-8 text-center text-slate-400" data-testid="no-slips-msg">No payslips generated for {genMonth} yet.</td></tr>
                ) : slips.map((s) => (
                  <tr key={s.id} className="border-t hover:bg-slate-50" data-testid={`slip-row-${s.employee_name}`}>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-800">{s.employee_name}</div>
                      <div className="text-xs text-slate-400">{s.employee?.custom_employee_id} · {s.employee?.employment_type || '—'}</div>
                    </td>
                    <td className="px-4 py-3">{s.template_name}</td>
                    <td className="px-4 py-3 text-right">{s.calc?.payable_days}</td>
                    <td className="px-4 py-3 text-right">{inr(s.calc?.gross_earnings)}</td>
                    <td className="px-4 py-3 text-right text-red-600">−{inr(s.calc?.total_deductions)}</td>
                    <td className="px-4 py-3 text-right font-semibold">{inr(s.calc?.net_pay)}</td>
                    <td className="px-4 py-3">
                      <Badge className={s.status === 'confirmed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'} data-testid={`slip-status-${s.employee_name}`}>
                        {s.status === 'confirmed' ? 'Confirmed' : 'Draft'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <Button data-testid={`view-slip-${s.employee_name}`} size="sm" variant="ghost" title="View breakdown" onClick={() => setViewSlip(s)}><Eye className="w-4 h-4" /></Button>
                      <Button data-testid={`pdf-slip-${s.employee_name}`} size="sm" variant="ghost" title="Download PDF" onClick={() => downloadPdf(s)}><Download className="w-4 h-4" /></Button>
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
                  <Input data-testid="assign-effective-date" type="date" value={assignDate} onChange={(e) => setAssignDate(e.target.value)} />
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
    </div>
  );
}
