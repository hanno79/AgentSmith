/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Hauptseite des BugTrackers mit State-Management und CRUD-Operationen
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Plus } from 'lucide-react';
import { Header } from '@/components/Header';
import { StatsKarten } from '@/components/StatsKarten';
import { FilterLeiste } from '@/components/FilterLeiste';
import { ItemTabelle } from '@/components/ItemTabelle';
import { AddItemDialog } from '@/components/AddItemDialog';
import { EditItemDialog } from '@/components/EditItemDialog';
import { DeleteDialog } from '@/components/DeleteDialog';
import { Button } from '@/components/ui/button';
import type {
  TrackerItem,
  CreateItemDTO,
  UpdateItemDTO,
  FilterZustand,
  ItemStatus,
} from '@/types';

/**
 * Hauptseite des BugTrackers
 * Verwaltet den globalen Zustand und koordiniert alle Komponenten
 */
export default function Startseite() {
  // Datenzustand
  const [alleItems, setAlleItems] = useState<TrackerItem[]>([]);
  const [laedt, setLaedt] = useState(true);
  const [fehler, setFehler] = useState<string | null>(null);

  // Filter-Zustand
  const [filter, setFilter] = useState<FilterZustand>({
    typ: 'Alle',
    status: 'Alle',
  });

  // Dialog-Zustaende
  const [addDialogOffen, setAddDialogOffen] = useState(false);
  const [bearbeitenItem, setBearbeitenItem] = useState<TrackerItem | null>(null);
  const [loeschenItem, setLoeschenItem] = useState<TrackerItem | null>(null);

  /**
   * Alle Items von der API laden
   */
  const itemsLaden = useCallback(async () => {
    setLaedt(true);
    setFehler(null);
    try {
      const antwort = await fetch('/api/items');
      if (!antwort.ok) {
        throw new Error('Fehler beim Laden der Daten');
      }
      const daten = await antwort.json();
      setAlleItems(daten.daten || []);
    } catch (err) {
      setFehler('Daten konnten nicht geladen werden. Bitte Seite neu laden.');
      console.error('Fehler beim Laden der Items:', err);
    } finally {
      setLaedt(false);
    }
  }, []);

  // Items beim Start laden
  useEffect(() => {
    itemsLaden();
  }, [itemsLaden]);

  /**
   * Neues Item erstellen
   */
  const handleHinzufuegen = async (daten: CreateItemDTO) => {
    const antwort = await fetch('/api/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(daten),
    });

    if (!antwort.ok) {
      const fehlerDaten = await antwort.json();
      throw new Error(fehlerDaten.fehler || 'Fehler beim Erstellen');
    }

    const ergebnis = await antwort.json();
    // Neues Item am Anfang der Liste einfuegen
    setAlleItems((vorherig) => [ergebnis.daten, ...vorherig]);
  };

  /**
   * Item bearbeiten und speichern
   */
  const handleSpeichern = async (id: number, daten: UpdateItemDTO) => {
    const antwort = await fetch(`/api/items/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(daten),
    });

    if (!antwort.ok) {
      const fehlerDaten = await antwort.json();
      throw new Error(fehlerDaten.fehler || 'Fehler beim Aktualisieren');
    }

    const ergebnis = await antwort.json();
    // Item in der Liste aktualisieren
    setAlleItems((vorherig) =>
      vorherig.map((item) => (item.id === id ? ergebnis.daten : item))
    );
    setBearbeitenItem(null);
  };

  /**
   * Status direkt in der Tabelle aendern
   */
  const handleStatusAenderung = async (id: number, neuerStatus: ItemStatus) => {
    try {
      await handleSpeichern(id, { status: neuerStatus });
    } catch (err) {
      console.error('Fehler beim Aendern des Status:', err);
    }
  };

  /**
   * Item loeschen
   */
  const handleLoeschen = async (id: number) => {
    const antwort = await fetch(`/api/items/${id}`, {
      method: 'DELETE',
    });

    if (!antwort.ok) {
      const fehlerDaten = await antwort.json();
      throw new Error(fehlerDaten.fehler || 'Fehler beim Loeschen');
    }

    // Item aus der Liste entfernen
    setAlleItems((vorherig) => vorherig.filter((item) => item.id !== id));
    setLoeschenItem(null);
  };

  /**
   * Filter-Zustand aktualisieren
   */
  const handleFilterAenderung = (neuerFilter: Partial<FilterZustand>) => {
    setFilter((vorherig) => ({ ...vorherig, ...neuerFilter }));
  };

  /**
   * Items nach aktiven Filtern filtern
   */
  const gefilterteItems = alleItems.filter((item) => {
    // Typ-Filter anwenden
    if (filter.typ !== 'Alle' && item.typ !== filter.typ) return false;
    // Status-Filter anwenden
    if (filter.status !== 'Alle' && item.status !== filter.status) return false;
    return true;
  });

  return (
    <>
      {/* Hintergrund-Gradient (fixiert) */}
      <div className="hintergrund-gradient" aria-hidden="true" />

      {/* Hauptinhalt */}
      <main className="relative min-h-screen">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Header */}
          <Header />

          {/* Fehler-Anzeige */}
          {fehler && (
            <div className="mb-6 px-5 py-4 rounded-xl bg-[rgba(135,0,16,0.15)] border border-[rgba(135,0,16,0.3)] text-[#ff4d6d] text-sm animate-slideUp">
              {fehler}
              <button
                onClick={itemsLaden}
                className="ml-3 underline hover:no-underline"
              >
                Erneut versuchen
              </button>
            </div>
          )}

          {/* Statistik-Karten */}
          <StatsKarten items={alleItems} />

          {/* Filter-Leiste und Hinzufuegen-Button */}
          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center mb-6">
            <div className="flex-1 w-full">
              <FilterLeiste
                filter={filter}
                onFilterAenderung={handleFilterAenderung}
              />
            </div>
          </div>

          {/* Item-Tabelle */}
          <ItemTabelle
            items={gefilterteItems}
            onStatusAenderung={handleStatusAenderung}
            onBearbeiten={setBearbeitenItem}
            onLoeschen={setLoeschenItem}
            laedt={laedt}
          />
        </div>
      </main>

      {/* Schwebender Hinzufuegen-Button (FAB) */}
      <div className="fixed bottom-8 right-8 z-30">
        <Button
          variante="primaer"
          groesse="gross"
          onClick={() => setAddDialogOffen(true)}
          className="rounded-2xl shadow-[0_8px_32px_rgba(43,51,106,0.6)] hover:shadow-[0_12px_40px_rgba(43,51,106,0.8)] px-6"
          aria-label="Neuen Eintrag hinzufuegen"
        >
          <Plus className="w-5 h-5" aria-hidden="true" />
          Neuer Eintrag
        </Button>
      </div>

      {/* Dialoge */}
      <AddItemDialog
        offen={addDialogOffen}
        onSchliessen={() => setAddDialogOffen(false)}
        onHinzufuegen={handleHinzufuegen}
      />

      <EditItemDialog
        item={bearbeitenItem}
        offen={bearbeitenItem !== null}
        onSchliessen={() => setBearbeitenItem(null)}
        onSpeichern={handleSpeichern}
      />

      <DeleteDialog
        item={loeschenItem}
        offen={loeschenItem !== null}
        onSchliessen={() => setLoeschenItem(null)}
        onBestaetigen={handleLoeschen}
      />
    </>
  );
}
