'use client'

/**
 * PageTransition — wraps page content with Framer Motion AnimatePresence.
 * Drop into any page layout to get smooth enter/exit transitions.
 *
 * Phase 7.1 — Design System & Animations (Week 19)
 *
 * Usage:
 *   <PageTransition>
 *     <YourPageContent />
 *   </PageTransition>
 */

import React from 'react'
import { motion } from 'framer-motion'

interface PageTransitionProps {
  children: React.ReactNode
  className?: string
}

const variants = {
  hidden:  { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0  },
  exit:    { opacity: 0, y: -8 },
}

export function PageTransition({ children, className }: PageTransitionProps) {
  return (
    <motion.div
      variants={variants}
      initial="hidden"
      animate="visible"
      exit="exit"
      transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

// ── Staggered list wrapper ─────────────────────────────────────────────────────

interface StaggerListProps {
  children: React.ReactNode
  className?: string
  /** delay between each child (seconds) */
  staggerDelay?: number
}

const containerVariants = {
  hidden:  {},
  visible: { transition: { staggerChildren: 0.07, delayChildren: 0.05 } },
}

const itemVariants = {
  hidden:  { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 300, damping: 24 } },
}

export function StaggerList({ children, className, staggerDelay }: StaggerListProps) {
  const customContainer = staggerDelay
    ? { hidden: {}, visible: { transition: { staggerChildren: staggerDelay, delayChildren: 0.05 } } }
    : containerVariants

  return (
    <motion.div
      variants={customContainer}
      initial="hidden"
      animate="visible"
      className={className}
    >
      {React.Children.map(children, (child, i) => (
        <motion.div key={i} variants={itemVariants}>
          {child}
        </motion.div>
      ))}
    </motion.div>
  )
}

// ── Individual stagger item (for use inside StaggerList or manually) ───────────

export function StaggerItem({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div variants={itemVariants} className={className}>
      {children}
    </motion.div>
  )
}

export default PageTransition
