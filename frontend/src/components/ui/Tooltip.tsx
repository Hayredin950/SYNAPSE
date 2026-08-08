'use client'

/**
 * Premium Tooltip Component — uses a fixed-position portal so it is never
 * clipped by overflow:hidden parents or sidebar borders.
 *
 * Usage:
 *   <Tooltip content="Hello world"><button>Hover me</button></Tooltip>
 *   <Tooltip content="Hello" side="right"><button>Hover me</button></Tooltip>
 *
 * Sides: top (default) | bottom | left | right
 */

import React, { useRef, useState, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/utils/helpers'

interface TooltipProps {
  content: React.ReactNode
  side?: 'top' | 'bottom' | 'left' | 'right'
  children: React.ReactElement
  className?: string
  delay?: boolean
}

export function Tooltip({ content, side = 'top', children, className, delay = false }: TooltipProps) {
  const [show, setShow] = useState(false)
  const [coords, setCoords] = useState({ top: 0, left: 0 })
  const triggerRef = useRef<HTMLDivElement>(null)
  const GAP = 8 // px gap between trigger and tooltip

  const updateCoords = useCallback(() => {
    if (!triggerRef.current) return
    const rect = triggerRef.current.getBoundingClientRect()

    let top = 0
    let left = 0

    switch (side) {
      case 'top':
        top  = rect.top - GAP
        left = rect.left + rect.width / 2
        break
      case 'bottom':
        top  = rect.bottom + GAP
        left = rect.left + rect.width / 2
        break
      case 'left':
        top  = rect.top + rect.height / 2
        left = rect.left - GAP
        break
      case 'right':
        top  = rect.top + rect.height / 2
        left = rect.right + GAP
        break
    }

    setCoords({ top, left })
  }, [side])

  const handleMouseEnter = () => {
    updateCoords()
    setShow(true)
  }

  // transform classes to anchor the rendered tooltip box to the computed point
  const transformClasses: Record<string, string> = {
    top:    '-translate-x-1/2 -translate-y-full',
    bottom: '-translate-x-1/2',
    left:   '-translate-x-full -translate-y-1/2',
    right:  '-translate-y-1/2',
  }

  const arrowClasses: Record<string, string> = {
    top:    'top-full left-1/2 -translate-x-1/2 border-l border-b border-slate-700',
    bottom: 'bottom-full left-1/2 -translate-x-1/2 border-l border-t border-slate-700',
    left:   'left-full top-1/2 -translate-y-1/2 border-r border-t border-slate-700',
    right:  'right-full top-1/2 -translate-y-1/2 border-l border-b border-slate-700',
  }

  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  return (
    <div
      ref={triggerRef}
      className="relative inline-flex"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={() => setShow(false)}
      onFocus={handleMouseEnter}
      onBlur={() => setShow(false)}
    >
      {children}

      {mounted && show && content && createPortal(
        <div
          className={cn(
            'pointer-events-none fixed z-[99999] whitespace-nowrap',
            transformClasses[side],
            delay && 'animate-in fade-in-0 zoom-in-95 duration-150',
            className
          )}
          style={{ top: coords.top, left: coords.left }}
        >
          <div className="relative bg-slate-800 text-white text-[10px] font-semibold px-2.5 py-1.5 rounded-lg border border-slate-600 shadow-xl shadow-black/40">
            {content}
            {/* Arrow */}
            <div className={cn(
              'absolute w-2 h-2 bg-slate-800 rotate-45 border-slate-600',
              arrowClasses[side]
            )} />
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}
