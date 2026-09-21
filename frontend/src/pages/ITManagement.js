import { useState, useEffect, useMemo, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Laptop, Package, CheckCircle2, Wrench, AlertTriangle, Search, Plus, Upload, Download, History, ArrowRightLeft, UserPlus, Undo2, Archive, Eye } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const StatusBadge = ({ status }) => {
  const map = {
    'Assigned': 'bg-blue-100 text-blue-700', 'Available': 'bg-emerald-100 text-emerald-700',
    'In Stock': 'bg-slate-100 text-slate-700', 'Under Repair': 'bg-amber-100 text-amber-700',
    'Under Maintenance': 'bg-amber-100 text-amber-700', 'Damaged': 'bg-red-100 text-red-700',
    'Lost': 'bg-red-100 text-red-700', 'Retired': 'bg-slate-200 text-slate-600',
    'Disposed': 'bg-slate-200 text-slate-600',
  };
  return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[status] || 'bg-slate-100 text-slate-700'}`}>{status}</span>;
};

export default function ITManagement() {
  const { token } = useAuth();
  const authHeaders = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);
  const [meta, setMeta] = useState({ statuses: [], conditions: [], sources: [], categories: [], import_columns: [] });
  const [dash, setDash] = useState(null);

  useEffect(() => {
    axios.get(`${API}/it/meta`, { headers: authHeaders }).then(r => setMeta(r.data)).catch(() => toast.error('Failed to load IT metadata'));
    loadDash();
  }, []); // eslint-disable-line

  const loadDash = useCallback(() => {
    axios.get(`${API}/it/dashboard`, { headers: authHeaders }).then(r => setDash(r.data)).catch(() => {});
  }, [authHeaders]);

  return (
    <div className="space-y-6" data-testid="it-management-page">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">IT Asset & Infrastructure Management</h1>
        <p className="text-sm text-slate-500">Manage IT hardware, assignments and lifecycle across the organization.</p>
      </div>
      <Tabs defaultValue="dashboard">
        <TabsList data-testid="it-tabs">
          <TabsTrigger value="dashboard" data-testid="it-tab-dashboard">Dashboard</TabsTrigger>
          <TabsTrigger value="assets" data-testid="it-tab-assets">Assets</TabsTrigger>
          <TabsTrigger value="import" data-testid="it-tab-import">Import</TabsTrigger>
        </TabsList>
        <TabsContent value="dashboard" className="mt-4"><DashboardTab dash={dash} /></TabsContent>
        <TabsContent value="assets" className="mt-4"><AssetsTab authHeaders={authHeaders} meta={meta} onChange={loadDash} /></TabsContent>
        <TabsContent value="import" className="mt-4"><ImportTab authHeaders={authHeaders} onDone={loadDash} /></TabsContent>
      </Tabs>
    </div>
  );
}

function DashboardTab({ dash }) {
  if (!dash) return <div className="text-slate-400 text-sm">Loading…</div>;
  const cards = [
    { label: 'Total Assets', value: dash.total, icon: Package, color: 'text-slate-700' },
    { label: 'Assigned', value: dash.summary.Assigned, icon: Laptop, color: 'text-blue-600' },
    { label: 'Available', value: dash.summary.Available, icon: CheckCircle2, color: 'text-emerald-600' },
    { label: 'In Stock', value: dash.summary['In Stock'], icon: Package, color: 'text-slate-600' },
    { label: 'Under Repair', value: dash.summary['Under Repair'], icon: Wrench, color: 'text-amber-600' },
    { label: 'Damaged/Lost', value: (dash.summary.Damaged || 0) + (dash.summary.Lost || 0), icon: AlertTriangle, color: 'text-red-600' },
  ];
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4" data-testid="it-dashboard-cards">
        {cards.map(c => (
          <Card key={c.label}><CardContent className="p-4">
            <div className="flex items-center justify-between"><c.icon className={`w-5 h-5 ${c.color}`} /></div>
            <div className="mt-2 text-2xl font-bold text-slate-900">{c.value ?? 0}</div>
            <div className="text-xs text-slate-500">{c.label}</div>
          </CardContent></Card>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card><CardHeader><CardTitle className="text-base">By Category</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {Object.entries(dash.by_category || {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
              <div key={k} className="flex justify-between text-sm border-b border-slate-100 py-1"><span className="text-slate-600">{k}</span><span className="font-semibold">{v}</span></div>
            ))}
            {Object.keys(dash.by_category || {}).length === 0 && <div className="text-sm text-slate-400">No assets yet.</div>}
          </CardContent>
        </Card>
        <Card><CardHeader><CardTitle className="text-base">Alerts</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm" data-testid="it-alerts">
            {[['Warranty expiring (30d)', dash.alerts.warranty_expiring], ['Warranty expired', dash.alerts.warranty_expired], ['AMC expiring (30d)', dash.alerts.amc_expiring], ['Under repair', dash.alerts.under_repair], ['Lost', dash.alerts.lost]].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-slate-100 py-1"><span className="text-slate-600">{k}</span><Badge variant={v > 0 ? 'destructive' : 'secondary'}>{v}</Badge></div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function AssetsTab({ authHeaders, meta, onChange }) {
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 25 });
  const [filters, setFilters] = useState({ search: '', category: 'All', status: 'All' });
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [detail, setDetail] = useState(null);
  const [action, setAction] = useState(null); // {type, asset}

  const load = useCallback(() => {
    const params = { page, page_size: 25 };
    if (filters.search) params.search = filters.search;
    if (filters.category !== 'All') params.category = filters.category;
    if (filters.status !== 'All') params.status = filters.status;
    axios.get(`${API}/it/assets`, { headers: authHeaders, params }).then(r => setData(r.data)).catch(() => toast.error('Failed to load assets'));
  }, [authHeaders, page, filters]);
  useEffect(() => { load(); }, [load]);

  const exportCsv = () => {
    const params = new URLSearchParams();
    if (filters.category !== 'All') params.set('category', filters.category);
    if (filters.status !== 'All') params.set('status', filters.status);
    if (filters.search) params.set('search', filters.search);
    axios.get(`${API}/it/export?${params}`, { headers: authHeaders, responseType: 'blob' }).then(r => {
      const url = URL.createObjectURL(r.data); const a = document.createElement('a');
      a.href = url; a.download = 'it_assets_export.csv'; a.click(); URL.revokeObjectURL(url);
    });
  };

  const totalPages = Math.max(1, Math.ceil(data.total / 25));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-center">
        <div className="relative">
          <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-slate-400" />
          <Input data-testid="it-asset-search" className="pl-8 w-64" placeholder="Search asset id, serial, brand…" value={filters.search}
            onChange={e => { setPage(1); setFilters(f => ({ ...f, search: e.target.value })); }} />
        </div>
        <Select value={filters.category} onValueChange={v => { setPage(1); setFilters(f => ({ ...f, category: v })); }}>
          <SelectTrigger className="w-40" data-testid="it-filter-category"><SelectValue placeholder="Category" /></SelectTrigger>
          <SelectContent><SelectItem value="All">All Categories</SelectItem>{meta.categories.map(c => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={filters.status} onValueChange={v => { setPage(1); setFilters(f => ({ ...f, status: v })); }}>
          <SelectTrigger className="w-40" data-testid="it-filter-status"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent><SelectItem value="All">All Statuses</SelectItem>{meta.statuses.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
        </Select>
        <div className="flex-1" />
        <Button variant="outline" onClick={exportCsv} data-testid="it-export-btn"><Download className="w-4 h-4 mr-1" />Export</Button>
        <Button onClick={() => setShowForm(true)} data-testid="it-add-asset-btn"><Plus className="w-4 h-4 mr-1" />Add Asset</Button>
      </div>

      <div className="border rounded-lg overflow-hidden">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Asset ID</TableHead><TableHead>Category</TableHead><TableHead>Brand / Model</TableHead>
            <TableHead>Serial</TableHead><TableHead>Status</TableHead><TableHead>Assigned To</TableHead><TableHead className="text-right">Actions</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {data.items.length === 0 && <TableRow><TableCell colSpan={7} className="text-center text-slate-400 py-8">No assets found.</TableCell></TableRow>}
            {data.items.map(a => (
              <TableRow key={a.asset_id} data-testid={`it-asset-row-${a.asset_id}`}>
                <TableCell className="font-medium">{a.asset_id}</TableCell>
                <TableCell>{a.category}</TableCell>
                <TableCell className="text-sm">{[a.brand, a.model].filter(Boolean).join(' ') || '—'}</TableCell>
                <TableCell className="text-sm text-slate-500">{a.serial_number || '—'}</TableCell>
                <TableCell><StatusBadge status={a.status} /></TableCell>
                <TableCell className="text-sm">{a.assigned_to?.employee_name || '—'}</TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  <Button size="icon" variant="ghost" title="View" onClick={() => setDetail(a.asset_id)} data-testid={`it-view-${a.asset_id}`}><Eye className="w-4 h-4" /></Button>
                  {!a.assigned_to && <Button size="icon" variant="ghost" title="Assign" onClick={() => setAction({ type: 'assign', asset: a })} data-testid={`it-assign-${a.asset_id}`}><UserPlus className="w-4 h-4" /></Button>}
                  {a.assigned_to && <Button size="icon" variant="ghost" title="Transfer" onClick={() => setAction({ type: 'transfer', asset: a })}><ArrowRightLeft className="w-4 h-4" /></Button>}
                  {a.assigned_to && <Button size="icon" variant="ghost" title="Return" onClick={() => setAction({ type: 'return', asset: a })}><Undo2 className="w-4 h-4" /></Button>}
                  <Button size="icon" variant="ghost" title="Archive" onClick={() => setAction({ type: 'archive', asset: a })}><Archive className="w-4 h-4 text-red-500" /></Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between text-sm text-slate-500">
        <span>{data.total} assets</span>
        <div className="flex gap-2 items-center">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
          <span>Page {page} / {totalPages}</span>
          <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next</Button>
        </div>
      </div>

      {showForm && <AssetForm authHeaders={authHeaders} meta={meta} onClose={() => setShowForm(false)} onSaved={() => { setShowForm(false); load(); onChange(); }} />}
      {detail && <AssetDetail authHeaders={authHeaders} assetId={detail} onClose={() => setDetail(null)} />}
      {action && <AssetActionDialog authHeaders={authHeaders} meta={meta} action={action} onClose={() => setAction(null)} onDone={() => { setAction(null); load(); onChange(); }} />}
    </div>
  );
}

function AssetForm({ authHeaders, meta, onClose, onSaved }) {
  const [f, setF] = useState({ category: '', status: 'In Stock', asset_id: '', name: '', brand: '', model: '', serial_number: '', condition: '', source: '', location: '', department: '', remarks: '' });
  const [purchase, setPurchase] = useState({ purchase_date: '', purchase_cost: '', vendor: '', invoice_number: '' });
  const [warranty, setWarranty] = useState({ warranty_end: '', amc_end: '' });
  const [specs, setSpecs] = useState({});
  const [saving, setSaving] = useState(false);
  const catFields = (meta.categories.find(c => c.name === f.category)?.fields) || [];

  const save = () => {
    if (!f.category) { toast.error('Category is required'); return; }
    setSaving(true);
    axios.post(`${API}/it/assets`, { ...f, purchase, warranty, specs }, { headers: authHeaders })
      .then(() => { toast.success('Asset created'); onSaved(); })
      .catch(e => toast.error(e.response?.data?.detail || 'Failed to create'))
      .finally(() => setSaving(false));
  };
  const set = (k, v) => setF(p => ({ ...p, [k]: v }));

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="it-asset-form">
        <DialogHeader><DialogTitle>Add Asset</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="text-xs font-semibold text-slate-500 uppercase">Basic Information</div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Asset Category *</Label>
              <Select value={f.category} onValueChange={v => set('category', v)}>
                <SelectTrigger data-testid="it-form-category"><SelectValue placeholder="Select category" /></SelectTrigger>
                <SelectContent>{meta.categories.map(c => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}</SelectContent>
              </Select></div>
            <div><Label>Status *</Label>
              <Select value={f.status} onValueChange={v => set('status', v)}>
                <SelectTrigger data-testid="it-form-status"><SelectValue /></SelectTrigger>
                <SelectContent>{meta.statuses.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select></div>
            <div><Label>Asset ID (blank = auto)</Label><Input value={f.asset_id} onChange={e => set('asset_id', e.target.value)} placeholder="Auto-generated" data-testid="it-form-assetid" /></div>
            <div><Label>Asset Tag</Label><Input value={f.asset_tag || ''} onChange={e => set('asset_tag', e.target.value)} /></div>
            <div><Label>Brand</Label><Input value={f.brand} onChange={e => set('brand', e.target.value)} /></div>
            <div><Label>Model</Label><Input value={f.model} onChange={e => set('model', e.target.value)} /></div>
            <div><Label>Serial Number</Label><Input value={f.serial_number} onChange={e => set('serial_number', e.target.value)} data-testid="it-form-serial" /></div>
            <div><Label>Condition</Label>
              <Select value={f.condition} onValueChange={v => set('condition', v)}>
                <SelectTrigger><SelectValue placeholder="—" /></SelectTrigger>
                <SelectContent>{meta.conditions.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select></div>
            <div><Label>Asset Source</Label>
              <Select value={f.source} onValueChange={v => set('source', v)}>
                <SelectTrigger><SelectValue placeholder="—" /></SelectTrigger>
                <SelectContent>{meta.sources.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select></div>
            <div><Label>Location</Label><Input value={f.location} onChange={e => set('location', e.target.value)} /></div>
            <div><Label>Department</Label><Input value={f.department} onChange={e => set('department', e.target.value)} /></div>
          </div>

          {catFields.length > 0 && <>
            <div className="text-xs font-semibold text-slate-500 uppercase">{f.category} Specifications</div>
            <div className="grid grid-cols-2 gap-3">
              {catFields.map(field => (
                <div key={field}><Label>{field}</Label><Input value={specs[field] || ''} onChange={e => setSpecs(p => ({ ...p, [field]: e.target.value }))} /></div>
              ))}
            </div>
          </>}

          <div className="text-xs font-semibold text-slate-500 uppercase">Purchase (optional)</div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Purchase Date</Label><Input type="date" value={purchase.purchase_date} onChange={e => setPurchase(p => ({ ...p, purchase_date: e.target.value }))} /></div>
            <div><Label>Purchase Cost</Label><Input value={purchase.purchase_cost} onChange={e => setPurchase(p => ({ ...p, purchase_cost: e.target.value }))} /></div>
            <div><Label>Vendor</Label><Input value={purchase.vendor} onChange={e => setPurchase(p => ({ ...p, vendor: e.target.value }))} /></div>
            <div><Label>Invoice Number</Label><Input value={purchase.invoice_number} onChange={e => setPurchase(p => ({ ...p, invoice_number: e.target.value }))} /></div>
          </div>
          <div className="text-xs font-semibold text-slate-500 uppercase">Warranty / AMC (optional)</div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Warranty End</Label><Input type="date" value={warranty.warranty_end} onChange={e => setWarranty(p => ({ ...p, warranty_end: e.target.value }))} /></div>
            <div><Label>AMC End</Label><Input type="date" value={warranty.amc_end} onChange={e => setWarranty(p => ({ ...p, amc_end: e.target.value }))} /></div>
          </div>
          <div><Label>Remarks</Label><Textarea value={f.remarks} onChange={e => set('remarks', e.target.value)} /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={saving} data-testid="it-form-save">{saving ? 'Saving…' : 'Save Asset'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EmployeePicker({ authHeaders, value, onSelect }) {
  const [q, setQ] = useState('');
  const [opts, setOpts] = useState([]);
  useEffect(() => {
    const t = setTimeout(() => {
      axios.get(`${API}/employees`, { headers: authHeaders, params: { search: q, limit: 20 } })
        .then(r => setOpts(Array.isArray(r.data) ? r.data : (r.data?.employees || []))).catch(() => {});
    }, 300);
    return () => clearTimeout(t);
  }, [q]); // eslint-disable-line
  return (
    <div>
      <Input placeholder="Search employee by name…" value={q} onChange={e => setQ(e.target.value)} data-testid="it-emp-search" />
      <div className="max-h-40 overflow-y-auto mt-1 border rounded">
        {opts.map(e => (
          <button key={e.id} type="button" onClick={() => onSelect(e)} className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-50 ${value?.id === e.id ? 'bg-blue-50' : ''}`} data-testid={`it-emp-opt-${e.id}`}>
            {e.full_name} <span className="text-slate-400 text-xs">{e.emp_id} · {e.department}</span>
          </button>
        ))}
      </div>
      {value && <div className="text-xs text-emerald-700 mt-1">Selected: {value.full_name}</div>}
    </div>
  );
}

function AssetActionDialog({ authHeaders, meta, action, onClose, onDone }) {
  const { type, asset } = action;
  const [emp, setEmp] = useState(null);
  const [status, setStatus] = useState('Available');
  const [condition, setCondition] = useState('');
  const [remarks, setRemarks] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = () => {
    setBusy(true);
    let url, body;
    if (type === 'assign') { url = `${API}/it/assets/${asset.asset_id}/assign`; body = { employee_id: emp?.id, condition }; if (!emp) { toast.error('Select an employee'); setBusy(false); return; } }
    else if (type === 'transfer') { url = `${API}/it/assets/${asset.asset_id}/transfer`; body = { employee_id: emp?.id }; if (!emp) { toast.error('Select an employee'); setBusy(false); return; } }
    else if (type === 'return') { url = `${API}/it/assets/${asset.asset_id}/return`; body = { status, condition, remarks }; }
    else if (type === 'archive') { axios.delete(`${API}/it/assets/${asset.asset_id}`, { headers: authHeaders }).then(() => { toast.success('Asset archived'); onDone(); }).catch(e => toast.error(e.response?.data?.detail || 'Failed')).finally(() => setBusy(false)); return; }
    axios.post(url, body, { headers: authHeaders }).then(() => { toast.success('Done'); onDone(); }).catch(e => toast.error(e.response?.data?.detail || 'Failed')).finally(() => setBusy(false));
  };
  const titles = { assign: 'Assign Asset', transfer: 'Transfer Asset', return: 'Return Asset', archive: 'Archive Asset' };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent data-testid="it-action-dialog">
        <DialogHeader><DialogTitle>{titles[type]} — {asset.asset_id}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          {(type === 'assign' || type === 'transfer') && <EmployeePicker authHeaders={authHeaders} value={emp} onSelect={setEmp} />}
          {type === 'return' && <>
            <div><Label>New Status</Label>
              <Select value={status} onValueChange={setStatus}><SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{['Available', 'In Stock', 'Under Repair', 'Damaged', 'Retired'].map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>
            <div><Label>Remarks</Label><Textarea value={remarks} onChange={e => setRemarks(e.target.value)} /></div>
          </>}
          {(type === 'assign' || type === 'return') && <div><Label>Condition</Label>
            <Select value={condition} onValueChange={setCondition}><SelectTrigger><SelectValue placeholder="—" /></SelectTrigger>
              <SelectContent>{meta.conditions.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>}
          {type === 'archive' && <p className="text-sm text-slate-600">This soft-deletes the asset (history preserved). Continue?</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} disabled={busy} data-testid="it-action-confirm">{busy ? '…' : 'Confirm'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AssetDetail({ authHeaders, assetId, onClose }) {
  const [d, setD] = useState(null);
  useEffect(() => { axios.get(`${API}/it/assets/${assetId}`, { headers: authHeaders }).then(r => setD(r.data)).catch(() => {}); }, [assetId]); // eslint-disable-line
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="it-asset-detail">
        <DialogHeader><DialogTitle>{assetId}</DialogTitle></DialogHeader>
        {!d ? <div className="text-slate-400">Loading…</div> : <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2 text-sm">
            {[['Category', d.asset.category], ['Status', d.asset.status], ['Brand', d.asset.brand], ['Model', d.asset.model], ['Serial', d.asset.serial_number], ['Condition', d.asset.condition], ['Source', d.asset.source], ['Location', d.asset.location], ['Department', d.asset.department], ['Assigned To', d.asset.assigned_to?.employee_name]].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-slate-100 py-1"><span className="text-slate-500">{k}</span><span className="font-medium">{v || '—'}</span></div>
            ))}
          </div>
          {Object.keys(d.asset.specs || {}).length > 0 && <div>
            <div className="text-xs font-semibold text-slate-500 uppercase mb-1">Specifications</div>
            <div className="grid grid-cols-2 gap-2 text-sm">{Object.entries(d.asset.specs).map(([k, v]) => v && <div key={k} className="flex justify-between border-b border-slate-100 py-1"><span className="text-slate-500">{k}</span><span>{v}</span></div>)}</div>
          </div>}
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase mb-2 flex items-center gap-1"><History className="w-3.5 h-3.5" />Timeline</div>
            <div className="space-y-2" data-testid="it-history">
              {d.history.map(h => (
                <div key={h.id} className="flex gap-3 text-sm">
                  <div className="w-2 h-2 rounded-full bg-blue-400 mt-1.5" />
                  <div><div className="font-medium">{h.action}</div><div className="text-slate-500 text-xs">{h.note}</div><div className="text-slate-400 text-xs">{h.by_name} · {new Date(h.at).toLocaleString()}</div></div>
                </div>
              ))}
            </div>
          </div>
        </div>}
      </DialogContent>
    </Dialog>
  );
}

function ImportTab({ authHeaders, onDone }) {
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);

  const template = () => axios.get(`${API}/it/import/template`, { headers: authHeaders, responseType: 'blob' }).then(r => {
    const url = URL.createObjectURL(r.data); const a = document.createElement('a'); a.href = url; a.download = 'it_asset_import_template.csv'; a.click(); URL.revokeObjectURL(url);
  });

  const upload = (e) => {
    const file = e.target.files?.[0]; if (!file) return;
    const fd = new FormData(); fd.append('file', file); setBusy(true);
    axios.post(`${API}/it/import/preview`, fd, { headers: { ...authHeaders } })
      .then(r => setPreview(r.data)).catch(er => toast.error(er.response?.data?.detail || 'Parse failed')).finally(() => setBusy(false));
  };
  const confirm = () => {
    setBusy(true);
    axios.post(`${API}/it/import/confirm`, { rows: preview.rows }, { headers: authHeaders })
      .then(r => { toast.success(`Imported ${r.data.created}, skipped ${r.data.skipped}`); setPreview(null); onDone(); })
      .catch(e => toast.error(e.response?.data?.detail || 'Import failed')).finally(() => setBusy(false));
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Button variant="outline" onClick={template} data-testid="it-import-template"><Download className="w-4 h-4 mr-1" />Download Template</Button>
        <label className="inline-flex">
          <input type="file" accept=".csv,.xlsx" className="hidden" onChange={upload} data-testid="it-import-file" />
          <span className="inline-flex items-center px-4 py-2 rounded-md bg-slate-900 text-white text-sm cursor-pointer hover:bg-slate-800"><Upload className="w-4 h-4 mr-1" />Upload CSV / Excel</span>
        </label>
      </div>
      {busy && <div className="text-sm text-slate-400">Processing…</div>}
      {preview && <div className="space-y-3">
        <div className="flex gap-3 text-sm" data-testid="it-import-summary">
          <Badge variant="secondary">Total {preview.total}</Badge>
          <Badge className="bg-emerald-100 text-emerald-700">Valid {preview.valid}</Badge>
          <Badge variant="destructive">Errors {preview.errors}</Badge>
          <Badge className="bg-amber-100 text-amber-700">Warnings {preview.warnings}</Badge>
        </div>
        <div className="border rounded max-h-96 overflow-auto">
          <Table><TableHeader><TableRow><TableHead>Row</TableHead><TableHead>Asset ID</TableHead><TableHead>Category</TableHead><TableHead>Status</TableHead><TableHead>Issues</TableHead></TableRow></TableHeader>
            <TableBody>{preview.rows.map(r => (
              <TableRow key={r.row} className={r.errors.length ? 'bg-red-50' : ''}>
                <TableCell>{r.row}</TableCell><TableCell>{r.data.asset_id || '(auto)'}</TableCell><TableCell>{r.data.category}</TableCell><TableCell>{r.data.status}</TableCell>
                <TableCell className="text-xs">{r.errors.map((e, i) => <div key={i} className="text-red-600">{e}</div>)}{r.warnings.map((w, i) => <div key={i} className="text-amber-600">{w}</div>)}</TableCell>
              </TableRow>
            ))}</TableBody></Table>
        </div>
        <Button onClick={confirm} disabled={busy || preview.valid === 0} data-testid="it-import-confirm">Import {preview.valid} valid rows</Button>
      </div>}
    </div>
  );
}
