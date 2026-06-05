import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { User, Mail, Phone, Calendar, Briefcase, MapPin, Building2, Users, Sparkles } from 'lucide-react';
import { formatDate } from '../lib/dateFormat';
import AvatarUploader from '../components/AvatarUploader';
import EmployeeAvatar from '../components/EmployeeAvatar';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EmployeeProfile = () => {
  const { getAuthHeaders, token, updateUser, user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [params] = useSearchParams();
  const showWelcomeBanner = params.get('welcome') === 'upload';

  // Fetch ONLY depends on getAuthHeaders. We deliberately keep updateUser
  // out of the dep array to prevent re-fetch loops (updateUser would change
  // every render if AuthContext re-renders for any reason).
  const fetchProfile = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/employee/profile`, { headers: getAuthHeaders() });
      setProfile(response.data);
    } catch (error) {
      toast.error('Failed to load profile');
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  useEffect(() => { fetchProfile(); }, [fetchProfile]);

  // Sync the loaded avatar into AuthContext ONLY when it actually differs
  // from what the context already has. Runs in a separate effect so it
  // never triggers a re-fetch loop.
  useEffect(() => {
    if (!profile) return;
    const newAvatar = profile.avatar || null;
    if ((user?.avatar || null) !== newAvatar) {
      updateUser?.({ avatar: newAvatar });
    }
    // We only react to profile.avatar changes; user.avatar is read inside
    // the guard above and intentionally NOT a dependency to avoid an
    // update→re-render→update cycle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile?.avatar]);

  const handleAvatarUpdated = (updatedEmployee) => {
    setProfile((prev) => ({ ...(prev || {}), ...(updatedEmployee || {}) }));
    // updateUser will be triggered by the effect above when profile.avatar changes.
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="w-12 h-12 border-3 border-[#063c88] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="employee-profile-page">
      {/* Welcome banner — shown when arriving via the email upload link */}
      {showWelcomeBanner && !profile?.avatar && (
        <div
          className="rounded-2xl border border-[#0a5cba]/20 bg-gradient-to-r from-[#063c88]/5 to-[#0a5cba]/5 p-5 flex items-start gap-4"
          data-testid="profile-upload-welcome-banner"
        >
          <div className="w-10 h-10 rounded-full bg-[#063c88] flex items-center justify-center flex-shrink-0">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900" style={{ fontFamily: 'Outfit' }}>
              Welcome! Let's add your profile picture
            </h3>
            <p className="text-sm text-slate-600 mt-1">
              Tap the camera icon on your avatar below to upload a photo. It will appear instantly across the entire HRMS — attendance, directory, ID card and more.
            </p>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
          <User className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>My Profile</h1>
          <p className="text-sm text-slate-500">View your personal information</p>
        </div>
      </div>

      {/* Profile Card */}
      <div className="card-premium p-8">
        <div className="flex flex-col md:flex-row gap-8 items-start">
          {/* Avatar & Basic Info */}
          <div className="text-center md:text-left">
            <div className="mx-auto md:mx-0 w-fit">
              {/* Employee-side photo upload disabled per HR policy. Admins
                  can still update photos from the Photo Wall. */}
              <EmployeeAvatar
                employee={profile}
                employeeId={profile?.id}
                name={profile?.full_name}
                size="xl"
                shape="square"
                testId="my-profile-avatar"
              />
            </div>
            <div className="mt-4">
              <h2 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>{profile?.full_name}</h2>
              <p className="text-slate-500">{profile?.designation}</p>
              <p className="text-sm text-[#063c88] font-medium mt-1">{profile?.emp_id}</p>
            </div>
          </div>

          {/* Details Grid */}
          <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-6">
            {[
              { icon: Mail, label: 'Email', value: profile?.official_email },
              { icon: Phone, label: 'Phone', value: profile?.phone_number || '-' },
              { icon: Calendar, label: 'Date of Birth', value: formatDate(profile?.date_of_birth) },
              { icon: Calendar, label: 'Date of Joining', value: formatDate(profile?.date_of_joining) },
              { icon: Building2, label: 'Department', value: profile?.department },
              { icon: Users, label: 'Team', value: profile?.team },
              { icon: Briefcase, label: 'Employment Type', value: profile?.employment_type },
              { icon: MapPin, label: 'Work Location', value: profile?.work_location },
            ].map((item, i) => (
              <div key={i} className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center flex-shrink-0">
                  <item.icon className="w-5 h-5 text-slate-500" />
                </div>
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">{item.label}</p>
                  <p className="text-sm font-medium text-slate-900 mt-0.5">{item.value || '-'}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Additional Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: 'Tier Level', value: profile?.tier_level || '-' },
          { label: 'Shift Type', value: profile?.shift_type || 'General' },
          { label: 'Leave Policy', value: profile?.leave_policy || 'Standard' },
        ].map((item, i) => (
          <div key={i} className="card-flat p-5">
            <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">{item.label}</p>
            <p className="text-lg font-semibold text-slate-900 mt-1">{item.value}</p>
          </div>
        ))}
      </div>

      {/* Reporting Manager */}
      {profile?.reporting_manager && (
        <div className="card-flat p-5">
          <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-3">Reporting Manager</p>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#063c88] to-[#0a5cba] flex items-center justify-center">
              <span className="text-white font-medium text-sm">{profile.reporting_manager.name?.charAt(0)}</span>
            </div>
            <div>
              <p className="font-medium text-slate-900">{profile.reporting_manager.name}</p>
              <p className="text-sm text-slate-500">{profile.reporting_manager.email}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EmployeeProfile;
