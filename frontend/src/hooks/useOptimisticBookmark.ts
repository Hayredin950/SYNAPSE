/**
 * useOptimisticBookmark — React Query optimistic update hook for bookmarks.
 *
 * Industry best practice: optimistic updates give instant UI feedback while
 * the network request completes in background. On failure, the cache is
 * rolled back to the previous state automatically.
 *
 * Phase 7.2 — Optimistic UI updates
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/utils/api'
import toast from 'react-hot-toast'

interface ToggleBookmarkArgs {
  contentType: string  // e.g. 'article', 'repository', 'paper', 'video'
  objectId:    string
  currentlyBookmarked: boolean
}

interface BookmarkListItem {
  id:           string
  content_type: string
  object_id:    string
  [key: string]: unknown
}

export function useOptimisticBookmark() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ contentType, objectId }: ToggleBookmarkArgs) => {
      // Backend route: /api/v1/bookmarks/<content_type_name>/<object_id>/
      // (registered under core/urls.py — NOT under /core/ prefix)
      const { data } = await api.post(
        `/bookmarks/${contentType}/${objectId}/`,
      )
      return data
    },

    // ── Optimistic update ────────────────────────────────────────────────────
    onMutate: async ({ contentType, objectId, currentlyBookmarked }) => {
      // Cancel any outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: ['bookmarks'] })

      // Snapshot previous state for rollback
      const previousBookmarks = queryClient.getQueryData<BookmarkListItem[]>(['bookmarks'])

      // Optimistically update the cache
      queryClient.setQueryData<BookmarkListItem[]>(['bookmarks'], (old = []) => {
        if (currentlyBookmarked) {
          // Remove bookmark
          return old.filter(
            (b) => !(b.content_type === contentType && b.object_id === objectId),
          )
        } else {
          // Add bookmark (temporary placeholder)
          return [
            ...old,
            {
              id:           `optimistic-${objectId}`,
              content_type: contentType,
              object_id:    objectId,
            },
          ]
        }
      })

      return { previousBookmarks }
    },

    // ── Rollback on error ────────────────────────────────────────────────────
    onError: (_err, _vars, context) => {
      if (context?.previousBookmarks) {
        queryClient.setQueryData(['bookmarks'], context.previousBookmarks)
      }
      toast.error('Failed to update bookmark. Please try again.')
    },

    // ── Sync with server after success or error ──────────────────────────────
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['bookmarks'] })
    },
  })
}
