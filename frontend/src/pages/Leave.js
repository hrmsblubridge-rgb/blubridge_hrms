import { useState, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { CalendarDays, Search, Filter, RotateCcw, Check, X, ChevronUp, ChevronDown, Eye, AlertTriangle, Clock, CheckCircle2, XCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../components/ui/sheet';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Leave = () => {
  const { getAuthHeaders, user } = useAuth();
  const location = useLocation();
  const [leaves, setLeaves] = useState([]);
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('requests');
  const [sortField, setSortField] = useState('emp_name');
  const [sortOrder, setSortOrder] = useState('asc');
  const [selectedLeave, setSelectedLeave] = useState(null);
  const [showDetailSheet, setShowDetailSheet] = useState(false);
  const [showApproveDialog, setShowApproveDialog] = useState(false);
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [filters, setFilters] = useState({ empName: '', team: 'All', fromDate: '', toDate: '', leaveType: 'All', status: 'All' });

  useEffect(() => {
    if (location.state?.tab) {
      if (location.state.tab === 'approved') { setFilters(prev => ({ ...prev, status: 'approved' })); setActiveTab('history'); }
      else if (location.state.tab === 'pending') { setFilters(prev => ({ ...prev, status: 'pending' })); setActiveTab('requests'); }
    }
  }, [location.state]);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [leavesRes, teamsRes] = await Promise.all([
        axios.get(`${API}/leaves`, { headers: getAuthHeaders() }),
        axios.get(`${API}/teams`, { headers: getAuthHeaders() })
      ]);
      setLeaves(leavesRes.data);
      setTeams(teamsRes.data);
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
  const openApproveDialog = (leave) => { setSelectedLeave(leave); setShowApproveDialog(true); };
  const openRejectDialog = (leave) => { setSelectedLeave(leave); setShowRejectDialog(true); };

  const confirmApprove = async () => {
    if (!selectedLeave) return;
    setActionLoading(true);
    try {
      await axios.put(`${API}/leaves/${selectedLeave.id}/approve`, {}, { headers: getAuthHeaders() });
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

  const handleSort = (field) => {
    if (sortField === field) setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortOrder('asc'); }
  };

  const sortedLeaves = [...leaves].sort((a, b) => {
    const aVal = a[sortField] || '';
    const bVal = b[sortField] || '';
    return sortOrder === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
  });

  const pendingLeaves = sortedLeaves.filter(l => l.status === 'pending');
  const historyLeaves = sortedLeaves.filter(l => l.status !== 'pending');
  const SortIcon = ({ field }) => sortField !== field ? null : sortOrder === 'asc' ? <ChevronUp className="w-4 h-4 inline ml-1" /> : <ChevronDown className="w-4 h-4 inline ml-1" />;
  const getStatusBadge = (status) => ({ 'pending': 'badge-warning', 'approved': 'badge-success', 'rejected': 'badge-error' }[status] || 'badge-neutral');
  const canApprove = ['super_admin', 'admin', 'hr_manager', 'team_lead'].includes(user?.role);

  return (
    <div className="space-y-6 animate-fade-in" data-testid="leave-page">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
          <CalendarDays className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Leave Management</h1>
          <p className="text-sm text-slate-500">Manage employee leave requests</p>
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
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input placeholder="Search..." value={filters.empName} onChange={(e) => setFilters({ ...filters, empName: e.target.value })} className="pl-10 rounded-lg" data-testid="search-emp-name" />
            </div>
          </div>
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">From</label>
            <Input type="date" value={filters.fromDate} onChange={(e) => setFilters({ ...filters, fromDate: e.target.value })} className="rounded-lg" data-testid="filter-from" />
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
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">To</label>
            <Input type="date" value={filters.toDate} onChange={(e) => setFilters({ ...filters, toDate: e.target.value })} className="rounded-lg" data-testid="filter-to" />
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
                      <th className="cursor-pointer" onClick={() => handleSort('emp_name')}>Employee <SortIcon field="emp_name" /></th>
                      <th className="cursor-pointer" onClick={() => handleSort('team')}>Team <SortIcon field="team" /></th>
                      <th>Type</th>
                      <th>Date</th>
                      <th>Duration</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingLeaves.length === 0 ? (
                      <tr><td colSpan="7" className="text-center py-12 text-slate-500">No pending requests</td></tr>
                    ) : (
                      pendingLeaves.map((leave) => (
                        <tr key={leave.id}>
                          <td>
                            <button className="p-2 hover:bg-slate-100 rounded-lg transition-colors" onClick={() => handleViewLeave(leave)}>
                              <Eye className="w-4 h-4 text-slate-400" />
                            </button>
                          </td>
                          <td className="font-medium text-slate-900">{leave.emp_name}</td>
                          <td className="text-slate-600">{leave.team}</td>
                          <td className="text-slate-600">{leave.leave_type}</td>
                          <td className="text-slate-600">{leave.start_date}</td>
                          <td className="text-slate-600">{leave.duration}</td>
                          <td>
                            {canApprove && (
                              <div className="flex gap-2">
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
              </div>
            )}
          </TabsContent>

          <TabsContent value="history" className="mt-0">
            <div className="overflow-x-auto">
              <table className="table-premium">
                <thead>
                  <tr>
                    <th className="w-12"></th>
                    <th>Employee</th>
                    <th>Team</th>
                    <th>Type</th>
                    <th>Date</th>
                    <th>Duration</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {historyLeaves.length === 0 ? (
                    <tr><td colSpan="7" className="text-center py-12 text-slate-500">No history records</td></tr>
                  ) : (
                    historyLeaves.map((leave) => (
                      <tr key={leave.id}>
                        <td>
                          <button className="p-2 hover:bg-slate-100 rounded-lg transition-colors" onClick={() => handleViewLeave(leave)}>
                            <Eye className="w-4 h-4 text-slate-400" />
                          </button>
                        </td>
                        <td className="font-medium text-slate-900">{leave.emp_name}</td>
                        <td className="text-slate-600">{leave.team}</td>
                        <td className="text-slate-600">{leave.leave_type}</td>
                        <td className="text-slate-600">{leave.start_date}</td>
                        <td className="text-slate-600">{leave.duration}</td>
                        <td><Badge className={getStatusBadge(leave.status)}>{leave.status}</Badge></td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
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

      {/* Approve Dialog */}
      <Dialog open={showApproveDialog} onOpenChange={setShowApproveDialog}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Outfit' }}>
              <Check className="w-5 h-5 text-emerald-500" /> Approve Leave
            </DialogTitle>
            <DialogDescription>Confirm leave approval</DialogDescription>
          </DialogHeader>
          {selectedLeave && (
            <div className="py-4 space-y-2">
              <p><span className="text-slate-500">Employee:</span> <span className="font-medium">{selectedLeave.emp_name}</span></p>
              <p><span className="text-slate-500">Type:</span> <span className="font-medium">{selectedLeave.leave_type}</span></p>
              <p><span className="text-slate-500">Duration:</span> <span className="font-medium">{selectedLeave.duration}</span></p>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowApproveDialog(false)} disabled={actionLoading} className="rounded-lg">Cancel</Button>
            <Button onClick={confirmApprove} disabled={actionLoading} className="bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg">
              {actionLoading ? <div className="w-4 h-4 mr-2 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Check className="w-4 h-4 mr-2" />}
              Confirm
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
    </div>
  );
};

export default Leave;
