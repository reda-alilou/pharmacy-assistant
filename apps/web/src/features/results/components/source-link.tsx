import type { ReactNode } from 'react'
import { ArrowUpRight } from 'lucide-react'
import { safeLink } from '../lib/presentation'

export function SourceLink({ url, children }: { url: string; children: ReactNode }) {
  const href = safeLink(url)
  return href ? <a className="source-link" href={href} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">
    {children}<ArrowUpRight aria-hidden="true" size={13} /><span className="sr-only"> (nouvel onglet)</span>
  </a> : <span>{children}</span>
}
