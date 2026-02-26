/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Dialog-Komponente zum Hinzufuegen neuer BugTracker-Eintraege
 */

'use client';

import React, { useState } from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import * as SelectPrimitive from '@radix-ui/react-select';
import { X, Plus, ChevronDown, Check } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { cn } from '@/lib/utils';
import type { CreateItemDTO, ItemTyp, ItemStatus } from '@/types';

// Props-Interface
interface AddItemDialogProps {
  offen: boolean;
  onSchliessen: () => void;
  onHinzufuegen: (daten: CreateItemDTO) => Promise<void>;
}

// Leerer Formular-Zustand
const LEERES_FORMULAR: CreateItemDTO = {
  name: '',
  beschreibung: '',
  typ: 'Bug',
  status: 'Offen',
};

/**
 * Dialog zum Hinzufuegen eines neuen BugTracker-Eintrags
 */
export function AddItemDialog({
  offen,
  onSchliessen,
  onHinzufuegen,
}: AddItemDialogProps) {
  // Formular-Zustand
  const [formDaten, setFormDaten] = useState<CreateItemDTO>(LEERES_FORMULAR);
  const [laedt, setLaedt] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);

  // Formular-Eingabe verarbeiten
  const handleEingabe = (feld: keyof CreateItemDTO, wert: string) => {
    setFormDaten((vorherig) => ({ ...vorherig, [feld]: wert }));
    if (fehler) setFehler(null);
  };

  // Formular absenden
  const handleAbsenden = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validierung
    if (!formDaten.name.trim()) {
      setFehler('Name ist ein Pflichtfeld');
      return;
    }

    setLaedt(true);
    setFehler(null);

    try {
      await onHinzufuegen(formDaten);
      // Formular zuruecksetzen nach Erfolg
      setFormDaten(LEERES_FORMULAR);
      onSchliessen();
    } catch (err) {
      setFehler('Eintrag konnte nicht erstellt werden');
      console.error('Fehler beim Hinzufuegen:', err);
    } finally {
      setLaedt(false);
    }
  };

  // Dialog schliessen und Formular zuruecksetzen
  const handleSchliessen = () => {
    setFormDaten(LEERES_FORMULAR);
    setFehler(null);
    onSchliessen();
  };

  return (
    <DialogPrimitive.Root open={offen} onOpenChange={(istOffen) => !istOffen && handleSchliessen()}>
      <DialogPrimitive.Portal>
        {/* Overlay */}
        <DialogPrimitive.Overlay className="fixed inset-0 bg-black/75 backdrop-blur-sm z-40 animate-fadeIn" />

        {/* Dialog-Box */}
        <DialogPrimitive.Content
          className={cn(
            'fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50',
            'w-full max-w-md mx-auto px-4',
            'animate-slideUp'
          )}
        >
          <div className={cn(
            'rounded-2xl p-6',
            'bg-[rgba(14,16,30,0.95)] backdrop-blur-2xl',
            'border border-[rgba(255,255,255,0.1)]',
            'shadow-[0_24px_80px_rgba(0,0,0,0.6)]'
          )}>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <DialogPrimitive.Title className="text-lg font-semibold text-white">
                Neuer Eintrag
              </DialogPrimitive.Title>
              <DialogPrimitive.Close asChild>
                <Button
                  variante="geist"
                  groesse="icon"
                  onClick={handleSchliessen}
                  aria-label="Dialog schliessen"
                >
                  <X className="w-4 h-4" aria-hidden="true" />
                </Button>
              </DialogPrimitive.Close>
            </div>

            {/* Fehler-Anzeige */}
            {fehler && (
              <div className="mb-4 px-4 py-3 rounded-lg bg-[rgba(135,0,16,0.2)] border border-[rgba(135,0,16,0.35)] text-[#ff4d6d] text-sm">
                {fehler}
              </div>
            )}

            {/* Formular */}
            <form onSubmit={handleAbsenden} className="space-y-4">
              {/* Name */}
              <div>
                <Label htmlFor="add-name">Name *</Label>
                <Input
                  id="add-name"
                  type="text"
                  placeholder="Titel des Eintrags..."
                  value={formDaten.name}
                  onChange={(e) => handleEingabe('name', e.target.value)}
                  required
                  autoFocus
                />
              </div>

              {/* Beschreibung */}
              <div>
                <Label htmlFor="add-beschreibung">Beschreibung</Label>
                <Textarea
                  id="add-beschreibung"
                  placeholder="Detaillierte Beschreibung..."
                  value={formDaten.beschreibung}
                  onChange={(e) => handleEingabe('beschreibung', e.target.value)}
                  rows={3}
                />
              </div>

              {/* Typ und Status nebeneinander */}
              <div className="grid grid-cols-2 gap-4">
                {/* Typ Select */}
                <div>
                  <Label htmlFor="add-typ">Typ</Label>
                  <SelectPrimitive.Root
                    value={formDaten.typ}
                    onValueChange={(wert) => handleEingabe('typ', wert)}
                  >
                    <SelectPrimitive.Trigger
                      id="add-typ"
                      className={cn(
                        'w-full flex items-center justify-between px-4 py-2.5 rounded-lg text-sm',
                        'bg-[rgba(255,255,255,0.05)] text-white/90',
                        'border border-[rgba(255,255,255,0.1)]',
                        'focus:outline-none focus:border-[rgba(43,51,106,0.8)]',
                        'transition-all duration-200 cursor-pointer'
                      )}
                    >
                      <SelectPrimitive.Value />
                      <ChevronDown className="w-4 h-4 text-white/40" aria-hidden="true" />
                    </SelectPrimitive.Trigger>
                    <SelectPrimitive.Portal>
                      <SelectPrimitive.Content
                        className="z-50 min-w-[120px] rounded-lg overflow-hidden bg-[#111320] border border-[rgba(255,255,255,0.1)] shadow-[0_16px_48px_rgba(0,0,0,0.5)]"
                        position="popper"
                        sideOffset={4}
                      >
                        <SelectPrimitive.Viewport className="p-1">
                          {(['Bug', 'Idee'] as ItemTyp[]).map((typ) => (
                            <SelectPrimitive.Item
                              key={typ}
                              value={typ}
                              className="flex items-center gap-2 px-3 py-2 rounded-md text-sm text-white/80 cursor-pointer outline-none data-[highlighted]:bg-[rgba(255,255,255,0.07)] transition-all"
                            >
                              <SelectPrimitive.ItemIndicator>
                                <Check className="w-3 h-3" aria-hidden="true" />
                              </SelectPrimitive.ItemIndicator>
                              <SelectPrimitive.ItemText>{typ}</SelectPrimitive.ItemText>
                            </SelectPrimitive.Item>
                          ))}
                        </SelectPrimitive.Viewport>
                      </SelectPrimitive.Content>
                    </SelectPrimitive.Portal>
                  </SelectPrimitive.Root>
                </div>

                {/* Status Select */}
                <div>
                  <Label htmlFor="add-status">Status</Label>
                  <SelectPrimitive.Root
                    value={formDaten.status}
                    onValueChange={(wert) => handleEingabe('status', wert)}
                  >
                    <SelectPrimitive.Trigger
                      id="add-status"
                      className={cn(
                        'w-full flex items-center justify-between px-4 py-2.5 rounded-lg text-sm',
                        'bg-[rgba(255,255,255,0.05)] text-white/90',
                        'border border-[rgba(255,255,255,0.1)]',
                        'focus:outline-none focus:border-[rgba(43,51,106,0.8)]',
                        'transition-all duration-200 cursor-pointer'
                      )}
                    >
                      <SelectPrimitive.Value />
                      <ChevronDown className="w-4 h-4 text-white/40" aria-hidden="true" />
                    </SelectPrimitive.Trigger>
                    <SelectPrimitive.Portal>
                      <SelectPrimitive.Content
                        className="z-50 min-w-[150px] rounded-lg overflow-hidden bg-[#111320] border border-[rgba(255,255,255,0.1)] shadow-[0_16px_48px_rgba(0,0,0,0.5)]"
                        position="popper"
                        sideOffset={4}
                      >
                        <SelectPrimitive.Viewport className="p-1">
                          {(['Offen', 'In Bearbeitung', 'Erledigt', 'Abgelehnt'] as ItemStatus[]).map((status) => (
                            <SelectPrimitive.Item
                              key={status}
                              value={status}
                              className="flex items-center gap-2 px-3 py-2 rounded-md text-sm text-white/80 cursor-pointer outline-none data-[highlighted]:bg-[rgba(255,255,255,0.07)] transition-all"
                            >
                              <SelectPrimitive.ItemIndicator>
                                <Check className="w-3 h-3" aria-hidden="true" />
                              </SelectPrimitive.ItemIndicator>
                              <SelectPrimitive.ItemText>{status}</SelectPrimitive.ItemText>
                            </SelectPrimitive.Item>
                          ))}
                        </SelectPrimitive.Viewport>
                      </SelectPrimitive.Content>
                    </SelectPrimitive.Portal>
                  </SelectPrimitive.Root>
                </div>
              </div>

              {/* Aktions-Buttons */}
              <div className="flex gap-3 pt-2">
                <Button
                  type="button"
                  variante="glas"
                  groesse="mittel"
                  className="flex-1"
                  onClick={handleSchliessen}
                  disabled={laedt}
                >
                  Abbrechen
                </Button>
                <Button
                  type="submit"
                  variante="primaer"
                  groesse="mittel"
                  className="flex-1"
                  loading={laedt}
                >
                  <Plus className="w-4 h-4" aria-hidden="true" />
                  Hinzufuegen
                </Button>
              </div>
            </form>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
