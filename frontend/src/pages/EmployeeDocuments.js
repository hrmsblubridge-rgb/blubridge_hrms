import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import {
  FileText,
  Download,
  ExternalLink,
  Loader2,
  File,
  FolderOpen,
  Clock,
  User,
  AlertCircle,
  Upload,
  CheckCircle2,
  XCircle,
  Lock,
  Briefcase,
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DOCUMENT_TYPES = {
  offer_letter: {
    label: 'Offer Letter',
    description: 'Your official offer letter from the company',
    icon: FileText,
    color: 'text-blue-600 bg-blue-100',
  },
  appointment_letter: {
    label: 'Appointment Letter',
    description: 'Your appointment confirmation letter',
    icon: FileText,
    color: 'text-emerald-600 bg-emerald-100',
  },
  relieving_letter: {
    label: 'Relieving Letter',
    description: 'Relieving letter from previous employment',
    icon: FileText,
    color: 'text-orange-600 bg-orange-100',
  },
  experience_letter: {
    label: 'Experience Letter',
    description: 'Experience certificate from previous employer',
    icon: FileText,
    color: 'text-purple-600 bg-purple-100',
  },
};

// Maps onboarding document status -> badge styling/icon
const ONBOARDING_STATUS = {
  not_uploaded: { label: 'Not Uploaded', cls: 'bg-slate-100 text-slate-600 border-slate-200', icon: Upload },
  uploaded: { label: 'Pending Review', cls: 'bg-amber-100 text-amber-700 border-amber-200', icon: Clock },
  verified: { label: 'Approved', cls: 'bg-emerald-100 text-emerald-700 border-emerald-200', icon: CheckCircle2 },
  rejected: { label: 'Rejected', cls: 'bg-red-100 text-red-700 border-red-200', icon: XCircle },
};

const ONBOARDING_DOC_ICONS = {
  aadhaar_card: FileText,
  pan_card: FileText,
  passport: FileText,
  voter_id: FileText,
  education: FileText,
  experience: Briefcase,
  offer_letter: FileText,
  relieving_letter: FileText,
  photo: User,
};

const EmployeeDocuments = () => {
  const { token } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);

  // Onboarding state (uploadable section)
  const [onbDocs, setOnbDocs] = useState([]);
  const [requiredOnbDocs, setRequiredOnbDocs] = useState([]);
  const [onbLoading, setOnbLoading] = useState(true);
  const [uploadingType, setUploadingType] = useState(null);
  const fileInputRef = useRef(null);
  const selectedTypeRef = useRef(null);

  const fetchDocuments = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/employee-profile/documents`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setDocuments(response.data.documents || []);
    } catch (error) {
      console.error('Error fetching documents:', error);
      toast.error('Failed to load documents');
    } finally {
      setLoading(false);
    }
  }, [token]);

  const fetchOnboardingDocs = useCallback(async () => {
    try {
      setOnbLoading(true);
      const res = await axios.get(`${API}/onboarding/my-status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setOnbDocs(res.data.documents || []);
      setRequiredOnbDocs(res.data.required_documents || []);
    } catch (error) {
      // Non-fatal: employees without an employee_id (rare) just won't see the section.
      console.warn('Onboarding docs unavailable:', error?.response?.data?.detail);
      setOnbDocs([]);
      setRequiredOnbDocs([]);
    } finally {
      setOnbLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchDocuments();
    fetchOnboardingDocs();
  }, [fetchDocuments, fetchOnboardingDocs]);

  const getDocumentConfig = (type) => {
    return (
      DOCUMENT_TYPES[type] || {
        label: type.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
        description: 'Official document',
        icon: File,
        color: 'text-slate-600 bg-slate-100',
      }
    );
  };

  const offerLetter = documents.find((d) => d.document_type === 'offer_letter');

  // ===== Onboarding upload handlers =====
  const triggerUpload = (docType) => {
    selectedTypeRef.current = docType;
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    const docType = selectedTypeRef.current;
    if (!file || !docType) return;

    const maxSize = 5 * 1024 * 1024;
    if (file.size > maxSize) {
      toast.error('File size must be less than 5MB');
      e.target.value = '';
      return;
    }
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
    if (!allowedTypes.includes(file.type)) {
      toast.error('Please upload a JPG, PNG, WebP or PDF file');
      e.target.value = '';
      return;
    }

    setUploadingType(docType);
    try {
      // Cloudinary signed upload (same flow as the onboarding gate)
      const sigRes = await axios.get(`${API}/cloudinary/signature?folder=documents`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const { signature, timestamp, cloud_name, api_key, folder, type } = sigRes.data;

      const formData = new FormData();
      formData.append('file', file);
      formData.append('signature', signature);
      formData.append('timestamp', timestamp);
      formData.append('api_key', api_key);
      formData.append('folder', folder);
      if (type) formData.append('type', type);

      const uploadRes = await axios.post(
        `https://api.cloudinary.com/v1_1/${cloud_name}/auto/upload`,
        formData
      );

      await axios.post(
        `${API}/onboarding/upload-document`,
        {
          document_type: docType,
          file_url: uploadRes.data.secure_url,
          file_public_id: uploadRes.data.public_id,
          file_name: file.name,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      toast.success('Document uploaded — pending HR review');
      fetchOnboardingDocs();
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Failed to upload document';
      toast.error(detail);
    } finally {
      setUploadingType(null);
      selectedTypeRef.current = null;
      e.target.value = '';
    }
  };

  // Build an ordered list of (required-doc-meta + matching uploaded record).
  const onboardingRows = requiredOnbDocs.map((req) => {
    const rec = onbDocs.find((d) => d.document_type === req.type) || {};
    return {
      type: req.type,
      label: req.label,
      required: req.required,
      status: rec.status || 'not_uploaded',
      file_url: rec.file_url,
      file_name: rec.file_name,
      uploaded_at: rec.uploaded_at,
      rejection_reason: rec.rejection_reason,
    };
  });

  return (
    <div className="space-y-6 animate-fade-in" data-testid="employee-documents-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[#0b1f3b]" style={{ fontFamily: 'Outfit' }}>
            My Documents
          </h1>
          <p className="text-slate-500 mt-1">
            Upload your onboarding documents and view your official company documents
          </p>
        </div>
      </div>

      {/* Hidden file input shared by all onboarding upload buttons */}
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        accept="image/jpeg,image/png,image/webp,application/pdf"
        onChange={handleFileChange}
        data-testid="onboarding-doc-file-input"
      />

      {/* ============ Onboarding Documents (uploadable) ============ */}
      <Card className="card-premium" data-testid="onboarding-docs-section">
        <CardHeader className="border-b border-slate-100 bg-gradient-to-r from-indigo-50 to-white">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-indigo-100 flex items-center justify-center">
              <Upload className="w-6 h-6 text-indigo-600" />
            </div>
            <div>
              <CardTitle className="text-xl" style={{ fontFamily: 'Outfit' }}>
                Onboarding Documents
              </CardTitle>
              <CardDescription>
                Upload identity, education and experience documents. HR will review and approve each one.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {onbLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
            </div>
          ) : onboardingRows.length === 0 ? (
            <div className="py-10 text-center text-slate-500 text-sm">
              No onboarding document slots available for your account. Please contact HR.
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {onboardingRows.map((row) => {
                const cfg = ONBOARDING_STATUS[row.status] || ONBOARDING_STATUS.not_uploaded;
                const StatusIcon = cfg.icon;
                const DocIcon = ONBOARDING_DOC_ICONS[row.type] || FileText;
                const isVerified = row.status === 'verified';
                const isUploading = uploadingType === row.type;
                const canUpload = !isVerified; // 2c: locked only when verified

                return (
                  <div
                    key={row.type}
                    className="p-4 md:p-5 hover:bg-slate-50/60 transition-colors"
                    data-testid={`onboarding-row-${row.type}`}
                  >
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                      <div className="flex items-start gap-3 min-w-0">
                        <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0">
                          <DocIcon className="w-5 h-5 text-slate-600" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className="font-medium text-slate-900">{row.label}</p>
                            {row.required && (
                              <span className="text-[10px] font-semibold tracking-wide uppercase text-red-600 bg-red-50 border border-red-100 px-1.5 py-0.5 rounded">
                                Required
                              </span>
                            )}
                            <Badge
                              className={`${cfg.cls} border text-[11px] px-2 py-0.5 rounded-full flex items-center gap-1`}
                              data-testid={`onboarding-status-${row.type}`}
                            >
                              <StatusIcon className="w-3 h-3" />
                              {cfg.label}
                            </Badge>
                          </div>
                          {row.file_name && (
                            <p className="text-xs text-slate-500 mt-1 truncate" title={row.file_name}>
                              {row.file_name}
                              {row.uploaded_at &&
                                ` • Uploaded ${new Date(row.uploaded_at).toLocaleDateString('en-IN', {
                                  day: 'numeric',
                                  month: 'short',
                                  year: 'numeric',
                                })}`}
                            </p>
                          )}
                          {row.status === 'rejected' && row.rejection_reason && (
                            <p
                              className="text-xs text-red-600 mt-1"
                              data-testid={`onboarding-reject-reason-${row.type}`}
                            >
                              Reason: {row.rejection_reason}
                            </p>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 flex-shrink-0">
                        {row.file_url && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="rounded-lg"
                            onClick={() => window.open(row.file_url, '_blank')}
                            data-testid={`onboarding-view-${row.type}`}
                          >
                            <ExternalLink className="w-4 h-4 mr-1" />
                            View
                          </Button>
                        )}
                        {canUpload ? (
                          <Button
                            size="sm"
                            disabled={isUploading}
                            onClick={() => triggerUpload(row.type)}
                            className="bg-[#063c88] hover:bg-[#052d66] rounded-lg"
                            data-testid={`onboarding-upload-${row.type}`}
                          >
                            {isUploading ? (
                              <>
                                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                                Uploading...
                              </>
                            ) : row.status === 'rejected' ? (
                              <>
                                <Upload className="w-4 h-4 mr-1" />
                                Re-upload
                              </>
                            ) : row.status === 'not_uploaded' ? (
                              <>
                                <Upload className="w-4 h-4 mr-1" />
                                Upload
                              </>
                            ) : (
                              <>
                                <Upload className="w-4 h-4 mr-1" />
                                Replace
                              </>
                            )}
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            disabled
                            variant="outline"
                            className="rounded-lg cursor-not-allowed"
                            title="Approved by HR — raise a support ticket to update."
                            data-testid={`onboarding-locked-${row.type}`}
                          >
                            <Lock className="w-4 h-4 mr-1" />
                            Locked
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ============ Official Documents (HR-uploaded, read-only) ============ */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-[#063c88]" />
        </div>
      ) : (
        <div className="grid gap-6">
          {/* Offer Letter Card - Prominent */}
          <Card className="card-premium overflow-hidden">
            <CardHeader className="border-b border-slate-100 bg-gradient-to-r from-blue-50 to-white">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
                  <FileText className="w-6 h-6 text-blue-600" />
                </div>
                <div>
                  <CardTitle className="text-xl" style={{ fontFamily: 'Outfit' }}>
                    Offer Letter
                  </CardTitle>
                  <CardDescription>Your official offer letter from BluBridge</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-6">
              {offerLetter ? (
                <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg shadow-blue-200">
                      <File className="w-7 h-7 text-white" />
                    </div>
                    <div>
                      <p className="font-semibold text-slate-900 text-lg">{offerLetter.file_name}</p>
                      <div className="flex items-center gap-4 mt-1 text-sm text-slate-500">
                        <span className="flex items-center gap-1">
                          <Clock className="w-4 h-4" />
                          {new Date(offerLetter.uploaded_at).toLocaleDateString('en-IN', {
                            day: 'numeric',
                            month: 'short',
                            year: 'numeric',
                          })}
                        </span>
                        <span className="flex items-center gap-1">
                          <User className="w-4 h-4" />
                          Uploaded by {offerLetter.uploaded_by_name}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Button
                      variant="outline"
                      onClick={() => window.open(offerLetter.file_url, '_blank')}
                      className="rounded-xl"
                      data-testid="view-offer-btn"
                    >
                      <ExternalLink className="w-4 h-4 mr-2" />
                      View
                    </Button>
                    <a href={offerLetter.file_url} download>
                      <Button className="bg-[#063c88] hover:bg-[#052d66] rounded-xl" data-testid="download-offer-btn">
                        <Download className="w-4 h-4 mr-2" />
                        Download
                      </Button>
                    </a>
                  </div>
                </div>
              ) : (
                <div className="text-center py-10">
                  <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
                    <AlertCircle className="w-8 h-8 text-slate-400" />
                  </div>
                  <h3 className="text-lg font-semibold text-slate-700 mb-2">No Offer Letter Available</h3>
                  <p className="text-slate-500 text-sm max-w-md mx-auto">
                    Your offer letter hasn't been uploaded yet. Please contact HR if you need a copy of your offer letter.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Other Documents */}
          {documents.filter((d) => d.document_type !== 'offer_letter').length > 0 && (
            <Card className="card-premium">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center">
                    <FolderOpen className="w-5 h-5 text-slate-600" />
                  </div>
                  <div>
                    <CardTitle className="text-lg" style={{ fontFamily: 'Outfit' }}>
                      Other Documents
                    </CardTitle>
                    <CardDescription>Additional official documents</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y divide-slate-100">
                  {documents
                    .filter((d) => d.document_type !== 'offer_letter')
                    .map((doc) => {
                      const config = getDocumentConfig(doc.document_type);
                      const Icon = config.icon;

                      return (
                        <div key={doc.id} className="p-4 hover:bg-slate-50 transition-colors">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className={`w-10 h-10 rounded-lg ${config.color} flex items-center justify-center`}>
                                <Icon className="w-5 h-5" />
                              </div>
                              <div>
                                <p className="font-medium text-slate-900">{config.label}</p>
                                <p className="text-xs text-slate-500">
                                  {new Date(doc.uploaded_at).toLocaleDateString()} • {doc.file_name}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => window.open(doc.file_url, '_blank')}
                                className="text-slate-600"
                              >
                                <ExternalLink className="w-4 h-4" />
                              </Button>
                              <a href={doc.file_url} download>
                                <Button variant="ghost" size="sm" className="text-slate-600">
                                  <Download className="w-4 h-4" />
                                </Button>
                              </a>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Empty State for No Documents at All */}
          {documents.length === 0 && (
            <Card className="card-premium">
              <CardContent className="py-16 text-center">
                <div className="w-20 h-20 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
                  <FolderOpen className="w-10 h-10 text-slate-400" />
                </div>
                <h3 className="text-xl font-semibold text-slate-900 mb-2">No Official Documents Yet</h3>
                <p className="text-slate-500 max-w-md mx-auto">
                  Your HR team will upload your official documents here. Check back later or contact HR for assistance.
                </p>
              </CardContent>
            </Card>
          )}

          {/* Info Card */}
          <Card className="border-blue-100 bg-blue-50/50">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <AlertCircle className="w-4 h-4 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-blue-900">Need a document?</p>
                  <p className="text-sm text-blue-700 mt-0.5">
                    If you need any official documents like experience letters or relieving letters, please raise a
                    support ticket or contact your HR representative.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default EmployeeDocuments;
