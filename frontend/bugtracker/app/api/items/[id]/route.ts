/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: API-Route fuer einzelne Items (PATCH Aktualisieren, DELETE Loeschen)
 */

import { NextRequest, NextResponse } from 'next/server';
import { itemAktualisieren, itemLoeschen } from '@/lib/database';
import type { UpdateItemDTO } from '@/types';

/**
 * PATCH /api/items/[id] - Item aktualisieren
 */
export async function PATCH(
  anfrage: NextRequest,
  { params }: { params: { id: string } }
): Promise<NextResponse> {
  try {
    const id = parseInt(params.id, 10);

    // ID validieren
    if (isNaN(id) || id <= 0) {
      return NextResponse.json(
        { erfolg: false, fehler: 'Ungültige ID' },
        { status: 400 }
      );
    }

    const koerper = await anfrage.json() as Partial<UpdateItemDTO>;

    // Mindestens ein Feld muss vorhanden sein
    if (Object.keys(koerper).length === 0) {
      return NextResponse.json(
        { erfolg: false, fehler: 'Keine Felder zum Aktualisieren angegeben' },
        { status: 400 }
      );
    }

    // Typ validieren wenn angegeben
    if (koerper.typ) {
      const erlaubteTypen = ['Bug', 'Idee'];
      if (!erlaubteTypen.includes(koerper.typ)) {
        return NextResponse.json(
          { erfolg: false, fehler: 'Ungültiger Typ' },
          { status: 400 }
        );
      }
    }

    // Status validieren wenn angegeben
    if (koerper.status) {
      const erlaubteStatus = ['Offen', 'In Bearbeitung', 'Erledigt', 'Abgelehnt'];
      if (!erlaubteStatus.includes(koerper.status)) {
        return NextResponse.json(
          { erfolg: false, fehler: 'Ungültiger Status' },
          { status: 400 }
        );
      }
    }

    const aktualisiertesItem = itemAktualisieren(id, koerper);

    if (!aktualisiertesItem) {
      return NextResponse.json(
        { erfolg: false, fehler: 'Item nicht gefunden' },
        { status: 404 }
      );
    }

    return NextResponse.json({ erfolg: true, daten: aktualisiertesItem });
  } catch (fehler) {
    console.error('Fehler beim Aktualisieren des Items:', fehler);
    return NextResponse.json(
      { erfolg: false, fehler: 'Item konnte nicht aktualisiert werden' },
      { status: 500 }
    );
  }
}

/**
 * DELETE /api/items/[id] - Item loeschen
 */
export async function DELETE(
  _anfrage: NextRequest,
  { params }: { params: { id: string } }
): Promise<NextResponse> {
  try {
    const id = parseInt(params.id, 10);

    // ID validieren
    if (isNaN(id) || id <= 0) {
      return NextResponse.json(
        { erfolg: false, fehler: 'Ungültige ID' },
        { status: 400 }
      );
    }

    const geloescht = itemLoeschen(id);

    if (!geloescht) {
      return NextResponse.json(
        { erfolg: false, fehler: 'Item nicht gefunden' },
        { status: 404 }
      );
    }

    return NextResponse.json({
      erfolg: true,
      nachricht: 'Item erfolgreich gelöscht',
    });
  } catch (fehler) {
    console.error('Fehler beim Loeschen des Items:', fehler);
    return NextResponse.json(
      { erfolg: false, fehler: 'Item konnte nicht gelöscht werden' },
      { status: 500 }
    );
  }
}
