import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
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
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../components/ui/alert-dialog';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '../components/ui/tooltip';
import {
  ShieldAlert, Download, Upload, Filter, Plus, Pencil, Trash2, X, FileSpreadsheet, Loader2,
  ChevronLeft, ChevronRight, Eye, ArrowUp, ArrowDown, ChevronsUpDown, HelpCircle, FileText, BookOpen,
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

// ---------------------------------------------------------------------------
// Reusable, type-aware header sorting (text / date / time-of-day / duration).
// Keys: base -> 'name'|'email'|'team'|'date'|'punch_in'|'punch_out'|'total_hours'
//       own vigilance -> 'system_login'|'system_logout'|'total_research_hours'|
//                         'total_break_hours'|'break:<label>:from|to|total'
//       admin per-uploader -> 'up:<uid>:<field>' | 'up:<uid>:break:<label>:from|to|total'
// ---------------------------------------------------------------------------
const TIME_FIELDS = ['punch_in', 'punch_out', 'system_login', 'system_logout', 'from', 'to'];
const DUR_FIELDS = ['total_hours', 'total_research_hours', 'total_break_hours', 'total'];
const BASE_MAP = { name: 'target_employee_name', email: 'target_email', team: 'target_team' };

const fieldOf = (key) => key.split(':').pop();
const typeOf = (key) => {
  const f = fieldOf(key);
  if (f === 'date') return 'date';
  if (TIME_FIELDS.includes(f)) return 'time';
  if (DUR_FIELDS.includes(f)) return 'duration';
  return 'text';
};

const rawValue = (row, key) => {
  if (!key) return '';
  if (key.startsWith('up:')) {
    const p = key.split(':');
    const s = (row.submissions || []).find(x => x.uploaded_by_employee_id === p[1]);
    if (!s) return '';
    if (p[2] === 'break') { const b = (s.breaks || []).find(x => x.label === p[3]); return b ? (b[p[4]] || '') : ''; }
    return s[p[2]] || '';
  }
  if (key.startsWith('break:')) {
    const p = key.split(':'); const b = (row.breaks || []).find(x => x.label === p[1]); return b ? (b[p[2]] || '') : '';
  }
  return row[BASE_MAP[key] || key] || '';
};

const timeToMin = (v) => {
  const m = String(v).trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)?$/i);
  if (!m) return null;
  let h = +m[1]; const mm = +m[2]; const ap = m[3] && m[3].toUpperCase();
  if (ap) { if (ap === 'PM' && h !== 12) h += 12; if (ap === 'AM' && h === 12) h = 0; }
  return h * 60 + mm;
};
const durToSec = (v) => {
  const m = String(v).trim().match(/^(\d{1,3}):(\d{2})(?::(\d{2}))?$/);
  if (!m) return null;
  return (+m[1]) * 3600 + (+m[2]) * 60 + (m[3] ? +m[3] : 0);
};

const sortVal = (row, key) => {
  const raw = rawValue(row, key);
  const blankRaw = raw == null || String(raw).trim() === '' || raw === '—';
  const t = typeOf(key);
  if (t === 'time') { const n = timeToMin(raw); return { blank: n == null, v: n }; }
  if (t === 'duration') { const n = durToSec(raw); return { blank: n == null, v: n }; }
  if (t === 'date') return { blank: blankRaw, v: String(raw) };
  return { blank: blankRaw, v: String(raw).toLowerCase() };
};

// Stable, blanks-last sort. Returns the original array reference when inactive.
const sortRows = (rows, sort) => {
  if (!sort.key || !sort.dir) return rows;
  const mul = sort.dir === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    const A = sortVal(a, sort.key), B = sortVal(b, sort.key);
    if (A.blank && B.blank) return 0;
    if (A.blank) return 1;
    if (B.blank) return -1;
    if (A.v < B.v) return -1 * mul;
    if (A.v > B.v) return 1 * mul;
    return 0;
  });
};

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
  const [page, setPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [sort, setSort] = useState({ key: null, dir: null });

  const isAdmin = access?.is_admin;

  // ---- Premium scroll (synced top+bottom) + sticky-header measurement ----
  const topScrollRef = useRef(null);
  const bodyScrollRef = useRef(null);
  const [scrollW, setScrollW] = useState(0);
  const [row1H, setRow1H] = useState(44);
  const syncingScroll = useRef(false);

  const onTopScroll = () => {
    if (syncingScroll.current) { syncingScroll.current = false; return; }
    syncingScroll.current = true;
    if (bodyScrollRef.current) bodyScrollRef.current.scrollLeft = topScrollRef.current.scrollLeft;
  };
  const onBodyScroll = () => {
    if (syncingScroll.current) { syncingScroll.current = false; return; }
    syncingScroll.current = true;
    if (topScrollRef.current) topScrollRef.current.scrollLeft = bodyScrollRef.current.scrollLeft;
  };

  useEffect(() => {
    const measure = () => {
      const el = bodyScrollRef.current;
      if (!el) return;
      setScrollW(el.scrollWidth);
      const h1 = el.querySelector('thead tr');
      if (h1 && h1.offsetHeight) setRow1H(h1.offsetHeight);
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (bodyScrollRef.current) ro.observe(bodyScrollRef.current);
    window.addEventListener('resize', measure);
    return () => { ro.disconnect(); window.removeEventListener('resize', measure); };
  }, [data, page, rowsPerPage, loading]);

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
      setPage(1);
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

  // 3-state header sort toggle: asc -> desc -> reset (default backend order).
  const toggleSort = (key) => {
    setSort(prev => prev.key !== key ? { key, dir: 'asc' }
      : prev.dir === 'asc' ? { key, dir: 'desc' }
      : prev.dir === 'desc' ? { key: null, dir: null }
      : { key, dir: 'asc' });
    setPage(1);
  };
  const sortedRows = useMemo(() => sortRows(data.rows, sort), [data.rows, sort]);
  const totalRows = sortedRows.length;
  const pagedRows = sortedRows.slice((page - 1) * rowsPerPage, page * rowsPerPage);

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
    if (!filters.fromDate || !filters.toDate) { toast.error('Please select both From Date and To Date'); return; }
    if (!validRange) { toast.error('To Date must be the same as or after From Date.'); return; }
    setDownloading(true);
    try {
      await blobDownload(`${API}/vigilance/template`, {
        from_date: filters.fromDate, to_date: filters.toDate,
        ...(filters.employeeName && { employee_name: filters.employeeName }),
        ...(filters.department !== 'All' && { department: filters.department }),
        ...(filters.designation !== 'All' && { designation: filters.designation }),
        ...(filters.team !== 'All' && { team: filters.team }),
      }, 'Vigilance-Template.xlsx');
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

  const handleHelp = async (format) => {
    try {
      await blobDownload(`${API}/vigilance/help`, { format },
        `Vigilance-Report-Help-Guide.${format}`);
      toast.success('Help guide downloaded');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not download help guide');
    }
  };

  const handleUserGuide = async () => {
    try {
      await blobDownload(`${API}/vigilance/user-guide`, { format: 'pdf' },
        'Vigilance_Module_User_Guide.pdf');
      toast.success('User guide downloaded');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not download user guide');
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

  const openView = (submission, row) => {
    setDraft({
      id: submission.id, readOnly: true,
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
          {!isAdmin && (
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button onClick={handleUserGuide} variant="outline"
                  className="rounded-lg border-[#0b1f3b]/30 text-[#0b1f3b] hover:bg-[#0b1f3b]/5"
                  data-testid="vig-user-guide-btn">
                  <BookOpen className="w-4 h-4 mr-2" /> Download User Guide
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                Download complete Vigilance Module user guide
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          )}
          {isAdmin && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" className="rounded-lg" data-testid="vig-help-btn">
                <HelpCircle className="w-4 h-4 mr-2" /> Help Guide
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleHelp('docx')} data-testid="vig-help-docx">
                <FileText className="w-4 h-4 mr-2 text-blue-600" /> Download as Word (.docx)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleHelp('xlsx')} data-testid="vig-help-xlsx">
                <FileSpreadsheet className="w-4 h-4 mr-2 text-emerald-600" /> Download as Excel (.xlsx)
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {/* Premium synchronized TOP horizontal scrollbar */}
        <div ref={topScrollRef} onScroll={onTopScroll}
             className="scroll-premium overflow-x-auto overflow-y-hidden border-b border-slate-100"
             style={{ height: scrollW > 0 ? 12 : 0 }} data-testid="vig-top-scroll">
          <div style={{ width: scrollW, height: 1 }} />
        </div>
        {/* Body: synchronized vertical + horizontal scroll, sticky header */}
        <div ref={bodyScrollRef} onScroll={onBodyScroll} className="overflow-auto scroll-premium"
             style={{ maxHeight: '68vh', '--vig-h1': `${row1H || 44}px` }} data-testid="vig-table-scroll">
          {isAdmin ? (
            <AdminMergedTable data={data} rows={pagedRows} loading={loading} sort={sort} onSort={toggleSort} onView={openView} onEdit={openEdit} onDelete={setDeleteId} />
          ) : (
            <VigilanceOwnTable data={data} rows={pagedRows} loading={loading} sort={sort} onSort={toggleSort} onView={openView} onEdit={openEdit} onDelete={setDeleteId} />
          )}
        </div>
        <PaginationBar page={page} setPage={setPage} rowsPerPage={rowsPerPage} setRowsPerPage={(v) => { setRowsPerPage(v); setPage(1); }} total={totalRows} />
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

// ===================== Sortable header cell =====================
function SortHeader({ label, sortKey, sort, onSort, className, align = 'left', rowSpan, colSpan }) {
  const active = sort.key === sortKey;
  const Icon = active && sort.dir === 'asc' ? ArrowUp : active && sort.dir === 'desc' ? ArrowDown : ChevronsUpDown;
  return (
    <th rowSpan={rowSpan} colSpan={colSpan} className={`${className} cursor-pointer select-none`} onClick={() => onSort(sortKey)} data-testid={`vig-sort-${sortKey}`} title="Click to sort">
      <div className={`flex items-center gap-1 ${align === 'center' ? 'justify-center' : ''}`}>
        <span>{label}</span>
        <Icon className={`w-3 h-3 shrink-0 ${active ? 'text-slate-700' : 'text-slate-300'}`} />
      </div>
    </th>
  );
}

// ===================== Vigilance own-view table =====================
function VigilanceOwnTable({ data, rows, loading, sort, onSort, onView, onEdit, onDelete }) {
  const labels = data.break_labels || [];
  const colCount = 11 + labels.length * 3 + 1;
  const scalars = [['Email-id', 'email'], ['Team', 'team'], ['Punch-In', 'punch_in'], ['Punch-Out', 'punch_out'], ['Total Hours', 'total_hours'], ['System Login', 'system_login'], ['System Logout', 'system_logout'], ['Research Hrs', 'total_research_hours'], ['Break Hrs', 'total_break_hours']];
  return (
    <table className="text-sm border-collapse min-w-full" data-testid="vig-own-table">
      <thead>
        <tr className="bg-slate-100 text-slate-600">
          <SortHeader label="Name" sortKey="name" sort={sort} onSort={onSort} className="vig-sticky-h1 left-0 z-40 bg-slate-100 px-3 py-3 text-left font-semibold min-w-[180px]" />
          <SortHeader label="Date" sortKey="date" sort={sort} onSort={onSort} className="vig-sticky-h1 left-[180px] z-40 bg-slate-100 px-3 py-3 text-left font-semibold min-w-[120px]" />
          {scalars.map(([h, k]) => (
            <SortHeader key={k} label={h} sortKey={k} sort={sort} onSort={onSort} className="vig-sticky-h1 z-30 bg-slate-100 px-3 py-3 text-left font-semibold whitespace-nowrap" />
          ))}
          {labels.map(l => (
            <th key={l} colSpan={3} className="vig-sticky-h1 z-30 px-3 py-2 text-center font-semibold border-l border-slate-200 whitespace-nowrap bg-emerald-50">{l}</th>
          ))}
          <th className="vig-sticky-h1 right-0 z-40 bg-slate-100 px-3 py-3 text-center font-semibold min-w-[130px]">Actions</th>
        </tr>
        {labels.length > 0 && (
        <tr className="bg-slate-50 text-[11px] text-slate-500">
          <th className="vig-sticky-h2 left-0 z-40 bg-slate-50" />
          <th className="vig-sticky-h2 left-[180px] z-40 bg-slate-50" />
          {scalars.map(([, k]) => <th key={k} className="vig-sticky-h2 z-30 bg-slate-50" />)}
          {labels.map(l => ['From', 'To', 'Total'].map((s, i) => (
            <SortHeader key={l + s} label={s} sortKey={`break:${l}:${s.toLowerCase()}`} sort={sort} onSort={onSort} align="center"
              className={`vig-sticky-h2 z-30 bg-slate-50 px-2 py-1.5 text-center ${i === 0 ? 'border-l border-slate-200' : ''}`} />
          )))}
          <th className="vig-sticky-h2 right-0 z-40 bg-slate-50" />
        </tr>
        )}
      </thead>
      <tbody>
        {loading ? (
          <tr><td colSpan={colCount} className="text-center py-16"><Loader2 className="w-6 h-6 animate-spin text-slate-400 inline" /></td></tr>
        ) : rows.length === 0 ? (
          <tr><td colSpan={colCount} className="text-center py-16 text-slate-400" data-testid="vig-empty">No active employees for the selected date range.</td></tr>
        ) : rows.map(row => {
          const bmap = Object.fromEntries((row.breaks || []).map(b => [b.label, b]));
          return (
            <tr key={row.key} className="border-t border-slate-100 hover:bg-slate-50/50" data-testid="vig-own-row">
              <td className="sticky left-0 bg-white z-20 px-3 py-2.5 font-medium text-slate-800 min-w-[180px]">{row.target_employee_name}</td>
              <td className="sticky left-[180px] bg-white z-20 px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.date_display}</td>
              <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.target_email || '—'}</td>
              <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.target_team || '—'}</td>
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
              <td className="sticky right-0 bg-white z-20 px-3 py-2.5 border-l border-slate-100">
                <div className="flex items-center justify-center gap-1">
                  {row.id && (
                    <Button size="icon" variant="ghost" className="h-8 w-8 text-slate-500 hover:text-slate-800" onClick={() => onView(row, row)} data-testid="vig-view-btn" title="View"><Eye className="w-4 h-4" /></Button>
                  )}
                  <Button size="icon" variant="ghost" className="h-8 w-8 text-blue-600" onClick={() => onEdit({ ...row }, row)} data-testid="vig-edit-btn" title={row.id ? 'Edit' : 'Add observation'}><Pencil className="w-4 h-4" /></Button>
                  {row.id && (
                    <Button size="icon" variant="ghost" className="h-8 w-8 text-red-600" onClick={() => onDelete(row.id)} data-testid="vig-delete-btn" title="Delete"><Trash2 className="w-4 h-4" /></Button>
                  )}
                </div>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ===================== Admin merged table =====================
function AdminMergedTable({ data, rows, loading, sort, onSort, onView, onEdit, onDelete }) {
  const labels = data.break_labels || [];
  const uploaders = data.uploaders || [];
  const perUploaderCols = 4 + labels.length * 3; // sys login/out, research, break + breaks
  const colCount = 7 + Math.max(uploaders.length, 0) * perUploaderCols + 1;
  const baseTh = 'vig-sticky-h1 z-30 bg-slate-100 px-3 py-3 text-left font-semibold whitespace-nowrap';
  const baseScalars = [['Email-id', 'email'], ['Team', 'team'], ['Punch-In', 'punch_in'], ['Punch-Out', 'punch_out'], ['Total Hours', 'total_hours']];
  return (
    <table className="text-sm border-collapse min-w-full" data-testid="vig-admin-table">
      <thead>
        <tr className="bg-slate-100 text-slate-600">
          <SortHeader label="Name" sortKey="name" sort={sort} onSort={onSort} rowSpan={2} className="vig-sticky-h1 left-0 z-40 bg-slate-100 px-3 py-3 text-left font-semibold min-w-[170px]" />
          <SortHeader label="Date" sortKey="date" sort={sort} onSort={onSort} rowSpan={2} className="vig-sticky-h1 left-[170px] z-40 bg-slate-100 px-3 py-3 text-left font-semibold min-w-[115px]" />
          {baseScalars.map(([h, k]) => (
            <SortHeader key={k} label={h} sortKey={k} sort={sort} onSort={onSort} rowSpan={2} className={baseTh} />
          ))}
          {uploaders.map((u, idx) => (
            <th key={u.employee_id} colSpan={perUploaderCols} className={`vig-sticky-h1 z-30 px-3 py-2 text-center font-semibold border-l-2 border-slate-300 whitespace-nowrap ${idx % 2 ? 'bg-indigo-50' : 'bg-amber-50'}`}>
              {u.name}
            </th>
          ))}
          <th rowSpan={2} className="vig-sticky-h1 right-0 z-40 bg-slate-100 px-3 py-3 text-center font-semibold min-w-[150px]">Actions</th>
        </tr>
        <tr className="bg-slate-50 text-[11px] text-slate-500">
          {uploaders.map((u) => (
            <FragmentCols key={u.employee_id} ukey={u.employee_id} labels={labels} sort={sort} onSort={onSort} firstClass="border-l-2 border-slate-300" />
          ))}
        </tr>
      </thead>
      <tbody>
        {loading ? (
          <tr><td colSpan={colCount} className="text-center py-16"><Loader2 className="w-6 h-6 animate-spin text-slate-400 inline" /></td></tr>
        ) : rows.length === 0 ? (
          <tr><td colSpan={colCount} className="text-center py-16 text-slate-400" data-testid="vig-empty">No active employees for the selected date range.</td></tr>
        ) : rows.map(row => {
          const subByUp = Object.fromEntries((row.submissions || []).map(s => [s.uploaded_by_employee_id, s]));
          return (
            <tr key={row.key} className="border-t border-slate-100 hover:bg-slate-50/50" data-testid="vig-admin-row">
              <td className="sticky left-0 bg-white z-20 px-3 py-2.5 font-medium text-slate-800 min-w-[170px]">{row.target_employee_name}</td>
              <td className="sticky left-[170px] bg-white z-20 px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.date_display}</td>
              <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.target_email || '—'}</td>
              <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.target_team || '—'}</td>
              <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.punch_in || '—'}</td>
              <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.punch_out || '—'}</td>
              <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{row.total_hours || '—'}</td>
              {uploaders.map((u) => {
                const s = subByUp[u.employee_id];
                const bmap = s ? Object.fromEntries((s.breaks || []).map(b => [b.label, b])) : {};
                return (
                  <FragmentData key={u.employee_id} ukey={u.employee_id} s={s} bmap={bmap} labels={labels} firstClass="border-l-2 border-slate-200" />
                );
              })}
              <td className="sticky right-0 bg-white z-20 px-2 py-2 border-l border-slate-100 min-w-[150px]" data-testid="vig-admin-actions">
                {(row.submissions || []).length === 0 ? (
                  <span className="block text-center text-slate-300">—</span>
                ) : (
                  <div className="flex flex-col gap-1.5">
                    {(row.submissions || []).map(s => (
                      <div key={s.id} className="flex items-center justify-end gap-1.5">
                        <span className="text-[10px] text-slate-400 mr-0.5 truncate max-w-[64px]" title={s.uploaded_by_name}>{s.uploaded_by_name}</span>
                        <button onClick={() => onView(s, row)} className="text-slate-400 hover:text-slate-800" title="View" data-testid="vig-admin-view-btn"><Eye className="w-3.5 h-3.5" /></button>
                        <button onClick={() => onEdit(s, row)} className="text-slate-400 hover:text-blue-600" title="Edit" data-testid="vig-admin-edit-btn"><Pencil className="w-3.5 h-3.5" /></button>
                        <button onClick={() => onDelete(s.id)} className="text-slate-400 hover:text-red-600" title="Delete" data-testid="vig-admin-delete-btn"><Trash2 className="w-3.5 h-3.5" /></button>
                      </div>
                    ))}
                  </div>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function FragmentCols({ labels, firstClass, ukey, sort, onSort }) {
  const th = 'vig-sticky-h2 z-30 bg-slate-50 px-2 py-1.5 text-center';
  const subs = [['Sys In', `up:${ukey}:system_login`], ['Sys Out', `up:${ukey}:system_logout`], ['Research', `up:${ukey}:total_research_hours`], ['Break', `up:${ukey}:total_break_hours`]];
  return (
    <>
      {subs.map(([label, key], i) => (
        <SortHeader key={key} label={label} sortKey={key} sort={sort} onSort={onSort} align="center" className={`${th} ${i === 0 ? firstClass : ''}`} />
      ))}
      {labels.map(l => ['From', 'To', 'Total'].map(s => (
        <SortHeader key={`${ukey}-${l}-${s}`} label={`${l.replace('Break', 'Brk')} ${s}`} sortKey={`up:${ukey}:break:${l}:${s.toLowerCase()}`} sort={sort} onSort={onSort} align="center" className={`${th} whitespace-nowrap`} />
      )))}
    </>
  );
}

function FragmentData({ s, bmap, labels, firstClass, ukey }) {
  const cell = (v, extra = '') => <td className={`px-2 py-2.5 text-center text-slate-700 whitespace-nowrap ${extra}`}>{v || '—'}</td>;
  if (!s) {
    return (
      <>
        {cell('', firstClass)}{cell('')}{cell('')}{cell('')}
        {labels.map(l => ['from', 'to', 'total'].map(k => (
          <td key={`${ukey}-${l}-${k}`} className="px-2 py-2.5 text-center text-slate-400 whitespace-nowrap">—</td>
        )))}
      </>
    );
  }
  return (
    <>
      {cell(s.system_login, firstClass)}{cell(s.system_logout)}{cell(s.total_research_hours)}{cell(s.total_break_hours)}
      {labels.map(l => {
        const b = bmap[l] || {};
        return ['from', 'to', 'total'].map(k => (
          <td key={`${ukey}-${l}-${k}`} className="px-2 py-2.5 text-center text-slate-700 whitespace-nowrap">{b[k] || '—'}</td>
        ));
      })}
    </>
  );
}

// ===================== Pagination bar =====================
function PaginationBar({ page, setPage, rowsPerPage, setRowsPerPage, total }) {
  const totalPages = Math.max(1, Math.ceil(total / rowsPerPage));
  const current = Math.min(page, totalPages);
  const start = total === 0 ? 0 : (current - 1) * rowsPerPage + 1;
  const end = Math.min(total, current * rowsPerPage);

  const pageNumbers = [];
  const win = 2;
  for (let p = Math.max(1, current - win); p <= Math.min(totalPages, current + win); p++) pageNumbers.push(p);

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-3 border-t border-slate-100 bg-slate-50/50" data-testid="vig-pagination">
      <div className="flex items-center gap-2 text-sm text-slate-600">
        <span>Rows per page</span>
        <Select value={String(rowsPerPage)} onValueChange={(v) => setRowsPerPage(Number(v))}>
          <SelectTrigger className="h-8 w-[78px] rounded-lg" data-testid="vig-rows-per-page"><SelectValue /></SelectTrigger>
          <SelectContent>
            {[10, 25, 50, 100].map(n => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="text-sm text-slate-500" data-testid="vig-record-count">
        Showing <span className="font-medium text-slate-700">{start.toLocaleString()}–{end.toLocaleString()}</span> of <span className="font-medium text-slate-700">{total.toLocaleString()}</span> records
      </div>
      <div className="flex items-center gap-1">
        <Button variant="outline" size="icon" className="h-8 w-8 rounded-lg" disabled={current <= 1} onClick={() => setPage(current - 1)} data-testid="vig-prev-page"><ChevronLeft className="w-4 h-4" /></Button>
        {pageNumbers[0] > 1 && <span className="px-1 text-slate-400">…</span>}
        {pageNumbers.map(p => (
          <Button key={p} variant={p === current ? 'default' : 'outline'} size="icon"
            className={`h-8 w-8 rounded-lg ${p === current ? 'bg-[#0b1f3b] hover:bg-[#0b1f3b]/90' : ''}`}
            onClick={() => setPage(p)} data-testid={`vig-page-${p}`}>{p}</Button>
        ))}
        {pageNumbers[pageNumbers.length - 1] < totalPages && <span className="px-1 text-slate-400">…</span>}
        <Button variant="outline" size="icon" className="h-8 w-8 rounded-lg" disabled={current >= totalPages} onClick={() => setPage(current + 1)} data-testid="vig-next-page"><ChevronRight className="w-4 h-4" /></Button>
      </div>
    </div>
  );
}

// ===================== Add / Edit / View dialog =====================
function EntryDialog({ draft, setDraft, onSave, saving, employees }) {
  if (!draft) return null;
  const ro = !!draft.readOnly;
  const isEdit = !!draft.id;
  const update = (patch) => setDraft({ ...draft, ...patch });
  const updateBreak = (i, patch) => {
    const breaks = draft.breaks.map((b, idx) => idx === i ? { ...b, ...patch } : b);
    update({ breaks });
  };
  const addBreak = () => update({ breaks: [...draft.breaks, { label: `Extra-Break${draft.breaks.length + 1}`, from: '', to: '', total: '' }] });
  const removeBreak = (i) => update({ breaks: draft.breaks.filter((_, idx) => idx !== i) });
  const title = ro ? `View Vigilance Entry — ${draft.target_employee_name || ''}`
    : isEdit ? `Edit Vigilance Entry — ${draft.target_employee_name || ''}` : 'Add Vigilance Entry';

  return (
    <Dialog open onOpenChange={(o) => !o && setDraft(null)}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="vig-entry-dialog">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{ro ? 'Read-only view of this vigilance entry.' : 'Record observational data. Clock times are 24h; durations accept HH:MM or HH:MM:SS.'}</DialogDescription>
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
          {ro && (
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><Label className="text-xs text-slate-500 mb-0.5 block">Employee</Label><div className="font-medium text-slate-800">{draft.target_employee_name || '—'}</div></div>
              <div><Label className="text-xs text-slate-500 mb-0.5 block">Date</Label><div className="font-medium text-slate-800">{draft.date || '—'}</div></div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-sm mb-1.5 block">System Login <span className="text-slate-400">(24h e.g. 13:45)</span></Label>
              <Input value={draft.system_login} disabled={ro} onChange={(e) => update({ system_login: e.target.value })} placeholder="13:45" data-testid="vig-dialog-sys-login" /></div>
            <div><Label className="text-sm mb-1.5 block">System Logout <span className="text-slate-400">(24h e.g. 18:30)</span></Label>
              <Input value={draft.system_logout} disabled={ro} onChange={(e) => update({ system_logout: e.target.value })} placeholder="18:30" data-testid="vig-dialog-sys-logout" /></div>
            <div><Label className="text-sm mb-1.5 block">Total Research Hours <span className="text-slate-400">(HH:MM or HH:MM:SS)</span></Label>
              <Input value={draft.total_research_hours} disabled={ro} onChange={(e) => update({ total_research_hours: e.target.value })} placeholder="10:00" data-testid="vig-dialog-research" /></div>
            <div><Label className="text-sm mb-1.5 block">Total Break Hours <span className="text-slate-400">(HH:MM or HH:MM:SS)</span></Label>
              <Input value={draft.total_break_hours} disabled={ro} onChange={(e) => update({ total_break_hours: e.target.value })} placeholder="01:00" data-testid="vig-dialog-break" /></div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <Label className="text-sm font-semibold">Breaks</Label>
              {!ro && <Button size="sm" variant="outline" onClick={addBreak} className="h-8" data-testid="vig-dialog-add-break"><Plus className="w-3.5 h-3.5 mr-1" /> Add Break</Button>}
            </div>
            <div className="space-y-2">
              {draft.breaks.length === 0 && <p className="text-xs text-slate-400">No breaks added.</p>}
              {draft.breaks.map((b, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 items-center">
                  <Input className="col-span-4 h-9" disabled={ro} value={b.label} onChange={(e) => updateBreak(i, { label: e.target.value })} placeholder="Break label" />
                  <Input className="col-span-3 h-9" disabled={ro} value={b.from || ''} onChange={(e) => updateBreak(i, { from: e.target.value })} placeholder="From 13:00" />
                  <Input className="col-span-2 h-9" disabled={ro} value={b.to || ''} onChange={(e) => updateBreak(i, { to: e.target.value })} placeholder="To 13:15" />
                  <Input className="col-span-2 h-9" disabled={ro} value={b.total || ''} onChange={(e) => updateBreak(i, { total: e.target.value })} placeholder="00:15" />
                  {!ro && <button onClick={() => removeBreak(i)} className="col-span-1 text-slate-400 hover:text-red-600"><X className="w-4 h-4" /></button>}
                </div>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDraft(null)}>{ro ? 'Close' : 'Cancel'}</Button>
          {!ro && (
            <Button onClick={onSave} disabled={saving} className="bg-[#0b1f3b] hover:bg-[#0b1f3b]/90" data-testid="vig-dialog-save">
              {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null} Save
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
