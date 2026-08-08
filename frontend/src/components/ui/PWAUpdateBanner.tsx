'use client'

/**
 * Feature #20: PWA Service Worker Update Notification
 * Shows a non-intrusive banner when a new app version is available.
 */

import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { RefreshCw, X } from 'lucide-react'

export function PWAUpdateBanner() {
  const [showUpdate, setShowUpdate] = useState(false)
  const [reg, setReg] = useState<ServiceWorkerRegistration | null>(null)

  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return

    navigator.serviceWorker.ready.then(registration => {
      setReg(registration)
      registration.addEventListener('updatefound', () => {
        const newWorker = registration.installing
        if (!newWorker) return
        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
            setShowUpdate(true)
          }
        })
      })
    })

    // Also handle controller change
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      window.location.reload()
    })
  }, [])

  const update = () => {
    if (reg?.waiting) {
      reg.waiting.postMessage({ type: 'SKIP_WAITING' })
    }
    setShowUpdate(false)
    window.location.reload()
  }

  return (
    <AnimatePresence>
      {showUpdate && (
        <motion.div
          className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[9999] flex items-center gap-3 px-4 py-3 bg-indigo-600 text-white rounded-2xl shadow-2xl shadow-indigo-900/30 text-sm font-medium"
          initial={{ y: 80, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 80, opacity: 0 }}
        >
          <RefreshCw size={15} className="flex-shrink-0 animate-spin" />
          <span>New version available!</span>
          <button onClick={update} className="px-3 py-1 bg-white text-indigo-600 rounded-lg text-xs font-bold hover:bg-indigo-50 transition-colors">
            Reload
          </button>
          <button onClick={() => setShowUpdate(false)} className="p-1 hover:opacity-70 transition-opacity">
            <X size={14} />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
