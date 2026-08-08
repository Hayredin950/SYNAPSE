'use client';

/**
 * TASK-006-F4: Organization Settings Page
 * Route: /organizations/[id]/settings
 *
 * Tabs: General | Members | Invites | Audit Log | Danger Zone
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Settings, Users, Mail, Shield, Trash2, ArrowLeft, Plus, Loader2,
  Crown, Eye, User, AlertCircle, Check, X, Send, Clock, ChevronDown,
} from 'lucide-react';
import { api } from '@/utils/api';
import { useOrganization, OrgMember } from '@/contexts/OrganizationContext';
import { useAuthStore } from '@/store/authStore';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Invite {
  id: string;
  email: string;
  role: string;
  is_accepted: boolean;
  expires_at: string | null;
  created_at: string;
  invited_by_email: string;
}

interface AuditEntry {
  id: string;
  action: string;
  actor_email: string | null;
  resource: string;
  metadata: Record<string, any>;
  timestamp: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const ROLE_STYLES: Record<string, string> = {
  owner:  'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  admin:  'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300',
  member: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  viewer: 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
};

const ACTION_LABELS: Record<string, string> = {
  org_created:      '🏢 Org created',
  org_deleted:      '🗑 Org deleted',
  settings_changed: '⚙️ Settings changed',
  member_added:     '➕ Member added',
  member_removed:   '➖ Member removed',
  role_changed:     '🔄 Role changed',
  invite_sent:      '📨 Invite sent',
  invite_cancelled: '❌ Invite cancelled',
  invite_accepted:  '✅ Invite accepted',
};

function timeAgo(iso: string): string {
  const secs = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return 'just now';
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

// ── Tab: General ──────────────────────────────────────────────────────────────

function GeneralTab({ orgId, isAdmin }: { orgId: string; isAdmin: boolean }) {
  const { refetchOrgs } = useOrganization();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get(`/organizations/${orgId}/`).then(r => {
      const d = r.data?.data;
      setName(d?.name || '');
      setDescription(d?.description || '');
      setLoading(false);
    });
  }, [orgId]);

  const save = async () => {
    setSaving(true); setError(''); setSuccess(false);
    try {
      await api.patch(`/organizations/${orgId}/`, { name, description });
      await refetchOrgs();
      setSuccess(true);
      setTimeout(() => setSuccess(false), 2000);
    } catch (e: any) {
      setError(e?.response?.data?.error || 'Failed to save.');
    } finally { setSaving(false); }
  };

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-indigo-500" /></div>;

  return (
    <div className="max-w-lg space-y-4">
      <div>
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Organization name</label>
        <input
          type="text" value={name} onChange={e => setName(e.target.value)} disabled={!isAdmin}
          className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Description</label>
        <textarea
          value={description} onChange={e => setDescription(e.target.value)} disabled={!isAdmin} rows={3}
          className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none disabled:opacity-60"
        />
      </div>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      {isAdmin && (
        <button
          onClick={save} disabled={saving}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors disabled:opacity-60"
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : success ? <Check size={14} /> : null}
          {success ? 'Saved!' : 'Save changes'}
        </button>
      )}
    </div>
  );
}

// ── Tab: Members ──────────────────────────────────────────────────────────────

function MembersTab({ orgId, isAdmin, currentUserId }: { orgId: string; isAdmin: boolean; currentUserId: string }) {
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [removing, setRemoving] = useState<string | null>(null);
  const [changingRole, setChangingRole] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get(`/organizations/${orgId}/members/`);
      setMembers(r.data?.data || []);
    } finally { setLoading(false); }
  }, [orgId]);

  useEffect(() => { fetch(); }, [fetch]);

  const removeUser = async (userId: string) => {
    setRemoving(userId);
    try { await api.delete(`/organizations/${orgId}/members/${userId}/`); await fetch(); }
    catch (e: any) { alert(e?.response?.data?.error || 'Failed to remove member.'); }
    finally { setRemoving(null); }
  };

  const changeRole = async (userId: string, role: string) => {
    setChangingRole(userId);
    try { await api.patch(`/organizations/${orgId}/members/${userId}/`, { role }); await fetch(); }
    catch (e: any) { alert(e?.response?.data?.error || 'Failed to change role.'); }
    finally { setChangingRole(null); }
  };

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-indigo-500" /></div>;

  return (
    <div className="space-y-2">
      {members.map(m => (
        <div key={m.id} className="flex items-center gap-3 p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 flex items-center justify-center flex-shrink-0">
            <span className="text-white text-sm font-bold">{(m.user_name || m.user_email)[0].toUpperCase()}</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-slate-900 dark:text-white truncate">{m.user_name || m.user_email}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{m.user_email}</p>
          </div>
          {/* Role selector (admin only, not for owners) */}
          {isAdmin && m.role !== 'owner' ? (
            <select
              value={m.role}
              onChange={e => changeRole(m.user, e.target.value)}
              disabled={changingRole === m.user}
              className="text-xs px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {['admin', 'member', 'viewer'].map(r => (
                <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
              ))}
            </select>
          ) : (
            <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${ROLE_STYLES[m.role] || ROLE_STYLES.member}`}>
              {m.role.charAt(0).toUpperCase() + m.role.slice(1)}
            </span>
          )}
          {/* Remove button */}
          {(isAdmin && m.role !== 'owner') || m.user === currentUserId ? (
            <button
              onClick={() => removeUser(m.user)}
              disabled={removing === m.user}
              className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-40"
              title={m.user === currentUserId ? 'Leave org' : 'Remove member'}
            >
              {removing === m.user ? <Loader2 size={14} className="animate-spin" /> : <X size={14} />}
            </button>
          ) : null}
        </div>
      ))}
    </div>
  );
}

// ── Tab: Invites ──────────────────────────────────────────────────────────────

function InvitesTab({ orgId, isAdmin }: { orgId: string; isAdmin: boolean }) {
  const [invites, setInvites] = useState<Invite[]>([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('member');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  const fetch = useCallback(async () => {
    setLoading(true);
    try { const r = await api.get(`/organizations/${orgId}/invites/`); setInvites(r.data?.data || []); }
    finally { setLoading(false); }
  }, [orgId]);

  useEffect(() => { fetch(); }, [fetch]);

  const sendInvite = async () => {
    if (!email.trim()) return;
    setSending(true); setError('');
    try { await api.post(`/organizations/${orgId}/invites/`, { email: email.trim(), role }); setEmail(''); await fetch(); }
    catch (e: any) { setError(e?.response?.data?.error || 'Failed to send invite.'); }
    finally { setSending(false); }
  };

  const cancelInvite = async (inviteId: string) => {
    try { await api.delete(`/organizations/${orgId}/invites/${inviteId}/`); await fetch(); }
    catch (e: any) { alert(e?.response?.data?.error || 'Failed to cancel invite.'); }
  };

  return (
    <div className="space-y-4">
      {/* Send invite form */}
      {isAdmin && (
        <div className="flex items-end gap-2 p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Email address</label>
            <input
              type="email" value={email} onChange={e => setEmail(e.target.value)}
              placeholder="colleague@company.com"
              className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              onKeyDown={e => e.key === 'Enter' && sendInvite()}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Role</label>
            <select
              value={role} onChange={e => setRole(e.target.value)}
              className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {['admin', 'member', 'viewer'].map(r => (
                <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
              ))}
            </select>
          </div>
          <button
            onClick={sendInvite} disabled={sending || !email.trim()}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors disabled:opacity-60"
          >
            {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            Invite
          </button>
        </div>
      )}
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      {/* Pending invites list */}
      {loading ? (
        <div className="flex justify-center py-8"><Loader2 className="animate-spin text-indigo-500" /></div>
      ) : invites.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400 text-center py-8">No pending invites.</p>
      ) : (
        <div className="space-y-2">
          {invites.map(inv => (
            <div key={inv.id} className="flex items-center gap-3 p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <div className="w-9 h-9 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center flex-shrink-0">
                <Mail size={16} className="text-slate-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900 dark:text-white truncate">{inv.email}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Invited by {inv.invited_by_email} · {timeAgo(inv.created_at)}
                  {inv.expires_at && ` · expires ${timeAgo(inv.expires_at)}`}
                </p>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${ROLE_STYLES[inv.role] || ROLE_STYLES.member}`}>
                {inv.role}
              </span>
              {isAdmin && (
                <button
                  onClick={() => cancelInvite(inv.id)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                  title="Cancel invite"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Tab: Audit Log ────────────────────────────────────────────────────────────

function AuditLogTab({ orgId }: { orgId: string }) {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/organizations/${orgId}/audit-logs/`).then(r => {
      setEntries(r.data?.data || []);
    }).finally(() => setLoading(false));
  }, [orgId]);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-indigo-500" /></div>;
  if (entries.length === 0) return <p className="text-sm text-slate-500 dark:text-slate-400 text-center py-10">No audit entries yet.</p>;

  return (
    <div className="space-y-2">
      {entries.map(e => (
        <div key={e.id} className="flex items-start gap-3 p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <div className="mt-0.5 text-base w-7 flex-shrink-0 text-center">
            {ACTION_LABELS[e.action]?.split(' ')[0] || '📋'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-slate-900 dark:text-white">
              <span className="font-medium">{e.actor_email || 'System'}</span>
              {' '}{ACTION_LABELS[e.action]?.slice(2) || e.action}
              {e.resource && <span className="font-medium"> {e.resource}</span>}
            </p>
            {Object.keys(e.metadata).length > 0 && (
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                {Object.entries(e.metadata).map(([k, v]) => `${k}: ${v}`).join(' · ')}
              </p>
            )}
          </div>
          <span className="text-xs text-slate-400 dark:text-slate-500 flex-shrink-0 whitespace-nowrap">{timeAgo(e.timestamp)}</span>
        </div>
      ))}
    </div>
  );
}

// ── Tab: Danger Zone ──────────────────────────────────────────────────────────

function DangerZoneTab({ orgId, orgName, isOwner }: { orgId: string; orgName: string; isOwner: boolean }) {
  const router = useRouter();
  const { refetchOrgs, switchOrg } = useOrganization();
  const [confirm, setConfirm] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');

  const deleteOrg = async () => {
    setDeleting(true); setError('');
    try {
      await api.delete(`/organizations/${orgId}/`);
      switchOrg(null);
      await refetchOrgs();
      router.push('/organizations');
    } catch (e: any) {
      setError(e?.response?.data?.error || 'Failed to delete organization.');
    } finally { setDeleting(false); }
  };

  if (!isOwner) return (
    <p className="text-sm text-slate-500 dark:text-slate-400">Only the organization owner can access the danger zone.</p>
  );

  return (
    <div className="max-w-lg">
      <div className="p-5 rounded-xl border-2 border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/10">
        <h3 className="text-base font-semibold text-red-700 dark:text-red-400 mb-2 flex items-center gap-2">
          <Trash2 size={16} />
          Delete Organization
        </h3>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
          This will permanently delete <strong>{orgName}</strong> and all associated data.
          This action <strong>cannot be undone</strong>.
        </p>
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
          Type <code className="bg-slate-100 dark:bg-slate-800 px-1 rounded text-red-600">{orgName}</code> to confirm
        </label>
        <input
          type="text" value={confirm} onChange={e => setConfirm(e.target.value)}
          placeholder={orgName}
          className="w-full px-3 py-2 rounded-lg border border-red-200 dark:border-red-800 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-red-500 mb-3"
        />
        {error && <p className="text-sm text-red-600 dark:text-red-400 mb-3">{error}</p>}
        <button
          onClick={deleteOrg}
          disabled={confirm !== orgName || deleting}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-medium transition-colors disabled:opacity-40"
        >
          {deleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
          Delete permanently
        </button>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'general',   label: 'General',   icon: Settings },
  { id: 'members',   label: 'Members',   icon: Users },
  { id: 'invites',   label: 'Invites',   icon: Mail },
  { id: 'audit',     label: 'Audit Log', icon: Shield },
  { id: 'danger',    label: 'Danger',    icon: Trash2 },
];

export default function OrgSettingsPage() {
  const params = useParams();
  const orgId = params?.id as string;
  const { org: activeOrg, orgs } = useOrganization();
  const { user } = useAuthStore();
  const [tab, setTab] = useState('general');
  const [orgName, setOrgName] = useState('');

  // Find the org from context or fetch name
  useEffect(() => {
    const found = orgs.find(o => o.id === orgId);
    if (found) { setOrgName(found.name); return; }
    api.get(`/organizations/${orgId}/`).then(r => setOrgName(r.data?.data?.name || 'Organization')).catch(() => {});
  }, [orgId, orgs]);

  const myOrg = orgs.find(o => o.id === orgId);
  const isAdmin = myOrg?.my_role === 'owner' || myOrg?.my_role === 'admin';
  const isOwner = myOrg?.my_role === 'owner';
  const currentUserId = user?.id || '';

  return (
    <div className="flex-1 overflow-y-auto p-6">
      {/* Back link */}
      <Link
        href="/organizations"
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white mb-5 transition-colors"
      >
        <ArrowLeft size={15} />
        All organizations
      </Link>

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          {orgName || 'Organization'} Settings
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Manage members, invites, and organization settings
        </p>
      </div>

      {/* Tab navigation */}
      <div className="flex items-center gap-1 mb-6 border-b border-slate-200 dark:border-slate-800">
        {TABS.map(t => {
          const Icon = t.icon;
          const isDanger = t.id === 'danger';
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 px-3 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
                tab === t.id
                  ? isDanger
                    ? 'border-red-500 text-red-600 dark:text-red-400'
                    : 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
                  : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              <Icon size={14} />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {tab === 'general'  && <GeneralTab orgId={orgId} isAdmin={isAdmin} />}
      {tab === 'members'  && <MembersTab orgId={orgId} isAdmin={isAdmin} currentUserId={currentUserId} />}
      {tab === 'invites'  && <InvitesTab orgId={orgId} isAdmin={isAdmin} />}
      {tab === 'audit'    && <AuditLogTab orgId={orgId} />}
      {tab === 'danger'   && <DangerZoneTab orgId={orgId} orgName={orgName} isOwner={isOwner} />}
    </div>
  );
}
