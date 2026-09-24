import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Card, CardContent } from '../components/ui/card';
import { Checkbox } from '../components/ui/checkbox';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Cpu, MemoryStick, HardDrive, Plus, Search, Download, Upload, History, Eye, Wrench, ArrowRightLeft, Trash2, Undo2, CheckCircle2, Package } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CompStatusBadge = ({ status }) => {
  const map = {
    Installed: 'bg-blue-100 text-blue-700', Available: 'bg-emerald-100 text-emerald-700',
    Reserved: 'bg-slate-100 text-slate-700', 'Under Repair': 'bg-amber-100 text-amber-700',
    Damaged: 'bg-red-100 text-red-700', Lost: 'bg-red-100 text-red-700',
    Scrapped: 'bg-slate-200 text-slate-600', Disposed: 'bg-slate-200 text-slate-600',
  };
  return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[status] || 'bg-slate-100 text-slate-700'}`}>{status}</span>;
};

function useCompMeta(authHeaders) {
  const [meta, setMeta] = useState({ statuses: [], conditions: [], sources: [], removal_reasons: [], types: [] });
  useEffect(() => {
    axios.get(`${API}/it/components/meta`, { headers: authHeaders }).then(r => setMeta(r.data)).catch(() => {});
  }, [authHeaders]);
  return meta;
}

// Availability-driven selector: type-first, shows live counts + "No X available"
function AvailableComponentSelector({ authHeaders, meta, type, setType, exclude = [], value, onSelect }) {
  const [q, setQ] = useState('');
  const [data, setData] = useState({ counts: null, available_items: [], message: null });
  const load = useCallback(() => {
    if (!type) { setData({ counts: null, available_items: [], message: null }); return; }
    axios.get(`${API}/it/components/availability`, { headers: authHeaders, params: { type, search: q, exclude: exclude.join(',') } })
      .then(r => setData(r.data)).catch(() => {});
  }, [authHeaders, type, q, exclude]); // eslint-disable-line
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <div><Label>Component Type</Label>
          <Select value={type || ''} onValueChange={v => { onSelect(null); setType(v); }}>
            <SelectTrigger data-testid="avail-type-select"><SelectValue placeholder="Select type" /></SelectTrigger>
            <SelectContent>{meta.types.map(t => <SelectItem key={t.id} value={t.name}>{t.name}</SelectItem>)}</SelectContent>
          </Select></div>
        <div><Label>Search</Label><Input value={q} onChange={e => setQ(e.target.value)} placeholder="id, serial, brand…" disabled={!type} data-testid="avail-search" /></div>
      </div>
      {type && data.counts && (
        <div className="flex gap-2 text-xs" data-testid="avail-counts">
          <Badge variant="secondary">Total {data.counts.total}</Badge>
          <Badge className="bg-blue-100 text-blue-700">Used {data.counts.used}</Badge>
          <Badge className="bg-emerald-100 text-emerald-700">Available {data.counts.available}</Badge>
          {data.counts.under_repair > 0 && <Badge className="bg-amber-100 text-amber-700">Repair {data.counts.under_repair}</Badge>}
        </div>
      )}
      {type && (
        <div className="max-h-44 overflow-y-auto border rounded">
          {data.available_items.length === 0 && <div className="px-3 py-2 text-xs text-slate-400" data-testid="avail-none">{data.message || 'No components available.'}</div>}
          {data.available_items.map(c => (
            <button key={c.component_id} type="button" onClick={() => onSelect(c)}
              className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-50 ${value?.component_id === c.component_id ? 'bg-blue-50' : ''}`}
              data-testid={`avail-opt-${c.component_id}`}>
              {c.component_id} <span className="text-slate-400 text-xs">{[c.capacity, c.brand, c.model].filter(Boolean).join(' ')}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// Components picker used INSIDE the Create-Asset form. Manages a local selected list.
export function AssetCreateComponents({ authHeaders, selected, onChange }) {
  const meta = useCompMeta(authHeaders);
  const [type, setType] = useState('');
  const [pick, setPick] = useState(null);
  const [slot, setSlot] = useState('');
  const excludeIds = selected.map(s => s.component_id);

  const add = () => {
    if (!pick) { toast.error('Select an available component'); return; }
    onChange([...selected, { ...pick, slot }]);
    setPick(null); setSlot('');
  };
  const remove = (cid) => onChange(selected.filter(s => s.component_id !== cid));

  return (
    <div className="space-y-3" data-testid="asset-create-components">
      <AvailableComponentSelector authHeaders={authHeaders} meta={meta} type={type} setType={setType}
        exclude={excludeIds} value={pick} onSelect={setPick} />
      <div className="flex items-end gap-2">
        <div className="flex-1"><Label>Slot / Position (optional)</Label><Input value={slot} onChange={e => setSlot(e.target.value)} placeholder="e.g. DIMM 1" /></div>
        <Button type="button" onClick={add} disabled={!pick} data-testid="asset-create-comp-add"><Plus className="w-4 h-4 mr-1" />Add</Button>
      </div>
      {selected.length > 0 && (
        <div className="border rounded overflow-hidden">
          <Table><TableHeader><TableRow>
            <TableHead>Type</TableHead><TableHead>Component</TableHead><TableHead>Details</TableHead><TableHead>Slot</TableHead><TableHead></TableHead>
          </TableRow></TableHeader>
            <TableBody>
              {selected.map(c => (
                <TableRow key={c.component_id} data-testid={`asset-create-comp-row-${c.component_id}`}>
                  <TableCell>{c.type}</TableCell>
                  <TableCell className="font-medium">{c.component_id}</TableCell>
                  <TableCell className="text-sm">{[c.capacity, c.brand, c.model].filter(Boolean).join(' ') || '—'}</TableCell>
                  <TableCell className="text-sm text-slate-500">{c.slot || '—'}</TableCell>
                  <TableCell><Button type="button" size="icon" variant="ghost" onClick={() => remove(c.component_id)}><Trash2 className="w-4 h-4 text-red-500" /></Button></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

// ---------- Pickers ----------
function AssetPicker({ authHeaders, value, onSelect }) {
  const [q, setQ] = useState('');
  const [opts, setOpts] = useState([]);
  useEffect(() => {
    const t = setTimeout(() => {
      axios.get(`${API}/it/assets`, { headers: authHeaders, params: { search: q, page_size: 20 } })
        .then(r => setOpts(r.data.items || [])).catch(() => {});
    }, 300);
    return () => clearTimeout(t);
  }, [q]); // eslint-disable-line
  return (
    <div>
      <Input placeholder="Search parent asset (id, serial, brand)…" value={q} onChange={e => setQ(e.target.value)} data-testid="comp-asset-search" />
      <div className="max-h-40 overflow-y-auto mt-1 border rounded">
        {opts.map(a => (
          <button key={a.asset_id} type="button" onClick={() => onSelect(a)}
            className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-50 ${value?.asset_id === a.asset_id ? 'bg-blue-50' : ''}`}
            data-testid={`comp-asset-opt-${a.asset_id}`}>
            {a.asset_id} <span className="text-slate-400 text-xs">{a.category} · {a.assigned_to?.employee_name || 'Unassigned'}</span>
          </button>
        ))}
      </div>
      {value && <div className="text-xs text-emerald-700 mt-1">Selected: {value.asset_id}</div>}
    </div>
  );
}

function ComponentPicker({ authHeaders, value, onSelect, filterType }) {
  const [q, setQ] = useState('');
  const [opts, setOpts] = useState([]);
  useEffect(() => {
    const t = setTimeout(() => {
      axios.get(`${API}/it/components`, { headers: authHeaders, params: { search: q, installed: 'false', page_size: 25 } })
        .then(r => {
          let items = (r.data.items || []).filter(c => !['Disposed', 'Scrapped', 'Lost'].includes(c.status));
          if (filterType) items = items.filter(c => c.type === filterType);
          setOpts(items);
        }).catch(() => {});
    }, 300);
    return () => clearTimeout(t);
  }, [q, filterType]); // eslint-disable-line
  return (
    <div>
      <Input placeholder="Search available components…" value={q} onChange={e => setQ(e.target.value)} data-testid="comp-picker-search" />
      <div className="max-h-40 overflow-y-auto mt-1 border rounded">
        {opts.length === 0 && <div className="px-3 py-2 text-xs text-slate-400">No available components.</div>}
        {opts.map(c => (
          <button key={c.component_id} type="button" onClick={() => onSelect(c)}
            className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-50 ${value?.component_id === c.component_id ? 'bg-blue-50' : ''}`}
            data-testid={`comp-picker-opt-${c.component_id}`}>
            {c.component_id} <span className="text-slate-400 text-xs">{c.type} · {[c.capacity, c.brand, c.model].filter(Boolean).join(' ')}</span>
          </button>
        ))}
      </div>
      {value && <div className="text-xs text-emerald-700 mt-1">Selected: {value.component_id}</div>}
    </div>
  );
}

// ---------- Component form (create / edit) ----------
function ComponentForm({ authHeaders, meta, existing, onClose, onSaved }) {
  const init = existing || { type: '', status: 'Available', condition: '', source: '', location: '', trackable: true };
  const [f, setF] = useState({ component_id: '', name: '', brand: '', model: '', serial_number: '', part_number: '', capacity: '', remarks: '', ...init });
  const [purchase, setPurchase] = useState(existing?.purchase || { purchase_date: '', purchase_cost: '', vendor: '', invoice_number: '' });
  const [warranty, setWarranty] = useState(existing?.warranty || { warranty_start: '', warranty_end: '' });
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setF(p => ({ ...p, [k]: v }));

  const save = () => {
    if (!f.type) { toast.error('Component Type is required'); return; }
    setSaving(true);
    const body = { ...f, purchase, warranty };
    const req = existing
      ? axios.put(`${API}/it/components/${existing.component_id}`, body, { headers: authHeaders })
      : axios.post(`${API}/it/components`, body, { headers: authHeaders });
    req.then(() => { toast.success(existing ? 'Component updated' : 'Component created'); onSaved(); })
      .catch(e => toast.error(e.response?.data?.detail || 'Failed'))
      .finally(() => setSaving(false));
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="comp-form">
        <DialogHeader><DialogTitle>{existing ? `Edit ${existing.component_id}` : 'Add Component'}</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="text-xs font-semibold text-slate-500 uppercase">Basic Information</div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Component Type *</Label>
              <Select value={f.type} onValueChange={v => set('type', v)}>
                <SelectTrigger data-testid="comp-form-type"><SelectValue placeholder="Select type" /></SelectTrigger>
                <SelectContent>{meta.types.map(t => <SelectItem key={t.id} value={t.name}>{t.name}</SelectItem>)}</SelectContent>
              </Select></div>
            <div><Label>Status</Label>
              <Select value={f.status} onValueChange={v => set('status', v)} disabled={!!existing && !!existing.parent_asset_id}>
                <SelectTrigger data-testid="comp-form-status"><SelectValue /></SelectTrigger>
                <SelectContent>{meta.statuses.filter(s => s !== 'Installed').map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select></div>
            {!existing && <div><Label>Component ID (blank = auto)</Label><Input value={f.component_id} onChange={e => set('component_id', e.target.value)} placeholder="Auto-generated" data-testid="comp-form-id" /></div>}
            <div><Label>Component Name</Label><Input value={f.name || ''} onChange={e => set('name', e.target.value)} /></div>
            <div><Label>Brand</Label><Input value={f.brand || ''} onChange={e => set('brand', e.target.value)} /></div>
            <div><Label>Model</Label><Input value={f.model || ''} onChange={e => set('model', e.target.value)} /></div>
            <div><Label>Serial Number</Label><Input value={f.serial_number || ''} onChange={e => set('serial_number', e.target.value)} data-testid="comp-form-serial" /></div>
            <div><Label>Part Number</Label><Input value={f.part_number || ''} onChange={e => set('part_number', e.target.value)} /></div>
            <div><Label>Capacity / Spec</Label><Input value={f.capacity || ''} onChange={e => set('capacity', e.target.value)} placeholder="e.g. 16 GB, 1 TB, RTX 4060" data-testid="comp-form-capacity" /></div>
            <div><Label>Condition</Label>
              <Select value={f.condition || ''} onValueChange={v => set('condition', v)}>
                <SelectTrigger><SelectValue placeholder="—" /></SelectTrigger>
                <SelectContent>{meta.conditions.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>
            <div><Label>Asset Source</Label>
              <Select value={f.source || ''} onValueChange={v => set('source', v)}>
                <SelectTrigger><SelectValue placeholder="—" /></SelectTrigger>
                <SelectContent>{meta.sources.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>
            <div><Label>Location</Label><Input value={f.location || ''} onChange={e => set('location', e.target.value)} placeholder="e.g. IT Store" /></div>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="comp-trackable" checked={!!f.trackable} onCheckedChange={v => set('trackable', !!v)} data-testid="comp-form-trackable" />
            <Label htmlFor="comp-trackable" className="cursor-pointer">Trackable component (lifecycle managed)</Label>
          </div>

          <div className="text-xs font-semibold text-slate-500 uppercase">Purchase (optional — leave blank for legacy)</div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Purchase Date</Label><Input type="date" value={purchase.purchase_date || ''} onChange={e => setPurchase(p => ({ ...p, purchase_date: e.target.value }))} /></div>
            <div><Label>Purchase Cost</Label><Input value={purchase.purchase_cost || ''} onChange={e => setPurchase(p => ({ ...p, purchase_cost: e.target.value }))} /></div>
            <div><Label>Vendor</Label><Input value={purchase.vendor || ''} onChange={e => setPurchase(p => ({ ...p, vendor: e.target.value }))} /></div>
            <div><Label>Invoice Number</Label><Input value={purchase.invoice_number || ''} onChange={e => setPurchase(p => ({ ...p, invoice_number: e.target.value }))} /></div>
          </div>
          <div className="text-xs font-semibold text-slate-500 uppercase">Warranty (optional)</div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Warranty Start</Label><Input type="date" value={warranty.warranty_start || ''} onChange={e => setWarranty(p => ({ ...p, warranty_start: e.target.value }))} /></div>
            <div><Label>Warranty End</Label><Input type="date" value={warranty.warranty_end || ''} onChange={e => setWarranty(p => ({ ...p, warranty_end: e.target.value }))} /></div>
          </div>
          <div><Label>Remarks</Label><Textarea value={f.remarks || ''} onChange={e => set('remarks', e.target.value)} /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={saving} data-testid="comp-form-save">{saving ? 'Saving…' : 'Save Component'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------- Component action dialog ----------
function ComponentActionDialog({ authHeaders, meta, action, onClose, onDone }) {
  const { type, component, presetAsset } = action;
  const [asset, setAsset] = useState(presetAsset || null);
  const [newComp, setNewComp] = useState(null);
  const [form, setForm] = useState({ slot: '', reason: 'Upgrade', new_status: 'Available', condition: '', destination: '', remarks: '', issue: '', action: '', vendor: '', cost: '', status: 'Open', method: '', approved_by: '' });
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const submit = () => {
    setBusy(true);
    let url, body;
    if (type === 'install') {
      if (!asset) { toast.error('Select a parent asset'); setBusy(false); return; }
      url = `${API}/it/components/${component.component_id}/install`;
      body = { parent_asset_id: asset.asset_id, slot: form.slot, condition: form.condition, remarks: form.remarks };
    } else if (type === 'remove') {
      url = `${API}/it/components/${component.component_id}/remove`;
      body = { reason: form.reason, new_status: form.new_status, condition: form.condition, destination: form.destination, remarks: form.remarks };
    } else if (type === 'replace') {
      if (!newComp) { toast.error('Select a replacement component'); setBusy(false); return; }
      url = `${API}/it/components/replace`;
      body = { parent_asset_id: component.parent_asset_id, old_component_id: component.component_id, new_component_id: newComp.component_id, reason: form.reason, old_new_status: form.new_status, slot: form.slot };
    } else if (type === 'maintenance') {
      url = `${API}/it/components/${component.component_id}/maintenance`;
      body = { issue: form.issue, action: form.action, vendor: form.vendor, cost: form.cost, status: form.status, remarks: form.remarks };
    } else if (type === 'dispose') {
      url = `${API}/it/components/${component.component_id}/dispose`;
      body = { reason: form.reason, method: form.method, approved_by: form.approved_by, remarks: form.remarks };
    }
    axios.post(url, body, { headers: authHeaders })
      .then(() => { toast.success('Done'); onDone(); })
      .catch(e => toast.error(e.response?.data?.detail || 'Failed'))
      .finally(() => setBusy(false));
  };

  const titles = { install: 'Install Component', remove: 'Remove Component', replace: 'Replace Component', maintenance: 'Log Maintenance', dispose: 'Dispose Component' };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-lg" data-testid="comp-action-dialog">
        <DialogHeader><DialogTitle>{titles[type]} — {component.component_id}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          {type === 'install' && <>
            {!presetAsset && <div><Label>Parent Asset *</Label><AssetPicker authHeaders={authHeaders} value={asset} onSelect={setAsset} /></div>}
            {presetAsset && <div className="text-sm text-slate-600">Installing into <b>{presetAsset.asset_id}</b></div>}
            <div><Label>Slot / Position</Label><Input value={form.slot} onChange={e => set('slot', e.target.value)} placeholder="e.g. DIMM 1, PCIe Slot 1" data-testid="comp-install-slot" /></div>
            <div><Label>Condition</Label>
              <Select value={form.condition} onValueChange={v => set('condition', v)}><SelectTrigger><SelectValue placeholder="—" /></SelectTrigger>
                <SelectContent>{meta.conditions.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>
          </>}
          {type === 'remove' && <>
            <div><Label>Removal Reason</Label>
              <Select value={form.reason} onValueChange={v => set('reason', v)}><SelectTrigger data-testid="comp-remove-reason"><SelectValue /></SelectTrigger>
                <SelectContent>{meta.removal_reasons.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>
            <div><Label>New Status</Label>
              <Select value={form.new_status} onValueChange={v => set('new_status', v)}><SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{meta.statuses.filter(s => s !== 'Installed').map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>
            <div><Label>Destination / Location</Label><Input value={form.destination} onChange={e => set('destination', e.target.value)} placeholder="e.g. IT Store" /></div>
            <div><Label>Remarks</Label><Textarea value={form.remarks} onChange={e => set('remarks', e.target.value)} /></div>
          </>}
          {type === 'replace' && <>
            <div className="text-sm text-slate-600">Replacing <b>{component.component_id}</b> in <b>{component.parent_asset_id}</b></div>
            <div><Label>Replacement Component *</Label><ComponentPicker authHeaders={authHeaders} value={newComp} onSelect={setNewComp} filterType={component.type} /></div>
            <div><Label>Reason</Label>
              <Select value={form.reason} onValueChange={v => set('reason', v)}><SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{meta.removal_reasons.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>
            <div><Label>Old Component New Status</Label>
              <Select value={form.new_status} onValueChange={v => set('new_status', v)}><SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{['Damaged', 'Available', 'Under Repair', 'Scrapped'].map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>
          </>}
          {type === 'maintenance' && <>
            <div><Label>Issue</Label><Input value={form.issue} onChange={e => set('issue', e.target.value)} data-testid="comp-maint-issue" /></div>
            <div><Label>Action Taken</Label><Input value={form.action} onChange={e => set('action', e.target.value)} /></div>
            <div className="grid grid-cols-2 gap-2">
              <div><Label>Vendor</Label><Input value={form.vendor} onChange={e => set('vendor', e.target.value)} /></div>
              <div><Label>Cost</Label><Input value={form.cost} onChange={e => set('cost', e.target.value)} /></div>
            </div>
            <div><Label>Status</Label>
              <Select value={form.status} onValueChange={v => set('status', v)}><SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{['Open', 'In Progress', 'Repaired', 'Closed'].map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>
            <div><Label>Remarks</Label><Textarea value={form.remarks} onChange={e => set('remarks', e.target.value)} /></div>
          </>}
          {type === 'dispose' && <>
            <div><Label>Disposal Reason</Label><Input value={form.reason} onChange={e => set('reason', e.target.value)} data-testid="comp-dispose-reason" /></div>
            <div><Label>Disposal Method</Label><Input value={form.method} onChange={e => set('method', e.target.value)} placeholder="e.g. E-waste vendor, Scrap" /></div>
            <div><Label>Approved By</Label><Input value={form.approved_by} onChange={e => set('approved_by', e.target.value)} /></div>
            <div><Label>Remarks</Label><Textarea value={form.remarks} onChange={e => set('remarks', e.target.value)} /></div>
          </>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} disabled={busy} data-testid="comp-action-confirm">{busy ? '…' : 'Confirm'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------- Component detail drawer ----------
function ComponentDetail({ authHeaders, componentId, onClose }) {
  const [d, setD] = useState(null);
  useEffect(() => { axios.get(`${API}/it/components/${componentId}`, { headers: authHeaders }).then(r => setD(r.data)).catch(() => {}); }, [componentId]); // eslint-disable-line
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="comp-detail">
        <DialogHeader><DialogTitle>{componentId}</DialogTitle></DialogHeader>
        {!d ? <div className="text-slate-400">Loading…</div> : <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2 text-sm">
            {[['Type', d.component.type], ['Status', d.component.status], ['Brand', d.component.brand], ['Model', d.component.model],
              ['Serial', d.component.serial_number], ['Part No', d.component.part_number], ['Capacity', d.component.capacity],
              ['Condition', d.component.condition], ['Location', d.component.location], ['Current Parent', d.component.parent_asset_id],
              ['Slot', d.component.slot], ['Current Holder', d.current_holder?.employee_name]].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-slate-100 py-1"><span className="text-slate-500">{k}</span><span className="font-medium">{v || '—'}</span></div>
            ))}
          </div>
          {d.maintenance.length > 0 && <div>
            <div className="text-xs font-semibold text-slate-500 uppercase mb-1">Maintenance</div>
            <div className="space-y-1 text-sm">{d.maintenance.map(m => (
              <div key={m.id} className="border-b border-slate-100 py-1"><span className="font-medium">{m.issue || '—'}</span> <span className="text-slate-500 text-xs">· {m.status} · {m.reported_date} · {m.vendor || ''}</span></div>
            ))}</div>
          </div>}
          {d.assignments && d.assignments.length > 0 && <div>
            <div className="text-xs font-semibold text-slate-500 uppercase mb-1">Employee Assignment History</div>
            <div className="border rounded overflow-hidden" data-testid="comp-assignment-history">
              <Table><TableHeader><TableRow><TableHead>Employee</TableHead><TableHead>Asset</TableHead><TableHead>From</TableHead><TableHead>To</TableHead><TableHead>Reason</TableHead></TableRow></TableHeader>
                <TableBody>{d.assignments.map(a => (
                  <TableRow key={a.id}>
                    <TableCell className="text-sm font-medium">{a.employee_name || '—'}</TableCell>
                    <TableCell className="text-sm">{a.asset_id || '—'}</TableCell>
                    <TableCell className="text-xs text-slate-500">{a.from ? new Date(a.from).toLocaleDateString() : '—'}</TableCell>
                    <TableCell className="text-xs text-slate-500">{a.to ? new Date(a.to).toLocaleDateString() : <Badge className="bg-emerald-100 text-emerald-700">Present</Badge>}</TableCell>
                    <TableCell className="text-xs">{a.reason || '—'}</TableCell>
                  </TableRow>
                ))}</TableBody></Table>
            </div>
          </div>}
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase mb-2 flex items-center gap-1"><History className="w-3.5 h-3.5" />Component Timeline</div>
            <div className="space-y-2" data-testid="comp-history">
              {d.history.map(h => (
                <div key={h.id} className="flex gap-3 text-sm">
                  <div className="w-2 h-2 rounded-full bg-blue-400 mt-1.5" />
                  <div><div className="font-medium">{h.action}{h.parent_asset_id ? ` · ${h.parent_asset_id}` : ''}</div><div className="text-slate-500 text-xs">{h.note}</div><div className="text-slate-400 text-xs">{h.by_name} · {new Date(h.at).toLocaleString()}</div></div>
                </div>
              ))}
            </div>
          </div>
        </div>}
      </DialogContent>
    </Dialog>
  );
}

// ---------- Component import dialog (components + bulk assembly) ----------
function ComponentImportDialog({ authHeaders, onClose, onDone }) {
  const [mode, setMode] = useState('components'); // components | assembly
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);

  const template = () => {
    if (mode !== 'components') return;
    axios.get(`${API}/it/components/import/template`, { headers: authHeaders, responseType: 'blob' }).then(r => {
      const url = URL.createObjectURL(r.data); const a = document.createElement('a'); a.href = url; a.download = 'it_component_import_template.csv'; a.click(); URL.revokeObjectURL(url);
    });
  };
  const upload = (e) => {
    const file = e.target.files?.[0]; if (!file) return;
    const fd = new FormData(); fd.append('file', file); setBusy(true); setPreview(null);
    const ep = mode === 'components' ? 'import/preview' : 'assembly/preview';
    axios.post(`${API}/it/components/${ep}`, fd, { headers: { ...authHeaders } })
      .then(r => setPreview(r.data)).catch(er => toast.error(er.response?.data?.detail || 'Parse failed')).finally(() => setBusy(false));
  };
  const confirm = () => {
    setBusy(true);
    const ep = mode === 'components' ? 'import/confirm' : 'assembly/confirm';
    axios.post(`${API}/it/components/${ep}`, { rows: preview.rows }, { headers: authHeaders })
      .then(r => { toast.success(mode === 'components' ? `Imported ${r.data.created}, skipped ${r.data.skipped}` : `Installed ${r.data.installed}, skipped ${r.data.skipped}`); onDone(); })
      .catch(e => toast.error(e.response?.data?.detail || 'Failed')).finally(() => setBusy(false));
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="comp-import-dialog">
        <DialogHeader><DialogTitle>Import Components</DialogTitle></DialogHeader>
        <div className="flex gap-2 mb-2">
          <Button size="sm" variant={mode === 'components' ? 'default' : 'outline'} onClick={() => { setMode('components'); setPreview(null); }} data-testid="comp-import-mode-components">Component Master</Button>
          <Button size="sm" variant={mode === 'assembly' ? 'default' : 'outline'} onClick={() => { setMode('assembly'); setPreview(null); }} data-testid="comp-import-mode-assembly">Bulk Assembly (install)</Button>
        </div>
        <p className="text-xs text-slate-500 mb-2">{mode === 'components' ? 'Columns: component_id, type, brand, model, serial_number, capacity, status, …' : 'Columns: parent_asset_id, component_id, slot'}</p>
        <div className="flex gap-2">
          {mode === 'components' && <Button variant="outline" onClick={template} data-testid="comp-import-template"><Download className="w-4 h-4 mr-1" />Template</Button>}
          <label className="inline-flex">
            <input type="file" accept=".csv,.xlsx" className="hidden" onChange={upload} data-testid="comp-import-file" />
            <span className="inline-flex items-center px-4 py-2 rounded-md bg-slate-900 text-white text-sm cursor-pointer hover:bg-slate-800"><Upload className="w-4 h-4 mr-1" />Upload CSV / Excel</span>
          </label>
        </div>
        {busy && <div className="text-sm text-slate-400 mt-3">Processing…</div>}
        {preview && <div className="space-y-3 mt-3">
          <div className="flex gap-3 text-sm" data-testid="comp-import-summary">
            <Badge variant="secondary">Total {preview.total}</Badge>
            <Badge className="bg-emerald-100 text-emerald-700">Valid {preview.valid}</Badge>
            <Badge variant="destructive">Errors {preview.errors}</Badge>
          </div>
          <div className="border rounded max-h-80 overflow-auto">
            <Table><TableHeader><TableRow><TableHead>Row</TableHead><TableHead>{mode === 'components' ? 'Component' : 'Parent → Component'}</TableHead><TableHead>Issues</TableHead></TableRow></TableHeader>
              <TableBody>{preview.rows.map(r => (
                <TableRow key={r.row} className={r.errors.length ? 'bg-red-50' : ''}>
                  <TableCell>{r.row}</TableCell>
                  <TableCell className="text-sm">{mode === 'components' ? `${r.data.component_id || '(auto)'} · ${r.data.type}` : `${r.data.parent_asset_id} → ${r.data.component_id}`}</TableCell>
                  <TableCell className="text-xs">{r.errors.map((e, i) => <div key={i} className="text-red-600">{e}</div>)}{(r.warnings || []).map((w, i) => <div key={i} className="text-amber-600">{w}</div>)}</TableCell>
                </TableRow>
              ))}</TableBody></Table>
          </div>
          <Button onClick={confirm} disabled={busy || preview.valid === 0} data-testid="comp-import-confirm">Commit {preview.valid} valid rows</Button>
        </div>}
      </DialogContent>
    </Dialog>
  );
}

// ---------- Top-level Components tab ----------
export function ComponentsTab({ authHeaders, onChange }) {
  const meta = useCompMeta(authHeaders);
  const [data, setData] = useState({ items: [], total: 0 });
  const [filters, setFilters] = useState({ search: '', type: 'All', status: 'All', installed: 'All' });
  const [page, setPage] = useState(1);
  const [form, setForm] = useState(null); // {} for new, {existing} for edit
  const [detail, setDetail] = useState(null);
  const [action, setAction] = useState(null);
  const [showImport, setShowImport] = useState(false);
  const [report, setReport] = useState('inventory');

  const load = useCallback(() => {
    const params = { page, page_size: 25 };
    if (filters.search) params.search = filters.search;
    if (filters.type !== 'All') params.type = filters.type;
    if (filters.status !== 'All') params.status = filters.status;
    if (filters.installed !== 'All') params.installed = filters.installed;
    axios.get(`${API}/it/components`, { headers: authHeaders, params }).then(r => setData(r.data)).catch(() => toast.error('Failed to load components'));
  }, [authHeaders, page, filters]);
  useEffect(() => { load(); }, [load]);

  const exportCsv = () => {
    const params = new URLSearchParams({ report });
    if (filters.type !== 'All') params.set('type', filters.type);
    if (filters.status !== 'All') params.set('status', filters.status);
    if (filters.search) params.set('search', filters.search);
    axios.get(`${API}/it/components/export?${params}`, { headers: authHeaders, responseType: 'blob' }).then(r => {
      const url = URL.createObjectURL(r.data); const a = document.createElement('a'); a.href = url; a.download = `it_components_${report}.csv`; a.click(); URL.revokeObjectURL(url);
    });
  };

  const refresh = () => { load(); onChange && onChange(); };
  const totalPages = Math.max(1, Math.ceil(data.total / 25));

  return (
    <div className="space-y-4" data-testid="it-components-tab">
      <div className="flex flex-wrap gap-2 items-center">
        <div className="relative">
          <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-slate-400" />
          <Input data-testid="comp-search" className="pl-8 w-64" placeholder="Search component id, serial, capacity…" value={filters.search}
            onChange={e => { setPage(1); setFilters(f => ({ ...f, search: e.target.value })); }} />
        </div>
        <Select value={filters.type} onValueChange={v => { setPage(1); setFilters(f => ({ ...f, type: v })); }}>
          <SelectTrigger className="w-40" data-testid="comp-filter-type"><SelectValue placeholder="Type" /></SelectTrigger>
          <SelectContent><SelectItem value="All">All Types</SelectItem>{meta.types.map(t => <SelectItem key={t.id} value={t.name}>{t.name}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={filters.status} onValueChange={v => { setPage(1); setFilters(f => ({ ...f, status: v })); }}>
          <SelectTrigger className="w-36" data-testid="comp-filter-status"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent><SelectItem value="All">All Statuses</SelectItem>{meta.statuses.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={filters.installed} onValueChange={v => { setPage(1); setFilters(f => ({ ...f, installed: v })); }}>
          <SelectTrigger className="w-36"><SelectValue placeholder="Installed?" /></SelectTrigger>
          <SelectContent><SelectItem value="All">All</SelectItem><SelectItem value="true">Installed</SelectItem><SelectItem value="false">In Inventory</SelectItem></SelectContent>
        </Select>
        <div className="flex-1" />
        <Select value={report} onValueChange={setReport}>
          <SelectTrigger className="w-44" data-testid="comp-report-select"><SelectValue /></SelectTrigger>
          <SelectContent>
            {[['inventory', 'Inventory'], ['installed', 'Installed'], ['available', 'Available'], ['removed', 'Removed'], ['replacement', 'Replacement History'], ['movement', 'Movement History'], ['maintenance', 'Maintenance']].map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button variant="outline" onClick={exportCsv} data-testid="comp-export-btn"><Download className="w-4 h-4 mr-1" />Export</Button>
        <Button variant="outline" onClick={() => setShowImport(true)} data-testid="comp-import-btn"><Upload className="w-4 h-4 mr-1" />Import</Button>
        <Button onClick={() => setForm({})} data-testid="comp-add-btn"><Plus className="w-4 h-4 mr-1" />Add Component</Button>
      </div>

      <div className="border rounded-lg overflow-hidden">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Component ID</TableHead><TableHead>Type</TableHead><TableHead>Details</TableHead>
            <TableHead>Serial</TableHead><TableHead>Status</TableHead><TableHead>Parent Asset</TableHead><TableHead className="text-right">Actions</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {data.items.length === 0 && <TableRow><TableCell colSpan={7} className="text-center text-slate-400 py-8">No components found.</TableCell></TableRow>}
            {data.items.map(c => (
              <TableRow key={c.component_id} data-testid={`comp-row-${c.component_id}`}>
                <TableCell className="font-medium">{c.component_id}</TableCell>
                <TableCell>{c.type}</TableCell>
                <TableCell className="text-sm">{[c.capacity, c.brand, c.model].filter(Boolean).join(' ') || '—'}</TableCell>
                <TableCell className="text-sm text-slate-500">{c.serial_number || '—'}</TableCell>
                <TableCell><CompStatusBadge status={c.status} /></TableCell>
                <TableCell className="text-sm">{c.parent_asset_id || '—'}</TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  <Button size="icon" variant="ghost" title="View" onClick={() => setDetail(c.component_id)} data-testid={`comp-view-${c.component_id}`}><Eye className="w-4 h-4" /></Button>
                  {!c.parent_asset_id && !['Disposed', 'Scrapped', 'Lost'].includes(c.status) &&
                    <Button size="icon" variant="ghost" title="Install" onClick={() => setAction({ type: 'install', component: c })} data-testid={`comp-install-${c.component_id}`}><CheckCircle2 className="w-4 h-4 text-blue-600" /></Button>}
                  {c.parent_asset_id && <Button size="icon" variant="ghost" title="Remove" onClick={() => setAction({ type: 'remove', component: c })} data-testid={`comp-remove-${c.component_id}`}><Undo2 className="w-4 h-4" /></Button>}
                  {c.parent_asset_id && <Button size="icon" variant="ghost" title="Replace" onClick={() => setAction({ type: 'replace', component: c })}><ArrowRightLeft className="w-4 h-4" /></Button>}
                  <Button size="icon" variant="ghost" title="Maintenance" onClick={() => setAction({ type: 'maintenance', component: c })}><Wrench className="w-4 h-4 text-amber-600" /></Button>
                  {!c.parent_asset_id && <Button size="icon" variant="ghost" title="Dispose" onClick={() => setAction({ type: 'dispose', component: c })}><Trash2 className="w-4 h-4 text-red-500" /></Button>}
                  {!c.parent_asset_id && <Button size="icon" variant="ghost" title="Edit" onClick={() => setForm(c)}>✎</Button>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between text-sm text-slate-500">
        <span>{data.total} components</span>
        <div className="flex gap-2 items-center">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
          <span>Page {page} / {totalPages}</span>
          <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next</Button>
        </div>
      </div>

      {form && <ComponentForm authHeaders={authHeaders} meta={meta} existing={form.component_id ? form : null} onClose={() => setForm(null)} onSaved={() => { setForm(null); refresh(); }} />}
      {detail && <ComponentDetail authHeaders={authHeaders} componentId={detail} onClose={() => setDetail(null)} />}
      {action && <ComponentActionDialog authHeaders={authHeaders} meta={meta} action={action} onClose={() => setAction(null)} onDone={() => { setAction(null); refresh(); }} />}
      {showImport && <ComponentImportDialog authHeaders={authHeaders} onClose={() => setShowImport(false)} onDone={() => { setShowImport(false); refresh(); }} />}
    </div>
  );
}

// ---------- Section embedded in Asset Detail ----------
export function AssetComponentsSection({ authHeaders, assetId }) {
  const meta = useCompMeta(authHeaders);
  const [d, setD] = useState(null);
  const [action, setAction] = useState(null);
  const [detail, setDetail] = useState(null);
  const [addOpen, setAddOpen] = useState(false);

  const load = useCallback(() => {
    axios.get(`${API}/it/assets/${assetId}/components`, { headers: authHeaders }).then(r => setD(r.data)).catch(() => {});
  }, [authHeaders, assetId]);
  useEffect(() => { load(); }, [load]);

  if (!d) return <div className="text-slate-400 text-sm">Loading components…</div>;
  const cfg = d.current_configuration?.by_type || {};

  return (
    <div className="space-y-4" data-testid="asset-components-section">
      {Object.keys(cfg).length > 0 && <div>
        <div className="text-xs font-semibold text-slate-500 uppercase mb-1">Current Configuration</div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          {Object.entries(cfg).map(([type, list]) => (
            <div key={type} className="flex justify-between border-b border-slate-100 py-1">
              <span className="text-slate-500">{type}{list.length > 1 ? ` (${list.length})` : ''}</span>
              <span className="font-medium text-right">{list.map(i => i.display).join(', ')}</span>
            </div>
          ))}
        </div>
      </div>}

      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold text-slate-500 uppercase">Installed Components</div>
        <Button size="sm" onClick={() => setAddOpen(true)} data-testid="asset-add-component-btn"><Plus className="w-3.5 h-3.5 mr-1" />Add Component</Button>
      </div>
      <div className="border rounded overflow-hidden">
        <Table><TableHeader><TableRow>
          <TableHead>Component</TableHead><TableHead>ID</TableHead><TableHead>Details</TableHead><TableHead>Slot</TableHead><TableHead className="text-right">Actions</TableHead>
        </TableRow></TableHeader>
          <TableBody>
            {d.components.length === 0 && <TableRow><TableCell colSpan={5} className="text-center text-slate-400 py-6">No components installed. Use “Add Component”.</TableCell></TableRow>}
            {d.components.map(c => (
              <TableRow key={c.component_id} data-testid={`asset-comp-${c.component_id}`}>
                <TableCell>{c.type}</TableCell>
                <TableCell className="font-medium">{c.component_id}</TableCell>
                <TableCell className="text-sm">{[c.capacity, c.brand, c.model].filter(Boolean).join(' ') || '—'}</TableCell>
                <TableCell className="text-sm text-slate-500">{c.slot || '—'}</TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  <Button size="icon" variant="ghost" title="History" onClick={() => setDetail(c.component_id)}><History className="w-4 h-4" /></Button>
                  <Button size="icon" variant="ghost" title="Replace" onClick={() => setAction({ type: 'replace', component: { ...c, parent_asset_id: assetId } })}><ArrowRightLeft className="w-4 h-4" /></Button>
                  <Button size="icon" variant="ghost" title="Remove" onClick={() => setAction({ type: 'remove', component: { ...c, parent_asset_id: assetId } })}><Undo2 className="w-4 h-4 text-red-500" /></Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {d.config_history.length > 0 && <div>
        <div className="text-xs font-semibold text-slate-500 uppercase mb-2">Component Change History</div>
        <div className="space-y-1.5">
          {d.config_history.map(h => (
            <div key={h.id} className="flex gap-3 text-sm"><div className="w-2 h-2 rounded-full bg-slate-400 mt-1.5" />
              <div><span className="font-medium">{h.component_id}</span> <span className="text-slate-600">{h.action}</span><div className="text-slate-400 text-xs">{h.note} · {new Date(h.at).toLocaleString()}</div></div>
            </div>
          ))}
        </div>
      </div>}

      {d.assignment_history && d.assignment_history.length > 0 && <div>
        <div className="text-xs font-semibold text-slate-500 uppercase mb-1">Asset Assignment History</div>
        <div className="border rounded overflow-hidden" data-testid="asset-assignment-history">
          <Table><TableHeader><TableRow><TableHead>Employee</TableHead><TableHead>From</TableHead><TableHead>To</TableHead><TableHead>Reason</TableHead></TableRow></TableHeader>
            <TableBody>{d.assignment_history.map(a => (
              <TableRow key={a.id}>
                <TableCell className="text-sm font-medium">{a.employee_name || '—'}</TableCell>
                <TableCell className="text-xs text-slate-500">{a.from ? new Date(a.from).toLocaleDateString() : '—'}</TableCell>
                <TableCell className="text-xs text-slate-500">{a.to ? new Date(a.to).toLocaleDateString() : <Badge className="bg-emerald-100 text-emerald-700">Present</Badge>}</TableCell>
                <TableCell className="text-xs">{a.reason || '—'}</TableCell>
              </TableRow>
            ))}</TableBody></Table>
        </div>
      </div>}

      {action && <ComponentActionDialog authHeaders={authHeaders} meta={meta} action={action}
        onClose={() => setAction(null)} onDone={() => { setAction(null); load(); }} />}
      {addOpen && <AssetAddComponentDialog authHeaders={authHeaders} assetId={assetId}
        onClose={() => setAddOpen(false)} onDone={() => { setAddOpen(false); load(); }} />}
      {detail && <ComponentDetail authHeaders={authHeaders} componentId={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}

// Add-to-asset flow needs component selection: wrap install with a component picker when adding from asset
export function AssetAddComponentDialog({ authHeaders, assetId, onClose, onDone }) {
  const meta = useCompMeta(authHeaders);
  const [type, setType] = useState('');
  const [comp, setComp] = useState(null);
  const [slot, setSlot] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = () => {
    if (!comp) { toast.error('Select a component'); return; }
    setBusy(true);
    axios.post(`${API}/it/components/${comp.component_id}/install`, { parent_asset_id: assetId, slot }, { headers: authHeaders })
      .then(() => { toast.success('Component installed'); onDone(); })
      .catch(e => toast.error(e.response?.data?.detail || 'Failed')).finally(() => setBusy(false));
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent data-testid="asset-add-comp-dialog">
        <DialogHeader><DialogTitle>Add Component to {assetId}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <AvailableComponentSelector authHeaders={authHeaders} meta={meta} type={type} setType={setType} value={comp} onSelect={setComp} />
          <div><Label>Slot / Position</Label><Input value={slot} onChange={e => setSlot(e.target.value)} placeholder="e.g. DIMM 1" data-testid="asset-add-slot" /></div>
          <p className="text-xs text-slate-500">Select a type first — only components not installed elsewhere appear. The component inherits this asset's employee assignment.</p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} disabled={busy || !comp} data-testid="asset-add-comp-confirm">{busy ? '…' : 'Install'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------- Dashboard cards ----------
export function ComponentDashboardCards({ authHeaders }) {
  const [dash, setDash] = useState(null);
  useEffect(() => { axios.get(`${API}/it/components/dashboard`, { headers: authHeaders }).then(r => setDash(r.data)).catch(() => {}); }, [authHeaders]);
  if (!dash) return null;
  const cards = [
    { label: 'Total Components', value: dash.total, icon: Cpu, color: 'text-slate-700' },
    { label: 'Installed', value: dash.installed, icon: MemoryStick, color: 'text-blue-600' },
    { label: 'Available', value: dash.summary.Available, icon: Package, color: 'text-emerald-600' },
    { label: 'Under Repair', value: dash.summary['Under Repair'], icon: Wrench, color: 'text-amber-600' },
    { label: 'Damaged', value: dash.summary.Damaged, icon: HardDrive, color: 'text-red-600' },
    { label: 'Replaced', value: dash.summary.Replaced, icon: ArrowRightLeft, color: 'text-slate-600' },
  ];
  return (
    <div data-testid="it-component-dashboard-cards">
      <div className="text-sm font-semibold text-slate-700 mb-2">Components</div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {cards.map(c => (
          <Card key={c.label}><CardContent className="p-4">
            <div className="flex items-center justify-between"><c.icon className={`w-5 h-5 ${c.color}`} /></div>
            <div className="mt-2 text-2xl font-bold text-slate-900">{c.value ?? 0}</div>
            <div className="text-xs text-slate-500">{c.label}</div>
          </CardContent></Card>
        ))}
      </div>
    </div>
  );
}
