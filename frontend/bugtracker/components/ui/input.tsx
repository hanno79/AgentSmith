/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Glassmorphismus Input-Komponente fuer Formulare
 */

import * as React from 'react';
import { cn } from '@/lib/utils';

// Interface fuer Input-Props
export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

/**
 * Input-Komponente mit Glassmorphismus-Styling
 */
const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        ref={ref}
        type={type}
        className={cn(
          // Basisstile
          'w-full px-4 py-2.5 rounded-lg text-sm',
          // Text und Hintergrund
          'bg-[rgba(255,255,255,0.05)] text-white/90',
          'placeholder:text-white/25',
          // Border
          'border border-[rgba(255,255,255,0.1)]',
          // Backdrop-Filter
          'backdrop-blur-md',
          // Fokus-Zustand
          'focus:outline-none focus:border-[rgba(43,51,106,0.8)]',
          'focus:bg-[rgba(255,255,255,0.07)]',
          'focus:shadow-[0_0_0_2px_rgba(43,51,106,0.3)]',
          // Transition
          'transition-all duration-200',
          // Disabled-Zustand
          'disabled:opacity-50 disabled:cursor-not-allowed',
          className
        )}
        {...props}
      />
    );
  }
);

Input.displayName = 'Input';

export { Input };
