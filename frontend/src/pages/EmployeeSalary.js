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
  Calendar,
  FileText,
  Building2,
  User,
  Briefcase,
  Shield,
  Heart,
  Plane,
  Phone,
  Utensils,
  Car,
  Star,
  PiggyBank,
  Award,
  Banknote,
  TrendingUp,
  TrendingDown,
  Receipt,
  ChevronRight,
  Info
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
      maximumFractionDigits: 0
    }).format(amount || 0);
  };

  const handleDownloadPDF = () => {
    if (!payslip) return;
    
    const content = generateCompensationPDF();
    const printWindow = window.open('', '_blank', 'width=800,height=600');
    printWindow.document.write(content);
    printWindow.document.close();
    
    // Add instruction for user
    const style = printWindow.document.createElement('style');
    style.textContent = `
      @media print {
        @page {
          margin: 10mm;
        }
      }
    `;
    printWindow.document.head.appendChild(style);
    
    // Trigger print after content loads
    printWindow.onload = function() {
      setTimeout(() => {
        printWindow.print();
      }, 300);
    };
  };

  const generateCompensationPDF = () => {
    if (!payslip) return '';
    
    const monthYear = new Date(payslip.month + '-01').toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
    
    return `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Compensation & Benefits Structure - ${payslip.employee_name}</title>
        <style>
          @page { 
            size: A4; 
            margin: 10mm;
          }
          @media print {
            html, body {
              -webkit-print-color-adjust: exact !important;
              print-color-adjust: exact !important;
            }
          }
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            background: white;
            color: #1a1a2e;
            font-size: 11px;
            line-height: 1.4;
          }
          .container { max-width: 210mm; margin: 0 auto; padding: 15px; }
          
          /* Header */
          .header { 
            background: linear-gradient(135deg, #063c88 0%, #0a5cba 100%);
            color: white;
            padding: 25px 30px;
            border-radius: 12px;
            margin-bottom: 20px;
          }
          .header h1 { 
            font-size: 22px; 
            font-weight: 700;
            margin-bottom: 4px;
          }
          .header .subtitle { 
            font-size: 13px;
            opacity: 0.9;
          }
          .header .company-name {
            font-size: 12px;
            opacity: 0.8;
            margin-top: 10px;
          }
          
          /* Employee Info */
          .employee-info {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 20px;
            padding: 20px;
            background: #f8f9fc;
            border-radius: 10px;
            border: 1px solid #e5e7eb;
          }
          .info-item { }
          .info-item label { 
            font-size: 10px; 
            color: #6b7280; 
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: block;
            margin-bottom: 4px;
          }
          .info-item span { 
            font-size: 13px;
            font-weight: 600;
            color: #1f2937;
          }
          
          /* Section */
          .section {
            margin-bottom: 15px;
          }
          .section-header {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 15px;
            background: #f1f5f9;
            border-radius: 8px 8px 0 0;
            border: 1px solid #e2e8f0;
            border-bottom: none;
          }
          .section-header .badge {
            background: #063c88;
            color: white;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
          }
          .section-header h3 {
            font-size: 12px;
            font-weight: 600;
            color: #334155;
          }
          
          /* Table */
          table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border: 1px solid #e2e8f0;
            border-top: none;
            border-radius: 0 0 8px 8px;
            overflow: hidden;
          }
          th, td {
            padding: 10px 15px;
            text-align: left;
            border-bottom: 1px solid #f1f5f9;
          }
          th {
            background: #f8fafc;
            font-size: 10px;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
          }
          td { font-size: 12px; color: #374151; }
          td:last-child { text-align: right; font-family: 'SF Mono', monospace; font-weight: 600; }
          tr:last-child td { border-bottom: none; }
          .subtotal-row { background: #f8fafc; }
          .subtotal-row td { font-weight: 700; color: #1f2937; }
          .total-row { 
            background: linear-gradient(135deg, #063c88 0%, #0a5cba 100%);
          }
          .total-row td { 
            color: white; 
            font-weight: 700;
            font-size: 13px;
          }
          
          /* Summary Cards */
          .summary-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin: 20px 0;
          }
          .summary-card {
            padding: 20px;
            border-radius: 10px;
            text-align: center;
          }
          .summary-card.fixed { background: #e0f2fe; border: 1px solid #7dd3fc; }
          .summary-card.variable { background: #fef3c7; border: 1px solid #fcd34d; }
          .summary-card.ctc { background: linear-gradient(135deg, #063c88 0%, #0a5cba 100%); color: white; }
          .summary-card label { 
            display: block;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
          }
          .summary-card .amount {
            font-size: 18px;
            font-weight: 700;
          }
          .summary-card.fixed label { color: #0369a1; }
          .summary-card.fixed .amount { color: #0c4a6e; }
          .summary-card.variable label { color: #92400e; }
          .summary-card.variable .amount { color: #78350f; }
          .summary-card.ctc label { opacity: 0.9; }
          
          /* Insurance */
          .insurance-section {
            background: #f0fdf4;
            border: 1px solid #86efac;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
          }
          .insurance-section h3 {
            font-size: 13px;
            font-weight: 600;
            color: #166534;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
          }
          .insurance-section h3::before {
            content: '🛡️';
          }
          .insurance-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
          }
          .insurance-item {
            text-align: center;
            padding: 12px;
            background: white;
            border-radius: 8px;
          }
          .insurance-item label {
            display: block;
            font-size: 10px;
            color: #4b5563;
            margin-bottom: 4px;
          }
          .insurance-item span {
            font-size: 14px;
            font-weight: 600;
            color: #166534;
          }
          
          /* Footer */
          .footer {
            margin-top: 25px;
            padding-top: 15px;
            border-top: 1px solid #e5e7eb;
            text-align: center;
            font-size: 10px;
            color: #9ca3af;
          }
          .footer p { margin: 4px 0; }
          
          /* Note */
          .note {
            background: #fefce8;
            border: 1px solid #fde047;
            border-radius: 8px;
            padding: 12px 15px;
            margin-top: 15px;
            font-size: 10px;
            color: #713f12;
          }
          .note strong { display: block; margin-bottom: 4px; }
          
          @media print {
            body { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
          }
        </style>
      </head>
      <body>
        <div class="container">
          <!-- Header -->
          <div class="header">
            <h1>Compensation & Benefits Structure</h1>
            <div class="subtitle">Payslip for ${monthYear}</div>
            <div class="company-name">${payslip.company_name} | ${payslip.company_address}</div>
          </div>
          
          <!-- Employee Info -->
          <div class="employee-info">
            <div class="info-item">
              <label>Employee Name</label>
              <span>${payslip.employee_name}</span>
            </div>
            <div class="info-item">
              <label>Employee ID</label>
              <span>${payslip.emp_id}</span>
            </div>
            <div class="info-item">
              <label>Designation</label>
              <span>${payslip.designation}</span>
            </div>
            <div class="info-item">
              <label>Tier</label>
              <span>${payslip.tier_level || 'Tier 1'}</span>
            </div>
          </div>
          
          <!-- Base Components -->
          <div class="section">
            <div class="section-header">
              <span class="badge">A</span>
              <h3>Base Components</h3>
            </div>
            <table>
              <tr><th>Component</th><th>Monthly (₹)</th></tr>
              <tr><td>Basic</td><td>${formatCurrency(payslip.basic)}</td></tr>
              <tr><td>House Rent Allowance (HRA)</td><td>${formatCurrency(payslip.hra)}</td></tr>
              <tr class="subtotal-row"><td>Base Components Total (A)</td><td>${formatCurrency(payslip.base_components_total || (payslip.basic + payslip.hra))}</td></tr>
            </table>
          </div>
          
          <!-- Basket of Allowances -->
          <div class="section">
            <div class="section-header">
              <span class="badge">B</span>
              <h3>Basket of Allowances</h3>
            </div>
            <table>
              <tr><th>Component</th><th>Monthly (₹)</th></tr>
              <tr><td>Leave Travel Allowance (LTA)</td><td>${formatCurrency(payslip.lta)}</td></tr>
              <tr><td>Phone & Internet</td><td>${formatCurrency(payslip.phone_internet)}</td></tr>
              <tr><td>Performance Bonus</td><td>${formatCurrency(payslip.bonus)}</td></tr>
              <tr><td>Stay & Travel</td><td>${formatCurrency(payslip.stay_travel)}</td></tr>
              <tr><td>Special Allowance</td><td>${formatCurrency(payslip.special_allowance)}</td></tr>
              <tr><td>Food Reimbursement</td><td>${formatCurrency(payslip.food_reimbursement)}</td></tr>
              <tr><td>Medical Allowance</td><td>${formatCurrency(payslip.medical_allowance)}</td></tr>
              <tr><td>Conveyance</td><td>${formatCurrency(payslip.conveyance)}</td></tr>
              <tr class="subtotal-row"><td>Basket Allowances Total (B)</td><td>${formatCurrency(payslip.basket_allowances_total)}</td></tr>
            </table>
          </div>
          
          <!-- Retirement Benefits -->
          <div class="section">
            <div class="section-header">
              <span class="badge">C</span>
              <h3>Retirement Benefits</h3>
            </div>
            <table>
              <tr><th>Component</th><th>Monthly (₹)</th></tr>
              <tr><td>PF Company's Contribution</td><td>${formatCurrency(payslip.pf_employer)}</td></tr>
              <tr><td>Gratuity</td><td>${formatCurrency(payslip.gratuity)}</td></tr>
              <tr class="subtotal-row"><td>Retirement Benefits Total (C)</td><td>${formatCurrency(payslip.retirement_benefits_total)}</td></tr>
            </table>
          </div>
          
          <!-- Summary Cards -->
          <div class="summary-grid">
            <div class="summary-card fixed">
              <label>Fixed Compensation (A+B+C)</label>
              <div class="amount">₹${formatCurrency(payslip.fixed_compensation)}</div>
            </div>
            <div class="summary-card variable">
              <label>Variable Compensation</label>
              <div class="amount">₹${formatCurrency(payslip.variable_compensation)}</div>
            </div>
            <div class="summary-card ctc">
              <label>Cost to Company (CTC)</label>
              <div class="amount">₹${formatCurrency(payslip.monthly_ctc)}</div>
            </div>
          </div>
          
          <!-- Deductions -->
          <div class="section">
            <div class="section-header">
              <span class="badge" style="background: #dc2626;">D</span>
              <h3>Deductions</h3>
            </div>
            <table>
              <tr><th>Component</th><th>Monthly (₹)</th></tr>
              <tr><td>Provident Fund (Employee)</td><td>${formatCurrency(payslip.pf_employee)}</td></tr>
              ${payslip.esi_employee > 0 ? `<tr><td>ESI (Employee)</td><td>${formatCurrency(payslip.esi_employee)}</td></tr>` : ''}
              <tr><td>Professional Tax</td><td>${formatCurrency(payslip.professional_tax)}</td></tr>
              ${payslip.tds > 0 ? `<tr><td>TDS</td><td>${formatCurrency(payslip.tds)}</td></tr>` : ''}
              ${payslip.lop_days > 0 ? `<tr><td>Loss of Pay (${payslip.lop_days} days)</td><td>${formatCurrency(payslip.lop_deduction)}</td></tr>` : ''}
              <tr class="subtotal-row"><td>Total Deductions (D)</td><td>${formatCurrency(payslip.total_deductions)}</td></tr>
            </table>
          </div>
          
          <!-- Net Pay -->
          <div class="section">
            <table>
              <tr class="total-row">
                <td>NET PAY (Take Home)</td>
                <td>₹${formatCurrency(payslip.net_pay)}</td>
              </tr>
            </table>
          </div>
          
          <!-- Insurance -->
          <div class="insurance-section">
            <h3>Insurance Coverage</h3>
            <div class="insurance-grid">
              <div class="insurance-item">
                <label>Medical Insurance</label>
                <span>₹${formatCurrency(payslip.medical_insurance)}</span>
              </div>
              <div class="insurance-item">
                <label>Accident Insurance</label>
                <span>${payslip.accident_insurance}</span>
              </div>
              <div class="insurance-item">
                <label>Life Insurance</label>
                <span>₹${formatCurrency(payslip.life_insurance)}</span>
              </div>
            </div>
          </div>
          
          <!-- Note -->
          <div class="note">
            <strong>Note:</strong>
            • Annual CTC: ₹${formatCurrency(payslip.annual_ctc)}<br>
            • Variable Compensation is subject to performance and company policy<br>
            • PF is calculated on Basic up to ₹15,000 as per statutory requirements<br>
            • Gratuity is payable as per the Payment of Gratuity Act, 1972
          </div>
          
          <!-- Footer -->
          <div class="footer">
            <p>This is a computer-generated payslip and does not require a signature.</p>
            <p>Generated on ${new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })} | ${payslip.company_name}</p>
          </div>
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
            Compensation & Benefits
          </h1>
          <p className="text-slate-500 mt-1">View your salary structure and download payslips</p>
        </div>
        <Card className="card-premium">
          <CardContent className="py-16 text-center">
            <div className="w-20 h-20 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
              <Wallet className="w-10 h-10 text-slate-400" />
            </div>
            <h3 className="text-xl font-semibold text-slate-900 mb-2">Salary Not Configured</h3>
            <p className="text-slate-500 max-w-md mx-auto">
              Your compensation details haven't been set up yet. Please contact HR for assistance.
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
            Compensation & Benefits
          </h1>
          <p className="text-slate-500 mt-1">Your complete salary structure and payslip</p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={selectedMonth} onValueChange={setSelectedMonth}>
            <SelectTrigger className="w-[200px] rounded-xl bg-white">
              <Calendar className="w-4 h-4 mr-2 text-slate-500" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {getMonthOptions().map(opt => (
                <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button 
            onClick={handleDownloadPDF}
            disabled={!payslip || loadingPayslip}
            className="bg-[#063c88] hover:bg-[#052d66] rounded-xl shadow-lg shadow-blue-900/20"
            data-testid="download-payslip-btn"
          >
            {loadingPayslip ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <Download className="w-4 h-4 mr-2" />
            )}
            Download PDF
          </Button>
        </div>
      </div>

      {/* CTC Summary Card */}
      <Card className="card-premium overflow-hidden">
        <div className="bg-gradient-to-r from-[#063c88] to-[#0a5cba] p-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="text-center md:text-left text-white">
              <p className="text-blue-200 text-sm font-medium uppercase tracking-wider">Monthly Net Pay</p>
              <p className="text-5xl font-bold mt-2 number-display">
                ₹{formatCurrency(payslip?.net_pay || salary?.net_salary)}
              </p>
              <p className="text-blue-200 text-sm mt-2">
                {new Date(selectedMonth + '-01').toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}
              </p>
            </div>
            <div className="flex gap-4">
              <div className="text-center px-6 py-4 bg-white/10 rounded-xl backdrop-blur-sm">
                <p className="text-blue-200 text-xs uppercase">Annual CTC</p>
                <p className="text-2xl font-bold text-white mt-1">₹{formatCurrency(salary?.annual_ctc)}</p>
              </div>
              <div className="text-center px-6 py-4 bg-white/10 rounded-xl backdrop-blur-sm">
                <p className="text-blue-200 text-xs uppercase">Monthly CTC</p>
                <p className="text-2xl font-bold text-white mt-1">₹{formatCurrency(salary?.monthly_ctc)}</p>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Compensation Structure */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Base Components (A) */}
        <Card className="card-premium">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center text-sm font-bold text-blue-700">A</div>
              <CardTitle className="text-lg">Base Components</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-3">
              <CompItem icon={Banknote} label="Basic" amount={payslip?.basic || salary?.basic} />
              <CompItem icon={Building2} label="HRA" amount={payslip?.hra || salary?.hra} />
              <div className="pt-3 border-t border-slate-100 flex justify-between items-center">
                <span className="font-semibold text-slate-700">Total (A)</span>
                <span className="font-bold text-blue-700 text-lg">₹{formatCurrency(payslip?.base_components_total || (salary?.basic + salary?.hra))}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Basket of Allowances (B) */}
        <Card className="card-premium">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center text-sm font-bold text-emerald-700">B</div>
              <CardTitle className="text-lg">Basket of Allowances</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-2">
              <CompItem icon={Plane} label="LTA" amount={payslip?.lta || salary?.lta} small />
              <CompItem icon={Phone} label="Phone & Internet" amount={payslip?.phone_internet || salary?.phone_internet} small />
              <CompItem icon={Award} label="Performance Bonus" amount={payslip?.bonus || salary?.bonus} small />
              <CompItem icon={Car} label="Stay & Travel" amount={payslip?.stay_travel || salary?.stay_travel} small />
              <CompItem icon={Star} label="Special Allowance" amount={payslip?.special_allowance || salary?.special_allowance} small />
              <CompItem icon={Utensils} label="Food Reimbursement" amount={payslip?.food_reimbursement || salary?.food_reimbursement} small />
              <CompItem icon={Heart} label="Medical" amount={payslip?.medical_allowance || salary?.medical_allowance} small />
              <CompItem icon={Car} label="Conveyance" amount={payslip?.conveyance || salary?.conveyance} small />
              <div className="pt-3 border-t border-slate-100 flex justify-between items-center">
                <span className="font-semibold text-slate-700">Total (B)</span>
                <span className="font-bold text-emerald-700 text-lg">₹{formatCurrency(payslip?.basket_allowances_total || salary?.basket_allowances_total)}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Retirement Benefits (C) */}
        <Card className="card-premium">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center text-sm font-bold text-purple-700">C</div>
              <CardTitle className="text-lg">Retirement Benefits</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-3">
              <CompItem icon={PiggyBank} label="PF (Employer)" amount={payslip?.pf_employer || salary?.pf_employer} />
              <CompItem icon={Shield} label="Gratuity" amount={payslip?.gratuity || salary?.gratuity} />
              <div className="pt-3 border-t border-slate-100 flex justify-between items-center">
                <span className="font-semibold text-slate-700">Total (C)</span>
                <span className="font-bold text-purple-700 text-lg">₹{formatCurrency(payslip?.retirement_benefits_total || salary?.retirement_benefits_total)}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Deductions (D) */}
        <Card className="card-premium">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-red-100 flex items-center justify-center text-sm font-bold text-red-700">D</div>
              <CardTitle className="text-lg">Deductions</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-3">
              <CompItem icon={PiggyBank} label="PF (Employee)" amount={payslip?.pf_employee || salary?.pf_employee} isDeduction />
              {(payslip?.esi_employee > 0 || salary?.esi_employee > 0) && (
                <CompItem icon={Receipt} label="ESI" amount={payslip?.esi_employee || salary?.esi_employee} isDeduction />
              )}
              <CompItem icon={Receipt} label="Professional Tax" amount={payslip?.professional_tax || salary?.professional_tax} isDeduction />
              {(payslip?.tds > 0 || salary?.tds > 0) && (
                <CompItem icon={Receipt} label="TDS" amount={payslip?.tds || salary?.tds} isDeduction />
              )}
              {payslip?.lop_days > 0 && (
                <CompItem icon={TrendingDown} label={`LOP (${payslip.lop_days} days)`} amount={payslip.lop_deduction} isDeduction />
              )}
              <div className="pt-3 border-t border-slate-100 flex justify-between items-center">
                <span className="font-semibold text-slate-700">Total (D)</span>
                <span className="font-bold text-red-700 text-lg">-₹{formatCurrency(payslip?.total_deductions || salary?.total_deductions)}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Compensation Summary */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="card-flat bg-blue-50 border-blue-100">
          <CardContent className="p-6 text-center">
            <p className="text-xs text-blue-600 font-medium uppercase tracking-wider">Fixed Compensation</p>
            <p className="text-2xl font-bold text-blue-900 mt-2">₹{formatCurrency(payslip?.fixed_compensation || salary?.fixed_compensation)}</p>
            <p className="text-xs text-blue-600 mt-1">A + B + C</p>
          </CardContent>
        </Card>
        <Card className="card-flat bg-amber-50 border-amber-100">
          <CardContent className="p-6 text-center">
            <p className="text-xs text-amber-600 font-medium uppercase tracking-wider">Variable Compensation</p>
            <p className="text-2xl font-bold text-amber-900 mt-2">₹{formatCurrency(payslip?.variable_compensation || salary?.variable_compensation)}</p>
            <p className="text-xs text-amber-600 mt-1">Performance Based</p>
          </CardContent>
        </Card>
        <Card className="card-flat bg-emerald-50 border-emerald-100">
          <CardContent className="p-6 text-center">
            <p className="text-xs text-emerald-600 font-medium uppercase tracking-wider">Net Take Home</p>
            <p className="text-2xl font-bold text-emerald-900 mt-2">₹{formatCurrency(payslip?.net_pay || salary?.net_salary)}</p>
            <p className="text-xs text-emerald-600 mt-1">After Deductions</p>
          </CardContent>
        </Card>
      </div>

      {/* Insurance Coverage */}
      <Card className="card-premium border-green-100 bg-green-50/30">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <Shield className="w-6 h-6 text-green-600" />
            <CardTitle className="text-lg text-green-800">Insurance Coverage</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-6">
            <div className="text-center p-4 bg-white rounded-xl">
              <Heart className="w-8 h-8 text-green-600 mx-auto mb-2" />
              <p className="text-xs text-slate-500 uppercase">Medical Insurance</p>
              <p className="text-xl font-bold text-green-700 mt-1">₹3,00,000</p>
            </div>
            <div className="text-center p-4 bg-white rounded-xl">
              <Shield className="w-8 h-8 text-green-600 mx-auto mb-2" />
              <p className="text-xs text-slate-500 uppercase">Accident Insurance</p>
              <p className="text-xl font-bold text-green-700 mt-1">1x CTC</p>
              <p className="text-xs text-slate-400">(Min ₹5 Lakhs)</p>
            </div>
            <div className="text-center p-4 bg-white rounded-xl">
              <User className="w-8 h-8 text-green-600 mx-auto mb-2" />
              <p className="text-xs text-slate-500 uppercase">Life Insurance</p>
              <p className="text-xl font-bold text-green-700 mt-1">₹5,00,000</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Note */}
      <Card className="border-amber-200 bg-amber-50/50">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-amber-800">
              <p className="font-semibold mb-1">Important Notes:</p>
              <ul className="space-y-1 text-amber-700">
                <li>• Variable Compensation is subject to performance and company policy</li>
                <li>• PF is calculated on Basic up to ₹15,000 as per statutory requirements</li>
                <li>• Gratuity is payable as per the Payment of Gratuity Act, 1972</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

// Compensation Item Component
const CompItem = ({ icon: Icon, label, amount, isDeduction, small }) => {
  const formatCurrency = (amt) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(amt || 0);
  
  return (
    <div className={`flex items-center justify-between ${small ? 'py-1' : 'py-2'}`}>
      <div className="flex items-center gap-3">
        <div className={`${small ? 'w-7 h-7' : 'w-9 h-9'} rounded-lg flex items-center justify-center ${
          isDeduction ? 'bg-red-50' : 'bg-slate-50'
        }`}>
          <Icon className={`${small ? 'w-3.5 h-3.5' : 'w-4 h-4'} ${isDeduction ? 'text-red-500' : 'text-slate-600'}`} />
        </div>
        <span className={`${small ? 'text-sm' : 'text-sm'} text-slate-700`}>{label}</span>
      </div>
      <span className={`font-semibold ${small ? 'text-sm' : ''} ${isDeduction ? 'text-red-600' : 'text-slate-900'}`}>
        {isDeduction ? '-' : ''}₹{formatCurrency(amount)}
      </span>
    </div>
  );
};

export default EmployeeSalary;
