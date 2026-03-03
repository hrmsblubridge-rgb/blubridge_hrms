import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Progress } from '../components/ui/progress';
import { Badge } from '../components/ui/badge';
import {
  Upload,
  CheckCircle2,
  XCircle,
  Clock,
  FileText,
  AlertCircle,
  Loader2,
  ArrowRight,
  Lock,
  Eye,
  LogOut,
  User,
  Building2,
  Briefcase
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DOCUMENT_ICONS = {
  aadhaar_card: FileText,
  pan_card: FileText,
  passport: FileText,
  voter_id: FileText,
  education: FileText,
  experience: Briefcase,
  offer_letter: FileText,
  relieving_letter: FileText,
  photo: User
};

const STATUS_CONFIG = {
  not_uploaded: { color: 'bg-slate-100 text-slate-600', icon: Upload, label: 'NOT UPLOADED' },
  uploaded: { color: 'bg-amber-100 text-amber-700', icon: Clock, label: 'Pending Review' },
  verified: { color: 'bg-emerald-100 text-emerald-700', icon: CheckCircle2, label: 'Verified' },
  rejected: { color: 'bg-red-100 text-red-700', icon: XCircle, label: 'Rejected' }
};

const EmployeeOnboarding = () => {
  const { user, token, logout, updateUser } = useAuth();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  
  const [onboardingData, setOnboardingData] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [requiredDocuments, setRequiredDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [selectedDocType, setSelectedDocType] = useState(null);

  useEffect(() => {
    fetchOnboardingStatus();
  }, []);

  const fetchOnboardingStatus = async () => {
    try {
      const response = await axios.get(`${API}/onboarding/my-status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setOnboardingData(response.data.onboarding);
      setDocuments(response.data.documents || []);
      setRequiredDocuments(response.data.required_documents || []);
      
      // If already approved, redirect to dashboard
      if (response.data.onboarding_completed || response.data.onboarding?.status === 'approved') {
        updateUser({ onboarding_status: 'approved', onboarding_completed: true });
        navigate('/employee/dashboard');
      }
    } catch (error) {
      console.error('Error fetching onboarding status:', error);
      toast.error('Failed to load onboarding status');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (docType) => {
    setSelectedDocType(docType);
    fileInputRef.current?.click();
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !selectedDocType) return;

    // Validate file
    const maxSize = 5 * 1024 * 1024; // 5MB
    if (file.size > maxSize) {
      toast.error('File size must be less than 5MB');
      return;
    }

    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
    if (!allowedTypes.includes(file.type)) {
      toast.error('Please upload a JPG, PNG, WebP or PDF file');
      return;
    }

    setUploading(selectedDocType);

    try {
      // Get Cloudinary signature
      const sigResponse = await axios.get(`${API}/cloudinary/signature?folder=documents`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      const { signature, timestamp, cloud_name, api_key, folder, type } = sigResponse.data;

      // Upload to Cloudinary
      const formData = new FormData();
      formData.append('file', file);
      formData.append('signature', signature);
      formData.append('timestamp', timestamp);
      formData.append('api_key', api_key);
      formData.append('folder', folder);
      if (type) formData.append('type', type);

      const uploadResponse = await axios.post(
        `https://api.cloudinary.com/v1_1/${cloud_name}/auto/upload`,
        formData
      );

      // Save to backend
      await axios.post(`${API}/onboarding/upload-document`, {
        document_type: selectedDocType,
        file_url: uploadResponse.data.secure_url,
        file_public_id: uploadResponse.data.public_id,
        file_name: file.name
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      toast.success('Document uploaded successfully');
      fetchOnboardingStatus();
    } catch (error) {
      console.error('Upload error:', error);
      toast.error('Failed to upload document');
    } finally {
      setUploading(null);
      setSelectedDocType(null);
      e.target.value = '';
    }
  };

  const handleSubmitOnboarding = async () => {
    setSubmitting(true);
    try {
      await axios.post(`${API}/onboarding/submit`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Onboarding submitted for review!');
      fetchOnboardingStatus();
    } catch (error) {
      console.error('Submit error:', error);
      toast.error(error.response?.data?.detail || 'Failed to submit onboarding');
    } finally {
      setSubmitting(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getProgress = () => {
    if (!documents.length) return 0;
    const uploaded = documents.filter(d => d.status !== 'not_uploaded').length;
    return Math.round((uploaded / documents.length) * 100);
  };

  const canSubmit = () => {
    const requiredTypes = requiredDocuments.filter(r => r.required).map(r => r.type);
    const uploadedTypes = documents
      .filter(d => ['uploaded', 'verified'].includes(d.status))
      .map(d => d.document_type);
    return requiredTypes.every(t => uploadedTypes.includes(t));
  };

  const isReadOnly = onboardingData?.status === 'approved' || onboardingData?.status === 'under_review';

  if (loading) {
    return (
      <div className="min-h-screen bg-[#efede5] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-[#063c88]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#efede5]">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        accept=".jpg,.jpeg,.png,.webp,.pdf"
        onChange={handleFileUpload}
      />

      {/* Header */}
      <header className="bg-[#fffdf7]/90 backdrop-blur-xl border-b border-black/5 sticky top-0 z-30">
        <div className="max-w-5xl mx-auto px-4 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/logo-black.png" alt="BluBridge" className="" />
            <Badge variant="secondary" className="bg-blue-50 text-blue-700">
              Onboarding
            </Badge>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <p className="text-sm font-medium text-slate-900">{user?.name}</p>
              <p className="text-xs text-slate-500">Employee</p>
            </div>
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              <LogOut className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 lg:px-8 py-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>
            Welcome to BluBridge! 
          </h1>
          <p className="text-slate-600 mt-2">
            Complete your onboarding by uploading the required documents below.
          </p>
        </div>

        {/* Status Card */}
        <Card className="mb-6 bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#063c88] to-[#0a5cba] flex items-center justify-center">
                  <Building2 className="w-6 h-6 text-white" />
                </div>
                <div>
                  <p className="text-sm text-slate-500">Onboarding Status</p>
                  <Badge 
                    className={`mt-1 ${
                      onboardingData?.status === 'approved' ? 'bg-emerald-100 text-emerald-700' :
                      onboardingData?.status === 'under_review' ? 'bg-blue-100 text-blue-700' :
                      onboardingData?.status === 'rejected' ? 'bg-red-100 text-red-700' :
                      'bg-amber-100 text-amber-700'
                    }`}
                  >
                    {onboardingData?.status === 'approved' ? 'Approved' :
                     onboardingData?.status === 'under_review' ? 'Under Review' :
                     onboardingData?.status === 'rejected' ? 'Action Required' :
                     onboardingData?.status === 'in_progress' ? 'In Progress' :
                     'Pending'}
                  </Badge>
                </div>
              </div>
              <div className="flex-1 max-w-xs">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-600">Progress</span>
                  <span className="font-medium text-slate-900">{getProgress()}%</span>
                </div>
                <Progress value={getProgress()} className="h-2" />
              </div>
            </div>

            {onboardingData?.status === 'approved' && (
              <div className="mt-4 p-4 bg-emerald-50 rounded-lg border border-emerald-200">
                <div className="flex items-center gap-2 text-emerald-700">
                  <CheckCircle2 className="w-5 h-5" />
                  <span className="font-medium">Your onboarding is complete!</span>
                </div>
                <p className="text-sm text-emerald-600 mt-1">
                  You now have full access to the HRMS portal.
                </p>
                <Button 
                  className="mt-3 bg-emerald-600 hover:bg-emerald-700"
                  onClick={() => navigate('/employee/dashboard')}
                >
                  Go to Dashboard <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </div>
            )}

            {onboardingData?.status === 'under_review' && (
              <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
                <div className="flex items-center gap-2 text-blue-700">
                  <Clock className="w-5 h-5" />
                  <span className="font-medium">Documents Under Review</span>
                </div>
                <p className="text-sm text-blue-600 mt-1">
                  HR is reviewing your documents. You'll be notified once the review is complete.
                </p>
              </div>
            )}

            {onboardingData?.review_notes && onboardingData?.status === 'rejected' && (
              <div className="mt-4 p-4 bg-red-50 rounded-lg border border-red-200">
                <div className="flex items-center gap-2 text-red-700">
                  <AlertCircle className="w-5 h-5" />
                  <span className="font-medium">Action Required</span>
                </div>
                <p className="text-sm text-red-600 mt-1">{onboardingData.review_notes}</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Documents Grid */}
        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">Required Documents</CardTitle>
            <CardDescription>
              Upload clear copies of all required documents
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4">
              {documents.map((doc) => {
                const IconComponent = DOCUMENT_ICONS[doc.document_type] || FileText;
                const statusConfig = STATUS_CONFIG[doc.status] || STATUS_CONFIG.not_uploaded;
                const StatusIcon = statusConfig.icon;
                const isUploading = uploading === doc.document_type;
                const reqDoc = requiredDocuments.find(r => r.type === doc.document_type);
                const isRequired = reqDoc?.required;

                return (
                  <div
                    key={doc.id}
                    className={`p-4 rounded-xl border transition-all ${
                      doc.status === 'rejected' ? 'border-red-200 bg-red-50/50' :
                      doc.status === 'verified' ? 'border-emerald-200 bg-emerald-50/50' :
                      'border-slate-200 bg-white'
                    }`}
                    data-testid={`doc-${doc.document_type}`}
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                          doc.status === 'verified' ? 'bg-emerald-100' :
                          doc.status === 'rejected' ? 'bg-red-100' :
                          'bg-slate-100'
                        }`}>
                          <IconComponent className={`w-5 h-5 ${
                            doc.status === 'verified' ? 'text-emerald-600' :
                            doc.status === 'rejected' ? 'text-red-600' :
                            'text-slate-600'
                          }`} />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-slate-900">{doc.document_label}</p>
                            {isRequired && (
                              <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 border-red-300 text-red-600">
                                Required
                              </Badge>
                            )}
                          </div>
                          {doc.file_name && (
                            <p className="text-xs text-slate-500 truncate max-w-[200px]">
                              {doc.file_name}
                            </p>
                          )}
                          {doc.rejection_reason && (
                            <p className="text-xs text-red-600 mt-1">
                              Reason: {doc.rejection_reason}
                            </p>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <Badge className={statusConfig.color}>
                          <StatusIcon className="w-3 h-3 mr-1" />
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

                        {!isReadOnly && doc.status !== 'verified' && (
                          <Button
                            variant={doc.status === 'rejected' ? 'destructive' : 'outline'}
                            size="sm"
                            onClick={() => handleFileSelect(doc.document_type)}
                            disabled={isUploading}
                          >
                            {isUploading ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <>
                                <Upload className="w-4 h-4 mr-1" />
                                {doc.status === 'not_uploaded' ? 'Upload' : 'Re-upload'}
                              </>
                            )}
                          </Button>
                        )}

                        {isReadOnly && doc.status === 'verified' && (
                          <Lock className="w-4 h-4 text-slate-400" />
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Submit Button */}
            {!isReadOnly && onboardingData?.status !== 'under_review' && (
              <div className="mt-6 pt-6 border-t border-slate-200">
                <Button
                  className="w-full bg-[#063c88] hover:bg-[#052d66] h-12"
                  onClick={handleSubmitOnboarding}
                  disabled={!canSubmit() || submitting}
                  data-testid="submit-onboarding-btn"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Submitting...
                    </>
                  ) : (
                    <>
                      Submit for Review
                      <ArrowRight className="w-4 h-4 ml-2" />
                    </>
                  )}
                </Button>
                {!canSubmit() && (
                  <p className="text-xs text-slate-500 text-center mt-2">
                    Please upload all required documents before submitting
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default EmployeeOnboarding;
