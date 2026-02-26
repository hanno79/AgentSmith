/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.1
 * Beschreibung: SQLite Datenbankschicht mit better-sqlite3, Singleton-Pattern und CRUD-Funktionen
 * AENDERUNG 25.02.2026: Datenbankpfad in data/ Unterordner verlegt, fs-Import fuer Verzeichnis-Erstellung
 */

import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';
import type { TrackerItem, CreateItemDTO, UpdateItemDTO } from '@/types';

// Singleton-Instanz der Datenbank
let db: Database.Database | null = null;

/**
 * Gibt die Singleton-Datenbankverbindung zurueck
 * Erstellt die Verbindung und Tabellen beim ersten Aufruf
 */
function getDatenbank(): Database.Database {
  if (!db) {
    // data/ Verzeichnis erstellen falls nicht vorhanden
    const dataVerzeichnis = path.join(process.cwd(), 'data');
    if (!fs.existsSync(dataVerzeichnis)) {
      fs.mkdirSync(dataVerzeichnis, { recursive: true });
    }

    // Datenbankdatei im data/ Unterordner
    const dbPfad = path.join(dataVerzeichnis, 'bugtracker.db');
    db = new Database(dbPfad);

    // WAL-Modus fuer bessere Lese-/Schreib-Performance aktivieren
    db.pragma('journal_mode = WAL');
    db.pragma('foreign_keys = ON');

    // Tabelle erstellen wenn nicht vorhanden
    db.exec(`
      CREATE TABLE IF NOT EXISTS tracker_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nr INTEGER,
        name TEXT NOT NULL,
        beschreibung TEXT NOT NULL DEFAULT '',
        typ TEXT NOT NULL CHECK(typ IN ('Bug', 'Idee')) DEFAULT 'Bug',
        status TEXT NOT NULL CHECK(status IN ('Offen', 'In Bearbeitung', 'Erledigt', 'Abgelehnt')) DEFAULT 'Offen',
        erstellt_am TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        aktualisiert_am TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
      )
    `);

    // Trigger fuer automatische nr = id nach Einfuegen
    db.exec(`
      CREATE TRIGGER IF NOT EXISTS setze_nr_nach_insert
      AFTER INSERT ON tracker_items
      BEGIN
        UPDATE tracker_items SET nr = NEW.id WHERE id = NEW.id;
      END
    `);

    // Trigger fuer automatische Aktualisierung von aktualisiert_am
    db.exec(`
      CREATE TRIGGER IF NOT EXISTS aktualisiere_zeitstempel
      AFTER UPDATE ON tracker_items
      BEGIN
        UPDATE tracker_items
        SET aktualisiert_am = datetime('now', 'localtime')
        WHERE id = NEW.id;
      END
    `);
  }
  return db;
}

/**
 * Alle Items aus der Datenbank abrufen (nach ID absteigend sortiert)
 */
export function alleItemsAbrufen(): TrackerItem[] {
  const datenbank = getDatenbank();
  const aussage = datenbank.prepare(
    'SELECT * FROM tracker_items ORDER BY id DESC'
  );
  return aussage.all() as TrackerItem[];
}

/**
 * Neues Item in der Datenbank erstellen
 */
export function itemErstellen(daten: CreateItemDTO): TrackerItem {
  const datenbank = getDatenbank();
  const aussage = datenbank.prepare(`
    INSERT INTO tracker_items (name, beschreibung, typ, status)
    VALUES (@name, @beschreibung, @typ, @status)
  `);

  const ergebnis = aussage.run({
    name: daten.name,
    beschreibung: daten.beschreibung || '',
    typ: daten.typ,
    status: daten.status || 'Offen',
  });

  const neuesItem = datenbank
    .prepare('SELECT * FROM tracker_items WHERE id = ?')
    .get(ergebnis.lastInsertRowid) as TrackerItem;

  return neuesItem;
}

/**
 * Bestehendes Item in der Datenbank aktualisieren
 */
export function itemAktualisieren(
  id: number,
  daten: UpdateItemDTO
): TrackerItem | null {
  const datenbank = getDatenbank();

  // Pruefen ob Item existiert
  const vorhandenes = datenbank
    .prepare('SELECT * FROM tracker_items WHERE id = ?')
    .get(id) as TrackerItem | undefined;

  if (!vorhandenes) return null;

  // Nur vorhandene Felder aktualisieren
  const felder: string[] = [];
  const werte: Record<string, unknown> = { id };

  if (daten.name !== undefined) {
    felder.push('name = @name');
    werte.name = daten.name;
  }
  if (daten.beschreibung !== undefined) {
    felder.push('beschreibung = @beschreibung');
    werte.beschreibung = daten.beschreibung;
  }
  if (daten.typ !== undefined) {
    felder.push('typ = @typ');
    werte.typ = daten.typ;
  }
  if (daten.status !== undefined) {
    felder.push('status = @status');
    werte.status = daten.status;
  }

  if (felder.length === 0) {
    // Keine Felder zum Aktualisieren - vorhandenes Item zurueckgeben
    return vorhandenes;
  }

  const aussage = datenbank.prepare(
    `UPDATE tracker_items SET ${felder.join(', ')} WHERE id = @id`
  );
  aussage.run(werte);

  return datenbank
    .prepare('SELECT * FROM tracker_items WHERE id = ?')
    .get(id) as TrackerItem | null;
}

/**
 * Item aus der Datenbank loeschen
 */
export function itemLoeschen(id: number): boolean {
  const datenbank = getDatenbank();
  const aussage = datenbank.prepare(
    'DELETE FROM tracker_items WHERE id = ?'
  );
  const ergebnis = aussage.run(id);
  return ergebnis.changes > 0;
}
