/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: API-Route fuer alle Items (GET Liste, POST Erstellen)
 */

import { NextRequest, NextResponse } from 'next/server';
import { alleItemsAbrufen, itemErstellen } from '@/lib/database';
import type { CreateItemDTO } from '@/types';

/**
 * GET /api/items - Alle Items abrufen
 */
export async function GET(): Promise<NextResponse> {
  try {
    const items = alleItemsAbrufen();
    return NextResponse.json({ erfolg: true, daten: items });
  } catch (fehler) {
    console.error('Fehler beim Abrufen der Items:', fehler);
    return NextResponse.json(
      { erfolg: false, fehler: 'Items konnten nicht abgerufen werden' },
      { status: 500 }
    );
  }
}

/**
 * POST /api/items - Neues Item erstellen
 */
export async function POST(anfrage: NextRequest): Promise<NextResponse> {
  try {
    const koerper = await anfrage.json() as Partial<CreateItemDTO>;

    // Pflichtfelder validieren
    if (!koerper.name || koerper.name.trim() === '') {
      return NextResponse.json(
        { erfolg: false, fehler: 'Name ist ein Pflichtfeld' },
        { status: 400 }
      );
    }

    // Typ validieren
    const erlaubteTypen = ['Bug', 'Idee'];
    if (!koerper.typ || !erlaubteTypen.includes(koerper.typ)) {
      return NextResponse.json(
        { erfolg: false, fehler: 'Ungültiger Typ (Bug oder Idee erlaubt)' },
        { status: 400 }
      );
    }

    // Status validieren
    const erlaubteStatus = ['Offen', 'In Bearbeitung', 'Erledigt', 'Abgelehnt'];
    if (!koerper.status || !erlaubteStatus.includes(koerper.status)) {
      return NextResponse.json(
        { erfolg: false, fehler: 'Ungültiger Status' },
        { status: 400 }
      );
    }

    const neuesItem = itemErstellen({
      name: koerper.name.trim(),
      beschreibung: (koerper.beschreibung || '').trim(),
      typ: koerper.typ,
      status: koerper.status,
    });

    return NextResponse.json(
      { erfolg: true, daten: neuesItem },
      { status: 201 }
    );
  } catch (fehler) {
    console.error('Fehler beim Erstellen des Items:', fehler);
    return NextResponse.json(
      { erfolg: false, fehler: 'Item konnte nicht erstellt werden' },
      { status: 500 }
    );
  }
}
