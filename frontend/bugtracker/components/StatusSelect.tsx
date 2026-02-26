/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Inline Status-Auswahl direkt in der Tabelle mit farbigen Optionen
 */

'use client';

import React from 'react';
import * as SelectPrimitive from '@radix-ui/react-select';
import { ChevronDown, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ItemStatus } from '@/types';

// Farbige Konfiguration fuer jeden Status
const statusKonfiguration: Record<
  ItemStatus,
  { farbe: string; hintergrund: string; border: string }
> = {
  'Offen': {
    farbe: 'text-white/70',
    hintergrund: 'bg-[rgba(124,124,107,0.2)]',
    border: 'border-[rgba(124,124,107,0.3)]',
  },
  'In Bearbeitung': {
    farbe: 'text-[#7b8fff]',
    hintergrund: 'bg-[rgba(43,51,106,0.25)]',
    border: 'border-[rgba(43,51,106,0.4)]',
  },
  'Erledigt': {
    farbe: 'text-[#4ade80]',
    hintergrund: 'bg-[rgba(22,163,74,0.18)]',
    border: 'border-[rgba(22,163,74,0.3)]',
  },
  'Abgelehnt': {
    farbe: 'text-[#ff4d6d]',
    hintergrund: 'bg-[rgba(135,0,16,0.18)]',
    border: 'border-[rgba(135,0,16,0.3)]',
  },
};

// Alle verfuegbaren Status-Optionen
const alleStatus: ItemStatus[] = ['Offen', 'In Bearbeitung', 'Erledigt', 'Abgelehnt'];

// Props-Interface
interface StatusSelectProps {
  wert: ItemStatus;
  onAenderung: (neuerStatus: ItemStatus) => void;
  disabled?: boolean;
}

/**
 * Inline Status-Select Komponente mit farbigen Optionen
 */
export function StatusSelect({ wert, onAenderung, disabled = false }: StatusSelectProps) {
  const konfig = statusKonfiguration[wert];

  return (
    <SelectPrimitive.Root
      value={wert}
      onValueChange={(neuerWert) => onAenderung(neuerWert as ItemStatus)}
      disabled={disabled}
    >
      {/* Trigger-Button */}
      <SelectPrimitive.Trigger
        className={cn(
          'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium',
          'border backdrop-blur-sm cursor-pointer',
          'transition-all duration-200',
          'hover:opacity-90 focus:outline-none',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          konfig.farbe,
          konfig.hintergrund,
          konfig.border
        )}
        aria-label="Status aendern"
      >
        <SelectPrimitive.Value />
        <ChevronDown className="w-3 h-3 opacity-70" aria-hidden="true" />
      </SelectPrimitive.Trigger>

      {/* Portal fuer das Dropdown */}
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          className={cn(
            'z-50 min-w-[160px] rounded-lg overflow-hidden',
            'bg-[#111320] border border-[rgba(255,255,255,0.1)]',
            'shadow-[0_16px_48px_rgba(0,0,0,0.5)]',
            'backdrop-blur-xl',
            'animate-fadeIn'
          )}
          position="popper"
          sideOffset={4}
        >
          <SelectPrimitive.Viewport className="p-1">
            {alleStatus.map((status) => {
              const optKonfig = statusKonfiguration[status];
              return (
                <SelectPrimitive.Item
                  key={status}
                  value={status}
                  className={cn(
                    'relative flex items-center gap-2 px-3 py-2 rounded-md',
                    'text-xs cursor-pointer select-none',
                    'outline-none transition-all duration-150',
                    'data-[highlighted]:bg-[rgba(255,255,255,0.07)]',
                    optKonfig.farbe
                  )}
                >
                  {/* Haekchen fuer aktiven Status */}
                  <SelectPrimitive.ItemIndicator>
                    <Check className="w-3 h-3" aria-hidden="true" />
                  </SelectPrimitive.ItemIndicator>
                  <SelectPrimitive.ItemText>{status}</SelectPrimitive.ItemText>
                </SelectPrimitive.Item>
              );
            })}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}
