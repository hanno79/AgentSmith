/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Typ-Badge Komponente fuer Bug (Rot) und Idee (Blau) Eintraege
 */

import React from 'react';
import { Bug, Lightbulb } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ItemTyp } from '@/types';

// Props-Interface
interface TypBadgeProps {
  typ: ItemTyp;
  className?: string;
}

/**
 * Zeigt den Typ eines Eintrags als farbiges Badge an
 * Bug: Rot-Akzent | Idee: Blau-Akzent
 */
export function TypBadge({ typ, className }: TypBadgeProps) {
  const istBug = typ === 'Bug';

  return (
    <span
      className={cn(
        // Basisstile
        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium',
        'border backdrop-blur-sm',
        // Farbvarianten
        istBug
          ? [
              'bg-[rgba(135,0,16,0.18)] text-[#ff4d6d]',
              'border-[rgba(135,0,16,0.3)]',
            ].join(' ')
          : [
              'bg-[rgba(43,51,106,0.25)] text-[#7b8fff]',
              'border-[rgba(43,51,106,0.4)]',
            ].join(' '),
        className
      )}
    >
      {/* Icon je nach Typ */}
      {istBug ? (
        <Bug className="w-3 h-3" aria-hidden="true" />
      ) : (
        <Lightbulb className="w-3 h-3" aria-hidden="true" />
      )}
      {typ}
    </span>
  );
}
