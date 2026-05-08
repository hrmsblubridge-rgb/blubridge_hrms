import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Checkbox } from '../components/ui/checkbox';
import {
  FileText, Loader2, BookOpen, Calendar, Users, Building2,
  Laptop, FlaskConical, ShieldCheck, Sparkles, Check, CheckCircle2, Clock,
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// ---- Visual config: per-policy theming for the full-page view ----
const POLICY_THEME = {
  policy_leave:           { icon: Calendar,    accent: '#0ea5e9', tint: 'sky',     label: 'HR' },
  policy_it:              { icon: Laptop,      accent: '#6366f1', tint: 'indigo',  label: 'Company-wide' },
  policy_research:        { icon: FlaskConical, accent: '#10b981', tint: 'emerald', label: 'Research' },
  policy_research_hr:     { icon: FlaskConical, accent: '#0d9488', tint: 'teal',    label: 'Research' },
  policy_support_hr:      { icon: Users,       accent: '#f59e0b', tint: 'amber',   label: 'Support' },
  policy_admin_induction: { icon: Building2,   accent: '#ec4899', tint: 'pink',    label: 'Admin' },
};

const FALLBACK_THEME = { icon: FileText, accent: '#475569', tint: 'slate', label: 'Policy' };

// Render a single section as a fully-expanded panel — NO accordion / toggle.
const SectionBlock = ({ section, accent }) => {
  const hasItems = Array.isArray(section.items) && section.items.length > 0;
  const isLeaveTable = hasItems && section.items[0]?.type;
  const tableData = section.table;

  return (
    <div className="rounded-xl bg-white border border-slate-200 overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]" data-testid="policy-section">
      <div
        className="px-5 py-4 border-b border-slate-100 flex items-center gap-3"
        style={{ background: `linear-gradient(90deg, ${accent}10, transparent)` }}
      >
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: `${accent}15`, color: accent }}
        >
          <BookOpen className="w-4 h-4" />
        </div>
        <h3 className="text-[15px] font-semibold text-slate-900 leading-snug">
          {section.title}
        </h3>
      </div>

      <div className="px-5 py-4 space-y-3">
        {section.text && (
          <p className="text-[14px] text-slate-700 whitespace-pre-line leading-relaxed">
            {section.text}
          </p>
        )}

        {tableData && Array.isArray(tableData.headers) && Array.isArray(tableData.rows) && (
          <div className="overflow-x-auto rounded-lg border border-slate-200 mt-1">
            <table className="w-full text-[13px]">
              <thead style={{ background: `${accent}0a` }}>
                <tr>
                  {tableData.headers.map((h, hi) => (
                    <th key={hi} className="text-left px-3 py-2 font-semibold text-slate-700 border-b border-slate-200 align-top whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableData.rows.map((row, ri) => (
                  <tr key={ri} className="border-b border-slate-100 last:border-0 align-top hover:bg-slate-50">
                    {row.map((cell, ci) => (
                      <td key={ci} className="px-3 py-2 text-slate-700 whitespace-pre-line align-top">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {hasItems && isLeaveTable && (
          <div className="overflow-x-auto rounded-lg border border-slate-200 mt-1">
            <table className="w-full text-[13px]">
              <thead style={{ background: `${accent}0a` }}>
                <tr>
                  <th className="text-left py-2 px-3 font-semibold text-slate-700">Type</th>
                  <th className="text-center py-2 px-3 font-semibold text-slate-700">Days</th>
                  <th className="text-left py-2 px-3 font-semibold text-slate-700">Description</th>
                </tr>
              </thead>
              <tbody>
                {section.items.map((item, i) => (
                  <tr key={i} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 px-3 font-medium text-slate-900">{item.type}</td>
                    <td className="py-2 px-3 text-center">
                      <Badge style={{ background: `${accent}1a`, color: accent }} className="border-0 font-semibold">
                        {item.days}
                      </Badge>
                    </td>
                    <td className="py-2 px-3 text-slate-600">{item.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {hasItems && !isLeaveTable && (
          <ul className="space-y-2.5">
            {section.items.map((item, i) => (
              <li key={i} className="flex items-start gap-3 text-[14px] leading-relaxed">
                <span
                  className="mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ background: accent }}
                />
                <span className="text-slate-700">{item}</span>
              </li>
            ))}
          </ul>
        )}

        {section.footer && (
          <p className="text-[12px] italic text-slate-500 pt-2 border-t border-slate-100 mt-3">
            {section.footer}
          </p>
        )}
      </div>
    </div>
  );
};

// Per-policy "page card" — the full document, top-to-bottom, no toggles.
const PolicyDocument = ({ policy, onAcknowledge, isEmployee }) => {
  const theme = POLICY_THEME[policy.id] || FALLBACK_THEME;
  const PolicyIcon = theme.icon;
  const sections = policy.content?.sections || [];
  const [agreed, setAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const acknowledged = !!policy.is_acknowledged;
  const ackTime = policy.acknowledged_at ? new Date(policy.acknowledged_at) : null;

  const handleAgree = async () => {
    if (!agreed || submitting || acknowledged) return;
    setSubmitting(true);
    try {
      await onAcknowledge(policy.id);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <article
      className="bg-white rounded-2xl shadow-[0_2px_18px_rgba(15,23,42,0.06)] border border-slate-100 overflow-hidden"
      data-testid={`policy-${policy.id}`}
      id={`policy-${policy.id}`}
    >
      {/* Hero band */}
      <header
        className="px-7 py-7"
        style={{
          background: `linear-gradient(135deg, ${theme.accent}, ${theme.accent}cc)`,
        }}
      >
        <div className="flex items-start gap-4">
          <div className="w-14 h-14 rounded-2xl bg-white/15 backdrop-blur-sm flex items-center justify-center flex-shrink-0 ring-1 ring-white/20">
            <PolicyIcon className="w-7 h-7 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5">
              <Badge className="bg-white/20 text-white border-0 font-medium uppercase tracking-wide text-[10px] backdrop-blur-sm">
                {theme.label}
              </Badge>
              <Badge className="bg-white/15 text-white border-0 text-[10px] backdrop-blur-sm">
                v{policy.version || '1.0'}
              </Badge>
            </div>
            <h2 className="text-[22px] sm:text-[24px] font-bold text-white leading-tight" style={{ fontFamily: 'Outfit' }}>
              {policy.name}
            </h2>
            <div className="flex flex-wrap gap-x-5 gap-y-1 mt-2.5 text-[12px] text-white/85">
              <span className="flex items-center gap-1.5"><Users className="w-3.5 h-3.5" /> {policy.applicable_to}</span>
              {policy.effective_date && (
                <span className="flex items-center gap-1.5"><Calendar className="w-3.5 h-3.5" /> Effective: {new Date(policy.effective_date).toLocaleDateString()}</span>
              )}
              {isEmployee && (
                acknowledged ? (
                  <span
                    className="flex items-center gap-1.5 bg-emerald-500/30 text-white border border-emerald-200/40 px-2 py-0.5 rounded-full font-medium backdrop-blur-sm"
                    data-testid={`ack-status-${policy.id}`}
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" /> Acknowledged
                  </span>
                ) : (
                  <span
                    className="flex items-center gap-1.5 bg-amber-400/30 text-white border border-amber-200/40 px-2 py-0.5 rounded-full font-medium backdrop-blur-sm"
                    data-testid={`ack-status-${policy.id}`}
                  >
                    <Clock className="w-3.5 h-3.5" /> Pending Acknowledgement
                  </span>
                )
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Body */}
      <div className="px-5 sm:px-7 py-6 space-y-4">
        {policy.content?.overview && (
          <div
            className="rounded-xl px-5 py-4 border-l-4"
            style={{ borderColor: theme.accent, background: `${theme.accent}08` }}
          >
            <div className="flex items-start gap-2.5">
              <Sparkles className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: theme.accent }} />
              <p className="text-[14px] text-slate-700 leading-relaxed">{policy.content.overview}</p>
            </div>
          </div>
        )}

        {sections.length === 0 ? (
          <p className="text-sm text-slate-500 italic px-1 py-4">No sections published yet.</p>
        ) : (
          <div className="grid gap-4">
            {sections.map((section, idx) => (
              <SectionBlock key={idx} section={section} accent={theme.accent} />
            ))}
          </div>
        )}
      </div>

      {/* Acknowledgement section (employees only) */}
      {isEmployee && (
        <section className="mx-5 sm:mx-7 mb-5 mt-1" data-testid={`ack-section-${policy.id}`}>
          {acknowledged ? (
            <div
              className="rounded-xl border-2 border-emerald-200 bg-gradient-to-br from-emerald-50 to-white px-5 py-4 flex items-center gap-3"
            >
              <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[14px] font-semibold text-emerald-900">You have acknowledged this policy</div>
                <div className="text-[12px] text-emerald-700/80 mt-0.5">
                  Acknowledged on {ackTime ? ackTime.toLocaleString() : '—'}
                </div>
              </div>
              <Button disabled className="rounded-full bg-emerald-100 text-emerald-700 hover:bg-emerald-100" data-testid={`ack-done-btn-${policy.id}`}>
                <CheckCircle2 className="w-4 h-4 mr-1.5" /> Acknowledged
              </Button>
            </div>
          ) : (
            <div
              className="rounded-xl border-2 border-dashed px-5 py-4"
              style={{ borderColor: `${theme.accent}55`, background: `${theme.accent}06` }}
            >
              <div className="flex items-start gap-3 mb-3">
                <ShieldCheck className="w-5 h-5 mt-0.5 flex-shrink-0" style={{ color: theme.accent }} />
                <div className="flex-1">
                  <div className="text-[14px] font-semibold text-slate-900">Acknowledgement required</div>
                  <p className="text-[12.5px] text-slate-600 mt-0.5">
                    Please confirm that you have read and understood the policy above. Your acknowledgement will be timestamped and recorded.
                  </p>
                </div>
              </div>
              <label
                className="flex items-center gap-2.5 cursor-pointer select-none px-3 py-2.5 rounded-lg bg-white border border-slate-200 hover:border-slate-300 transition-colors"
                data-testid={`ack-checkbox-label-${policy.id}`}
              >
                <Checkbox
                  checked={agreed}
                  onCheckedChange={(v) => setAgreed(v === true)}
                  data-testid={`ack-checkbox-${policy.id}`}
                />
                <span className="text-[13.5px] text-slate-800">
                  I have read and agree to this policy
                </span>
              </label>
              <div className="flex justify-end mt-3">
                <Button
                  disabled={!agreed || submitting}
                  onClick={handleAgree}
                  className="rounded-full text-white font-semibold disabled:opacity-50"
                  style={{ background: theme.accent }}
                  data-testid={`ack-agree-btn-${policy.id}`}
                >
                  {submitting ? <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> Saving…</> : <>Agree</>}
                </Button>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Footer */}
      <footer className="px-7 py-3 border-t border-slate-100 bg-slate-50/60 flex flex-wrap items-center justify-between gap-2 text-[12px] text-slate-500">
        <span className="flex items-center gap-1.5"><ShieldCheck className="w-3.5 h-3.5" /> Internal — login required</span>
        <span>Last updated: {new Date(policy.updated_at || policy.created_at || Date.now()).toLocaleDateString()}</span>
      </footer>
    </article>
  );
};

const Policies = () => {
  const { token, user } = useAuth();
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState(null);

  const isEmployee = !!user?.employee_id;

  const fetchPolicies = async () => {
    try {
      const { data } = await axios.get(`${API}/policies`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const list = data || [];
      setPolicies(list);
      if (list.length && !activeId) setActiveId(list[0].id);
    } catch (err) {
      console.error('Error fetching policies:', err);
      toast.error('Failed to load policies');
    }
  };

  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoading(true);
      await fetchPolicies();
      if (mounted) setLoading(false);
    })();
    return () => { mounted = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const handleAcknowledge = async (policyId) => {
    try {
      const { data } = await axios.post(
        `${API}/policies/${policyId}/acknowledge`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      // Optimistic local update so the UI flips immediately
      setPolicies((prev) => prev.map((p) =>
        p.id === policyId
          ? { ...p, is_acknowledged: true, acknowledged_at: data.acknowledged_at }
          : p
      ));
      if (data.already_acknowledged) {
        toast.message('Already acknowledged earlier');
      } else {
        toast.success('Policy acknowledged. Thank you!');
      }
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Could not record acknowledgement';
      toast.error(typeof msg === 'string' ? msg : 'Could not record acknowledgement');
    }
  };

  const tocItems = useMemo(() => policies.map((p) => ({
    id: p.id,
    name: p.name,
    theme: POLICY_THEME[p.id] || FALLBACK_THEME,
    acknowledged: !!p.is_acknowledged,
  })), [policies]);

  const ackedCount = useMemo(
    () => policies.filter((p) => p.is_acknowledged).length,
    [policies],
  );

  const scrollTo = (id) => {
    setActiveId(id);
    const el = document.getElementById(`policy-${id}`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12" data-testid="policies-page">
      {/* Header */}
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl sm:text-[28px] font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>
            Company Policies
          </h1>
          <p className="text-slate-500 mt-1 text-[14px]">
            All policies applicable to you — open, end-to-end, no accordions.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {isEmployee && policies.length > 0 && (
            <div
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12px] font-medium border ${
                ackedCount === policies.length
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-amber-50 text-amber-700 border-amber-200'
              }`}
              data-testid="policies-ack-progress"
            >
              {ackedCount === policies.length
                ? <CheckCircle2 className="w-3.5 h-3.5" />
                : <Clock className="w-3.5 h-3.5" />}
              {ackedCount} of {policies.length} acknowledged
            </div>
          )}
          <div className="flex items-center gap-2 text-[12px] text-slate-500">
            <Check className="w-4 h-4 text-emerald-500" />
            <span>{policies.length} policies available</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-6">
        {/* Sticky TOC sidebar */}
        <aside className="lg:sticky lg:top-4 lg:self-start" data-testid="policies-toc">
          <div className="bg-white rounded-2xl border border-slate-100 shadow-[0_1px_4px_rgba(15,23,42,0.04)] p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 px-3 py-2">On this page</p>
            <nav className="flex flex-col">
              {tocItems.map((it) => {
                const Icon = it.theme.icon;
                const active = activeId === it.id;
                return (
                  <button
                    key={it.id}
                    onClick={() => scrollTo(it.id)}
                    className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-left transition-all ${
                      active
                        ? 'bg-slate-50 text-slate-900 font-medium ring-1 ring-slate-200'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`}
                    data-testid={`policy-toc-${it.id}`}
                  >
                    <span
                      className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0"
                      style={{ background: `${it.theme.accent}15`, color: it.theme.accent }}
                    >
                      <Icon className="w-3.5 h-3.5" />
                    </span>
                    <span className="text-[13px] truncate flex-1">{it.name}</span>
                    {isEmployee && (
                      it.acknowledged
                        ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" />
                        : <Clock className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                    )}
                  </button>
                );
              })}
            </nav>
          </div>
        </aside>

        {/* Stacked, fully-expanded policy documents */}
        <main className="space-y-7 min-w-0">
          {policies.length === 0 ? (
            <div className="bg-white rounded-2xl border border-slate-100 p-12 text-center text-slate-500">
              <FileText className="w-10 h-10 mx-auto mb-3 text-slate-300" />
              <p>No policies are published or visible to your account.</p>
            </div>
          ) : (
            policies.map((p) => (
              <PolicyDocument
                key={p.id}
                policy={p}
                onAcknowledge={handleAcknowledge}
                isEmployee={isEmployee}
              />
            ))
          )}
        </main>
      </div>
    </div>
  );
};

export default Policies;
