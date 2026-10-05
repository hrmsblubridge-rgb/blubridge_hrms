import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { User, Mail, Shield, Calendar, Building, Save, Phone } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';

import { formatDate } from '../lib/dateFormat';
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminProfile = () => {
  const { user, getAuthHeaders } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [profile, setProfile] = useState({ name: '', email: '', phone: '', role: '', department: '', joined_date: '' });

  useEffect(() => { fetchProfile(); }, []);

  const fetchProfile = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/auth/me`, { headers: getAuthHeaders() });
      setProfile({
        name: response.data.name || user?.name || '',
        email: response.data.email || '',
        phone: response.data.phone || '',
        role: response.data.role || user?.role || '',
        department: response.data.department || 'Administration',
        joined_date: response.data.created_at || ''
      });
    } catch (error) {
      setProfile({ name: user?.name || 'System Admin', email: user?.email || 'admin@blubridge.ai', phone: '', role: user?.role || 'admin', department: 'Administration', joined_date: '' });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      await axios.put(`${API}/auth/update-profile`, { name: profile.name, email: profile.email, phone: profile.phone }, { headers: getAuthHeaders() });
      toast.success('Profile updated successfully');
    } catch (error) {
      toast.error('Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="w-12 h-12 border-3 border-[#063c88] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="admin-profile-page">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
          <User className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Admin Profile</h1>
          <p className="text-sm text-slate-500">Manage your account settings</p>
        </div>
      </div>

      {/* Profile Card */}
      <div className="card-premium overflow-hidden">
        {/* Header Banner */}
        <div className="bg-gradient-to-r from-[#063c88] to-[#0a5cba] p-8 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2" />
          <div className="relative z-10 flex items-center gap-6">
            <div className="w-24 h-24 rounded-2xl bg-white/10 backdrop-blur-sm flex items-center justify-center border-2 border-white/20 shadow-xl">
              <span className="text-4xl font-bold text-white">{profile.name?.charAt(0)?.toUpperCase()}</span>
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>{profile.name}</h2>
              <p className="text-white/80 flex items-center gap-2 mt-1">
                <Mail className="w-4 h-4" />
                {profile.email || 'admin@blubridge.ai'}
              </p>
              <Badge className="mt-3 bg-white/20 text-white border-0 hover:bg-white/30">
                <Shield className="w-3 h-3 mr-1" />
                {profile.role?.replace('_', ' ').toUpperCase()}
              </Badge>
            </div>
          </div>
        </div>

        {/* Form */}
        <div className="p-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <Label className="text-sm font-medium text-slate-700">Full Name</Label>
              <Input value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })} className="mt-1.5 rounded-lg bg-white" placeholder="Enter full name" />
            </div>
            <div>
              <Label className="text-sm font-medium text-slate-700">Email Address</Label>
              <Input type="email" value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })} className="mt-1.5 rounded-lg bg-white" placeholder="Enter email" />
            </div>
            <div>
              <Label className="text-sm font-medium text-slate-700">Phone Number</Label>
              <Input value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} className="mt-1.5 rounded-lg bg-white" placeholder="Enter phone number" />
            </div>
            <div>
              <Label className="text-sm font-medium text-slate-700">Role</Label>
              <Input value={profile.role?.replace('_', ' ').toUpperCase()} className="mt-1.5 rounded-lg bg-slate-50" disabled />
            </div>
            <div>
              <Label className="text-sm font-medium text-slate-700">Department</Label>
              <Input value={profile.department} className="mt-1.5 rounded-lg bg-slate-50" disabled />
            </div>
            <div>
              <Label className="text-sm font-medium text-slate-700">Account Created</Label>
              <div className="mt-1.5 flex items-center gap-2 p-3 bg-slate-50 rounded-lg text-slate-600 text-sm">
                <Calendar className="w-4 h-4" />
                {profile.joined_date ? formatDate(profile.joined_date) : 'N/A'}
              </div>
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-slate-100 flex justify-end">
            <Button onClick={handleSave} disabled={saving} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg px-8 shadow-lg shadow-[#063c88]/20" data-testid="save-profile-btn">
              {saving ? <div className="w-4 h-4 mr-2 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminProfile;
