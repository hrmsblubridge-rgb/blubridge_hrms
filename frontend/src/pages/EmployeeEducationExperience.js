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
  GraduationCap,
  Briefcase,
  Plus,
  Edit2,
  Trash2,
  CheckCircle2,
  Loader2,
  Building2,
  Calendar,
  Award,
  Lock,
  Shield
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EDUCATION_LEVELS = [
  'Class X',
  'Class XII',
  'Diploma',
  'Graduation',
  'Post Graduation',
  'Doctorate'
];

const EmployeeEducationExperience = () => {
  const { token } = useAuth();
  
  const [data, setData] = useState({ education: [], experience: [] });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
  // Education modal
  const [eduModal, setEduModal] = useState(null); // null, 'add', or index for edit
  const [eduForm, setEduForm] = useState({
    level: '',
    institution: '',
    board_university: '',
    year_of_passing: '',
    percentage_cgpa: ''
  });
  
  // Experience modal
  const [expModal, setExpModal] = useState(null);
  const [expForm, setExpForm] = useState({
    company_name: '',
    designation: '',
    start_date: '',
    end_date: '',
    is_current: false,
    responsibilities: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/employee-profile/education-experience`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setData(response.data);
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Failed to load education and experience details');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveEducation = async () => {
    if (!eduForm.level || !eduForm.institution || !eduForm.year_of_passing) {
      toast.error('Please fill in all required fields');
      return;
    }
    
    setSaving(true);
    try {
      const newEducation = [...data.education];
      if (eduModal === 'add') {
        newEducation.push(eduForm);
      } else {
        newEducation[eduModal] = eduForm;
      }
      
      await axios.put(`${API}/employee-profile/education-experience`, {
        education: newEducation
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success('Education details saved');
      setEduModal(null);
      setEduForm({ level: '', institution: '', board_university: '', year_of_passing: '', percentage_cgpa: '' });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteEducation = async (index) => {
    setSaving(true);
    try {
      const newEducation = data.education.filter((_, i) => i !== index);
      await axios.put(`${API}/employee-profile/education-experience`, {
        education: newEducation
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Education entry deleted');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveExperience = async () => {
    if (!expForm.company_name || !expForm.designation || !expForm.start_date) {
      toast.error('Please fill in all required fields');
      return;
    }
    
    setSaving(true);
    try {
      const newExperience = [...data.experience];
      if (expModal === 'add') {
        newExperience.push(expForm);
      } else {
        newExperience[expModal] = expForm;
      }
      
      await axios.put(`${API}/employee-profile/education-experience`, {
        experience: newExperience
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success('Experience details saved');
      setExpModal(null);
      setExpForm({ company_name: '', designation: '', start_date: '', end_date: '', is_current: false, responsibilities: '' });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteExperience = async (index) => {
    setSaving(true);
    try {
      const newExperience = data.experience.filter((_, i) => i !== index);
      await axios.put(`${API}/employee-profile/education-experience`, {
        experience: newExperience
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Experience entry deleted');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete');
    } finally {
      setSaving(false);
    }
  };

  const openEditEducation = (index) => {
    setEduForm(data.education[index]);
    setEduModal(index);
  };

  const openEditExperience = (index) => {
    setExpForm(data.experience[index]);
    setExpModal(index);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="education-experience-page">
      {/* Education Section */}
      <Card className="bg-[#fffdf7] border-0 shadow-sm">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center">
                <GraduationCap className="w-5 h-5 text-white" />
              </div>
              <div>
                <CardTitle className="text-lg">Education</CardTitle>
                <CardDescription>Your academic qualifications</CardDescription>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {data.education_verified ? (
                <Badge className="bg-emerald-100 text-emerald-700">
                  <Shield className="w-3 h-3 mr-1" />
                  APPROVED
                </Badge>
              ) : (
                <Button 
                  size="sm" 
                  onClick={() => { setEduForm({ level: '', institution: '', board_university: '', year_of_passing: '', percentage_cgpa: '' }); setEduModal('add'); }}
                  data-testid="add-education-btn"
                >
                  <Plus className="w-4 h-4 mr-1" />
                  Add
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {data.education.length === 0 ? (
            <div className="text-center py-8 text-slate-500">
              <GraduationCap className="w-12 h-12 mx-auto mb-3 text-slate-300" />
              <p>No education details added yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {data.education.map((edu, index) => (
                <div 
                  key={index}
                  className="p-4 bg-white rounded-lg border border-slate-200 flex items-start justify-between"
                  data-testid={`education-${index}`}
                >
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center mt-1">
                      <Award className="w-5 h-5 text-blue-600" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-semibold text-slate-900">{edu.level}</h4>
                        <Badge variant="outline" className="text-xs">{edu.year_of_passing}</Badge>
                      </div>
                      <p className="text-sm text-slate-700 mt-0.5">{edu.institution}</p>
                      <p className="text-xs text-slate-500 mt-1">
                        {edu.board_university} • {edu.percentage_cgpa}
                      </p>
                    </div>
                  </div>
                  {!data.education_verified && (
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="sm" onClick={() => openEditEducation(index)}>
                        <Edit2 className="w-4 h-4 text-slate-500" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDeleteEducation(index)}>
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </Button>
                    </div>
                  )}
                  {data.education_verified && (
                    <Lock className="w-4 h-4 text-slate-400" />
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Experience Section */}
      <Card className="bg-[#fffdf7] border-0 shadow-sm">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
                <Briefcase className="w-5 h-5 text-white" />
              </div>
              <div>
                <CardTitle className="text-lg">Work Experience</CardTitle>
                <CardDescription>Your professional background</CardDescription>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {data.experience_verified ? (
                <Badge className="bg-emerald-100 text-emerald-700">
                  <Shield className="w-3 h-3 mr-1" />
                  APPROVED
                </Badge>
              ) : (
                <Button 
                  size="sm" 
                  onClick={() => { setExpForm({ company_name: '', designation: '', start_date: '', end_date: '', is_current: false, responsibilities: '' }); setExpModal('add'); }}
                  data-testid="add-experience-btn"
                >
                  <Plus className="w-4 h-4 mr-1" />
                  Add
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {data.experience.length === 0 ? (
            <div className="text-center py-8 text-slate-500">
              <Briefcase className="w-12 h-12 mx-auto mb-3 text-slate-300" />
              <p>No work experience added yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {data.experience.map((exp, index) => (
                <div 
                  key={index}
                  className="p-4 bg-white rounded-lg border border-slate-200 flex items-start justify-between"
                  data-testid={`experience-${index}`}
                >
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center mt-1">
                      <Building2 className="w-5 h-5 text-emerald-600" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-semibold text-slate-900">{exp.designation}</h4>
                        {exp.is_current && (
                          <Badge className="bg-emerald-100 text-emerald-700 text-xs">Current</Badge>
                        )}
                      </div>
                      <p className="text-sm text-slate-700 mt-0.5">{exp.company_name}</p>
                      <p className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {exp.start_date} - {exp.is_current ? 'Present' : exp.end_date}
                      </p>
                      {exp.responsibilities && (
                        <p className="text-xs text-slate-600 mt-2">{exp.responsibilities}</p>
                      )}
                    </div>
                  </div>
                  {!data.experience_verified && (
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="sm" onClick={() => openEditExperience(index)}>
                        <Edit2 className="w-4 h-4 text-slate-500" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDeleteExperience(index)}>
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </Button>
                    </div>
                  )}
                  {data.experience_verified && (
                    <Lock className="w-4 h-4 text-slate-400" />
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Education Modal */}
      <Dialog open={eduModal !== null} onOpenChange={() => setEduModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{eduModal === 'add' ? 'Add Education' : 'Edit Education'}</DialogTitle>
            <DialogDescription>Enter your academic qualification details</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-slate-700">Level *</label>
              <Select value={eduForm.level} onValueChange={(v) => setEduForm({ ...eduForm, level: v })}>
                <SelectTrigger data-testid="edu-level-select">
                  <SelectValue placeholder="Select level" />
                </SelectTrigger>
                <SelectContent>
                  {EDUCATION_LEVELS.map(level => (
                    <SelectItem key={level} value={level}>{level}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">Institution *</label>
              <Input
                placeholder="e.g., ABC University"
                value={eduForm.institution}
                onChange={(e) => setEduForm({ ...eduForm, institution: e.target.value })}
                data-testid="edu-institution-input"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">Board / University</label>
              <Input
                placeholder="e.g., CBSE, Anna University"
                value={eduForm.board_university}
                onChange={(e) => setEduForm({ ...eduForm, board_university: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-slate-700">Year of Passing *</label>
                <Input
                  placeholder="e.g., 2020"
                  value={eduForm.year_of_passing}
                  onChange={(e) => setEduForm({ ...eduForm, year_of_passing: e.target.value })}
                  data-testid="edu-year-input"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">Percentage / CGPA</label>
                <Input
                  placeholder="e.g., 85% or 8.5 CGPA"
                  value={eduForm.percentage_cgpa}
                  onChange={(e) => setEduForm({ ...eduForm, percentage_cgpa: e.target.value })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEduModal(null)}>Cancel</Button>
            <Button onClick={handleSaveEducation} disabled={saving}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Experience Modal */}
      <Dialog open={expModal !== null} onOpenChange={() => setExpModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{expModal === 'add' ? 'Add Experience' : 'Edit Experience'}</DialogTitle>
            <DialogDescription>Enter your work experience details</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-slate-700">Company Name *</label>
              <Input
                placeholder="e.g., ABC Technologies"
                value={expForm.company_name}
                onChange={(e) => setExpForm({ ...expForm, company_name: e.target.value })}
                data-testid="exp-company-input"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">Designation *</label>
              <Input
                placeholder="e.g., Software Engineer"
                value={expForm.designation}
                onChange={(e) => setExpForm({ ...expForm, designation: e.target.value })}
                data-testid="exp-designation-input"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-slate-700">Start Date *</label>
                <Input
                  type="date"
                  value={expForm.start_date}
                  onChange={(e) => setExpForm({ ...expForm, start_date: e.target.value })}
                  data-testid="exp-start-input"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">End Date</label>
                <Input
                  type="date"
                  value={expForm.end_date}
                  onChange={(e) => setExpForm({ ...expForm, end_date: e.target.value })}
                  disabled={expForm.is_current}
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_current"
                checked={expForm.is_current}
                onChange={(e) => setExpForm({ ...expForm, is_current: e.target.checked, end_date: '' })}
                className="rounded border-slate-300"
              />
              <label htmlFor="is_current" className="text-sm text-slate-700">I currently work here</label>
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">Key Responsibilities</label>
              <Textarea
                placeholder="Brief description of your role..."
                value={expForm.responsibilities}
                onChange={(e) => setExpForm({ ...expForm, responsibilities: e.target.value })}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setExpModal(null)}>Cancel</Button>
            <Button onClick={handleSaveExperience} disabled={saving}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EmployeeEducationExperience;
