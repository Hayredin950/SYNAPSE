/**
 * useUpgradeModal — convenience re-export hook.
 * TASK-003-F3
 *
 * Usage:
 *   const { openUpgradeModal } = useUpgradeModal()
 *   openUpgradeModal({ resource: 'ai_queries', used: 50, limit: 50 })
 */
export { useUpgradeModal } from '@/components/modals/UpgradeModal'
export type { UpgradeContext } from '@/components/modals/UpgradeModal'
