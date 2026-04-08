import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Clock, Search, Check, X, Plus, Eye, AlertTriangle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../components/ui/sheet';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminLateRequests = () => {
  const { getAuthHeaders } = useAuth();
  const [requests, setRequests] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('requests');
  const [selected, setSelected] = useState(null);
  const [showDetail, setShowDetail] = useState(false);
  const [showApprove, setShowApprove] = useState(false);
  const [showReject, setShowReject] = useState(false);
  const [showApply, setShowApply] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [lopChoice, setLopChoice] = useState('no_lop');
  const [lopRemark, setLopRemark] = useState('');
  const [searchName, setSearchName] = useState('');
  const [form, setForm] = useState({ employee_id: '', date: '', expected_time: '', actual_time: '', reason: '', is_lop: null, auto_approve: false });

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

  const renderTable = (data, showActions) => (
    <div className="overflow-x-auto">
      <table className="table-premium">
        <thead><tr><th>Employee</th><th>Team</th><th>Date</th><th>Expected</th><th>Actual</th><th>Reason</th><th>Status</th><th>LOP</th>{showActions && <th>Actions</th>}</tr></thead>
        <tbody>
          {data.length === 0 ? <tr><td colSpan={showActions ? 9 : 8} className="text-center py-12 text-slate-500">No records</td></tr> : data.map(r => (
            <tr key={r.id}>
              <td className="font-medium text-slate-900">{r.emp_name}</td>
              <td className="text-slate-600">{r.team}</td>
              <td className="text-slate-600">{r.date}</td>
              <td className="text-slate-600">{r.expected_time || '-'}</td>
              <td className="text-slate-600">{r.actual_time || '-'}</td>
              <td className="text-slate-600 max-w-[180px] truncate">{r.reason}</td>
              <td><Badge className={getStatusBadge(r.status)}>{r.status}</Badge></td>
              <td>{r.is_lop === true ? <Badge className="badge-error">LOP</Badge> : r.is_lop === false ? <Badge className="badge-success">No LOP</Badge> : '-'}</td>
              {showActions && <td>
                <div className="flex gap-1">
                  <Button size="sm" variant="outline" onClick={() => { setSelected(r); setShowDetail(true); }} className="rounded-lg h-8 px-2"><Eye className="w-3 h-3" /></Button>
                  <Button size="sm" onClick={() => { setSelected(r); setLopChoice('no_lop'); setLopRemark(''); setShowApprove(true); }} className="bg-emerald-500 hover:bg-emerald-600 text-white h-8 px-2 rounded-lg"><Check className="w-3 h-3" /></Button>
                  <Button size="sm" onClick={() => { setSelected(r); setShowReject(true); }} className="bg-red-500 hover:bg-red-600 text-white h-8 px-2 rounded-lg"><X className="w-3 h-3" /></Button>
                </div>
              </td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in" data-testid="admin-late-requests-page">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center"><Clock className="w-5 h-5 text-white" /></div>
          <div><h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Late Requests</h1><p className="text-sm text-slate-500">Manage employee late login requests</p></div>
        </div>
        <Button onClick={() => setShowApply(true)} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-xl" data-testid="admin-apply-late-btn"><Plus className="w-4 h-4 mr-2" /> Apply for Employee</Button>
      </div>

      <div className="card-flat p-4"><div className="relative max-w-sm"><Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" /><Input placeholder="Search employee..." value={searchName} onChange={e => setSearchName(e.target.value)} className="pl-10 rounded-lg" /></div></div>

      <div className="card-premium overflow-hidden">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <div className="border-b border-slate-100 bg-slate-50/50">
            <TabsList className="bg-transparent h-auto p-0">
              <TabsTrigger value="requests" className="px-6 py-4 rounded-none data-[state=active]:bg-[#063c88] data-[state=active]:text-white">Pending ({filteredPending.length})</TabsTrigger>
              <TabsTrigger value="history" className="px-6 py-4 rounded-none data-[state=active]:bg-[#063c88] data-[state=active]:text-white">History ({filteredHistory.length})</TabsTrigger>
            </TabsList>
          </div>
          <TabsContent value="requests" className="mt-0">{loading ? <div className="flex items-center justify-center h-48"><div className="w-10 h-10 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" /></div> : renderTable(filteredPending, true)}</TabsContent>
          <TabsContent value="history" className="mt-0">{renderTable(filteredHistory, false)}</TabsContent>
        </Tabs>
      </div>

      {/* Detail Sheet */}
      <Sheet open={showDetail} onOpenChange={setShowDetail}>
        <SheetContent className="w-full sm:max-w-md bg-[#fffdf7]"><SheetHeader><SheetTitle style={{ fontFamily: 'Outfit' }}>Late Request Details</SheetTitle></SheetHeader>
          {selected && <div className="py-6 space-y-4">
            {[{ l: 'Employee', v: selected.emp_name }, { l: 'Team', v: selected.team }, { l: 'Date', v: selected.date }, { l: 'Expected Time', v: selected.expected_time || '-' }, { l: 'Actual Time', v: selected.actual_time || '-' }, { l: 'Reason', v: selected.reason }].map((item, i) => (
              <div key={i} className="flex justify-between py-2 border-b border-dashed border-slate-200"><span className="text-slate-500 text-sm">{item.l}</span><span className="font-medium text-slate-900 text-right max-w-[60%]">{item.v}</span></div>
            ))}
            {selected.status === 'pending' && <div className="flex gap-3 pt-4">
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
            {selected && <p className="text-sm"><span className="text-slate-500">Employee:</span> <span className="font-medium">{selected.emp_name}</span> — {selected.date}</p>}
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
          {selected && <p className="py-4 text-sm"><span className="text-slate-500">Employee:</span> <span className="font-medium">{selected.emp_name}</span> — {selected.date}</p>}
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
            <div><Label>Date</Label><Input type="date" value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} className="mt-1.5 rounded-lg" /></div>
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
    </div>
  );
};

export default AdminLateRequests;
