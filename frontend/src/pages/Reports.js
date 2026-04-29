import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { FileText, Download, RotateCcw, FileBarChart, FileSpreadsheet } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { DatePicker } from '../components/ui/date-picker';
import { EmployeeAutocomplete } from '../components/EmployeeAutocomplete';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Reports = () => {
  const { getAuthHeaders } = useAuth();
  const [activeTab, setActiveTab] = useState('leave');
  const [teams, setTeams] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState([]);
  
  const [leaveFilters, setLeaveFilters] = useState({ fromDate: '', toDate: '', empName: '', team: 'All', leaveType: 'All', department: 'All' });
  const [attendanceFilters, setAttendanceFilters] = useState({ fromDate: '', toDate: '', empName: '', team: 'All', status: 'All', department: 'All' });

  useEffect(() => { fetchTeamsAndDepts(); }, []);

  const fetchTeamsAndDepts = async () => {
    try {
      const [teamsRes, deptsRes] = await Promise.all([
        axios.get(`${API}/teams`, { headers: getAuthHeaders() }),
        axios.get(`${API}/departments`, { headers: getAuthHeaders() })
      ]);
      setTeams(teamsRes.data);
      setDepartments(deptsRes.data);
    } catch (error) {
      console.error('Failed to load teams/departments');
    }
  };

  const handleExport = async () => {
    try {
      setLoading(true);
      const filters = activeTab === 'leave' ? leaveFilters : attendanceFilters;

      // Attendance: download wide-pivot XLSX directly from backend (matches reference template)
      if (activeTab === 'attendance') {
        if (!filters.fromDate || !filters.toDate) {
          toast.error('Please select From and To dates');
          setLoading(false);
          return;
        }
        const params = {
          from_date: filters.fromDate,
          to_date: filters.toDate,
          employee_name: filters.empName || undefined,
          team: filters.team !== 'All' ? filters.team : undefined,
          department: filters.department !== 'All' ? filters.department : undefined,
          status: filters.status !== 'All' ? filters.status : undefined,
        };
        const resp = await axios.get(`${API}/reports/attendance/export`, {
          headers: getAuthHeaders(),
          params,
          responseType: 'blob',
        });
        const blob = new Blob([resp.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
        const a = document.createElement('a');
        a.href = window.URL.createObjectURL(blob);
        a.download = `attendance_report_${filters.fromDate}_to_${filters.toDate}.xlsx`;
        a.click();
        // Also fetch JSON for on-screen preview (lightweight)
        try {
          const previewParams = { ...params };
          const previewResp = await axios.get(`${API}/reports/attendance`, { headers: getAuthHeaders(), params: previewParams });
          setReportData(previewResp.data);
        } catch (_) { /* preview optional */ }
        toast.success('Attendance report exported');
        setLoading(false);
        return;
      }

      // Leave report: existing CSV path (untouched)
      const endpoint = '/reports/leaves';
      const params = {
        from_date: filters.fromDate || undefined,
        to_date: filters.toDate || undefined,
        employee_name: filters.empName || undefined,
        team: filters.team !== 'All' ? filters.team : undefined,
        department: filters.department !== 'All' ? filters.department : undefined,
        leave_type: filters.leaveType !== 'All' ? filters.leaveType : undefined,
      };

      const response = await axios.get(`${API}${endpoint}`, { headers: getAuthHeaders(), params });
      setReportData(response.data);
      
      if (response.data.length > 0) {
        const headers = ['Employee', 'Team', 'Department', 'Type', 'Start', 'End', 'Duration', 'Status'];
        const rows = response.data.map(r => [r.emp_name, r.team, r.department || '', r.leave_type, r.start_date, r.end_date, r.duration, r.status]);
        // CSV-safe quoting (preserves commas and quotes within cells)
        const esc = (v) => {
          const s = (v === null || v === undefined) ? '' : String(v);
          return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
        };
        const csv = [headers, ...rows].map(row => row.map(esc).join(',')).join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const a = document.createElement('a');
        a.href = window.URL.createObjectURL(blob);
        a.download = `${activeTab}-report-${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        toast.success('Report exported successfully');
      } else {
        toast.info('No data found for selected filters');
      }
    } catch (error) {
      toast.error('Failed to export report');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    if (activeTab === 'leave') setLeaveFilters({ fromDate: '', toDate: '', empName: '', team: 'All', leaveType: 'All', department: 'All' });
    else setAttendanceFilters({ fromDate: '', toDate: '', empName: '', team: 'All', status: 'All', department: 'All' });
    setReportData([]);
    toast.info('Filters reset');
  };

  const getStatusBadge = (status) => {
    const styles = {
      'Login': 'badge-success', 'Completed': 'badge-info', 'Present': 'badge-success',
      'Not Logged': 'badge-neutral', 'Late Login': 'badge-warning', 'Early Out': 'badge-error',
      'Loss of Pay': 'badge-error', 'Leave': 'bg-purple-50 text-purple-700 border border-purple-200/50',
      'pending': 'badge-warning', 'approved': 'badge-success', 'rejected': 'badge-error'
    };
    return styles[status] || 'badge-neutral';
  };

  return (
    <div className="space-y-6 animate-fade-in" data-testid="reports-page">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
          <FileText className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>HRMS Reports</h1>
          <p className="text-sm text-slate-500">Generate and export reports</p>
        </div>
      </div>

      {/* Tab Buttons */}
      <div className="flex gap-2">
        <Button
          onClick={() => { setActiveTab('leave'); setReportData([]); }}
          className={`rounded-xl px-6 ${activeTab === 'leave' ? 'bg-[#063c88] text-white shadow-lg shadow-[#063c88]/20' : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'}`}
          data-testid="tab-leave"
        >
          <FileSpreadsheet className="w-4 h-4 mr-2" /> Leave Report
        </Button>
        <Button
          onClick={() => { setActiveTab('attendance'); setReportData([]); }}
          className={`rounded-xl px-6 ${activeTab === 'attendance' ? 'bg-[#063c88] text-white shadow-lg shadow-[#063c88]/20' : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'}`}
          data-testid="tab-attendance"
        >
          <FileBarChart className="w-4 h-4 mr-2" /> Attendance Report
        </Button>
      </div>

      {/* Filters */}
      <div className="card-premium p-8">
        <h3 className="text-lg font-semibold text-slate-900 mb-6" style={{ fontFamily: 'Outfit' }}>
          {activeTab === 'leave' ? 'Leave Report Filters' : 'Attendance Report Filters'}
        </h3>
        
        {activeTab === 'leave' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div>
              <label className="text-sm text-slate-600 mb-2 block font-medium">From Date</label>
              <DatePicker value={leaveFilters.fromDate} onChange={(val) => setLeaveFilters({ ...leaveFilters, fromDate: val })} placeholder="Select date" data-testid="leave-filter-from" />
            </div>
            <div>
              <label className="text-sm text-slate-600 mb-2 block font-medium">Employee Name</label>
              <EmployeeAutocomplete
                value={leaveFilters.empName}
                onChange={(val) => setLeaveFilters({ ...leaveFilters, empName: val })}
                onSelect={(emp) => setLeaveFilters({ ...leaveFilters, empName: emp.full_name })}
                placeholder="Type to search employees..."
                data-testid="leave-filter-empname"
              />
            </div>
            <div>
              <label className="text-sm text-slate-600 mb-2 block font-medium">Leave Type</label>
              <Select value={leaveFilters.leaveType} onValueChange={(v) => setLeaveFilters({ ...leaveFilters, leaveType: v })}>
                <SelectTrigger className="rounded-lg" data-testid="leave-filter-type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="All">All Types</SelectItem>
                  <SelectItem value="Sick">Sick</SelectItem>
                  <SelectItem value="Preplanned">Preplanned</SelectItem>
                  <SelectItem value="Emergency">Emergency</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm text-slate-600 mb-2 block font-medium">To Date</label>
              <DatePicker value={leaveFilters.toDate} onChange={(val) => setLeaveFilters({ ...leaveFilters, toDate: val })} placeholder="Select date" data-testid="leave-filter-to" />
            </div>
            <div>
              <label className="text-sm text-slate-600 mb-2 block font-medium">Team</label>
              <Select value={leaveFilters.team} onValueChange={(v) => setLeaveFilters({ ...leaveFilters, team: v })}>
                <SelectTrigger className="rounded-lg" data-testid="leave-filter-team"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="All">All Teams</SelectItem>
                  {teams.map((team) => <SelectItem key={team.id} value={team.name}>{team.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm text-slate-600 mb-2 block font-medium">Department</label>
              <Select value={leaveFilters.department} onValueChange={(v) => setLeaveFilters({ ...leaveFilters, department: v })}>
                <SelectTrigger className="rounded-lg" data-testid="leave-filter-dept"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="All">All Departments</SelectItem>
                  {departments.map((dept) => <SelectItem key={dept.id} value={dept.name}>{dept.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div>
              <label className="text-sm text-slate-600 mb-2 block font-medium">From Date</label>
              <DatePicker value={attendanceFilters.fromDate} onChange={(val) => setAttendanceFilters({ ...attendanceFilters, fromDate: val })} placeholder="Select date" data-testid="attendance-filter-from" />
            </div>
            <div>
              <label className="text-sm text-slate-600 mb-2 block font-medium">Employee Name</label>
              <EmployeeAutocomplete
                value={attendanceFilters.empName}
                onChange={(val) => setAttendanceFilters({ ...attendanceFilters, empName: val })}
                onSelect={(emp) => setAttendanceFilters({ ...attendanceFilters, empName: emp.full_name })}
                placeholder="Type to search employees..."
                data-testid="attendance-filter-empname"
              />
            </div>
            <div>
              <label className="text-sm text-slate-600 mb-2 block font-medium">Status</label>
              <Select value={attendanceFilters.status} onValueChange={(v) => setAttendanceFilters({ ...attendanceFilters, status: v })}>
                <SelectTrigger className="rounded-lg" data-testid="attendance-filter-status"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="All">All Status</SelectItem>
                  <SelectItem value="Login">Login</SelectItem>
                  <SelectItem value="Logout">Logout</SelectItem>
                  <SelectItem value="Late">Late</SelectItem>
                  <SelectItem value="Leave">Leave</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm text-slate-600 mb-2 block font-medium">To Date</label>
              <DatePicker value={attendanceFilters.toDate} onChange={(val) => setAttendanceFilters({ ...attendanceFilters, toDate: val })} placeholder="Select date" data-testid="attendance-filter-to" />
            </div>
            <div>
              <label className="text-sm text-slate-600 mb-2 block font-medium">Team</label>
              <Select value={attendanceFilters.team} onValueChange={(v) => setAttendanceFilters({ ...attendanceFilters, team: v })}>
                <SelectTrigger className="rounded-lg" data-testid="attendance-filter-team"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="All">All Teams</SelectItem>
                  {teams.map((team) => <SelectItem key={team.id} value={team.name}>{team.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm text-slate-600 mb-2 block font-medium">Department</label>
              <Select value={attendanceFilters.department} onValueChange={(v) => setAttendanceFilters({ ...attendanceFilters, department: v })}>
                <SelectTrigger className="rounded-lg" data-testid="attendance-filter-dept"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="All">All Departments</SelectItem>
                  {departments.map((dept) => <SelectItem key={dept.id} value={dept.name}>{dept.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
        )}

        <div className="flex justify-end gap-4 mt-8 pt-6 border-t border-slate-100">
          <Button onClick={handleReset} variant="outline" className="rounded-lg px-6" data-testid="reset-btn">
            <RotateCcw className="w-4 h-4 mr-2" /> Reset
          </Button>
          <Button onClick={handleExport} disabled={loading} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg px-6 shadow-lg shadow-[#063c88]/20" data-testid="export-btn">
            {loading ? <div className="w-4 h-4 mr-2 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
            {loading ? 'Exporting...' : 'Export'}
          </Button>
        </div>
      </div>

      {/* Results */}
      {reportData.length > 0 && (
        <div className="card-premium overflow-hidden">
          <div className="p-6 border-b border-slate-100 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900" style={{ fontFamily: 'Outfit' }}>
              {activeTab === 'leave' ? 'Leave' : 'Attendance'} Report Results
            </h3>
            <Badge className="bg-[#063c88]/10 text-[#063c88] border-0 px-3 py-1">{reportData.length} records</Badge>
          </div>
          <div className="overflow-x-auto">
            <table className="table-premium">
              <thead>
                {activeTab === 'attendance' ? (
                  <tr>
                    <th>Employee</th>
                    <th>Team</th>
                    <th>Date</th>
                    <th>Check-In</th>
                    <th>Check-Out</th>
                    <th>Status</th>
                  </tr>
                ) : (
                  <tr>
                    <th>Employee</th>
                    <th>Team</th>
                    <th>Type</th>
                    <th>Start Date</th>
                    <th>End Date</th>
                    <th>Duration</th>
                    <th>Status</th>
                  </tr>
                )}
              </thead>
              <tbody>
                {activeTab === 'attendance' ? (
                  reportData.map((record, index) => (
                    <tr key={index}>
                      <td className="font-medium text-slate-900">{record.emp_name}</td>
                      <td className="text-slate-600">{record.team}</td>
                      <td className="text-slate-600">{record.date}</td>
                      <td className="text-slate-600">{record.check_in || '-'}</td>
                      <td className="text-slate-600">{record.check_out || '-'}</td>
                      <td><Badge className={getStatusBadge(record.status)}>{record.status}</Badge></td>
                    </tr>
                  ))
                ) : (
                  reportData.map((record, index) => (
                    <tr key={index}>
                      <td className="font-medium text-slate-900">{record.emp_name}</td>
                      <td className="text-slate-600">{record.team}</td>
                      <td className="text-slate-600">{record.leave_type}</td>
                      <td className="text-slate-600">{record.start_date}</td>
                      <td className="text-slate-600">{record.end_date}</td>
                      <td className="text-slate-600">{record.duration}</td>
                      <td><Badge className={getStatusBadge(record.status)}>{record.status}</Badge></td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default Reports;
