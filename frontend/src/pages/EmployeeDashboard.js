import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { CalendarCheck, CalendarX, Clock, Clock4, AlertTriangle, CalendarDays, User, FileText, Star, TrendingUp, Activity } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EmployeeDashboard = () => {
  const { getAuthHeaders, user } = useAuth();
  const navigate = useNavigate();
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [currentTime, setCurrentTime] = useState(new Date());

  // Mock working hours data for chart
  const [workingHoursData] = useState([
    { day: 'Mon', hours: 8.5 },
    { day: 'Tue', hours: 9.2 },
    { day: 'Wed', hours: 7.8 },
    { day: 'Thu', hours: 8.0 },
    { day: 'Fri', hours: 8.7 },
    { day: 'Sat', hours: 4.0 },
    { day: 'Sun', hours: 0 },
  ]);

  const fetchDashboard = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/employee/dashboard`, { headers: getAuthHeaders() });
      setDashboardData(response.data);
    } catch (error) {
      toast.error('Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);
  useEffect(() => { const timer = setInterval(() => setCurrentTime(new Date()), 1000); return () => clearInterval(timer); }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-3 border-[#063c88] border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-slate-500 text-sm">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  const todayStatus = dashboardData?.today_attendance;
  const isCompleted = todayStatus?.status === 'Completed' || todayStatus?.check_out;

  return (
    <div className="space-y-6 animate-fade-in" data-testid="employee-dashboard">
      {/* Welcome Section */}
      <div className="card-premium p-6 bg-gradient-to-r from-[#063c88] to-[#0a5cba] text-white relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2" />
        <div className="relative z-10">
          <h1 className="text-2xl lg:text-3xl font-bold" style={{ fontFamily: 'Outfit' }}>
            Good {currentTime.getHours() < 12 ? 'Morning' : currentTime.getHours() < 17 ? 'Afternoon' : 'Evening'}, {user?.name?.split(' ')[0]}!
          </h1>
          <p className="text-white/80 mt-1">
            {currentTime.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
          </p>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Present Days', value: dashboardData?.attendance_summary?.present || 0, icon: CalendarCheck, color: 'blue' },
          { label: 'Leave Taken', value: dashboardData?.attendance_summary?.leaves || 0, icon: CalendarX, color: 'amber' },
          { label: 'Absent', value: dashboardData?.attendance_summary?.absent || 0, icon: AlertTriangle, color: 'red' },
          { label: 'This Month', value: `${Math.round((dashboardData?.attendance_summary?.present || 0) / 22 * 100)}%`, icon: TrendingUp, color: 'blue' },
        ].map((stat, i) => (
          <div key={i} className="stat-card">
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-xl bg-${stat.color}-100 flex items-center justify-center`}>
                <stat.icon className={`w-6 h-6 text-${stat.color}-600`} strokeWidth={1.5} />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900 number-display">{stat.value}</p>
                <p className="text-xs text-slate-500">{stat.label}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Clock In/Out Card */}
        <div className="lg:col-span-1">
          <div className="card-premium p-6 h-full">
            <h3 className="text-lg font-semibold text-slate-900 mb-6" style={{ fontFamily: 'Outfit' }}>Time Tracker</h3>
            
            {/* Digital Clock */}
            <div className="text-center mb-6">
              <div className="text-4xl font-bold text-slate-900 number-display" style={{ fontFamily: 'JetBrains Mono' }}>
                {currentTime.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </div>
              <p className="text-sm text-slate-500 mt-1">
                {currentTime.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
              </p>
            </div>

            {/* Today's Status */}
            <div className="p-4 rounded-xl bg-slate-50 mb-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-slate-500">Check-in</span>
                <span className="text-sm font-medium text-slate-900">{todayStatus?.check_in || '--:--'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-500">Check-out</span>
                <span className="text-sm font-medium text-slate-900">{todayStatus?.check_out || '--:--'}</span>
              </div>
            </div>

            {/* Attendance is biometric-based only — manual check-in disabled */}
            {isCompleted ? (
              <div className="text-center p-4 rounded-xl bg-blue-50 border border-blue-200" data-testid="day-completed-card">
                <CalendarCheck className="w-8 h-8 text-[#063c88] mx-auto mb-2" />
                <p className="text-[#063c88] font-medium">Day Completed</p>
                <p className="text-xs text-blue-600 mt-1">Great work today!</p>
              </div>
            ) : (
              <div className="text-center p-4 rounded-xl bg-slate-50 border border-slate-200" data-testid="biometric-only-card">
                <Clock4 className="w-8 h-8 text-slate-500 mx-auto mb-2" />
                <p className="text-slate-700 font-medium">Biometric Attendance</p>
                <p className="text-xs text-slate-500 mt-1">Your check-in/out is synced from the biometric device</p>
              </div>
            )}
          </div>
        </div>

        {/* Working Hours Chart */}
        <div className="lg:col-span-2">
          <div className="card-premium p-6 h-full">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-semibold text-slate-900" style={{ fontFamily: 'Outfit' }}>Working Hours This Week</h3>
                <p className="text-sm text-slate-500">Daily breakdown</p>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Activity className="w-4 h-4 text-[#3271ec]" />
                <span className="text-slate-600">Avg: 7.5 hrs</span>
              </div>
            </div>
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={workingHoursData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorHours" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3271ec" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#3271ec" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
                  <Tooltip contentStyle={{ backgroundColor: 'white', border: 'none', borderRadius: '12px', boxShadow: '0 4px 20px rgba(0,0,0,0.1)' }} />
                  <Area type="monotone" dataKey="hours" stroke="#3271ec" strokeWidth={2} fillOpacity={1} fill="url(#colorHours)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Links */}
      <div className="card-flat p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4" style={{ fontFamily: 'Outfit' }}>Quick Actions</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'My Attendance', icon: CalendarCheck, path: '/employee/attendance' },
            { label: 'Apply Leave', icon: CalendarDays, path: '/employee/leave' },
            { label: 'My Profile', icon: User, path: '/employee/profile' },
            { label: 'Policies', icon: FileText, path: '#' },
          ].map((link, i) => (
            <button
              key={i}
              onClick={() => navigate(link.path)}
              className="p-4 rounded-xl bg-white border border-slate-100 hover:border-[#063c88]/30 hover:shadow-md transition-all flex items-center gap-3"
              data-testid={`quick-link-${link.label.toLowerCase().replace(/\s/g, '-')}`}
            >
              <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                <link.icon className="w-5 h-5 text-[#063c88]" />
              </div>
              <span className="text-sm font-medium text-slate-700">{link.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Leave Balance */}
      {dashboardData?.leave_balance && (
        <div className="card-premium p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4" style={{ fontFamily: 'Outfit' }}>Leave Balance</h3>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'Sick Leave', used: dashboardData.leave_balance.sick_used || 0, total: dashboardData.leave_balance.sick_total || 12 },
              { label: 'Casual Leave', used: dashboardData.leave_balance.casual_used || 0, total: dashboardData.leave_balance.casual_total || 12 },
              { label: 'Annual Leave', used: dashboardData.leave_balance.annual_used || 0, total: dashboardData.leave_balance.annual_total || 15 },
            ].map((leave, i) => (
              <div key={i} className="p-4 rounded-xl bg-slate-50">
                <p className="text-sm text-slate-500 mb-2">{leave.label}</p>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-bold text-slate-900">{leave.total - leave.used}</span>
                  <span className="text-sm text-slate-500">/ {leave.total}</span>
                </div>
                <div className="h-2 bg-slate-200 rounded-full mt-2 overflow-hidden">
                  <div className="h-full bg-[#063c88] rounded-full" style={{ width: `${((leave.total - leave.used) / leave.total) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default EmployeeDashboard;
