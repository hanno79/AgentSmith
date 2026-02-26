/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Glassmorphismus Textarea-Komponente fuer Formulare
 */

import * as React from 'react';
import { cn } from '@/lib/utils';

// Interface fuer Textarea-Props
export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

/**
 * Textarea-Komponente mit Glassmorphismus-Styling
 */
const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
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
          // Groesse
          'min-h-[80px] resize-vertical',
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

Textarea.displayName = 'Textarea';

export { Textarea };
