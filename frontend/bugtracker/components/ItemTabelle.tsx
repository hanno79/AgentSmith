/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Haupttabelle fuer BugTracker-Items mit Glassmorphismus und Aktionen
 */

'use client';

import React from 'react';
import { Pencil, Trash2, Bug } from 'lucide-react';
import { StatusSelect } from './StatusSelect';
import { TypBadge } from './TypBadge';
import { Button } from './ui/button';
import { kuerzeText } from '@/lib/utils';
import type { TrackerItem, ItemStatus } from '@/types';

// Props-Interface
interface ItemTabelleProps {
  items: TrackerItem[];
  onStatusAenderung: (id: number, neuerStatus: ItemStatus) => void;
  onBearbeiten: (item: TrackerItem) => void;
  onLoeschen: (item: TrackerItem) => void;
  laedt?: boolean;
}

/**
 * Tabellen-Komponente fuer alle BugTracker-Items
 * Mit farbigem Akzent-Balken links, Typ-Badge, Inline-Status-Select und Aktionen
 */
export function ItemTabelle({
  items,
  onStatusAenderung,
  onBearbeiten,
  onLoeschen,
  laedt = false,
}: ItemTabelleProps) {
  return (
    <div className="glas rounded-2xl overflow-hidden animate-slideUp">
      {/* Tabellen-Wrapper mit Scroll */}
      <div className="overflow-x-auto">
        <table className="w-full" role="table" aria-label="BugTracker Eintraege">
          {/* Tabellen-Header */}
          <thead>
            <tr className="glas-stark border-b border-[rgba(255,255,255,0.06)]">
              <th className="px-4 py-4 text-left text-[10px] font-semibold text-white/35 uppercase tracking-widest w-16">
                NR
              </th>
              <th className="px-4 py-4 text-left text-[10px] font-semibold text-white/35 uppercase tracking-widest min-w-[160px]">
                Name
              </th>
              <th className="px-4 py-4 text-left text-[10px] font-semibold text-white/35 uppercase tracking-widest min-w-[240px]">
                Beschreibung
              </th>
              <th className="px-4 py-4 text-left text-[10px] font-semibold text-white/35 uppercase tracking-widest w-28">
                Typ
              </th>
              <th className="px-4 py-4 text-left text-[10px] font-semibold text-white/35 uppercase tracking-widest w-40">
                Status
              </th>
              <th className="px-4 py-4 text-right text-[10px] font-semibold text-white/35 uppercase tracking-widest w-24">
                Aktionen
              </th>
            </tr>
          </thead>

          {/* Tabellen-Inhalt */}
          <tbody>
            {/* Lade-Zustand */}
            {laedt && (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-2 border-[rgba(43,51,106,0.6)] border-t-[#7b8fff] rounded-full animate-spin" />
                    <span className="text-white/40 text-sm">Laden...</span>
                  </div>
                </td>
              </tr>
            )}

            {/* Leerer Zustand */}
            {!laedt && items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-16 text-center">
                  <div className="flex flex-col items-center gap-4">
                    <div className="w-16 h-16 rounded-2xl bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] flex items-center justify-center">
                      <Bug className="w-8 h-8 text-white/15" aria-hidden="true" />
                    </div>
                    <div>
                      <p className="text-white/40 font-medium mb-1">Keine Eintraege vorhanden</p>
                      <p className="text-white/25 text-sm">Erstelle deinen ersten Bug oder deine erste Idee</p>
                    </div>
                  </div>
                </td>
              </tr>
            )}

            {/* Daten-Zeilen */}
            {!laedt && items.map((item) => {
              const istBug = item.typ === 'Bug';
              return (
                <tr
                  key={item.id}
                  className="border-b border-[rgba(255,255,255,0.04)] last:border-0 group transition-all duration-200 hover:bg-[rgba(255,255,255,0.025)]"
                >
                  {/* Nummer mit farbigem Akzent-Balken */}
                  <td className="px-4 py-4 relative">
                    {/* Farbiger Akzent-Balken links */}
                    <div
                      className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full transition-all duration-200 group-hover:top-1 group-hover:bottom-1"
                      style={{
                        background: istBug
                          ? 'linear-gradient(180deg, #870010, #ff4d6d)'
                          : 'linear-gradient(180deg, #2b336a, #7b8fff)',
                        boxShadow: istBug
                          ? '0 0 8px rgba(135,0,16,0.6)'
                          : '0 0 8px rgba(43,51,106,0.6)',
                      }}
                      aria-hidden="true"
                    />
                    <span className="text-white/50 text-sm font-mono pl-3">
                      #{item.nr}
                    </span>
                  </td>

                  {/* Name */}
                  <td className="px-4 py-4">
                    <span className="text-white/85 text-sm font-medium">
                      {item.name}
                    </span>
                  </td>

                  {/* Beschreibung (gekuerzt) */}
                  <td className="px-4 py-4">
                    <span
                      className="text-white/45 text-sm"
                      title={item.beschreibung}
                    >
                      {item.beschreibung
                        ? kuerzeText(item.beschreibung, 70)
                        : <span className="text-white/20 italic">Keine Beschreibung</span>
                      }
                    </span>
                  </td>

                  {/* Typ-Badge */}
                  <td className="px-4 py-4">
                    <TypBadge typ={item.typ} />
                  </td>

                  {/* Status Inline-Select */}
                  <td className="px-4 py-4">
                    <StatusSelect
                      wert={item.status}
                      onAenderung={(neuerStatus) =>
                        onStatusAenderung(item.id, neuerStatus)
                      }
                    />
                  </td>

                  {/* Aktionen */}
                  <td className="px-4 py-4">
                    <div className="flex items-center justify-end gap-1.5">
                      {/* Bearbeiten-Button */}
                      <Button
                        variante="glas"
                        groesse="icon"
                        onClick={() => onBearbeiten(item)}
                        title="Eintrag bearbeiten"
                        aria-label={`${item.name} bearbeiten`}
                        className="opacity-0 group-hover:opacity-100 text-white/60 hover:text-white"
                      >
                        <Pencil className="w-3.5 h-3.5" aria-hidden="true" />
                      </Button>

                      {/* Loeschen-Button */}
                      <Button
                        variante="geist"
                        groesse="icon"
                        onClick={() => onLoeschen(item)}
                        title="Eintrag loeschen"
                        aria-label={`${item.name} loeschen`}
                        className="opacity-0 group-hover:opacity-100 text-white/40 hover:text-[#ff4d6d] hover:bg-[rgba(135,0,16,0.15)]"
                      >
                        <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Tabellen-Footer mit Anzahl */}
      {!laedt && items.length > 0 && (
        <div className="px-6 py-3 border-t border-[rgba(255,255,255,0.04)] flex items-center justify-between">
          <span className="text-white/30 text-xs">
            {items.length} {items.length === 1 ? 'Eintrag' : 'Eintraege'}
          </span>
        </div>
      )}
    </div>
  );
}
