import { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { MonthPicker } from '../ui/month-picker';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
export const monthLabel = (m) => (m ? `${MONTHS[Number(m.slice(5, 7)) - 1]} ${m.slice(0, 4)}` : 'Ongoing');
const inr = (n) => '₹' + Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// ---------- Template version selector + save mode ----------
export const VersionBar = ({ versions, selected, onSelect, mode, setMode, newFrom, setNewFrom }) => (
  <div className="border rounded-lg p-3 bg-blue-50/50 space-y-2" data-testid="template-version-bar">
    <div className="flex flex-wrap items-center gap-2">
      <label className="text-xs font-medium text-slate-500">Editing version</label>
      <Select value={String(selected)} onValueChange={(v) => onSelect(Number(v))}>
        <SelectTrigger className="h-8 w-64" data-testid="template-version-select"><SelectValue /></SelectTrigger>
        <SelectContent>
          {versions.map((v) => (
            <SelectItem key={v.version_no} value={String(v.version_no)}>
              Version {v.version_no} · {v.effective_from_month ? `from ${monthLabel(v.effective_from_month)}` : 'from the start'}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
    <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600">
      <label className="flex items-center gap-1.5 cursor-pointer">
        <input type="radio" data-testid="save-mode-update" checked={mode === 'update'} onChange={() => setMode('update')} />
        Update this version
      </label>
      <label className="flex items-center gap-1.5 cursor-pointer">
        <input type="radio" data-testid="save-mode-new" checked={mode === 'new'} onChange={() => setMode('new')} />
        Save as a new version effective from
      </label>
      {mode === 'new' && (
        <div data-testid="new-version-month"><MonthPicker value={newFrom} onChange={setNewFrom} className="h-8" /></div>
      )}
    </div>
    <p className="text-[11px] text-slate-500">
      Payslips use the version in force for their month. Confirmed payslips keep the settings they were generated with.
    </p>
  </div>
);

// ---------- Employer PF ----------
export const EmployerPfSection = ({ value, onChange, pfEligible, employeePf }) => {
  const set = (patch) => onChange({ enabled: false, percentage: '', max_amount: '', components: [], ...(value || {}), ...patch });
  const toggle = (n) => set({ components: (value?.components || []).includes(n)
    ? value.components.filter((x) => x !== n) : [...(value?.components || []), n] });
  const copyEmployee = () => set({ enabled: true, percentage: employeePf?.percentage ?? '', max_amount: employeePf?.max_amount ?? '',
    components: [...(employeePf?.components || [])] });
  return (
    <div className="border-t pt-3 space-y-2" data-testid="employer-pf-section">
      <div className="flex items-center justify-between gap-2">
        <h5 className="text-xs font-semibold text-slate-700">Employer PF Contribution <span className="font-normal text-slate-400">(employer cost — not deducted from Net Pay)</span></h5>
        <label className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer">
          <input data-testid="employer-pf-enabled-checkbox" type="checkbox" checked={!!value?.enabled}
            onChange={(e) => (e.target.checked && !value?.percentage ? copyEmployee() : set({ enabled: e.target.checked }))} />
          Enabled
        </label>
      </div>
      {value?.enabled && (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-slate-500">Employer PF % *</label>
              <Input data-testid="employer-pf-percentage-input" type="number" min="0" max="100" step="0.01" value={value.percentage}
                onChange={(e) => set({ percentage: e.target.value })} placeholder="e.g. 12" />
            </div>
            <div>
              <label className="text-xs text-slate-500">Maximum Employer PF ₹ *</label>
              <Input data-testid="employer-pf-max-input" type="number" min="0" step="0.01" value={value.max_amount}
                onChange={(e) => set({ max_amount: e.target.value })} placeholder="e.g. 1800" />
            </div>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1.5">
            {pfEligible.map((n) => (
              <label key={n} className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer">
                <input data-testid={`employer-pf-comp-${n}`} type="checkbox" checked={(value.components || []).includes(n)} onChange={() => toggle(n)} />
                {n}
              </label>
            ))}
          </div>
          <button type="button" className="text-[11px] underline text-slate-500" data-testid="employer-pf-copy-btn" onClick={copyEmployee}>
            Copy the employee PF settings
          </button>
        </>
      )}
    </div>
  );
};

// ---------- Gratuity provision ----------
export const GratuitySection = ({ value, onChange }) => {
  const set = (patch) => onChange({ enabled: false, amount: 793, prorate: true, ...(value || {}), ...patch });
  return (
    <div className="border-t pt-3 space-y-2" data-testid="gratuity-section">
      <div className="flex items-center justify-between gap-2">
        <h5 className="text-xs font-semibold text-slate-700">Gratuity Provision <span className="font-normal text-slate-400">(employer cost — not deducted from Net Pay)</span></h5>
        <label className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer">
          <input data-testid="gratuity-enabled-checkbox" type="checkbox" checked={!!value?.enabled} onChange={(e) => set({ enabled: e.target.checked })} />
          Enabled
        </label>
      </div>
      {value?.enabled && (
        <div className="flex flex-wrap items-end gap-4">
          <div className="w-44">
            <label className="text-xs text-slate-500">Full-month amount ₹ *</label>
            <Input data-testid="gratuity-amount-input" type="number" min="0" step="0.01" value={value.amount ?? ''} onChange={(e) => set({ amount: e.target.value })} />
          </div>
          <label className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer pb-2">
            <input data-testid="gratuity-prorate-checkbox" type="checkbox" checked={value.prorate !== false} onChange={(e) => set({ prorate: e.target.checked })} />
            Reduce by payable days
          </label>
        </div>
      )}
    </div>
  );
};

// ---------- Employer contributions + warnings in calculation breakdown ----------
export const EmployerContributions = ({ calc }) => {
  const rows = calc.employer_contributions || [];
  const warnings = calc.warnings || [];
  if (!rows.length && !warnings.length) return null;
  return (
    <div className="space-y-2" data-testid="employer-contributions">
      {rows.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-xs text-slate-500 uppercase border-b">
            <tr><th className="text-left py-2" colSpan="2">Employer Contributions <span className="normal-case font-normal text-slate-400">(not deducted from Net Pay)</span></th><th className="text-right py-2">This Month</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name} className="border-b border-slate-100" data-testid={`employer-row-${r.name}`}>
                <td className="py-2 pl-3 font-medium">{r.name}</td>
                <td className="py-2 text-xs text-slate-500">{r.auto_note}</td>
                <td className="py-2 text-right font-medium">{inr(r.amount)}</td>
              </tr>
            ))}
            <tr><td colSpan="2" className="py-2 text-right text-slate-500">Total Employer Cost</td><td className="py-2 text-right font-semibold" data-testid="employer-cost-total">{inr(calc.employer_cost_total)}</td></tr>
          </tbody>
        </table>
      )}
      {warnings.map((w) => (
        <div key={w} className="text-xs bg-amber-50 border border-amber-200 text-amber-800 rounded p-2" data-testid="calc-warning">{w}</div>
      ))}
    </div>
  );
};

// ---------- Assignment history (effective periods) ----------
const PeriodEditor = ({ row, headers, onSaved }) => {
  const [from, setFrom] = useState(row.from_month);
  const [until, setUntil] = useState(row.to_month || '');
  const [saving, setSaving] = useState(false);
  const save = async () => {
    if (until && until < from) return toast.error('Effective Until cannot be before Effective From');
    setSaving(true);
    try {
      await axios.put(`${API}/payslips/assignments/${row.id}/period`, { effective_from_month: from, effective_to_month: until || null }, { headers });
      toast.success('Effective period updated');
      onSaved();
    } catch (e) { toast.error(e.response?.data?.detail || 'Update failed'); } finally { setSaving(false); }
  };
  return (
    <div className="flex flex-wrap items-center gap-2 mt-2" data-testid={`period-editor-${row.id}`}>
      <MonthPicker value={from} onChange={setFrom} className="h-8" />
      <span className="text-xs text-slate-400">to</span>
      {until ? <MonthPicker value={until} onChange={setUntil} className="h-8" /> : <span className="text-xs text-slate-600">Ongoing</span>}
      <button type="button" className="text-[11px] underline text-slate-500" data-testid="period-toggle-until"
        onClick={() => setUntil(until ? '' : from)}>{until ? 'Make ongoing' : 'Set end month'}</button>
      <Button size="sm" onClick={save} disabled={saving} data-testid="period-save-btn">{saving ? 'Saving…' : 'Save'}</Button>
    </div>
  );
};

export const AssignmentHistoryDialog = ({ employee, headers, onClose, onChanged }) => {
  const [rows, setRows] = useState([]);
  const [editing, setEditing] = useState(null);
  const load = async () => {
    try {
      const res = await axios.get(`${API}/payslips/assignments/${employee.id}/history`, { headers });
      setRows(res.data.filter((r) => !r.superseded).sort((a, b) => (b.from_month || '').localeCompare(a.from_month || '')));
    } catch { toast.error('Failed to load assignment history'); }
  };
  useEffect(() => { load(); }, [employee.id]); // eslint-disable-line
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="assignment-history-dialog">
        <DialogHeader><DialogTitle>Template history — {employee.full_name}</DialogTitle></DialogHeader>
        {rows.length === 0 ? <div className="text-sm text-slate-400">No assignments yet.</div> : (
          <div className="space-y-2">
            {rows.map((r) => (
              <div key={r.id} className="border rounded-lg p-3" data-testid={`history-row-${r.id}`}>
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <Badge className="bg-blue-100 text-blue-700">{r.template_name}</Badge>
                  <span className="font-medium">{inr(r.monthly_pay)}</span>
                  <span className="text-slate-500">{monthLabel(r.from_month)} – {monthLabel(r.to_month)}</span>
                  {!r.to_month && <Badge variant="outline" className="text-emerald-700 border-emerald-200">Current</Badge>}
                  <button type="button" className="ml-auto text-xs underline text-slate-500" data-testid={`history-edit-${r.id}`}
                    onClick={() => setEditing(editing === r.id ? null : r.id)}>{editing === r.id ? 'Close' : 'Edit period'}</button>
                </div>
                {editing === r.id && <PeriodEditor row={r} headers={headers} onSaved={() => { setEditing(null); load(); onChanged(); }} />}
              </div>
            ))}
          </div>
        )}
        <p className="text-[11px] text-slate-500">To add an older template for past months, use Change → set Effective Until to the last month it applied.</p>
      </DialogContent>
    </Dialog>
  );
};
