import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Download, DollarSign, Users, AlertTriangle, Calendar, Wallet, TrendingUp } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { MonthPicker } from '../components/ui/month-picker';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Payroll = () => {
  const { getAuthHeaders } = useAuth();
  const [payrollData, setPayrollData] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('attendance');
  const [selectedMonth, setSelectedMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });

  const getDaysInMonth = () => {
    const [year, month] = selectedMonth.split('-').map(Number);
    const daysInMonth = new Date(year, month, 0).getDate();
    const days = [];
    for (let d = 1; d <= daysInMonth; d++) {
      const date = new Date(year, month - 1, d);
      days.push({
        day: d,
        dayName: date.toLocaleDateString('en-US', { weekday: 'short' }),
        isSunday: date.getDay() === 0,
        date: `${String(d).padStart(2, '0')}-${String(month).padStart(2, '0')}-${year}`
      });
    }
    return days;
  };

  const days = getDaysInMonth();

  // Scroll sync refs for top + bottom horizontal scrollbars
  const topScrollRef = useRef(null);
  const tableScrollRef = useRef(null);
  const isSyncing = useRef(false);

  const handleTopScroll = useCallback(() => {
    if (isSyncing.current) return;
    isSyncing.current = true;
    if (tableScrollRef.current && topScrollRef.current) {
      tableScrollRef.current.scrollLeft = topScrollRef.current.scrollLeft;
    }
    isSyncing.current = false;
  }, []);

  const handleTableScroll = useCallback(() => {
    if (isSyncing.current) return;
    isSyncing.current = true;
    if (topScrollRef.current && tableScrollRef.current) {
      topScrollRef.current.scrollLeft = tableScrollRef.current.scrollLeft;
    }
    isSyncing.current = false;
  }, []);

  // Keep top scrollbar width in sync with actual table width
  const [tableWidth, setTableWidth] = useState(0);
  useEffect(() => {
    const updateWidth = () => {
      if (tableScrollRef.current) {
        setTableWidth(tableScrollRef.current.scrollWidth);
      }
    };
    updateWidth();
    const timer = setTimeout(updateWidth, 500);
    return () => clearTimeout(timer);
  }, [payrollData, selectedMonth]);

  const formatMonthDisplay = () => {
    const [year, month] = selectedMonth.split('-').map(Number);
    const monthName = new Date(year, month - 1, 1).toLocaleDateString('en-US', { month: 'long' });
    return `${monthName} ${year}`;
  };

  useEffect(() => { fetchData(); }, [selectedMonth]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const headers = getAuthHeaders();
      const [payrollRes, summaryRes] = await Promise.all([
        axios.get(`${API}/payroll`, { headers, params: { month: selectedMonth } }),
        axios.get(`${API}/payroll/summary/${selectedMonth}`, { headers })
      ]);
      setPayrollData(payrollRes.data || []);
      setSummary(summaryRes.data || null);
    } catch (error) {
      toast.error('Failed to load payroll data');
    } finally {
      setLoading(false);
    }
  };

  const getStatusDisplay = (status, isLop) => {
    // New payroll engine status codes
    if (status === 'PF') return { code: 'PF', color: 'text-emerald-600 font-semibold', bg: '' };
    if (status === 'PH') return { code: 'PH', color: 'text-blue-600 font-semibold', bg: 'bg-blue-50' };
    if (status === 'PA') return { code: 'PA', color: 'text-emerald-500 font-semibold', bg: 'bg-emerald-50' };
    if (status === 'WO') return { code: 'WO', color: 'text-slate-400', bg: 'bg-slate-50' };
    if (status === 'OH') return { code: 'OH', color: 'text-indigo-500', bg: 'bg-indigo-50' };
    if (status === 'LC') return { code: 'LC', color: 'text-orange-600 font-semibold', bg: 'bg-orange-50' };
    if (status === 'MP') return { code: 'MP', color: 'text-yellow-600 font-semibold', bg: 'bg-yellow-50' };
    if (status === 'LOP') return { code: 'LOP', color: 'text-red-600 font-bold', bg: 'bg-red-50' };
    if (status === 'R') return { code: 'R', color: 'text-gray-500', bg: 'bg-gray-100' };
    if (status === 'BLANK') return { code: '', color: '', bg: 'bg-gray-50' };
    if (status === 'H') return { code: 'H', color: 'text-indigo-500', bg: 'bg-indigo-50' };
    if (status === 'Su') return { code: 'Su', color: 'text-slate-400', bg: 'bg-slate-50' };
    // Legacy codes (backward compatibility)
    if (status === 'Sunday') return { code: 'Su', color: 'text-slate-400', bg: 'bg-slate-50' };
    if (isLop || status === 'Loss of Pay') return { code: 'LOP', color: 'text-red-600 font-bold', bg: 'bg-red-50' };
    if (status === 'Present' || status === 'Completed') return { code: 'P', color: 'text-emerald-600 font-semibold', bg: '' };
    if (status === 'Late Login' || status === 'Early Out') return { code: 'LOP', color: 'text-red-600 font-bold', bg: 'bg-red-50' };
    if (status === 'Leave') return { code: 'L', color: 'text-purple-600 font-semibold', bg: 'bg-purple-50' };
    if (status === 'Absent') return { code: 'A', color: 'text-amber-600 font-semibold', bg: 'bg-amber-50' };
    return { code: '-', color: 'text-slate-400', bg: '' };
  };

  const handleExportCSV = () => {
    let headers, rows, filename;
    if (activeTab === 'attendance') {
      headers = ['Sl.No', 'Emp ID', 'Name', 'Shift', ...days.map(d => `${String(d.day).padStart(2, '0')} ${d.dayName}`), 'Total Days', 'Working Days', 'Weekoff Pay', 'Extra Pay', 'LOP', 'Payable Days'];
      rows = payrollData.map((emp, i) => {
        const dayStatuses = days.map(day => {
          const detail = emp.attendance_details?.find(a => a.date === day.date);
          return getStatusDisplay(detail?.status, detail?.is_lop).code;
        });
        return [i + 1, emp.emp_id, emp.emp_name, emp.shift_type, ...dayStatuses, emp.total_days, emp.working_days, emp.weekoff_pay, emp.extra_pay, emp.lop, emp.final_payable_days];
      });
      filename = `payroll-attendance-${selectedMonth}.csv`;
    } else {
      headers = ['Sl.No', 'Emp ID', 'Name', 'Salary', 'Working Days', 'Present', 'LOP', 'Deduction', 'Net'];
      rows = payrollData.map((emp, i) => [i + 1, emp.emp_id, emp.emp_name, emp.monthly_salary, emp.working_days, emp.present_days, emp.lop_days, emp.lop_deduction, emp.net_salary]);
      filename = `payroll-salary-${selectedMonth}.csv`;
    }
    const csv = [headers, ...rows].map(row => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = window.URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    toast.success('CSV exported');
  };

  // Chart data for salary distribution
  const chartData = payrollData.slice(0, 10).map(emp => ({
    name: emp.emp_name?.split(' ')[0] || 'N/A',
    salary: emp.net_salary || 0,
    deduction: emp.lop_deduction || 0
  }));

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-3 border-[#063c88] border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-slate-500 text-sm">Loading payroll data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="payroll-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
            <Wallet className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Payroll Management</h1>
            <p className="text-sm text-slate-500">{formatMonthDisplay()}</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <MonthPicker value={selectedMonth} onChange={setSelectedMonth} className="w-44" data-testid="month-select" />
          <Button onClick={handleExportCSV} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-xl shadow-lg shadow-[#063c88]/20" data-testid="export-csv-btn">
            <Download className="w-4 h-4 mr-2" /> Export CSV
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          {[
            { label: 'Total Employees', value: summary.total_employees, icon: Users, color: 'blue' },
            { label: 'Total Salary', value: `₹${summary.total_salary?.toLocaleString()}`, icon: DollarSign, color: 'emerald' },
            { label: 'LOP Deductions', value: `₹${summary.total_deductions?.toLocaleString()}`, icon: AlertTriangle, color: 'red', isNeg: true },
            { label: 'Net Payable', value: `₹${summary.total_net_salary?.toLocaleString()}`, icon: TrendingUp, color: 'teal' },
            { label: 'Total LOP Days', value: summary.total_lop_days, icon: Calendar, color: 'amber' },
          ].map((stat, i) => (
            <div key={i} className="stat-card">
              <div className="flex items-center gap-4">
                <div className={`w-12 h-12 rounded-xl bg-${stat.color}-100 flex items-center justify-center`}>
                  <stat.icon className={`w-6 h-6 text-${stat.color}-600`} />
                </div>
                <div>
                  <p className={`text-xl font-bold number-display ${stat.isNeg ? 'text-red-600' : 'text-slate-900'}`}>{stat.value}</p>
                  <p className="text-xs text-slate-500">{stat.label}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Chart */}
      {chartData.length > 0 && (
        <div className="card-premium p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4" style={{ fontFamily: 'Outfit' }}>Salary Distribution (Top 10)</h3>
          <div className="h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#64748b' }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#64748b' }} />
                <Tooltip contentStyle={{ backgroundColor: 'white', border: 'none', borderRadius: '12px', boxShadow: '0 4px 20px rgba(0,0,0,0.1)' }} />
                <Bar dataKey="salary" radius={[4, 4, 0, 0]}>
                  {chartData.map((_, index) => <Cell key={index} fill={index % 2 === 0 ? '#063c88' : '#10b981'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-slate-100 p-1 rounded-xl">
          <TabsTrigger value="attendance" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm px-6">Attendance View</TabsTrigger>
          <TabsTrigger value="salary" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm px-6">Salary View</TabsTrigger>
        </TabsList>

        <TabsContent value="attendance" className="mt-4">
          <div className="card-premium overflow-hidden">
            {/* Top horizontal scrollbar */}
            <div
              ref={topScrollRef}
              onScroll={handleTopScroll}
              className="overflow-x-auto"
              style={{ height: '16px' }}
              data-testid="top-scrollbar"
            >
              <div style={{ width: tableWidth || '100%', height: '1px' }} />
            </div>
            <div className="overflow-x-auto" ref={tableScrollRef} onScroll={handleTableScroll}>
              <table className="w-full border-collapse min-w-max">
                <thead>
                  <tr className="bg-gradient-to-r from-slate-100 to-slate-50">
                    <th className="px-3 py-3 text-left text-xs font-semibold text-slate-600 sticky left-0 bg-slate-100 z-10 w-[50px]">Sl</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold text-slate-600 sticky left-[50px] bg-slate-100 z-10 min-w-[140px]">Name</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold text-slate-600 sticky left-[190px] bg-slate-100 z-10 min-w-[80px]">Shift</th>
                    {days.map((day) => (
                      <th key={day.day} className={`px-1 py-2 text-center text-xs font-medium min-w-[36px] ${day.isSunday ? 'bg-slate-50 text-slate-400' : 'text-slate-600'}`}>
                        <div>{String(day.day).padStart(2, '0')}</div>
                        <div className="text-[10px]">{day.dayName}</div>
                      </th>
                    ))}
                    <th className="px-2 py-3 text-center text-[11px] font-semibold text-slate-700 bg-slate-200 min-w-[62px] whitespace-nowrap">Total Days</th>
                    <th className="px-2 py-3 text-center text-[11px] font-semibold text-blue-700 bg-blue-50 min-w-[68px] whitespace-nowrap">Working Days</th>
                    <th className="px-2 py-3 text-center text-[11px] font-semibold text-indigo-700 bg-indigo-50 min-w-[72px] whitespace-nowrap">Weekoff Pay</th>
                    <th className="px-2 py-3 text-center text-[11px] font-semibold text-teal-700 bg-teal-50 min-w-[62px] whitespace-nowrap">Extra Pay</th>
                    <th className="px-2 py-3 text-center text-[11px] font-semibold text-red-700 bg-red-50 min-w-[44px] whitespace-nowrap">LOP</th>
                    <th className="px-2 py-3 text-center text-[11px] font-semibold text-emerald-700 bg-emerald-100 min-w-[76px] whitespace-nowrap">Payable Days</th>
                  </tr>
                </thead>
                <tbody>
                  {payrollData.length === 0 ? (
                    <tr><td colSpan={9 + days.length} className="px-4 py-12 text-center text-slate-500">No employees found</td></tr>
                  ) : (
                    payrollData.map((emp, index) => (
                      <tr key={emp.employee_id} className="border-t border-slate-100 hover:bg-slate-50/50">
                        <td className="px-3 py-2 text-sm text-slate-600 sticky left-0 bg-white z-10">{index + 1}</td>
                        <td className="px-3 py-2 sticky left-[50px] bg-white z-10">
                          <div className="text-sm font-medium text-slate-900">{emp.emp_name}</div>
                          <div className="text-xs text-slate-500">{emp.emp_id}</div>
                        </td>
                        <td className="px-3 py-2 text-xs text-slate-600 sticky left-[190px] bg-white z-10">{emp.shift_type}</td>
                        {days.map((day) => {
                          const detail = emp.attendance_details?.find(a => a.date === day.date);
                          const status = getStatusDisplay(detail?.status, detail?.is_lop);
                          return (
                            <td key={day.day} className={`px-1 py-2 text-center text-xs ${status.bg} ${day.isSunday ? 'bg-slate-50' : ''}`}>
                              <span className={status.color}>{status.code}</span>
                            </td>
                          );
                        })}
                        <td className="px-3 py-2 text-center text-sm font-medium text-slate-700 bg-slate-50">{emp.total_days}</td>
                        <td className="px-3 py-2 text-center text-sm font-medium text-blue-600 bg-blue-50">{emp.working_days}</td>
                        <td className="px-3 py-2 text-center text-sm font-medium text-indigo-600 bg-indigo-50">{emp.weekoff_pay}</td>
                        <td className="px-3 py-2 text-center text-sm font-medium text-teal-600 bg-teal-50">{emp.extra_pay}</td>
                        <td className="px-3 py-2 text-center text-sm font-semibold text-red-600 bg-red-50">{emp.lop > 0 ? emp.lop : <span className="text-slate-400">0</span>}</td>
                        <td className="px-3 py-2 text-center text-sm font-bold text-emerald-700 bg-emerald-100">{emp.final_payable_days}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
          <div className="flex flex-wrap gap-4 text-xs mt-4">
            {[
              { code: 'PF', label: 'Present Full', color: 'emerald' },
              { code: 'PH', label: 'Present Half', color: 'blue' },
              { code: 'PA', label: 'Present (Approved Leave)', color: 'emerald' },
              { code: 'WO', label: 'Week Off', color: 'slate' },
              { code: 'OH', label: 'Office Holiday', color: 'indigo' },
              { code: 'LC', label: 'Late Coming', color: 'orange' },
              { code: 'LOP', label: 'Loss of Pay', color: 'red' },
              { code: 'MP', label: 'Missed Punch', color: 'yellow' },
              { code: 'A', label: 'Absent', color: 'amber' },
              { code: 'Su', label: 'Sunday (Future)', color: 'slate' },
              { code: 'H', label: 'Holiday (Future)', color: 'indigo' },
              { code: 'R', label: 'Relieved', color: 'gray' },
            ].map((item, i) => (
              <div key={i} className="flex items-center gap-1">
                <span className={`text-${item.color}-600 font-semibold`}>{item.code}</span>
                <span className="text-slate-600">- {item.label}</span>
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="salary" className="mt-4">
          <div className="card-premium overflow-hidden">
            <div className="overflow-x-auto">
              <table className="table-premium">
                <thead className="bg-gradient-to-r from-slate-100 to-slate-50">
                  <tr>
                    <th>Sl</th>
                    <th>Employee</th>
                    <th>Department</th>
                    <th className="text-right">Monthly Salary</th>
                    <th className="text-center">Working</th>
                    <th className="text-center text-emerald-700">Present</th>
                    <th className="text-center text-red-700">LOP</th>
                    <th className="text-center">Leave</th>
                    <th className="text-center">Absent</th>
                    <th className="text-right text-red-700">Deduction</th>
                    <th className="text-right text-emerald-700">Net Salary</th>
                  </tr>
                </thead>
                <tbody>
                  {payrollData.length === 0 ? (
                    <tr><td colSpan="11" className="text-center py-12 text-slate-500">No payroll data found</td></tr>
                  ) : (
                    payrollData.map((emp, index) => (
                      <tr key={emp.employee_id}>
                        <td className="text-slate-600">{index + 1}</td>
                        <td>
                          <div className="font-medium text-slate-900">{emp.emp_name}</div>
                          <div className="text-xs text-slate-500">{emp.emp_id}</div>
                        </td>
                        <td className="text-slate-600">{emp.department}</td>
                        <td className="text-right font-medium">₹{emp.monthly_salary?.toLocaleString()}</td>
                        <td className="text-center text-slate-600">{emp.working_days}</td>
                        <td className="text-center text-emerald-600 font-semibold">{emp.present_days}</td>
                        <td className="text-center">
                          {emp.lop_days > 0 ? <Badge className="badge-error">{emp.lop_days}</Badge> : <span className="text-slate-400">0</span>}
                        </td>
                        <td className="text-center text-purple-600">{emp.leave_days}</td>
                        <td className="text-center text-amber-600">{emp.absent_days}</td>
                        <td className="text-right font-semibold text-red-600">{emp.lop_deduction > 0 ? `-₹${emp.lop_deduction?.toLocaleString()}` : '-'}</td>
                        <td className="text-right font-bold text-emerald-600">₹{emp.net_salary?.toLocaleString()}</td>
                      </tr>
                    ))
                  )}
                </tbody>
                {payrollData.length > 0 && (
                  <tfoot className="bg-slate-50 font-semibold">
                    <tr>
                      <td colSpan="3" className="text-right">Total:</td>
                      <td className="text-right">₹{summary?.total_salary?.toLocaleString()}</td>
                      <td className="text-center">-</td>
                      <td className="text-center text-emerald-600">{summary?.total_present_days}</td>
                      <td className="text-center text-red-600">{summary?.total_lop_days}</td>
                      <td colSpan="2"></td>
                      <td className="text-right text-red-600">-₹{summary?.total_deductions?.toLocaleString()}</td>
                      <td className="text-right text-emerald-600">₹{summary?.total_net_salary?.toLocaleString()}</td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </div>
          <div className="mt-4 p-4 bg-amber-50 rounded-xl border border-amber-200">
            <h3 className="font-semibold text-amber-800 mb-2 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" /> Payroll Calculation Rules
            </h3>
            <ul className="text-sm text-amber-700 space-y-1 list-disc list-inside">
              <li><strong>Late Coming (LC):</strong> Unapproved late = LOP 0.5 day</li>
              <li><strong>Half Day (PH):</strong> Less than full hours = LOP 0.5 day</li>
              <li><strong>Absent (A):</strong> No attendance = LOP 1 day</li>
              <li><strong>Formula:</strong> Payable Days = (Working Days - LOP) + Weekoff Pay + Extra Pay</li>
            </ul>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Payroll;
