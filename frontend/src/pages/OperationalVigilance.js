import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { DatePicker } from '../components/ui/date-picker';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../components/ui/dialog';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../components/ui/alert-dialog';
import {
  ShieldAlert, Download, Upload, Filter, Plus, Pencil, Trash2, X, FileSpreadsheet, Loader2,
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const today = () => new Date().toISOString().split('T')[0];

const emptyDraft = () => ({
  id: null,
  target_employee_id: '',
  date: today(),
  system_login: '',
  system_logout: '',
  total_research_hours: '',
  total_break_hours: '',
  breaks: [],
});

export default function OperationalVigilance() {
  const { getAuthHeaders } = useAuth();
  const [access, setAccess] = useState(null);
  const [meta, setMeta] = useState({ departments: [], teams: [], designations: [], employees: [] });
  const [filters, setFilters] = useState({
    fromDate: today(), toDate: today(), employeeName: '',
    department: 'All', designation: 'All', team: 'All',
  });
  const [data, setData] = useState({ mode: null, rows: [], break_labels: [], uploaders: [] });
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleteId, setDeleteId] = useState(null);

  const isAdmin = access?.is_admin;

  const loadEntries = useCallback(async (f) => {
    setLoading(true);
    try {
      const params = {
        from_date: f.fromDate, to_date: f.toDate,
        ...(f.employeeName && { employee_name: f.employeeName }),
        ...(f.department !== 'All' && { department: f.department }),
        ...(f.designation !== 'All' && { designation: f.designation }),
        ...(f.team !== 'All' && { team: f.team }),
      };
      const res = await axios.get(`${API}/vigilance/entries`, { headers: getAuthHeaders(), params });
      setData({ uploaders: [], ...res.data });
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load vigilance data');
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  useEffect(() => {
    (async () => {
      try {
        const a = await axios.get(`${API}/vigilance/access`, { headers: getAuthHeaders() });
        setAccess(a.data);
        if (a.data.has_access) {
          const m = await axios.get(`${API}/vigilance/filters-meta`, { headers: getAuthHeaders() });
          setMeta(m.data);
          loadEntries({ fromDate: today(), toDate: today(), employeeName: '', department: 'All', designation: 'All', team: 'All' });
        }
      } catch {
        setAccess({ has_access: false });
      }
    })();
  }, [getAuthHeaders, loadEntries]);

  const validRange = filters.fromDate && filters.toDate && filters.toDate >= filters.fromDate;

  const handleApplyFilter = () => {
    if (!validRange) { toast.error('Select a valid date range (To Date ≥ From Date).'); return; }
    loadEntries(filters);
  };

  const blobDownload = async (url, params, fname) => {
    const res = await axios.get(url, { headers: getAuthHeaders(), params, responseType: 'blob' });
    const blobUrl = window.URL.createObjectURL(new Blob([res.data]));
    const a = document.createElement('a');
    a.href = blobUrl; a.download = fname;
    document.body.appendChild(a); a.click(); a.remove();
    window.URL.revokeObjectURL(blobUrl);
  };

  const handleDownloadTemplate = async () => {
    if (!validRange) { toast.error('Both dates are required and To Date must be ≥ From Date.'); return; }
    setDownloading(true);
    try {
      await blobDownload(`${API}/vigilance/template`, { from_date: filters.fromDate, to_date: filters.toDate }, 'Vigilance-Template.xlsx');
      toast.success('Template downloaded');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Template download failed');
    } finally { setDownloading(false); }
  };

  const handleUpload = async (file) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.xlsx')) { toast.error('Only .xlsx files are accepted.'); return; }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await axios.post(`${API}/vigilance/upload`, fd, { headers: { ...getAuthHeaders() } });
      toast.success(`Upload complete — ${res.data.created} new, ${res.data.updated} updated`);
      loadEntries(filters);
    } catch (e) {
      const detail = e.response?.data?.detail;
      if (detail?.errors) {
        toast.error(`${detail.message} (${detail.errors.length} issue${detail.errors.length > 1 ? 's' : ''})`, {
          description: detail.errors.slice(0, 4).map(x => `Row ${x.row}: ${x.message}`).join('\n'),
          duration: 9000,
        });
      } else {
        toast.error(typeof detail === 'string' ? detail : 'Upload failed');
      }
    } finally { setUploading(false); }
  };

  const handleExport = async () => {
    try {
      await blobDownload(`${API}/vigilance/export`, {
        from_date: filters.fromDate, to_date: filters.toDate,
        ...(filters.employeeName && { employee_name: filters.employeeName }),
        ...(filters.department !== 'All' && { department: filters.department }),
        ...(filters.designation !== 'All' && { designation: filters.designation }),
        ...(filters.team !== 'All' && { team: filters.team }),
      }, 'Vigilance-Report.xlsx');
      toast.success('Export downloaded');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Export failed');
    }
  };

  const openEdit = (submission, row) => {
    setDraft({
      id: submission.id,
      target_employee_id: row.target_employee_id,
      target_employee_name: row.target_employee_name,
      date: row.date,
      system_login: submission.system_login || '',
      system_logout: submission.system_logout || '',
      total_research_hours: submission.total_research_hours || '',
      total_break_hours: submission.total_break_hours || '',
      breaks: (submission.breaks || []).map(b => ({ ...b })),
    });
  };

  const saveDraft = async () => {
    setSaving(true);
    try {
      if (draft.id) {
        await axios.put(`${API}/vigilance/entries/${draft.id}`, {
          system_login: draft.system_login, system_logout: draft.system_logout,
          total_research_hours: draft.total_research_hours, total_break_hours: draft.total_break_hours,
          breaks: draft.breaks,
        }, { headers: getAuthHeaders() });
        toast.success('Entry updated');
      } else {
        if (!draft.target_employee_id) { toast.error('Select an employee'); setSaving(false); return; }
        await axios.post(`${API}/vigilance/entries`, {
          target_employee_id: draft.target_employee_id, date: draft.date,
          system_login: draft.system_login, system_logout: draft.system_logout,
          total_research_hours: draft.total_research_hours, total_break_hours: draft.total_break_hours,
          breaks: draft.breaks,
        }, { headers: getAuthHeaders() });
        toast.success('Entry created');
      }
      setDraft(null);
      loadEntries(filters);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  const confirmDelete = async () => {
    try {
      await axios.delete(`${API}/vigilance/entries/${deleteId}`, { headers: getAuthHeaders() });
      toast.success('Entry deleted');
      setDeleteId(null);
      loadEntries(filters);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Delete failed');
    }
  };

  // ---------------- Access gate ----------------
  if (access === null) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-7 h-7 animate-spin text-slate-400" /></div>;
  }
  if (!access.has_access) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-center" data-testid="vigilance-no-access">
        <ShieldAlert className="w-14 h-14 text-amber-500 mb-4" />
        <h2 className="text-xl font-bold text-slate-800">Access Restricted</h2>
        <p className="text-slate-500 mt-2 max-w-md">The Operational Vigilance Report is available only to Admins and employees with the <span className="font-semibold">Vigilance</span> designation.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="vigilance-page">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="w-12 h-12 rounded-2xl bg-[#0b1f3b] flex items-center justify-center shrink-0">
          <ShieldAlert className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Operational Vigilance Report</h1>
          <p className="text-sm text-slate-500">{isAdmin ? 'View, compare & export all vigilance submissions (merged by employee/day).' : 'Download the template, fill your observations, upload & manage your own entries.'}</p>
        </div>
      </div>

      {/* Toolbar */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <div>
            <Label className="text-sm text-slate-600 mb-1.5 block">Employee Name</Label>
            <Input list="vig-emp-list" value={filters.employeeName} onChange={(e) => setFilters({ ...filters, employeeName: e.target.value })} placeholder="Search…" className="rounded-lg" data-testid="vig-filter-employee" />
            <datalist id="vig-emp-list">
              {meta.employees.map(e => <option key={e.id} value={e.name} />)}
            </datalist>
          </div>
          <div>
            <Label className="text-sm text-slate-600 mb-1.5 block">From Date</Label>
            <DatePicker value={filters.fromDate} onChange={(v) => setFilters({ ...filters, fromDate: v })} className="rounded-lg" data-testid="vig-filter-from" />
          </div>
          <div>
            <Label className="text-sm text-slate-600 mb-1.5 block">To Date</Label>
            <DatePicker value={filters.toDate} onChange={(v) => setFilters({ ...filters, toDate: v })} className="rounded-lg" data-testid="vig-filter-to" />
          </div>
          <div>
            <Label className="text-sm text-slate-600 mb-1.5 block">Department</Label>
            <Select value={filters.department} onValueChange={(v) => setFilters({ ...filters, department: v })}>
              <SelectTrigger className="rounded-lg" data-testid="vig-filter-department"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All</SelectItem>
                {meta.departments.map(d => <SelectItem key={d} value={d}>{d}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-sm text-slate-600 mb-1.5 block">Designation</Label>
            <Select value={filters.designation} onValueChange={(v) => setFilters({ ...filters, designation: v })}>
              <SelectTrigger className="rounded-lg" data-testid="vig-filter-designation"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All</SelectItem>
                {meta.designations.map(d => <SelectItem key={d} value={d}>{d}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-sm text-slate-600 mb-1.5 block">Team</Label>
            <Select value={filters.team} onValueChange={(v) => setFilters({ ...filters, team: v })}>
              <SelectTrigger className="rounded-lg" data-testid="vig-filter-team"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All</SelectItem>
                {meta.teams.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button onClick={handleApplyFilter} className="rounded-lg bg-[#0b1f3b] hover:bg-[#0b1f3b]/90" data-testid="vig-filter-btn">
            <Filter className="w-4 h-4 mr-2" /> Filter
          </Button>
          <Button onClick={handleDownloadTemplate} disabled={!validRange || downloading} variant="outline" className="rounded-lg" data-testid="vig-download-template-btn">
            {downloading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />} Download Sample Template
          </Button>
          <label className="inline-flex">
            <input type="file" accept=".xlsx" className="hidden" data-testid="vig-upload-input"
              onChange={(e) => { handleUpload(e.target.files[0]); e.target.value = ''; }} />
            <span className={`inline-flex items-center px-4 py-2 rounded-lg border border-slate-200 text-sm font-medium cursor-pointer hover:bg-slate-50 ${uploading ? 'opacity-60 pointer-events-none' : ''}`} data-testid="vig-upload-btn">
              {uploading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />} Upload Filled Sheet
            </span>
          </label>
          <Button onClick={() => setDraft(emptyDraft())} variant="outline" className="rounded-lg" data-testid="vig-add-entry-btn">
            <Plus className="w-4 h-4 mr-2" /> Add Entry
          </Button>
          <Button onClick={handleExport} variant="outline" className="rounded-lg ml-auto" data-testid="vig-export-btn">
            <FileSpreadsheet className="w-4 h-4 mr-2" /> Export
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-48"><Loader2 className="w-7 h-7 animate-spin text-slate-400" /></div>
        ) : data.rows.length === 0 ? (
          <div className="text-center py-16 text-slate-400" data-testid="vig-empty">No vigilance data for the selected filters. Download the template, fill it, and upload.</div>
        ) : isAdmin ? (
          <AdminMergedTable data={data} onEdit={openEdit} onDelete={setDeleteId} />
        ) : (
          <VigilanceOwnTable data={data} onEdit={openEdit} onDelete={setDeleteId} />
        )}
      </div>

      {/* Edit / Add dialog */}
      <EntryDialog
        draft={draft} setDraft={setDraft} onSave={saveDraft} saving={saving}
        employees={meta.employees}
      />

      <AlertDialog open={!!deleteId} onOpenChange={(o) => !o && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete vigilance entry?</AlertDialogTitle>
            <AlertDialogDescription>This removes only this vigilance row. Employee, attendance and other HRMS data are not affected.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} className="bg-red-600 hover:bg-red-700" data-testid="vig-confirm-delete">Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// ===================== Vigilance own-view table =====================
function VigilanceOwnTable({ data, onEdit, onDelete }) {
  const labels = data.break_labels || [];
  return (
    <div className="overflow-x-auto" data-testid="vig-own-table">
      <table className="text-sm border-collapse min-w-full">
        <thead>
          <tr className="bg-slate-100 text-slate-600">
            <th className="sticky left-0 bg-slate-100 z-20 px-3 py-3 text-left font-semibold min-w-[180px]">Name</th>
            <th className="sticky left-[180px] bg-slate-100 z-20 px-3 py-3 text-left font-semibold min-w-[120px]">Date</th>
            {['Punch-In', 'Punch-Out', 'Total Hours', 'System Login', 'System Logout', 'Research Hrs', 'Break Hrs'].map(h => (
              <th key={h} className="px-3 py-3 text-left font-semibold whitespace-nowrap">{h}</th>
            ))}
            {labels.map(l => (
              <th key={l} colSpan={3} className="px-3 py-2 text-center font-semibold border-l border-slate-200 whitespace-nowrap bg-emerald-50">{l}</th>
            ))}
            <th className="px-3 py-3 text-center font-semibold sticky right-0 bg-slate-100 z-20">Actions</th>
          </tr>
          <tr className="bg-slate-50 text-[11px] text-slate-500">
            <th className="sticky left-0 bg-slate-50 z-20" /><th className="sticky left-[180px] bg-slate-50 z-20" />
            {Array(7).fill(0).map((_, i) => <th key={i} />)}
            {labels.map(l => ['From', 'To', 'Total'].map((s, i) => (
              <th key={l + s} className={`px-2 py-1.5 text-center ${i === 0 ? 'border-l border-slate-200' : ''}`}>{s}</th>
            )))}
            <th className="sticky right-0 bg-slate-50 z-20" />
          </tr>
        </thead>
        <tbody>
          {data.rows.map(row => {
            const bmap = Object.fromEntries((row.breaks || []).map(b => [b.label, b]));
            return (
              <tr key={row.id} className="border-t border-slate-100 hover:bg-slate-50/50" data-testid="vig-own-row">
                <td className="sticky left-0 bg-white z-10 px-3 py-2.5 font-medium text-slate-800 min-w-[180px]">{row.target_employee_name}</td>
                <td className="sticky left-[180px] bg-white z-10 px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.date_display}</td>
                <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.punch_in || '—'}</td>
                <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.punch_out || '—'}</td>
                <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.total_hours || '—'}</td>
                <td className="px-3 py-2.5 text-slate-700 whitespace-nowrap">{row.system_login || '—'}</td>
                <td className="px-3 py-2.5 text-slate-700 whitespace-nowrap">{row.system_logout || '—'}</td>
                <td className="px-3 py-2.5 text-slate-700 whitespace-nowrap">{row.total_research_hours || '—'}</td>
                <td className="px-3 py-2.5 text-slate-700 whitespace-nowrap">{row.total_break_hours || '—'}</td>
                {labels.map(l => {
                  const b = bmap[l] || {};
                  return ['from', 'to', 'total'].map((k, i) => (
                    <td key={l + k} className={`px-2 py-2.5 text-center text-slate-600 whitespace-nowrap ${i === 0 ? 'border-l border-slate-100' : ''}`}>{b[k] || '—'}</td>
                  ));
                })}
                <td className="sticky right-0 bg-white z-10 px-3 py-2.5">
                  <div className="flex items-center justify-center gap-1">
                    <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => onEdit({ ...row }, row)} data-testid="vig-edit-btn"><Pencil className="w-4 h-4" /></Button>
                    <Button size="icon" variant="ghost" className="h-8 w-8 text-red-600" onClick={() => onDelete(row.id)} data-testid="vig-delete-btn"><Trash2 className="w-4 h-4" /></Button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ===================== Admin merged table =====================
function AdminMergedTable({ data, onEdit, onDelete }) {
  const labels = data.break_labels || [];
  const uploaders = data.uploaders || [];
  const perUploaderCols = 4 + labels.length * 3; // sys login/out, research, break + breaks
  return (
    <div className="overflow-x-auto" data-testid="vig-admin-table">
      <table className="text-sm border-collapse min-w-full">
        <thead>
          <tr className="bg-slate-100 text-slate-600">
            <th rowSpan={2} className="sticky left-0 bg-slate-100 z-20 px-3 py-3 text-left font-semibold min-w-[170px]">Name</th>
            <th rowSpan={2} className="sticky left-[170px] bg-slate-100 z-20 px-3 py-3 text-left font-semibold min-w-[115px]">Date</th>
            <th rowSpan={2} className="px-3 py-3 text-left font-semibold whitespace-nowrap">Team</th>
            <th rowSpan={2} className="px-3 py-3 text-left font-semibold whitespace-nowrap">Punch-In</th>
            <th rowSpan={2} className="px-3 py-3 text-left font-semibold whitespace-nowrap">Punch-Out</th>
            <th rowSpan={2} className="px-3 py-3 text-left font-semibold whitespace-nowrap">Total Hours</th>
            {uploaders.map((u, idx) => (
              <th key={u.employee_id} colSpan={perUploaderCols} className={`px-3 py-2 text-center font-semibold border-l-2 border-slate-300 whitespace-nowrap ${idx % 2 ? 'bg-indigo-50' : 'bg-amber-50'}`}>
                {u.name}
              </th>
            ))}
          </tr>
          <tr className="bg-slate-50 text-[11px] text-slate-500">
            {uploaders.map((u, idx) => (
              <FragmentCols key={u.employee_id} labels={labels} firstClass="border-l-2 border-slate-300" />
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map(row => {
            const subByUp = Object.fromEntries((row.submissions || []).map(s => [s.uploaded_by_employee_id, s]));
            return (
              <tr key={row.key} className="border-t border-slate-100 hover:bg-slate-50/50" data-testid="vig-admin-row">
                <td className="sticky left-0 bg-white z-10 px-3 py-2.5 font-medium text-slate-800 min-w-[170px]">{row.target_employee_name}</td>
                <td className="sticky left-[170px] bg-white z-10 px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.date_display}</td>
                <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.target_team || '—'}</td>
                <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.punch_in || '—'}</td>
                <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.punch_out || '—'}</td>
                <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.total_hours || '—'}</td>
                {uploaders.map((u, idx) => {
                  const s = subByUp[u.employee_id];
                  const bmap = s ? Object.fromEntries((s.breaks || []).map(b => [b.label, b])) : {};
                  return (
                    <FragmentData key={u.employee_id} s={s} bmap={bmap} labels={labels} firstClass="border-l-2 border-slate-200"
                      onEdit={() => s && onEdit(s, row)} onDelete={() => s && onDelete(s.id)} />
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function FragmentCols({ labels, firstClass }) {
  return (
    <>
      <th className={`px-2 py-1.5 text-center ${firstClass}`}>Sys In</th>
      <th className="px-2 py-1.5 text-center">Sys Out</th>
      <th className="px-2 py-1.5 text-center">Research</th>
      <th className="px-2 py-1.5 text-center">Break</th>
      {labels.map(l => ['From', 'To', 'Total'].map(s => (
        <th key={l + s} className="px-2 py-1.5 text-center whitespace-nowrap">{l.replace('Break', 'Brk')} {s}</th>
      )))}
    </>
  );
}

function FragmentData({ s, bmap, labels, firstClass, onEdit, onDelete }) {
  const cell = (v, extra = '') => <td className={`px-2 py-2.5 text-center text-slate-700 whitespace-nowrap ${extra}`}>{v || '—'}</td>;
  if (!s) {
    return (
      <>
        {cell('', firstClass)}{cell('')}{cell('')}{cell('')}
        {labels.map(l => ['from', 'to', 'total'].map(k => cell('', undefined && k)))}
      </>
    );
  }
  return (
    <>
      <td className={`px-2 py-2.5 text-center text-slate-700 whitespace-nowrap ${firstClass}`}>
        <div className="flex items-center justify-center gap-1">
          {s.system_login || '—'}
          <span className="inline-flex gap-0.5 ml-1">
            <button onClick={onEdit} className="text-slate-400 hover:text-blue-600" title="Edit" data-testid="vig-admin-edit-btn"><Pencil className="w-3.5 h-3.5" /></button>
            <button onClick={onDelete} className="text-slate-400 hover:text-red-600" title="Delete" data-testid="vig-admin-delete-btn"><Trash2 className="w-3.5 h-3.5" /></button>
          </span>
        </div>
      </td>
      {cell(s.system_logout)}{cell(s.total_research_hours)}{cell(s.total_break_hours)}
      {labels.map(l => {
        const b = bmap[l] || {};
        return ['from', 'to', 'total'].map(k => cell(b[k]));
      })}
    </>
  );
}

// ===================== Add / Edit dialog =====================
function EntryDialog({ draft, setDraft, onSave, saving, employees }) {
  if (!draft) return null;
  const isEdit = !!draft.id;
  const update = (patch) => setDraft({ ...draft, ...patch });
  const updateBreak = (i, patch) => {
    const breaks = draft.breaks.map((b, idx) => idx === i ? { ...b, ...patch } : b);
    update({ breaks });
  };
  const addBreak = () => update({ breaks: [...draft.breaks, { label: `Extra-Break${draft.breaks.length + 1}`, from: '', to: '', total: '' }] });
  const removeBreak = (i) => update({ breaks: draft.breaks.filter((_, idx) => idx !== i) });

  return (
    <Dialog open onOpenChange={(o) => !o && setDraft(null)}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="vig-entry-dialog">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Edit Vigilance Entry — ${draft.target_employee_name || ''}` : 'Add Vigilance Entry'}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {!isEdit && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-sm mb-1.5 block">Employee</Label>
                <Select value={draft.target_employee_id} onValueChange={(v) => update({ target_employee_id: v })}>
                  <SelectTrigger data-testid="vig-dialog-employee"><SelectValue placeholder="Select employee" /></SelectTrigger>
                  <SelectContent className="max-h-64">
                    {employees.map(e => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-sm mb-1.5 block">Date</Label>
                <DatePicker value={draft.date} onChange={(v) => update({ date: v })} data-testid="vig-dialog-date" />
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-sm mb-1.5 block">System Login <span className="text-slate-400">(HH:MM AM/PM)</span></Label>
              <Input value={draft.system_login} onChange={(e) => update({ system_login: e.target.value })} placeholder="09:45 AM" data-testid="vig-dialog-sys-login" /></div>
            <div><Label className="text-sm mb-1.5 block">System Logout <span className="text-slate-400">(HH:MM AM/PM)</span></Label>
              <Input value={draft.system_logout} onChange={(e) => update({ system_logout: e.target.value })} placeholder="06:30 PM" data-testid="vig-dialog-sys-logout" /></div>
            <div><Label className="text-sm mb-1.5 block">Total Research Hours <span className="text-slate-400">(HH:MM)</span></Label>
              <Input value={draft.total_research_hours} onChange={(e) => update({ total_research_hours: e.target.value })} placeholder="10:00" data-testid="vig-dialog-research" /></div>
            <div><Label className="text-sm mb-1.5 block">Total Break Hours <span className="text-slate-400">(HH:MM)</span></Label>
              <Input value={draft.total_break_hours} onChange={(e) => update({ total_break_hours: e.target.value })} placeholder="01:00" data-testid="vig-dialog-break" /></div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <Label className="text-sm font-semibold">Breaks</Label>
              <Button size="sm" variant="outline" onClick={addBreak} className="h-8" data-testid="vig-dialog-add-break"><Plus className="w-3.5 h-3.5 mr-1" /> Add Break</Button>
            </div>
            <div className="space-y-2">
              {draft.breaks.length === 0 && <p className="text-xs text-slate-400">No breaks added.</p>}
              {draft.breaks.map((b, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 items-center">
                  <Input className="col-span-4 h-9" value={b.label} onChange={(e) => updateBreak(i, { label: e.target.value })} placeholder="Break label" />
                  <Input className="col-span-3 h-9" value={b.from || ''} onChange={(e) => updateBreak(i, { from: e.target.value })} placeholder="From 11:00 AM" />
                  <Input className="col-span-2 h-9" value={b.to || ''} onChange={(e) => updateBreak(i, { to: e.target.value })} placeholder="To" />
                  <Input className="col-span-2 h-9" value={b.total || ''} onChange={(e) => updateBreak(i, { total: e.target.value })} placeholder="00:15" />
                  <button onClick={() => removeBreak(i)} className="col-span-1 text-slate-400 hover:text-red-600"><X className="w-4 h-4" /></button>
                </div>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDraft(null)}>Cancel</Button>
          <Button onClick={onSave} disabled={saving} className="bg-[#0b1f3b] hover:bg-[#0b1f3b]/90" data-testid="vig-dialog-save">
            {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null} Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
