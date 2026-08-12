'use client'

import Image from 'next/image'

interface LogoMarkProps {
  /** Square size in pixels. Default 32 */
  size?: number
  /** Extra classes (rounding, shadow, …) */
  className?: string
  priority?: boolean
}

/**
 * LogoMark — the app's brand mark (square logo image).
 * Used in the sidebar, loading state, auth & landing pages, and as the
 * favicon / PWA icon source.
 */
export function LogoMark({ size = 32, className = '', priority }: LogoMarkProps) {
  return (
    <Image
      src="/icons/logo.png"
      alt="SYNAPSE"
      width={size}
      height={size}
      priority={priority}
      className={`object-cover flex-shrink-0 ${className}`}
    />
  )
}
