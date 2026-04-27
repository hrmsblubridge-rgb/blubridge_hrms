import { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Settings as SettingsIcon,
  Building2,
  Users,
  Briefcase,
  PartyPopper,
  Clock,
  UserPlus,
  Plus,
  Edit2,
  Trash2,
  Loader2,
  Search,
  RefreshCw,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Checkbox } from '../components/ui/checkbox';
import { Switch } from '../components/ui/switch';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const emptyDialogState = { open: false, mode: 'create', data: null };

const Settings = () => {
  const { token } = useAuth();
  const [tab, setTab] = useState('departments');
  const authHeaders = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  return (
    <div className="space-y-6 animate-fade-in" data-testid="settings-page">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
          <SettingsIcon className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>
            Settings
          </h1>
          <p className="text-sm text-slate-500">
            Centralized configuration • changes reflect across Attendance, Payroll & Reports
          </p>
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab} className="w-full">
        <TabsList className="bg-white border border-slate-200 h-auto p-1 flex flex-wrap gap-1" data-testid="settings-tabs-list">
          <TabsTrigger value="departments" data-testid="tab-departments" className="gap-2">
            <Building2 className="w-4 h-4" /> Departments
          </TabsTrigger>
          <TabsTrigger value="teams" data-testid="tab-teams" className="gap-2">
            <Users className="w-4 h-4" /> Teams
          </TabsTrigger>
          <TabsTrigger value="designations" data-testid="tab-designations" className="gap-2">
            <Briefcase className="w-4 h-4" /> Designations
          </TabsTrigger>
          <TabsTrigger value="holidays" data-testid="tab-holidays" className="gap-2">
            <PartyPopper className="w-4 h-4" /> Holidays
          </TabsTrigger>
          <TabsTrigger value="shifts" data-testid="tab-shifts" className="gap-2">
            <Clock className="w-4 h-4" /> Shifts
          </TabsTrigger>
          <TabsTrigger value="assign" data-testid="tab-assign" className="gap-2">
            <UserPlus className="w-4 h-4" /> Assign Shifts
          </TabsTrigger>
        </TabsList>

        <TabsContent value="departments" className="mt-5">
          <DepartmentsTab authHeaders={authHeaders} />
        </TabsContent>
        <TabsContent value="teams" className="mt-5">
          <TeamsTab authHeaders={authHeaders} />
        </TabsContent>
        <TabsContent value="designations" className="mt-5">
          <DesignationsTab authHeaders={authHeaders} />
        </TabsContent>
        <TabsContent value="holidays" className="mt-5">
          <HolidaysTab authHeaders={authHeaders} />
        </TabsContent>
        <TabsContent value="shifts" className="mt-5">
          <ShiftsTab authHeaders={authHeaders} />
        </TabsContent>
        <TabsContent value="assign" className="mt-5">
          <AssignShiftsTab authHeaders={authHeaders} />
        </TabsContent>
      </Tabs>
    </div>
  );
};

// ============================================================
//  Generic helpers
// ============================================================

const Card = ({ title, subtitle, action, children }) => (
  <div className="bg-white rounded-2xl border border-slate-200/80 overflow-hidden">
    <div className="flex items-center justify-between p-5 border-b border-slate-100">
      <div>
        <h3 className="text-lg font-semibold text-slate-900" style={{ fontFamily: 'Outfit' }}>
          {title}
        </h3>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
    {children}
  </div>
);

const EmptyRow = ({ cols, text = 'No records' }) => (
  <TableRow>
    <TableCell colSpan={cols} className="text-center text-sm text-slate-500 py-8">
      {text}
    </TableCell>
  </TableRow>
);

// ============================================================
//  Departments Tab
// ============================================================

const DepartmentsTab = ({ authHeaders }) => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dlg, setDlg] = useState(emptyDialogState);
  const [form, setForm] = useState({ name: '', description: '' });
  const [saving, setSaving] = useState(false);
  const [confirmDel, setConfirmDel] = useState(null);

  const fetchRows = async () => {
    try {
      setLoading(true);
      const r = await axios.get(`${API}/settings/departments`, { headers: authHeaders });
      setRows(r.data || []);
    } catch {
      toast.error('Failed to load departments');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { fetchRows(); }, []); // eslint-disable-line

  const openCreate = () => { setForm({ name: '', description: '' }); setDlg({ open: true, mode: 'create', data: null }); };
  const openEdit = (row) => { setForm({ name: row.name, description: row.description || '' }); setDlg({ open: true, mode: 'edit', data: row }); };

  const submit = async () => {
    if (!form.name.trim()) return toast.error('Name is required');
    setSaving(true);
    try {
      if (dlg.mode === 'create') {
        await axios.post(`${API}/settings/departments`, form, { headers: authHeaders });
        toast.success('Department added');
      } else {
        await axios.put(`${API}/settings/departments/${dlg.data.id}`, form, { headers: authHeaders });
        toast.success('Department updated');
      }
      setDlg(emptyDialogState);
      await fetchRows();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  const confirmDelete = async () => {
    if (!confirmDel) return;
    setSaving(true);
    try {
      await axios.delete(`${API}/settings/departments/${confirmDel.id}`, { headers: authHeaders });
      toast.success('Department deleted');
      setConfirmDel(null);
      await fetchRows();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Delete failed');
    } finally { setSaving(false); }
  };

  return (
    <>
      <Card
        title="Departments"
        subtitle={`${rows.length} departments`}
        action={
          <Button onClick={openCreate} data-testid="add-department-btn" className="bg-[#063c88] hover:bg-[#04274f]">
            <Plus className="w-4 h-4 mr-1" /> Add Department
          </Button>
        }
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Description</TableHead>
              <TableHead className="text-center">Teams</TableHead>
              <TableHead className="text-center">Employees</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && <TableRow><TableCell colSpan={5} className="text-center py-6"><Loader2 className="w-4 h-4 animate-spin inline" /></TableCell></TableRow>}
            {!loading && rows.length === 0 && <EmptyRow cols={5} />}
            {!loading && rows.map((r) => (
              <TableRow key={r.id} data-testid={`dept-row-${r.id}`}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell className="text-slate-600 text-sm">{r.description || '—'}</TableCell>
                <TableCell className="text-center">{r.team_count || 0}</TableCell>
                <TableCell className="text-center">{r.employee_count || 0}</TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="sm" onClick={() => openEdit(r)} data-testid={`edit-dept-${r.id}`}>
                    <Edit2 className="w-4 h-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setConfirmDel(r)} data-testid={`delete-dept-${r.id}`} className="text-red-600 hover:text-red-700">
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <Dialog open={dlg.open} onOpenChange={(o) => !o && setDlg(emptyDialogState)}>
        <DialogContent data-testid="department-dialog">
          <DialogHeader>
            <DialogTitle>{dlg.mode === 'create' ? 'Add Department' : 'Edit Department'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label>Name *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="department-name-input" />
            </div>
            <div>
              <Label>Description</Label>
              <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="department-desc-input" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDlg(emptyDialogState)}>Cancel</Button>
            <Button onClick={submit} disabled={saving} data-testid="save-department-btn" className="bg-[#063c88] hover:bg-[#04274f]">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!confirmDel} onOpenChange={(o) => !o && setConfirmDel(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Department</DialogTitle>
            <DialogDescription>Are you sure you want to delete <b>{confirmDel?.name}</b>?</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDel(null)}>Cancel</Button>
            <Button onClick={confirmDelete} disabled={saving} className="bg-red-600 hover:bg-red-700">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

// ============================================================
//  Teams Tab
// ============================================================

const TeamsTab = ({ authHeaders }) => {
  const [rows, setRows] = useState([]);
  const [depts, setDepts] = useState([]);
  const [deptFilter, setDeptFilter] = useState('All');
  const [loading, setLoading] = useState(true);
  const [dlg, setDlg] = useState(emptyDialogState);
  const [form, setForm] = useState({ name: '', department: '', description: '' });
  const [saving, setSaving] = useState(false);
  const [confirmDel, setConfirmDel] = useState(null);

  const fetchRows = async () => {
    try {
      setLoading(true);
      const [t, d] = await Promise.all([
        axios.get(`${API}/settings/teams`, { headers: authHeaders }),
        axios.get(`${API}/settings/departments`, { headers: authHeaders }),
      ]);
      setRows(t.data || []);
      setDepts(d.data || []);
    } catch {
      toast.error('Failed to load teams');
    } finally { setLoading(false); }
  };
  useEffect(() => { fetchRows(); }, []); // eslint-disable-line

  const filtered = rows.filter((t) => deptFilter === 'All' || t.department === deptFilter);

  const openCreate = () => { setForm({ name: '', department: depts[0]?.name || '', description: '' }); setDlg({ open: true, mode: 'create', data: null }); };
  const openEdit = (row) => { setForm({ name: row.name, department: row.department, description: row.description || '' }); setDlg({ open: true, mode: 'edit', data: row }); };

  const submit = async () => {
    if (!form.name.trim()) return toast.error('Name is required');
    if (!form.department) return toast.error('Department is required');
    setSaving(true);
    try {
      if (dlg.mode === 'create') {
        await axios.post(`${API}/settings/teams`, form, { headers: authHeaders });
        toast.success('Team added');
      } else {
        await axios.put(`${API}/settings/teams/${dlg.data.id}`, form, { headers: authHeaders });
        toast.success('Team updated');
      }
      setDlg(emptyDialogState);
      await fetchRows();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  const confirmDelete = async () => {
    if (!confirmDel) return;
    setSaving(true);
    try {
      await axios.delete(`${API}/settings/teams/${confirmDel.id}`, { headers: authHeaders });
      toast.success('Team deleted'); setConfirmDel(null); await fetchRows();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Delete failed');
    } finally { setSaving(false); }
  };

  return (
    <>
      <Card
        title="Teams"
        subtitle={`${filtered.length} of ${rows.length} teams`}
        action={
          <div className="flex items-center gap-2">
            <Select value={deptFilter} onValueChange={setDeptFilter}>
              <SelectTrigger className="w-56" data-testid="teams-dept-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All Departments</SelectItem>
                {depts.map((d) => <SelectItem key={d.id} value={d.name}>{d.name}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button onClick={openCreate} data-testid="add-team-btn" className="bg-[#063c88] hover:bg-[#04274f]">
              <Plus className="w-4 h-4 mr-1" /> Add Team
            </Button>
          </div>
        }
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Department</TableHead>
              <TableHead className="text-center">Members</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && <TableRow><TableCell colSpan={4} className="text-center py-6"><Loader2 className="w-4 h-4 animate-spin inline" /></TableCell></TableRow>}
            {!loading && filtered.length === 0 && <EmptyRow cols={4} />}
            {!loading && filtered.map((r) => (
              <TableRow key={r.id} data-testid={`team-row-${r.id}`}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell className="text-sm text-slate-600">{r.department}</TableCell>
                <TableCell className="text-center">{r.member_count || 0}</TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="sm" onClick={() => openEdit(r)} data-testid={`edit-team-${r.id}`}>
                    <Edit2 className="w-4 h-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setConfirmDel(r)} data-testid={`delete-team-${r.id}`} className="text-red-600 hover:text-red-700">
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <Dialog open={dlg.open} onOpenChange={(o) => !o && setDlg(emptyDialogState)}>
        <DialogContent data-testid="team-dialog">
          <DialogHeader>
            <DialogTitle>{dlg.mode === 'create' ? 'Add Team' : 'Edit Team'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label>Name *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="team-name-input" />
            </div>
            <div>
              <Label>Department *</Label>
              <Select value={form.department} onValueChange={(v) => setForm({ ...form, department: v })}>
                <SelectTrigger data-testid="team-dept-select"><SelectValue placeholder="Select department" /></SelectTrigger>
                <SelectContent>
                  {depts.map((d) => <SelectItem key={d.id} value={d.name}>{d.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Description</Label>
              <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDlg(emptyDialogState)}>Cancel</Button>
            <Button onClick={submit} disabled={saving} data-testid="save-team-btn" className="bg-[#063c88] hover:bg-[#04274f]">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!confirmDel} onOpenChange={(o) => !o && setConfirmDel(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Team</DialogTitle>
            <DialogDescription>Are you sure you want to delete <b>{confirmDel?.name}</b>?</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDel(null)}>Cancel</Button>
            <Button onClick={confirmDelete} disabled={saving} className="bg-red-600 hover:bg-red-700">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

// ============================================================
//  Designations Tab
// ============================================================

const DesignationsTab = ({ authHeaders }) => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dlg, setDlg] = useState(emptyDialogState);
  const [form, setForm] = useState({ name: '', description: '' });
  const [saving, setSaving] = useState(false);
  const [confirmDel, setConfirmDel] = useState(null);
  const [search, setSearch] = useState('');

  const fetchRows = async () => {
    try {
      setLoading(true);
      const r = await axios.get(`${API}/settings/designations`, { headers: authHeaders });
      setRows(r.data || []);
    } catch {
      toast.error('Failed to load designations');
    } finally { setLoading(false); }
  };
  useEffect(() => { fetchRows(); }, []); // eslint-disable-line

  const filtered = rows.filter((r) => !search || r.name.toLowerCase().includes(search.toLowerCase()));

  const openCreate = () => { setForm({ name: '', description: '' }); setDlg({ open: true, mode: 'create', data: null }); };
  const openEdit = (row) => { setForm({ name: row.name, description: row.description || '' }); setDlg({ open: true, mode: 'edit', data: row }); };

  const submit = async () => {
    if (!form.name.trim()) return toast.error('Name is required');
    setSaving(true);
    try {
      if (dlg.mode === 'create') {
        await axios.post(`${API}/settings/designations`, form, { headers: authHeaders });
        toast.success('Designation added');
      } else {
        await axios.put(`${API}/settings/designations/${dlg.data.id}`, form, { headers: authHeaders });
        toast.success('Designation updated');
      }
      setDlg(emptyDialogState);
      await fetchRows();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  const confirmDelete = async () => {
    if (!confirmDel) return;
    setSaving(true);
    try {
      await axios.delete(`${API}/settings/designations/${confirmDel.id}`, { headers: authHeaders });
      toast.success('Designation deleted'); setConfirmDel(null); await fetchRows();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Delete failed');
    } finally { setSaving(false); }
  };

  return (
    <>
      <Card
        title="Designations"
        subtitle={`${filtered.length} of ${rows.length} designations`}
        action={
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 w-64" placeholder="Search..." data-testid="designation-search" />
            </div>
            <Button onClick={openCreate} data-testid="add-designation-btn" className="bg-[#063c88] hover:bg-[#04274f]">
              <Plus className="w-4 h-4 mr-1" /> Add Designation
            </Button>
          </div>
        }
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Description</TableHead>
              <TableHead className="text-center">Employees</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && <TableRow><TableCell colSpan={4} className="text-center py-6"><Loader2 className="w-4 h-4 animate-spin inline" /></TableCell></TableRow>}
            {!loading && filtered.length === 0 && <EmptyRow cols={4} />}
            {!loading && filtered.map((r) => (
              <TableRow key={r.id} data-testid={`desig-row-${r.id}`}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell className="text-sm text-slate-600">{r.description || '—'}</TableCell>
                <TableCell className="text-center">{r.employee_count || 0}</TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="sm" onClick={() => openEdit(r)} data-testid={`edit-desig-${r.id}`}>
                    <Edit2 className="w-4 h-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setConfirmDel(r)} data-testid={`delete-desig-${r.id}`} className="text-red-600 hover:text-red-700">
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <Dialog open={dlg.open} onOpenChange={(o) => !o && setDlg(emptyDialogState)}>
        <DialogContent data-testid="designation-dialog">
          <DialogHeader>
            <DialogTitle>{dlg.mode === 'create' ? 'Add Designation' : 'Edit Designation'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label>Name *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="designation-name-input" />
            </div>
            <div>
              <Label>Description</Label>
              <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDlg(emptyDialogState)}>Cancel</Button>
            <Button onClick={submit} disabled={saving} data-testid="save-designation-btn" className="bg-[#063c88] hover:bg-[#04274f]">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!confirmDel} onOpenChange={(o) => !o && setConfirmDel(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Designation</DialogTitle>
            <DialogDescription>Are you sure you want to delete <b>{confirmDel?.name}</b>?</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDel(null)}>Cancel</Button>
            <Button onClick={confirmDelete} disabled={saving} className="bg-red-600 hover:bg-red-700">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

// ============================================================
//  Holidays Tab
// ============================================================

const HolidaysTab = ({ authHeaders }) => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dlg, setDlg] = useState(emptyDialogState);
  const [form, setForm] = useState({ name: '', holiday_date: '', type: 'company', is_paid: true, note: '' });
  const [saving, setSaving] = useState(false);
  const [confirmDel, setConfirmDel] = useState(null);
  const [year, setYear] = useState(new Date().getFullYear());

  const fetchRows = async () => {
    try {
      setLoading(true);
      const r = await axios.get(`${API}/settings/holidays?year=${year}`, { headers: authHeaders });
      setRows(r.data || []);
    } catch {
      toast.error('Failed to load holidays');
    } finally { setLoading(false); }
  };
  useEffect(() => { fetchRows(); }, [year]); // eslint-disable-line

  const openCreate = () => { setForm({ name: '', holiday_date: '', type: 'company', is_paid: true, note: '' }); setDlg({ open: true, mode: 'create', data: null }); };
  const openEdit = (row) => {
    setForm({
      name: row.name,
      holiday_date: row.date,
      type: row.type || 'company',
      is_paid: row.is_paid !== false,
      note: row.note || '',
    });
    setDlg({ open: true, mode: 'edit', data: row });
  };

  const submit = async () => {
    if (!form.name.trim() || !form.holiday_date) return toast.error('Name and date are required');
    setSaving(true);
    try {
      if (dlg.mode === 'create') {
        await axios.post(`${API}/settings/holidays`, form, { headers: authHeaders });
        toast.success('Holiday added');
      } else {
        await axios.put(`${API}/settings/holidays/${dlg.data.id}`, form, { headers: authHeaders });
        toast.success('Holiday updated');
      }
      setDlg(emptyDialogState);
      await fetchRows();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  const confirmDelete = async () => {
    if (!confirmDel) return;
    setSaving(true);
    try {
      await axios.delete(`${API}/settings/holidays/${confirmDel.id}`, { headers: authHeaders });
      toast.success('Holiday deleted'); setConfirmDel(null); await fetchRows();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Delete failed');
    } finally { setSaving(false); }
  };

  const YEAR_OPTIONS = [2024, 2025, 2026, 2027];

  return (
    <>
      <Card
        title="Holidays"
        subtitle={`${rows.length} holidays in ${year}`}
        action={
          <div className="flex items-center gap-2">
            <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
              <SelectTrigger className="w-32" data-testid="holiday-year-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                {YEAR_OPTIONS.map((y) => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button onClick={openCreate} data-testid="add-holiday-btn" className="bg-[#063c88] hover:bg-[#04274f]">
              <Plus className="w-4 h-4 mr-1" /> Add Holiday
            </Button>
          </div>
        }
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Day</TableHead>
              <TableHead>Type</TableHead>
              <TableHead className="text-center">Paid</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && <TableRow><TableCell colSpan={6} className="text-center py-6"><Loader2 className="w-4 h-4 animate-spin inline" /></TableCell></TableRow>}
            {!loading && rows.length === 0 && <EmptyRow cols={6} />}
            {!loading && rows.map((r) => (
              <TableRow key={r.id} data-testid={`holiday-row-${r.id}`}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell className="text-sm">{r.date}</TableCell>
                <TableCell className="text-sm text-slate-600">{r.day}</TableCell>
                <TableCell><Badge variant="secondary">{r.type || 'company'}</Badge></TableCell>
                <TableCell className="text-center">{r.is_paid === false ? 'No' : 'Yes'}</TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="sm" onClick={() => openEdit(r)} data-testid={`edit-holiday-${r.id}`}>
                    <Edit2 className="w-4 h-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setConfirmDel(r)} data-testid={`delete-holiday-${r.id}`} className="text-red-600 hover:text-red-700">
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <Dialog open={dlg.open} onOpenChange={(o) => !o && setDlg(emptyDialogState)}>
        <DialogContent data-testid="holiday-dialog">
          <DialogHeader>
            <DialogTitle>{dlg.mode === 'create' ? 'Add Holiday' : 'Edit Holiday'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label>Name *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="holiday-name-input" />
            </div>
            <div>
              <Label>Date *</Label>
              <Input type="date" value={form.holiday_date} onChange={(e) => setForm({ ...form, holiday_date: e.target.value })} data-testid="holiday-date-input" />
            </div>
            <div>
              <Label>Type</Label>
              <Select value={form.type} onValueChange={(v) => setForm({ ...form, type: v })}>
                <SelectTrigger data-testid="holiday-type-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="national">National</SelectItem>
                  <SelectItem value="regional">Regional</SelectItem>
                  <SelectItem value="religious">Religious</SelectItem>
                  <SelectItem value="company">Company</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between">
              <Label>Paid Holiday</Label>
              <Switch checked={form.is_paid} onCheckedChange={(v) => setForm({ ...form, is_paid: v })} data-testid="holiday-is-paid-switch" />
            </div>
            <div>
              <Label>Note</Label>
              <Textarea value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDlg(emptyDialogState)}>Cancel</Button>
            <Button onClick={submit} disabled={saving} data-testid="save-holiday-btn" className="bg-[#063c88] hover:bg-[#04274f]">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!confirmDel} onOpenChange={(o) => !o && setConfirmDel(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Holiday</DialogTitle>
            <DialogDescription>Are you sure you want to delete <b>{confirmDel?.name}</b>?</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDel(null)}>Cancel</Button>
            <Button onClick={confirmDelete} disabled={saving} className="bg-red-600 hover:bg-red-700">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

// ============================================================
//  Shifts Tab
// ============================================================

const ShiftsTab = ({ authHeaders }) => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dlg, setDlg] = useState(emptyDialogState);
  const [form, setForm] = useState({
    name: '', start_time: '10:00', total_hours: 9,
    late_grace_minutes: 0, early_out_grace_minutes: 0,
    status: 'active', description: '',
  });
  const [saving, setSaving] = useState(false);
  const [confirmDel, setConfirmDel] = useState(null);

  const fetchRows = async () => {
    try {
      setLoading(true);
      const r = await axios.get(`${API}/settings/shifts`, { headers: authHeaders });
      setRows(r.data || []);
    } catch {
      toast.error('Failed to load shifts');
    } finally { setLoading(false); }
  };
  useEffect(() => { fetchRows(); }, []); // eslint-disable-line

  const openCreate = () => {
    setForm({ name: '', start_time: '10:00', total_hours: 9, late_grace_minutes: 0, early_out_grace_minutes: 0, status: 'active', description: '' });
    setDlg({ open: true, mode: 'create', data: null });
  };
  const openEdit = (row) => {
    setForm({
      name: row.name, start_time: row.start_time, total_hours: row.total_hours,
      late_grace_minutes: row.late_grace_minutes || 0,
      early_out_grace_minutes: row.early_out_grace_minutes || 0,
      status: row.status || 'active', description: row.description || '',
    });
    setDlg({ open: true, mode: 'edit', data: row });
  };

  const submit = async () => {
    if (!form.name.trim()) return toast.error('Name is required');
    if (!form.start_time) return toast.error('Start time is required');
    if (!form.total_hours || Number(form.total_hours) <= 0) return toast.error('Total hours must be > 0');
    setSaving(true);
    try {
      const payload = {
        ...form,
        total_hours: Number(form.total_hours),
        late_grace_minutes: Number(form.late_grace_minutes || 0),
        early_out_grace_minutes: Number(form.early_out_grace_minutes || 0),
      };
      if (dlg.mode === 'create') {
        await axios.post(`${API}/settings/shifts`, payload, { headers: authHeaders });
        toast.success('Shift added');
      } else {
        await axios.put(`${API}/settings/shifts/${dlg.data.id}`, payload, { headers: authHeaders });
        toast.success('Shift updated — existing assignments recalculated');
      }
      setDlg(emptyDialogState);
      await fetchRows();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  const confirmDelete = async () => {
    if (!confirmDel) return;
    setSaving(true);
    try {
      await axios.delete(`${API}/settings/shifts/${confirmDel.id}`, { headers: authHeaders });
      toast.success('Shift deleted'); setConfirmDel(null); await fetchRows();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Delete failed');
    } finally { setSaving(false); }
  };

  return (
    <>
      <Card
        title="Shifts"
        subtitle={`${rows.length} shifts configured`}
        action={
          <Button onClick={openCreate} data-testid="add-shift-btn" className="bg-[#063c88] hover:bg-[#04274f]">
            <Plus className="w-4 h-4 mr-1" /> Add Shift
          </Button>
        }
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Start Time</TableHead>
              <TableHead>Total Hours</TableHead>
              <TableHead>Late Grace (min)</TableHead>
              <TableHead>Early-out Grace (min)</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-center">Assigned</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && <TableRow><TableCell colSpan={8} className="text-center py-6"><Loader2 className="w-4 h-4 animate-spin inline" /></TableCell></TableRow>}
            {!loading && rows.length === 0 && <EmptyRow cols={8} text="No shifts yet. Click Add Shift to create one." />}
            {!loading && rows.map((r) => (
              <TableRow key={r.id} data-testid={`shift-row-${r.id}`}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell className="font-mono text-sm">{r.start_time}</TableCell>
                <TableCell>{r.total_hours}</TableCell>
                <TableCell>{r.late_grace_minutes || 0}</TableCell>
                <TableCell>{r.early_out_grace_minutes || 0}</TableCell>
                <TableCell>
                  <Badge variant={r.status === 'active' ? 'default' : 'secondary'}>
                    {r.status || 'active'}
                  </Badge>
                </TableCell>
                <TableCell className="text-center">{r.assigned_count || 0}</TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="sm" onClick={() => openEdit(r)} data-testid={`edit-shift-${r.id}`}>
                    <Edit2 className="w-4 h-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setConfirmDel(r)} data-testid={`delete-shift-${r.id}`} className="text-red-600 hover:text-red-700">
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <Dialog open={dlg.open} onOpenChange={(o) => !o && setDlg(emptyDialogState)}>
        <DialogContent data-testid="shift-dialog">
          <DialogHeader>
            <DialogTitle>{dlg.mode === 'create' ? 'Add Shift' : 'Edit Shift'}</DialogTitle>
            <DialogDescription>
              Late-grace=0 means any minute past start time is marked LATE. Early-out uses total hours only.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label>Name *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="shift-name-input" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Start Time (HH:MM) *</Label>
                <Input type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} data-testid="shift-start-time-input" />
              </div>
              <div>
                <Label>Total Hours *</Label>
                <Input type="number" step="0.25" min="0.5" max="24"
                       value={form.total_hours}
                       onChange={(e) => setForm({ ...form, total_hours: e.target.value })}
                       data-testid="shift-total-hours-input" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Late Grace (min)</Label>
                <Input type="number" min="0" value={form.late_grace_minutes}
                       onChange={(e) => setForm({ ...form, late_grace_minutes: e.target.value })}
                       data-testid="shift-late-grace-input" />
              </div>
              <div>
                <Label>Early-out Grace (min)</Label>
                <Input type="number" min="0" value={form.early_out_grace_minutes}
                       onChange={(e) => setForm({ ...form, early_out_grace_minutes: e.target.value })}
                       data-testid="shift-early-grace-input" />
              </div>
            </div>
            <div>
              <Label>Status</Label>
              <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                <SelectTrigger data-testid="shift-status-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Description</Label>
              <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDlg(emptyDialogState)}>Cancel</Button>
            <Button onClick={submit} disabled={saving} data-testid="save-shift-btn" className="bg-[#063c88] hover:bg-[#04274f]">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!confirmDel} onOpenChange={(o) => !o && setConfirmDel(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Shift</DialogTitle>
            <DialogDescription>Are you sure you want to delete <b>{confirmDel?.name}</b>?</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDel(null)}>Cancel</Button>
            <Button onClick={confirmDelete} disabled={saving} className="bg-red-600 hover:bg-red-700">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

// ============================================================
//  Assign Shifts Tab
// ============================================================

const AssignShiftsTab = ({ authHeaders }) => {
  const [shifts, setShifts] = useState([]);
  const [depts, setDepts] = useState([]);
  const [teams, setTeams] = useState([]);
  const [desigs, setDesigs] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Assignment form
  const [shiftId, setShiftId] = useState('');
  const [effectiveFrom, setEffectiveFrom] = useState(new Date().toISOString().slice(0, 10));
  const [effectiveTo, setEffectiveTo] = useState('');
  const [filterDept, setFilterDept] = useState([]);
  const [filterTeam, setFilterTeam] = useState([]);
  const [filterDesig, setFilterDesig] = useState([]);
  const [selectedEmps, setSelectedEmps] = useState([]);
  const [empSearch, setEmpSearch] = useState('');
  const [recalcing, setRecalcing] = useState(false);

  const fetchAll = async () => {
    try {
      setLoading(true);
      const [s, d, t, dz, e, a] = await Promise.all([
        axios.get(`${API}/settings/shifts`, { headers: authHeaders }),
        axios.get(`${API}/settings/departments`, { headers: authHeaders }),
        axios.get(`${API}/settings/teams`, { headers: authHeaders }),
        axios.get(`${API}/settings/designations`, { headers: authHeaders }),
        axios.get(`${API}/employees?limit=500`, { headers: authHeaders }),
        axios.get(`${API}/settings/shifts/assignments?active_only=true`, { headers: authHeaders }),
      ]);
      setShifts(s.data || []);
      setDepts(d.data || []);
      setTeams(t.data || []);
      setDesigs(dz.data || []);
      const empList = Array.isArray(e.data) ? e.data : (e.data?.employees || []);
      setEmployees(empList);
      setAssignments(a.data || []);
    } catch {
      toast.error('Failed to load assign shifts data');
    } finally { setLoading(false); }
  };
  useEffect(() => { fetchAll(); }, []); // eslint-disable-line

  const filteredEmployees = employees.filter((e) => {
    if (filterDept.length && !filterDept.includes(e.department)) return false;
    if (filterTeam.length && !filterTeam.includes(e.team)) return false;
    if (filterDesig.length && !filterDesig.includes(e.designation)) return false;
    if (empSearch && !(e.full_name || '').toLowerCase().includes(empSearch.toLowerCase())) return false;
    return true;
  });

  const toggleEmp = (id) => setSelectedEmps((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  const toggleAll = () => {
    if (selectedEmps.length === filteredEmployees.length) setSelectedEmps([]);
    else setSelectedEmps(filteredEmployees.map((e) => e.id));
  };

  const assignSelected = async () => {
    if (!shiftId) return toast.error('Select a shift');
    if (!effectiveFrom) return toast.error('Select effective from date');
    if (selectedEmps.length === 0) return toast.error('Select at least one employee');
    setSaving(true);
    try {
      const payload = {
        employee_ids: selectedEmps, shift_id: shiftId,
        effective_from: effectiveFrom, effective_to: effectiveTo || null,
      };
      const r = await axios.post(`${API}/settings/shifts/assign`, payload, { headers: authHeaders });
      toast.success(`Shift assigned (${r.data.created} new, ${r.data.updated} updated)`);
      setSelectedEmps([]);
      await fetchAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Assignment failed');
    } finally { setSaving(false); }
  };

  const bulkAssignByFilter = async () => {
    if (!shiftId) return toast.error('Select a shift');
    if (!effectiveFrom) return toast.error('Select effective from date');
    if (!filterDept.length && !filterTeam.length && !filterDesig.length) {
      return toast.error('Pick at least one filter (department/team/designation)');
    }
    setSaving(true);
    try {
      const payload = {
        shift_id: shiftId,
        effective_from: effectiveFrom,
        effective_to: effectiveTo || null,
        departments: filterDept.length ? filterDept : null,
        teams: filterTeam.length ? filterTeam : null,
        designations: filterDesig.length ? filterDesig : null,
      };
      const r = await axios.post(`${API}/settings/shifts/bulk-assign`, payload, { headers: authHeaders });
      toast.success(`${r.data.matched} matched • ${r.data.created} new • ${r.data.updated} updated`);
      setSelectedEmps([]);
      await fetchAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Bulk assignment failed');
    } finally { setSaving(false); }
  };

  const removeAssignment = async (id) => {
    try {
      await axios.delete(`${API}/settings/shifts/assignments/${id}`, { headers: authHeaders });
      toast.success('Assignment removed');
      await fetchAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Remove failed');
    }
  };

  const recompute = async () => {
    setRecalcing(true);
    try {
      const r = await axios.post(`${API}/settings/attendance/recompute`, {}, { headers: authHeaders });
      toast.success(`Recomputed ${r.data.updated} records • skipped ${r.data.skipped_locked} locked`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Recompute failed');
    } finally { setRecalcing(false); }
  };

  const MultiChip = ({ values, options, onChange, testId }) => (
    <div className="flex flex-wrap gap-1" data-testid={testId}>
      {options.map((o) => {
        const active = values.includes(o);
        return (
          <button key={o} type="button"
            className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${active ? 'bg-[#063c88] text-white border-[#063c88]' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'}`}
            onClick={() => onChange(active ? values.filter((x) => x !== o) : [...values, o])}>
            {o}
          </button>
        );
      })}
    </div>
  );

  return (
    <div className="space-y-5">
      {/* Assignment form */}
      <Card
        title="Assign Shift"
        subtitle="Pick a shift and filter employees, then assign individually or in bulk"
        action={
          <Button onClick={recompute} disabled={recalcing} variant="outline" data-testid="recompute-btn">
            <RefreshCw className={`w-4 h-4 mr-1 ${recalcing ? 'animate-spin' : ''}`} />
            Recompute Attendance
          </Button>
        }
      >
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <Label>Shift *</Label>
              <Select value={shiftId} onValueChange={setShiftId}>
                <SelectTrigger data-testid="assign-shift-select"><SelectValue placeholder="Select shift" /></SelectTrigger>
                <SelectContent>
                  {shifts.filter((s) => s.status !== 'inactive').map((s) => (
                    <SelectItem key={s.id} value={s.id}>{s.name} ({s.start_time} • {s.total_hours}h)</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Effective From *</Label>
              <Input type="date" value={effectiveFrom} onChange={(e) => setEffectiveFrom(e.target.value)} data-testid="assign-effective-from" />
            </div>
            <div>
              <Label>Effective To (optional)</Label>
              <Input type="date" value={effectiveTo} onChange={(e) => setEffectiveTo(e.target.value)} data-testid="assign-effective-to" />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <Label className="text-xs text-slate-500">Departments</Label>
              <MultiChip testId="filter-dept-chips" values={filterDept} options={depts.map((d) => d.name)} onChange={setFilterDept} />
            </div>
            <div>
              <Label className="text-xs text-slate-500">Teams</Label>
              <MultiChip testId="filter-team-chips" values={filterTeam} options={teams.map((t) => t.name)} onChange={setFilterTeam} />
            </div>
            <div>
              <Label className="text-xs text-slate-500">Designations</Label>
              <MultiChip testId="filter-desig-chips" values={filterDesig} options={desigs.map((d) => d.name)} onChange={setFilterDesig} />
            </div>
          </div>

          <div className="flex items-center gap-2 pt-2">
            <Button onClick={bulkAssignByFilter} disabled={saving} data-testid="bulk-assign-btn" className="bg-[#063c88] hover:bg-[#04274f]">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : `Bulk Assign by Filter`}
            </Button>
            <Button onClick={assignSelected} disabled={saving || selectedEmps.length === 0} variant="outline" data-testid="assign-selected-btn">
              Assign Selected ({selectedEmps.length})
            </Button>
          </div>
        </div>
      </Card>

      {/* Employee picker */}
      <Card
        title="Employees"
        subtitle={`${filteredEmployees.length} employees match current filters`}
        action={
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input value={empSearch} onChange={(e) => setEmpSearch(e.target.value)} className="pl-9 w-56" placeholder="Search name..." data-testid="emp-search-input" />
            </div>
          </div>
        }
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <Checkbox
                  checked={filteredEmployees.length > 0 && selectedEmps.length === filteredEmployees.length}
                  onCheckedChange={toggleAll}
                  data-testid="assign-select-all"
                />
              </TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Emp ID</TableHead>
              <TableHead>Department</TableHead>
              <TableHead>Team</TableHead>
              <TableHead>Designation</TableHead>
              <TableHead>Current Shift</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && <TableRow><TableCell colSpan={7} className="text-center py-6"><Loader2 className="w-4 h-4 animate-spin inline" /></TableCell></TableRow>}
            {!loading && filteredEmployees.length === 0 && <EmptyRow cols={7} />}
            {!loading && filteredEmployees.slice(0, 200).map((e) => (
              <TableRow key={e.id} data-testid={`assign-row-${e.id}`}>
                <TableCell>
                  <Checkbox checked={selectedEmps.includes(e.id)} onCheckedChange={() => toggleEmp(e.id)} data-testid={`assign-check-${e.id}`} />
                </TableCell>
                <TableCell className="font-medium">{e.full_name}</TableCell>
                <TableCell className="text-sm text-slate-600">{e.emp_id}</TableCell>
                <TableCell className="text-sm">{e.department}</TableCell>
                <TableCell className="text-sm">{e.team}</TableCell>
                <TableCell className="text-sm">{e.designation}</TableCell>
                <TableCell className="text-sm text-slate-600">
                  {e.active_shift_name || e.shift_type || '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {filteredEmployees.length > 200 && (
          <p className="text-xs text-slate-500 p-3 text-center">Showing first 200 of {filteredEmployees.length} — narrow the filters to see more.</p>
        )}
      </Card>

      {/* Active assignments */}
      <Card title="Active Assignments" subtitle={`${assignments.length} active records`}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Employee</TableHead>
              <TableHead>Shift</TableHead>
              <TableHead>Effective From</TableHead>
              <TableHead>Effective To</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {assignments.length === 0 && <EmptyRow cols={5} text="No active assignments." />}
            {assignments.map((a) => (
              <TableRow key={a.id} data-testid={`active-assignment-${a.id}`}>
                <TableCell className="font-medium">{a.employee_name} <span className="text-xs text-slate-500">({a.emp_id})</span></TableCell>
                <TableCell>{a.shift_name} <span className="text-xs text-slate-500">({a.shift_start_time})</span></TableCell>
                <TableCell>{a.effective_from}</TableCell>
                <TableCell>{a.effective_to || '—'}</TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="sm" onClick={() => removeAssignment(a.id)} className="text-red-600 hover:text-red-700" data-testid={`remove-assignment-${a.id}`}>
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
};

export default Settings;
