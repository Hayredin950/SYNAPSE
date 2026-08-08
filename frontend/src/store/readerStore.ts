import { create } from 'zustand'
import type { ReaderArticle } from '@/components/modals/ContentReaderModal'

interface ReaderStore {
  article: ReaderArticle | null
  open:    (article: ReaderArticle) => void
  close:   () => void
}

export const useReaderStore = create<ReaderStore>(set => ({
  article: null,
  open:    article => set({ article }),
  close:   ()      => set({ article: null }),
}))
