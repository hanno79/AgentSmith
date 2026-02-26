/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Filter-Leiste zum Filtern nach Typ und Status mit Glassmorphismus
 */

'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { FilterZustand, ItemTyp, ItemStatus } from '@/types';

// Props-Interface
interface FilterLeisteProps {
  filter: FilterZustand;
  onFilterAenderung: (neuerFilter: Partial<FilterZustand>) => void;
}

// Typ-Optionen
const typOptionen: Array<{ wert: ItemTyp | 'Alle'; label: string }> = [
  { wert: 'Alle', label: 'Alle Typen' },
  { wert: 'Bug', label: 'Bug' },
  { wert: 'Idee', label: 'Idee' },
];

// Status-Optionen
const statusOptionen: Array<{ wert: ItemStatus | 'Alle'; label: string }> = [
  { wert: 'Alle', label: 'Alle Status' },
  { wert: 'Offen', label: 'Offen' },
  { wert: 'In Bearbeitung', label: 'In Bearbeitung' },
  { wert: 'Erledigt', label: 'Erledigt' },
  { wert: 'Abgelehnt', label: 'Abgelehnt' },
];

/**
 * Filter-Leiste mit Schaltflaechen fuer Typ und Status
 */
export function FilterLeiste({ filter, onFilterAenderung }: FilterLeisteProps) {
  return (
    <div className="glas rounded-xl px-6 py-4 mb-6 animate-slideUp flex flex-wrap gap-6 items-center">
      {/* Typ-Filter */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-white/40 text-xs font-medium uppercase tracking-widest mr-1">
          Typ:
        </span>
        {typOptionen.map((option) => {
          const istAktiv = filter.typ === option.wert;
          return (
            <button
              key={option.wert}
              onClick={() => onFilterAenderung({ typ: option.wert })}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium',
                'border transition-all duration-200',
                'cursor-pointer select-none',
                istAktiv
                  ? [
                      'bg-[rgba(43,51,106,0.45)] text-[#7b8fff]',
                      'border-[rgba(43,51,106,0.6)]',
                      'shadow-[0_0_12px_rgba(43,51,106,0.4)]',
                    ].join(' ')
                  : [
                      'bg-[rgba(255,255,255,0.04)] text-white/50',
                      'border-[rgba(255,255,255,0.07)]',
                      'hover:bg-[rgba(255,255,255,0.08)] hover:text-white/80',
                      'hover:border-[rgba(255,255,255,0.12)]',
                    ].join(' ')
              )}
              aria-pressed={istAktiv}
            >
              {option.label}
            </button>
          );
        })}
      </div>

      {/* Trennlinie */}
      <div className="w-px h-5 bg-[rgba(255,255,255,0.08)] hidden sm:block" />

      {/* Status-Filter */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-white/40 text-xs font-medium uppercase tracking-widest mr-1">
          Status:
        </span>
        {statusOptionen.map((option) => {
          const istAktiv = filter.status === option.wert;
          return (
            <button
              key={option.wert}
              onClick={() => onFilterAenderung({ status: option.wert })}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium',
                'border transition-all duration-200',
                'cursor-pointer select-none',
                istAktiv
                  ? [
                      'bg-[rgba(43,51,106,0.45)] text-[#7b8fff]',
                      'border-[rgba(43,51,106,0.6)]',
                      'shadow-[0_0_12px_rgba(43,51,106,0.4)]',
                    ].join(' ')
                  : [
                      'bg-[rgba(255,255,255,0.04)] text-white/50',
                      'border-[rgba(255,255,255,0.07)]',
                      'hover:bg-[rgba(255,255,255,0.08)] hover:text-white/80',
                      'hover:border-[rgba(255,255,255,0.12)]',
                    ].join(' ')
              )}
              aria-pressed={istAktiv}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
