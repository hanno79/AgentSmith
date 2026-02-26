/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.1
 * Beschreibung: TypeScript Interfaces und Typen fuer den BugTracker
 * AENDERUNG 25.02.2026: suche-Feld zu FilterZustand hinzugefuegt, nachricht zu ApiAntwort ergaenzt
 */

/** Typ-Enum: Bug oder Idee */
export type ItemTyp = 'Bug' | 'Idee';

/** Status-Enum: Moegliche Zustands-Werte eines Eintrags */
export type ItemStatus = 'Offen' | 'In Bearbeitung' | 'Erledigt' | 'Abgelehnt';

/** Haupt-Interface fuer einen BugTracker-Eintrag */
export interface TrackerItem {
  id: number;
  nr: number;
  name: string;
  beschreibung: string;
  typ: ItemTyp;
  status: ItemStatus;
  erstellt_am: string;
  aktualisiert_am: string;
}

/** DTO fuer das Erstellen eines neuen Eintrags */
export interface CreateItemDTO {
  name: string;
  beschreibung?: string;
  typ: ItemTyp;
  status?: ItemStatus;
}

/** DTO fuer das Aktualisieren eines bestehenden Eintrags */
export interface UpdateItemDTO {
  name?: string;
  beschreibung?: string;
  typ?: ItemTyp;
  status?: ItemStatus;
}

/** Filter-Zustand Interface mit Suchfeld */
export interface FilterZustand {
  typ: ItemTyp | 'Alle';
  status: ItemStatus | 'Alle';
  suche: string;
}

/** API-Antwort-Interface */
export interface ApiAntwort<T> {
  daten?: T;
  fehler?: string;
  erfolg: boolean;
  nachricht?: string;
}
