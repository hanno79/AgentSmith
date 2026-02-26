/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: API-Route fuer einzelne Items (PUT: Aktualisieren, DELETE: Loeschen)
 */

import { NextRequest, NextResponse } from 'next/server'
import { getDb } from '@/lib/db'
import { UpdateItemInput, TodoItem } from '@/types'

type RouteParams = { params: { id: string } }

/**
 * PUT /api/items/[id]
 * Aktualisiert ein Item. Partial-Update moeglich (nur geaenderte Felder uebergeben).
 */
export async function PUT(request: NextRequest, { params }: RouteParams): Promise<NextResponse> {
  try {
    const id = parseInt(params.id)
    if (isNaN(id)) {
      return NextResponse.json({ error: 'Ungueltige ID' }, { status: 400 })
    }

    const body: UpdateItemInput = await request.json()
    const db = getDb()

    // Pruefen ob Item existiert
    const vorhandenesItem = db.prepare('SELECT * FROM items WHERE id = ?').get(id) as TodoItem | undefined
    if (!vorhandenesItem) {
      return NextResponse.json({ error: 'Item nicht gefunden' }, { status: 404 })
    }

    // Nur uebergebene Felder aktualisieren (partial update)
    const aktualisierteWerte: UpdateItemInput = {}

    if (body.name !== undefined) {
      if (body.name.trim() === '') {
        return NextResponse.json({ error: 'Name darf nicht leer sein' }, { status: 400 })
      }
      aktualisierteWerte.name = body.name.trim()
    }

    if (body.beschreibung !== undefined) {
      aktualisierteWerte.beschreibung = body.beschreibung.trim()
    }

    if (body.typ !== undefined) {
      if (!['bug', 'idee'].includes(body.typ)) {
        return NextResponse.json({ error: 'Unguelltiger Typ-Wert' }, { status: 400 })
      }
      aktualisierteWerte.typ = body.typ
    }

    if (body.status !== undefined) {
      const erlaubteStatus = ['offen', 'in_bearbeitung', 'erledigt', 'verworfen']
      if (!erlaubteStatus.includes(body.status)) {
        return NextResponse.json({ error: 'Unguelltiger Status-Wert' }, { status: 400 })
      }
      aktualisierteWerte.status = body.status
    }

    // Dynamisches UPDATE-Statement aufbauen
    const felder = Object.keys(aktualisierteWerte)
    if (felder.length === 0) {
      return NextResponse.json({ error: 'Keine Felder zum Aktualisieren angegeben' }, { status: 400 })
    }

    const setClause = felder.map((f) => `${f} = @${f}`).join(', ')
    const stmt = db.prepare(`UPDATE items SET ${setClause} WHERE id = @id`)
    stmt.run({ ...aktualisierteWerte, id })

    // Aktualisiertes Item zurueckgeben
    const aktualisiertesItem = db.prepare('SELECT * FROM items WHERE id = ?').get(id) as TodoItem
    return NextResponse.json({ data: aktualisiertesItem })
  } catch (fehler) {
    console.error('[API PUT /api/items/[id]] Fehler:', fehler)
    return NextResponse.json(
      { error: 'Fehler beim Aktualisieren des Items' },
      { status: 500 }
    )
  }
}

/**
 * DELETE /api/items/[id]
 * Loescht ein Item anhand der ID.
 */
export async function DELETE(_request: NextRequest, { params }: RouteParams): Promise<NextResponse> {
  try {
    const id = parseInt(params.id)
    if (isNaN(id)) {
      return NextResponse.json({ error: 'Ungueltige ID' }, { status: 400 })
    }

    const db = getDb()

    // Pruefen ob Item existiert
    const vorhandenesItem = db.prepare('SELECT * FROM items WHERE id = ?').get(id)
    if (!vorhandenesItem) {
      return NextResponse.json({ error: 'Item nicht gefunden' }, { status: 404 })
    }

    db.prepare('DELETE FROM items WHERE id = ?').run(id)

    return NextResponse.json({ message: 'Item erfolgreich geloescht' })
  } catch (fehler) {
    console.error('[API DELETE /api/items/[id]] Fehler:', fehler)
    return NextResponse.json(
      { error: 'Fehler beim Loeschen des Items' },
      { status: 500 }
    )
  }
}
