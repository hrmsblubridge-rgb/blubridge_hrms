import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Clock, Check, X, Plus, Search, Filter, ChevronLeft, ChevronRight, Eye } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../components/ui/sheet';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter
} from '../components/ui/dialog';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminMissedPunch = () => {
  const { getAuthHeaders, user } = useAuth();
  const isHR = user?.role === 'hr';
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [showApply, setShowApply] = useState(false);
  const [showApprove, setShowApprove] = useState(false);
  const [showReject, setShowReject] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [formData, setFormData] = useState({ employee_id: '', date: '', punch_type: 'Check-in', check_in_time: '', check_out_time: '', reason: '', auto_approve: false });
  const [empSearch, setEmpSearch] = useState('');
  const [empDropdownOpen, setEmpDropdownOpen] = useState(false);

  // Filters
  const [filterFromDate, setFilterFromDate] = useState('');
  const [filterToDate, setFilterToDate] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterEmpName, setFilterEmpName] = useState('');

  // Pagination
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(25);
  const [total, setTotal] = useState(0);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, per_page: perPage };
      if (filterFromDate) params.from_date = filterFromDate;
      if (filterToDate) params.to_date = filterToDate;
      if (filterStatus) params.status = filterStatus;
      if (filterEmpName) params.employee_name = filterEmpName;

      const [res, empRes] = await Promise.all([
        axios.get(`${API}/missed-punches`, { headers: getAuthHeaders(), params }),
        isHR ? axios.get(`${API}/employees/all`, { headers: getAuthHeaders() }) : Promise.resolve({ data: [] })
      ]);

      // Handle both old (array) and new (paginated) response
      if (Array.isArray(res.data)) {
        setData(res.data);
        setTotal(res.data.length);
      } else {
        setData(res.data.data || []);
        setTotal(res.data.total || 0);
      }
      setEmployees(empRes.data || []);
    } catch {
      toast.error('Failed to load missed punch data');
    } finally {
      setLoading(false);
    }
  }, [page, perPage, filterFromDate, filterToDate, filterStatus, filterEmpName]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Reset to page 1 when filters change
  useEffect(() => { setPage(1); }, [filterFromDate, filterToDate, filterStatus, filterEmpName, perPage]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/missed-punches`, formData, { headers: getAuthHeaders() });
      toast.success(formData.auto_approve ? 'Applied & Approved' : 'Applied for employee');
      setShowApply(false);
      setFormData({ employee_id: '', date: '', punch_type: 'Check-in', check_in_time: '', check_out_time: '', reason: '', auto_approve: false });
      setEmpSearch('');
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to apply');
    }
  };

  const handleApprove = async () => {
    try {
      await axios.put(`${API}/missed-punches/${selected.id}/approve`, {}, { headers: getAuthHeaders() });
      toast.success('Approved! Attendance updated.');
      setShowApprove(false);
      setSelected(null);
      fetchData();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
  };

  const handleReject = async () => {
    try {
      await axios.put(`${API}/missed-punches/${selected.id}/reject`, { reason: rejectReason }, { headers: getAuthHeaders() });
      toast.success('Rejected');
      setShowReject(false);
      setSelected(null);
      setRejectReason('');
      fetchData();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
  };

  const filteredEmployees = employees.filter(e =>
    empSearch && e.full_name?.toLowerCase().includes(empSearch.toLowerCase())
  ).slice(0, 8);

  const statusColor = { pending: 'bg-amber-100 text-amber-700 border-amber-200', approved: 'bg-emerald-100 text-emerald-700 border-emerald-200', rejected: 'bg-red-100 text-red-700 border-red-200' };

  const formatTime = (val) => {
    if (!val) return '-';
    if (val.includes('T')) {
      const dt = new Date(val);
      return dt.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true });
    }
    return val;
  };

  const totalPages = Math.ceil(total / perPage) || 1;

  const pendingData = data.filter(r => r.status === 'pending');
  const historyData = data.filter(r => r.status !== 'pending');

  const renderTable = (items, showActions) => (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-50">
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-600 uppercase">Employee</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-600 uppercase">Date</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-600 uppercase">Type</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-600 uppercase">Check-in</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-600 uppercase">Check-out</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-600 uppercase">Status</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-600 uppercase">Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr><td colSpan={7} className="text-center py-8 text-slate-400">No records found</td></tr>
          ) : items.map(r => (
            <tr key={r.id} className="border-t border-slate-50 hover:bg-slate-50/50">
              <td className="px-4 py-3 font-medium text-slate-900">{r.emp_name}</td>
              <td className="px-4 py-3 text-slate-600">{r.date}</td>
              <td className="px-4 py-3"><Badge variant="outline" className="text-xs">{r.punch_type}</Badge></td>
              <td className="px-4 py-3 text-slate-600">{formatTime(r.check_in_time)}</td>
              <td className="px-4 py-3 text-slate-600">{formatTime(r.check_out_time)}</td>
              <td className="px-4 py-3"><Badge className={`${statusColor[r.status]} border text-xs`}>{r.status}</Badge></td>
              <td className="px-4 py-3">
                <Button variant="ghost" size="sm" onClick={() => setSelected(r)} className="text-xs h-7" data-testid={`view-${r.id}`}>
                  <Eye className="w-3.5 h-3.5 mr-1" /> View
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in" data-testid="admin-missed-punch-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
            <Clock className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Missed Punch Management</h1>
            <p className="text-sm text-slate-500">Manage missed punch requests</p>
          </div>
        </div>
        {isHR && <Button onClick={() => setShowApply(true)} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-xl" data-testid="admin-apply-missed-punch-btn"><Plus className="w-4 h-4 mr-2" /> Apply for Employee</Button>}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm" data-testid="missed-punch-filters">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-slate-500" />
          <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">Filters</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="text-xs text-slate-500 mb-1 block">From Date</label>
            <Input type="date" value={filterFromDate} onChange={e => setFilterFromDate(e.target.value)} className="h-9 bg-slate-50 rounded-xl text-sm" data-testid="filter-from-date" />
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">To Date</label>
            <Input type="date" value={filterToDate} onChange={e => setFilterToDate(e.target.value)} className="h-9 bg-slate-50 rounded-xl text-sm" data-testid="filter-to-date" />
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Status</label>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="h-9 bg-slate-50 rounded-xl text-sm" data-testid="filter-status">
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all_status">All</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Employee</label>
            <Input value={filterEmpName} onChange={e => setFilterEmpName(e.target.value)} placeholder="Search employee..." className="h-9 bg-slate-50 rounded-xl text-sm" data-testid="filter-employee" />
          </div>
        </div>
        {(filterFromDate || filterToDate || filterStatus || filterEmpName) && (
          <Button variant="ghost" size="sm" className="mt-2 text-xs h-7 text-slate-500" onClick={() => { setFilterFromDate(''); setFilterToDate(''); setFilterStatus(''); setFilterEmpName(''); }} data-testid="clear-filters">
            Clear Filters
          </Button>
        )}
      </div>

      {/* Data Table with Tabs */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        <Tabs defaultValue="requests" className="w-full">
          <div className="border-b border-slate-100 px-4">
            <TabsList className="bg-transparent h-12">
              <TabsTrigger value="requests" className="text-sm data-[state=active]:border-b-2 data-[state=active]:border-[#063c88]" data-testid="tab-requests">Pending ({pendingData.length})</TabsTrigger>
              <TabsTrigger value="history" className="text-sm data-[state=active]:border-b-2 data-[state=active]:border-[#063c88]" data-testid="tab-history">History ({historyData.length})</TabsTrigger>
            </TabsList>
          </div>
          <TabsContent value="requests" className="mt-0">{loading ? <div className="flex items-center justify-center h-48"><div className="w-10 h-10 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" /></div> : renderTable(pendingData, isHR)}</TabsContent>
          <TabsContent value="history" className="mt-0">{loading ? <div className="flex items-center justify-center h-48"><div className="w-10 h-10 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" /></div> : renderTable(historyData, false)}</TabsContent>
        </Tabs>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-1" data-testid="pagination-controls">
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">Total: {total} records</span>
          <Select value={String(perPage)} onValueChange={v => setPerPage(Number(v))}>
            <SelectTrigger className="h-8 w-24 text-xs bg-white border-slate-200 rounded-lg" data-testid="per-page-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="10">10 / page</SelectItem>
              <SelectItem value="25">25 / page</SelectItem>
              <SelectItem value="50">50 / page</SelectItem>
              <SelectItem value="100">100 / page</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1} className="h-8 w-8 p-0" data-testid="prev-page">
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="text-xs text-slate-600 px-2">Page {page} of {totalPages}</span>
          <Button variant="outline" size="sm" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="h-8 w-8 p-0" data-testid="next-page">
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Detail Sheet */}
      <Sheet open={!!selected} onOpenChange={(open) => { if (!open) setSelected(null); }}>
        <SheetContent className="sm:max-w-md overflow-y-auto" data-testid="missed-punch-detail">
          {selected && (
            <>
              <SheetHeader>
                <SheetTitle>Missed Punch Details</SheetTitle>
              </SheetHeader>
              <div className="mt-6 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div><p className="text-xs text-slate-500">Employee</p><p className="text-sm font-medium">{selected.emp_name}</p></div>
                  <div><p className="text-xs text-slate-500">Date</p><p className="text-sm font-medium">{selected.date}</p></div>
                  <div><p className="text-xs text-slate-500">Punch Type</p><p className="text-sm font-medium">{selected.punch_type}</p></div>
                  <div><p className="text-xs text-slate-500">Status</p><Badge className={`${statusColor[selected.status]} border text-xs`}>{selected.status}</Badge></div>
                  {selected.check_in_time && <div><p className="text-xs text-slate-500">Check-in</p><p className="text-sm font-medium">{formatTime(selected.check_in_time)}</p></div>}
                  {selected.check_out_time && <div><p className="text-xs text-slate-500">Check-out</p><p className="text-sm font-medium">{formatTime(selected.check_out_time)}</p></div>}
                </div>
                <div><p className="text-xs text-slate-500">Reason</p><p className="text-sm bg-slate-50 p-3 rounded-xl">{selected.reason}</p></div>
              </div>
            {selected.status === 'pending' && isHR && <div className="flex gap-3 pt-4">
              <Button onClick={() => setShowApprove(true)} className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg" data-testid="approve-btn"><Check className="w-4 h-4 mr-2" /> Approve</Button>
              <Button onClick={() => setShowReject(true)} className="flex-1 bg-red-500 hover:bg-red-600 text-white rounded-lg" data-testid="reject-btn"><X className="w-4 h-4 mr-2" /> Reject</Button>
            </div>}
            </>
          )}
        </SheetContent>
      </Sheet>

      {/* Apply Dialog - JOB 1: Datetime pickers */}
      <Dialog open={showApply} onOpenChange={setShowApply}>
        <DialogContent className="sm:max-w-lg" data-testid="apply-missed-punch-dialog">
          <DialogHeader><DialogTitle>Apply Missed Punch</DialogTitle></DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Employee autocomplete */}
            <div className="relative">
              <label className="text-xs font-medium text-slate-700 mb-1 block">Employee</label>
              <Input
                value={empSearch}
                onChange={e => { setEmpSearch(e.target.value); setEmpDropdownOpen(true); }}
                onFocus={() => empSearch && setEmpDropdownOpen(true)}
                placeholder="Search employee..."
                className="bg-slate-50 rounded-xl"
                data-testid="emp-search-input"
              />
              {empDropdownOpen && filteredEmployees.length > 0 && (
                <div className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-xl shadow-lg max-h-48 overflow-y-auto">
                  {filteredEmployees.map(emp => (
                    <button key={emp.id} type="button" onClick={() => { setFormData(f => ({ ...f, employee_id: emp.id })); setEmpSearch(emp.full_name); setEmpDropdownOpen(false); }} className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 border-b border-slate-50 last:border-0" data-testid={`emp-option-${emp.id}`}>
                      <span className="font-medium">{emp.full_name}</span>
                      <span className="text-xs text-slate-400 ml-2">{emp.department}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1 block">Date</label>
              <Input type="date" value={formData.date} onChange={e => setFormData(f => ({ ...f, date: e.target.value }))} required className="bg-slate-50 rounded-xl" data-testid="missed-date" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1 block">Punch Type</label>
              <Select value={formData.punch_type} onValueChange={v => setFormData(f => ({ ...f, punch_type: v }))}>
                <SelectTrigger className="bg-slate-50 rounded-xl" data-testid="missed-punch-type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Check-in">Check-in</SelectItem>
                  <SelectItem value="Check-out">Check-out</SelectItem>
                  <SelectItem value="Both">Both</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {(formData.punch_type === 'Check-in' || formData.punch_type === 'Both') && (
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1 block">Check-in Date & Time</label>
                <Input type="datetime-local" value={formData.check_in_time} onChange={e => setFormData(f => ({ ...f, check_in_time: e.target.value }))} required className="bg-slate-50 rounded-xl" data-testid="check-in-datetime" />
              </div>
            )}
            {(formData.punch_type === 'Check-out' || formData.punch_type === 'Both') && (
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1 block">Check-out Date & Time</label>
                <Input type="datetime-local" value={formData.check_out_time} onChange={e => setFormData(f => ({ ...f, check_out_time: e.target.value }))} required className="bg-slate-50 rounded-xl" data-testid="check-out-datetime" />
              </div>
            )}
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1 block">Reason</label>
              <Textarea value={formData.reason} onChange={e => setFormData(f => ({ ...f, reason: e.target.value }))} required placeholder="Explain reason..." className="bg-slate-50 rounded-xl" data-testid="missed-reason" />
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" id="auto_approve" checked={formData.auto_approve} onChange={e => setFormData(f => ({ ...f, auto_approve: e.target.checked }))} className="rounded" />
              <label htmlFor="auto_approve" className="text-xs text-slate-600">Auto-approve & update attendance</label>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowApply(false)}>Cancel</Button>
              <Button type="submit" className="bg-[#063c88] hover:bg-[#052d66] text-white" data-testid="submit-missed-punch">Submit</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Approve Confirmation */}
      <Dialog open={showApprove} onOpenChange={setShowApprove}>
        <DialogContent className="sm:max-w-sm" data-testid="approve-dialog">
          <DialogHeader><DialogTitle>Approve Missed Punch</DialogTitle></DialogHeader>
          <p className="text-sm text-slate-600">Approving will update the attendance record. Continue?</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowApprove(false)}>Cancel</Button>
            <Button onClick={handleApprove} className="bg-emerald-500 hover:bg-emerald-600 text-white" data-testid="confirm-approve">Approve</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject Confirmation */}
      <Dialog open={showReject} onOpenChange={setShowReject}>
        <DialogContent className="sm:max-w-sm" data-testid="reject-dialog">
          <DialogHeader><DialogTitle>Reject Missed Punch</DialogTitle></DialogHeader>
          <Textarea value={rejectReason} onChange={e => setRejectReason(e.target.value)} placeholder="Reason for rejection..." className="bg-slate-50 rounded-xl" data-testid="reject-reason" />
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowReject(false)}>Cancel</Button>
            <Button onClick={handleReject} className="bg-red-500 hover:bg-red-600 text-white" data-testid="confirm-reject">Reject</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AdminMissedPunch;
