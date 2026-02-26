/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Badge-Komponente mit Glassmorphismus-Varianten fuer Status und Typen
 */

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

// Badge-Varianten mit CVA
const badgeVarianten = cva(
  'inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-medium border backdrop-blur-sm transition-all duration-200',
  {
    variants: {
      variante: {
        // Standard Glas-Badge
        standard: [
          'bg-[rgba(255,255,255,0.06)] text-white/70',
          'border-[rgba(255,255,255,0.1)]',
        ].join(' '),
        // Bug - Rot-Akzent
        bug: [
          'bg-[rgba(135,0,16,0.18)] text-[#ff4d6d]',
          'border-[rgba(135,0,16,0.3)]',
        ].join(' '),
        // Idee - Blau-Akzent
        idee: [
          'bg-[rgba(43,51,106,0.25)] text-[#7b8fff]',
          'border-[rgba(43,51,106,0.4)]',
        ].join(' '),
        // Erledigt - Gruen-Akzent
        erledigt: [
          'bg-[rgba(22,163,74,0.18)] text-[#4ade80]',
          'border-[rgba(22,163,74,0.3)]',
        ].join(' '),
        // Offen - Neutral
        offen: [
          'bg-[rgba(124,124,107,0.2)] text-white/70',
          'border-[rgba(124,124,107,0.3)]',
        ].join(' '),
      },
    },
    defaultVariants: {
      variante: 'standard',
    },
  }
);

// Interface fuer Badge-Props
export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVarianten> {}

/**
 * Badge-Komponente mit farbigen Varianten
 */
function Badge({ className, variante, ...props }: BadgeProps) {
  return (
    <span
      className={cn(badgeVarianten({ variante }), className)}
      {...props}
    />
  );
}

export { Badge, badgeVarianten };
