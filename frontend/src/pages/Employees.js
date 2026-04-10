import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import SalarySlip from '../components/SalarySlip';
import { 
  Users, 
  Search, 
  Plus,
  Eye,
  Edit,
  Trash2,
  RotateCcw,
  Download,
  Filter,
  ChevronLeft,
  ChevronRight,
  UserCheck,
  UserX,
  Briefcase,
  Mail,
  Phone,
  MapPin,
  Calendar,
  GraduationCap,
  Building2,
  Award,
  Shield,
  CheckCircle,
  Loader2,
  FileText,
  Upload,
  ExternalLink,
  File,
  Wallet,
  DollarSign,
  TrendingUp,
  TrendingDown,
  PiggyBank,
  Receipt,
  Banknote,
  FileSpreadsheet,
  AlertCircle,
  X,
  Fingerprint,
  Hash,
  Printer
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Premium Stat Card
const StatCard = ({ title, value, icon: Icon, color, bgColor }) => (
  <div className="stat-card">
    <div className="flex items-center gap-4">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${bgColor}`}>
        <Icon className="w-6 h-6" style={{ color }} strokeWidth={1.5} />
      </div>
      <div>
        <p className="text-2xl font-bold text-slate-900 number-display">{value}</p>
        <p className="text-sm text-slate-500">{title}</p>
      </div>
    </div>
  </div>
);

const Employees = () => {
  const { getAuthHeaders, user } = useAuth();
  const [searchParams] = useSearchParams();
  const [employees, setEmployees] = useState([]);
  const [stats, setStats] = useState(null);
  const [teams, setTeams] = useState([]);
  const [departments, setDepartments] = useState([]);

  // Fixed dropdown values
  const FIXED_DEPARTMENTS = ['Research Unit', 'Support Staff', 'Business & Product'];
  const FIXED_TEAMS = ['Data', 'Parallelism', 'Quantization', 'Compiler', 'Tensor & Ops', 'Hardware', 'Administation', 'IT', 'Product Team', 'Unknown'];
  const FIXED_DESIGNATIONS = ['AI Research scientist', 'AI Research - Intern', 'Research', 'Front Office', 'Junior Admin', 'Junior System admin', 'Business & Product - Product Team', 'System Engineer'];
  const [allEmployees, setAllEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({ page: 1, limit: 10, total: 0, pages: 0 });
  
  // Initialize search from URL params
  const initialSearch = searchParams.get('search') || '';
  const [filters, setFilters] = useState({
    search: initialSearch,
    department: 'All',
    team: 'All',
    status: 'All',
    employment_type: 'All',
    tier_level: 'All',
    work_location: 'All'
  });
  
  const [showAddSheet, setShowAddSheet] = useState(false);
  const [showEditSheet, setShowEditSheet] = useState(false);
  const [showViewDialog, setShowViewDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [viewTab, setViewTab] = useState('profile');
  const [eduExpData, setEduExpData] = useState(null);
  const [loadingEduExp, setLoadingEduExp] = useState(false);
  const [verifyingEducation, setVerifyingEducation] = useState(false);
  const [verifyingExperience, setVerifyingExperience] = useState(false);
  
  // Documents state
  const [documentsData, setDocumentsData] = useState(null);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [uploadingDocument, setUploadingDocument] = useState(false);
  
  // Salary state
  const [salaryData, setSalaryData] = useState(null);
  const [loadingSalary, setLoadingSalary] = useState(false);
  const [adjustments, setAdjustments] = useState([]);
  const [showAdjustmentModal, setShowAdjustmentModal] = useState(false);
  const [newAdjustment, setNewAdjustment] = useState({
    adjustment_type: 'bonus',
    description: '',
    amount: '',
    frequency: 'one_time',
    applicable_month: new Date().toISOString().slice(0, 7),
    start_month: '',
    end_month: ''
  });
  const [savingSalary, setSavingSalary] = useState(false);
  const [showPayslip, setShowPayslip] = useState(false);
  const salarySlipRef = useRef(null);
  
  // Bulk import state
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  
  const [form, setForm] = useState({
    full_name: '', official_email: '', phone_number: '', gender: '', date_of_birth: '',
    date_of_joining: '', employment_type: 'Full-time', designation: '', tier_level: 'Mid',
    reporting_manager_id: '', department: '', team: '', work_location: 'Office',
    leave_policy: 'Standard', shift_type: 'General', custom_login_time: '', custom_logout_time: '',
    monthly_salary: 0, attendance_tracking_enabled: true, user_role: 'employee', login_enabled: true,
    custom_employee_id: '', biometric_id: ''
  });
  
  const [config, setConfig] = useState({
    employmentTypes: [], employeeStatuses: [], tierLevels: [], workLocations: [], userRoles: []
  });

  const fetchConfig = useCallback(async () => {
    try {
      const [types, statuses, tiers, locations, roles] = await Promise.all([
        axios.get(`${API}/config/employment-types`),
        axios.get(`${API}/config/employee-statuses`),
        axios.get(`${API}/config/tier-levels`),
        axios.get(`${API}/config/work-locations`),
        axios.get(`${API}/config/user-roles`)
      ]);
      setConfig({
        employmentTypes: types.data, employeeStatuses: statuses.data,
        tierLevels: tiers.data, workLocations: locations.data, userRoles: roles.data
      });
    } catch (error) {
      console.error('Config fetch error:', error);
    }
  }, []);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const params = {
        page: pagination.page, limit: pagination.limit,
        ...(filters.search && { search: filters.search }),
        ...(filters.department !== 'All' && { department: filters.department }),
        ...(filters.team !== 'All' && { team: filters.team }),
        ...(filters.status !== 'All' && { status: filters.status }),
        ...(filters.employment_type !== 'All' && { employment_type: filters.employment_type }),
        ...(filters.tier_level !== 'All' && { tier_level: filters.tier_level }),
        ...(filters.work_location !== 'All' && { work_location: filters.work_location })
      };
      
      const [employeesRes, statsRes, teamsRes, deptsRes, allEmpRes] = await Promise.all([
        axios.get(`${API}/employees`, { headers: getAuthHeaders(), params }),
        axios.get(`${API}/employees/stats`, { headers: getAuthHeaders() }),
        axios.get(`${API}/teams`, { headers: getAuthHeaders() }),
        axios.get(`${API}/departments`, { headers: getAuthHeaders() }),
        axios.get(`${API}/employees/all`, { headers: getAuthHeaders() })
      ]);
      
      setEmployees(employeesRes.data.employees);
      setPagination({ page: employeesRes.data.page, limit: employeesRes.data.limit, total: employeesRes.data.total, pages: employeesRes.data.pages });
      setStats(statsRes.data);
      setTeams(teamsRes.data);
      setDepartments(deptsRes.data);
      setAllEmployees(allEmpRes.data);
    } catch (error) {
      console.error('Fetch error:', error);
      toast.error('Failed to load employee data');
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders, pagination.page, pagination.limit, filters]);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);
  useEffect(() => { fetchData(); }, [pagination.page, filters.department, filters.team, filters.status]);

  const handleSearch = () => { setPagination(prev => ({ ...prev, page: 1 })); fetchData(); };
  const handleReset = () => {
    setFilters({ search: '', department: 'All', team: 'All', status: 'All', employment_type: 'All', tier_level: 'All', work_location: 'All' });
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const resetForm = () => {
    setForm({
      full_name: '', official_email: '', phone_number: '', gender: '', date_of_birth: '',
      date_of_joining: '', employment_type: 'Full-time', designation: '', tier_level: 'Mid',
      reporting_manager_id: '', department: '', team: '', work_location: 'Office',
      leave_policy: 'Standard', shift_type: 'General', custom_login_time: '', custom_logout_time: '',
      monthly_salary: 0, attendance_tracking_enabled: true, user_role: 'employee', login_enabled: true,
      custom_employee_id: '', biometric_id: ''
    });
  };

  const handleAdd = () => { resetForm(); setShowAddSheet(true); };
  
  const handleEdit = (employee) => {
    setSelectedEmployee(employee);
    setForm({
      full_name: employee.full_name || '', official_email: employee.official_email || '',
      phone_number: employee.phone_number || '', gender: employee.gender || '',
      date_of_birth: employee.date_of_birth || '', date_of_joining: employee.date_of_joining || '',
      employment_type: employee.employment_type || 'Full-time', designation: employee.designation || '',
      tier_level: employee.tier_level || 'Mid', reporting_manager_id: employee.reporting_manager_id || '',
      department: employee.department || '', team: employee.team || '',
      work_location: employee.work_location || 'Office', leave_policy: employee.leave_policy || 'Standard',
      shift_type: employee.shift_type || 'General', custom_login_time: employee.custom_login_time || '',
      custom_logout_time: employee.custom_logout_time || '', monthly_salary: employee.monthly_salary || 0,
      attendance_tracking_enabled: employee.attendance_tracking_enabled ?? true,
      user_role: employee.user_role || 'employee', login_enabled: employee.login_enabled ?? true,
      custom_employee_id: employee.custom_employee_id || '',
      biometric_id: employee.biometric_id || ''
    });
    setShowEditSheet(true);
  };

  const handleView = async (employee) => { 
    setSelectedEmployee(employee); 
    setViewTab('profile');
    setEduExpData(null);
    setDocumentsData(null);
    setSalaryData(null);
    setAdjustments([]);
    setShowViewDialog(true);
  };
  
  const fetchEduExp = async (employeeId) => {
    setLoadingEduExp(true);
    try {
      const response = await axios.get(`${API}/employees/${employeeId}/education-experience`, { headers: getAuthHeaders() });
      setEduExpData(response.data);
    } catch (error) {
      console.error('Error fetching education/experience:', error);
      toast.error('Failed to load education/experience data');
    } finally {
      setLoadingEduExp(false);
    }
  };
  
  const handleVerifyEducation = async (employeeId) => {
    setVerifyingEducation(true);
    try {
      await axios.post(`${API}/employees/${employeeId}/verify-education`, {}, { headers: getAuthHeaders() });
      toast.success('Education details verified');
      fetchEduExp(employeeId);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to verify education');
    } finally {
      setVerifyingEducation(false);
    }
  };
  
  const handleVerifyExperience = async (employeeId) => {
    setVerifyingExperience(true);
    try {
      await axios.post(`${API}/employees/${employeeId}/verify-experience`, {}, { headers: getAuthHeaders() });
      toast.success('Experience details verified');
      fetchEduExp(employeeId);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to verify experience');
    } finally {
      setVerifyingExperience(false);
    }
  };
  
  // Fetch employee documents
  const fetchDocuments = async (employeeId) => {
    setLoadingDocuments(true);
    try {
      const response = await axios.get(`${API}/employees/${employeeId}/documents`, { headers: getAuthHeaders() });
      setDocumentsData(response.data);
    } catch (error) {
      console.error('Error fetching documents:', error);
      toast.error('Failed to load documents');
    } finally {
      setLoadingDocuments(false);
    }
  };
  
  // Upload offer letter
  const handleUploadOfferLetter = async (file) => {
    if (!selectedEmployee) return;
    
    setUploadingDocument(true);
    try {
      // Get signed upload params from backend
      const sigResponse = await axios.get(`${API}/cloudinary/signature?folder=documents`, {
        headers: getAuthHeaders()
      });
      const { signature, timestamp, cloud_name, api_key, folder } = sigResponse.data;
      
      // Upload to Cloudinary with signed params
      const formData = new FormData();
      formData.append('file', file);
      formData.append('signature', signature);
      formData.append('timestamp', timestamp);
      formData.append('api_key', api_key);
      formData.append('folder', folder);
      formData.append('type', 'upload');
      
      const cloudinaryResponse = await axios.post(
        `https://api.cloudinary.com/v1_1/${cloud_name}/auto/upload`,
        formData
      );
      
      // Save document reference to backend
      await axios.post(`${API}/employees/${selectedEmployee.id}/documents`, {
        file_url: cloudinaryResponse.data.secure_url,
        file_name: file.name,
        file_type: file.type,
        file_public_id: cloudinaryResponse.data.public_id,
        document_type: 'offer_letter'
      }, { headers: getAuthHeaders() });
      
      toast.success('Offer letter uploaded successfully');
      fetchDocuments(selectedEmployee.id);
    } catch (error) {
      console.error('Upload error:', error);
      toast.error('Failed to upload offer letter');
    } finally {
      setUploadingDocument(false);
    }
  };
  
  // Fetch employee salary
  const fetchSalary = async (employeeId) => {
    setLoadingSalary(true);
    try {
      const [salaryRes, adjustmentsRes] = await Promise.all([
        axios.get(`${API}/employees/${employeeId}/salary`, { headers: getAuthHeaders() }),
        axios.get(`${API}/employees/${employeeId}/salary/adjustments`, { headers: getAuthHeaders() })
      ]);
      setSalaryData(salaryRes.data.salary);
      setAdjustments(adjustmentsRes.data.adjustments || []);
    } catch (error) {
      console.error('Error fetching salary:', error);
      setSalaryData(null);
    } finally {
      setLoadingSalary(false);
    }
  };
  
  // Update salary CTC
  const handleUpdateSalary = async (annualCtc) => {
    if (!selectedEmployee) return;
    setSavingSalary(true);
    try {
      await axios.put(`${API}/employees/${selectedEmployee.id}/salary`, 
        { annual_ctc: parseFloat(annualCtc) },
        { headers: getAuthHeaders() }
      );
      toast.success('Salary updated successfully');
      fetchSalary(selectedEmployee.id);
    } catch (error) {
      toast.error('Failed to update salary');
    } finally {
      setSavingSalary(false);
    }
  };
  
  // Create salary adjustment
  const handleCreateAdjustment = async () => {
    if (!selectedEmployee || !newAdjustment.description || !newAdjustment.amount) {
      toast.error('Please fill all required fields');
      return;
    }
    setSavingSalary(true);
    try {
      await axios.post(`${API}/employees/${selectedEmployee.id}/salary/adjustments`, {
        ...newAdjustment,
        amount: parseFloat(newAdjustment.amount)
      }, { headers: getAuthHeaders() });
      toast.success('Adjustment created successfully');
      setShowAdjustmentModal(false);
      setNewAdjustment({
        adjustment_type: 'bonus',
        description: '',
        amount: '',
        frequency: 'one_time',
        applicable_month: new Date().toISOString().slice(0, 7),
        start_month: '',
        end_month: ''
      });
      fetchSalary(selectedEmployee.id);
    } catch (error) {
      toast.error('Failed to create adjustment');
    } finally {
      setSavingSalary(false);
    }
  };
  
  // Delete adjustment
  const handleDeleteAdjustment = async (adjustmentId) => {
    if (!selectedEmployee) return;
    try {
      await axios.delete(`${API}/employees/${selectedEmployee.id}/salary/adjustments/${adjustmentId}`, 
        { headers: getAuthHeaders() }
      );
      toast.success('Adjustment deleted');
      fetchSalary(selectedEmployee.id);
    } catch (error) {
      toast.error('Failed to delete adjustment');
    }
  };
  
  const handlePrintPayslip = () => {
    const content = salarySlipRef.current;
    if (!content) return;
    const printWindow = window.open('', '_blank', 'width=900,height=700');
    printWindow.document.write(`<!DOCTYPE html><html><head><title>Salary Slip - ${selectedEmployee?.full_name || 'Employee'}</title><style>body{margin:0;padding:20px;font-family:'Segoe UI',sans-serif}@media print{body{padding:0}}</style></head><body>`);
    printWindow.document.write(content.innerHTML);
    printWindow.document.write('</body></html>');
    printWindow.document.close();
    setTimeout(() => { printWindow.print(); }, 300);
  };

  const handleDelete = (employee) => { setSelectedEmployee(employee); setShowDeleteDialog(true); };

  const validateForm = (isEdit = false) => {
    if (!form.full_name.trim()) { toast.error('Full name is required'); return false; }
    if (!form.official_email.trim()) { toast.error('Email is required'); return false; }
    if (!form.date_of_joining) { toast.error('Date of joining is required'); return false; }
    if (!form.department) { toast.error('Department is required'); return false; }
    if (!form.team) { toast.error('Team is required'); return false; }
    if (!form.designation.trim()) { toast.error('Designation is required'); return false; }
    if (!form.custom_employee_id.trim()) { toast.error('Employee ID is required'); return false; }
    if (!form.biometric_id.trim()) { toast.error('Biometric ID is required'); return false; }
    return true;
  };

  const submitAdd = async () => {
    if (!validateForm()) return;
    try {
      const response = await axios.post(`${API}/employees`, form, { headers: getAuthHeaders() });
      if (form.login_enabled && response.data.temp_password) {
        toast.success(`Employee added! Credentials sent to ${form.official_email}`, { duration: 5000 });
      } else {
        toast.success('Employee added successfully');
      }
      resetForm();
      setShowAddSheet(false);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to add employee');
    }
  };

  const submitEdit = async () => {
    if (!validateForm()) return;
    try {
      await axios.put(`${API}/employees/${selectedEmployee.id}`, form, { headers: getAuthHeaders() });
      toast.success('Employee updated successfully');
      setShowEditSheet(false);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update employee');
    }
  };

  const confirmDelete = async () => {
    try {
      await axios.delete(`${API}/employees/${selectedEmployee.id}`, { headers: getAuthHeaders() });
      toast.success('Employee deactivated successfully');
      setShowDeleteDialog(false);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to deactivate employee');
    }
  };

  const handleExportCSV = () => {
    const headers = ['Emp ID', 'Employee ID', 'Biometric ID', 'Name', 'Email', 'Department', 'Team', 'Designation', 'Status', 'Employment Type', 'Work Location'];
    const rows = employees.map(e => [e.emp_id, e.custom_employee_id || '', e.biometric_id || '', e.full_name, e.official_email, e.department, e.team, e.designation, e.employee_status, e.employment_type, e.work_location]);
    const csv = [headers, ...rows].map(row => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `employees-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    toast.success('CSV exported');
  };

  // Bulk Import handlers
  const handleDownloadTemplate = async () => {
    try {
      const response = await axios.get(`${API}/employees/import-template`, {
        headers: getAuthHeaders(),
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = 'employee_import_template.xlsx';
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success('Template downloaded');
    } catch (error) {
      toast.error('Failed to download template');
    }
  };

  const handleBulkImport = async () => {
    if (!importFile) { toast.error('Please select a file'); return; }
    setImporting(true);
    setImportResult(null);
    try {
      const formData = new FormData();
      formData.append('file', importFile);
      const response = await axios.post(`${API}/employees/bulk-import`, formData, {
        headers: { ...getAuthHeaders(), 'Content-Type': 'multipart/form-data' }
      });
      setImportResult(response.data);
      if (response.data.success > 0) {
        toast.success(`${response.data.success} employees imported successfully`);
        fetchData();
      }
      if (response.data.failed > 0) {
        toast.error(`${response.data.failed} records failed`);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to import employees');
    } finally {
      setImporting(false);
    }
  };

  const getStatusBadge = (status) => {
    const styles = { 'Active': 'badge-success', 'Inactive': 'badge-neutral', 'Resigned': 'badge-error' };
    return styles[status] || 'badge-neutral';
  };

  const canEdit = ['hr'].includes(user?.role);
  const filteredTeams = form.department ? teams.filter(t => t.department === form.department) : teams;

  return (
    <div className="space-y-6 animate-fade-in" data-testid="employees-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
            <Users className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Employee Management</h1>
            <p className="text-sm text-slate-500">Manage your workforce efficiently</p>
          </div>
        </div>
        {canEdit && (
          <div className="flex gap-2">
            <Button onClick={() => { setImportFile(null); setImportResult(null); setShowBulkImport(true); }} variant="outline" className="rounded-xl border-[#063c88] text-[#063c88] hover:bg-[#063c88]/5" data-testid="bulk-import-btn">
              <FileSpreadsheet className="w-4 h-4 mr-2" />
              Bulk Import
            </Button>
            <Button onClick={handleAdd} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-xl shadow-lg shadow-[#063c88]/20" data-testid="add-employee-btn">
              <Plus className="w-4 h-4 mr-2" />
              Add Employee
            </Button>
          </div>
        )}
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard title="Total Employees" value={stats.total} icon={Users} color="#063c88" bgColor="bg-blue-100" />
          <StatCard title="Active" value={stats.active} icon={UserCheck} color="#10b981" bgColor="bg-emerald-100" />
          <StatCard title="Inactive" value={stats.inactive} icon={UserX} color="#64748b" bgColor="bg-slate-100" />
          <StatCard title="Resigned" value={stats.resigned} icon={Briefcase} color="#ef4444" bgColor="bg-red-100" />
        </div>
      )}

      {/* Filters */}
      <div className="card-flat p-6">
        <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-7 gap-4">
          <div className="lg:col-span-2">
            <Label className="text-sm text-slate-600 mb-1.5 block">Search</Label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input placeholder="Name, email, ID..." value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })} onKeyPress={(e) => e.key === 'Enter' && handleSearch()} className="pl-10 rounded-lg" data-testid="filter-search" />
            </div>
          </div>
          <div>
            <Label className="text-sm text-slate-600 mb-1.5 block">Department</Label>
            <Select value={filters.department} onValueChange={(v) => setFilters({ ...filters, department: v })}>
              <SelectTrigger className="rounded-lg" data-testid="filter-department"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All</SelectItem>
                {FIXED_DEPARTMENTS.map(dept => <SelectItem key={dept} value={dept}>{dept}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-sm text-slate-600 mb-1.5 block">Team</Label>
            <Select value={filters.team} onValueChange={(v) => setFilters({ ...filters, team: v })}>
              <SelectTrigger className="rounded-lg" data-testid="filter-team"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All</SelectItem>
                {FIXED_TEAMS.map(team => <SelectItem key={team} value={team}>{team}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-sm text-slate-600 mb-1.5 block">Status</Label>
            <Select value={filters.status} onValueChange={(v) => setFilters({ ...filters, status: v })}>
              <SelectTrigger className="rounded-lg" data-testid="filter-status"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All</SelectItem>
                {config.employeeStatuses.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end gap-2">
            <Button onClick={handleSearch} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg" data-testid="search-btn">
              <Filter className="w-4 h-4 mr-1" /> Filter
            </Button>
            <Button variant="outline" onClick={handleReset} className="rounded-lg" data-testid="reset-btn">
              <RotateCcw className="w-4 h-4" />
            </Button>
          </div>
          <div className="flex items-end">
            <Button variant="outline" onClick={handleExportCSV} className="rounded-lg" data-testid="export-btn">
              <Download className="w-4 h-4 mr-1" /> Export
            </Button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card-premium overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-10 h-10 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="table-premium w-full">
                <thead>
                  <tr>
                    <th className="whitespace-nowrap">Employee ID</th>
                    <th className="whitespace-nowrap">Name</th>
                    <th className="whitespace-nowrap hidden md:table-cell">Email</th>
                    <th className="whitespace-nowrap hidden lg:table-cell">Department</th>
                    <th className="whitespace-nowrap hidden lg:table-cell">Team</th>
                    <th className="whitespace-nowrap hidden xl:table-cell">Designation</th>
                    <th className="whitespace-nowrap hidden xl:table-cell">Biometric ID</th>
                    <th className="whitespace-nowrap">Status</th>
                    <th className="whitespace-nowrap">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {employees.length === 0 ? (
                    <tr>
                      <td colSpan="9" className="text-center py-12 text-slate-500">No employees found</td>
                    </tr>
                  ) : (
                    employees.map((emp) => (
                      <tr key={emp.id}>
                        <td className="font-semibold text-[#063c88] whitespace-nowrap">{emp.custom_employee_id || emp.emp_id}</td>
                        <td>
                          <div className="flex items-center gap-2">
                            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#063c88] to-[#0a5cba] flex items-center justify-center flex-shrink-0">
                              <span className="text-white text-xs font-medium">{emp.full_name?.charAt(0)}</span>
                            </div>
                            <span className="font-medium text-slate-900 truncate max-w-[120px]" title={emp.full_name}>{emp.full_name}</span>
                          </div>
                        </td>
                        <td className="text-slate-600 hidden md:table-cell">
                          <span className="truncate max-w-[180px] block" title={emp.official_email}>{emp.official_email}</span>
                        </td>
                        <td className="text-slate-600 hidden lg:table-cell whitespace-nowrap">{emp.department}</td>
                        <td className="text-slate-600 hidden lg:table-cell">
                          <span className="truncate max-w-[120px] block" title={emp.team}>{emp.team}</span>
                        </td>
                        <td className="text-slate-600 hidden xl:table-cell">
                          <span className="truncate max-w-[100px] block" title={emp.designation}>{emp.designation}</span>
                        </td>
                        <td className="text-slate-600 hidden xl:table-cell whitespace-nowrap">
                          <span className="text-xs font-mono">{emp.biometric_id || '-'}</span>
                        </td>
                        <td><Badge className={getStatusBadge(emp.employee_status)}>{emp.employee_status}</Badge></td>
                        <td>
                          <div className="flex gap-1">
                            <Button size="sm" variant="ghost" onClick={() => handleView(emp)} className="h-7 w-7 p-0 rounded-lg" data-testid={`view-${emp.id}`}>
                              <Eye className="w-4 h-4 text-slate-500" />
                            </Button>
                            {canEdit && (
                              <>
                                <Button size="sm" variant="ghost" onClick={() => handleEdit(emp)} className="h-7 w-7 p-0 rounded-lg" data-testid={`edit-${emp.id}`}>
                                  <Edit className="w-4 h-4 text-blue-500" />
                                </Button>
                                <Button size="sm" variant="ghost" onClick={() => handleDelete(emp)} className="h-7 w-7 p-0 rounded-lg" data-testid={`delete-${emp.id}`}>
                                  <Trash2 className="w-4 h-4 text-red-500" />
                                </Button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            
            {/* Pagination */}
            <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50">
              <p className="text-sm text-slate-500">
                Showing {((pagination.page - 1) * pagination.limit) + 1} to {Math.min(pagination.page * pagination.limit, pagination.total)} of {pagination.total}
              </p>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" disabled={pagination.page <= 1} onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))} className="rounded-lg" data-testid="prev-page">
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <span className="text-sm text-slate-600 px-3">Page {pagination.page} of {pagination.pages}</span>
                <Button size="sm" variant="outline" disabled={pagination.page >= pagination.pages} onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))} className="rounded-lg" data-testid="next-page">
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Add Dialog */}
      <Dialog open={showAddSheet} onOpenChange={(open) => { if (!open) resetForm(); setShowAddSheet(open); }}>
        <DialogContent className="bg-[#fffdf7] max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Outfit' }}>Add New Employee</DialogTitle>
            <DialogDescription>Fill in the details to add a new team member</DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Tabs defaultValue="personal" className="w-full">
              <TabsList className="grid w-full grid-cols-4 mb-6 bg-slate-100 p-1 rounded-xl">
                <TabsTrigger value="personal" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">Personal</TabsTrigger>
                <TabsTrigger value="employment" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">Employment</TabsTrigger>
                <TabsTrigger value="organization" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">Organization</TabsTrigger>
                <TabsTrigger value="system" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">System</TabsTrigger>
              </TabsList>
              <TabsContent value="personal" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Full Name <span className="text-red-500">*</span></Label>
                    <Input value={form.full_name} onChange={(e) => setForm(prev => ({ ...prev, full_name: e.target.value }))} placeholder="Enter full name" className="mt-1.5 rounded-lg" data-testid="input-full-name" />
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Official Email <span className="text-red-500">*</span></Label>
                    <Input type="email" value={form.official_email} onChange={(e) => setForm(prev => ({ ...prev, official_email: e.target.value }))} placeholder="Enter email" className="mt-1.5 rounded-lg" data-testid="input-email" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Phone Number</Label>
                    <Input value={form.phone_number} onChange={(e) => setForm(prev => ({ ...prev, phone_number: e.target.value }))} placeholder="Enter phone" className="mt-1.5 rounded-lg" data-testid="input-phone" />
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Gender</Label>
                    <Select value={form.gender} onValueChange={(val) => setForm(prev => ({ ...prev, gender: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue placeholder="Select gender" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Male">Male</SelectItem>
                        <SelectItem value="Female">Female</SelectItem>
                        <SelectItem value="Other">Other</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div>
                  <Label className="text-sm font-medium text-slate-700">Date of Birth</Label>
                  <Input type="date" value={form.date_of_birth} onChange={(e) => setForm(prev => ({ ...prev, date_of_birth: e.target.value }))} className="mt-1.5 rounded-lg" data-testid="input-dob" />
                </div>
              </TabsContent>
              <TabsContent value="employment" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Employee ID <span className="text-red-500">*</span></Label>
                    <Input value={form.custom_employee_id} onChange={(e) => setForm(prev => ({ ...prev, custom_employee_id: e.target.value }))} placeholder="e.g., EID-001" className="mt-1.5 rounded-lg" data-testid="input-custom-employee-id" />
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Date of Joining</Label>
                    <Input type="date" value={form.date_of_joining} onChange={(e) => setForm(prev => ({ ...prev, date_of_joining: e.target.value }))} className="mt-1.5 rounded-lg" data-testid="input-doj" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Employment Type</Label>
                    <Select value={form.employment_type} onValueChange={(val) => setForm(prev => ({ ...prev, employment_type: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {config.employmentTypes.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Designation <span className="text-red-500">*</span></Label>
                    <Select value={form.designation} onValueChange={(val) => setForm(prev => ({ ...prev, designation: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg" data-testid="input-designation"><SelectValue placeholder="Select Designation" /></SelectTrigger>
                      <SelectContent>
                        {FIXED_DESIGNATIONS.map(d => <SelectItem key={d} value={d}>{d}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Tier Level</Label>
                    <Select value={form.tier_level} onValueChange={(val) => setForm(prev => ({ ...prev, tier_level: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {config.tierLevels.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Reporting Manager</Label>
                    <Select value={form.reporting_manager_id} onValueChange={(val) => setForm(prev => ({ ...prev, reporting_manager_id: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue placeholder="Select manager" /></SelectTrigger>
                      <SelectContent>
                        {allEmployees.filter(e => e.id !== selectedEmployee?.id).map(e => <SelectItem key={e.id} value={e.id}>{e.full_name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Work Location</Label>
                    <Select value={form.work_location} onValueChange={(val) => setForm(prev => ({ ...prev, work_location: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {config.workLocations.map(w => <SelectItem key={w} value={w}>{w}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </TabsContent>
              <TabsContent value="organization" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Department <span className="text-red-500">*</span></Label>
                    <Select value={form.department} onValueChange={(val) => setForm(prev => ({ ...prev, department: val, team: '' }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue placeholder="Select Department" /></SelectTrigger>
                      <SelectContent>
                        {FIXED_DEPARTMENTS.map(d => <SelectItem key={d} value={d}>{d}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Team <span className="text-red-500">*</span></Label>
                    <Select value={form.team} onValueChange={(val) => setForm(prev => ({ ...prev, team: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue placeholder="Select Team" /></SelectTrigger>
                      <SelectContent>
                        {FIXED_TEAMS.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Leave Policy</Label>
                    <Select value={form.leave_policy} onValueChange={(val) => setForm(prev => ({ ...prev, leave_policy: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Standard">Standard</SelectItem>
                        <SelectItem value="Extended">Extended</SelectItem>
                        <SelectItem value="Probation">Probation</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Shift Type</Label>
                    <Select value={form.shift_type} onValueChange={(val) => setForm(prev => ({ ...prev, shift_type: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="General">General (9 AM - 6 PM)</SelectItem>
                        <SelectItem value="Morning">Morning (6 AM - 3 PM)</SelectItem>
                        <SelectItem value="Evening">Evening (2 PM - 11 PM)</SelectItem>
                        <SelectItem value="Night">Night (10 PM - 7 AM)</SelectItem>
                        <SelectItem value="Flexible">Flexible</SelectItem>
                        <SelectItem value="Custom">Custom</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                {form.shift_type === 'Custom' && (
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label className="text-sm font-medium text-slate-700">Custom Login Time</Label>
                      <Input type="time" value={form.custom_login_time} onChange={(e) => setForm(prev => ({ ...prev, custom_login_time: e.target.value }))} className="mt-1.5 rounded-lg" />
                    </div>
                    <div>
                      <Label className="text-sm font-medium text-slate-700">Custom Logout Time</Label>
                      <Input type="time" value={form.custom_logout_time} onChange={(e) => setForm(prev => ({ ...prev, custom_logout_time: e.target.value }))} className="mt-1.5 rounded-lg" />
                    </div>
                  </div>
                )}
                <div>
                  <Label className="text-sm font-medium text-slate-700">Monthly Salary (INR)</Label>
                  <Input type="number" value={form.monthly_salary} onChange={(e) => setForm(prev => ({ ...prev, monthly_salary: parseFloat(e.target.value) || 0 }))} placeholder="0" className="mt-1.5 rounded-lg" data-testid="input-salary" />
                </div>
              </TabsContent>
              <TabsContent value="system" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">User Role</Label>
                    <Select value={form.user_role} onValueChange={(val) => setForm(prev => ({ ...prev, user_role: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {config.userRoles.map(r => <SelectItem key={r} value={r}>{r.replace('_', ' ').toUpperCase()}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Biometric ID <span className="text-red-500">*</span></Label>
                    <Input value={form.biometric_id} onChange={(e) => setForm(prev => ({ ...prev, biometric_id: e.target.value }))} placeholder="e.g., BIO-001" className="mt-1.5 rounded-lg" data-testid="input-biometric-id" />
                  </div>
                </div>
                <div className="flex items-center justify-between p-4 bg-slate-50 rounded-xl">
                  <div>
                    <p className="font-medium text-slate-900">Enable System Login</p>
                    <p className="text-sm text-slate-500">User can log into the system</p>
                  </div>
                  <Switch checked={form.login_enabled} onCheckedChange={(checked) => setForm(prev => ({ ...prev, login_enabled: checked }))} />
                </div>
                <div className="flex items-center justify-between p-4 bg-slate-50 rounded-xl">
                  <div>
                    <p className="font-medium text-slate-900">Attendance Tracking</p>
                    <p className="text-sm text-slate-500">Enable daily attendance</p>
                  </div>
                  <Switch checked={form.attendance_tracking_enabled} onCheckedChange={(checked) => setForm(prev => ({ ...prev, attendance_tracking_enabled: checked }))} />
                </div>
              </TabsContent>
            </Tabs>
          </div>
          <DialogFooter className="flex gap-2 pt-4 border-t border-slate-100">
            <Button variant="outline" onClick={() => { resetForm(); setShowAddSheet(false); }} className="rounded-lg">Cancel</Button>
            <Button onClick={submitAdd} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg" data-testid="submit-add">Save Employee</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={showEditSheet} onOpenChange={setShowEditSheet}>
        <DialogContent className="bg-[#fffdf7] max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Outfit' }}>Edit Employee - {selectedEmployee?.emp_id}</DialogTitle>
            <DialogDescription>Update employee information</DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Tabs defaultValue="personal" className="w-full">
              <TabsList className="grid w-full grid-cols-4 mb-6 bg-slate-100 p-1 rounded-xl">
                <TabsTrigger value="personal" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">Personal</TabsTrigger>
                <TabsTrigger value="employment" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">Employment</TabsTrigger>
                <TabsTrigger value="organization" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">Organization</TabsTrigger>
                <TabsTrigger value="system" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">System</TabsTrigger>
              </TabsList>
              <TabsContent value="personal" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Full Name <span className="text-red-500">*</span></Label>
                    <Input value={form.full_name} onChange={(e) => setForm(prev => ({ ...prev, full_name: e.target.value }))} placeholder="Enter full name" className="mt-1.5 rounded-lg" data-testid="input-full-name" />
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Official Email <span className="text-red-500">*</span></Label>
                    <Input type="email" value={form.official_email} onChange={(e) => setForm(prev => ({ ...prev, official_email: e.target.value }))} placeholder="Enter email" className="mt-1.5 rounded-lg" data-testid="input-email" disabled />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Phone Number</Label>
                    <Input value={form.phone_number} onChange={(e) => setForm(prev => ({ ...prev, phone_number: e.target.value }))} placeholder="Enter phone" className="mt-1.5 rounded-lg" data-testid="input-phone" />
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Gender</Label>
                    <Select value={form.gender} onValueChange={(val) => setForm(prev => ({ ...prev, gender: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue placeholder="Select gender" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Male">Male</SelectItem>
                        <SelectItem value="Female">Female</SelectItem>
                        <SelectItem value="Other">Other</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div>
                  <Label className="text-sm font-medium text-slate-700">Date of Birth</Label>
                  <Input type="date" value={form.date_of_birth} onChange={(e) => setForm(prev => ({ ...prev, date_of_birth: e.target.value }))} className="mt-1.5 rounded-lg" data-testid="input-dob" />
                </div>
              </TabsContent>
              <TabsContent value="employment" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Employee ID <span className="text-red-500">*</span></Label>
                    <Input value={form.custom_employee_id} onChange={(e) => setForm(prev => ({ ...prev, custom_employee_id: e.target.value }))} placeholder="e.g., EID-001" className="mt-1.5 rounded-lg" data-testid="input-custom-employee-id" />
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Date of Joining</Label>
                    <Input type="date" value={form.date_of_joining} onChange={(e) => setForm(prev => ({ ...prev, date_of_joining: e.target.value }))} className="mt-1.5 rounded-lg" data-testid="input-doj" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Employment Type</Label>
                    <Select value={form.employment_type} onValueChange={(val) => setForm(prev => ({ ...prev, employment_type: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {config.employmentTypes.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Designation <span className="text-red-500">*</span></Label>
                    <Select value={form.designation} onValueChange={(val) => setForm(prev => ({ ...prev, designation: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg" data-testid="input-designation"><SelectValue placeholder="Select Designation" /></SelectTrigger>
                      <SelectContent>
                        {FIXED_DESIGNATIONS.map(d => <SelectItem key={d} value={d}>{d}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Tier Level</Label>
                    <Select value={form.tier_level} onValueChange={(val) => setForm(prev => ({ ...prev, tier_level: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {config.tierLevels.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Reporting Manager</Label>
                    <Select value={form.reporting_manager_id} onValueChange={(val) => setForm(prev => ({ ...prev, reporting_manager_id: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue placeholder="Select manager" /></SelectTrigger>
                      <SelectContent>
                        {allEmployees.filter(e => e.id !== selectedEmployee?.id).map(e => <SelectItem key={e.id} value={e.id}>{e.full_name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Work Location</Label>
                    <Select value={form.work_location} onValueChange={(val) => setForm(prev => ({ ...prev, work_location: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {config.workLocations.map(w => <SelectItem key={w} value={w}>{w}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </TabsContent>
              <TabsContent value="organization" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Department <span className="text-red-500">*</span></Label>
                    <Select value={form.department} onValueChange={(val) => setForm(prev => ({ ...prev, department: val, team: '' }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue placeholder="Select Department" /></SelectTrigger>
                      <SelectContent>
                        {FIXED_DEPARTMENTS.map(d => <SelectItem key={d} value={d}>{d}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Team <span className="text-red-500">*</span></Label>
                    <Select value={form.team} onValueChange={(val) => setForm(prev => ({ ...prev, team: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue placeholder="Select Team" /></SelectTrigger>
                      <SelectContent>
                        {FIXED_TEAMS.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Leave Policy</Label>
                    <Select value={form.leave_policy} onValueChange={(val) => setForm(prev => ({ ...prev, leave_policy: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Standard">Standard</SelectItem>
                        <SelectItem value="Extended">Extended</SelectItem>
                        <SelectItem value="Probation">Probation</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Shift Type</Label>
                    <Select value={form.shift_type} onValueChange={(val) => setForm(prev => ({ ...prev, shift_type: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="General">General (9 AM - 6 PM)</SelectItem>
                        <SelectItem value="Morning">Morning (6 AM - 3 PM)</SelectItem>
                        <SelectItem value="Evening">Evening (2 PM - 11 PM)</SelectItem>
                        <SelectItem value="Night">Night (10 PM - 7 AM)</SelectItem>
                        <SelectItem value="Flexible">Flexible</SelectItem>
                        <SelectItem value="Custom">Custom</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                {form.shift_type === 'Custom' && (
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label className="text-sm font-medium text-slate-700">Custom Login Time</Label>
                      <Input type="time" value={form.custom_login_time} onChange={(e) => setForm(prev => ({ ...prev, custom_login_time: e.target.value }))} className="mt-1.5 rounded-lg" />
                    </div>
                    <div>
                      <Label className="text-sm font-medium text-slate-700">Custom Logout Time</Label>
                      <Input type="time" value={form.custom_logout_time} onChange={(e) => setForm(prev => ({ ...prev, custom_logout_time: e.target.value }))} className="mt-1.5 rounded-lg" />
                    </div>
                  </div>
                )}
                <div>
                  <Label className="text-sm font-medium text-slate-700">Monthly Salary (INR)</Label>
                  <Input type="number" value={form.monthly_salary} onChange={(e) => setForm(prev => ({ ...prev, monthly_salary: parseFloat(e.target.value) || 0 }))} placeholder="0" className="mt-1.5 rounded-lg" data-testid="input-salary" />
                </div>
              </TabsContent>
              <TabsContent value="system" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700">User Role</Label>
                    <Select value={form.user_role} onValueChange={(val) => setForm(prev => ({ ...prev, user_role: val }))}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {config.userRoles.map(r => <SelectItem key={r} value={r}>{r.replace('_', ' ').toUpperCase()}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-slate-700">Biometric ID <span className="text-red-500">*</span></Label>
                    <Input value={form.biometric_id} onChange={(e) => setForm(prev => ({ ...prev, biometric_id: e.target.value }))} placeholder="e.g., BIO-001" className="mt-1.5 rounded-lg" data-testid="edit-input-biometric-id" />
                  </div>
                </div>
                <div className="flex items-center justify-between p-4 bg-slate-50 rounded-xl">
                  <div>
                    <p className="font-medium text-slate-900">Attendance Tracking</p>
                    <p className="text-sm text-slate-500">Enable daily attendance</p>
                  </div>
                  <Switch checked={form.attendance_tracking_enabled} onCheckedChange={(checked) => setForm(prev => ({ ...prev, attendance_tracking_enabled: checked }))} />
                </div>
              </TabsContent>
            </Tabs>
          </div>
          <DialogFooter className="flex gap-2 pt-4 border-t border-slate-100">
            <Button variant="outline" onClick={() => setShowEditSheet(false)} className="rounded-lg">Cancel</Button>
            <Button onClick={submitEdit} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg" data-testid="submit-edit">Update Employee</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Dialog */}
      <Dialog open={showViewDialog} onOpenChange={setShowViewDialog}>
        <DialogContent className="bg-[#fffdf7] max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Outfit' }}>Employee Details</DialogTitle>
            <DialogDescription>{selectedEmployee?.emp_id}</DialogDescription>
          </DialogHeader>
          {selectedEmployee && (
            <div className="space-y-4">
              {/* Header */}
              <div className="flex items-center gap-4 pb-4 border-b border-slate-100">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#063c88] to-[#0a5cba] flex items-center justify-center shadow-lg">
                  <span className="text-white text-2xl font-bold">{selectedEmployee.full_name?.charAt(0)?.toUpperCase()}</span>
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-900">{selectedEmployee.full_name}</h3>
                  <p className="text-sm text-slate-500">{selectedEmployee.designation} • {selectedEmployee.tier_level}</p>
                  <Badge className={`${getStatusBadge(selectedEmployee.employee_status)} mt-1`}>{selectedEmployee.employee_status}</Badge>
                </div>
              </div>
              
              {/* Tabs */}
              <Tabs value={viewTab} onValueChange={(v) => { 
                setViewTab(v); 
                if (v === 'education' && !eduExpData && selectedEmployee.id) {
                  fetchEduExp(selectedEmployee.id);
                }
                if (v === 'documents' && !documentsData && selectedEmployee.id) {
                  fetchDocuments(selectedEmployee.id);
                }
                if (v === 'salary' && !salaryData && selectedEmployee.id) {
                  fetchSalary(selectedEmployee.id);
                }
              }}>
                <TabsList className="grid w-full grid-cols-4 bg-slate-100 rounded-lg p-1">
                  <TabsTrigger value="profile" className="rounded-md data-[state=active]:bg-white data-[state=active]:shadow-sm text-xs">Profile</TabsTrigger>
                  <TabsTrigger value="education" className="rounded-md data-[state=active]:bg-white data-[state=active]:shadow-sm text-xs">Education</TabsTrigger>
                  <TabsTrigger value="documents" className="rounded-md data-[state=active]:bg-white data-[state=active]:shadow-sm text-xs" data-testid="documents-tab">Documents</TabsTrigger>
                  <TabsTrigger value="salary" className="rounded-md data-[state=active]:bg-white data-[state=active]:shadow-sm text-xs" data-testid="salary-tab">Salary</TabsTrigger>
                </TabsList>
                
                {/* Profile Tab */}
                <TabsContent value="profile" className="mt-4">
                  <div className="grid grid-cols-2 gap-6">
                    <div className="space-y-4">
                      <h4 className="font-semibold text-sm text-slate-500 uppercase tracking-wide">Personal</h4>
                      <div className="space-y-3">
                        <div className="flex items-center gap-3"><Mail className="w-4 h-4 text-slate-400" /><span className="text-sm text-slate-600">{selectedEmployee.official_email}</span></div>
                        <div className="flex items-center gap-3"><Phone className="w-4 h-4 text-slate-400" /><span className="text-sm text-slate-600">{selectedEmployee.phone_number || '-'}</span></div>
                        <div className="flex items-center gap-3"><Calendar className="w-4 h-4 text-slate-400" /><span className="text-sm text-slate-600">DOB: {selectedEmployee.date_of_birth || '-'}</span></div>
                      </div>
                    </div>
                    <div className="space-y-4">
                      <h4 className="font-semibold text-sm text-slate-500 uppercase tracking-wide">Employment</h4>
                      <div className="space-y-3">
                        <div className="flex items-center gap-3"><Hash className="w-4 h-4 text-slate-400" /><span className="text-sm text-slate-600">Employee ID: {selectedEmployee.custom_employee_id || '-'}</span></div>
                        <div className="flex items-center gap-3"><Fingerprint className="w-4 h-4 text-slate-400" /><span className="text-sm text-slate-600">Biometric ID: {selectedEmployee.biometric_id || '-'}</span></div>
                        <div className="flex items-center gap-3"><Briefcase className="w-4 h-4 text-slate-400" /><span className="text-sm text-slate-600">Joined: {selectedEmployee.date_of_joining}</span></div>
                        <div className="flex items-center gap-3"><Users className="w-4 h-4 text-slate-400" /><span className="text-sm text-slate-600">{selectedEmployee.department} / {selectedEmployee.team}</span></div>
                        <div className="flex items-center gap-3"><MapPin className="w-4 h-4 text-slate-400" /><span className="text-sm text-slate-600">{selectedEmployee.work_location}</span></div>
                      </div>
                    </div>
                  </div>
                </TabsContent>
                
                {/* Education & Experience Tab */}
                <TabsContent value="education" className="mt-4">
                  {loadingEduExp ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
                    </div>
                  ) : eduExpData ? (
                    <div className="space-y-6">
                      {/* Education Section */}
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <GraduationCap className="w-5 h-5 text-blue-600" />
                            <h4 className="font-semibold text-slate-900">Education</h4>
                          </div>
                          {eduExpData.education_verified ? (
                            <Badge className="bg-emerald-100 text-emerald-700">
                              <Shield className="w-3 h-3 mr-1" />Verified
                            </Badge>
                          ) : eduExpData.education?.length > 0 && (
                            <Button 
                              size="sm" 
                              onClick={() => handleVerifyEducation(selectedEmployee.id)}
                              disabled={verifyingEducation}
                              data-testid="verify-education-btn"
                            >
                              {verifyingEducation ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <CheckCircle className="w-4 h-4 mr-1" />}
                              Verify
                            </Button>
                          )}
                        </div>
                        {eduExpData.education?.length > 0 ? (
                          <div className="space-y-2">
                            {eduExpData.education.map((edu, idx) => (
                              <div key={idx} className="p-3 bg-white rounded-lg border border-slate-200">
                                <div className="flex items-start gap-3">
                                  <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center mt-0.5">
                                    <Award className="w-4 h-4 text-blue-600" />
                                  </div>
                                  <div className="flex-1">
                                    <div className="flex items-center gap-2">
                                      <span className="font-medium text-slate-900">{edu.level}</span>
                                      <Badge variant="outline" className="text-xs">{edu.year_of_passing}</Badge>
                                    </div>
                                    <p className="text-sm text-slate-700">{edu.institution}</p>
                                    <p className="text-xs text-slate-500">{edu.board_university} • {edu.percentage_cgpa}</p>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-slate-500 py-4 text-center">No education details added</p>
                        )}
                      </div>
                      
                      {/* Experience Section */}
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Briefcase className="w-5 h-5 text-emerald-600" />
                            <h4 className="font-semibold text-slate-900">Work Experience</h4>
                          </div>
                          {eduExpData.experience_verified ? (
                            <Badge className="bg-emerald-100 text-emerald-700">
                              <Shield className="w-3 h-3 mr-1" />Verified
                            </Badge>
                          ) : eduExpData.experience?.length > 0 && (
                            <Button 
                              size="sm" 
                              onClick={() => handleVerifyExperience(selectedEmployee.id)}
                              disabled={verifyingExperience}
                              data-testid="verify-experience-btn"
                            >
                              {verifyingExperience ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <CheckCircle className="w-4 h-4 mr-1" />}
                              Verify
                            </Button>
                          )}
                        </div>
                        {eduExpData.experience?.length > 0 ? (
                          <div className="space-y-2">
                            {eduExpData.experience.map((exp, idx) => (
                              <div key={idx} className="p-3 bg-white rounded-lg border border-slate-200">
                                <div className="flex items-start gap-3">
                                  <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center mt-0.5">
                                    <Building2 className="w-4 h-4 text-emerald-600" />
                                  </div>
                                  <div className="flex-1">
                                    <div className="flex items-center gap-2">
                                      <span className="font-medium text-slate-900">{exp.designation}</span>
                                      {exp.is_current && <Badge className="bg-emerald-100 text-emerald-700 text-xs">Current</Badge>}
                                    </div>
                                    <p className="text-sm text-slate-700">{exp.company_name}</p>
                                    <p className="text-xs text-slate-500">
                                      {exp.start_date} - {exp.is_current ? 'Present' : exp.end_date}
                                    </p>
                                    {exp.responsibilities && (
                                      <p className="text-xs text-slate-600 mt-1">{exp.responsibilities}</p>
                                    )}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-slate-500 py-4 text-center">No work experience added</p>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-8 text-slate-500">
                      <p>Click to load education and experience details</p>
                    </div>
                  )}
                </TabsContent>
                
                {/* Documents Tab */}
                <TabsContent value="documents" className="mt-4">
                  {loadingDocuments ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
                    </div>
                  ) : (
                    <div className="space-y-6">
                      {/* Offer Letter Section */}
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <FileText className="w-5 h-5 text-blue-600" />
                            <h4 className="font-semibold text-slate-900">Offer Letter</h4>
                          </div>
                        </div>
                        
                        {/* Existing Offer Letter */}
                        {documentsData?.documents?.find(d => d.document_type === 'offer_letter') ? (
                          <div className="p-4 bg-white rounded-xl border border-slate-200">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                                  <File className="w-5 h-5 text-blue-600" />
                                </div>
                                <div>
                                  <p className="font-medium text-slate-900">
                                    {documentsData.documents.find(d => d.document_type === 'offer_letter')?.file_name || 'Offer Letter'}
                                  </p>
                                  <p className="text-xs text-slate-500">
                                    Uploaded by {documentsData.documents.find(d => d.document_type === 'offer_letter')?.uploaded_by_name} • {new Date(documentsData.documents.find(d => d.document_type === 'offer_letter')?.uploaded_at).toLocaleDateString()}
                                  </p>
                                </div>
                              </div>
                              <div className="flex items-center gap-2">
                                <a 
                                  href={documentsData.documents.find(d => d.document_type === 'offer_letter')?.file_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                                  data-testid="view-offer-letter-btn"
                                >
                                  <ExternalLink className="w-4 h-4" />
                                  View
                                </a>
                                <a 
                                  href={documentsData.documents.find(d => d.document_type === 'offer_letter')?.file_url}
                                  download
                                  className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                                >
                                  <Download className="w-4 h-4" />
                                  Download
                                </a>
                              </div>
                            </div>
                          </div>
                        ) : (
                          <div className="p-4 bg-slate-50 rounded-xl border-2 border-dashed border-slate-200 text-center">
                            <p className="text-sm text-slate-500 mb-2">No offer letter uploaded yet</p>
                          </div>
                        )}
                        
                        {/* Upload Button */}
                        {canEdit && (
                          <div className="mt-3">
                            <input
                              type="file"
                              id="offer-letter-upload"
                              className="hidden"
                              accept=".pdf,.doc,.docx"
                              onChange={(e) => {
                                if (e.target.files?.[0]) {
                                  handleUploadOfferLetter(e.target.files[0]);
                                }
                              }}
                            />
                            <label
                              htmlFor="offer-letter-upload"
                              className={`flex items-center justify-center gap-2 w-full py-3 border-2 border-dashed border-blue-300 rounded-xl cursor-pointer hover:bg-blue-50 hover:border-blue-400 transition-colors ${uploadingDocument ? 'opacity-50 pointer-events-none' : ''}`}
                              data-testid="upload-offer-letter-btn"
                            >
                              {uploadingDocument ? (
                                <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
                              ) : (
                                <Upload className="w-5 h-5 text-blue-500" />
                              )}
                              <span className="text-sm font-medium text-blue-600">
                                {uploadingDocument ? 'Uploading...' : documentsData?.documents?.find(d => d.document_type === 'offer_letter') ? 'Replace Offer Letter' : 'Upload Offer Letter'}
                              </span>
                            </label>
                            <p className="text-xs text-slate-400 text-center mt-2">Supported: PDF, DOC, DOCX</p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </TabsContent>
                
                {/* Salary Tab */}
                <TabsContent value="salary" className="mt-4">
                  {loadingSalary ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
                    </div>
                  ) : (
                    <div className="space-y-6">
                      {/* CTC Update + View Payslip */}
                      <div className="flex items-center justify-between gap-4">
                        {canEdit && (
                          <div className="flex-1 p-4 bg-blue-50 rounded-xl border border-blue-100">
                            <div className="flex items-center justify-between">
                              <div>
                                <p className="text-sm font-medium text-blue-700">Annual CTC</p>
                                <p className="text-2xl font-bold text-blue-900">
                                  {salaryData?.annual_ctc ? `₹${salaryData.annual_ctc.toLocaleString('en-IN')}` : 'Not Set'}
                                </p>
                              </div>
                              <div className="flex items-center gap-2">
                                <input type="number" placeholder="Enter Annual CTC" className="w-40 px-3 py-2 rounded-lg border border-blue-200 text-sm" id="new-ctc-input" data-testid="ctc-input" />
                                <Button size="sm" onClick={() => { const input = document.getElementById('new-ctc-input'); if (input?.value) handleUpdateSalary(input.value); }} disabled={savingSalary} className="bg-blue-600 hover:bg-blue-700 rounded-lg" data-testid="update-ctc-btn">
                                  {savingSalary ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Update CTC'}
                                </Button>
                              </div>
                            </div>
                          </div>
                        )}
                        {salaryData && (
                          <Button onClick={() => setShowPayslip(true)} className="bg-[#063c88] hover:bg-[#052d66] rounded-xl h-14 px-6 gap-2" data-testid="view-payslip-btn">
                            <Printer className="w-4 h-4" /> View Payslip
                          </Button>
                        )}
                      </div>
                      
                      {/* Structured Compensation Table */}
                      {salaryData ? (
                        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="bg-[#063c88]">
                                <th className="text-left px-5 py-3 text-xs text-white font-semibold uppercase tracking-wider">Particulars</th>
                                <th className="text-right px-5 py-3 text-xs text-white font-semibold uppercase tracking-wider">Monthly (INR)</th>
                                <th className="text-right px-5 py-3 text-xs text-white font-semibold uppercase tracking-wider">Annual (INR)</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr className="bg-slate-50"><td colSpan={3} className="px-5 py-2 text-xs font-bold text-slate-700 uppercase tracking-wider">Base Components (A)</td></tr>
                              <SalaryRow label="Basic" value={salaryData.basic} />
                              <SalaryRow label="HRA" value={salaryData.hra} />
                              <tr className="bg-slate-50 border-b-2 border-slate-200"><td className="px-5 py-2.5 font-bold text-slate-800">Sub Total (A)</td><td className="px-5 py-2.5 text-right font-bold text-slate-800">{fmtINR(salaryData.base_components_total)}</td><td className="px-5 py-2.5 text-right font-bold text-slate-800">{fmtINR(salaryData.base_components_total * 12)}</td></tr>
                              
                              <tr className="bg-slate-50"><td colSpan={3} className="px-5 py-2 text-xs font-bold text-slate-700 uppercase tracking-wider">Basket of Allowances (B)</td></tr>
                              <SalaryRow label="Leave Travel Assistance" value={salaryData.lta} />
                              <SalaryRow label="Phone & Internet Reimbursement" value={salaryData.phone_internet} />
                              <SalaryRow label="Bonus" value={salaryData.bonus} />
                              <SalaryRow label="Stay and Travel Allowance" value={salaryData.stay_travel} />
                              <SalaryRow label="Special Allowance" value={salaryData.special_allowance} />
                              <SalaryRow label="Food Reimbursement" value={salaryData.food_reimbursement} />
                              {salaryData.medical_allowance > 0 && <SalaryRow label="Medical Allowance" value={salaryData.medical_allowance} />}
                              {salaryData.conveyance > 0 && <SalaryRow label="Conveyance" value={salaryData.conveyance} />}
                              <tr className="bg-slate-50 border-b-2 border-slate-200"><td className="px-5 py-2.5 font-bold text-slate-800">Sub Total (B)</td><td className="px-5 py-2.5 text-right font-bold text-slate-800">{fmtINR(salaryData.basket_allowances_total)}</td><td className="px-5 py-2.5 text-right font-bold text-slate-800">{fmtINR(salaryData.basket_allowances_total * 12)}</td></tr>
                              
                              <tr className="bg-slate-50"><td colSpan={3} className="px-5 py-2 text-xs font-bold text-slate-700 uppercase tracking-wider">Retirement Benefits (C)</td></tr>
                              <SalaryRow label="PF Company Contribution" value={salaryData.pf_employer} />
                              <SalaryRow label="Gratuity" value={salaryData.gratuity} />
                              <tr className="bg-slate-50 border-b-2 border-slate-200"><td className="px-5 py-2.5 font-bold text-slate-800">Sub Total (C)</td><td className="px-5 py-2.5 text-right font-bold text-slate-800">{fmtINR(salaryData.retirement_benefits_total)}</td><td className="px-5 py-2.5 text-right font-bold text-slate-800">{fmtINR(salaryData.retirement_benefits_total * 12)}</td></tr>
                              
                              <tr className="bg-blue-50 border-b-2 border-blue-200"><td className="px-5 py-3 font-bold text-blue-800">Fixed Compensation (A+B+C)</td><td className="px-5 py-3 text-right font-bold text-blue-800">{fmtINR(salaryData.fixed_compensation)}</td><td className="px-5 py-3 text-right font-bold text-blue-800">{fmtINR(salaryData.fixed_compensation * 12)}</td></tr>
                              
                              <SalaryRow label="Variable Compensation (at 100%)" value={salaryData.variable_compensation} />
                              
                              <tr className="bg-[#063c88]"><td className="px-5 py-3 font-bold text-white text-sm">Cost To Company (CTC)</td><td className="px-5 py-3 text-right font-bold text-white text-sm">{fmtINR(salaryData.monthly_ctc)}</td><td className="px-5 py-3 text-right font-bold text-white text-sm">{fmtINR(salaryData.annual_ctc)}</td></tr>
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <div className="text-center py-8 text-slate-500">
                          <Wallet className="w-12 h-12 mx-auto text-slate-300 mb-2" />
                          <p>No salary structure configured</p>
                          <p className="text-sm">Enter Annual CTC above to auto-calculate salary breakup</p>
                        </div>
                      )}
                      
                      {/* Deductions Summary */}
                      {salaryData && (
                        <div className="grid grid-cols-2 gap-4">
                          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
                            <div className="p-4 bg-red-50 border-b border-red-100">
                              <h4 className="text-sm font-bold text-red-700 flex items-center gap-2"><TrendingDown className="w-4 h-4" /> Employee Deductions</h4>
                            </div>
                            <div className="divide-y divide-slate-100">
                              <div className="p-3 flex justify-between"><span className="text-slate-600">PF (Employee)</span><span className="font-medium text-red-600">{fmtINR(salaryData.pf_employee)}</span></div>
                              {salaryData.esi_employee > 0 && <div className="p-3 flex justify-between"><span className="text-slate-600">ESI</span><span className="font-medium text-red-600">{fmtINR(salaryData.esi_employee)}</span></div>}
                              <div className="p-3 flex justify-between"><span className="text-slate-600">Professional Tax</span><span className="font-medium text-red-600">{fmtINR(salaryData.professional_tax)}</span></div>
                              {salaryData.tds > 0 && <div className="p-3 flex justify-between"><span className="text-slate-600">TDS</span><span className="font-medium text-red-600">{fmtINR(salaryData.tds)}</span></div>}
                              <div className="p-3 bg-red-50 flex justify-between font-bold"><span className="text-red-700">Total Deductions</span><span className="text-red-700">{fmtINR(salaryData.total_deductions)}</span></div>
                            </div>
                          </div>
                          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
                            <div className="p-4 bg-slate-50 border-b border-slate-100">
                              <h4 className="text-sm font-bold text-slate-700 flex items-center gap-2"><Shield className="w-4 h-4" /> Insurance Coverage</h4>
                            </div>
                            <div className="divide-y divide-slate-100">
                              <div className="p-3 flex justify-between"><span className="text-slate-600">Medical Insurance</span><span className="font-medium">Up to ₹3,00,000 p.a.</span></div>
                              <div className="p-3 flex justify-between"><span className="text-slate-600">Accident Insurance</span><span className="font-medium">1x CTC (Min ₹5,00,000)</span></div>
                              <div className="p-3 flex justify-between"><span className="text-slate-600">Life Insurance</span><span className="font-medium">₹5,00,000</span></div>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      {/* Net Salary */}
                      {salaryData && (
                        <div className="p-5 bg-gradient-to-r from-[#063c88] to-[#0a5cba] rounded-2xl text-white">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-blue-200 text-sm">Monthly Net Salary (Take Home)</p>
                              <p className="text-3xl font-bold">₹{salaryData.net_salary?.toLocaleString('en-IN')}</p>
                            </div>
                            <div className="text-right">
                              <p className="text-blue-200 text-sm">Annual Take Home</p>
                              <p className="text-xl font-bold">₹{(salaryData.net_salary * 12)?.toLocaleString('en-IN')}</p>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      {/* Adjustments Section */}
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <h4 className="font-semibold text-slate-700 flex items-center gap-2">
                            <Receipt className="w-4 h-4" /> Salary Adjustments
                          </h4>
                          {canEdit && (
                            <Button 
                              size="sm" 
                              variant="outline"
                              onClick={() => setShowAdjustmentModal(true)}
                              className="rounded-lg"
                            >
                              <Plus className="w-4 h-4 mr-1" /> Add Adjustment
                            </Button>
                          )}
                        </div>
                        
                        {adjustments.length > 0 ? (
                          <div className="space-y-2">
                            {adjustments.map((adj) => (
                              <div key={adj.id} className="p-3 bg-white rounded-lg border border-slate-200 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${adj.category === 'earning' ? 'bg-emerald-100' : 'bg-red-100'}`}>
                                    {adj.category === 'earning' ? (
                                      <TrendingUp className="w-4 h-4 text-emerald-600" />
                                    ) : (
                                      <TrendingDown className="w-4 h-4 text-red-600" />
                                    )}
                                  </div>
                                  <div>
                                    <p className="text-sm font-medium text-slate-700">{adj.description}</p>
                                    <p className="text-xs text-slate-500">
                                      {adj.adjustment_type} • {adj.frequency === 'recurring' ? 'Recurring' : `One-time (${adj.applicable_month})`}
                                    </p>
                                  </div>
                                </div>
                                <div className="flex items-center gap-3">
                                  <span className={`font-semibold ${adj.category === 'earning' ? 'text-emerald-600' : 'text-red-600'}`}>
                                    {adj.category === 'earning' ? '+' : '-'}₹{adj.amount?.toLocaleString('en-IN')}
                                  </span>
                                  {canEdit && (
                                    <Button 
                                      size="sm" 
                                      variant="ghost" 
                                      onClick={() => handleDeleteAdjustment(adj.id)}
                                      className="h-8 w-8 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                    >
                                      <Trash2 className="w-4 h-4" />
                                    </Button>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-slate-500 text-center py-4">No adjustments added</p>
                        )}
                      </div>
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowViewDialog(false)} className="rounded-lg">Close</Button>
            {canEdit && <Button onClick={() => { setShowViewDialog(false); handleEdit(selectedEmployee); }} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg">Edit</Button>}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Outfit' }}>Deactivate Employee</DialogTitle>
            <DialogDescription>This will disable their login access and mark them as inactive.</DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <p className="text-slate-600">Are you sure you want to deactivate <span className="font-semibold">{selectedEmployee?.full_name}</span>?</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)} className="rounded-lg">Cancel</Button>
            <Button onClick={confirmDelete} className="bg-red-500 hover:bg-red-600 text-white rounded-lg" data-testid="confirm-delete">Deactivate</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
      {/* Adjustment Modal */}
      <Dialog open={showAdjustmentModal} onOpenChange={setShowAdjustmentModal}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Outfit' }}>Add Salary Adjustment</DialogTitle>
            <DialogDescription>Add bonus, incentive, deduction or reimbursement</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1.5 block">Type</label>
              <Select value={newAdjustment.adjustment_type} onValueChange={(v) => setNewAdjustment({...newAdjustment, adjustment_type: v})}>
                <SelectTrigger className="rounded-lg">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="bonus">Bonus</SelectItem>
                  <SelectItem value="incentive">Incentive</SelectItem>
                  <SelectItem value="reimbursement">Reimbursement</SelectItem>
                  <SelectItem value="deduction">Deduction</SelectItem>
                  <SelectItem value="lop">Loss of Pay</SelectItem>
                  <SelectItem value="advance_recovery">Advance Recovery</SelectItem>
                  <SelectItem value="penalty">Penalty</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1.5 block">Description</label>
              <Input
                placeholder="e.g., Performance Bonus Q1"
                value={newAdjustment.description}
                onChange={(e) => setNewAdjustment({...newAdjustment, description: e.target.value})}
                className="rounded-lg"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1.5 block">Amount (₹)</label>
              <Input
                type="number"
                placeholder="Enter amount"
                value={newAdjustment.amount}
                onChange={(e) => setNewAdjustment({...newAdjustment, amount: e.target.value})}
                className="rounded-lg"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1.5 block">Frequency</label>
              <Select value={newAdjustment.frequency} onValueChange={(v) => setNewAdjustment({...newAdjustment, frequency: v})}>
                <SelectTrigger className="rounded-lg">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="one_time">One Time</SelectItem>
                  <SelectItem value="recurring">Recurring</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {newAdjustment.frequency === 'one_time' && (
              <div>
                <label className="text-sm font-medium text-slate-700 mb-1.5 block">Applicable Month</label>
                <Input
                  type="month"
                  value={newAdjustment.applicable_month}
                  onChange={(e) => setNewAdjustment({...newAdjustment, applicable_month: e.target.value})}
                  className="rounded-lg"
                />
              </div>
            )}
            {newAdjustment.frequency === 'recurring' && (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-slate-700 mb-1.5 block">Start Month</label>
                  <Input
                    type="month"
                    value={newAdjustment.start_month}
                    onChange={(e) => setNewAdjustment({...newAdjustment, start_month: e.target.value})}
                    className="rounded-lg"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700 mb-1.5 block">End Month (Optional)</label>
                  <Input
                    type="month"
                    value={newAdjustment.end_month}
                    onChange={(e) => setNewAdjustment({...newAdjustment, end_month: e.target.value})}
                    className="rounded-lg"
                  />
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdjustmentModal(false)} className="rounded-lg">Cancel</Button>
            <Button onClick={handleCreateAdjustment} disabled={savingSalary} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg">
              {savingSalary ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Add Adjustment
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Import Dialog */}
      <Dialog open={showBulkImport} onOpenChange={(open) => { if (!open) { setImportFile(null); setImportResult(null); } setShowBulkImport(open); }}>
        <DialogContent className="bg-[#fffdf7] max-w-xl max-h-[85vh] overflow-y-auto rounded-2xl">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Outfit' }}>Bulk Import Employees</DialogTitle>
            <DialogDescription>Upload an Excel or CSV file to import multiple employees at once</DialogDescription>
          </DialogHeader>
          <div className="space-y-5 py-4">
            {/* Download Template */}
            <div className="flex items-center justify-between p-4 bg-blue-50 rounded-xl border border-blue-100">
              <div>
                <p className="font-medium text-slate-900 text-sm">Sample Template</p>
                <p className="text-xs text-slate-500">Download the template to fill in employee data</p>
              </div>
              <Button size="sm" variant="outline" onClick={handleDownloadTemplate} className="rounded-lg border-[#063c88] text-[#063c88]" data-testid="download-template-btn">
                <Download className="w-4 h-4 mr-1" /> Template
              </Button>
            </div>

            {/* File Upload */}
            <div className="space-y-2">
              <Label className="text-sm font-medium text-slate-700">Upload File (.xlsx or .csv)</Label>
              <div className="relative">
                <input
                  type="file"
                  accept=".xlsx,.csv"
                  onChange={(e) => { setImportFile(e.target.files[0]); setImportResult(null); }}
                  className="block w-full text-sm text-slate-500 file:mr-4 file:py-2.5 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-[#063c88] file:text-white hover:file:bg-[#052d66] cursor-pointer border border-slate-200 rounded-lg"
                  data-testid="import-file-input"
                />
              </div>
              {importFile && (
                <p className="text-xs text-slate-500 flex items-center gap-1">
                  <FileSpreadsheet className="w-3 h-3" /> {importFile.name} ({(importFile.size / 1024).toFixed(1)} KB)
                </p>
              )}
            </div>

            {/* Import Results */}
            {importResult && (
              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-3">
                  <div className="text-center p-3 bg-slate-100 rounded-lg">
                    <p className="text-lg font-bold text-slate-900">{importResult.total}</p>
                    <p className="text-xs text-slate-500">Total Records</p>
                  </div>
                  <div className="text-center p-3 bg-emerald-50 rounded-lg">
                    <p className="text-lg font-bold text-emerald-600">{importResult.success}</p>
                    <p className="text-xs text-emerald-600">Successful</p>
                  </div>
                  <div className="text-center p-3 bg-red-50 rounded-lg">
                    <p className="text-lg font-bold text-red-600">{importResult.failed}</p>
                    <p className="text-xs text-red-600">Failed</p>
                  </div>
                </div>

                {importResult.errors?.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-red-600 flex items-center gap-1">
                      <AlertCircle className="w-4 h-4" /> Error Report
                    </p>
                    <div className="max-h-48 overflow-y-auto space-y-1.5 border border-red-100 rounded-lg p-3 bg-red-50/50">
                      {importResult.errors.map((err, idx) => (
                        <div key={idx} className="text-xs bg-white p-2 rounded border border-red-100" data-testid={`import-error-${idx}`}>
                          <span className="font-medium text-slate-700">Row {err.row} ({err.name}):</span>
                          <ul className="mt-0.5 ml-3 list-disc text-red-600">
                            {err.errors.map((e, i) => <li key={i}>{e}</li>)}
                          </ul>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
          <DialogFooter className="flex gap-2 pt-4 border-t border-slate-100">
            <Button variant="outline" onClick={() => setShowBulkImport(false)} className="rounded-lg">Close</Button>
            <Button
              onClick={handleBulkImport}
              disabled={!importFile || importing}
              className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg"
              data-testid="import-submit-btn"
            >
              {importing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Upload className="w-4 h-4 mr-2" />}
              {importing ? 'Importing...' : 'Import Employees'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Payslip Dialog */}
      <Dialog open={showPayslip} onOpenChange={setShowPayslip}>
        <DialogContent className="bg-white max-w-[950px] max-h-[90vh] overflow-y-auto rounded-2xl p-0" data-testid="payslip-dialog">
          <DialogHeader className="px-6 pt-5 pb-0">
            <DialogTitle style={{ fontFamily: 'Outfit' }} className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-[#063c88]" /> Salary Slip
            </DialogTitle>
            <DialogDescription>Compensation structure for {selectedEmployee?.full_name}</DialogDescription>
          </DialogHeader>
          <div className="px-4 py-4">
            <SalarySlip
              ref={salarySlipRef}
              employee={selectedEmployee}
              salary={salaryData}
              month={new Date().toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}
            />
          </div>
          <DialogFooter className="px-6 pb-5 pt-2 border-t border-slate-100 flex gap-2">
            <Button variant="outline" onClick={() => setShowPayslip(false)} className="rounded-lg">Close</Button>
            <Button onClick={handlePrintPayslip} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg gap-2" data-testid="print-payslip-btn">
              <Printer className="w-4 h-4" /> Print / Download PDF
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

// Salary Item Component
const SalaryItem = ({ label, amount, isDeduction }) => (
  <div className="p-3 flex justify-between items-center">
    <span className="text-sm text-slate-600">{label}</span>
    <span className={`text-sm font-medium ${isDeduction ? 'text-red-600' : 'text-slate-900'}`}>
      {isDeduction && amount > 0 ? '-' : ''}₹{amount?.toLocaleString('en-IN') || '0'}
    </span>
  </div>
);

const fmtINR = (v) => {
  if (!v && v !== 0) return '₹0';
  return `₹${Math.round(Number(v)).toLocaleString('en-IN')}`;
};

const SalaryRow = ({ label, value }) => (
  <tr className="border-b border-slate-100 hover:bg-slate-50/50">
    <td className="px-5 py-2.5 text-slate-700">{label}</td>
    <td className="px-5 py-2.5 text-right tabular-nums text-slate-800">{fmtINR(value)}</td>
    <td className="px-5 py-2.5 text-right tabular-nums text-slate-800">{fmtINR(value * 12)}</td>
  </tr>
);

export default Employees;
