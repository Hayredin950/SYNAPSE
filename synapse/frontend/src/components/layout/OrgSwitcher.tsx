'use client';

/**
 * TASK-006-F1: Organization Switcher
 * Shown in Navbar. Lets the user switch between personal workspace and orgs.
 */

import React, { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { Building2, ChevronDown, Check, Plus, Users } from 'lucide-react';
import { useOrganization } from '@/contexts/OrganizationContext';

export function OrgSwitcher() {
  const { orgs, org, switchOrg, loading } = useOrganization();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Don't render if user has no orgs
  if (!loading && orgs.length === 0) {
    return (
      <Link
        href="/organizations"
        className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors border border-dashed border-slate-300 dark:border-slate-700"
      >
        <Plus size={12} />
        New Org
      </Link>
    );
  }

  const label = org ? org.name : 'Personal';
  const initial = org ? org.name[0].toUpperCase() : '👤';

  return (
    <div ref={ref} className="relative hidden sm:block">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors border border-slate-200 dark:border-slate-700 max-w-[160px]"
        title="Switch workspace"
      >
        {/* Avatar */}
        {org ? (
          org.logo_url ? (
            <img src={org.logo_url} alt={org.name} className="w-5 h-5 rounded object-cover flex-shrink-0" />
          ) : (
            <div className="w-5 h-5 rounded bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center flex-shrink-0">
              <span className="text-white text-[10px] font-bold">{initial}</span>
            </div>
          )
        ) : (
          <div className="w-5 h-5 rounded bg-slate-200 dark:bg-slate-700 flex items-center justify-center flex-shrink-0 text-[11px]">
            👤
          </div>
        )}
        <span className="truncate text-xs">{label}</span>
        <ChevronDown size={12} className="flex-shrink-0 text-slate-400" />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-2 w-56 bg-white dark:bg-slate-900 rounded-xl shadow-xl border border-slate-200 dark:border-slate-800 z-50 overflow-hidden">
          {/* Personal workspace */}
          <div className="p-1.5">
            <p className="px-2 pt-1 pb-0.5 text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
              Workspace
            </p>
            <button
              onClick={() => { switchOrg(null); setOpen(false); }}
              className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm transition-colors ${
                org === null
                  ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-300'
                  : 'text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'
              }`}
            >
              <div className="w-6 h-6 rounded-lg bg-slate-200 dark:bg-slate-700 flex items-center justify-center flex-shrink-0 text-sm">
                👤
              </div>
              <span className="flex-1 text-left text-sm font-medium truncate">Personal</span>
              {org === null && <Check size={14} className="text-indigo-600 dark:text-indigo-400 flex-shrink-0" />}
            </button>
          </div>

          {/* Organizations */}
          {orgs.length > 0 && (
            <div className="p-1.5 border-t border-slate-100 dark:border-slate-800">
              <p className="px-2 pt-1 pb-0.5 text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                Organizations
              </p>
              {orgs.map(o => (
                <button
                  key={o.id}
                  onClick={() => { switchOrg(o.id); setOpen(false); }}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm transition-colors ${
                    org?.id === o.id
                      ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-300'
                      : 'text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'
                  }`}
                >
                  {o.logo_url ? (
                    <img src={o.logo_url} alt={o.name} className="w-6 h-6 rounded-lg object-cover flex-shrink-0" />
                  ) : (
                    <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center flex-shrink-0">
                      <span className="text-white text-[11px] font-bold">{o.name[0].toUpperCase()}</span>
                    </div>
                  )}
                  <div className="flex-1 text-left min-w-0">
                    <p className="text-sm font-medium truncate">{o.name}</p>
                    <p className="text-[10px] text-slate-500 dark:text-slate-500 capitalize">{o.my_role} · {o.member_count} member{o.member_count !== 1 ? 's' : ''}</p>
                  </div>
                  {org?.id === o.id && <Check size={14} className="text-indigo-600 dark:text-indigo-400 flex-shrink-0" />}
                </button>
              ))}
            </div>
          )}

          {/* Footer: manage / create */}
          <div className="p-1.5 border-t border-slate-100 dark:border-slate-800">
            <Link
              href="/organizations"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
            >
              <Users size={13} />
              Manage organizations
            </Link>
            <Link
              href="/organizations?create=1"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-colors"
            >
              <Plus size={13} />
              New organization
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
