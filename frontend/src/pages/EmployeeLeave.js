import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { CalendarDays, Plus, Clock, CheckCircle2, XCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EmployeeLeave = () => {
  const { getAuthHeaders } = useAuth();
  const [leaves, setLeaves] = useState([]);
  const [leaveBalance, setLeaveBalance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showApplyDialog, setShowApplyDialog] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [form, setForm] = useState({ leave_type: 'Sick', leave_date: '', duration: 'Full Day', reason: '' });

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const leavesRes = await axios.get(`${API}/employee/leaves`, { headers: getAuthHeaders() });
      const data = leavesRes.data;
      // Backend returns {requests: [], history: []} - merge into flat array
      const allLeaves = [...(data.requests || []), ...(data.history || [])];
      setLeaves(Array.isArray(data) ? data : allLeaves);
      try {
        const balanceRes = await axios.get(`${API}/employee/leave-balance`, { headers: getAuthHeaders() });
        setLeaveBalance(balanceRes.data);
      } catch {
        setLeaveBalance(null);
      }
    } catch (error) {
      toast.error('Failed to load leave data');
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleApplyLeave = async () => {
    if (!form.leave_type || !form.leave_date || !form.duration || !form.reason) {
      toast.error('Please fill all fields');
      return;
    }
    if (form.reason.trim().length < 10) {
      toast.error('Reason must be at least 10 characters');
      return;
    }
    // Convert date from YYYY-MM-DD (input) to DD-MM-YYYY (backend)
    const [y, m, d] = form.leave_date.split('-');
    const payload = { ...form, leave_date: `${d}-${m}-${y}` };
    try {
      setFormLoading(true);
      await axios.post(`${API}/employee/leaves/apply`, payload, { headers: getAuthHeaders() });
      toast.success('Leave application submitted');
      setShowApplyDialog(false);
      setForm({ leave_type: 'Sick', leave_date: '', duration: 'Full Day', reason: '' });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to apply leave');
    } finally {
      setFormLoading(false);
    }
  };

  const getStatusBadge = (status) => ({ 'pending': 'badge-warning', 'approved': 'badge-success', 'rejected': 'badge-error' }[status] || 'badge-neutral');

  const stats = {
    pending: leaves.filter(l => l.status === 'pending').length,
    approved: leaves.filter(l => l.status === 'approved').length,
    rejected: leaves.filter(l => l.status === 'rejected').length,
  };

  return (
    <div className="space-y-6 animate-fade-in" data-testid="employee-leave-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
            <CalendarDays className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Leave Management</h1>
            <p className="text-sm text-slate-500">Apply for leave and track requests</p>
          </div>
        </div>
        <Button onClick={() => setShowApplyDialog(true)} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-xl shadow-lg shadow-[#063c88]/20" data-testid="apply-leave-btn">
          <Plus className="w-4 h-4 mr-2" /> Apply Leave
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Pending', value: stats.pending, icon: Clock, color: 'amber' },
          { label: 'Approved', value: stats.approved, icon: CheckCircle2, color: 'blue' },
          { label: 'Rejected', value: stats.rejected, icon: XCircle, color: 'red' },
        ].map((stat, i) => (
          <div key={i} className="stat-card">
            <div className="flex items-center gap-4">
              <div className={`w-10 h-10 rounded-xl bg-${stat.color}-100 flex items-center justify-center`}>
                <stat.icon className={`w-5 h-5 text-${stat.color}-600`} />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900 number-display">{stat.value}</p>
                <p className="text-xs text-slate-500">{stat.label}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Leave Balance */}
      {leaveBalance && (
        <div className="card-premium p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4" style={{ fontFamily: 'Outfit' }}>Leave Balance</h3>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'Sick', remaining: leaveBalance.sick_remaining, total: leaveBalance.sick_total },
              { label: 'Casual', remaining: leaveBalance.casual_remaining, total: leaveBalance.casual_total },
              { label: 'Annual', remaining: leaveBalance.annual_remaining, total: leaveBalance.annual_total },
            ].map((leave, i) => (
              <div key={i} className="p-4 rounded-xl bg-slate-50">
                <p className="text-sm text-slate-500 mb-2">{leave.label} Leave</p>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-bold text-slate-900">{leave.remaining}</span>
                  <span className="text-sm text-slate-500">/ {leave.total}</span>
                </div>
                <div className="h-2 bg-slate-200 rounded-full mt-2 overflow-hidden">
                  <div className="h-full bg-[#063c88] rounded-full transition-all" style={{ width: `${(leave.remaining / leave.total) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Leave History */}
      <div className="card-premium overflow-hidden">
        <div className="p-6 border-b border-slate-100">
          <h3 className="text-lg font-semibold text-slate-900" style={{ fontFamily: 'Outfit' }}>Leave History</h3>
        </div>
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-10 h-10 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-premium">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Start Date</th>
                  <th>End Date</th>
                  <th>Duration</th>
                  <th>Reason</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {leaves.length === 0 ? (
                  <tr><td colSpan="6" className="text-center py-12 text-slate-500">No leave records found</td></tr>
                ) : (
                  leaves.map((leave, index) => (
                    <tr key={index}>
                      <td className="font-medium text-slate-900">{leave.leave_type}</td>
                      <td className="text-slate-600">{leave.start_date}</td>
                      <td className="text-slate-600">{leave.end_date}</td>
                      <td className="text-slate-600">{leave.duration}</td>
                      <td className="text-slate-600 max-w-[200px] truncate">{leave.reason}</td>
                      <td><Badge className={getStatusBadge(leave.status)}>{leave.status}</Badge></td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Apply Leave Dialog */}
      <Dialog open={showApplyDialog} onOpenChange={setShowApplyDialog}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Outfit' }}>Apply for Leave</DialogTitle>
            <DialogDescription>Submit a new leave request</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label className="text-sm font-medium text-slate-700">Leave Type</Label>
              <Select value={form.leave_type} onValueChange={(v) => setForm({ ...form, leave_type: v })}>
                <SelectTrigger className="mt-1.5 rounded-lg" data-testid="leave-type-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Sick">Sick Leave</SelectItem>
                  <SelectItem value="Casual">Casual Leave</SelectItem>
                  <SelectItem value="Annual">Annual Leave</SelectItem>
                  <SelectItem value="Emergency">Emergency</SelectItem>
                  <SelectItem value="Preplanned">Preplanned</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-medium text-slate-700">Leave Date</Label>
                <Input type="date" value={form.leave_date} onChange={(e) => setForm({ ...form, leave_date: e.target.value })} className="mt-1.5 rounded-lg" data-testid="leave-date-input" />
              </div>
              <div>
                <Label className="text-sm font-medium text-slate-700">Duration</Label>
                <Select value={form.duration} onValueChange={(v) => setForm({ ...form, duration: v })}>
                  <SelectTrigger className="mt-1.5 rounded-lg" data-testid="duration-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Full Day">Full Day</SelectItem>
                    <SelectItem value="First Half">First Half</SelectItem>
                    <SelectItem value="Second Half">Second Half</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label className="text-sm font-medium text-slate-700">Reason (min 10 characters)</Label>
              <Textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="mt-1.5 rounded-lg min-h-[80px]" placeholder="Enter reason for leave..." data-testid="reason-textarea" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowApplyDialog(false)} className="rounded-lg">Cancel</Button>
            <Button onClick={handleApplyLeave} disabled={formLoading} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg" data-testid="submit-leave-btn">
              {formLoading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Submit'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EmployeeLeave;
