import { useState, useEffect, useMemo, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Card, CardContent } from '../components/ui/card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Laptop, Package, CheckCircle2, Wrench, AlertTriangle, Search, Plus, Upload, Download, History, ArrowRightLeft, UserPlus, Undo2, Archive, Eye, Server, X, ClipboardList } from 'lucide-react';
import { ComponentsTab, AssetComponentsSection, ComponentDashboardCards, AssetCreateComponents } from './ITComponents';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const NAVY = '#0b1f3b';
const PRIMARY = 'bg-[#063c88] hover:bg-[#052d66] text-white rounded-xl shadow-sm shadow-[#063c88]/20';
const OUTLINE = 'rounded-xl border-[#063c88]/30 text-[#063c88] hover:bg-[#063c88]/5';
const CARD = 'bg-[#fffdf7] rounded-2xl border border-slate-200/70 shadow-sm';
const DIALOG = 'bg-[#fffdf7] rounded-2xl max-w-2xl max-h-[85vh] overflow-y-auto';
const font = { fontFamily: 'Outfit, sans-serif' };

const StatusBadge = ({ status }) => {
  const map = {
    'Assigned': 'bg-blue-100 text-blue-700 ring-blue-600/20', 'Available': 'bg-emerald-100 text-emerald-700 ring-emerald-600/20',
    'In Stock': 'bg-slate-100 text-slate-700 ring-slate-500/20', 'Under Repair': 'bg-amber-100 text-amber-700 ring-amber-600/20',
    'Under Maintenance': 'bg-amber-100 text-amber-700 ring-amber-600/20', 'Damaged': 'bg-red-100 text-red-700 ring-red-600/20',
    'Lost': 'bg-red-100 text-red-700 ring-red-600/20', 'Retired': 'bg-slate-200 text-slate-600 ring-slate-500/20',
    'Disposed': 'bg-slate-200 text-slate-600 ring-slate-500/20',
  };
  return <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ring-1 ring-inset ${map[status] || 'bg-slate-100 text-slate-700 ring-slate-500/20'}`}>{status || '—'}</span>;
};

const Spinner = () => (
  <div className="flex justify-center py-12"><div className="w-8 h-8 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" /></div>
);

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

  const tabCls = 'rounded-lg px-4 data-[state=active]:bg-white data-[state=active]:text-[#063c88] data-[state=active]:shadow-sm text-slate-600 font-medium';

  return (
    <div className="space-y-6" data-testid="it-management-page">
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-xl bg-[#063c88] flex items-center justify-center shadow-lg shadow-[#063c88]/20">
          <Server className="w-6 h-6 text-white" strokeWidth={1.8} />
        </div>
        <div>
          <h1 className="text-2xl font-bold" style={{ ...font, color: NAVY }}>IT Asset &amp; Infrastructure Management</h1>
          <p className="text-sm text-slate-500">Manage IT hardware, components, assignments and lifecycle across the organization.</p>
        </div>
      </div>
      <Tabs defaultValue="dashboard">
        <TabsList data-testid="it-tabs" className="bg-[#063c88]/5 p-1 rounded-xl max-w-full overflow-x-auto flex-nowrap justify-start">
          <TabsTrigger value="dashboard" data-testid="it-tab-dashboard" className={tabCls}>Dashboard</TabsTrigger>
          <TabsTrigger value="assets" data-testid="it-tab-assets" className={tabCls}>Assets</TabsTrigger>
          <TabsTrigger value="components" data-testid="it-tab-components" className={tabCls}>Components</TabsTrigger>
          <TabsTrigger value="import" data-testid="it-tab-import" className={tabCls}>Import</TabsTrigger>
        </TabsList>
        <TabsContent value="dashboard" className="mt-5"><DashboardTab dash={dash} authHeaders={authHeaders} /></TabsContent>
        <TabsContent value="assets" className="mt-5"><AssetsTab authHeaders={authHeaders} meta={meta} onChange={loadDash} /></TabsContent>
        <TabsContent value="components" className="mt-5"><ComponentsTab authHeaders={authHeaders} onChange={loadDash} /></TabsContent>
        <TabsContent value="import" className="mt-5"><ImportTab authHeaders={authHeaders} onDone={loadDash} /></TabsContent>
      </Tabs>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, tint }) {
  return (
    <div className={`${CARD} p-4`}>
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${tint}`}><Icon className="w-5 h-5" strokeWidth={1.8} /></div>
      <div className="mt-3 text-2xl font-bold" style={{ ...font, color: NAVY }}>{value ?? 0}</div>
      <div className="text-xs text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}

function DashboardTab({ dash, authHeaders }) {
  if (!dash) return <Spinner />;
  const cards = [
    { label: 'Total Assets', value: dash.total, icon: Package, tint: 'bg-[#063c88]/10 text-[#063c88]' },
    { label: 'Assigned', value: dash.summary.Assigned, icon: Laptop, tint: 'bg-blue-100 text-blue-600' },
    { label: 'Available', value: dash.summary.Available, icon: CheckCircle2, tint: 'bg-emerald-100 text-emerald-600' },
    { label: 'In Stock', value: dash.summary['In Stock'], icon: Package, tint: 'bg-slate-100 text-slate-600' },
    { label: 'Under Repair', value: dash.summary['Under Repair'], icon: Wrench, tint: 'bg-amber-100 text-amber-600' },
    { label: 'Damaged / Lost', value: (dash.summary.Damaged || 0) + (dash.summary.Lost || 0), icon: AlertTriangle, tint: 'bg-red-100 text-red-600' },
  ];
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4" data-testid="it-dashboard-cards">
        {cards.map(c => <StatCard key={c.label} {...c} />)}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className={CARD}>
          <div className="px-5 py-3 border-b border-slate-200/70 font-semibold" style={{ ...font, color: NAVY }}>By Category</div>
          <div className="p-5 space-y-2">
            {Object.entries(dash.by_category || {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
              <div key={k} className="flex justify-between text-sm border-b border-slate-100 py-1.5"><span className="text-slate-600">{k}</span><span className="font-semibold text-[#063c88]">{v}</span></div>
            ))}
            {Object.keys(dash.by_category || {}).length === 0 && <div className="text-sm text-slate-400">No assets yet.</div>}
          </div>
        </div>
        <div className={CARD}>
          <div className="px-5 py-3 border-b border-slate-200/70 font-semibold" style={{ ...font, color: NAVY }}>Alerts</div>
          <div className="p-5 space-y-2 text-sm" data-testid="it-alerts">
            {[['Warranty expiring (30d)', dash.alerts.warranty_expiring], ['Warranty expired', dash.alerts.warranty_expired], ['AMC expiring (30d)', dash.alerts.amc_expiring], ['Under repair', dash.alerts.under_repair], ['Lost', dash.alerts.lost]].map(([k, v]) => (
              <div key={k} className="flex justify-between items-center border-b border-slate-100 py-1.5"><span className="text-slate-600">{k}</span><Badge variant={v > 0 ? 'destructive' : 'secondary'}>{v}</Badge></div>
            ))}
          </div>
        </div>
      </div>
      <ComponentDashboardCards authHeaders={authHeaders} />
    </div>
  );
}

function AssetsTab({ authHeaders, meta, onChange }) {
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 25 });
  const [filters, setFilters] = useState({ search: '', category: 'All', status: 'All' });
  const [pageSize, setPageSize] = useState(25);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [detail, setDetail] = useState(null);
  const [action, setAction] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    const params = { page, page_size: pageSize };
    if (filters.search) params.search = filters.search;
    if (filters.category !== 'All') params.category = filters.category;
    if (filters.status !== 'All') params.status = filters.status;
    axios.get(`${API}/it/assets`, { headers: authHeaders, params }).then(r => setData(r.data)).catch(() => toast.error('Failed to load assets')).finally(() => setLoading(false));
  }, [authHeaders, page, pageSize, filters]);
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

  const chips = [];
  if (filters.category !== 'All') chips.push(['category', filters.category]);
  if (filters.status !== 'All') chips.push(['status', filters.status]);
  const clearChip = (k) => { setPage(1); setFilters(f => ({ ...f, [k]: 'All' })); };
  const clearAll = () => { setPage(1); setFilters({ search: '', category: 'All', status: 'All' }); };
  const totalPages = Math.max(1, Math.ceil(data.total / pageSize));

  return (
    <div className="space-y-4">
      <div className={`${CARD} p-4 space-y-3`}>
        <div className="flex flex-wrap gap-2 items-center">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <Input data-testid="it-asset-search" className="pl-9 rounded-xl bg-white" placeholder="Search asset ID, serial number, brand…" value={filters.search}
              onChange={e => { setPage(1); setFilters(f => ({ ...f, search: e.target.value })); }} />
          </div>
          <Select value={filters.category} onValueChange={v => { setPage(1); setFilters(f => ({ ...f, category: v })); }}>
            <SelectTrigger className="w-40 rounded-xl bg-white" data-testid="it-filter-category"><SelectValue placeholder="Category" /></SelectTrigger>
            <SelectContent><SelectItem value="All">All Categories</SelectItem>{meta.categories.map(c => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={filters.status} onValueChange={v => { setPage(1); setFilters(f => ({ ...f, status: v })); }}>
            <SelectTrigger className="w-40 rounded-xl bg-white" data-testid="it-filter-status"><SelectValue placeholder="Status" /></SelectTrigger>
            <SelectContent><SelectItem value="All">All Statuses</SelectItem>{meta.statuses.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
          </Select>
          <Button variant="outline" className={OUTLINE} onClick={exportCsv} data-testid="it-export-btn"><Download className="w-4 h-4 mr-1.5" />Export</Button>
          <Button className={PRIMARY} onClick={() => setShowForm(true)} data-testid="it-add-asset-btn"><Plus className="w-4 h-4 mr-1.5" />Add Asset</Button>
        </div>
        {chips.length > 0 && (
          <div className="flex flex-wrap gap-2 items-center">
            <span className="text-xs text-slate-400 font-medium">Filters:</span>
            {chips.map(([k, v]) => (
              <button key={k} onClick={() => clearChip(k)} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-[#063c88]/10 text-[#063c88] hover:bg-[#063c88]/20" data-testid={`it-chip-${k}`}>
                {v}<X className="w-3 h-3" />
              </button>
            ))}
            <button onClick={clearAll} className="text-xs text-slate-500 hover:text-[#063c88] underline" data-testid="it-clear-filters">Clear all</button>
          </div>
        )}
      </div>

      <div className={`${CARD} overflow-hidden`}>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="bg-[#063c88]/[0.04] hover:bg-[#063c88]/[0.04]">
                <TableHead className="font-semibold text-slate-600">Asset ID</TableHead>
                <TableHead className="font-semibold text-slate-600">Category</TableHead>
                <TableHead className="font-semibold text-slate-600">Brand / Model</TableHead>
                <TableHead className="font-semibold text-slate-600">Serial</TableHead>
                <TableHead className="font-semibold text-slate-600">Status</TableHead>
                <TableHead className="font-semibold text-slate-600">Assigned To</TableHead>
                <TableHead className="font-semibold text-slate-600 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && <TableRow><TableCell colSpan={7}><Spinner /></TableCell></TableRow>}
              {!loading && data.items.length === 0 && (
                <TableRow><TableCell colSpan={7}>
                  <div className="flex flex-col items-center justify-center py-14 text-center">
                    <div className="w-14 h-14 rounded-2xl bg-[#063c88]/10 flex items-center justify-center mb-3"><Package className="w-7 h-7 text-[#063c88]" /></div>
                    <div className="font-semibold" style={{ ...font, color: NAVY }}>No assets found</div>
                    <div className="text-sm text-slate-500 mt-1">{chips.length || filters.search ? 'Try changing your search or filters.' : 'Get started by adding your first asset.'}</div>
                    {(chips.length || filters.search)
                      ? <Button variant="outline" className={`${OUTLINE} mt-4`} onClick={clearAll} data-testid="it-empty-clear">Clear Filters</Button>
                      : <Button className={`${PRIMARY} mt-4`} onClick={() => setShowForm(true)}><Plus className="w-4 h-4 mr-1.5" />Add Asset</Button>}
                  </div>
                </TableCell></TableRow>
              )}
              {!loading && data.items.map(a => (
                <TableRow key={a.asset_id} data-testid={`it-asset-row-${a.asset_id}`} className="hover:bg-[#063c88]/[0.03] transition-colors">
                  <TableCell className="font-semibold text-[#063c88]">{a.asset_id}</TableCell>
                  <TableCell>{a.category}</TableCell>
                  <TableCell className="text-sm">{[a.brand, a.model].filter(Boolean).join(' ') || '—'}</TableCell>
                  <TableCell className="text-sm text-slate-500">{a.serial_number || '—'}</TableCell>
                  <TableCell><StatusBadge status={a.status} /></TableCell>
                  <TableCell className="text-sm">{a.assigned_to?.employee_name || <span className="text-slate-400">Unassigned</span>}</TableCell>
                  <TableCell className="text-right whitespace-nowrap">
                    <Button size="icon" variant="ghost" className="rounded-lg hover:bg-[#063c88]/10 hover:text-[#063c88]" title="View" onClick={() => setDetail(a.asset_id)} data-testid={`it-view-${a.asset_id}`}><Eye className="w-4 h-4" /></Button>
                    {!a.assigned_to && <Button size="icon" variant="ghost" className="rounded-lg hover:bg-[#063c88]/10 hover:text-[#063c88]" title="Assign" onClick={() => setAction({ type: 'assign', asset: a })} data-testid={`it-assign-${a.asset_id}`}><UserPlus className="w-4 h-4" /></Button>}
                    {a.assigned_to && <Button size="icon" variant="ghost" className="rounded-lg hover:bg-[#063c88]/10 hover:text-[#063c88]" title="Transfer" onClick={() => setAction({ type: 'transfer', asset: a })}><ArrowRightLeft className="w-4 h-4" /></Button>}
                    {a.assigned_to && <Button size="icon" variant="ghost" className="rounded-lg hover:bg-[#063c88]/10 hover:text-[#063c88]" title="Return" onClick={() => setAction({ type: 'return', asset: a })}><Undo2 className="w-4 h-4" /></Button>}
                    <Button size="icon" variant="ghost" className="rounded-lg hover:bg-red-50 hover:text-red-600" title="Archive" onClick={() => setAction({ type: 'archive', asset: a })}><Archive className="w-4 h-4" /></Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-t border-slate-200/70 text-sm text-slate-500">
          <div className="flex items-center gap-2">
            <span>{data.total} asset{data.total === 1 ? '' : 's'}</span>
            <span className="text-slate-300">·</span>
            <span>Rows</span>
            <Select value={String(pageSize)} onValueChange={v => { setPage(1); setPageSize(Number(v)); }}>
              <SelectTrigger className="h-7 w-16 rounded-lg bg-white" data-testid="it-page-size"><SelectValue /></SelectTrigger>
              <SelectContent>{[10, 25, 50, 100].map(n => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="flex gap-2 items-center">
            <Button size="sm" variant="outline" className={OUTLINE} disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
            <span>Page {page} / {totalPages}</span>
            <Button size="sm" variant="outline" className={OUTLINE} disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next</Button>
          </div>
        </div>
      </div>

      {showForm && <AssetForm authHeaders={authHeaders} meta={meta} onClose={() => setShowForm(false)} onSaved={() => { setShowForm(false); load(); onChange(); }} />}
      {detail && <AssetDetail authHeaders={authHeaders} assetId={detail} onClose={() => setDetail(null)} />}
      {action && <AssetActionDialog authHeaders={authHeaders} meta={meta} action={action} onClose={() => setAction(null)} onDone={() => { setAction(null); load(); onChange(); }} />}
    </div>
  );
}

const SectionTitle = ({ children }) => (
  <div className="text-xs font-semibold uppercase tracking-wide text-[#063c88] pt-1">{children}</div>
);

function AssetForm({ authHeaders, meta, onClose, onSaved }) {
  const [f, setF] = useState({ category: '', status: 'In Stock', asset_id: '', name: '', brand: '', model: '', serial_number: '', condition: '', source: '', location: '', department: '', remarks: '' });
  const [purchase, setPurchase] = useState({ purchase_date: '', purchase_cost: '', vendor: '', invoice_number: '' });
  const [warranty, setWarranty] = useState({ warranty_end: '', amc_end: '' });
  const [specs, setSpecs] = useState({});
  const [components, setComponents] = useState([]);
  const [assignEmp, setAssignEmp] = useState(null);
  const [saving, setSaving] = useState(false);
  const catFields = (meta.categories.find(c => c.name === f.category)?.fields) || [];

  const save = () => {
    if (!f.category) { toast.error('Category is required'); return; }
    setSaving(true);
    const payload = { ...f, purchase, warranty, specs };
    if (assignEmp) payload.assign_employee_id = assignEmp.id;
    axios.post(`${API}/it/assets`, payload, { headers: authHeaders })
      .then(async (res) => {
        const assetId = res.data.asset_id;
        if (components.length > 0 && assetId) {
          try {
            await axios.post(`${API}/it/assets/${assetId}/install-components`,
              { items: components.map(c => ({ component_id: c.component_id, slot: c.slot })) },
              { headers: authHeaders });
          } catch (e) {
            toast.error(e.response?.data?.detail || 'Asset created but some components could not be installed');
          }
        }
        toast.success('Asset created');
        onSaved();
      })
      .catch(e => toast.error(e.response?.data?.detail || 'Failed to create'))
      .finally(() => setSaving(false));
  };
  const set = (k, v) => setF(p => ({ ...p, [k]: v }));

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className={DIALOG} data-testid="it-asset-form">
        <DialogHeader><DialogTitle style={font}>Add Asset</DialogTitle></DialogHeader>
        <div className="space-y-5">
          <div className="rounded-xl border border-slate-200/70 bg-white/60 p-4 space-y-3">
            <SectionTitle>Basic Information</SectionTitle>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Asset Category *</Label>
                <Select value={f.category} onValueChange={v => set('category', v)}>
                  <SelectTrigger data-testid="it-form-category" className="rounded-xl"><SelectValue placeholder="Select category" /></SelectTrigger>
                  <SelectContent>{meta.categories.map(c => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}</SelectContent>
                </Select></div>
              <div><Label>Status *</Label>
                <Select value={f.status} onValueChange={v => set('status', v)}>
                  <SelectTrigger data-testid="it-form-status" className="rounded-xl"><SelectValue /></SelectTrigger>
                  <SelectContent>{meta.statuses.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                </Select></div>
              <div><Label>Asset ID (blank = auto)</Label><Input className="rounded-xl" value={f.asset_id} onChange={e => set('asset_id', e.target.value)} placeholder="Auto-generated" data-testid="it-form-assetid" /></div>
              <div><Label>Asset Tag</Label><Input className="rounded-xl" value={f.asset_tag || ''} onChange={e => set('asset_tag', e.target.value)} /></div>
              <div><Label>Brand</Label><Input className="rounded-xl" value={f.brand} onChange={e => set('brand', e.target.value)} /></div>
              <div><Label>Model</Label><Input className="rounded-xl" value={f.model} onChange={e => set('model', e.target.value)} /></div>
              <div><Label>Serial Number</Label><Input className="rounded-xl" value={f.serial_number} onChange={e => set('serial_number', e.target.value)} data-testid="it-form-serial" /></div>
              <div><Label>Condition</Label>
                <Select value={f.condition} onValueChange={v => set('condition', v)}>
                  <SelectTrigger className="rounded-xl"><SelectValue placeholder="—" /></SelectTrigger>
                  <SelectContent>{meta.conditions.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                </Select></div>
              <div><Label>Asset Source</Label>
                <Select value={f.source} onValueChange={v => set('source', v)}>
                  <SelectTrigger className="rounded-xl"><SelectValue placeholder="—" /></SelectTrigger>
                  <SelectContent>{meta.sources.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                </Select></div>
              <div><Label>Location</Label><Input className="rounded-xl" value={f.location} onChange={e => set('location', e.target.value)} /></div>
              <div><Label>Department</Label><Input className="rounded-xl" value={f.department} onChange={e => set('department', e.target.value)} /></div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200/70 bg-white/60 p-4 space-y-3">
            <SectionTitle>Assignment (optional)</SectionTitle>
            <ActiveEmployeePicker authHeaders={authHeaders} value={assignEmp} onSelect={setAssignEmp} />
            {!assignEmp && <p className="text-xs text-slate-500">Asset will remain unassigned and can be assigned later.</p>}
          </div>

          {catFields.length > 0 && (
            <div className="rounded-xl border border-slate-200/70 bg-white/60 p-4 space-y-3">
              <SectionTitle>{f.category} Specifications</SectionTitle>
              <div className="grid grid-cols-2 gap-3">
                {catFields.map(field => (
                  <div key={field}><Label>{field}</Label><Input className="rounded-xl" value={specs[field] || ''} onChange={e => setSpecs(p => ({ ...p, [field]: e.target.value }))} /></div>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-xl border border-slate-200/70 bg-white/60 p-4 space-y-3">
            <SectionTitle>Purchase &amp; Warranty (optional)</SectionTitle>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Purchase Date</Label><Input type="date" className="rounded-xl" value={purchase.purchase_date} onChange={e => setPurchase(p => ({ ...p, purchase_date: e.target.value }))} /></div>
              <div><Label>Purchase Cost</Label><Input className="rounded-xl" value={purchase.purchase_cost} onChange={e => setPurchase(p => ({ ...p, purchase_cost: e.target.value }))} /></div>
              <div><Label>Vendor</Label><Input className="rounded-xl" value={purchase.vendor} onChange={e => setPurchase(p => ({ ...p, vendor: e.target.value }))} /></div>
              <div><Label>Invoice Number</Label><Input className="rounded-xl" value={purchase.invoice_number} onChange={e => setPurchase(p => ({ ...p, invoice_number: e.target.value }))} /></div>
              <div><Label>Warranty End</Label><Input type="date" className="rounded-xl" value={warranty.warranty_end} onChange={e => setWarranty(p => ({ ...p, warranty_end: e.target.value }))} /></div>
              <div><Label>AMC End</Label><Input type="date" className="rounded-xl" value={warranty.amc_end} onChange={e => setWarranty(p => ({ ...p, amc_end: e.target.value }))} /></div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200/70 bg-white/60 p-4 space-y-3">
            <SectionTitle>Components (optional)</SectionTitle>
            <p className="text-xs text-slate-500">Attach available components now, or add them later from the asset's detail view. Pick a type to see only components that are currently free.</p>
            <AssetCreateComponents authHeaders={authHeaders} selected={components} onChange={setComponents} />
          </div>

          <div><Label>Remarks</Label><Textarea className="rounded-xl" value={f.remarks} onChange={e => set('remarks', e.target.value)} /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" className={OUTLINE} onClick={onClose}>Cancel</Button>
          <Button className={PRIMARY} onClick={save} disabled={saving} data-testid="it-form-save">{saving ? 'Saving…' : 'Create Asset'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Active-only employee picker (used by the Create-Asset assignment shortcut)
function ActiveEmployeePicker({ authHeaders, value, onSelect }) {
  const [q, setQ] = useState('');
  const [opts, setOpts] = useState([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => {
      setLoading(true);
      axios.get(`${API}/employees`, { headers: authHeaders, params: { search: q, status: 'Active', limit: 20 } })
        .then(r => setOpts(Array.isArray(r.data) ? r.data : (r.data?.employees || []))).catch(() => {}).finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(t);
  }, [q]); // eslint-disable-line
  return (
    <div>
      <div className="relative">
        <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
        <Input className="pl-9 rounded-xl bg-white" placeholder="Search active employee by name, ID, department…" value={q} onChange={e => setQ(e.target.value)} data-testid="it-active-emp-search" />
      </div>
      {(q || value) && (
        <div className="max-h-44 overflow-y-auto mt-1.5 border rounded-xl bg-white">
          {loading && <div className="px-3 py-2 text-xs text-slate-400">Searching…</div>}
          {!loading && opts.length === 0 && <div className="px-3 py-2 text-xs text-slate-400" data-testid="it-active-emp-none">No active employees found.</div>}
          {opts.map(e => (
            <button key={e.id} type="button" onClick={() => { onSelect(e); setQ(''); }} className={`w-full text-left px-3 py-2 text-sm hover:bg-[#063c88]/5 ${value?.id === e.id ? 'bg-[#063c88]/10' : ''}`} data-testid={`it-active-emp-opt-${e.id}`}>
              <div className="font-medium text-slate-800">{e.full_name}</div>
              <div className="text-slate-400 text-xs">{e.emp_id}{e.department ? ` · ${e.department}` : ''}{e.designation ? ` · ${e.designation}` : ''}</div>
            </button>
          ))}
        </div>
      )}
      {value && (
        <div className="mt-2 flex items-center justify-between rounded-xl bg-emerald-50 border border-emerald-200 px-3 py-2" data-testid="it-active-emp-selected">
          <div className="text-sm"><span className="font-medium text-emerald-800">{value.full_name}</span> <span className="text-emerald-600 text-xs">{value.emp_id}</span></div>
          <button type="button" onClick={() => onSelect(null)} className="text-emerald-700 hover:text-emerald-900"><X className="w-4 h-4" /></button>
        </div>
      )}
    </div>
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
      <div className="relative">
        <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
        <Input className="pl-9 rounded-xl bg-white" placeholder="Search employee by name…" value={q} onChange={e => setQ(e.target.value)} data-testid="it-emp-search" />
      </div>
      <div className="max-h-40 overflow-y-auto mt-1.5 border rounded-xl bg-white">
        {opts.map(e => (
          <button key={e.id} type="button" onClick={() => onSelect(e)} className={`w-full text-left px-3 py-1.5 text-sm hover:bg-[#063c88]/5 ${value?.id === e.id ? 'bg-[#063c88]/10' : ''}`} data-testid={`it-emp-opt-${e.id}`}>
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
      <DialogContent className="bg-[#fffdf7] rounded-2xl" data-testid="it-action-dialog">
        <DialogHeader><DialogTitle style={font}>{titles[type]} — {asset.asset_id}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          {(type === 'assign' || type === 'transfer') && <EmployeePicker authHeaders={authHeaders} value={emp} onSelect={setEmp} />}
          {type === 'return' && <>
            <div><Label>New Status</Label>
              <Select value={status} onValueChange={setStatus}><SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
                <SelectContent>{['Available', 'In Stock', 'Under Repair', 'Damaged', 'Retired'].map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>
            <div><Label>Remarks</Label><Textarea className="rounded-xl" value={remarks} onChange={e => setRemarks(e.target.value)} /></div>
          </>}
          {(type === 'assign' || type === 'return') && <div><Label>Condition</Label>
            <Select value={condition} onValueChange={setCondition}><SelectTrigger className="rounded-xl"><SelectValue placeholder="—" /></SelectTrigger>
              <SelectContent>{meta.conditions.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>}
          {type === 'archive' && <p className="text-sm text-slate-600">This soft-deletes the asset (history preserved). Continue?</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" className={OUTLINE} onClick={onClose}>Cancel</Button>
          <Button className={type === 'archive' ? 'bg-red-600 hover:bg-red-700 text-white rounded-xl' : PRIMARY} onClick={submit} disabled={busy} data-testid="it-action-confirm">{busy ? '…' : 'Confirm'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AssetDetail({ authHeaders, assetId, onClose }) {
  const [d, setD] = useState(null);
  useEffect(() => { axios.get(`${API}/it/assets/${assetId}`, { headers: authHeaders }).then(r => setD(r.data)).catch(() => {}); }, [assetId]); // eslint-disable-line
  const quick = d ? [['Assigned To', d.asset.assigned_to?.employee_name], ['Department', d.asset.department], ['Location', d.asset.location], ['Serial', d.asset.serial_number], ['Condition', d.asset.condition]] : [];
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className={DIALOG} data-testid="it-asset-detail">
        {!d ? <><DialogHeader><DialogTitle style={font}>{assetId}</DialogTitle></DialogHeader><Spinner /></> : <div className="space-y-5">
          <DialogHeader>
            <div className="flex items-start justify-between gap-3">
              <div>
                <DialogTitle style={{ ...font, color: NAVY }} className="text-xl">{d.asset.asset_id}</DialogTitle>
                <div className="text-sm text-slate-500 mt-0.5">{d.asset.category}{d.asset.brand ? ` · ${[d.asset.brand, d.asset.model].filter(Boolean).join(' ')}` : ''}</div>
              </div>
              <StatusBadge status={d.asset.status} />
            </div>
          </DialogHeader>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {quick.map(([k, v]) => (
              <div key={k} className="rounded-xl border border-slate-200/70 bg-white/60 px-3 py-2">
                <div className="text-[10px] uppercase tracking-wide text-slate-400 font-semibold">{k}</div>
                <div className="text-sm font-medium text-slate-800 truncate">{v || '—'}</div>
              </div>
            ))}
          </div>

          {Object.keys(d.asset.specs || {}).length > 0 && <div className="rounded-xl border border-slate-200/70 bg-white/60 p-4">
            <SectionTitle>Specifications</SectionTitle>
            <div className="grid grid-cols-2 gap-2 text-sm mt-2">{Object.entries(d.asset.specs).map(([k, v]) => v && <div key={k} className="flex justify-between border-b border-slate-100 py-1"><span className="text-slate-500">{k}</span><span className="font-medium">{v}</span></div>)}</div>
          </div>}

          <div className="rounded-xl border border-slate-200/70 bg-white/60 p-4">
            <SectionTitle>Components &amp; Assignment</SectionTitle>
            <div className="mt-2"><AssetComponentsSection authHeaders={authHeaders} assetId={assetId} /></div>
          </div>

          <div className="rounded-xl border border-slate-200/70 bg-white/60 p-4">
            <div className="flex items-center gap-1.5"><ClipboardList className="w-3.5 h-3.5 text-[#063c88]" /><SectionTitle>Asset Timeline</SectionTitle></div>
            <div className="space-y-2.5 mt-3" data-testid="it-history">
              {d.history.map(h => (
                <div key={h.id} className="flex gap-3 text-sm">
                  <div className="w-2 h-2 rounded-full bg-[#063c88] mt-1.5 shrink-0" />
                  <div><div className="font-medium text-slate-800">{h.action}</div><div className="text-slate-500 text-xs">{h.note}</div><div className="text-slate-400 text-xs">{h.by_name} · {new Date(h.at).toLocaleString()}</div></div>
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
    <div className={`${CARD} p-5 space-y-4`}>
      <div className="flex gap-2">
        <Button variant="outline" className={OUTLINE} onClick={template} data-testid="it-import-template"><Download className="w-4 h-4 mr-1.5" />Download Template</Button>
        <label className="inline-flex">
          <input type="file" accept=".csv,.xlsx" className="hidden" onChange={upload} data-testid="it-import-file" />
          <span className={`inline-flex items-center px-4 py-2 rounded-xl text-white text-sm cursor-pointer bg-[#063c88] hover:bg-[#052d66] shadow-sm shadow-[#063c88]/20`}><Upload className="w-4 h-4 mr-1.5" />Upload CSV / Excel</span>
        </label>
      </div>
      {busy && <Spinner />}
      {preview && <div className="space-y-3">
        <div className="flex gap-3 text-sm" data-testid="it-import-summary">
          <Badge variant="secondary">Total {preview.total}</Badge>
          <Badge className="bg-emerald-100 text-emerald-700">Valid {preview.valid}</Badge>
          <Badge variant="destructive">Errors {preview.errors}</Badge>
          <Badge className="bg-amber-100 text-amber-700">Warnings {preview.warnings}</Badge>
        </div>
        <div className="border rounded-xl max-h-96 overflow-auto">
          <Table><TableHeader><TableRow className="bg-[#063c88]/[0.04]"><TableHead>Row</TableHead><TableHead>Asset ID</TableHead><TableHead>Category</TableHead><TableHead>Status</TableHead><TableHead>Issues</TableHead></TableRow></TableHeader>
            <TableBody>{preview.rows.map(r => (
              <TableRow key={r.row} className={r.errors.length ? 'bg-red-50' : ''}>
                <TableCell>{r.row}</TableCell><TableCell>{r.data.asset_id || '(auto)'}</TableCell><TableCell>{r.data.category}</TableCell><TableCell>{r.data.status}</TableCell>
                <TableCell className="text-xs">{r.errors.map((e, i) => <div key={i} className="text-red-600">{e}</div>)}{r.warnings.map((w, i) => <div key={i} className="text-amber-600">{w}</div>)}</TableCell>
              </TableRow>
            ))}</TableBody></Table>
        </div>
        <Button className={PRIMARY} onClick={confirm} disabled={busy || preview.valid === 0} data-testid="it-import-confirm">Import {preview.valid} valid rows</Button>
      </div>}
    </div>
  );
}
