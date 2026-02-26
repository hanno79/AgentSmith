/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Statistik-Karten mit Glassmorphismus-Design fuer den Ueberblick
 */

import React from 'react';
import { LayoutGrid, Bug, Lightbulb, CheckCircle2 } from 'lucide-react';
import type { TrackerItem } from '@/types';

// Props-Interface
interface StatsKartenProps {
  items: TrackerItem[];
}

/**
 * Zeigt 4 Statistik-Karten (Gesamt, Bugs, Ideen, Erledigt) mit Glassmorphismus
 */
export function StatsKarten({ items }: StatsKartenProps) {
  // Statistiken berechnen
  const gesamt = items.length;
  const bugs = items.filter((i) => i.typ === 'Bug').length;
  const ideen = items.filter((i) => i.typ === 'Idee').length;
  const erledigt = items.filter((i) => i.status === 'Erledigt').length;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {/* Gesamt-Karte */}
      <div className="glas-hover rounded-xl p-5 animate-slideUp">
        <div className="w-10 h-10 rounded-lg flex items-center justify-center mb-4 text-white/70 bg-[rgba(124,124,107,0.15)] shadow-[0_0_16px_rgba(124,124,107,0.3)]">
          <LayoutGrid className="w-5 h-5" aria-hidden="true" />
        </div>
        <div className="text-3xl font-bold tabular-nums mb-1 text-white/70">
          {gesamt}
        </div>
        <div className="text-white/45 text-xs font-medium uppercase tracking-widest">
          Gesamt
        </div>
      </div>

      {/* Bug-Karte */}
      <div className="glas-hover rounded-xl p-5 animate-slideUp" style={{ animationDelay: '0.07s', borderColor: 'rgba(135,0,16,0.3)' }}>
        <div className="w-10 h-10 rounded-lg flex items-center justify-center mb-4 text-[#ff4d6d] bg-[rgba(135,0,16,0.15)] shadow-[0_0_16px_rgba(135,0,16,0.4)]">
          <Bug className="w-5 h-5" aria-hidden="true" />
        </div>
        <div className="text-3xl font-bold tabular-nums mb-1 text-[#ff4d6d]">
          {bugs}
        </div>
        <div className="text-white/45 text-xs font-medium uppercase tracking-widest">
          Bugs
        </div>
      </div>

      {/* Ideen-Karte */}
      <div className="glas-hover rounded-xl p-5 animate-slideUp" style={{ animationDelay: '0.14s', borderColor: 'rgba(43,51,106,0.35)' }}>
        <div className="w-10 h-10 rounded-lg flex items-center justify-center mb-4 text-[#7b8fff] bg-[rgba(43,51,106,0.2)] shadow-[0_0_16px_rgba(43,51,106,0.5)]">
          <Lightbulb className="w-5 h-5" aria-hidden="true" />
        </div>
        <div className="text-3xl font-bold tabular-nums mb-1 text-[#7b8fff]">
          {ideen}
        </div>
        <div className="text-white/45 text-xs font-medium uppercase tracking-widest">
          Ideen
        </div>
      </div>

      {/* Erledigt-Karte */}
      <div className="glas-hover rounded-xl p-5 animate-slideUp" style={{ animationDelay: '0.21s', borderColor: 'rgba(22,163,74,0.25)' }}>
        <div className="w-10 h-10 rounded-lg flex items-center justify-center mb-4 text-[#4ade80] bg-[rgba(22,163,74,0.12)] shadow-[0_0_16px_rgba(22,163,74,0.35)]">
          <CheckCircle2 className="w-5 h-5" aria-hidden="true" />
        </div>
        <div className="text-3xl font-bold tabular-nums mb-1 text-[#4ade80]">
          {erledigt}
        </div>
        <div className="text-white/45 text-xs font-medium uppercase tracking-widest">
          Erledigt
        </div>
      </div>
    </div>
  );
}
