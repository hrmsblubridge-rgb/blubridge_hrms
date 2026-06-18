import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import EmployeeAvatar from '../components/EmployeeAvatar';
import { Users, Eye, Mail, Briefcase, ChevronRight, Building2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Team = () => {
  const { getAuthHeaders } = useAuth();
  const location = useLocation();
  const [teams, setTeams] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeDept, setActiveDept] = useState('');
  const [selectedTeam, setSelectedTeam] = useState(null);
  const [teamMembers, setTeamMembers] = useState([]);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => { fetchData(); }, []);

  useEffect(() => {
    if (location.state?.department && departments.length > 0) {
      const deptExists = departments.find(d => d.name === location.state.department);
      if (deptExists) setActiveDept(location.state.department);
    }
  }, [location.state, departments]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [teamsRes, deptsRes] = await Promise.all([
        axios.get(`${API}/teams`, { headers: getAuthHeaders() }),
        axios.get(`${API}/departments`, { headers: getAuthHeaders() })
      ]);
      setTeams(teamsRes.data);
      setDepartments(deptsRes.data);
      if (deptsRes.data.length > 0 && !activeDept && !location.state?.department) {
        setActiveDept(deptsRes.data[0].name);
      } else if (location.state?.department) {
        const deptExists = deptsRes.data.find(d => d.name === location.state.department);
        setActiveDept(deptExists ? location.state.department : deptsRes.data[0]?.name || '');
      }
    } catch (error) {
      toast.error('Failed to load team data');
    } finally {
      setLoading(false);
    }
  };

  const handleViewDetails = async (team) => {
    setSelectedTeam(team);
    try {
      const response = await axios.get(`${API}/teams/${team.id}`, { headers: getAuthHeaders() });
      setTeamMembers(response.data.members || []);
      setShowModal(true);
    } catch (error) {
      toast.error('Failed to load team details');
    }
  };

  const filteredTeams = teams.filter(t => t.department === activeDept);
  // UI visibility rule: hide team cards with zero members (records are NOT deleted;
  // this only affects display). Grid reflows automatically; a team reappears as soon
  // as member_count > 0 on the next data load.
  const visibleTeams = filteredTeams.filter(t => (t.member_count || 0) > 0);
  const totalMembers = filteredTeams.reduce((sum, t) => sum + (t.member_count || 0), 0);

  return (
    <div className="space-y-6 animate-fade-in" data-testid="team-page">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
          <Users className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Team Dashboard</h1>
          <p className="text-sm text-slate-500">Manage teams across departments</p>
        </div>
      </div>

      {/* Main Card */}
      <div className="card-premium overflow-hidden">
        {/* Department Tabs */}
        <div className="flex border-b border-slate-100 bg-slate-50/50 overflow-x-auto">
          {departments.map((dept) => {
            const isActive = activeDept === dept.name;
            const deptTeamCount = teams.filter(t => t.department === dept.name && (t.member_count || 0) > 0).length;
            return (
              <button
                key={dept.id}
                onClick={() => setActiveDept(dept.name)}
                className={`
                  relative px-6 py-4 text-sm font-medium transition-all duration-200 whitespace-nowrap
                  ${isActive ? 'bg-[#063c88] text-white' : 'text-slate-600 hover:text-slate-900 hover:bg-white'}
                `}
                data-testid={`tab-${dept.name.replace(/\s+/g, '-').toLowerCase()}`}
              >
                <div className="flex items-center gap-2">
                  <Building2 className="w-4 h-4" />
                  <span>{dept.name}</span>
                  {isActive && <Badge className="ml-2 bg-white/20 text-white text-[10px] px-1.5">{deptTeamCount}</Badge>}
                </div>
              </button>
            );
          })}
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Department Summary */}
          <div className="flex items-center justify-between p-5 rounded-xl bg-gradient-to-r from-slate-50 to-slate-100/50 mb-6">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-[#063c88] flex items-center justify-center shadow-lg shadow-[#063c88]/20">
                <Building2 className="w-7 h-7 text-white" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>{activeDept}</h2>
                <p className="text-sm text-slate-500">Department Overview</p>
              </div>
            </div>
            <div className="text-right">
              <div className="flex items-center gap-8">
                <div>
                  <p className="text-3xl font-bold text-slate-900 number-display">{visibleTeams.length}</p>
                  <p className="text-xs text-slate-500 font-medium">Teams</p>
                </div>
                <div>
                  <p className="text-3xl font-bold text-slate-900 number-display">{totalMembers}</p>
                  <p className="text-xs text-slate-500 font-medium">Members</p>
                </div>
              </div>
            </div>
          </div>

          {/* Teams Grid */}
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <div className="w-10 h-10 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : visibleTeams.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-slate-500">
              <Users className="w-12 h-12 mb-3 text-slate-300" />
              <p>No teams with members in this department</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {visibleTeams.map((team, index) => (
                <div 
                  key={team.id} 
                  className="group p-5 rounded-xl bg-white border border-slate-100 hover:border-[#063c88]/20 hover:shadow-lg transition-all duration-300 animate-slide-up"
                  style={{ animationDelay: `${index * 0.05}s` }}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="font-semibold text-slate-900 text-lg" style={{ fontFamily: 'Outfit' }}>{team.name}</h3>
                      <p className="text-xs text-slate-500 mt-1">{team.department}</p>
                    </div>
                    <div className="w-10 h-10 rounded-xl bg-[#063c88]/5 flex items-center justify-center group-hover:bg-[#063c88]/10 transition-colors">
                      <Users className="w-5 h-5 text-[#063c88]" />
                    </div>
                  </div>
                  
                  <div className="pt-4 border-t border-slate-100 flex items-end justify-between">
                    <div>
                      <p className="text-[10px] text-slate-400 uppercase tracking-wide font-medium">Members</p>
                      <p className="text-2xl font-bold text-slate-900 number-display">{team.member_count}</p>
                    </div>
                    <Button
                      onClick={() => handleViewDetails(team)}
                      size="sm"
                      className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg shadow-lg shadow-[#063c88]/20"
                      data-testid={`view-team-btn-${team.id}`}
                    >
                      <Eye className="w-4 h-4 mr-1" /> View
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Team Details Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="bg-[#fffdf7] max-w-2xl rounded-2xl">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Outfit' }} className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
                <Users className="w-5 h-5 text-white" />
              </div>
              <div>
                <span className="block">{selectedTeam?.name}</span>
                <span className="text-sm font-normal text-slate-500">{selectedTeam?.department}</span>
              </div>
            </DialogTitle>
            <DialogDescription>View team members and details</DialogDescription>
          </DialogHeader>
          
          <div className="py-4">
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="p-4 rounded-xl bg-slate-50">
                <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">Department</p>
                <p className="text-lg font-semibold text-slate-900 mt-1">{selectedTeam?.department}</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-50">
                <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">Total Members</p>
                <p className="text-lg font-semibold text-slate-900 mt-1">{teamMembers.length}</p>
              </div>
            </div>
            
            <div>
              <h4 className="font-semibold text-slate-900 mb-4" style={{ fontFamily: 'Outfit' }}>Team Members</h4>
              {teamMembers.length === 0 ? (
                <div className="text-center py-8 rounded-xl bg-slate-50">
                  <Users className="w-10 h-10 mx-auto mb-2 text-slate-300" />
                  <p className="text-slate-500">No members found</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-64 overflow-y-auto pr-2">
                  {teamMembers.map((member) => (
                    <div key={member.id} className="flex items-center justify-between p-3 rounded-xl bg-white border border-slate-100 hover:border-slate-200 hover:shadow-sm transition-all">
                      <div className="flex items-center gap-3">
                        <EmployeeAvatar employeeId={member.id} name={member.full_name} size="md" shape="circle" className="shadow-md" />
                        <div>
                          <p className="font-medium text-slate-900">{member.full_name}</p>
                          <div className="flex items-center gap-1 text-xs text-slate-500">
                            <Mail className="w-3 h-3" />
                            <span>{member.official_email}</span>
                          </div>
                        </div>
                      </div>
                      <Badge className="bg-[#063c88]/10 text-[#063c88] border-0">
                        <Briefcase className="w-3 h-3 mr-1" />
                        {member.designation || 'Employee'}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowModal(false)} className="rounded-lg">Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Team;
