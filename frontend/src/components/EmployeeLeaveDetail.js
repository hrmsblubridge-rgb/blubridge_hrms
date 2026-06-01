import { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import EmployeeAvatar from './EmployeeAvatar';
import {
  X,
  Calendar,
  CalendarDays,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  TrendingUp,
  Briefcase,
  ChevronLeft,
  ChevronRight,
  LayoutGrid,
  List,
  Filter
} from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Legend,
  PieChart,
  Pie
} from 'recharts';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Color scheme for different statuses
const STATUS_COLORS = {
  present: '#10b981',
  leave: '#ef4444',
  halfDay: '#f59e0b',
  holiday: '#3b82f6',
  weekOff: '#6b7280',
  lop: '#dc2626',
  absent: '#9ca3af'
};

const LEAVE_TYPE_COLORS = {
  'Sick': '#ef4444',
  'Emergency': '#f97316',
  'Preplanned': '#8b5cf6',
  'Casual': '#06b6d4',
  'Paid': '#10b981',
  'Unpaid': '#6b7280'
};

const EmployeeLeaveDetail = ({ employee, onClose }) => {
  const { getAuthHeaders } = useAuth();
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState('month'); // day, week, month
  const [currentDate, setCurrentDate] = useState(new Date());
  const [leaveTypeFilter, setLeaveTypeFilter] = useState('All');
  const [attendanceData, setAttendanceData] = useState([]);
  const [leaveData, setLeaveData] = useState([]);
  const [employeeDetails, setEmployeeDetails] = useState(null);

  // Month names for display
  const months = ['January', 'February', 'March', 'April', 'May', 'June', 
                  'July', 'August', 'September', 'October', 'November', 'December'];

  useEffect(() => {
    if (employee) {
      fetchData();
    }
  }, [employee, currentDate]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const year = currentDate.getFullYear();
      const month = currentDate.getMonth() + 1;
      
      // Calculate date range for the current view
      const startDate = `01-${String(month).padStart(2, '0')}-${year}`;
      const lastDay = new Date(year, month, 0).getDate();
      const endDate = `${String(lastDay).padStart(2, '0')}-${String(month).padStart(2, '0')}-${year}`;

      const [attendanceRes, leavesRes, employeeRes] = await Promise.all([
        axios.get(`${API}/attendance`, {
          headers: getAuthHeaders(),
          params: {
            employee_name: employee.emp_name || employee.full_name,
            from_date: startDate,
            to_date: endDate
          }
        }),
        axios.get(`${API}/leaves`, {
          headers: getAuthHeaders(),
          params: {
            employee_name: employee.emp_name || employee.full_name
          }
        }),
        employee.employee_id ? 
          axios.get(`${API}/employees/${employee.employee_id}`, { headers: getAuthHeaders() }) :
          Promise.resolve({ data: employee })
      ]);

      setAttendanceData(attendanceRes.data);
      setLeaveData(leavesRes.data);
      setEmployeeDetails(employeeRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Failed to load employee data');
    } finally {
      setLoading(false);
    }
  };

  // Navigate months
  const navigateMonth = (direction) => {
    const newDate = new Date(currentDate);
    newDate.setMonth(newDate.getMonth() + direction);
    setCurrentDate(newDate);
  };

  // Calculate summary statistics
  const summary = useMemo(() => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth() + 1;
    
    // Filter leaves for current month
    const monthLeaves = leaveData.filter(leave => {
      if (!leave.start_date) return false;
      const leaveDate = new Date(leave.start_date);
      return leaveDate.getFullYear() === year && leaveDate.getMonth() + 1 === month;
    });

    const approved = monthLeaves.filter(l => l.status === 'approved').length;
    const pending = monthLeaves.filter(l => l.status === 'pending').length;
    const rejected = monthLeaves.filter(l => l.status === 'rejected').length;
    
    // Calculate from attendance
    const presentDays = attendanceData.filter(a => 
      ['Present', 'Completed', 'Login'].includes(a.status)
    ).length;
    
    const lopDays = attendanceData.filter(a => a.is_lop || a.status === 'Loss of Pay').length;
    const lateDays = attendanceData.filter(a => a.status === 'Late Login').length;
    const earlyOutDays = attendanceData.filter(a => a.status === 'Early Out').length;

    // Calculate remaining leaves (assuming 12 annual leaves as standard)
    const totalAnnualLeaves = 12;
    const totalApprovedLeaves = leaveData.filter(l => l.status === 'approved').length;
    const remainingLeaves = Math.max(0, totalAnnualLeaves - totalApprovedLeaves);

    return {
      totalLeaves: monthLeaves.length,
      approved,
      pending,
      rejected,
      presentDays,
      lopDays,
      lateDays,
      earlyOutDays,
      remainingLeaves,
      totalApprovedLeaves
    };
  }, [attendanceData, leaveData, currentDate]);

  // Generate calendar data for monthly view
  const calendarData = useMemo(() => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const firstDayOfWeek = new Date(year, month, 1).getDay();
    
    const days = [];
    
    // Add empty cells for days before the first day of month
    for (let i = 0; i < firstDayOfWeek; i++) {
      days.push({ day: null, status: null });
    }
    
    // Add days of the month
    for (let day = 1; day <= daysInMonth; day++) {
      const dateStr = `${String(day).padStart(2, '0')}-${String(month + 1).padStart(2, '0')}-${year}`;
      const dayOfWeek = new Date(year, month, day).getDay();
      
      // Check if Sunday (week off)
      if (dayOfWeek === 0) {
        days.push({ day, status: 'weekOff', label: 'Week Off', date: dateStr });
        continue;
      }
      
      // Find attendance record for this day
      const attendance = attendanceData.find(a => a.date === dateStr);
      
      // Find leave record for this day
      const leave = leaveData.find(l => {
        if (!l.start_date || !l.end_date) return false;
        const start = new Date(l.start_date);
        const end = new Date(l.end_date);
        const current = new Date(year, month, day);
        return current >= start && current <= end && l.status === 'approved';
      });

      let status = 'absent';
      let label = 'No Record';
      let details = null;

      if (attendance) {
        if (attendance.is_lop || attendance.status === 'Loss of Pay') {
          status = 'lop';
          label = 'LOP';
          details = attendance.lop_reason;
        } else if (['Present', 'Completed'].includes(attendance.status)) {
          status = 'present';
          label = 'Present';
          details = `${attendance.check_in || '-'} - ${attendance.check_out || '-'}`;
        } else if (attendance.status === 'Login') {
          status = 'present';
          label = 'Logged In';
          details = `Check-in: ${attendance.check_in || '-'}`;
        } else if (attendance.status === 'Late Login') {
          status = 'halfDay';
          label = 'Late Login';
          details = attendance.lop_reason;
        } else if (attendance.status === 'Early Out') {
          status = 'halfDay';
          label = 'Early Out';
          details = attendance.lop_reason;
        } else if (attendance.status === 'Leave') {
          status = 'leave';
          label = 'On Leave';
        } else {
          status = 'absent';
          label = attendance.status || 'Absent';
        }
      } else if (leave) {
        status = 'leave';
        label = leave.leave_type;
        details = leave.reason;
      }

      days.push({ day, status, label, details, date: dateStr, attendance, leave });
    }
    
    return days;
  }, [attendanceData, leaveData, currentDate]);

  // Generate bar chart data for monthly view
  const monthlyChartData = useMemo(() => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    
    const data = [];
    for (let day = 1; day <= daysInMonth; day++) {
      const dateStr = `${String(day).padStart(2, '0')}-${String(month + 1).padStart(2, '0')}-${year}`;
      const dayOfWeek = new Date(year, month, day).getDay();
      
      const attendance = attendanceData.find(a => a.date === dateStr);
      const leave = leaveData.find(l => {
        if (!l.start_date || !l.end_date) return false;
        const start = new Date(l.start_date);
        const end = new Date(l.end_date);
        const current = new Date(year, month, day);
        return current >= start && current <= end && l.status === 'approved';
      });

      let status = 'absent';
      if (dayOfWeek === 0) {
        status = 'weekOff';
      } else if (attendance) {
        if (attendance.is_lop || attendance.status === 'Loss of Pay') {
          status = 'lop';
        } else if (['Present', 'Completed', 'Login'].includes(attendance.status)) {
          status = 'present';
        } else if (['Late Login', 'Early Out'].includes(attendance.status)) {
          status = 'halfDay';
        } else if (attendance.status === 'Leave') {
          status = 'leave';
        }
      } else if (leave) {
        status = 'leave';
      }

      data.push({
        day: String(day),
        date: dateStr,
        status,
        value: status === 'weekOff' ? 0 : 1,
        present: status === 'present' ? 1 : 0,
        leave: status === 'leave' ? 1 : 0,
        halfDay: status === 'halfDay' ? 1 : 0,
        lop: status === 'lop' ? 1 : 0,
        weekOff: status === 'weekOff' ? 1 : 0,
        absent: status === 'absent' ? 1 : 0
      });
    }
    
    return data;
  }, [attendanceData, leaveData, currentDate]);

  // Weekly chart data
  const weeklyChartData = useMemo(() => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    
    const weeks = [];
    let weekNum = 1;
    let weekData = { week: `Week ${weekNum}`, present: 0, leave: 0, lop: 0, weekOff: 0, absent: 0 };
    
    for (let day = 1; day <= daysInMonth; day++) {
      const dateStr = `${String(day).padStart(2, '0')}-${String(month + 1).padStart(2, '0')}-${year}`;
      const dayOfWeek = new Date(year, month, day).getDay();
      
      // Start new week on Sunday
      if (dayOfWeek === 0 && day > 1) {
        weeks.push(weekData);
        weekNum++;
        weekData = { week: `Week ${weekNum}`, present: 0, leave: 0, lop: 0, weekOff: 0, absent: 0 };
      }
      
      if (dayOfWeek === 0) {
        weekData.weekOff++;
        continue;
      }
      
      const attendance = attendanceData.find(a => a.date === dateStr);
      const leave = leaveData.find(l => {
        if (!l.start_date || !l.end_date) return false;
        const start = new Date(l.start_date);
        const end = new Date(l.end_date);
        const current = new Date(year, month, day);
        return current >= start && current <= end && l.status === 'approved';
      });

      if (attendance) {
        if (attendance.is_lop || attendance.status === 'Loss of Pay' || 
            attendance.status === 'Late Login' || attendance.status === 'Early Out') {
          weekData.lop++;
        } else if (['Present', 'Completed', 'Login'].includes(attendance.status)) {
          weekData.present++;
        } else if (attendance.status === 'Leave') {
          weekData.leave++;
        } else {
          weekData.absent++;
        }
      } else if (leave) {
        weekData.leave++;
      } else {
        weekData.absent++;
      }
    }
    
    // Push the last week
    weeks.push(weekData);
    
    return weeks;
  }, [attendanceData, leaveData, currentDate]);

  // Filter leave data by type
  const filteredLeaveLog = useMemo(() => {
    if (leaveTypeFilter === 'All') return leaveData;
    return leaveData.filter(l => l.leave_type === leaveTypeFilter);
  }, [leaveData, leaveTypeFilter]);

  // Custom tooltip for charts
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-3 rounded-lg shadow-lg border border-slate-200">
          <p className="font-semibold text-slate-900 mb-1">{label}</p>
          {payload.map((entry, index) => (
            <p key={index} className="text-sm" style={{ color: entry.color }}>
              {entry.name}: {entry.value}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  // Get status badge style
  const getStatusBadgeClass = (status) => {
    const classes = {
      'approved': 'bg-emerald-100 text-emerald-700',
      'pending': 'bg-amber-100 text-amber-700',
      'rejected': 'bg-red-100 text-red-700'
    };
    return classes[status] || 'bg-slate-100 text-slate-700';
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="leave-detail-loading">
        <div className="bg-[#fffdf7] rounded-2xl p-8 flex items-center gap-4">
          <div className="w-8 h-8 border-3 border-[#063c88] border-t-transparent rounded-full animate-spin" />
          <span className="text-slate-600">Loading employee data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 animate-fade-in" data-testid="employee-leave-detail-modal">
      <div className="bg-[#efede5] rounded-2xl w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl">
        {/* Header */}
        <div className="bg-gradient-to-r from-[#063c88] to-[#0a5cba] p-6 text-white relative">
          <button 
            onClick={onClose}
            className="absolute right-4 top-4 p-2 hover:bg-white/10 rounded-lg transition-colors"
            data-testid="close-leave-detail-btn"
          >
            <X className="w-5 h-5" />
          </button>
          
          <div className="flex items-center gap-4">
            <EmployeeAvatar
              employeeId={employee.id || employee.employee_id}
              name={employee.emp_name || employee.full_name}
              size="lg"
              shape="square"
              className="bg-white/20 backdrop-blur-sm ring-2 ring-white/30"
            />
            <div>
              <h2 className="text-2xl font-bold" style={{ fontFamily: 'Outfit' }} data-testid="employee-detail-name">
                {employee.emp_name || employee.full_name}
              </h2>
              <div className="flex items-center gap-4 mt-1 text-white/80 text-sm">
                <span className="flex items-center gap-1">
                  <Briefcase className="w-4 h-4" />
                  {employeeDetails?.emp_id || employee.emp_id || 'N/A'}
                </span>
                <span>{employeeDetails?.department || employee.department}</span>
                <span>{employeeDetails?.designation || employee.designation || 'Employee'}</span>
              </div>
            </div>
          </div>

          {/* Month Navigation */}
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-white/20">
            <button 
              onClick={() => navigateMonth(-1)}
              className="flex items-center gap-1 hover:bg-white/10 px-3 py-1.5 rounded-lg transition-colors"
              data-testid="prev-month-btn"
            >
              <ChevronLeft className="w-4 h-4" />
              <span className="text-sm">Previous</span>
            </button>
            <div className="flex items-center gap-2">
              <Calendar className="w-5 h-5" />
              <span className="text-lg font-semibold" data-testid="current-month-display">
                {months[currentDate.getMonth()]} {currentDate.getFullYear()}
              </span>
            </div>
            <button 
              onClick={() => navigateMonth(1)}
              className="flex items-center gap-1 hover:bg-white/10 px-3 py-1.5 rounded-lg transition-colors"
              data-testid="next-month-btn"
            >
              <span className="text-sm">Next</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* KPI Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4" data-testid="leave-summary-cards">
            {[
              { label: 'Total Leaves Taken', value: summary.totalApprovedLeaves, icon: CalendarDays, color: 'red' },
              { label: 'Remaining Leaves', value: summary.remainingLeaves, icon: TrendingUp, color: 'emerald' },
              { label: 'Approved This Month', value: summary.approved, icon: CheckCircle2, color: 'blue' },
              { label: 'Pending Requests', value: summary.pending, icon: Clock, color: 'amber' },
              { label: 'LOP Days', value: summary.lopDays, icon: AlertCircle, color: 'slate' }
            ].map((stat, i) => (
              <div key={i} className="card-flat p-4" data-testid={`summary-card-${stat.label.toLowerCase().replace(/\s+/g, '-')}`}>
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl bg-${stat.color}-100 flex items-center justify-center`}>
                    <stat.icon className={`w-5 h-5 text-${stat.color}-600`} />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-slate-900 number-display">{stat.value}</p>
                    <p className="text-xs text-slate-500 leading-tight">{stat.label}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Filters & View Toggle */}
          <div className="card-flat p-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <Filter className="w-4 h-4 text-slate-400" />
                <span className="text-sm text-slate-600 font-medium">View:</span>
                <Tabs value={viewMode} onValueChange={setViewMode} className="w-auto">
                  <TabsList className="bg-slate-100 h-9">
                    <TabsTrigger value="day" className="text-xs px-3 data-[state=active]:bg-[#063c88] data-[state=active]:text-white" data-testid="view-day-btn">
                      Day
                    </TabsTrigger>
                    <TabsTrigger value="week" className="text-xs px-3 data-[state=active]:bg-[#063c88] data-[state=active]:text-white" data-testid="view-week-btn">
                      Week
                    </TabsTrigger>
                    <TabsTrigger value="month" className="text-xs px-3 data-[state=active]:bg-[#063c88] data-[state=active]:text-white" data-testid="view-month-btn">
                      Month
                    </TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>
              
              <div className="flex items-center gap-3">
                <span className="text-sm text-slate-600 font-medium">Leave Type:</span>
                <Select value={leaveTypeFilter} onValueChange={setLeaveTypeFilter}>
                  <SelectTrigger className="w-[140px] h-9 rounded-lg text-sm" data-testid="leave-type-filter">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="All">All Types</SelectItem>
                    <SelectItem value="Sick">Sick Leave</SelectItem>
                    <SelectItem value="Emergency">Emergency</SelectItem>
                    <SelectItem value="Preplanned">Preplanned</SelectItem>
                    <SelectItem value="Casual">Casual Leave</SelectItem>
                    <SelectItem value="Paid">Paid Leave</SelectItem>
                    <SelectItem value="Unpaid">Unpaid Leave</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          {/* Visualization Section */}
          <div className="card-premium p-6" data-testid="leave-visualization-section">
            <h3 className="text-lg font-semibold text-slate-900 mb-4" style={{ fontFamily: 'Outfit' }}>
              {viewMode === 'month' ? 'Monthly Attendance Overview' : 
               viewMode === 'week' ? 'Weekly Summary' : 'Daily Calendar View'}
            </h3>

            {/* Monthly Bar Chart View */}
            {viewMode === 'month' && (
              <div className="h-[300px]" data-testid="monthly-chart">
                <ResponsiveContainer width="100%" height="100%" minWidth={100} minHeight={100}>
                  <BarChart data={monthlyChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                    <XAxis 
                      dataKey="day" 
                      tick={{ fontSize: 10, fill: '#64748b' }}
                      axisLine={{ stroke: '#e2e8f0' }}
                    />
                    <YAxis 
                      tick={{ fontSize: 10, fill: '#64748b' }}
                      axisLine={{ stroke: '#e2e8f0' }}
                      domain={[0, 1]}
                      ticks={[0, 1]}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {monthlyChartData.map((entry, index) => (
                        <Cell 
                          key={`cell-${index}`} 
                          fill={STATUS_COLORS[entry.status] || STATUS_COLORS.absent}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                
                {/* Legend */}
                <div className="flex flex-wrap justify-center gap-4 mt-4">
                  {[
                    { label: 'Present', color: STATUS_COLORS.present },
                    { label: 'Leave', color: STATUS_COLORS.leave },
                    { label: 'Half Day/Late', color: STATUS_COLORS.halfDay },
                    { label: 'LOP', color: STATUS_COLORS.lop },
                    { label: 'Week Off', color: STATUS_COLORS.weekOff },
                    { label: 'Absent', color: STATUS_COLORS.absent }
                  ].map((item, i) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <div className="w-3 h-3 rounded" style={{ backgroundColor: item.color }} />
                      <span className="text-xs text-slate-600">{item.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Weekly Grouped Bar Chart View */}
            {viewMode === 'week' && (
              <div className="h-[300px]" data-testid="weekly-chart">
                <ResponsiveContainer width="100%" height="100%" minWidth={100} minHeight={100}>
                  <BarChart data={weeklyChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                    <XAxis 
                      dataKey="week" 
                      tick={{ fontSize: 11, fill: '#64748b' }}
                      axisLine={{ stroke: '#e2e8f0' }}
                    />
                    <YAxis 
                      tick={{ fontSize: 11, fill: '#64748b' }}
                      axisLine={{ stroke: '#e2e8f0' }}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend 
                      wrapperStyle={{ fontSize: '12px' }}
                      iconType="circle"
                    />
                    <Bar dataKey="present" name="Present" fill={STATUS_COLORS.present} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="leave" name="Leave" fill={STATUS_COLORS.leave} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="lop" name="LOP" fill={STATUS_COLORS.lop} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="weekOff" name="Week Off" fill={STATUS_COLORS.weekOff} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Daily Calendar/Timeline View */}
            {viewMode === 'day' && (
              <div className="grid grid-cols-7 gap-2" data-testid="daily-calendar">
                {/* Day headers */}
                {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day, i) => (
                  <div key={day} className="text-center text-xs font-semibold text-slate-500 py-2">
                    {day}
                  </div>
                ))}
                
                {/* Calendar days */}
                {calendarData.map((dayData, i) => (
                  <div 
                    key={i}
                    className={`
                      aspect-square p-1 rounded-lg transition-all cursor-pointer
                      ${dayData.day ? 'hover:scale-105' : ''}
                      ${dayData.status === 'present' ? 'bg-emerald-100 border border-emerald-200' : ''}
                      ${dayData.status === 'leave' ? 'bg-red-100 border border-red-200' : ''}
                      ${dayData.status === 'halfDay' ? 'bg-amber-100 border border-amber-200' : ''}
                      ${dayData.status === 'lop' ? 'bg-red-200 border border-red-300' : ''}
                      ${dayData.status === 'weekOff' ? 'bg-slate-100 border border-slate-200' : ''}
                      ${dayData.status === 'absent' ? 'bg-slate-50 border border-slate-100' : ''}
                      ${!dayData.day ? 'bg-transparent' : ''}
                    `}
                    title={dayData.details || dayData.label}
                    data-testid={dayData.day ? `calendar-day-${dayData.day}` : undefined}
                  >
                    {dayData.day && (
                      <div className="h-full flex flex-col items-center justify-center">
                        <span className={`text-sm font-medium ${
                          dayData.status === 'weekOff' ? 'text-slate-400' : 'text-slate-700'
                        }`}>
                          {dayData.day}
                        </span>
                        <span className={`text-[9px] leading-tight text-center ${
                          dayData.status === 'present' ? 'text-emerald-600' :
                          dayData.status === 'leave' ? 'text-red-600' :
                          dayData.status === 'halfDay' ? 'text-amber-600' :
                          dayData.status === 'lop' ? 'text-red-700' :
                          dayData.status === 'weekOff' ? 'text-slate-400' :
                          'text-slate-400'
                        }`}>
                          {dayData.label?.substring(0, 6)}
                        </span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Detailed Leave Log Table */}
          <div className="card-premium overflow-hidden" data-testid="leave-log-section">
            <div className="p-4 border-b border-slate-100 bg-slate-50/50">
              <h3 className="text-lg font-semibold text-slate-900" style={{ fontFamily: 'Outfit' }}>
                Leave History Log
              </h3>
            </div>
            
            {filteredLeaveLog.length === 0 ? (
              <div className="p-12 text-center" data-testid="no-leave-records">
                <CalendarDays className="w-12 h-12 mx-auto text-slate-300 mb-3" />
                <p className="text-slate-500">No leave records found for this period</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="table-premium">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Leave Type</th>
                      <th>Duration</th>
                      <th>Reason</th>
                      <th>Status</th>
                      <th>Approved By</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredLeaveLog.map((leave, index) => (
                      <tr 
                        key={leave.id || index}
                        className="hover:bg-slate-50/80 transition-colors"
                        data-testid={`leave-row-${index}`}
                      >
                        <td className="text-slate-900 font-medium">
                          {leave.start_date}
                          {leave.end_date && leave.end_date !== leave.start_date && (
                            <span className="text-slate-400"> - {leave.end_date}</span>
                          )}
                        </td>
                        <td>
                          <Badge 
                            className="text-xs"
                            style={{ 
                              backgroundColor: `${LEAVE_TYPE_COLORS[leave.leave_type] || '#6b7280'}20`,
                              color: LEAVE_TYPE_COLORS[leave.leave_type] || '#6b7280'
                            }}
                          >
                            {leave.leave_type}
                          </Badge>
                        </td>
                        <td className="text-slate-600">{leave.duration}</td>
                        <td className="text-slate-600 max-w-[200px] truncate" title={leave.reason}>
                          {leave.reason || '-'}
                        </td>
                        <td>
                          <Badge className={getStatusBadgeClass(leave.status)}>
                            {leave.status}
                          </Badge>
                        </td>
                        <td className="text-slate-600">{leave.approved_by_name || (leave.approved_by ? 'System' : '-')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default EmployeeLeaveDetail;
