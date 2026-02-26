/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Bestaeligungs-Dialog fuer das Loeschen von BugTracker-Eintraegen
 */

'use client';

import React, { useState } from 'react';
import * as AlertDialogPrimitive from '@radix-ui/react-alert-dialog';
import { AlertTriangle, Trash2 } from 'lucide-react';
import { Button } from './ui/button';
import { cn } from '@/lib/utils';
import type { TrackerItem } from '@/types';

// Props-Interface
interface DeleteDialogProps {
  item: TrackerItem | null;
  offen: boolean;
  onSchliessen: () => void;
  onBestaetigen: (id: number) => Promise<void>;
}

/**
 * Bestaeltigungs-Dialog vor dem endgueltigen Loeschen eines Eintrags
 */
export function DeleteDialog({
  item,
  offen,
  onSchliessen,
  onBestaetigen,
}: DeleteDialogProps) {
  const [laedt, setLaedt] = useState(false);

  // Loeschen bestaetigen
  const handleBestaetigen = async () => {
    if (!item) return;

    setLaedt(true);
    try {
      await onBestaetigen(item.id);
      onSchliessen();
    } catch (fehler) {
      console.error('Fehler beim Loeschen:', fehler);
    } finally {
      setLaedt(false);
    }
  };

  if (!item) return null;

  return (
    <AlertDialogPrimitive.Root open={offen} onOpenChange={(istOffen) => !istOffen && onSchliessen()}>
      <AlertDialogPrimitive.Portal>
        {/* Overlay */}
        <AlertDialogPrimitive.Overlay className="fixed inset-0 bg-black/75 backdrop-blur-sm z-40 animate-fadeIn" />

        {/* Dialog-Box */}
        <AlertDialogPrimitive.Content
          className={cn(
            'fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50',
            'w-full max-w-sm mx-auto px-4',
            'animate-slideUp'
          )}
        >
          <div className={cn(
            'rounded-2xl p-6',
            'bg-[rgba(14,16,30,0.95)] backdrop-blur-2xl',
            'border border-[rgba(135,0,16,0.25)]',
            'shadow-[0_24px_80px_rgba(0,0,0,0.6),0_0_40px_rgba(135,0,16,0.15)]'
          )}>
            {/* Warn-Icon */}
            <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-[rgba(135,0,16,0.15)] border border-[rgba(135,0,16,0.3)] mx-auto mb-5">
              <AlertTriangle className="w-7 h-7 text-[#ff4d6d]" aria-hidden="true" />
            </div>

            {/* Titel */}
            <AlertDialogPrimitive.Title className="text-lg font-semibold text-white text-center mb-2">
              Eintrag loeschen?
            </AlertDialogPrimitive.Title>

            {/* Beschreibung */}
            <AlertDialogPrimitive.Description className="text-white/50 text-sm text-center mb-6">
              Der Eintrag{' '}
              <span className="text-white/80 font-medium">
                &quot;{item.name}&quot;
              </span>{' '}
              wird unwiderruflich geloescht. Diese Aktion kann nicht rueckgaengig gemacht werden.
            </AlertDialogPrimitive.Description>

            {/* Aktions-Buttons */}
            <div className="flex gap-3">
              <AlertDialogPrimitive.Cancel asChild>
                <Button
                  variante="glas"
                  groesse="mittel"
                  className="flex-1"
                  onClick={onSchliessen}
                  disabled={laedt}
                >
                  Abbrechen
                </Button>
              </AlertDialogPrimitive.Cancel>

              <AlertDialogPrimitive.Action asChild>
                <Button
                  variante="gefahr"
                  groesse="mittel"
                  className="flex-1"
                  onClick={handleBestaetigen}
                  loading={laedt}
                >
                  <Trash2 className="w-4 h-4" aria-hidden="true" />
                  Loeschen
                </Button>
              </AlertDialogPrimitive.Action>
            </div>
          </div>
        </AlertDialogPrimitive.Content>
      </AlertDialogPrimitive.Portal>
    </AlertDialogPrimitive.Root>
  );
}
