import React, { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Download, Plus, Eye, ArrowLeft, Star, Users, Award, TrendingUp, Trophy, Sparkles, AlertTriangle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { MonthPicker } from '../components/ui/month-picker';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { PageSizeSelector } from '../components/PageSizeSelector';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getWeeksForMonth = (monthStr) => {
  const [year, month] = monthStr.split('-').map(Number);
  const firstDay = new Date(year, month - 1, 1);
  const lastDay = new Date(year, month, 0);
  const weeks = [];
  let weekStart = new Date(firstDay);
  let weekNum = 1;
  
  while (weekStart <= lastDay && weekNum <= 5) {
    let weekEnd = new Date(weekStart);
    weekEnd.setDate(weekEnd.getDate() + 6);
    if (weekEnd > lastDay) weekEnd = new Date(lastDay);
    weeks.push({
      week: weekNum,
      startDate: weekStart.toISOString().split('T')[0],
      endDate: weekEnd.toISOString().split('T')[0],
      fromDate: weekStart.toISOString().split('T')[0],
      toDate: weekEnd.toISOString().split('T')[0],
      value: '',
      reason: ''
    });
    weekStart = new Date(weekEnd);
    weekStart.setDate(weekStart.getDate() + 1);
    weekNum++;
  }
  while (weeks.length < 5) {
    const lastWeek = weeks[weeks.length - 1];
    const newStart = new Date(lastWeek.endDate);
    newStart.setDate(newStart.getDate() + 1);
    const newEnd = new Date(newStart);
    newEnd.setDate(newEnd.getDate() + 6);
    weeks.push({
      week: weeks.length + 1, startDate: newStart.toISOString().split('T')[0], endDate: newEnd.toISOString().split('T')[0],
      fromDate: newStart.toISOString().split('T')[0], toDate: newEnd.toISOString().split('T')[0], value: '', reason: ''
    });
  }
  return weeks;
};

const StarReward = () => {
  const { getAuthHeaders, user } = useAuth();
  const [employees, setEmployees] = useState([]);
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('employees');
  const [viewMode, setViewMode] = useState('table');
  const [showTeamDetails, setShowTeamDetails] = useState(false);
  const [selectedTeam, setSelectedTeam] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [addFormType, setAddFormType] = useState('performance');
  const [addFormMonth, setAddFormMonth] = useState(new Date().toISOString().slice(0, 7));
  const [weeklyData, setWeeklyData] = useState([]);
  const [simpleFormData, setSimpleFormData] = useState({ value: '', reason: '' });
  const [showViewModal, setShowViewModal] = useState(false);
  const [starHistory, setStarHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [filters, setFilters] = useState({ team: 'All', month: new Date().toISOString().slice(0, 7), search: '' });
  const [tableFilters, setTableFilters] = useState({ fromMonth: new Date().toISOString().slice(0, 7), toMonth: new Date().toISOString().slice(0, 7), pageSize: 25 });
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => { fetchData(); }, []);
  useEffect(() => { if (addFormType === 'performance' || addFormType === 'learning') setWeeklyData(getWeeksForMonth(addFormMonth)); }, [addFormMonth, addFormType]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [employeesRes, teamsRes] = await Promise.all([
        axios.get(`${API}/star-rewards`, { headers: getAuthHeaders(), params: { department: 'Research Unit', team: filters.team !== 'All' ? filters.team : undefined } }),
        axios.get(`${API}/teams`, { headers: getAuthHeaders(), params: { department: 'Research Unit' } })
      ]);
      setEmployees(employeesRes.data);
      setTeams(teamsRes.data.filter(t => t.department === 'Research Unit'));
    } catch (error) {
      toast.error('Failed to load star rewards data');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/star-rewards`, { headers: getAuthHeaders(), params: { department: 'Research Unit', team: filters.team !== 'All' ? filters.team : undefined, month: filters.month, search: filters.search || undefined } });
      setEmployees(response.data);
      setCurrentPage(1);
      toast.success('Filters applied');
    } catch (error) {
      toast.error('Failed to apply filters');
    } finally {
      setLoading(false);
    }
  };

  const handleExportCSV = () => {
    let data, headers, filename;
    if (activeTab === 'employees') {
      headers = ['Name', 'Email', 'Team', 'Stars', 'Unsafe'];
      data = filteredEmployees.map(e => [e.name, e.email, e.team, e.stars, e.unsafe_count]);
      filename = `employees-star-rating-${filters.month}.csv`;
    } else {
      headers = ['Team', 'Members', 'Team Stars', 'Avg'];
      data = teamStats.map(t => [t.name, t.members, t.totalStars.toFixed(2), t.avgStars.toFixed(2)]);
      filename = `teams-star-rating-${filters.month}.csv`;
    }
    const csv = [headers, ...data].map(row => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = window.URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    toast.success('CSV exported');
  };

  const handleViewEmployee = async (employee) => {
    setSelectedEmployee(employee);
    setStarHistory([]);
    setLoadingHistory(true);
    setShowViewModal(true);
    try {
      const response = await axios.get(`${API}/star-rewards/history/${employee.id}`, { headers: getAuthHeaders() });
      setStarHistory(response.data);
    } catch (error) {
      setStarHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleAddStars = (employee) => {
    setSelectedEmployee(employee);
    setAddFormType('performance');
    setAddFormMonth(filters.month);
    setWeeklyData(getWeeksForMonth(filters.month));
    setSimpleFormData({ value: '', reason: '' });
    setShowAddForm(true);
  };

  const updateWeekData = (weekIndex, field, value) => {
    setWeeklyData(prev => { const updated = [...prev]; updated[weekIndex] = { ...updated[weekIndex], [field]: value }; return updated; });
  };

  const submitStars = async () => {
    try {
      if (addFormType === 'performance' || addFormType === 'learning') {
        const validWeeks = weeklyData.filter(w => w.value && w.reason);
        if (validWeeks.length === 0) { toast.error('Please fill at least one week'); return; }
        for (const week of validWeeks) {
          await axios.post(`${API}/star-rewards`, { employee_id: selectedEmployee.id, stars: parseInt(week.value), reason: week.reason, type: addFormType, week_number: week.week, from_date: week.fromDate, to_date: week.toDate }, { headers: getAuthHeaders() });
        }
        toast.success(`Stars awarded for ${validWeeks.length} week(s)`);
      } else {
        if (!simpleFormData.value || !simpleFormData.reason) { toast.error('Please fill value and reason'); return; }
        const stars = addFormType === 'unsafe' ? -Math.abs(parseInt(simpleFormData.value)) : parseInt(simpleFormData.value);
        await axios.post(`${API}/star-rewards`, { employee_id: selectedEmployee.id, stars, reason: simpleFormData.reason, type: addFormType }, { headers: getAuthHeaders() });
        toast.success('Stars recorded');
      }
      setShowAddForm(false);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to award stars');
    }
  };

  const canAddStars = ['hr'].includes(user?.role);
  const filteredEmployees = useMemo(() => employees.filter(e => !filters.search || e.name.toLowerCase().includes(filters.search.toLowerCase()) || e.email.toLowerCase().includes(filters.search.toLowerCase())), [employees, filters.search]);
  const paginatedEmployees = useMemo(() => { const start = (currentPage - 1) * tableFilters.pageSize; return filteredEmployees.slice(start, start + tableFilters.pageSize); }, [filteredEmployees, currentPage, tableFilters.pageSize]);
  const totalPages = Math.ceil(filteredEmployees.length / tableFilters.pageSize);
  const teamStats = useMemo(() => teams.map(team => { const teamEmployees = filteredEmployees.filter(e => e.team === team.name); const totalStars = teamEmployees.reduce((sum, e) => sum + (e.stars || 0), 0); return { ...team, members: teamEmployees.length || team.member_count || 0, totalStars, avgStars: teamEmployees.length > 0 ? totalStars / teamEmployees.length : 0, employees: teamEmployees }; }), [teams, filteredEmployees]);
  const totalStars = useMemo(() => filteredEmployees.reduce((sum, e) => sum + (e.stars || 0), 0), [filteredEmployees]);
  const topPerformer = useMemo(() => filteredEmployees.reduce((top, e) => (!top || (e.stars || 0) > (top.stars || 0)) ? e : top, null), [filteredEmployees]);

  // View History Modal
  const ViewHistoryModal = () => (
    <Dialog open={showViewModal} onOpenChange={setShowViewModal}>
      <DialogContent className="bg-[#fffdf7] max-w-2xl rounded-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3" style={{ fontFamily: 'Outfit' }}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg">
              <Star className="w-5 h-5 text-white fill-white" />
            </div>
            Star History - {selectedEmployee?.name}
          </DialogTitle>
          <DialogDescription>View award history and performance</DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="p-4 rounded-xl bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200/50">
              <p className="text-xs text-amber-600 uppercase tracking-wide font-medium">Total Stars</p>
              <p className={`text-2xl font-bold mt-1 ${(selectedEmployee?.stars || 0) >= 0 ? 'text-amber-600' : 'text-red-600'}`}>{selectedEmployee?.stars || 0}</p>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/50">
              <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">Unsafe Count</p>
              <p className="text-2xl font-bold text-red-500 mt-1">{selectedEmployee?.unsafe_count || 0}</p>
            </div>
          </div>
          {loadingHistory ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : starHistory.length === 0 ? (
            <p className="text-center text-slate-500 py-8">No history records found</p>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {starHistory.map((record) => (
                <div key={record.id} className="flex items-center justify-between p-3 rounded-xl bg-white border border-slate-100 hover:border-amber-200 transition-colors">
                  <div>
                    <p className="text-sm font-medium text-slate-900">{record.type}</p>
                    <p className="text-sm text-slate-600">{record.reason}</p>
                    <p className="text-xs text-slate-400 mt-1">{record.month}</p>
                  </div>
                  <Badge className={`${record.stars >= 0 ? 'bg-amber-100 text-amber-700 border-amber-200' : 'bg-red-100 text-red-700 border-red-200'}`}>
                    {record.stars > 0 ? `+${record.stars}` : record.stars} <Star className="w-3 h-3 ml-1 fill-current" />
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setShowViewModal(false)} className="rounded-lg">Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-3 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-slate-500 text-sm">Loading star rewards...</p>
        </div>
      </div>
    );
  }

  // ADD FORM VIEW
  if (showAddForm && selectedEmployee) {
    return (
      <>
        <ViewHistoryModal />
        <div className="space-y-6 animate-fade-in" data-testid="star-add-form">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button variant="ghost" onClick={() => setShowAddForm(false)} className="rounded-xl p-2" data-testid="back-btn">
                <ArrowLeft className="w-5 h-5" />
              </Button>
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg">
                <Award className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Award Stars</h1>
                <p className="text-sm text-slate-500">{selectedEmployee.name} • {addFormMonth}</p>
              </div>
            </div>
          </div>

          <div className="card-premium p-6">
            <div className="mb-6">
              <Label className="text-sm font-medium text-slate-700 mb-2 block">Award Type</Label>
              <Select value={addFormType} onValueChange={setAddFormType}>
                <SelectTrigger className="w-64 rounded-lg" data-testid="form-type-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="performance">Performance</SelectItem>
                  <SelectItem value="learning">Learning</SelectItem>
                  <SelectItem value="innovation">Innovation</SelectItem>
                  <SelectItem value="unsafe">Unsafe Conduct</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {(addFormType === 'performance' || addFormType === 'learning') && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mb-6">
                {weeklyData.map((week, index) => (
                  <div key={index} className="p-5 rounded-2xl bg-[#f8f6f0] border border-[#e8e4d9]">
                    <div className="flex items-center justify-between mb-4">
                      <span className="font-semibold text-[#e67e22] text-lg">Week {week.week}</span>
                      <span className="text-xs text-slate-400">{week.startDate} → {week.endDate}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-3 mb-4">
                      <div>
                        <Label className="text-sm text-slate-600 font-medium">From</Label>
                        <Input type="date" value={week.fromDate} onChange={(e) => updateWeekData(index, 'fromDate', e.target.value)} className="rounded-xl text-sm mt-1.5 bg-white border-slate-200" />
                      </div>
                      <div>
                        <Label className="text-sm text-slate-600 font-medium">To</Label>
                        <Input type="date" value={week.toDate} onChange={(e) => updateWeekData(index, 'toDate', e.target.value)} className="rounded-xl text-sm mt-1.5 bg-white border-slate-200" />
                      </div>
                    </div>
                    <div className="mb-4">
                      <Label className="text-sm text-slate-600 font-medium">Stars</Label>
                      <Input type="number" value={week.value} onChange={(e) => updateWeekData(index, 'value', e.target.value)} className="rounded-xl mt-1.5 bg-white border-slate-200" placeholder="0" data-testid={`week-${index}-value`} />
                    </div>
                    <div>
                      <Label className="text-sm text-slate-600 font-medium">Reason</Label>
                      <Textarea value={week.reason} onChange={(e) => updateWeekData(index, 'reason', e.target.value)} className="rounded-xl mt-1.5 min-h-[80px] bg-white border-slate-200 resize-none" placeholder="Enter reason..." data-testid={`week-${index}-reason`} />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {(addFormType === 'innovation' || addFormType === 'unsafe') && (
              <div className="max-w-md space-y-4 mb-6">
                <div>
                  <Label className="text-sm font-medium text-slate-700">Month</Label>
                  <Input type="month" value={addFormMonth} onChange={(e) => setAddFormMonth(e.target.value)} className="rounded-lg mt-1.5" data-testid="simple-month" />
                </div>
                <div>
                  <Label className="text-sm font-medium text-slate-700">Stars {addFormType === 'unsafe' && '(will be negative)'}</Label>
                  <Input type="number" value={simpleFormData.value} onChange={(e) => setSimpleFormData(prev => ({ ...prev, value: e.target.value }))} className="rounded-lg mt-1.5" placeholder="Enter value" data-testid="simple-value" />
                </div>
                <div>
                  <Label className="text-sm font-medium text-slate-700">Reason</Label>
                  <Textarea value={simpleFormData.reason} onChange={(e) => setSimpleFormData(prev => ({ ...prev, reason: e.target.value }))} className="rounded-lg mt-1.5 min-h-[100px]" placeholder="Enter reason..." data-testid="simple-reason" />
                </div>
              </div>
            )}

            <div className="flex gap-3 pt-4 border-t border-slate-100">
              <Button onClick={submitStars} className="bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white rounded-lg shadow-lg shadow-amber-500/20" data-testid="save-btn">
                <Star className="w-4 h-4 mr-2 fill-white" /> Save Stars
              </Button>
              <Button variant="outline" onClick={() => setShowAddForm(false)} className="rounded-lg" data-testid="cancel-btn">Cancel</Button>
            </div>
          </div>
        </div>
      </>
    );
  }

  // TEAM DETAILS VIEW
  if (showTeamDetails && selectedTeam) {
    return (
      <>
        <ViewHistoryModal />
        <div className="space-y-6 animate-fade-in" data-testid="team-details-view">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button variant="ghost" onClick={() => { setShowTeamDetails(false); setSelectedTeam(null); }} className="rounded-xl p-2">
                <ArrowLeft className="w-5 h-5" />
              </Button>
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg">
                <Users className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>{selectedTeam.name}</h1>
                <p className="text-sm text-slate-500">{selectedTeam.members} members • {selectedTeam.totalStars} total stars</p>
              </div>
            </div>
          </div>

          <div className="card-premium overflow-hidden">
            <div className="overflow-x-auto">
              <table className="table-premium">
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Email</th>
                    <th className="text-center">Stars</th>
                    <th className="text-center">Unsafe</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedTeam.employees?.length === 0 ? (
                    <tr><td colSpan="5" className="text-center py-12 text-slate-500">No team members found</td></tr>
                  ) : (
                    selectedTeam.employees?.map((emp) => (
                      <tr key={emp.id}>
                        <td>
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center">
                              <span className="text-white text-xs font-medium">{emp.name?.charAt(0)}</span>
                            </div>
                            <span className="font-medium text-slate-900">{emp.name}</span>
                          </div>
                        </td>
                        <td className="text-slate-600">{emp.email}</td>
                        <td className="text-center">
                          <Badge className={`${(emp.stars || 0) >= 0 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                            {emp.stars || 0} <Star className="w-3 h-3 ml-1 fill-current" />
                          </Badge>
                        </td>
                        <td className="text-center">{emp.unsafe_count > 0 ? <Badge className="badge-error">{emp.unsafe_count}</Badge> : <span className="text-slate-400">0</span>}</td>
                        <td>
                          <div className="flex gap-1">
                            <Button size="sm" variant="ghost" onClick={() => handleViewEmployee(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`view-history-${emp.id}`}>
                              <Eye className="w-4 h-4 text-slate-500" />
                            </Button>
                            {canAddStars && (
                              <Button size="sm" variant="ghost" onClick={() => handleAddStars(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`add-stars-${emp.id}`}>
                                <Plus className="w-4 h-4 text-amber-500" />
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </>
    );
  }

  // MAIN VIEW
  return (
    <>
      <ViewHistoryModal />
      <div className="space-y-6 animate-fade-in" data-testid="star-reward-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg shadow-amber-500/20">
              <Trophy className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Star Rewards</h1>
              <p className="text-sm text-slate-500">Research Unit • {filters.month}</p>
            </div>
          </div>
          <Button onClick={handleExportCSV} variant="outline" className="rounded-xl" data-testid="export-csv-btn">
            <Download className="w-4 h-4 mr-2" /> Export
          </Button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Total Stars', value: totalStars, icon: Star, gradient: 'from-amber-400 to-orange-500' },
            { label: 'Total Employees', value: filteredEmployees.length, icon: Users, gradient: 'from-blue-500 to-indigo-600' },
            { label: 'Teams', value: teams.length, icon: Users, gradient: 'from-emerald-500 to-teal-600' },
            { label: 'Top Performer', value: topPerformer?.name?.split(' ')[0] || '-', icon: Trophy, gradient: 'from-purple-500 to-pink-500', subValue: topPerformer ? `${topPerformer.stars} stars` : '' },
          ].map((stat, i) => (
            <div key={i} className="stat-card">
              <div className="flex items-center gap-4">
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${stat.gradient} flex items-center justify-center shadow-lg`}>
                  <stat.icon className="w-6 h-6 text-white" strokeWidth={1.5} />
                </div>
                <div>
                  <p className="text-2xl font-bold text-slate-900 number-display">{stat.value}</p>
                  <p className="text-xs text-slate-500">{stat.label}</p>
                  {stat.subValue && <p className="text-xs text-amber-600 font-medium">{stat.subValue}</p>}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="card-flat p-6">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <Label className="text-sm text-slate-600 mb-1.5 block">Team</Label>
              <Select value={filters.team} onValueChange={(v) => setFilters({ ...filters, team: v })}>
                <SelectTrigger className="w-40 rounded-lg" data-testid="filter-team"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="All">All Teams</SelectItem>
                  {teams.map((team) => <SelectItem key={team.id} value={team.name}>{team.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-sm text-slate-600 mb-1.5 block">Month</Label>
              <MonthPicker value={filters.month} onChange={(v) => setFilters({ ...filters, month: v })} className="w-36" data-testid="filter-month" />
            </div>
            <div>
              <Label className="text-sm text-slate-600 mb-1.5 block">Search</Label>
              <Input placeholder="Name or email..." value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })} className="w-48 rounded-lg" data-testid="filter-search" />
            </div>
            <Button onClick={handleApply} className="bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white rounded-lg shadow-lg shadow-amber-500/20" data-testid="apply-btn">
              Apply
            </Button>
          </div>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="bg-slate-100 p-1 rounded-xl">
            <TabsTrigger value="employees" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm px-6" data-testid="tab-employees">
              <Users className="w-4 h-4 mr-2" /> Employees
            </TabsTrigger>
            <TabsTrigger value="teams" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm px-6" data-testid="tab-teams">
              <Award className="w-4 h-4 mr-2" /> Teams
            </TabsTrigger>
          </TabsList>

          <TabsContent value="employees" className="mt-4">
            {/* View Toggle */}
            <div className="flex justify-end mb-4">
              <div className="flex rounded-lg overflow-hidden border border-slate-200">
                <Button variant={viewMode === 'table' ? 'default' : 'ghost'} onClick={() => setViewMode('table')} className={`rounded-none px-4 ${viewMode === 'table' ? 'bg-[#063c88] text-white' : ''}`} size="sm">Table</Button>
                <Button variant={viewMode === 'grid' ? 'default' : 'ghost'} onClick={() => setViewMode('grid')} className={`rounded-none px-4 ${viewMode === 'grid' ? 'bg-[#063c88] text-white' : ''}`} size="sm">Grid</Button>
              </div>
            </div>

            {viewMode === 'table' ? (
              <div className="card-premium overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="table-premium">
                    <thead>
                      <tr>
                        <th>Employee</th>
                        <th>Email</th>
                        <th>Team</th>
                        <th className="text-center">Stars</th>
                        <th className="text-center">Unsafe</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paginatedEmployees.length === 0 ? (
                        <tr><td colSpan="6" className="text-center py-12 text-slate-500">No employees found</td></tr>
                      ) : (
                        paginatedEmployees.map((emp) => (
                          <tr key={emp.id}>
                            <td>
                              <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center">
                                  <span className="text-white text-xs font-medium">{emp.name?.charAt(0)}</span>
                                </div>
                                <span className="font-medium text-slate-900">{emp.name}</span>
                              </div>
                            </td>
                            <td className="text-slate-600">{emp.email}</td>
                            <td className="text-slate-600">{emp.team}</td>
                            <td className="text-center">
                              <Badge className={`${(emp.stars || 0) >= 0 ? 'bg-amber-100 text-amber-700 border-amber-200' : 'bg-red-100 text-red-700 border-red-200'}`}>
                                {emp.stars || 0} <Star className="w-3 h-3 ml-1 fill-current" />
                              </Badge>
                            </td>
                            <td className="text-center">{emp.unsafe_count > 0 ? <Badge className="badge-error">{emp.unsafe_count}</Badge> : <span className="text-slate-400">0</span>}</td>
                            <td>
                              <div className="flex gap-1">
                                <Button size="sm" variant="ghost" onClick={() => handleViewEmployee(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`view-history-${emp.id}`}>
                                  <Eye className="w-4 h-4 text-slate-500" />
                                </Button>
                                {canAddStars && (
                                  <Button size="sm" variant="ghost" onClick={() => handleAddStars(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`add-stars-${emp.id}`}>
                                    <Plus className="w-4 h-4 text-amber-500" />
                                  </Button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
                {filteredEmployees.length > 0 && (
                  <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50">
                    <div className="flex items-center gap-4">
                      <p className="text-sm text-slate-500">
                        Showing {filteredEmployees.length === 0 ? 0 : ((currentPage - 1) * tableFilters.pageSize) + 1}–{Math.min(currentPage * tableFilters.pageSize, filteredEmployees.length)} of {filteredEmployees.length}
                      </p>
                      <PageSizeSelector
                        value={tableFilters.pageSize}
                        onChange={(v) => { setTableFilters(prev => ({ ...prev, pageSize: v })); setCurrentPage(1); }}
                        testId="star-reward-rows-per-page"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="outline" disabled={currentPage <= 1} onClick={() => setCurrentPage(p => p - 1)} className="rounded-lg">Prev</Button>
                      <span className="text-sm text-slate-600 px-3">Page {currentPage} of {totalPages}</span>
                      <Button size="sm" variant="outline" disabled={currentPage >= totalPages} onClick={() => setCurrentPage(p => p + 1)} className="rounded-lg">Next</Button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {paginatedEmployees.map((emp, index) => (
                  <div key={emp.id} className="p-5 rounded-xl bg-gradient-to-br from-[#fffdf7] to-amber-50/30 border border-amber-200/30 hover:border-amber-300 hover:shadow-lg transition-all animate-slide-up" style={{ animationDelay: `${index * 0.03}s` }}>
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg">
                          <span className="text-white text-lg font-bold">{emp.name?.charAt(0)}</span>
                        </div>
                        <div>
                          <p className="font-semibold text-slate-900">{emp.name}</p>
                          <p className="text-xs text-slate-500">{emp.team}</p>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between pt-4 border-t border-amber-200/50">
                      <div className="flex items-center gap-2">
                        <Star className="w-5 h-5 text-amber-500 fill-amber-500" />
                        <span className={`text-xl font-bold ${(emp.stars || 0) >= 0 ? 'text-amber-600' : 'text-red-600'}`}>{emp.stars || 0}</span>
                      </div>
                      <div className="flex gap-1">
                        <Button size="sm" variant="ghost" onClick={() => handleViewEmployee(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`grid-view-${emp.id}`}>
                          <Eye className="w-4 h-4 text-slate-500" />
                        </Button>
                        {canAddStars && (
                          <Button size="sm" variant="ghost" onClick={() => handleAddStars(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`grid-add-${emp.id}`}>
                            <Plus className="w-4 h-4 text-amber-500" />
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="teams" className="mt-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {teamStats.map((team, index) => (
                <div key={team.id} className="p-5 rounded-xl bg-gradient-to-br from-[#fffdf7] to-amber-50/30 border border-amber-200/30 hover:border-amber-300 hover:shadow-lg transition-all animate-slide-up" style={{ animationDelay: `${index * 0.05}s` }}>
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="font-semibold text-lg text-slate-900" style={{ fontFamily: 'Outfit' }}>{team.name}</h3>
                      <p className="text-xs text-slate-500">{team.members} members</p>
                    </div>
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg">
                      <Users className="w-5 h-5 text-white" />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div className="p-3 rounded-lg bg-white/70">
                      <p className="text-xs text-slate-500">Total Stars</p>
                      <p className="text-xl font-bold text-amber-600">{team.totalStars.toFixed(0)}</p>
                    </div>
                    <div className="p-3 rounded-lg bg-white/70">
                      <p className="text-xs text-slate-500">Avg / Member</p>
                      <p className="text-xl font-bold text-slate-900">{team.avgStars.toFixed(1)}</p>
                    </div>
                  </div>
                  <Button onClick={() => { setSelectedTeam(team); setShowTeamDetails(true); }} className="w-full bg-white/80 hover:bg-white text-slate-700 border border-amber-200 rounded-lg" data-testid={`view-team-${team.id}`}>
                    <Eye className="w-4 h-4 mr-2" /> View Members
                  </Button>
                </div>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
};

export default StarReward;
