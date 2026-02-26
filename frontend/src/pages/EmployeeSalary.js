import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '../components/ui/select';
import {
  Wallet,
  Download,
  Loader2,
  TrendingUp,
  TrendingDown,
  Calendar,
  FileText,
  Building2,
  DollarSign,
  PiggyBank,
  CreditCard,
  Receipt,
  ChevronRight,
  Banknote,
  CircleDollarSign,
  Minus,
  Plus
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EmployeeSalary = () => {
  const { token } = useAuth();
  const [salary, setSalary] = useState(null);
  const [adjustments, setAdjustments] = useState([]);
  const [payslip, setPayslip] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingPayslip, setLoadingPayslip] = useState(false);
  const [selectedMonth, setSelectedMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });

  const fetchSalary = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/employee-profile/salary`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSalary(response.data.salary);
      setAdjustments(response.data.adjustments || []);
    } catch (error) {
      console.error('Error fetching salary:', error);
      toast.error('Failed to load salary details');
    } finally {
      setLoading(false);
    }
  }, [token]);

  const fetchPayslip = useCallback(async (month) => {
    try {
      setLoadingPayslip(true);
      const response = await axios.get(`${API}/employee-profile/salary`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      // Get employee_id from salary response for payslip
      if (response.data.salary?.employee_id) {
        const payslipRes = await axios.get(
          `${API}/employees/${response.data.salary.employee_id}/payslip/${month}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        setPayslip(payslipRes.data);
      }
    } catch (error) {
      console.error('Error fetching payslip:', error);
      setPayslip(null);
    } finally {
      setLoadingPayslip(false);
    }
  }, [token]);

  useEffect(() => {
    fetchSalary();
  }, [fetchSalary]);

  useEffect(() => {
    if (salary?.employee_id) {
      fetchPayslip(selectedMonth);
    }
  }, [selectedMonth, salary?.employee_id, fetchPayslip]);

  const getMonthOptions = () => {
    const options = [];
    const now = new Date();
    for (let i = 0; i < 12; i++) {
      const date = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const value = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
      const label = date.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
      options.push({ value, label });
    }
    return options;
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(amount || 0);
  };

  const handleDownloadPayslip = (type) => {
    if (!payslip) return;
    
    // Create printable content
    const content = type === 'simple' ? generateSimplePayslip() : generateDetailedPayslip();
    const printWindow = window.open('', '_blank');
    printWindow.document.write(content);
    printWindow.document.close();
    printWindow.print();
  };

  const generateSimplePayslip = () => {
    if (!payslip) return '';
    return `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Salary Slip - ${payslip.month}</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto; }
          .header { text-align: center; border-bottom: 2px solid #063c88; padding-bottom: 20px; margin-bottom: 20px; }
          .header h1 { color: #063c88; margin: 0; }
          .header p { color: #666; margin: 5px 0; }
          .info { display: flex; justify-content: space-between; margin-bottom: 20px; }
          .info-item { }
          .info-item label { color: #666; font-size: 12px; }
          .info-item p { margin: 2px 0; font-weight: bold; }
          table { width: 100%; border-collapse: collapse; margin: 20px 0; }
          th, td { padding: 10px; text-align: left; border-bottom: 1px solid #eee; }
          th { background: #f5f5f5; }
          .amount { text-align: right; }
          .total { font-weight: bold; background: #063c88; color: white; }
          .total td { border: none; }
          .net-pay { font-size: 24px; text-align: center; padding: 20px; background: #e8f4e8; border-radius: 8px; margin-top: 20px; }
          .net-pay span { color: #063c88; font-weight: bold; }
        </style>
      </head>
      <body>
        <div class="header">
          <h1>${payslip.company_name}</h1>
          <p>Salary Slip for ${new Date(payslip.month + '-01').toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}</p>
        </div>
        <div class="info">
          <div class="info-item">
            <label>Employee Name</label>
            <p>${payslip.employee_name}</p>
          </div>
          <div class="info-item">
            <label>Employee ID</label>
            <p>${payslip.emp_id}</p>
          </div>
          <div class="info-item">
            <label>Department</label>
            <p>${payslip.department}</p>
          </div>
        </div>
        <table>
          <tr><th>Earnings</th><th class="amount">Amount</th></tr>
          <tr><td>Gross Salary</td><td class="amount">${formatCurrency(payslip.gross_earnings)}</td></tr>
          <tr class="total"><td>Total Earnings</td><td class="amount">${formatCurrency(payslip.gross_earnings)}</td></tr>
        </table>
        <table>
          <tr><th>Deductions</th><th class="amount">Amount</th></tr>
          <tr><td>Total Deductions</td><td class="amount">${formatCurrency(payslip.total_deductions)}</td></tr>
          <tr class="total"><td>Total Deductions</td><td class="amount">${formatCurrency(payslip.total_deductions)}</td></tr>
        </table>
        <div class="net-pay">
          Net Pay: <span>${formatCurrency(payslip.net_pay)}</span>
        </div>
      </body>
      </html>
    `;
  };

  const generateDetailedPayslip = () => {
    if (!payslip) return '';
    return `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Payslip - ${payslip.month}</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 40px; max-width: 800px; margin: 0 auto; }
          .header { text-align: center; border-bottom: 3px solid #063c88; padding-bottom: 20px; margin-bottom: 30px; }
          .header h1 { color: #063c88; margin: 0; font-size: 28px; }
          .header p { color: #666; margin: 5px 0; }
          .company-info { text-align: center; color: #666; font-size: 12px; margin-top: 10px; }
          .employee-info { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; padding: 20px; background: #f8f9fa; border-radius: 8px; }
          .info-group { }
          .info-group label { color: #666; font-size: 11px; text-transform: uppercase; }
          .info-group p { margin: 2px 0; font-weight: 600; color: #333; }
          .section-title { color: #063c88; font-size: 14px; font-weight: bold; margin: 20px 0 10px; text-transform: uppercase; letter-spacing: 1px; }
          table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
          th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e0e0e0; }
          th { background: #f0f4f8; color: #063c88; font-weight: 600; font-size: 12px; text-transform: uppercase; }
          .amount { text-align: right; font-family: monospace; }
          .total-row { background: #063c88; color: white; font-weight: bold; }
          .total-row td { border: none; }
          .summary { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-top: 30px; }
          .summary-card { padding: 20px; border-radius: 8px; text-align: center; }
          .summary-card.earnings { background: #e8f5e9; }
          .summary-card.deductions { background: #ffebee; }
          .summary-card.net { background: #063c88; color: white; }
          .summary-card label { font-size: 11px; text-transform: uppercase; opacity: 0.8; }
          .summary-card p { font-size: 24px; font-weight: bold; margin: 5px 0; }
          .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #e0e0e0; font-size: 11px; color: #666; text-align: center; }
        </style>
      </head>
      <body>
        <div class="header">
          <h1>${payslip.company_name}</h1>
          <p class="company-info">${payslip.company_address}</p>
          <p style="font-size: 16px; margin-top: 15px;">PAYSLIP FOR ${new Date(payslip.month + '-01').toLocaleDateString('en-IN', { month: 'long', year: 'numeric' }).toUpperCase()}</p>
        </div>
        
        <div class="employee-info">
          <div class="info-group"><label>Employee Name</label><p>${payslip.employee_name}</p></div>
          <div class="info-group"><label>Employee ID</label><p>${payslip.emp_id}</p></div>
          <div class="info-group"><label>Designation</label><p>${payslip.designation}</p></div>
          <div class="info-group"><label>Department</label><p>${payslip.department}</p></div>
        </div>
        
        <div class="section-title">Earnings</div>
        <table>
          <tr><th>Component</th><th class="amount">Amount (₹)</th></tr>
          <tr><td>Basic Salary</td><td class="amount">${payslip.basic?.toLocaleString('en-IN')}</td></tr>
          <tr><td>House Rent Allowance (HRA)</td><td class="amount">${payslip.hra?.toLocaleString('en-IN')}</td></tr>
          <tr><td>Dearness Allowance (DA)</td><td class="amount">${payslip.da?.toLocaleString('en-IN')}</td></tr>
          <tr><td>Conveyance Allowance</td><td class="amount">${payslip.conveyance?.toLocaleString('en-IN')}</td></tr>
          <tr><td>Medical Allowance</td><td class="amount">${payslip.medical_allowance?.toLocaleString('en-IN')}</td></tr>
          <tr><td>Special Allowance</td><td class="amount">${payslip.special_allowance?.toLocaleString('en-IN')}</td></tr>
          ${payslip.other_allowances > 0 ? `<tr><td>Other Allowances</td><td class="amount">${payslip.other_allowances?.toLocaleString('en-IN')}</td></tr>` : ''}
          ${payslip.earnings_adjustments?.map(a => `<tr><td>${a.description} (${a.adjustment_type})</td><td class="amount">+${a.amount?.toLocaleString('en-IN')}</td></tr>`).join('') || ''}
          <tr class="total-row"><td>GROSS EARNINGS</td><td class="amount">${payslip.gross_earnings?.toLocaleString('en-IN')}</td></tr>
        </table>
        
        <div class="section-title">Deductions</div>
        <table>
          <tr><th>Component</th><th class="amount">Amount (₹)</th></tr>
          <tr><td>Provident Fund (PF)</td><td class="amount">${payslip.pf_employee?.toLocaleString('en-IN')}</td></tr>
          ${payslip.esi_employee > 0 ? `<tr><td>Employee State Insurance (ESI)</td><td class="amount">${payslip.esi_employee?.toLocaleString('en-IN')}</td></tr>` : ''}
          <tr><td>Professional Tax</td><td class="amount">${payslip.professional_tax?.toLocaleString('en-IN')}</td></tr>
          ${payslip.tds > 0 ? `<tr><td>Tax Deducted at Source (TDS)</td><td class="amount">${payslip.tds?.toLocaleString('en-IN')}</td></tr>` : ''}
          ${payslip.other_deductions > 0 ? `<tr><td>Other Deductions</td><td class="amount">${payslip.other_deductions?.toLocaleString('en-IN')}</td></tr>` : ''}
          ${payslip.deduction_adjustments?.map(a => `<tr><td>${a.description} (${a.adjustment_type})</td><td class="amount">${a.amount?.toLocaleString('en-IN')}</td></tr>`).join('') || ''}
          ${payslip.lop_days > 0 ? `<tr><td>Loss of Pay (${payslip.lop_days} days)</td><td class="amount">${payslip.lop_deduction?.toLocaleString('en-IN')}</td></tr>` : ''}
          <tr class="total-row"><td>TOTAL DEDUCTIONS</td><td class="amount">${payslip.total_deductions?.toLocaleString('en-IN')}</td></tr>
        </table>
        
        <div class="summary">
          <div class="summary-card earnings">
            <label>Total Earnings</label>
            <p>₹${payslip.gross_earnings?.toLocaleString('en-IN')}</p>
          </div>
          <div class="summary-card deductions">
            <label>Total Deductions</label>
            <p>₹${payslip.total_deductions?.toLocaleString('en-IN')}</p>
          </div>
          <div class="summary-card net">
            <label>Net Pay</label>
            <p>₹${payslip.net_pay?.toLocaleString('en-IN')}</p>
          </div>
        </div>
        
        <div class="footer">
          <p>This is a computer-generated payslip and does not require a signature.</p>
          <p>Generated on ${new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
        </div>
      </body>
      </html>
    `;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-[#063c88]" />
      </div>
    );
  }

  if (!salary) {
    return (
      <div className="space-y-6 animate-fade-in" data-testid="employee-salary-page">
        <div>
          <h1 className="text-3xl font-bold text-[#0b1f3b]" style={{ fontFamily: 'Outfit' }}>
            My Salary
          </h1>
          <p className="text-slate-500 mt-1">View your salary breakup and download payslips</p>
        </div>
        <Card className="card-premium">
          <CardContent className="py-16 text-center">
            <div className="w-20 h-20 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
              <Wallet className="w-10 h-10 text-slate-400" />
            </div>
            <h3 className="text-xl font-semibold text-slate-900 mb-2">Salary Not Configured</h3>
            <p className="text-slate-500 max-w-md mx-auto">
              Your salary details haven't been set up yet. Please contact HR for assistance.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="employee-salary-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[#0b1f3b]" style={{ fontFamily: 'Outfit' }}>
            My Salary
          </h1>
          <p className="text-slate-500 mt-1">View your salary breakup and download payslips</p>
        </div>
        <Select value={selectedMonth} onValueChange={setSelectedMonth}>
          <SelectTrigger className="w-[200px] rounded-xl">
            <Calendar className="w-4 h-4 mr-2" />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {getMonthOptions().map(opt => (
              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Net Pay Summary Card */}
      <Card className="card-premium overflow-hidden bg-gradient-to-r from-[#063c88] to-[#0a5cba]">
        <CardContent className="p-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="text-center md:text-left">
              <p className="text-blue-200 text-sm font-medium uppercase tracking-wider">Net Pay This Month</p>
              <p className="text-4xl md:text-5xl font-bold text-white mt-2 number-display">
                {formatCurrency(payslip?.net_pay || salary?.net_salary)}
              </p>
              <p className="text-blue-200 text-sm mt-2">
                {new Date(selectedMonth + '-01').toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}
              </p>
            </div>
            <div className="flex gap-3">
              <Button 
                onClick={() => handleDownloadPayslip('simple')}
                variant="secondary"
                className="bg-white/20 hover:bg-white/30 text-white border-0 rounded-xl"
                disabled={!payslip}
              >
                <Download className="w-4 h-4 mr-2" />
                Simple Slip
              </Button>
              <Button 
                onClick={() => handleDownloadPayslip('detailed')}
                className="bg-white text-[#063c88] hover:bg-white/90 rounded-xl"
                disabled={!payslip}
              >
                <FileText className="w-4 h-4 mr-2" />
                Detailed Payslip
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Salary Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Earnings Card */}
        <Card className="card-premium">
          <CardHeader className="border-b border-slate-100">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-emerald-600" />
              </div>
              <div>
                <CardTitle className="text-lg" style={{ fontFamily: 'Outfit' }}>Earnings</CardTitle>
                <CardDescription>Your monthly income breakdown</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-slate-100">
              <SalaryRow label="Basic Salary" amount={salary?.basic} icon={Banknote} />
              <SalaryRow label="House Rent Allowance (HRA)" amount={salary?.hra} icon={Building2} />
              <SalaryRow label="Dearness Allowance (DA)" amount={salary?.da} icon={CircleDollarSign} />
              <SalaryRow label="Conveyance Allowance" amount={salary?.conveyance} icon={CreditCard} />
              <SalaryRow label="Medical Allowance" amount={salary?.medical_allowance} icon={Plus} />
              <SalaryRow label="Special Allowance" amount={salary?.special_allowance} icon={DollarSign} />
              {salary?.other_allowances > 0 && (
                <SalaryRow label="Other Allowances" amount={salary?.other_allowances} icon={Plus} />
              )}
              {/* Earnings Adjustments */}
              {payslip?.earnings_adjustments?.map((adj, i) => (
                <SalaryRow 
                  key={i} 
                  label={`${adj.description} (${adj.adjustment_type})`} 
                  amount={adj.amount} 
                  icon={Plus}
                  isAdjustment 
                />
              ))}
            </div>
            <div className="p-4 bg-emerald-50 flex items-center justify-between">
              <span className="font-semibold text-emerald-700">Gross Earnings</span>
              <span className="font-bold text-emerald-700 text-lg">
                {formatCurrency(payslip?.gross_earnings || salary?.gross_salary)}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Deductions Card */}
        <Card className="card-premium">
          <CardHeader className="border-b border-slate-100">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-red-100 flex items-center justify-center">
                <TrendingDown className="w-5 h-5 text-red-600" />
              </div>
              <div>
                <CardTitle className="text-lg" style={{ fontFamily: 'Outfit' }}>Deductions</CardTitle>
                <CardDescription>Monthly deductions from your salary</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-slate-100">
              <SalaryRow label="Provident Fund (PF)" amount={salary?.pf_employee} icon={PiggyBank} isDeduction />
              {salary?.esi_employee > 0 && (
                <SalaryRow label="Employee State Insurance (ESI)" amount={salary?.esi_employee} icon={Receipt} isDeduction />
              )}
              <SalaryRow label="Professional Tax" amount={salary?.professional_tax} icon={Receipt} isDeduction />
              {salary?.tds > 0 && (
                <SalaryRow label="Tax Deducted at Source (TDS)" amount={salary?.tds} icon={Receipt} isDeduction />
              )}
              {salary?.other_deductions > 0 && (
                <SalaryRow label="Other Deductions" amount={salary?.other_deductions} icon={Minus} isDeduction />
              )}
              {/* Deduction Adjustments */}
              {payslip?.deduction_adjustments?.map((adj, i) => (
                <SalaryRow 
                  key={i} 
                  label={`${adj.description} (${adj.adjustment_type})`} 
                  amount={adj.amount} 
                  icon={Minus}
                  isDeduction
                  isAdjustment 
                />
              ))}
              {/* LOP */}
              {payslip?.lop_days > 0 && (
                <SalaryRow 
                  label={`Loss of Pay (${payslip.lop_days} days)`} 
                  amount={payslip.lop_deduction} 
                  icon={Minus}
                  isDeduction 
                />
              )}
            </div>
            <div className="p-4 bg-red-50 flex items-center justify-between">
              <span className="font-semibold text-red-700">Total Deductions</span>
              <span className="font-bold text-red-700 text-lg">
                {formatCurrency(payslip?.total_deductions || salary?.total_deductions)}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Adjustments History */}
      {adjustments.length > 0 && (
        <Card className="card-premium">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center">
                <Receipt className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <CardTitle className="text-lg" style={{ fontFamily: 'Outfit' }}>Active Adjustments</CardTitle>
                <CardDescription>Recurring and one-time salary adjustments</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-slate-100">
              {adjustments.map((adj) => (
                <div key={adj.id} className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      adj.category === 'earning' ? 'bg-emerald-100' : 'bg-red-100'
                    }`}>
                      {adj.category === 'earning' ? (
                        <Plus className="w-5 h-5 text-emerald-600" />
                      ) : (
                        <Minus className="w-5 h-5 text-red-600" />
                      )}
                    </div>
                    <div>
                      <p className="font-medium text-slate-900">{adj.description}</p>
                      <div className="flex items-center gap-2 text-xs text-slate-500">
                        <Badge variant="outline" className="text-[10px]">{adj.adjustment_type}</Badge>
                        <span>•</span>
                        <span>{adj.frequency === 'recurring' ? 'Recurring' : `One-time (${adj.applicable_month})`}</span>
                      </div>
                    </div>
                  </div>
                  <span className={`font-semibold ${adj.category === 'earning' ? 'text-emerald-600' : 'text-red-600'}`}>
                    {adj.category === 'earning' ? '+' : '-'}{formatCurrency(adj.amount)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* CTC Info */}
      <Card className="border-blue-100 bg-blue-50/50">
        <CardContent className="p-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
              <Wallet className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-blue-700">Annual Cost to Company (CTC)</p>
              <p className="text-2xl font-bold text-blue-900">{formatCurrency(salary?.annual_ctc)}</p>
            </div>
            <ChevronRight className="w-5 h-5 text-blue-400 ml-auto" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

// Salary Row Component
const SalaryRow = ({ label, amount, icon: Icon, isDeduction, isAdjustment }) => (
  <div className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors">
    <div className="flex items-center gap-3">
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
        isAdjustment 
          ? (isDeduction ? 'bg-orange-100' : 'bg-teal-100')
          : (isDeduction ? 'bg-red-50' : 'bg-emerald-50')
      }`}>
        <Icon className={`w-4 h-4 ${
          isAdjustment 
            ? (isDeduction ? 'text-orange-600' : 'text-teal-600')
            : (isDeduction ? 'text-red-500' : 'text-emerald-500')
        }`} />
      </div>
      <span className="text-sm text-slate-700">{label}</span>
      {isAdjustment && (
        <Badge className="bg-amber-100 text-amber-700 text-[10px]">Adjustment</Badge>
      )}
    </div>
    <span className={`font-medium ${isDeduction ? 'text-red-600' : 'text-slate-900'}`}>
      {isDeduction ? '-' : ''}{new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 0
      }).format(amount || 0)}
    </span>
  </div>
);

export default EmployeeSalary;
