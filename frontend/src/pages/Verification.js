import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '../components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '../components/ui/table';
import {
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  Clock,
  FileText,
  Eye,
  User,
  Building2,
  Loader2,
  AlertCircle,
  ChevronRight,
  X,
  Download
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_CONFIG = {
  pending: { color: 'bg-slate-100 text-slate-600', label: 'Pending' },
  in_progress: { color: 'bg-amber-100 text-amber-700', label: 'In Progress' },
  under_review: { color: 'bg-blue-100 text-blue-700', label: 'Under Review' },
  approved: { color: 'bg-emerald-100 text-emerald-700', label: 'Approved' },
  rejected: { color: 'bg-red-100 text-red-700', label: 'Rejected' }
};

const DOC_STATUS_CONFIG = {
  not_uploaded: { color: 'bg-slate-100 text-slate-600', label: 'Not Uploaded' },
  uploaded: { color: 'bg-amber-100 text-amber-700', label: 'Pending Review' },
  verified: { color: 'bg-emerald-100 text-emerald-700', label: 'Verified' },
  rejected: { color: 'bg-red-100 text-red-700', label: 'Rejected' }
};

const Verification = () => {
  const { token } = useAuth();
  
  const [onboardingList, setOnboardingList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [departments, setDepartments] = useState([]);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState('All');
  const [departmentFilter, setDepartmentFilter] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');
  
  // Review Modal
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [employeeDocuments, setEmployeeDocuments] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [reviewNotes, setReviewNotes] = useState('');
  const [processingAction, setProcessingAction] = useState(null);
  
  // Document rejection
  const [rejectDocModal, setRejectDocModal] = useState(null);
  const [rejectionReason, setRejectionReason] = useState('');

  useEffect(() => {
    fetchData();
  }, [statusFilter, departmentFilter, searchTerm]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [listRes, statsRes, deptRes] = await Promise.all([
        axios.get(`${API}/onboarding/list`, {
          params: { 
            status: statusFilter !== 'All' ? statusFilter : undefined,
            department: departmentFilter !== 'All' ? departmentFilter : undefined,
            search: searchTerm || undefined
          },
          headers: { Authorization: `Bearer ${token}` }
        }),
        axios.get(`${API}/onboarding/stats`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        axios.get(`${API}/departments`, {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);
      
      setOnboardingList(listRes.data);
      setStats(statsRes.data);
      setDepartments(deptRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Failed to load verification data');
    } finally {
      setLoading(false);
    }
  };

  const openEmployeeReview = async (employee) => {
    setSelectedEmployee(employee);
    setLoadingDocs(true);
    setReviewNotes(employee.review_notes || '');
    
    try {
      const response = await axios.get(`${API}/onboarding/employee/${employee.employee_id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setEmployeeDocuments(response.data.documents || []);
    } catch (error) {
      console.error('Error fetching documents:', error);
      toast.error('Failed to load documents');
    } finally {
      setLoadingDocs(false);
    }
  };

  const handleVerifyDocument = async (docId) => {
    setProcessingAction(docId);
    try {
      await axios.post(`${API}/onboarding/verify-document`, {
        document_id: docId,
        status: 'verified'
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Document verified');
      
      // Refresh documents
      const response = await axios.get(`${API}/onboarding/employee/${selectedEmployee.employee_id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setEmployeeDocuments(response.data.documents || []);
    } catch (error) {
      toast.error('Failed to verify document');
    } finally {
      setProcessingAction(null);
    }
  };

  const handleRejectDocument = async () => {
    if (!rejectionReason.trim()) {
      toast.error('Please provide a rejection reason');
      return;
    }
    
    setProcessingAction(rejectDocModal);
    try {
      await axios.post(`${API}/onboarding/verify-document`, {
        document_id: rejectDocModal,
        status: 'rejected',
        rejection_reason: rejectionReason
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Document rejected, employee notified');
      setRejectDocModal(null);
      setRejectionReason('');
      
      // Refresh documents
      const response = await axios.get(`${API}/onboarding/employee/${selectedEmployee.employee_id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setEmployeeDocuments(response.data.documents || []);
    } catch (error) {
      toast.error('Failed to reject document');
    } finally {
      setProcessingAction(null);
    }
  };

  const handleApproveOnboarding = async () => {
    setProcessingAction('approve');
    try {
      await axios.post(`${API}/onboarding/approve/${selectedEmployee.employee_id}`, {
        status: 'approved',
        review_notes: reviewNotes
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Onboarding approved! Employee now has full access.');
      setSelectedEmployee(null);
      fetchData();
    } catch (error) {
      toast.error('Failed to approve onboarding');
    } finally {
      setProcessingAction(null);
    }
  };

  const handleRejectOnboarding = async () => {
    if (!reviewNotes.trim()) {
      toast.error('Please provide notes explaining what needs to be corrected');
      return;
    }
    
    setProcessingAction('reject');
    try {
      await axios.post(`${API}/onboarding/approve/${selectedEmployee.employee_id}`, {
        status: 'rejected',
        review_notes: reviewNotes
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Onboarding returned to employee for corrections');
      setSelectedEmployee(null);
      fetchData();
    } catch (error) {
      toast.error('Failed to reject onboarding');
    } finally {
      setProcessingAction(null);
    }
  };

  const allDocsVerified = employeeDocuments.length > 0 && 
    employeeDocuments.filter(d => d.status !== 'not_uploaded').every(d => d.status === 'verified');

  return (
    <div className="space-y-6" data-testid="verification-page">
      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500">Total Employees</p>
                <p className="text-2xl font-bold text-slate-900">{stats?.total_employees || 0}</p>
                <p className="text-xs text-slate-500 mt-1">
                  {stats?.completion_rate || 0}% completion rate
                </p>
              </div>
              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                <User className="w-5 h-5 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500">Pending Verifications</p>
                <p className="text-2xl font-bold text-amber-600">{stats?.under_review || 0}</p>
                <button 
                  onClick={() => setStatusFilter('under_review')}
                  className="text-xs text-blue-600 hover:underline mt-1"
                >
                  Review now →
                </button>
              </div>
              <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
                <Clock className="w-5 h-5 text-amber-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500">Rejected Documents</p>
                <p className="text-2xl font-bold text-red-600">{stats?.rejected_documents || 0}</p>
                <p className="text-xs text-slate-500 mt-1">
                  Require employee re-upload
                </p>
              </div>
              <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                <XCircle className="w-5 h-5 text-red-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500">Completed</p>
                <p className="text-2xl font-bold text-emerald-600">{stats?.approved || 0}</p>
                <p className="text-xs text-slate-500 mt-1">
                  Onboarding complete
                </p>
              </div>
              <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="bg-[#fffdf7] border-0 shadow-sm">
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                placeholder="Search by name or ID..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
                data-testid="verification-search"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[180px]" data-testid="status-filter">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All Status</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="in_progress">In Progress</SelectItem>
                <SelectItem value="under_review">Under Review</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
              </SelectContent>
            </Select>
            <Select value={departmentFilter} onValueChange={setDepartmentFilter}>
              <SelectTrigger className="w-[180px]" data-testid="dept-filter">
                <SelectValue placeholder="Department" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All Departments</SelectItem>
                {departments.map(dept => (
                  <SelectItem key={dept.id} value={dept.name}>{dept.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Onboarding List */}
      <Card className="bg-[#fffdf7] border-0 shadow-sm">
        <CardHeader>
          <CardTitle className="text-lg">Onboarding Queue</CardTitle>
          <CardDescription>
            Review and verify employee documents
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
            </div>
          ) : onboardingList.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500">No onboarding records found</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employee</TableHead>
                  <TableHead>Department</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {onboardingList.map((record) => {
                  const statusConfig = STATUS_CONFIG[record.status] || STATUS_CONFIG.pending;
                  
                  return (
                    <TableRow key={record.id} data-testid={`onboarding-row-${record.employee_id}`}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[#063c88] to-[#0a5cba] flex items-center justify-center">
                            <span className="text-white text-sm font-medium">
                              {record.emp_name?.charAt(0)?.toUpperCase()}
                            </span>
                          </div>
                          <div>
                            <p className="font-medium text-slate-900">{record.emp_name}</p>
                            <p className="text-xs text-slate-500">{record.emp_id}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <p className="text-sm text-slate-700">{record.department}</p>
                        <p className="text-xs text-slate-500">{record.designation}</p>
                      </TableCell>
                      <TableCell>
                        <Badge className={statusConfig.color}>
                          {statusConfig.label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <p className="text-sm text-slate-600">
                          {record.submitted_at ? new Date(record.submitted_at).toLocaleDateString() : '-'}
                        </p>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEmployeeReview(record)}
                          data-testid={`review-btn-${record.employee_id}`}
                        >
                          Review <ChevronRight className="w-4 h-4 ml-1" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Review Modal */}
      <Dialog open={!!selectedEmployee} onOpenChange={() => setSelectedEmployee(null)}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#063c88] to-[#0a5cba] flex items-center justify-center">
                <span className="text-white font-medium">
                  {selectedEmployee?.emp_name?.charAt(0)?.toUpperCase()}
                </span>
              </div>
              <div>
                <p>{selectedEmployee?.emp_name}</p>
                <p className="text-sm font-normal text-slate-500">
                  {selectedEmployee?.emp_id} • {selectedEmployee?.department}
                </p>
              </div>
            </DialogTitle>
            <DialogDescription>
              Review uploaded documents and approve or request corrections
            </DialogDescription>
          </DialogHeader>

          {loadingDocs ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin" />
            </div>
          ) : (
            <div className="space-y-4">
              {/* Documents List */}
              <div className="space-y-3">
                <h4 className="font-medium text-slate-900">Uploaded Documents</h4>
                {employeeDocuments.map((doc) => {
                  const statusConfig = DOC_STATUS_CONFIG[doc.status] || DOC_STATUS_CONFIG.not_uploaded;
                  
                  return (
                    <div 
                      key={doc.id}
                      className={`p-4 rounded-lg border ${
                        doc.status === 'rejected' ? 'border-red-200 bg-red-50' :
                        doc.status === 'verified' ? 'border-emerald-200 bg-emerald-50' :
                        'border-slate-200 bg-white'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <FileText className={`w-5 h-5 ${
                            doc.status === 'verified' ? 'text-emerald-600' :
                            doc.status === 'rejected' ? 'text-red-600' :
                            'text-slate-500'
                          }`} />
                          <div>
                            <p className="font-medium text-slate-900">{doc.document_label}</p>
                            {doc.file_name && (
                              <p className="text-xs text-slate-500">{doc.file_name}</p>
                            )}
                            {doc.rejection_reason && (
                              <p className="text-xs text-red-600 mt-1">
                                Rejected: {doc.rejection_reason}
                              </p>
                            )}
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-2">
                          <Badge className={statusConfig.color}>
                            {statusConfig.label}
                          </Badge>
                          
                          {doc.file_url && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => window.open(doc.file_url, '_blank')}
                            >
                              <Eye className="w-4 h-4" />
                            </Button>
                          )}
                          
                          {doc.status === 'uploaded' && (
                            <>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
                                onClick={() => handleVerifyDocument(doc.id)}
                                disabled={processingAction === doc.id}
                              >
                                {processingAction === doc.id ? (
                                  <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                  <CheckCircle2 className="w-4 h-4" />
                                )}
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                onClick={() => setRejectDocModal(doc.id)}
                              >
                                <XCircle className="w-4 h-4" />
                              </Button>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Review Notes */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">
                  Review Notes (visible to employee)
                </label>
                <Textarea
                  placeholder="Add notes about the review..."
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  rows={3}
                />
              </div>
            </div>
          )}

          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => setSelectedEmployee(null)}
            >
              Cancel
            </Button>
            {selectedEmployee?.status !== 'approved' && (
              <>
                <Button
                  variant="destructive"
                  onClick={handleRejectOnboarding}
                  disabled={processingAction === 'reject'}
                >
                  {processingAction === 'reject' ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <XCircle className="w-4 h-4 mr-2" />
                  )}
                  Request Corrections
                </Button>
                <Button
                  className="bg-emerald-600 hover:bg-emerald-700"
                  onClick={handleApproveOnboarding}
                  disabled={!allDocsVerified || processingAction === 'approve'}
                  data-testid="approve-onboarding-btn"
                >
                  {processingAction === 'approve' ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                  )}
                  Approve Onboarding
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Document Rejection Modal */}
      <Dialog open={!!rejectDocModal} onOpenChange={() => setRejectDocModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Document</DialogTitle>
            <DialogDescription>
              Provide a reason for rejection. The employee will be notified and asked to re-upload.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            placeholder="Enter rejection reason..."
            value={rejectionReason}
            onChange={(e) => setRejectionReason(e.target.value)}
            rows={3}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectDocModal(null)}>
              Cancel
            </Button>
            <Button 
              variant="destructive" 
              onClick={handleRejectDocument}
              disabled={processingAction === rejectDocModal}
            >
              {processingAction === rejectDocModal ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : null}
              Reject Document
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Verification;
