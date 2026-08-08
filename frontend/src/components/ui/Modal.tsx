'use client'

/**
 * Modal / Dialog — Radix UI Dialog with Framer Motion animations.
 *
 * Phase 7.1 — Design System & Animations (Week 19)
 */

import React from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import { clsx } from 'clsx'

// ── Types ──────────────────────────────────────────────────────────────────────

type ModalSize = 'sm' | 'md' | 'lg' | 'xl' | 'full'

interface ModalProps {
  open:         boolean
  onClose:      () => void
  title?:       string
  description?: string
  size?:        ModalSize
  children:     React.ReactNode
  className?:   string
  /** Hide default close (✕) button */
  hideClose?:   boolean
  /** Footer content (e.g. action buttons) */
  footer?:      React.ReactNode
  /**
   * TASK-104-1: Close the modal when the backdrop overlay is clicked.
   * Defaults to true. Set to false for modals with unsaved-changes guards.
   */
  closeOnBackdrop?: boolean
}

// ── Size map ───────────────────────────────────────────────────────────────────

const SIZE_MAP: Record<ModalSize, string> = {
  sm:   'max-w-sm',
  md:   'max-w-md',
  lg:   'max-w-lg',
  xl:   'max-w-2xl',
  full: 'max-w-[95vw]',
}

// ── Animations ─────────────────────────────────────────────────────────────────

const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
}

const dialogVariants = {
  hidden:  { opacity: 0, scale: 0.95, y: 12 },
  visible: { opacity: 1, scale: 1,    y: 0   },
  exit:    { opacity: 0, scale: 0.95, y: 8   },
}

// ── Component ──────────────────────────────────────────────────────────────────

export function Modal({
  open,
  onClose,
  title,
  description,
  size             = 'md',
  children,
  className,
  hideClose        = false,
  footer,
  closeOnBackdrop  = true,
}: ModalProps) {
  return (
    <DialogPrimitive.Root
      open={open}
      onOpenChange={(v) => {
        if (!v && closeOnBackdrop) onClose()
      }}
    >
      <DialogPrimitive.Portal forceMount>
        <AnimatePresence>
          {open && (
            <>
              {/* Overlay */}
              <DialogPrimitive.Overlay asChild forceMount>
                <motion.div
                  key="overlay"
                  variants={overlayVariants}
                  initial="hidden"
                  animate="visible"
                  exit="hidden"
                  transition={{ duration: 0.18 }}
                  className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
                />
              </DialogPrimitive.Overlay>

              {/* Dialog */}
              {/* TASK-405-1: role, aria-modal, aria-labelledby, aria-describedby */}
              <DialogPrimitive.Content asChild forceMount>
                <motion.div
                  key="dialog"
                  variants={dialogVariants}
                  initial="hidden"
                  animate="visible"
                  exit="exit"
                  transition={{ type: 'spring', stiffness: 350, damping: 28 }}
                  role="dialog"
                  aria-modal="true"
                  aria-labelledby={title ? 'modal-title' : undefined}
                  aria-describedby={description ? 'modal-desc' : undefined}
                  className={clsx(
                    'fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2',
                    'w-full mx-auto',
                    SIZE_MAP[size],
                    'bg-white dark:bg-slate-900 rounded-2xl shadow-2xl',
                    'border border-slate-200 dark:border-slate-700/60',
                    'flex flex-col max-h-[90vh]',
                    className,
                  )}
                >
                  {/* Header */}
                  {(title || !hideClose) && (
                    <div className="flex items-start justify-between gap-4 px-6 pt-6 pb-4 border-b border-slate-100 dark:border-slate-800 flex-shrink-0">
                      <div>
                        {title && (
                          <DialogPrimitive.Title id="modal-title" className="text-lg font-semibold text-slate-900 dark:text-white leading-tight">
                            {title}
                          </DialogPrimitive.Title>
                        )}
                        {description && (
                          <DialogPrimitive.Description id="modal-desc" className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                            {description}
                          </DialogPrimitive.Description>
                        )}
                      </div>
                      {!hideClose && (
                        <DialogPrimitive.Close asChild>
                          <button
                            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors flex-shrink-0"
                            aria-label="Close"
                          >
                            <X size={16} />
                          </button>
                        </DialogPrimitive.Close>
                      )}
                    </div>
                  )}

                  {/* Body */}
                  <div className="flex-1 overflow-y-auto px-6 py-5">
                    {children}
                  </div>

                  {/* Footer */}
                  {footer && (
                    <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-slate-100 dark:border-slate-800 flex-shrink-0">
                      {footer}
                    </div>
                  )}
                </motion.div>
              </DialogPrimitive.Content>
            </>
          )}
        </AnimatePresence>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

export default Modal
