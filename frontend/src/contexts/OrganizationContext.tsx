'use client';

/**
 * TASK-006-F2: Organization Context Provider
 *
 * Provides the active organization throughout the dashboard.
 * - Fetches all orgs the user belongs to from GET /api/v1/organizations/
 * - Persists the selected org ID in localStorage
 * - Exposes useOrganization() hook with: org, orgs, role, isOwner, isAdmin,
 *   isMember, switchOrg, loading, refetchOrgs
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
} from 'react';
import { api } from '@/utils/api';
import { useAuthStore } from '@/store/authStore';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface OrgMember {
  id: string;
  user: string;
  user_email: string;
  user_name: string;
  user_avatar_url: string | null;
  role: 'owner' | 'admin' | 'member' | 'viewer';
  is_active: boolean;
  joined_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  description: string;
  logo_url: string;
  website: string;
  plan: 'free' | 'pro' | 'enterprise';
  owner: string;
  owner_email: string;
  member_count: number;
  my_role: 'owner' | 'admin' | 'member' | 'viewer' | null;
  created_at: string;
  members?: OrgMember[];
}

interface OrganizationContextValue {
  /** All orgs the current user belongs to */
  orgs: Organization[];
  /** The currently active/selected org (null = personal workspace) */
  org: Organization | null;
  /** Current user's role in the active org */
  role: string | null;
  isOwner: boolean;
  isAdmin: boolean;
  isMember: boolean;
  /** Switch the active org (pass null for personal workspace) */
  switchOrg: (orgId: string | null) => void;
  loading: boolean;
  /** Non-null when the org fetch failed — show to user */
  error: string | null;
  /** Force re-fetch orgs from API */
  refetchOrgs: () => Promise<void>;
}

// ── Context ───────────────────────────────────────────────────────────────────

const OrganizationContext = createContext<OrganizationContextValue>({
  orgs: [],
  org: null,
  role: null,
  isOwner: false,
  isAdmin: false,
  isMember: false,
  switchOrg: () => {},
  loading: false,
  error: null,
  refetchOrgs: async () => {},
});

const STORAGE_KEY = 'synapse_active_org_id';

// ── Provider ──────────────────────────────────────────────────────────────────

export function OrganizationProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [activeOrgId, setActiveOrgId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchOrgs = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get('/organizations/');
      const list: Organization[] = data?.data ?? data?.results ?? [];
      setOrgs(list);

      // Restore persisted org selection, validate it's still valid
      const saved = typeof window !== 'undefined'
        ? localStorage.getItem(STORAGE_KEY)
        : null;

      if (saved && list.some(o => o.id === saved)) {
        setActiveOrgId(saved);
      } else {
        // If only one org, auto-select it; otherwise default to personal workspace
        setActiveOrgId(list.length === 1 ? list[0].id : null);
      }
    } catch (err) {
      const status = typeof err === 'object' && err && 'response' in err
        ? (err as { response?: { status?: number } }).response?.status
        : null;
      if (status === 500) {
        setOrgs([]);
        setActiveOrgId(null);
        setError(null);
        return;
      }
      const msg = err instanceof Error ? err.message : 'Failed to load organizations';
      console.error('Failed to fetch organizations:', err);
      setError(msg);
      setOrgs([]);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchOrgs();
  }, [fetchOrgs]);

  const switchOrg = useCallback((orgId: string | null) => {
    setActiveOrgId(orgId);
    if (typeof window !== 'undefined') {
      if (orgId) {
        localStorage.setItem(STORAGE_KEY, orgId);
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    }
  }, []);

  const org = useMemo(
    () => orgs.find(o => o.id === activeOrgId) ?? null,
    [orgs, activeOrgId],
  );

  const role = org?.my_role ?? null;
  const isOwner = role === 'owner';
  const isAdmin = role === 'owner' || role === 'admin';
  const isMember = role !== null;

  const value = useMemo<OrganizationContextValue>(
    () => ({ orgs, org, role, isOwner, isAdmin, isMember, switchOrg, loading, error, refetchOrgs: fetchOrgs }),
    [orgs, org, role, isOwner, isAdmin, isMember, switchOrg, loading, error, fetchOrgs],
  );

  return (
    <OrganizationContext.Provider value={value}>
      {children}
    </OrganizationContext.Provider>
  );
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useOrganization(): OrganizationContextValue {
  return useContext(OrganizationContext);
}
