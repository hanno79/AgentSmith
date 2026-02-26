/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: EditItemModal-Komponente fuer das Bearbeiten vorhandener Todo-Items
 */

"use client"

import { useState, useEffect } from "react"
import { X, Pencil, Bug, Lightbulb } from "lucide-react"
import { TodoItem, UpdateItemInput, TodoTyp, TodoStatus } from "@/types"

interface EditItemModalProps {
  item: TodoItem | null
  onSchliessen: () => void
  onSpeichern: (id: number, input: UpdateItemInput) => Promise<void>
}

// Status-Optionen fuer das Select-Feld
const STATUS_OPTIONEN: { wert: TodoStatus; label: string }[] = [
  { wert: "offen", label: "Offen" },
  { wert: "in_bearbeitung", label: "In Bearbeitung" },
  { wert: "erledigt", label: "Erledigt" },
  { wert: "verworfen", label: "Verworfen" },
]

/**
 * Modal-Dialog zum Bearbeiten eines vorhandenen Todo-Items.
 * Vorhandene Werte werden vorbelegt.
 */
export default function EditItemModal({ item, onSchliessen, onSpeichern }: EditItemModalProps) {
  const [formDaten, setFormDaten] = useState<UpdateItemInput>({})
  const [fehler, setFehler] = useState<string | null>(null)
  const [laden, setLaden] = useState(false)

  // Formular mit bestehenden Werten vorbefuellen wenn Item sich aendert
  useEffect(() => {
    if (item) {
      setFormDaten({
        name: item.name,
        beschreibung: item.beschreibung,
        typ: item.typ,
        status: item.status,
      })
      setFehler(null)
    }
  }, [item])

  // Modal nicht rendern wenn kein Item ausgewaehlt
  if (!item) return null

  // Modal schliessen
  const handleSchliessen = () => {
    setFehler(null)
    setLaden(false)
    onSchliessen()
  }

  // Formular absenden
  const handleAbsenden = async (e: React.FormEvent) => {
    e.preventDefault()

    // Pflichtfeld-Validierung
    if (!formDaten.name?.trim()) {
      setFehler("Name ist ein Pflichtfeld.")
      return
    }

    try {
      setLaden(true)
      setFehler(null)
      await onSpeichern(item.id, formDaten)
      onSchliessen()
    } catch {
      setFehler("Fehler beim Speichern. Bitte versuche es erneut.")
    } finally {
      setLaden(false)
    }
  }

  // Typ umschalten
  const handleTypWaehlen = (typ: TodoTyp) => {
    setFormDaten((prev) => ({ ...prev, typ }))
  }

  const aktuellerTyp = formDaten.typ || item.typ

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-40 transition-opacity duration-300"
        style={{ background: "rgba(0, 0, 0, 0.75)", backdropFilter: "blur(4px)" }}
        onClick={handleSchliessen}
      />

      {/* Modal */}
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="w-full max-w-md rounded-2xl overflow-hidden fade-in"
          style={{
            background: "rgba(8, 11, 20, 0.96)",
            border: "1px solid rgba(255, 255, 255, 0.12)",
            boxShadow: "0 20px 60px rgba(0, 0, 0, 0.8), 0 0 40px rgba(43, 51, 106, 0.25)",
            backdropFilter: "blur(32px)",
          }}
        >
          {/* Modal-Header */}
          <div
            className="flex items-center justify-between px-6 py-4"
            style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}
          >
            <div className="flex items-center gap-3">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center"
                style={{ background: "rgba(43, 51, 106, 0.4)" }}
              >
                <Pencil size={14} style={{ color: "#a5b4fc" }} />
              </div>
              <div>
                <h2 className="text-base font-semibold" style={{ color: "rgba(255,255,255,0.9)" }}>
                  Item bearbeiten
                </h2>
                <p className="text-xs" style={{ color: "rgba(255,255,255,0.35)" }}>
                  #{item.nr} — {item.name}
                </p>
              </div>
            </div>
            <button
              onClick={handleSchliessen}
              className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors hover:bg-white/8"
              style={{ color: "rgba(255,255,255,0.4)" }}
            >
              <X size={16} />
            </button>
          </div>

          {/* Modal-Body */}
          <form onSubmit={handleAbsenden} className="p-6 flex flex-col gap-5">
            {/* Typ-Toggle */}
            <div>
              <label className="text-xs font-medium mb-2 block" style={{ color: "rgba(255,255,255,0.5)" }}>
                Typ
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => handleTypWaehlen("bug")}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium transition-all duration-200"
                  style={
                    aktuellerTyp === "bug"
                      ? {
                          background: "rgba(135, 0, 16, 0.3)",
                          border: "1px solid rgba(135, 0, 16, 0.6)",
                          color: "#ff4d5f",
                          boxShadow: "0 0 15px rgba(135, 0, 16, 0.3)",
                        }
                      : {
                          background: "rgba(255, 255, 255, 0.04)",
                          border: "1px solid rgba(255, 255, 255, 0.1)",
                          color: "rgba(255,255,255,0.45)",
                        }
                  }
                >
                  <Bug size={14} />
                  Bug
                </button>
                <button
                  type="button"
                  onClick={() => handleTypWaehlen("idee")}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium transition-all duration-200"
                  style={
                    aktuellerTyp === "idee"
                      ? {
                          background: "rgba(6, 182, 212, 0.2)",
                          border: "1px solid rgba(6, 182, 212, 0.5)",
                          color: "#22d3ee",
                          boxShadow: "0 0 15px rgba(6, 182, 212, 0.2)",
                        }
                      : {
                          background: "rgba(255, 255, 255, 0.04)",
                          border: "1px solid rgba(255, 255, 255, 0.1)",
                          color: "rgba(255,255,255,0.45)",
                        }
                  }
                >
                  <Lightbulb size={14} />
                  Idee
                </button>
              </div>
            </div>

            {/* Name */}
            <div>
              <label className="text-xs font-medium mb-2 block" style={{ color: "rgba(255,255,255,0.5)" }}>
                Name <span style={{ color: "#ff4d5f" }}>*</span>
              </label>
              <input
                type="text"
                value={formDaten.name || ""}
                onChange={(e) => setFormDaten((prev) => ({ ...prev, name: e.target.value }))}
                placeholder="Kurzer, beschreibender Name..."
                className="glass-input w-full px-3 py-2.5 rounded-xl text-sm"
                maxLength={200}
              />
            </div>

            {/* Beschreibung */}
            <div>
              <label className="text-xs font-medium mb-2 block" style={{ color: "rgba(255,255,255,0.5)" }}>
                Beschreibung
              </label>
              <textarea
                value={formDaten.beschreibung || ""}
                onChange={(e) => setFormDaten((prev) => ({ ...prev, beschreibung: e.target.value }))}
                placeholder="Detaillierte Beschreibung (optional)..."
                className="glass-input w-full px-3 py-2.5 rounded-xl text-sm resize-none"
                rows={3}
                maxLength={1000}
              />
            </div>

            {/* Status */}
            <div>
              <label className="text-xs font-medium mb-2 block" style={{ color: "rgba(255,255,255,0.5)" }}>
                Status
              </label>
              <select
                value={formDaten.status || item.status}
                onChange={(e) =>
                  setFormDaten((prev) => ({ ...prev, status: e.target.value as TodoStatus }))
                }
                className="glass-input w-full px-3 py-2.5 rounded-xl text-sm"
                style={{ appearance: "none", cursor: "pointer" }}
              >
                {STATUS_OPTIONEN.map((opt) => (
                  <option key={opt.wert} value={opt.wert}
                    style={{ background: "#0d0f20", color: "#fff" }}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Fehlermeldung */}
            {fehler && (
              <div
                className="px-3 py-2.5 rounded-xl text-sm"
                style={{
                  background: "rgba(135, 0, 16, 0.2)",
                  border: "1px solid rgba(135, 0, 16, 0.4)",
                  color: "#ff4d5f",
                }}
              >
                {fehler}
              </div>
            )}

            {/* Buttons */}
            <div className="flex gap-3 pt-1">
              <button
                type="button"
                onClick={handleSchliessen}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-all duration-200"
                style={{
                  background: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  color: "rgba(255, 255, 255, 0.6)",
                }}
              >
                Abbrechen
              </button>
              <button
                type="submit"
                disabled={laden}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 disabled:opacity-50"
                style={{
                  background: laden
                    ? "rgba(43, 51, 106, 0.3)"
                    : "rgba(43, 51, 106, 0.5)",
                  border: "1px solid rgba(61, 74, 150, 0.6)",
                  color: "#a5b4fc",
                  boxShadow: laden ? "none" : "0 0 15px rgba(43, 51, 106, 0.35)",
                }}
              >
                {laden ? "Wird gespeichert..." : "Aenderungen speichern"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  )
}
