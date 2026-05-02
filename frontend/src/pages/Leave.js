import { useState, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { CalendarDays, Search, Filter, RotateCcw, Check, X, ChevronUp, ChevronDown, Eye, AlertTriangle, Clock, CheckCircle2, XCircle, Plus, Upload, Download, Pencil, Undo2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { EmployeeAutocomplete } from '../components/EmployeeAutocomplete';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../components/ui/sheet';
import { Pagination } from '../components/Pagination';
import { useTableSort, SortableTh } from '../components/useTableSort';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Leave = () => {
  const { getAuthHeaders, user } = useAuth();
  const location = useLocation();
  const [leaves, setLeaves] = useState([]);
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('requests');
  const [selectedLeave, setSelectedLeave] = useState(null);
  const [showDetailSheet, setShowDetailSheet] = useState(false);
  const [showApproveDialog, setShowApproveDialog] = useState(false);
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [lopChoice, setLopChoice] = useState('no_lop');
  const [lopRemark, setLopRemark] = useState('');
  const [showApplyDialog, setShowApplyDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editForm, setEditForm] = useState({ leave_type: 'Sick', leave_split: 'Full Day', start_date: '', end_date: '', reason: '' });
  const [employees, setEmployees] = useState([]);
  const [applyForm, setApplyForm] = useState({ employee_id: '', leave_type: 'Sick', leave_split: 'Full Day', start_date: '', end_date: '', reason: '', is_lop: null, auto_approve: false });
  const [filters, setFilters] = useState({ empName: '', team: 'All', fromDate: '', toDate: '', leaveType: 'All', status: 'All' });
  // Bulk Import state
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [importPreview, setImportPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (location.state?.tab) {
      if (location.state.tab === 'approved') { setFilters(prev => ({ ...prev, status: 'approved' })); setActiveTab('history'); }
      else if (location.state.tab === 'pending') { setFilters(prev => ({ ...prev, status: 'pending' })); setActiveTab('requests'); }
    }
  }, [location.state]);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [leavesRes, teamsRes, empRes] = await Promise.all([
        axios.get(`${API}/leaves`, { headers: getAuthHeaders() }),
        axios.get(`${API}/teams`, { headers: getAuthHeaders() }),
        axios.get(`${API}/employees/all`, { headers: getAuthHeaders() })
      ]);
      setLeaves(leavesRes.data);
      setTeams(teamsRes.data);
      setEmployees(empRes.data);
    } catch (error) {
      toast.error('Failed to load leave data');
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleFilter = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/leaves`, {
        headers: getAuthHeaders(),
        params: {
          employee_name: filters.empName || undefined,
          team: filters.team !== 'All' ? filters.team : undefined,
          from_date: filters.fromDate || undefined,
          to_date: filters.toDate || undefined,
          leave_type: filters.leaveType !== 'All' ? filters.leaveType : undefined,
          status: filters.status !== 'All' ? filters.status : undefined
        }
      });
      setLeaves(response.data);
      toast.success('Filter applied');
    } catch (error) {
      toast.error('Failed to filter');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => { setFilters({ empName: '', team: 'All', fromDate: '', toDate: '', leaveType: 'All', status: 'All' }); fetchData(); toast.info('Filters reset'); };
  const handleViewLeave = (leave) => { setSelectedLeave(leave); setShowDetailSheet(true); };
  const openApproveDialog = (leave) => { setSelectedLeave(leave); setLopChoice('no_lop'); setLopRemark(''); setShowApproveDialog(true); };
  const openRejectDialog = (leave) => { setSelectedLeave(leave); setShowRejectDialog(true); };

  const confirmApprove = async () => {
    if (!selectedLeave) return;
    setActionLoading(true);
    try {
      await axios.put(`${API}/leaves/${selectedLeave.id}/approve`, { is_lop: lopChoice === 'lop', lop_remark: lopRemark || null }, { headers: getAuthHeaders() });
      toast.success('Leave approved successfully!');
      setShowApproveDialog(false);
      setShowDetailSheet(false);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to approve leave');
    } finally {
      setActionLoading(false);
    }
  };

  const handleApplyForEmployee = async () => {
    if (!applyForm.employee_id || !applyForm.start_date || !applyForm.reason || applyForm.reason.trim().length < 10) { toast.error('Fill all fields (reason min 10 chars)'); return; }
    setActionLoading(true);
    try {
      // Single-day leave: silently mirror end_date = start_date so the
      // existing backend contract keeps working unchanged.
      const payload = { ...applyForm, end_date: applyForm.start_date };
      await axios.post(`${API}/leaves`, payload, { headers: getAuthHeaders() });
      toast.success(applyForm.auto_approve ? 'Leave applied & approved' : 'Leave applied for employee');
      setShowApplyDialog(false); setApplyForm({ employee_id: '', leave_type: 'Sick', leave_split: 'Full Day', start_date: '', end_date: '', reason: '', is_lop: null, auto_approve: false }); fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setActionLoading(false); }
  };

  const openEditLeave = (leave) => {
    setSelectedLeave(leave);
    setEditForm({
      leave_type: leave.leave_type || 'Sick',
      leave_split: leave.leave_split || 'Full Day',
      start_date: leave.start_date || '',
      end_date: leave.end_date || leave.start_date || '',
      reason: leave.reason || '',
    });
    setShowEditDialog(true);
  };

  const handleEditLeave = async () => {
    if (!selectedLeave) return;
    if (!editForm.start_date || !editForm.reason || editForm.reason.trim().length < 10) {
      toast.error('Date and reason (min 10 chars) are required');
      return;
    }
    setActionLoading(true);
    try {
      // Single-day leave — backend recomputes duration from these
      const payload = {
        leave_type: editForm.leave_type,
        leave_split: editForm.leave_split,
        start_date: editForm.start_date,
        end_date: editForm.start_date,
        reason: editForm.reason,
      };
      await axios.put(`${API}/leaves/${selectedLeave.id}`, payload, { headers: getAuthHeaders() });
      toast.success('Leave updated');
      setShowEditDialog(false); setShowDetailSheet(false); fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to update leave'); }
    finally { setActionLoading(false); }
  };

  const handleResetLeave = async (leave) => {
    // Universal Reset — flips a processed leave back to `pending` AND clears
    // any approval / LOP state. Confirms first because this reverses payroll
    // / attendance impact computed from is_lop.
    if (!leave) return;
    const ok = window.confirm(
      `Reset this ${leave.status} leave for ${leave.emp_name} back to Pending?\n\nThis clears approval, LOP, and rejection details so the request can be re-processed from scratch.`
    );
    if (!ok) return;
    try {
      await axios.post(`${API}/leaves/${leave.id}/reset`, { reason: 'manual reset' }, { headers: getAuthHeaders() });
      toast.success('Leave reset to Pending');
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to reset leave'); }
  };

  const handleDownloadImportTemplate = async () => {
    try {
      const resp = await axios.get(`${API}/leaves/import-template`, { headers: getAuthHeaders(), responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([resp.data]));
      const a = document.createElement('a');
      a.href = url; a.download = 'leaves_import_template.xlsx';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to download template');
    }
  };

  const handleBulkImportSubmit = async () => {
    if (!importFile) { toast.error('Please select a .xlsx or .csv file'); return; }
    setImportLoading(true);
    setImportResult(null);
    try {
      const fd = new FormData();
      fd.append('file', importFile);
      const resp = await axios.post(`${API}/leaves/bulk-import`, fd, { headers: { ...getAuthHeaders(), 'Content-Type': 'multipart/form-data' } });
      setImportResult(resp.data);
      if (resp.data.success > 0) toast.success(`Imported ${resp.data.success} leave(s)`);
      if (resp.data.failed > 0 || resp.data.skipped_duplicates > 0) toast.warning(`${resp.data.failed} failed, ${resp.data.skipped_duplicates} duplicate(s) skipped`);
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Import failed');
    } finally {
      setImportLoading(false);
    }
  };

  const handlePreviewFile = async (file) => {
    if (!file) { setImportPreview(null); return; }
    setPreviewLoading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const resp = await axios.post(`${API}/leaves/import/preview`, fd, { headers: { ...getAuthHeaders(), 'Content-Type': 'multipart/form-data' } });
      setImportPreview(resp.data);
    } catch (e) {
      setImportPreview(null);
      toast.error(e.response?.data?.detail || 'Failed to preview file');
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleDownloadErrorLog = () => {
    if (!importResult || !importResult.errors || importResult.errors.length === 0) return;
    const headers = ['Row', 'Email', 'Reason'];
    const rows = importResult.errors.map(e => [e.row, e.email || '', (e.reason || '').replace(/"/g, '""')]);
    const csv = [headers.join(','), ...rows.map(r => r.map(c => `"${c}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `leave-import-errors-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  const confirmReject = async () => {
    if (!selectedLeave) return;
    setActionLoading(true);
    try {
      await axios.put(`${API}/leaves/${selectedLeave.id}/reject`, {}, { headers: getAuthHeaders() });
      toast.success('Leave rejected.');
      setShowRejectDialog(false);
      setShowDetailSheet(false);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to reject leave');
    } finally {
      setActionLoading(false);
    }
  };

  const { sortedRows: sortedLeaves, sortField, sortDir: sortOrder, toggleSort: handleSort } = useTableSort(leaves, 'emp_name', 'asc');

  const pendingLeaves = sortedLeaves.filter(l => l.status === 'pending');
  const historyLeaves = sortedLeaves.filter(l => l.status !== 'pending');

  // Pagination state — independent per tab so user can browse them in parallel
  const [pendingPage, setPendingPage] = useState(1);
  const [pendingPageSize, setPendingPageSize] = useState(10);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState(10);

  // Reset to page 1 whenever filters / search change so the user always lands on results
  useEffect(() => { setPendingPage(1); setHistoryPage(1); }, [filters, sortField, sortOrder]);

  const pendingTotal = pendingLeaves.length;
  const historyTotal = historyLeaves.length;
  const pendingPaginated = pendingLeaves.slice((pendingPage - 1) * pendingPageSize, pendingPage * pendingPageSize);
  const historyPaginated = historyLeaves.slice((historyPage - 1) * historyPageSize, historyPage * historyPageSize);
  const getStatusBadge = (status) => ({ 'pending': 'badge-warning', 'approved': 'badge-success', 'rejected': 'badge-error' }[status] || 'badge-neutral');
  const canApprove = ['hr'].includes(user?.role);

  return (
    <div className="space-y-6 animate-fade-in" data-testid="leave-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
            <CalendarDays className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Leave Management</h1>
            <p className="text-sm text-slate-500">Manage employee leave requests</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => { setImportFile(null); setImportResult(null); setShowImportDialog(true); }} className="rounded-xl border-[#063c88] text-[#063c88] hover:bg-[#063c88] hover:text-white" data-testid="admin-import-leaves-btn">
            <Upload className="w-4 h-4 mr-2" /> Import Leaves
          </Button>
          <Button onClick={() => setShowApplyDialog(true)} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-xl" data-testid="admin-apply-leave-btn">
            <Plus className="w-4 h-4 mr-2" /> Apply for Employee
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Pending', value: pendingLeaves.length, icon: Clock, color: 'amber' },
          { label: 'Approved', value: leaves.filter(l => l.status === 'approved').length, icon: CheckCircle2, color: 'emerald' },
          { label: 'Rejected', value: leaves.filter(l => l.status === 'rejected').length, icon: XCircle, color: 'red' },
        ].map((stat, i) => (
          <div key={i} className="card-flat p-4 flex items-center gap-4">
            <div className={`w-10 h-10 rounded-xl bg-${stat.color}-100 flex items-center justify-center`}>
              <stat.icon className={`w-5 h-5 text-${stat.color}-600`} />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900 number-display">{stat.value}</p>
              <p className="text-xs text-slate-500">{stat.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="card-flat p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">Employee</label>
            <EmployeeAutocomplete
              value={filters.empName}
              onChange={(val) => setFilters({ ...filters, empName: val })}
              onSelect={(emp) => setFilters({ ...filters, empName: emp.full_name })}
              placeholder="Search employee..."
              data-testid="search-emp-name"
            />
          </div>
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">From</label>
            <Input type="date" value={filters.fromDate} onChange={(e) => setFilters({ ...filters, fromDate: e.target.value })} className="rounded-lg" data-testid="filter-from" />
          </div>
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">To</label>
            <Input type="date" value={filters.toDate} onChange={(e) => setFilters({ ...filters, toDate: e.target.value })} className="rounded-lg" data-testid="filter-to" />
          </div>
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">Leave Type</label>
            <Select value={filters.leaveType} onValueChange={(v) => setFilters({ ...filters, leaveType: v })}>
              <SelectTrigger className="rounded-lg" data-testid="filter-leave-type"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All</SelectItem>
                <SelectItem value="Sick">Sick</SelectItem>
                <SelectItem value="Emergency">Emergency</SelectItem>
                <SelectItem value="Preplanned">Preplanned</SelectItem>
                <SelectItem value="Optional">Optional</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">Team</label>
            <Select value={filters.team} onValueChange={(v) => setFilters({ ...filters, team: v })}>
              <SelectTrigger className="rounded-lg" data-testid="filter-team"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All</SelectItem>
                {teams.map((team) => <SelectItem key={team.id} value={team.name}>{team.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">Status</label>
            <Select value={filters.status} onValueChange={(v) => setFilters({ ...filters, status: v })}>
              <SelectTrigger className="rounded-lg" data-testid="filter-status"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="flex gap-2 mt-4">
          <Button onClick={handleFilter} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg" data-testid="filter-btn">
            <Filter className="w-4 h-4 mr-2" /> Filter
          </Button>
          <Button variant="outline" onClick={handleReset} className="rounded-lg" data-testid="reset-btn">
            <RotateCcw className="w-4 h-4 mr-2" /> Reset
          </Button>
        </div>
      </div>

      {/* Table with Tabs */}
      <div className="card-premium overflow-hidden">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <div className="border-b border-slate-100 bg-slate-50/50">
            <TabsList className="bg-transparent h-auto p-0">
              <TabsTrigger value="requests" className="px-6 py-4 rounded-none data-[state=active]:bg-[#063c88] data-[state=active]:text-white transition-all" data-testid="tab-requests">
                Leave Requests ({pendingLeaves.length})
              </TabsTrigger>
              <TabsTrigger value="history" className="px-6 py-4 rounded-none data-[state=active]:bg-[#063c88] data-[state=active]:text-white transition-all" data-testid="tab-history">
                History ({historyLeaves.length})
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="requests" className="mt-0">
            {loading ? (
              <div className="flex items-center justify-center h-64">
                <div className="w-10 h-10 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="table-premium">
                  <thead>
                    <tr>
                      <th className="w-12"></th>
                      <SortableTh field="emp_name" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Employee</SortableTh>
                      <SortableTh field="team" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Team</SortableTh>
                      <SortableTh field="leave_type" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Type</SortableTh>
                      <SortableTh field="start_date" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Date</SortableTh>
                      <SortableTh field="duration" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Duration</SortableTh>
                      <th>Reason</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingPaginated.length === 0 ? (
                      <tr><td colSpan="8" className="text-center py-12 text-slate-500">No pending requests</td></tr>
                    ) : (
                      pendingPaginated.map((leave) => (
                        <tr key={leave.id}>
                          <td>
                            <button className="p-2 hover:bg-slate-100 rounded-lg transition-colors" onClick={() => handleViewLeave(leave)} data-testid={`view-reason-${leave.id}`} title={leave.reason || ''}>
                              <Eye className="w-4 h-4 text-slate-400" />
                            </button>
                          </td>
                          <td className="font-medium text-slate-900">{leave.emp_name}</td>
                          <td className="text-slate-600">{leave.team}</td>
                          <td className="text-slate-600">{leave.leave_type}</td>
                          <td className="text-slate-600">{leave.start_date}</td>
                          <td className="text-slate-600">{leave.duration}</td>
                          <td className="text-slate-600 max-w-[220px]">
                            <div
                              className="truncate cursor-pointer"
                              title={leave.reason || '-'}
                              onClick={() => handleViewLeave(leave)}
                              data-testid={`leave-reason-preview-${leave.id}`}
                            >
                              {leave.reason ? (leave.reason.length > 60 ? leave.reason.slice(0, 60) + '…' : leave.reason) : '-'}
                            </div>
                          </td>
                          <td>
                            {canApprove && (
                              <div className="flex gap-2">
                                <Button size="sm" variant="outline" onClick={() => openEditLeave(leave)} className="border-blue-300 text-blue-700 hover:bg-blue-50 h-8 px-3 rounded-lg" data-testid={`edit-leave-${leave.id}`} title="Edit">
                                  <Pencil className="w-4 h-4" />
                                </Button>
                                <Button size="sm" onClick={() => openApproveDialog(leave)} className="bg-emerald-500 hover:bg-emerald-600 text-white h-8 px-3 rounded-lg" data-testid={`approve-btn-${leave.id}`}>
                                  <Check className="w-4 h-4" />
                                </Button>
                                <Button size="sm" onClick={() => openRejectDialog(leave)} className="bg-red-500 hover:bg-red-600 text-white h-8 px-3 rounded-lg" data-testid={`reject-btn-${leave.id}`}>
                                  <X className="w-4 h-4" />
                                </Button>
                              </div>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
                <Pagination
                  page={pendingPage}
                  pageSize={pendingPageSize}
                  total={pendingTotal}
                  onPageChange={setPendingPage}
                  onPageSizeChange={(s) => { setPendingPageSize(s); setPendingPage(1); }}
                  testid="leave-pending-pagination"
                />
              </div>
            )}
          </TabsContent>

          <TabsContent value="history" className="mt-0">
            <div className="overflow-x-auto">
              <table className="table-premium">
                <thead>
                  <tr>
                    <th className="w-12"></th>
                    <SortableTh field="emp_name" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Employee</SortableTh>
                    <SortableTh field="team" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Team</SortableTh>
                    <SortableTh field="leave_type" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Type</SortableTh>
                    <SortableTh field="start_date" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Date</SortableTh>
                    <SortableTh field="duration" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Duration</SortableTh>
                    <th>Reason</th>
                    <SortableTh field="status" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Status</SortableTh>
                    <th className="w-44">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {historyPaginated.length === 0 ? (
                    <tr><td colSpan="9" className="text-center py-12 text-slate-500">No history records</td></tr>
                  ) : (
                    historyPaginated.map((leave) => (
                      <tr key={leave.id}>
                        <td>
                          <button className="p-2 hover:bg-slate-100 rounded-lg transition-colors" onClick={() => handleViewLeave(leave)} data-testid={`history-view-reason-${leave.id}`} title={leave.reason || ''}>
                            <Eye className="w-4 h-4 text-slate-400" />
                          </button>
                        </td>
                        <td className="font-medium text-slate-900">{leave.emp_name}</td>
                        <td className="text-slate-600">{leave.team}</td>
                        <td className="text-slate-600">{leave.leave_type}</td>
                        <td className="text-slate-600">{leave.start_date}</td>
                        <td className="text-slate-600">{leave.duration}</td>
                        <td className="text-slate-600 max-w-[220px]">
                          <div
                            className="truncate cursor-pointer"
                            title={leave.reason || '-'}
                            onClick={() => handleViewLeave(leave)}
                            data-testid={`history-leave-reason-preview-${leave.id}`}
                          >
                            {leave.reason ? (leave.reason.length > 60 ? leave.reason.slice(0, 60) + '…' : leave.reason) : '-'}
                          </div>
                        </td>
                        <td><Badge className={getStatusBadge(leave.status)}>{leave.status}</Badge></td>
                        <td>
                          <div className="flex items-center gap-2">
                            {canApprove && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => openEditLeave(leave)}
                                className="border-blue-300 text-blue-700 hover:bg-blue-50 h-8 px-3 rounded-lg"
                                data-testid={`history-edit-btn-${leave.id}`}
                                title="Edit"
                              >
                                <Pencil className="w-3.5 h-3.5 mr-1" /> Edit
                              </Button>
                            )}
                            {leave.status === 'approved' ? (
                              <Button
                                size="sm"
                                onClick={() => openRejectDialog(leave)}
                                className="bg-red-500 hover:bg-red-600 text-white h-8 px-3 rounded-lg"
                                data-testid={`history-reject-btn-${leave.id}`}
                                title="Override approved → rejected"
                              >
                                <XCircle className="w-3.5 h-3.5 mr-1" /> Reject
                              </Button>
                            ) : leave.status === 'rejected' ? (
                              <Button
                                size="sm"
                                onClick={() => openApproveDialog(leave)}
                                className="bg-emerald-500 hover:bg-emerald-600 text-white h-8 px-3 rounded-lg"
                                data-testid={`history-approve-btn-${leave.id}`}
                                title="Override rejected → approved"
                              >
                                <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Approve
                              </Button>
                            ) : null}
                            {canApprove && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleResetLeave(leave)}
                                className="border-amber-300 text-amber-700 hover:bg-amber-50 h-8 px-3 rounded-lg"
                                data-testid={`history-reset-btn-${leave.id}`}
                                title="Reset to Pending — clears approval, LOP, and reprocesses from scratch"
                              >
                                <Undo2 className="w-3.5 h-3.5 mr-1" /> Reset
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              <Pagination
                page={historyPage}
                pageSize={historyPageSize}
                total={historyTotal}
                onPageChange={setHistoryPage}
                onPageSizeChange={(s) => { setHistoryPageSize(s); setHistoryPage(1); }}
                testid="leave-history-pagination"
              />
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {/* Detail Sheet */}
      <Sheet open={showDetailSheet} onOpenChange={setShowDetailSheet}>
        <SheetContent className="w-full sm:max-w-md bg-[#fffdf7] border-l border-slate-200">
          <SheetHeader>
            <SheetTitle style={{ fontFamily: 'Outfit' }}>Leave Details</SheetTitle>
          </SheetHeader>
          {selectedLeave && (
            <div className="py-6 space-y-6">
              <div className="flex items-center gap-4 pb-6 border-b border-slate-100">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#063c88] to-[#0a5cba] flex items-center justify-center shadow-lg">
                  <span className="text-white text-xl font-bold">{selectedLeave.emp_name?.charAt(0)?.toUpperCase()}</span>
                </div>
                <div>
                  <h3 className="font-semibold text-lg text-slate-900">{selectedLeave.emp_name}</h3>
                  <p className="text-sm text-slate-500">{selectedLeave.team}</p>
                </div>
              </div>
              <div className="space-y-4">
                {[
                  { label: 'Leave Type', value: selectedLeave.leave_type },
                  { label: 'Start Date', value: selectedLeave.start_date },
                  { label: 'End Date', value: selectedLeave.end_date },
                  { label: 'Duration', value: selectedLeave.duration },
                  { label: 'Status', value: selectedLeave.status, isBadge: true },
                ].map((item, i) => (
                  <div key={i} className="flex justify-between items-center py-3 border-b border-dashed border-slate-200">
                    <span className="text-slate-500 text-sm">{item.label}</span>
                    {item.isBadge ? <Badge className={getStatusBadge(selectedLeave.status)}>{selectedLeave.status}</Badge> : <span className="font-medium text-slate-900">{item.value}</span>}
                  </div>
                ))}
                {selectedLeave.reason && (
                  <div className="pt-2">
                    <span className="text-slate-500 text-sm block mb-2">Reason</span>
                    <p className="text-sm bg-slate-50 p-4 rounded-xl text-slate-700">{selectedLeave.reason}</p>
                  </div>
                )}
              </div>
              {selectedLeave.status === 'pending' && canApprove && (
                <div className="flex gap-3 pt-4">
                  <Button onClick={() => openApproveDialog(selectedLeave)} className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg">
                    <Check className="w-4 h-4 mr-2" /> Approve
                  </Button>
                  <Button onClick={() => openRejectDialog(selectedLeave)} className="flex-1 bg-red-500 hover:bg-red-600 text-white rounded-lg">
                    <X className="w-4 h-4 mr-2" /> Reject
                  </Button>
                </div>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>

      {/* Approve Dialog with LOP */}
      <Dialog open={showApproveDialog} onOpenChange={setShowApproveDialog}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Outfit' }}>
              <Check className="w-5 h-5 text-emerald-500" /> Approve Leave
            </DialogTitle>
            <DialogDescription>Confirm leave approval and set LOP status</DialogDescription>
          </DialogHeader>
          {selectedLeave && (
            <div className="py-4 space-y-4">
              <div className="space-y-2">
                <p><span className="text-slate-500">Employee:</span> <span className="font-medium">{selectedLeave.emp_name}</span></p>
                <p><span className="text-slate-500">Type:</span> <span className="font-medium">{selectedLeave.leave_type}</span></p>
                <p><span className="text-slate-500">Duration:</span> <span className="font-medium">{selectedLeave.duration}</span></p>
              </div>
              <div>
                <Label className="text-sm font-medium text-slate-700">LOP Status</Label>
                <Select value={lopChoice} onValueChange={setLopChoice}>
                  <SelectTrigger className="mt-1.5 rounded-lg" data-testid="approve-lop-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="no_lop">No LOP</SelectItem>
                    <SelectItem value="lop">LOP (Loss of Pay)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-sm font-medium text-slate-700">Remark (optional)</Label>
                <Input value={lopRemark} onChange={e => setLopRemark(e.target.value)} className="mt-1.5 rounded-lg" placeholder="Optional remark..." />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowApproveDialog(false)} disabled={actionLoading} className="rounded-lg">Cancel</Button>
            <Button onClick={confirmApprove} disabled={actionLoading} className="bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg">
              {actionLoading ? <div className="w-4 h-4 mr-2 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Check className="w-4 h-4 mr-2" />}
              Confirm Approve
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject Dialog */}
      <Dialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Outfit' }}>
              <AlertTriangle className="w-5 h-5 text-red-500" /> Reject Leave
            </DialogTitle>
            <DialogDescription>Confirm leave rejection</DialogDescription>
          </DialogHeader>
          {selectedLeave && (
            <div className="py-4 space-y-2">
              <p><span className="text-slate-500">Employee:</span> <span className="font-medium">{selectedLeave.emp_name}</span></p>
              <p><span className="text-slate-500">Type:</span> <span className="font-medium">{selectedLeave.leave_type}</span></p>
              <p><span className="text-slate-500">Duration:</span> <span className="font-medium">{selectedLeave.duration}</span></p>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRejectDialog(false)} disabled={actionLoading} className="rounded-lg">Cancel</Button>
            <Button onClick={confirmReject} disabled={actionLoading} className="bg-red-500 hover:bg-red-600 text-white rounded-lg">
              {actionLoading ? <div className="w-4 h-4 mr-2 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <X className="w-4 h-4 mr-2" />}
              Reject
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Apply Leave for Employee Dialog */}
      <Dialog open={showApplyDialog} onOpenChange={setShowApplyDialog}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl sm:max-w-lg">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Outfit' }}>Apply Leave for Employee</DialogTitle>
            <DialogDescription>Submit leave on behalf of an employee</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label>Employee</Label>
              <Select value={applyForm.employee_id} onValueChange={v => setApplyForm({ ...applyForm, employee_id: v })}>
                <SelectTrigger className="mt-1.5 rounded-lg" data-testid="admin-leave-select-employee"><SelectValue placeholder="Select employee" /></SelectTrigger>
                <SelectContent>{employees.map(e => <SelectItem key={e.id} value={e.id}>{e.full_name} ({e.team})</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div><Label>Leave Type</Label>
                <Select value={applyForm.leave_type} onValueChange={v => setApplyForm({ ...applyForm, leave_type: v })}>
                  <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Sick">Sick Leave</SelectItem>
                    <SelectItem value="Emergency">Emergency</SelectItem>
                    <SelectItem value="Preplanned">Preplanned</SelectItem>
                    <SelectItem value="Optional">Optional</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Leave Split</Label>
                <Select value={applyForm.leave_split} onValueChange={v => setApplyForm({ ...applyForm, leave_split: v })}>
                  <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Full Day">Full Day</SelectItem>
                    <SelectItem value="First Half">First Half</SelectItem>
                    <SelectItem value="Second Half">Second Half</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label>Leave Date</Label>
              <Input type="date" value={applyForm.start_date} onChange={e => setApplyForm({ ...applyForm, start_date: e.target.value })} className="mt-1.5 rounded-lg" data-testid="admin-apply-leave-date" />
            </div>
            <div><Label>Reason (min 10 chars)</Label><Textarea value={applyForm.reason} onChange={e => setApplyForm({ ...applyForm, reason: e.target.value })} className="mt-1.5 rounded-lg min-h-[80px]" placeholder="Reason for leave..." /></div>
            <div className="flex items-center gap-4 pt-2">
              <label className="flex items-center gap-2 cursor-pointer"><input type="checkbox" checked={applyForm.auto_approve} onChange={e => setApplyForm({ ...applyForm, auto_approve: e.target.checked })} className="rounded" /><span className="text-sm text-slate-700">Auto-approve & set LOP status</span></label>
              {applyForm.auto_approve && <Select value={applyForm.is_lop === true ? 'lop' : 'no_lop'} onValueChange={v => setApplyForm({ ...applyForm, is_lop: v === 'lop' })}><SelectTrigger className="w-[140px] rounded-lg"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="no_lop">No LOP</SelectItem><SelectItem value="lop">LOP</SelectItem></SelectContent></Select>}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowApplyDialog(false)} className="rounded-lg">Cancel</Button>
            <Button onClick={handleApplyForEmployee} disabled={actionLoading} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg">{actionLoading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Submit'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Import Leaves Dialog */}
      <Dialog open={showImportDialog} onOpenChange={(o) => { setShowImportDialog(o); if (!o) { setImportFile(null); setImportResult(null); setImportPreview(null); } }}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl max-w-2xl" data-testid="leave-import-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Outfit' }}>
              <Upload className="w-5 h-5 text-[#063c88]" /> Import Leaves
            </DialogTitle>
            <DialogDescription>You can upload custom sheets with additional columns. Extra data will also be stored. Required core columns: Employee Email, Leave Type, From Date, To Date.</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="flex items-center justify-between p-3 rounded-lg bg-blue-50 border border-blue-200">
              <p className="text-sm text-slate-700">Need the format? Download the sample template.</p>
              <Button size="sm" variant="outline" onClick={handleDownloadImportTemplate} className="rounded-lg border-[#063c88] text-[#063c88]" data-testid="leave-import-template-btn">
                <Download className="w-4 h-4 mr-1" /> Template
              </Button>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium">Upload File (.xlsx or .csv)</Label>
              <Input
                type="file"
                accept=".xlsx,.csv"
                onChange={(e) => {
                  const f = e.target.files?.[0] || null;
                  setImportFile(f);
                  setImportResult(null);
                  setImportPreview(null);
                  if (f) handlePreviewFile(f);
                }}
                className="rounded-lg cursor-pointer"
                data-testid="leave-import-file-input"
              />
              {importFile && <p className="text-xs text-slate-500">Selected: <span className="font-medium">{importFile.name}</span></p>}
            </div>

            {previewLoading && <p className="text-sm text-slate-500">Detecting columns…</p>}

            {importPreview && !importResult && (
              <div className="border border-slate-200 rounded-lg p-3 bg-white space-y-2" data-testid="leave-import-preview">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-slate-700">Detected columns ({importPreview.headers.length}) · {importPreview.total_rows} row(s)</p>
                  {importPreview.ready_to_import
                    ? <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200">Ready to import</Badge>
                    : <Badge className="bg-red-100 text-red-700 border-red-200">Missing required fields</Badge>}
                </div>
                {!importPreview.ready_to_import && (
                  <p className="text-xs text-red-600">Missing required fields: {importPreview.missing_required.join(', ')}</p>
                )}
                <div className="space-y-1">
                  <p className="text-xs text-slate-500 font-medium">Column mapping (sheet → system field)</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 text-xs">
                    {Object.entries(importPreview.column_mapping || {}).map(([sheetCol, dbField]) => (
                      <div key={sheetCol} className="flex items-center gap-2 px-2 py-1 rounded bg-emerald-50 border border-emerald-200">
                        <span className="font-medium text-slate-700">{sheetCol}</span>
                        <span className="text-emerald-600">→</span>
                        <span className="text-emerald-700 font-mono">{dbField}</span>
                      </div>
                    ))}
                  </div>
                </div>
                {importPreview.ignored_columns && importPreview.ignored_columns.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-xs text-amber-700 font-medium">Ignored columns (no matching field)</p>
                    <div className="flex flex-wrap gap-1">
                      {importPreview.ignored_columns.map(c => <span key={c} className="px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 text-xs">{c}</span>)}
                    </div>
                  </div>
                )}
              </div>
            )}

            {importResult && (
              <div className="space-y-3" data-testid="leave-import-result">
                <div className="grid grid-cols-4 gap-2">
                  <div className="p-3 rounded-lg bg-slate-100 text-center">
                    <p className="text-xs text-slate-500">Total</p>
                    <p className="text-lg font-bold text-slate-900" data-testid="import-total">{importResult.total}</p>
                  </div>
                  <div className="p-3 rounded-lg bg-emerald-50 text-center">
                    <p className="text-xs text-emerald-700">Success</p>
                    <p className="text-lg font-bold text-emerald-700" data-testid="import-success">{importResult.success}</p>
                  </div>
                  <div className="p-3 rounded-lg bg-amber-50 text-center">
                    <p className="text-xs text-amber-700">Duplicates</p>
                    <p className="text-lg font-bold text-amber-700" data-testid="import-duplicates">{importResult.skipped_duplicates}</p>
                  </div>
                  <div className="p-3 rounded-lg bg-red-50 text-center">
                    <p className="text-xs text-red-700">Failed</p>
                    <p className="text-lg font-bold text-red-700" data-testid="import-failed">{importResult.failed}</p>
                  </div>
                </div>

                {importResult.ignored_columns && importResult.ignored_columns.length > 0 && (
                  <div className="text-xs text-slate-600 bg-amber-50 border border-amber-200 rounded-lg p-2">
                    <span className="font-medium">Ignored sheet columns (unmapped):</span> {importResult.ignored_columns.join(', ')}
                  </div>
                )}

                {importResult.errors && importResult.errors.length > 0 && (
                  <div className="border border-slate-200 rounded-lg p-3 bg-white max-h-48 overflow-auto">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm font-medium text-slate-700">Errors / Skipped ({importResult.errors.length})</p>
                      <Button size="sm" variant="outline" onClick={handleDownloadErrorLog} className="h-7 text-xs rounded-lg" data-testid="leave-import-download-errors-btn">
                        <Download className="w-3 h-3 mr-1" /> Error log
                      </Button>
                    </div>
                    <div className="space-y-1 text-xs">
                      {importResult.errors.slice(0, 50).map((err, i) => (
                        <div key={i} className="flex gap-2 text-slate-600">
                          <span className="font-mono text-slate-400">Row {err.row}</span>
                          <span className="font-mono text-slate-500">{err.email || '—'}</span>
                          <span>{err.reason}</span>
                        </div>
                      ))}
                      {importResult.errors.length > 50 && (
                        <p className="text-slate-400 italic">…and {importResult.errors.length - 50} more (download log to see all)</p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowImportDialog(false)} className="rounded-lg" data-testid="leave-import-close-btn">Close</Button>
            <Button
              onClick={handleBulkImportSubmit}
              disabled={!importFile || importLoading || (importPreview && !importPreview.ready_to_import)}
              className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg"
              data-testid="leave-import-submit-btn"
            >
              {importLoading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : (<><Upload className="w-4 h-4 mr-1" /> Upload &amp; Import</>)}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Leave Dialog (HR) - any status */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl sm:max-w-lg" data-testid="edit-leave-dialog">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Outfit' }} className="flex items-center gap-2">
              <Pencil className="w-5 h-5 text-[#063c88]" /> Edit Leave Request
            </DialogTitle>
            <DialogDescription>Update the leave details. Approval status remains unchanged — use the Approve / Reject buttons to change it.</DialogDescription>
          </DialogHeader>
          {selectedLeave && (
            <div className="space-y-4 py-2">
              <p className="text-sm"><span className="text-slate-500">Employee:</span> <span className="font-medium">{selectedLeave.emp_name}</span> — <Badge className={getStatusBadge(selectedLeave.status)}>{selectedLeave.status}</Badge></p>
              <div className="grid grid-cols-2 gap-4">
                <div><Label>Leave Type</Label>
                  <Select value={editForm.leave_type} onValueChange={v => setEditForm({ ...editForm, leave_type: v })}>
                    <SelectTrigger className="mt-1.5 rounded-lg" data-testid="edit-leave-type"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Sick">Sick Leave</SelectItem>
                      <SelectItem value="Emergency">Emergency</SelectItem>
                      <SelectItem value="Preplanned">Preplanned</SelectItem>
                      <SelectItem value="Optional">Optional</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div><Label>Leave Split</Label>
                  <Select value={editForm.leave_split} onValueChange={v => setEditForm({ ...editForm, leave_split: v })}>
                    <SelectTrigger className="mt-1.5 rounded-lg" data-testid="edit-leave-split"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Full Day">Full Day</SelectItem>
                      <SelectItem value="First Half">First Half</SelectItem>
                      <SelectItem value="Second Half">Second Half</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label>Leave Date</Label>
                <Input type="date" value={editForm.start_date} onChange={e => setEditForm({ ...editForm, start_date: e.target.value })} className="mt-1.5 rounded-lg" data-testid="edit-leave-date" />
              </div>
              <div>
                <Label>Reason (min 10 chars)</Label>
                <Textarea value={editForm.reason} onChange={e => setEditForm({ ...editForm, reason: e.target.value })} className="mt-1.5 rounded-lg min-h-[80px]" data-testid="edit-leave-reason" />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDialog(false)} disabled={actionLoading} className="rounded-lg">Cancel</Button>
            <Button onClick={handleEditLeave} disabled={actionLoading} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg" data-testid="confirm-edit-leave">
              {actionLoading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Leave;
