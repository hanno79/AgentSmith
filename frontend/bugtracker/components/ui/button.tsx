/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Wiederverwendbare Button-Komponente mit Glassmorphismus-Varianten
 */

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

// Button-Varianten mit CVA definieren
const buttonVarianten = cva(
  // Basisstile
  [
    'inline-flex items-center justify-center gap-2',
    'rounded-lg font-medium text-sm',
    'transition-all duration-200',
    'focus-visible:outline-none focus-visible:ring-2',
    'disabled:opacity-50 disabled:cursor-not-allowed',
    'cursor-pointer select-none',
  ].join(' '),
  {
    variants: {
      variante: {
        // Primaere Aktion - Blau
        primaer: [
          'bg-[#2b336a] text-white border border-[rgba(43,51,106,0.6)]',
          'hover:bg-[#353e80] hover:-translate-y-0.5',
          'hover:shadow-[0_6px_20px_rgba(43,51,106,0.5)]',
          'active:translate-y-0',
        ].join(' '),
        // Gefaehrliche Aktion - Rot
        gefahr: [
          'bg-[#870010] text-white border border-[rgba(135,0,16,0.6)]',
          'hover:bg-[#a00013] hover:-translate-y-0.5',
          'hover:shadow-[0_6px_20px_rgba(135,0,16,0.5)]',
          'active:translate-y-0',
        ].join(' '),
        // Glas-Variante
        glas: [
          'bg-[rgba(255,255,255,0.06)] text-white/80',
          'border border-[rgba(255,255,255,0.1)]',
          'backdrop-blur-md',
          'hover:bg-[rgba(255,255,255,0.1)] hover:text-white hover:-translate-y-0.5',
          'hover:border-[rgba(255,255,255,0.18)]',
        ].join(' '),
        // Geisterhafter Button
        geist: [
          'bg-transparent text-white/60',
          'border border-transparent',
          'hover:bg-[rgba(255,255,255,0.05)] hover:text-white',
        ].join(' '),
      },
      groesse: {
        klein: 'h-7 px-3 text-xs rounded-md',
        mittel: 'h-9 px-4 text-sm',
        gross: 'h-11 px-6 text-base',
        icon: 'h-8 w-8 rounded-md',
      },
    },
    defaultVariants: {
      variante: 'glas',
      groesse: 'mittel',
    },
  }
);

// Interface fuer Button-Props
export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVarianten> {
  loading?: boolean;
}

/**
 * Button-Komponente mit verschiedenen Glassmorphismus-Varianten
 */
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variante, groesse, loading, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(buttonVarianten({ variante, groesse }), className)}
        {...props}
      >
        {/* Lade-Indikator */}
        {loading && (
          <span className="inline-block w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';

export { Button, buttonVarianten };
