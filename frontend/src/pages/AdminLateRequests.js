import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Clock, Search, Check, X, Plus, Eye, AlertTriangle, Pencil, Undo2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { DatePicker } from '../components/ui/date-picker';
import { formatDate } from '../lib/dateFormat';
import { EmployeeAutocomplete } from '../components/EmployeeAutocomplete';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../components/ui/sheet';
import { useTableSort, SortableTh } from '../components/useTableSort';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminLateRequests = () => {
  const { getAuthHeaders, user } = useAuth();
  const isHR = user?.role === 'hr';
  const [requests, setRequests] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('requests');
  const [selected, setSelected] = useState(null);
  const [showDetail, setShowDetail] = useState(false);
  const [showApprove, setShowApprove] = useState(false);
  const [showReject, setShowReject] = useState(false);
  const [showApply, setShowApply] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [editForm, setEditForm] = useState({ date: '', expected_time: '', actual_time: '', reason: '' });
  const [actionLoading, setActionLoading] = useState(false);
  const [lopChoice, setLopChoice] = useState('no_lop');
  const [lopRemark, setLopRemark] = useState('');
  const [searchName, setSearchName] = useState('');
  const [form, setForm] = useState({ employee_id: '', date: '', expected_time: '', actual_time: '', reason: '', is_lop: null, auto_approve: false });
  // Bulk selection (pending tab only)
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [showBulkApprove, setShowBulkApprove] = useState(false);
  const [showBulkReject, setShowBulkReject] = useState(false);
  const [bulkLop, setBulkLop] = useState('no_lop');
  const [bulkRemark, setBulkRemark] = useState('');
  const [bulkReason, setBulkReason] = useState('');

  const fetchData = useCallback(async () => {
    try { setLoading(true);
      const [reqRes, empRes] = await Promise.all([
        axios.get(`${API}/late-requests`, { headers: getAuthHeaders() }),
        axios.get(`${API}/employees/all`, { headers: getAuthHeaders() })
      ]);
      setRequests(reqRes.data); setEmployees(empRes.data);
    } catch { toast.error('Failed to load data'); }
    finally { setLoading(false); }
  }, [getAuthHeaders]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const pendingRequests = requests.filter(r => r.status === 'pending');
  const historyRequests = requests.filter(r => r.status !== 'pending');
  const filteredPending = searchName ? pendingRequests.filter(r => r.emp_name?.toLowerCase().includes(searchName.toLowerCase())) : pendingRequests;
  const filteredHistory = searchName ? historyRequests.filter(r => r.emp_name?.toLowerCase().includes(searchName.toLowerCase())) : historyRequests;
  const getStatusBadge = (s) => ({ pending: 'badge-warning', approved: 'badge-success', rejected: 'badge-error' }[s] || 'badge-neutral');

  // Keep selection in sync with the eligible (pending, filtered) rows only.
  useEffect(() => { setSelectedIds(new Set()); }, [activeTab, searchName]);
  const eligibleIds = filteredPending.map(r => r.id);
  const allSelected = eligibleIds.length > 0 && eligibleIds.every(id => selectedIds.has(id));
  const toggleOne = (id) => setSelectedIds(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const toggleAll = () => setSelectedIds(prev => allSelected ? new Set() : new Set(eligibleIds));
  const selectedRecords = filteredPending.filter(r => selectedIds.has(r.id));

  const handleBulkApprove = async () => {
    setActionLoading(true);
    try {
      const res = await axios.put(`${API}/late-requests/bulk-approve`, { ids: Array.from(selectedIds), is_lop: bulkLop === 'lop', lop_remark: bulkRemark || null }, { headers: getAuthHeaders() });
      const d = res.data;
      if (d.processed > 0) toast.success(`${d.processed} request${d.processed > 1 ? 's' : ''} approved successfully with ${bulkLop === 'lop' ? 'LOP' : 'No LOP'}.`);
      if (d.skipped > 0) toast.warning(`${d.skipped} selected request(s) skipped (already processed or ineligible).`);
      setShowBulkApprove(false); setBulkRemark(''); setSelectedIds(new Set()); fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Bulk approve failed'); }
    finally { setActionLoading(false); }
  };

  const handleBulkReject = async () => {
    setActionLoading(true);
    try {
      const res = await axios.put(`${API}/late-requests/bulk-reject`, { ids: Array.from(selectedIds), reason: bulkReason || null }, { headers: getAuthHeaders() });
      const d = res.data;
      if (d.processed > 0) toast.success(`${d.processed} request${d.processed > 1 ? 's' : ''} rejected successfully.`);
      if (d.skipped > 0) toast.warning(`${d.skipped} selected request(s) skipped (already processed or ineligible).`);
      setShowBulkReject(false); setBulkReason(''); setSelectedIds(new Set()); fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Bulk reject failed'); }
    finally { setActionLoading(false); }
  };

  const handleApprove = async () => {
    if (!selected) return;
    setActionLoading(true);
    try {
      await axios.put(`${API}/late-requests/${selected.id}/approve`, { is_lop: lopChoice === 'lop', lop_remark: lopRemark || null }, { headers: getAuthHeaders() });
      toast.success('Approved'); setShowApprove(false); setShowDetail(false); fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setActionLoading(false); }
  };

  const handleReject = async () => {
    if (!selected) return;
    setActionLoading(true);
    try { await axios.put(`${API}/late-requests/${selected.id}/reject`, {}, { headers: getAuthHeaders() }); toast.success('Rejected'); setShowReject(false); setShowDetail(false); fetchData(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setActionLoading(false); }
  };

  const handleApplyForEmployee = async () => {
    if (!form.employee_id || !form.date || !form.reason) { toast.error('Fill required fields'); return; }
    setActionLoading(true);
    try {
      await axios.post(`${API}/late-requests`, form, { headers: getAuthHeaders() });
      toast.success(form.auto_approve ? 'Applied & Approved' : 'Applied for employee');
      setShowApply(false); setForm({ employee_id: '', date: '', expected_time: '', actual_time: '', reason: '', is_lop: null, auto_approve: false }); fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setActionLoading(false); }
  };

  const openEdit = (r) => {
    setSelected(r);
    setEditForm({
      date: r.date || '',
      expected_time: r.expected_time || '',
      actual_time: r.actual_time || '',
      reason: r.reason || '',
    });
    setShowEdit(true);
  };

  const handleEdit = async () => {
    if (!selected) return;
    if (!editForm.date || !editForm.reason) { toast.error('Date and reason are required'); return; }
    setActionLoading(true);
    try {
      // Backend expects LateRequestCreate shape — include employee_id from record
      await axios.put(`${API}/late-requests/${selected.id}`, {
        employee_id: selected.employee_id,
        date: editForm.date,
        expected_time: editForm.expected_time,
        actual_time: editForm.actual_time,
        reason: editForm.reason,
      }, { headers: getAuthHeaders() });
      toast.success('Request updated');
      setShowEdit(false); setShowDetail(false); fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to update'); }
    finally { setActionLoading(false); }
  };

  const handleReset = async (r) => {
    if (!r) return;
    const ok = window.confirm(`Reset this ${r.status} late request for ${r.emp_name} back to Pending?`);
    if (!ok) return;
    try {
      await axios.post(`${API}/late-requests/${r.id}/reset`, { reason: 'manual reset' }, { headers: getAuthHeaders() });
      toast.success('Request reset to Pending');
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to reset'); }
  };

  const LateRequestsTable = ({ data, isPending }) => {
    const { sortedRows, sortField, sortDir, toggleSort } = useTableSort(data);
    return (
    <div className="overflow-x-auto">
      <table className="table-premium">
        <thead><tr>
          {isPending && isHR && <th className="w-10"><input type="checkbox" checked={allSelected} onChange={toggleAll} className="rounded w-4 h-4 accent-[#063c88] cursor-pointer" data-testid="late-select-all" aria-label="Select all" /></th>}
          <SortableTh field="emp_name" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Employee</SortableTh>
          <SortableTh field="team" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Team</SortableTh>
          <SortableTh field="date" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Date</SortableTh>
          <SortableTh field="expected_time" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Expected</SortableTh>
          <SortableTh field="actual_time" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Actual</SortableTh>
          <SortableTh field="reason" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Reason</SortableTh>
          <SortableTh field="status" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Status</SortableTh>
          <SortableTh field="is_lop" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>LOP</SortableTh>
          {isHR && <th>Actions</th>}
        </tr></thead>
        <tbody>
          {sortedRows.length === 0 ? <tr><td colSpan={(isHR ? 9 : 8) + (isPending && isHR ? 1 : 0)} className="text-center py-12 text-slate-500">No records</td></tr> : sortedRows.map(r => (
            <tr key={r.id} className={selectedIds.has(r.id) ? 'bg-blue-50/60' : ''}>
              {isPending && isHR && <td><input type="checkbox" checked={selectedIds.has(r.id)} onChange={() => toggleOne(r.id)} className="rounded w-4 h-4 accent-[#063c88] cursor-pointer" data-testid={`late-select-${r.id}`} aria-label="Select request" /></td>}
              <td className="font-medium text-slate-900">{r.emp_name}</td>
              <td className="text-slate-600">{r.team}</td>
              <td className="text-slate-600">{formatDate(r.date)}</td>
              <td className="text-slate-600">{r.expected_time || '-'}</td>
              <td className="text-slate-600">{r.actual_time || '-'}</td>
              <td className="text-slate-600 max-w-[180px] truncate">{r.reason}</td>
              <td><Badge className={getStatusBadge(r.status)}>{r.status}</Badge></td>
              <td>{r.is_lop === true ? <Badge className="badge-error">LOP</Badge> : r.is_lop === false ? <Badge className="badge-success">No LOP</Badge> : '-'}</td>
              {isHR && <td>
                <div className="flex gap-1">
                  <Button size="sm" variant="outline" onClick={() => { setSelected(r); setShowDetail(true); }} className="rounded-lg h-8 px-2" data-testid={`view-late-${r.id}`}><Eye className="w-3 h-3" /></Button>
                  <Button size="sm" variant="outline" onClick={() => openEdit(r)} className="rounded-lg h-8 px-2 border-blue-300 text-blue-700 hover:bg-blue-50" data-testid={`edit-late-${r.id}`} title="Edit"><Pencil className="w-3 h-3" /></Button>
                  {isPending && <>
                    <Button size="sm" onClick={() => { setSelected(r); setLopChoice('no_lop'); setLopRemark(''); setShowApprove(true); }} className="bg-emerald-500 hover:bg-emerald-600 text-white h-8 px-2 rounded-lg" data-testid={`approve-late-${r.id}`}><Check className="w-3 h-3" /></Button>
                    <Button size="sm" onClick={() => { setSelected(r); setShowReject(true); }} className="bg-red-500 hover:bg-red-600 text-white h-8 px-2 rounded-lg" data-testid={`reject-late-${r.id}`}><X className="w-3 h-3" /></Button>
                  </>}
                  {!isPending && (
                    <Button size="sm" variant="outline" onClick={() => handleReset(r)} className="rounded-lg h-8 px-2 border-amber-300 text-amber-700 hover:bg-amber-50" data-testid={`reset-late-${r.id}`} title="Reset to Pending"><Undo2 className="w-3 h-3" /></Button>
                  )}
                </div>
              </td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    );
  };

  return (
    <div className="space-y-6 animate-fade-in" data-testid="admin-late-requests-page">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center"><Clock className="w-5 h-5 text-white" /></div>
          <div><h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Late Requests</h1><p className="text-sm text-slate-500">Manage employee late login requests</p></div>
        </div>
        {isHR && <Button onClick={() => setShowApply(true)} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-xl" data-testid="admin-apply-late-btn"><Plus className="w-4 h-4 mr-2" /> Apply for Employee</Button>}
      </div>

      <div className="card-flat p-4"><div className="max-w-sm"><EmployeeAutocomplete value={searchName} onChange={setSearchName} onSelect={(emp) => setSearchName(emp.full_name)} placeholder="Search employee..." data-testid="late-search" /></div></div>

      {isHR && activeTab === 'requests' && selectedIds.size > 0 && (
        <div className="flex items-center justify-between gap-3 bg-[#063c88] text-white rounded-2xl px-5 py-3 shadow-md animate-fade-in" data-testid="late-bulk-bar">
          <span className="text-sm font-medium" data-testid="late-bulk-count">{selectedIds.size} Request{selectedIds.size > 1 ? 's' : ''} Selected</span>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={() => { setBulkLop('no_lop'); setBulkRemark(''); setShowBulkApprove(true); }} className="bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg h-8" data-testid="late-bulk-approve-btn"><Check className="w-4 h-4 mr-1" /> Approve Selected</Button>
            <Button size="sm" onClick={() => { setBulkReason(''); setShowBulkReject(true); }} className="bg-red-500 hover:bg-red-600 text-white rounded-lg h-8" data-testid="late-bulk-reject-btn"><X className="w-4 h-4 mr-1" /> Reject Selected</Button>
            <Button size="sm" variant="outline" onClick={() => setSelectedIds(new Set())} className="rounded-lg h-8 bg-transparent border-white/40 text-white hover:bg-white/10" data-testid="late-bulk-clear-btn">Clear Selection</Button>
          </div>
        </div>
      )}

      <div className="card-premium overflow-hidden">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <div className="border-b border-slate-100 bg-slate-50/50">
            <TabsList className="bg-transparent h-auto p-0">
              <TabsTrigger value="requests" className="px-6 py-4 rounded-none data-[state=active]:bg-[#063c88] data-[state=active]:text-white">Pending ({filteredPending.length})</TabsTrigger>
              <TabsTrigger value="history" className="px-6 py-4 rounded-none data-[state=active]:bg-[#063c88] data-[state=active]:text-white">History ({filteredHistory.length})</TabsTrigger>
            </TabsList>
          </div>
          <TabsContent value="requests" className="mt-0">{loading ? <div className="flex items-center justify-center h-48"><div className="w-10 h-10 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" /></div> : <LateRequestsTable data={filteredPending} isPending={true} />}</TabsContent>
          <TabsContent value="history" className="mt-0"><LateRequestsTable data={filteredHistory} isPending={false} /></TabsContent>
        </Tabs>
      </div>

      {/* Detail Sheet */}
      <Sheet open={showDetail} onOpenChange={setShowDetail}>
        <SheetContent className="w-full sm:max-w-md bg-[#fffdf7]"><SheetHeader><SheetTitle style={{ fontFamily: 'Outfit' }}>Late Request Details</SheetTitle></SheetHeader>
          {selected && <div className="py-6 space-y-4">
            {[{ l: 'Employee', v: selected.emp_name }, { l: 'Team', v: selected.team }, { l: 'Date', v: selected.date }, { l: 'Expected Time', v: selected.expected_time || '-' }, { l: 'Actual Time', v: selected.actual_time || '-' }, { l: 'Reason', v: selected.reason }].map((item, i) => (
              <div key={i} className="flex justify-between py-2 border-b border-dashed border-slate-200"><span className="text-slate-500 text-sm">{item.l}</span><span className="font-medium text-slate-900 text-right max-w-[60%]">{item.v}</span></div>
            ))}
            {selected.status === 'pending' && isHR && <div className="flex gap-3 pt-4">
              <Button onClick={() => { setLopChoice('no_lop'); setLopRemark(''); setShowApprove(true); }} className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg"><Check className="w-4 h-4 mr-2" /> Approve</Button>
              <Button onClick={() => setShowReject(true)} className="flex-1 bg-red-500 hover:bg-red-600 text-white rounded-lg"><X className="w-4 h-4 mr-2" /> Reject</Button>
            </div>}
          </div>}
        </SheetContent>
      </Sheet>

      {/* Approve Dialog with LOP */}
      <Dialog open={showApprove} onOpenChange={setShowApprove}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl"><DialogHeader><DialogTitle style={{ fontFamily: 'Outfit' }}><Check className="w-5 h-5 text-emerald-500 inline mr-2" />Approve Late Request</DialogTitle><DialogDescription>Choose LOP status</DialogDescription></DialogHeader>
          <div className="py-4 space-y-4">
            {selected && <p className="text-sm"><span className="text-slate-500">Employee:</span> <span className="font-medium">{selected.emp_name}</span> — {formatDate(selected.date)}</p>}
            <div><Label>LOP Status</Label>
              <Select value={lopChoice} onValueChange={setLopChoice}><SelectTrigger className="mt-1.5 rounded-lg" data-testid="lop-select"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="no_lop">No LOP</SelectItem><SelectItem value="lop">LOP (Loss of Pay)</SelectItem></SelectContent>
              </Select>
            </div>
            <div><Label>Remark (optional)</Label><Input value={lopRemark} onChange={e => setLopRemark(e.target.value)} className="mt-1.5 rounded-lg" placeholder="Optional remark..." /></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setShowApprove(false)} disabled={actionLoading} className="rounded-lg">Cancel</Button><Button onClick={handleApprove} disabled={actionLoading} className="bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg">{actionLoading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Confirm Approve'}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject Dialog */}
      <Dialog open={showReject} onOpenChange={setShowReject}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl"><DialogHeader><DialogTitle style={{ fontFamily: 'Outfit' }}><AlertTriangle className="w-5 h-5 text-red-500 inline mr-2" />Reject Late Request</DialogTitle><DialogDescription>Are you sure you want to reject?</DialogDescription></DialogHeader>
          {selected && <p className="py-4 text-sm"><span className="text-slate-500">Employee:</span> <span className="font-medium">{selected.emp_name}</span> — {formatDate(selected.date)}</p>}
          <DialogFooter><Button variant="outline" onClick={() => setShowReject(false)} disabled={actionLoading} className="rounded-lg">Cancel</Button><Button onClick={handleReject} disabled={actionLoading} className="bg-red-500 hover:bg-red-600 text-white rounded-lg">{actionLoading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Confirm Reject'}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Apply for Employee Dialog */}
      <Dialog open={showApply} onOpenChange={setShowApply}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl sm:max-w-lg"><DialogHeader><DialogTitle style={{ fontFamily: 'Outfit' }}>Apply Late Request for Employee</DialogTitle><DialogDescription>Submit on behalf of an employee</DialogDescription></DialogHeader>
          <div className="space-y-4 py-4">
            <div><Label>Employee</Label>
              <Select value={form.employee_id} onValueChange={v => setForm({ ...form, employee_id: v })}><SelectTrigger className="mt-1.5 rounded-lg" data-testid="select-employee"><SelectValue placeholder="Select employee" /></SelectTrigger>
                <SelectContent>{employees.map(e => <SelectItem key={e.id} value={e.id}>{e.full_name} ({e.team})</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Date</Label><DatePicker value={form.date} onChange={(val) => setForm({ ...form, date: val })} className="mt-1.5 rounded-lg" /></div>
            <div className="grid grid-cols-2 gap-4">
              <div><Label>Expected Time</Label><Input type="time" value={form.expected_time} onChange={e => setForm({ ...form, expected_time: e.target.value })} className="mt-1.5 rounded-lg" /></div>
              <div><Label>Actual Time</Label><Input type="time" value={form.actual_time} onChange={e => setForm({ ...form, actual_time: e.target.value })} className="mt-1.5 rounded-lg" /></div>
            </div>
            <div><Label>Reason</Label><Textarea value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} className="mt-1.5 rounded-lg min-h-[80px]" placeholder="Reason..." /></div>
            <div className="flex items-center gap-4 pt-2">
              <label className="flex items-center gap-2 cursor-pointer"><input type="checkbox" checked={form.auto_approve} onChange={e => setForm({ ...form, auto_approve: e.target.checked })} className="rounded" /><span className="text-sm text-slate-700">Auto-approve</span></label>
              {form.auto_approve && <Select value={form.is_lop === true ? 'lop' : 'no_lop'} onValueChange={v => setForm({ ...form, is_lop: v === 'lop' })}><SelectTrigger className="w-[140px] rounded-lg"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="no_lop">No LOP</SelectItem><SelectItem value="lop">LOP</SelectItem></SelectContent></Select>}
            </div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setShowApply(false)} className="rounded-lg">Cancel</Button><Button onClick={handleApplyForEmployee} disabled={actionLoading} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg">{actionLoading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Submit'}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
      {/* Bulk Approve Dialog with LOP */}
      <Dialog open={showBulkApprove} onOpenChange={setShowBulkApprove}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl sm:max-w-lg" data-testid="late-bulk-approve-dialog">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Outfit' }}><Check className="w-5 h-5 text-emerald-500 inline mr-2" />Approve Selected Requests</DialogTitle><DialogDescription>Choose how these {selectedRecords.length} request{selectedRecords.length > 1 ? 's' : ''} should be treated.</DialogDescription></DialogHeader>
          <div className="py-3 space-y-4">
            <div><Label>LOP Decision</Label>
              <Select value={bulkLop} onValueChange={setBulkLop}><SelectTrigger className="mt-1.5 rounded-lg" data-testid="late-bulk-lop-select"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="no_lop">No LOP</SelectItem><SelectItem value="lop">LOP (Loss of Pay)</SelectItem></SelectContent>
              </Select>
              <p className="text-xs text-slate-500 mt-1">This decision will be applied to all eligible selected requests.</p>
            </div>
            <div><Label>Remark (optional)</Label><Input value={bulkRemark} onChange={e => setBulkRemark(e.target.value)} className="mt-1.5 rounded-lg" placeholder="Optional remark..." /></div>
            <div className="max-h-52 overflow-y-auto rounded-lg border border-slate-200 divide-y divide-slate-100" data-testid="late-bulk-approve-list">
              {selectedRecords.map((r, i) => (
                <div key={r.id} className="flex items-center justify-between px-3 py-2 text-sm">
                  <span className="text-slate-700">{i + 1}. <span className="font-medium">{r.emp_name}</span> — Late</span>
                  <span className="text-slate-500">{formatDate(r.date)}</span>
                </div>
              ))}
            </div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setShowBulkApprove(false)} disabled={actionLoading} className="rounded-lg">Cancel</Button><Button onClick={handleBulkApprove} disabled={actionLoading} className="bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg" data-testid="late-bulk-approve-confirm">{actionLoading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : `Approve ${selectedRecords.length} Request${selectedRecords.length > 1 ? 's' : ''}`}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Reject Dialog */}
      <Dialog open={showBulkReject} onOpenChange={setShowBulkReject}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl sm:max-w-lg" data-testid="late-bulk-reject-dialog">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Outfit' }}><AlertTriangle className="w-5 h-5 text-red-500 inline mr-2" />Reject Selected Requests</DialogTitle><DialogDescription>Are you sure you want to reject these {selectedRecords.length} request{selectedRecords.length > 1 ? 's' : ''}?</DialogDescription></DialogHeader>
          <div className="py-3 space-y-4">
            <div><Label>Reason (optional)</Label><Textarea value={bulkReason} onChange={e => setBulkReason(e.target.value)} className="mt-1.5 rounded-lg min-h-[70px]" placeholder="Reason for rejection..." /></div>
            <div className="max-h-52 overflow-y-auto rounded-lg border border-slate-200 divide-y divide-slate-100" data-testid="late-bulk-reject-list">
              {selectedRecords.map((r, i) => (
                <div key={r.id} className="flex items-center justify-between px-3 py-2 text-sm">
                  <span className="text-slate-700">{i + 1}. <span className="font-medium">{r.emp_name}</span> — Late</span>
                  <span className="text-slate-500">{formatDate(r.date)}</span>
                </div>
              ))}
            </div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setShowBulkReject(false)} disabled={actionLoading} className="rounded-lg">Cancel</Button><Button onClick={handleBulkReject} disabled={actionLoading} className="bg-red-500 hover:bg-red-600 text-white rounded-lg" data-testid="late-bulk-reject-confirm">{actionLoading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : `Reject ${selectedRecords.length} Request${selectedRecords.length > 1 ? 's' : ''}`}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog (HR) - any status */}
      <Dialog open={showEdit} onOpenChange={setShowEdit}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl sm:max-w-lg" data-testid="edit-late-dialog">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Outfit' }} className="flex items-center gap-2">
              <Pencil className="w-5 h-5 text-[#063c88]" /> Edit Late Request
            </DialogTitle>
            <DialogDescription>Update the request — status & approval remain unchanged.</DialogDescription>
          </DialogHeader>
          {selected && (
            <div className="space-y-4 py-2">
              <p className="text-sm"><span className="text-slate-500">Employee:</span> <span className="font-medium">{selected.emp_name}</span> — <Badge className={getStatusBadge(selected.status)}>{selected.status}</Badge></p>
              <div><Label>Date</Label><DatePicker value={editForm.date} onChange={(val) => setEditForm({ ...editForm, date: val })} className="mt-1.5 rounded-lg" data-testid="edit-late-date" /></div>
              <div className="grid grid-cols-2 gap-4">
                <div><Label>Expected Time</Label><Input type="time" value={editForm.expected_time} onChange={e => setEditForm({ ...editForm, expected_time: e.target.value })} className="mt-1.5 rounded-lg" data-testid="edit-late-expected" /></div>
                <div><Label>Actual Time</Label><Input type="time" value={editForm.actual_time} onChange={e => setEditForm({ ...editForm, actual_time: e.target.value })} className="mt-1.5 rounded-lg" data-testid="edit-late-actual" /></div>
              </div>
              <div><Label>Reason</Label><Textarea value={editForm.reason} onChange={e => setEditForm({ ...editForm, reason: e.target.value })} className="mt-1.5 rounded-lg min-h-[80px]" data-testid="edit-late-reason" /></div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEdit(false)} disabled={actionLoading} className="rounded-lg">Cancel</Button>
            <Button onClick={handleEdit} disabled={actionLoading} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg" data-testid="confirm-edit-late">
              {actionLoading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AdminLateRequests;
