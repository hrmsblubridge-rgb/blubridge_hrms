import { useState, useEffect, useCallback } from 'react';
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
  AlertCircle
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DOCUMENT_TYPES = {
  offer_letter: {
    label: 'Offer Letter',
    description: 'Your official offer letter from the company',
    icon: FileText,
    color: 'text-blue-600 bg-blue-100'
  },
  appointment_letter: {
    label: 'Appointment Letter',
    description: 'Your appointment confirmation letter',
    icon: FileText,
    color: 'text-emerald-600 bg-emerald-100'
  },
  relieving_letter: {
    label: 'Relieving Letter',
    description: 'Relieving letter from previous employment',
    icon: FileText,
    color: 'text-orange-600 bg-orange-100'
  },
  experience_letter: {
    label: 'Experience Letter',
    description: 'Experience certificate from previous employer',
    icon: FileText,
    color: 'text-purple-600 bg-purple-100'
  }
};

const EmployeeDocuments = () => {
  const { token } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchDocuments = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/employee-profile/documents`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDocuments(response.data.documents || []);
    } catch (error) {
      console.error('Error fetching documents:', error);
      toast.error('Failed to load documents');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const getDocumentConfig = (type) => {
    return DOCUMENT_TYPES[type] || {
      label: type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      description: 'Official document',
      icon: File,
      color: 'text-slate-600 bg-slate-100'
    };
  };

  const offerLetter = documents.find(d => d.document_type === 'offer_letter');

  return (
    <div className="space-y-6 animate-fade-in" data-testid="employee-documents-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[#0b1f3b]" style={{ fontFamily: 'Outfit' }}>
            My Documents
          </h1>
          <p className="text-slate-500 mt-1">View and download your official company documents</p>
        </div>
      </div>

      {/* Main Content */}
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
                  <CardTitle className="text-xl" style={{ fontFamily: 'Outfit' }}>Offer Letter</CardTitle>
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
                            year: 'numeric' 
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
          {documents.filter(d => d.document_type !== 'offer_letter').length > 0 && (
            <Card className="card-premium">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center">
                    <FolderOpen className="w-5 h-5 text-slate-600" />
                  </div>
                  <div>
                    <CardTitle className="text-lg" style={{ fontFamily: 'Outfit' }}>Other Documents</CardTitle>
                    <CardDescription>Additional official documents</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y divide-slate-100">
                  {documents.filter(d => d.document_type !== 'offer_letter').map((doc) => {
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
                <h3 className="text-xl font-semibold text-slate-900 mb-2">No Documents Yet</h3>
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
                    If you need any official documents like experience letters or relieving letters, please raise a support ticket or contact your HR representative.
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
