import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import EmployeeAvatar from '../components/EmployeeAvatar';
import { viewSecureDocument, downloadSecureDocument } from '../lib/documentAccess';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { formatDate } from '../lib/dateFormat';
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
  Download,
  RotateCcw,
  Trash2
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_CONFIG = {
  not_started: { color: 'bg-slate-100 text-slate-500', label: 'Not Started' },
  pending: { color: 'bg-slate-100 text-slate-600', label: 'Not Started' },
  in_progress: { color: 'bg-amber-100 text-amber-700', label: 'Pending' },
  under_review: { color: 'bg-blue-100 text-blue-700', label: 'Pending' },
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
  const { token, user } = useAuth();
  
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

  // Remove-from-queue confirmation
  const [removeTarget, setRemoveTarget] = useState(null);
  const [removing, setRemoving] = useState(false);

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

  const isAdmin = user?.role === 'hr';

  const handleRemoveEmployee = async () => {
    if (!removeTarget) return;
    setRemoving(true);
    try {
      await axios.delete(`${API}/onboarding/employee/${removeTarget.employee_id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`${removeTarget.emp_name} removed from verification queue`);
      setRemoveTarget(null);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to remove employee');
    } finally {
      setRemoving(false);
    }
  };

  const handleRollbackDocument = async (docId) => {
    setProcessingAction(docId);
    try {
      const res = await axios.post(`${API}/onboarding/rollback-document/${docId}`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(res.data?.message || 'Verification rolled back');
      const response = await axios.get(`${API}/onboarding/employee/${selectedEmployee.employee_id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setEmployeeDocuments(response.data.documents || []);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to rollback verification');
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
                <SelectItem value="not_started">Not Started</SelectItem>
                <SelectItem value="under_review">Pending</SelectItem>
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
                          <EmployeeAvatar employeeId={record.employee_id} name={record.emp_name} size="sm" shape="circle" />
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
                          {record.submitted_at ? formatDate(record.submitted_at) : '-'}
                        </p>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEmployeeReview(record)}
                            data-testid={`review-btn-${record.employee_id}`}
                          >
                            Review <ChevronRight className="w-4 h-4 ml-1" />
                          </Button>
                          {isAdmin && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                              onClick={() => setRemoveTarget(record)}
                              data-testid={`remove-btn-${record.employee_id}`}
                            >
                              <Trash2 className="w-4 h-4 mr-1" /> Remove
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Remove-from-queue confirmation */}
      <Dialog open={!!removeTarget} onOpenChange={(o) => { if (!o) setRemoveTarget(null); }}>
        <DialogContent className="max-w-md" data-testid="remove-confirm-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <AlertCircle className="w-5 h-5" /> Remove from verification?
            </DialogTitle>
            <DialogDescription className="pt-1 text-slate-600">
              This will permanently remove <strong>{removeTarget?.emp_name}</strong>
              {removeTarget?.emp_id ? ` (${removeTarget.emp_id})` : ''} from the verification queue
              and delete their onboarding record and all uploaded documents. The employee account
              is kept. <strong>This action cannot be undone.</strong>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setRemoveTarget(null)} disabled={removing}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleRemoveEmployee}
              disabled={removing}
              data-testid="remove-confirm-btn"
            >
              {removing ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Trash2 className="w-4 h-4 mr-1" />}
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Review Modal */}
      <Dialog open={!!selectedEmployee} onOpenChange={() => setSelectedEmployee(null)}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-3">
              <EmployeeAvatar employeeId={selectedEmployee?.employee_id} name={selectedEmployee?.emp_name} size="md" shape="circle" />
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
                            <>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() =>
                                  viewSecureDocument({
                                    employeeId: selectedEmployee?.employee_id,
                                    documentType: doc.document_type,
                                    fallbackUrl: doc.file_url,
                                  })
                                }
                                title="View document"
                                data-testid={`verify-view-${doc.document_type}`}
                              >
                                <Eye className="w-4 h-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                title="Download document"
                                onClick={() =>
                                  downloadSecureDocument({
                                    employeeId: selectedEmployee?.employee_id,
                                    documentType: doc.document_type,
                                    fileName: doc.file_name || 'document',
                                    fallbackUrl: doc.file_url,
                                  })
                                }
                                data-testid={`verify-download-${doc.document_type}`}
                              >
                                <Download className="w-4 h-4" />
                              </Button>
                            </>
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

                          {isAdmin && (doc.status === 'verified' || doc.status === 'rejected') && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="text-slate-600 hover:text-slate-900 border-slate-300 rounded-lg gap-1.5"
                              onClick={() => handleRollbackDocument(doc.id)}
                              disabled={processingAction === doc.id}
                              title="Revert this verification decision to its previous state"
                              data-testid={`verify-rollback-${doc.document_type}`}
                            >
                              {processingAction === doc.id ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <RotateCcw className="w-4 h-4" />
                              )}
                              Rollback
                            </Button>
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
