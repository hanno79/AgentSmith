/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: TypeScript-Interfaces fuer die TodoList-WebApp
 */

// Moegl. Typen fuer ein Todo-Item
export type TodoTyp = 'bug' | 'idee'

// Moegl. Status-Werte fuer ein Todo-Item
export type TodoStatus = 'offen' | 'in_bearbeitung' | 'erledigt' | 'verworfen'

// Hauptinterface fuer ein Todo-Item (entspricht Datenbankzeile)
export interface TodoItem {
  id: number
  nr: number
  name: string
  beschreibung: string
  typ: TodoTyp
  status: TodoStatus
  created_at: string
  updated_at: string
}

// Eingabe-Interface fuer das Erstellen eines neuen Items
export interface CreateItemInput {
  name: string
  beschreibung: string
  typ: TodoTyp
  status: TodoStatus
}

// Eingabe-Interface fuer das Aktualisieren eines Items (alle Felder optional)
export interface UpdateItemInput {
  name?: string
  beschreibung?: string
  typ?: TodoTyp
  status?: TodoStatus
}

// Interface fuer API-Antworten
export interface ApiResponse<T> {
  data?: T
  error?: string
  message?: string
}

// Interface fuer Filter-Zustand in der UI
export interface FilterState {
  suche: string
  typ: 'alle' | TodoTyp
  status: 'alle' | TodoStatus
}

// Interface fuer Statistiken
export interface StatsData {
  gesamt: number
  bugs: number
  ideen: number
  offen: number
  erledigt: number
}
