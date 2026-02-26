/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: SQLite Datenbankverbindung und Initialisierung mit better-sqlite3
 */

import Database from 'better-sqlite3'
import path from 'path'
import fs from 'fs'

// Datenbank-Dateipfad (data/todos.db relativ zum Projektroot)
const DB_DIR = path.join(process.cwd(), 'data')
const DB_PATH = path.join(DB_DIR, 'todos.db')

// Datenbankverzeichnis erstellen falls nicht vorhanden
if (!fs.existsSync(DB_DIR)) {
  fs.mkdirSync(DB_DIR, { recursive: true })
}

// Singleton-Datenbankinstanz
let db: Database.Database | null = null

/**
 * Gibt die Datenbankverbindung zurueck (Singleton-Pattern).
 * Stellt sicher, dass die Tabelle und Trigger initialisiert sind.
 */
export function getDb(): Database.Database {
  if (!db) {
    // Neue Verbindung oeffnen
    db = new Database(DB_PATH)

    // WAL-Modus fuer bessere Performance aktivieren
    db.pragma('journal_mode = WAL')

    // Tabelle initialisieren
    initialisiereDatenbank(db)
  }
  return db
}

/**
 * Erstellt die Tabelle und den Trigger fuer auto-nr falls nicht vorhanden.
 */
function initialisiereDatenbank(database: Database.Database): void {
  // Items-Tabelle erstellen
  database.exec(`
    CREATE TABLE IF NOT EXISTS items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      nr INTEGER,
      name TEXT NOT NULL,
      beschreibung TEXT DEFAULT '',
      typ TEXT NOT NULL CHECK(typ IN ('bug', 'idee')),
      status TEXT NOT NULL DEFAULT 'offen' CHECK(status IN ('offen', 'in_bearbeitung', 'erledigt', 'verworfen')),
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
  `)

  // Trigger: nr wird automatisch auf id gesetzt nach dem Einfuegen
  database.exec(`
    CREATE TRIGGER IF NOT EXISTS set_nr_after_insert
    AFTER INSERT ON items
    BEGIN
      UPDATE items SET nr = NEW.id WHERE id = NEW.id;
    END
  `)

  // Trigger: updated_at automatisch aktualisieren bei jedem UPDATE
  database.exec(`
    CREATE TRIGGER IF NOT EXISTS update_timestamp
    AFTER UPDATE ON items
    BEGIN
      UPDATE items SET updated_at = datetime('now') WHERE id = NEW.id;
    END
  `)
}

/**
 * Schliesst die Datenbankverbindung (fuer Tests/Cleanup).
 */
export function closeDb(): void {
  if (db) {
    db.close()
    db = null
  }
}
