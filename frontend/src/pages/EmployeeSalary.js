import { useState, useEffect, useCallback, useRef } from 'react';
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
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EmployeeSalary = () => {
  const { token } = useAuth();
  const [salary, setSalary] = useState(null);
  const [adjustments, setAdjustments] = useState([]);
  const [payslip, setPayslip] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingPayslip, setLoadingPayslip] = useState(false);
  const [generatingPDF, setGeneratingPDF] = useState(false);
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

  const handleDownloadPDF = async () => {
    if (!payslip) return;
    
    setGeneratingPDF(true);
    toast.info('Generating PDF...');
    
    try {
      const pdf = new jsPDF('p', 'mm', 'a4');
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const margin = 15;
      let yPos = margin;
      
      const monthYear = new Date(payslip.month + '-01').toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
      
      // Helper function to add text
      const addText = (text, x, y, options = {}) => {
        pdf.setFontSize(options.size || 10);
        pdf.setFont('helvetica', options.bold ? 'bold' : 'normal');
        pdf.setTextColor(options.color || '#1a1a2e');
        pdf.text(text, x, y);
      };
      
      // Helper function to format currency
      const fmtCurrency = (amt) => '₹' + new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(amt || 0);
      
      // Header Background
      pdf.setFillColor(6, 60, 136);
      pdf.rect(0, 0, pageWidth, 40, 'F');
      
      // Header Text
      pdf.setTextColor(255, 255, 255);
      pdf.setFontSize(18);
      pdf.setFont('helvetica', 'bold');
      pdf.text('Compensation & Benefits Structure', margin, 18);
      pdf.setFontSize(11);
      pdf.setFont('helvetica', 'normal');
      pdf.text(`Payslip for ${monthYear}`, margin, 26);
      pdf.setFontSize(9);
      pdf.text(`${payslip.company_name} | ${payslip.company_address}`, margin, 34);
      
      yPos = 50;
      
      // Employee Info Box
      pdf.setFillColor(248, 249, 252);
      pdf.setDrawColor(229, 231, 235);
      pdf.roundedRect(margin, yPos, pageWidth - 2 * margin, 22, 2, 2, 'FD');
      
      pdf.setTextColor(107, 114, 128);
      pdf.setFontSize(8);
      pdf.text('EMPLOYEE NAME', margin + 5, yPos + 6);
      pdf.text('EMPLOYEE ID', margin + 50, yPos + 6);
      pdf.text('DESIGNATION', margin + 95, yPos + 6);
      pdf.text('TIER', margin + 140, yPos + 6);
      
      pdf.setTextColor(31, 41, 55);
      pdf.setFontSize(10);
      pdf.setFont('helvetica', 'bold');
      pdf.text(payslip.employee_name || '', margin + 5, yPos + 14);
      pdf.text(payslip.emp_id || '', margin + 50, yPos + 14);
      pdf.text(payslip.designation || '', margin + 95, yPos + 14);
      pdf.text(payslip.tier_level || 'Tier 1', margin + 140, yPos + 14);
      
      yPos += 30;
      
      // Section A: Base Components
      pdf.setFillColor(241, 245, 249);
      pdf.roundedRect(margin, yPos, pageWidth - 2 * margin, 8, 1, 1, 'F');
      pdf.setFillColor(6, 60, 136);
      pdf.roundedRect(margin + 2, yPos + 1.5, 8, 5, 1, 1, 'F');
      pdf.setTextColor(255, 255, 255);
      pdf.setFontSize(8);
      pdf.setFont('helvetica', 'bold');
      pdf.text('A', margin + 4.5, yPos + 5);
      pdf.setTextColor(51, 65, 85);
      pdf.setFontSize(9);
      pdf.text('Base Components', margin + 14, yPos + 5.5);
      
      yPos += 12;
      
      // Table Header
      pdf.setFillColor(248, 250, 252);
      pdf.rect(margin, yPos, pageWidth - 2 * margin, 6, 'F');
      pdf.setTextColor(100, 116, 139);
      pdf.setFontSize(8);
      pdf.text('Component', margin + 3, yPos + 4);
      pdf.text('Monthly (₹)', pageWidth - margin - 25, yPos + 4);
      
      yPos += 8;
      
      // Base Components Data
      const baseComponents = [
        { label: 'Basic', amount: payslip.basic },
        { label: 'House Rent Allowance (HRA)', amount: payslip.hra },
      ];
      
      baseComponents.forEach(item => {
        pdf.setTextColor(55, 65, 81);
        pdf.setFont('helvetica', 'normal');
        pdf.setFontSize(9);
        pdf.text(item.label, margin + 3, yPos + 4);
        pdf.setFont('helvetica', 'bold');
        pdf.text(fmtCurrency(item.amount), pageWidth - margin - 25, yPos + 4);
        yPos += 7;
      });
      
      // Subtotal A
      pdf.setFillColor(248, 250, 252);
      pdf.rect(margin, yPos, pageWidth - 2 * margin, 7, 'F');
      pdf.setTextColor(31, 41, 55);
      pdf.setFont('helvetica', 'bold');
      pdf.setFontSize(9);
      pdf.text('Base Components Total (A)', margin + 3, yPos + 5);
      pdf.text(fmtCurrency(payslip.base_components_total || (payslip.basic + payslip.hra)), pageWidth - margin - 25, yPos + 5);
      
      yPos += 14;
      
      // Section B: Basket of Allowances
      pdf.setFillColor(241, 245, 249);
      pdf.roundedRect(margin, yPos, pageWidth - 2 * margin, 8, 1, 1, 'F');
      pdf.setFillColor(6, 60, 136);
      pdf.roundedRect(margin + 2, yPos + 1.5, 8, 5, 1, 1, 'F');
      pdf.setTextColor(255, 255, 255);
      pdf.setFontSize(8);
      pdf.setFont('helvetica', 'bold');
      pdf.text('B', margin + 4.5, yPos + 5);
      pdf.setTextColor(51, 65, 85);
      pdf.setFontSize(9);
      pdf.text('Basket of Allowances', margin + 14, yPos + 5.5);
      
      yPos += 12;
      
      // Table Header
      pdf.setFillColor(248, 250, 252);
      pdf.rect(margin, yPos, pageWidth - 2 * margin, 6, 'F');
      pdf.setTextColor(100, 116, 139);
      pdf.setFontSize(8);
      pdf.text('Component', margin + 3, yPos + 4);
      pdf.text('Monthly (₹)', pageWidth - margin - 25, yPos + 4);
      
      yPos += 8;
      
      // Allowances Data
      const allowances = [
        { label: 'Leave Travel Allowance (LTA)', amount: payslip.lta },
        { label: 'Phone & Internet', amount: payslip.phone_internet },
        { label: 'Performance Bonus', amount: payslip.bonus },
        { label: 'Stay & Travel', amount: payslip.stay_travel },
        { label: 'Special Allowance', amount: payslip.special_allowance },
        { label: 'Food Reimbursement', amount: payslip.food_reimbursement },
        { label: 'Medical Allowance', amount: payslip.medical_allowance },
        { label: 'Conveyance', amount: payslip.conveyance },
      ];
      
      allowances.forEach(item => {
        pdf.setTextColor(55, 65, 81);
        pdf.setFont('helvetica', 'normal');
        pdf.setFontSize(9);
        pdf.text(item.label, margin + 3, yPos + 4);
        pdf.setFont('helvetica', 'bold');
        pdf.text(fmtCurrency(item.amount), pageWidth - margin - 25, yPos + 4);
        yPos += 6;
      });
      
      // Subtotal B
      pdf.setFillColor(248, 250, 252);
      pdf.rect(margin, yPos, pageWidth - 2 * margin, 7, 'F');
      pdf.setTextColor(31, 41, 55);
      pdf.setFont('helvetica', 'bold');
      pdf.setFontSize(9);
      pdf.text('Basket Allowances Total (B)', margin + 3, yPos + 5);
      pdf.text(fmtCurrency(payslip.basket_allowances_total), pageWidth - margin - 25, yPos + 5);
      
      yPos += 14;
      
      // Section C: Retirement Benefits
      pdf.setFillColor(241, 245, 249);
      pdf.roundedRect(margin, yPos, pageWidth - 2 * margin, 8, 1, 1, 'F');
      pdf.setFillColor(6, 60, 136);
      pdf.roundedRect(margin + 2, yPos + 1.5, 8, 5, 1, 1, 'F');
      pdf.setTextColor(255, 255, 255);
      pdf.setFontSize(8);
      pdf.setFont('helvetica', 'bold');
      pdf.text('C', margin + 4.5, yPos + 5);
      pdf.setTextColor(51, 65, 85);
      pdf.setFontSize(9);
      pdf.text('Retirement Benefits', margin + 14, yPos + 5.5);
      
      yPos += 12;
      
      // Table Header
      pdf.setFillColor(248, 250, 252);
      pdf.rect(margin, yPos, pageWidth - 2 * margin, 6, 'F');
      pdf.setTextColor(100, 116, 139);
      pdf.setFontSize(8);
      pdf.text('Component', margin + 3, yPos + 4);
      pdf.text('Monthly (₹)', pageWidth - margin - 25, yPos + 4);
      
      yPos += 8;
      
      // Retirement Data
      const retirement = [
        { label: "PF Company's Contribution", amount: payslip.pf_employer },
        { label: 'Gratuity', amount: payslip.gratuity },
      ];
      
      retirement.forEach(item => {
        pdf.setTextColor(55, 65, 81);
        pdf.setFont('helvetica', 'normal');
        pdf.setFontSize(9);
        pdf.text(item.label, margin + 3, yPos + 4);
        pdf.setFont('helvetica', 'bold');
        pdf.text(fmtCurrency(item.amount), pageWidth - margin - 25, yPos + 4);
        yPos += 7;
      });
      
      // Subtotal C
      pdf.setFillColor(248, 250, 252);
      pdf.rect(margin, yPos, pageWidth - 2 * margin, 7, 'F');
      pdf.setTextColor(31, 41, 55);
      pdf.setFont('helvetica', 'bold');
      pdf.setFontSize(9);
      pdf.text('Retirement Benefits Total (C)', margin + 3, yPos + 5);
      pdf.text(fmtCurrency(payslip.retirement_benefits_total), pageWidth - margin - 25, yPos + 5);
      
      yPos += 14;
      
      // Summary Cards
      const cardWidth = (pageWidth - 2 * margin - 10) / 3;
      
      // Fixed Compensation Card
      pdf.setFillColor(224, 242, 254);
      pdf.roundedRect(margin, yPos, cardWidth, 20, 2, 2, 'F');
      pdf.setTextColor(3, 105, 161);
      pdf.setFontSize(7);
      pdf.text('FIXED COMPENSATION (A+B+C)', margin + 3, yPos + 6);
      pdf.setFontSize(12);
      pdf.setFont('helvetica', 'bold');
      pdf.text(fmtCurrency(payslip.fixed_compensation), margin + 3, yPos + 14);
      
      // Variable Compensation Card
      pdf.setFillColor(254, 243, 199);
      pdf.roundedRect(margin + cardWidth + 5, yPos, cardWidth, 20, 2, 2, 'F');
      pdf.setTextColor(146, 64, 14);
      pdf.setFontSize(7);
      pdf.text('VARIABLE COMPENSATION', margin + cardWidth + 8, yPos + 6);
      pdf.setFontSize(12);
      pdf.setFont('helvetica', 'bold');
      pdf.text(fmtCurrency(payslip.variable_compensation), margin + cardWidth + 8, yPos + 14);
      
      // CTC Card
      pdf.setFillColor(6, 60, 136);
      pdf.roundedRect(margin + 2 * cardWidth + 10, yPos, cardWidth, 20, 2, 2, 'F');
      pdf.setTextColor(255, 255, 255);
      pdf.setFontSize(7);
      pdf.text('COST TO COMPANY (CTC)', margin + 2 * cardWidth + 13, yPos + 6);
      pdf.setFontSize(12);
      pdf.setFont('helvetica', 'bold');
      pdf.text(fmtCurrency(payslip.monthly_ctc), margin + 2 * cardWidth + 13, yPos + 14);
      
      yPos += 28;
      
      // Section D: Deductions
      pdf.setFillColor(241, 245, 249);
      pdf.roundedRect(margin, yPos, pageWidth - 2 * margin, 8, 1, 1, 'F');
      pdf.setFillColor(220, 38, 38);
      pdf.roundedRect(margin + 2, yPos + 1.5, 8, 5, 1, 1, 'F');
      pdf.setTextColor(255, 255, 255);
      pdf.setFontSize(8);
      pdf.setFont('helvetica', 'bold');
      pdf.text('D', margin + 4.5, yPos + 5);
      pdf.setTextColor(51, 65, 85);
      pdf.setFontSize(9);
      pdf.text('Deductions', margin + 14, yPos + 5.5);
      
      yPos += 12;
      
      // Table Header
      pdf.setFillColor(248, 250, 252);
      pdf.rect(margin, yPos, pageWidth - 2 * margin, 6, 'F');
      pdf.setTextColor(100, 116, 139);
      pdf.setFontSize(8);
      pdf.text('Component', margin + 3, yPos + 4);
      pdf.text('Monthly (₹)', pageWidth - margin - 25, yPos + 4);
      
      yPos += 8;
      
      // Deductions Data
      const deductions = [
        { label: 'Provident Fund (Employee)', amount: payslip.pf_employee },
      ];
      if (payslip.esi_employee > 0) deductions.push({ label: 'ESI (Employee)', amount: payslip.esi_employee });
      deductions.push({ label: 'Professional Tax', amount: payslip.professional_tax });
      if (payslip.tds > 0) deductions.push({ label: 'TDS', amount: payslip.tds });
      if (payslip.lop_days > 0) deductions.push({ label: `Loss of Pay (${payslip.lop_days} days)`, amount: payslip.lop_deduction });
      
      deductions.forEach(item => {
        pdf.setTextColor(55, 65, 81);
        pdf.setFont('helvetica', 'normal');
        pdf.setFontSize(9);
        pdf.text(item.label, margin + 3, yPos + 4);
        pdf.setFont('helvetica', 'bold');
        pdf.text(fmtCurrency(item.amount), pageWidth - margin - 25, yPos + 4);
        yPos += 7;
      });
      
      // Subtotal D
      pdf.setFillColor(248, 250, 252);
      pdf.rect(margin, yPos, pageWidth - 2 * margin, 7, 'F');
      pdf.setTextColor(31, 41, 55);
      pdf.setFont('helvetica', 'bold');
      pdf.setFontSize(9);
      pdf.text('Total Deductions (D)', margin + 3, yPos + 5);
      pdf.text(fmtCurrency(payslip.total_deductions), pageWidth - margin - 25, yPos + 5);
      
      yPos += 14;
      
      // Net Pay
      pdf.setFillColor(6, 60, 136);
      pdf.roundedRect(margin, yPos, pageWidth - 2 * margin, 12, 2, 2, 'F');
      pdf.setTextColor(255, 255, 255);
      pdf.setFontSize(11);
      pdf.setFont('helvetica', 'bold');
      pdf.text('NET PAY (Take Home)', margin + 5, yPos + 8);
      pdf.setFontSize(13);
      pdf.text(fmtCurrency(payslip.net_pay), pageWidth - margin - 30, yPos + 8);
      
      yPos += 20;
      
      // Insurance Section
      pdf.setFillColor(240, 253, 244);
      pdf.setDrawColor(134, 239, 172);
      pdf.roundedRect(margin, yPos, pageWidth - 2 * margin, 30, 2, 2, 'FD');
      
      pdf.setTextColor(22, 101, 52);
      pdf.setFontSize(10);
      pdf.setFont('helvetica', 'bold');
      pdf.text('Insurance Coverage', margin + 5, yPos + 8);
      
      const insWidth = (pageWidth - 2 * margin - 20) / 3;
      yPos += 12;
      
      // Medical Insurance
      pdf.setTextColor(75, 85, 99);
      pdf.setFontSize(7);
      pdf.setFont('helvetica', 'normal');
      pdf.text('MEDICAL INSURANCE', margin + 10, yPos + 4);
      pdf.setTextColor(22, 101, 52);
      pdf.setFontSize(11);
      pdf.setFont('helvetica', 'bold');
      pdf.text('₹3,00,000', margin + 10, yPos + 11);
      
      // Accident Insurance
      pdf.setTextColor(75, 85, 99);
      pdf.setFontSize(7);
      pdf.setFont('helvetica', 'normal');
      pdf.text('ACCIDENT INSURANCE', margin + insWidth + 15, yPos + 4);
      pdf.setTextColor(22, 101, 52);
      pdf.setFontSize(11);
      pdf.setFont('helvetica', 'bold');
      pdf.text('1x CTC', margin + insWidth + 15, yPos + 11);
      
      // Life Insurance
      pdf.setTextColor(75, 85, 99);
      pdf.setFontSize(7);
      pdf.setFont('helvetica', 'normal');
      pdf.text('LIFE INSURANCE', margin + 2 * insWidth + 20, yPos + 4);
      pdf.setTextColor(22, 101, 52);
      pdf.setFontSize(11);
      pdf.setFont('helvetica', 'bold');
      pdf.text('₹5,00,000', margin + 2 * insWidth + 20, yPos + 11);
      
      yPos += 25;
      
      // Footer
      pdf.setTextColor(156, 163, 175);
      pdf.setFontSize(8);
      pdf.setFont('helvetica', 'normal');
      pdf.text('This is a computer-generated payslip and does not require a signature.', pageWidth / 2, yPos, { align: 'center' });
      pdf.text(`Generated on ${new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })} | ${payslip.company_name}`, pageWidth / 2, yPos + 5, { align: 'center' });
      
      // Save PDF
      pdf.save(`Payslip_${payslip.emp_id}_${payslip.month}.pdf`);
      toast.success('PDF downloaded successfully!');
      
    } catch (error) {
      console.error('PDF generation error:', error);
      toast.error('Failed to generate PDF');
    } finally {
      setGeneratingPDF(false);
    }
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
