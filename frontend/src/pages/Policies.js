import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from '../components/ui/accordion';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle
} from '../components/ui/dialog';
import {
  FileText,
  Loader2,
  BookOpen,
  CheckCircle2,
  Calendar,
  Users,
  Building2,
  Laptop,
  FlaskConical,
  ChevronRight,
  X,
  Download,
  Clock
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CATEGORY_CONFIG = {
  HR: { 
    color: 'bg-blue-100 text-blue-700', 
    icon: Users, 
    gradient: 'from-blue-500 to-indigo-500' 
  },
  Department: { 
    color: 'bg-emerald-100 text-emerald-700', 
    icon: Building2, 
    gradient: 'from-emerald-500 to-teal-500' 
  }
};

const POLICY_ICONS = {
  'policy_leave': Calendar,
  'policy_it': Laptop,
  'policy_research': FlaskConical
};

const Policies = () => {
  const { token, user } = useAuth();
  
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedPolicy, setSelectedPolicy] = useState(null);

  const isAdmin = ['hr'].includes(user?.role);

  useEffect(() => {
    fetchPolicies();
  }, []);

  const fetchPolicies = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/policies`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPolicies(response.data || []);
    } catch (error) {
      console.error('Error fetching policies:', error);
      toast.error('Failed to load policies');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="policies-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>
            Company Policies
          </h1>
          <p className="text-slate-500 mt-1">
            Guidelines and standards for all employees
          </p>
        </div>
      </div>

      {/* Policy Cards */}
      <div className="grid gap-6">
        {policies.map((policy) => {
          const categoryConfig = CATEGORY_CONFIG[policy.category] || CATEGORY_CONFIG.HR;
          const PolicyIcon = POLICY_ICONS[policy.id] || FileText;
          const CategoryIcon = categoryConfig.icon;

          return (
            <Card 
              key={policy.id} 
              className="bg-[#fffdf7] border-0 shadow-sm overflow-hidden cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => setSelectedPolicy(policy)}
              data-testid={`policy-${policy.id}`}
            >
              <div className="flex">
                {/* Left Color Bar */}
                <div className={`w-2 bg-gradient-to-b ${categoryConfig.gradient}`} />
                
                <div className="flex-1 p-6">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4">
                      <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${categoryConfig.gradient} flex items-center justify-center shadow-md`}>
                        <PolicyIcon className="w-6 h-6 text-white" />
                      </div>
                      <div>
                        <h3 className="text-lg font-semibold text-slate-900">{policy.name}</h3>
                        <p className="text-sm text-slate-500 mt-1">{policy.content?.overview}</p>
                        
                        <div className="flex items-center gap-3 mt-3">
                          <Badge variant="outline" className={categoryConfig.color}>
                            <CategoryIcon className="w-3 h-3 mr-1" />
                            {policy.category}
                          </Badge>
                          <Badge variant="outline" className="text-slate-600">
                            v{policy.version}
                          </Badge>
                          <span className="text-xs text-slate-500 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            Effective: {new Date(policy.effective_date).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                    </div>
                    
                    <Button variant="ghost" size="sm">
                      View <ChevronRight className="w-4 h-4 ml-1" />
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Policy Detail Modal */}
      <Dialog open={!!selectedPolicy} onOpenChange={() => setSelectedPolicy(null)}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          {selectedPolicy && (
            <>
              <DialogHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {(() => {
                      const PolicyIcon = POLICY_ICONS[selectedPolicy.id] || FileText;
                      const categoryConfig = CATEGORY_CONFIG[selectedPolicy.category] || CATEGORY_CONFIG.HR;
                      return (
                        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${categoryConfig.gradient} flex items-center justify-center`}>
                          <PolicyIcon className="w-5 h-5 text-white" />
                        </div>
                      );
                    })()}
                    <div>
                      <DialogTitle className="text-xl">{selectedPolicy.name}</DialogTitle>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline" className="text-xs">v{selectedPolicy.version}</Badge>
                        <span className="text-xs text-slate-500">
                          Applicable to: {selectedPolicy.applicable_to}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </DialogHeader>

              <div className="mt-4">
                {/* Overview */}
                <div className="bg-slate-50 rounded-lg p-4 mb-6">
                  <p className="text-slate-700">{selectedPolicy.content?.overview}</p>
                </div>

                {/* Sections */}
                <Accordion type="single" collapsible className="space-y-3">
                  {selectedPolicy.content?.sections?.map((section, idx) => (
                    <AccordionItem 
                      key={idx} 
                      value={`section-${idx}`}
                      className="border border-slate-200 rounded-lg overflow-hidden"
                    >
                      <AccordionTrigger className="px-4 py-3 hover:bg-slate-50 hover:no-underline">
                        <div className="flex items-center gap-2">
                          <BookOpen className="w-4 h-4 text-slate-500" />
                          <span className="font-medium text-slate-900">{section.title}</span>
                        </div>
                      </AccordionTrigger>
                      <AccordionContent className="px-4 pb-4">
                        {Array.isArray(section.items) && section.items[0]?.type ? (
                          // Leave type table format
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="border-b border-slate-200">
                                  <th className="text-left py-2 font-medium text-slate-700">Type</th>
                                  <th className="text-center py-2 font-medium text-slate-700">Days</th>
                                  <th className="text-left py-2 font-medium text-slate-700">Description</th>
                                </tr>
                              </thead>
                              <tbody>
                                {section.items.map((item, i) => (
                                  <tr key={i} className="border-b border-slate-100 last:border-0">
                                    <td className="py-2 font-medium text-slate-900">{item.type}</td>
                                    <td className="py-2 text-center">
                                      <Badge className="bg-blue-100 text-blue-700">{item.days}</Badge>
                                    </td>
                                    <td className="py-2 text-slate-600">{item.description}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          // List format
                          <ul className="space-y-2">
                            {section.items.map((item, i) => (
                              <li key={i} className="flex items-start gap-2">
                                <CheckCircle2 className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                                <span className="text-slate-600">{item}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>

                {/* Footer */}
                <div className="mt-6 pt-4 border-t border-slate-200 flex items-center justify-between text-sm text-slate-500">
                  <span>Last updated: {new Date(selectedPolicy.updated_at || selectedPolicy.created_at).toLocaleDateString()}</span>
                  <span>Effective from: {new Date(selectedPolicy.effective_date).toLocaleDateString()}</span>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Policies;
