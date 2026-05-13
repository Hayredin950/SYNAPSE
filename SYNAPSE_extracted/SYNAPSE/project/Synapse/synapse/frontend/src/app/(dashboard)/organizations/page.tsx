'use client';

/**
 * TASK-006-F3: Organizations Management Page
 * Route: /organizations
 *
 * Lists all orgs the user belongs to. Allows creating a new org.
 * Shows role, member count, and quick links to settings / leave.
 */

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useSearchParams, useRouter } from 'next/navigation';
import {
  Building2, Plus, Users, Settings, LogOut, Crown,
  Shield, Eye, User, Loader2, X, AlertCircle,
} from 'lucide-react';
import { api } from '@/utils/api';
import { useOrganization, Organization } from '@/contexts/OrganizationContext';
import { useAuthStore } from '@/store/authStore';

// ── Role badge ────────────────────────────────────────────────────────────────

const ROLE_STYLES: Record<string, { label: string; icon: React.ElementType; cls: string }> = {
  owner:  { label: 'Owner',  icon: Crown,  cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  admin:  { label: 'Admin',  icon: Shield, cls: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300' },
  member: { label: 'Member', icon: User,   cls: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300' },
  viewer: { label: 'Viewer', icon: Eye,    cls: 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400' },
};

function RoleBadge({ role }: { role: string }) {
  const style = ROLE_STYLES[role] || ROLE_STYLES.member;
  const Icon = style.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${style.cls}`}>
      <Icon size={10} />
      {style.label}
    </span>
  );
}

// ── Create Org Modal ──────────────────────────────────────────────────────────

function CreateOrgModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim().length < 2) { setError('Name must be at least 2 characters.'); return; }
    setLoading(true);
    setError('');
    try {
      await api.post('/organizations/', { name: name.trim(), description: description.trim() });
      onCreated();
      onClose();
    } catch (err: any) {
      const msg = err?.response?.data?.error;
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg) || 'Failed to create organization.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">New Organization</h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Organization name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Acme Corp"
              className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Description <span className="text-slate-400 font-normal">(optional)</span>
            </label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="What does this organization do?"
              rows={3}
              className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          <div className="flex items-center gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2 rounded-lg text-sm font-medium bg-indigo-600 hover:bg-indigo-700 text-white transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
              Create
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Leave Org Confirm ─────────────────────────────────────────────────────────

function LeaveConfirmModal({ org, onClose, onLeft }: { org: Organization; onClose: () => void; onLeft: () => void }) {
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLeave = async () => {
    setLoading(true);
    try {
      await api.delete(`/organizations/${org.id}/members/${user?.id}/`);
      onLeft();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Failed to leave organization.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-2">Leave {org.name}?</h2>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
          You will lose access to all shared content in this organization.
        </p>
        {error && (
          <div className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg p-3 mb-4">
            <AlertCircle size={14} />{error}
          </div>
        )}
        <div className="flex items-center gap-3">
          <button onClick={onClose} className="flex-1 px-4 py-2 rounded-lg text-sm font-medium border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
            Cancel
          </button>
          <button
            onClick={handleLeave}
            disabled={loading}
            className="flex-1 px-4 py-2 rounded-lg text-sm font-medium bg-red-600 hover:bg-red-700 text-white transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : null}
            Leave
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Org Card ──────────────────────────────────────────────────────────────────

function OrgCard({ org, onLeave }: { org: Organization; onLeave: (o: Organization) => void }) {
  const isOwner = org.my_role === 'owner';
  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 flex flex-col gap-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {org.logo_url ? (
            <img src={org.logo_url} alt={org.name} className="w-10 h-10 rounded-xl object-cover flex-shrink-0" />
          ) : (
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center flex-shrink-0 shadow-md">
              <span className="text-white font-bold text-base">{org.name[0].toUpperCase()}</span>
            </div>
          )}
          <div className="min-w-0">
            <h3 className="font-semibold text-slate-900 dark:text-white truncate">{org.name}</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">{org.slug}</p>
          </div>
        </div>
        <RoleBadge role={org.my_role || 'member'} />
      </div>

      {org.description && (
        <p className="text-sm text-slate-600 dark:text-slate-400 line-clamp-2">{org.description}</p>
      )}

      <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
        <span className="flex items-center gap-1">
          <Users size={12} />
          {org.member_count} member{org.member_count !== 1 ? 's' : ''}
        </span>
        <span className="capitalize">{org.plan} plan</span>
      </div>

      <div className="flex items-center gap-2 pt-1">
        {(org.my_role === 'owner' || org.my_role === 'admin') && (
          <Link
            href={`/organizations/${org.id}/settings`}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
          >
            <Settings size={13} />
            Settings
          </Link>
        )}
        {!isOwner && (
          <button
            onClick={() => onLeave(org)}
            className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
          >
            <LogOut size={13} />
            Leave
          </button>
        )}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function OrganizationsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { orgs, loading, refetchOrgs } = useOrganization();
  const [showCreate, setShowCreate] = useState(searchParams.get('create') === '1');
  const [leavingOrg, setLeavingOrg] = useState<Organization | null>(null);

  const handleCreated = async () => {
    await refetchOrgs();
  };

  const handleLeft = async () => {
    await refetchOrgs();
  };

  return (
    <div className="flex-1 overflow-y-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Organizations</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Manage your team workspaces
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors shadow-md"
        >
          <Plus size={16} />
          New Organization
        </button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="animate-spin text-indigo-500" size={32} />
        </div>
      ) : orgs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mb-4">
            <Building2 size={28} className="text-slate-400" />
          </div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">No organizations yet</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 max-w-sm mb-6">
            Create an organization to collaborate with your team and share workspaces, documents, and automations.
          </p>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors"
          >
            <Plus size={16} />
            Create your first organization
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {orgs.map(org => (
            <OrgCard key={org.id} org={org} onLeave={setLeavingOrg} />
          ))}
        </div>
      )}

      {/* Modals */}
      {showCreate && (
        <CreateOrgModal
          onClose={() => setShowCreate(false)}
          onCreated={handleCreated}
        />
      )}
      {leavingOrg && (
        <LeaveConfirmModal
          org={leavingOrg}
          onClose={() => setLeavingOrg(null)}
          onLeft={handleLeft}
        />
      )}
    </div>
  );
}
