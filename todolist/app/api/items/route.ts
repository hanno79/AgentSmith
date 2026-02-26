/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: API-Route fuer alle Items (GET: Laden, POST: Erstellen)
 */

import { NextRequest, NextResponse } from 'next/server'
import { getDb } from '@/lib/db'
import { CreateItemInput, TodoItem } from '@/types'

/**
 * GET /api/items
 * Laedt alle Items aus der Datenbank, sortiert nach nr absteigend.
 */
export async function GET(): Promise<NextResponse> {
  try {
    const db = getDb()
    const items = db.prepare('SELECT * FROM items ORDER BY nr DESC').all() as TodoItem[]
    return NextResponse.json({ data: items })
  } catch (fehler) {
    console.error('[API GET /api/items] Fehler:', fehler)
    return NextResponse.json(
      { error: 'Fehler beim Laden der Items' },
      { status: 500 }
    )
  }
}

/**
 * POST /api/items
 * Erstellt ein neues Item in der Datenbank.
 * Erwartet: { name, beschreibung, typ, status }
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    const body: CreateItemInput = await request.json()

    // Pflichtfeld-Validierung
    if (!body.name || body.name.trim() === '') {
      return NextResponse.json(
        { error: 'Name ist ein Pflichtfeld' },
        { status: 400 }
      )
    }

    // Typ-Validierung
    if (!['bug', 'idee'].includes(body.typ)) {
      return NextResponse.json(
        { error: 'Typ muss "bug" oder "idee" sein' },
        { status: 400 }
      )
    }

    // Status-Validierung
    const erlaubteStatus = ['offen', 'in_bearbeitung', 'erledigt', 'verworfen']
    if (!erlaubteStatus.includes(body.status)) {
      return NextResponse.json(
        { error: 'Unguelltiger Status-Wert' },
        { status: 400 }
      )
    }

    const db = getDb()
    const stmt = db.prepare(`
      INSERT INTO items (name, beschreibung, typ, status)
      VALUES (@name, @beschreibung, @typ, @status)
    `)

    const result = stmt.run({
      name: body.name.trim(),
      beschreibung: body.beschreibung?.trim() ?? '',
      typ: body.typ,
      status: body.status,
    })

    // Neu erstelltes Item zurueckgeben
    const neuesItem = db.prepare('SELECT * FROM items WHERE id = ?').get(result.lastInsertRowid) as TodoItem

    return NextResponse.json({ data: neuesItem }, { status: 201 })
  } catch (fehler) {
    console.error('[API POST /api/items] Fehler:', fehler)
    return NextResponse.json(
      { error: 'Fehler beim Erstellen des Items' },
      { status: 500 }
    )
  }
}
