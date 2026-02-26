/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: DeleteConfirmModal-Komponente - Bestaetigung vor dem Loeschen
 */

"use client"

import { useState } from "react"
import { X, Trash2, AlertTriangle } from "lucide-react"
import { TodoItem } from "@/types"

interface DeleteConfirmModalProps {
  item: TodoItem | null
  onSchliessen: () => void
  onBestaetigen: (id: number) => Promise<void>
}

/**
 * Bestaetigungs-Dialog vor dem endgueltigen Loeschen eines Items.
 */
export default function DeleteConfirmModal({
  item,
  onSchliessen,
  onBestaetigen,
}: DeleteConfirmModalProps) {
  const [laden, setLaden] = useState(false)

  // Modal nicht rendern wenn kein Item ausgewaehlt
  if (!item) return null

  // Loeschen bestaetigen
  const handleBestaetigen = async () => {
    try {
      setLaden(true)
      await onBestaetigen(item.id)
      onSchliessen()
    } catch {
      // Fehler wird in der Eltern-Komponente behandelt
    } finally {
      setLaden(false)
    }
  }

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-40 transition-opacity duration-300"
        style={{ background: "rgba(0, 0, 0, 0.8)", backdropFilter: "blur(4px)" }}
        onClick={onSchliessen}
      />

      {/* Modal */}
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="w-full max-w-sm rounded-2xl overflow-hidden fade-in"
          style={{
            background: "rgba(8, 11, 20, 0.97)",
            border: "1px solid rgba(135, 0, 16, 0.3)",
            boxShadow: "0 20px 60px rgba(0, 0, 0, 0.8), 0 0 40px rgba(135, 0, 16, 0.15)",
            backdropFilter: "blur(32px)",
          }}
        >
          {/* Modal-Header */}
          <div
            className="flex items-center justify-between px-6 py-4"
            style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
          >
            <div className="flex items-center gap-3">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center"
                style={{ background: "rgba(135, 0, 16, 0.25)" }}
              >
                <Trash2 size={14} style={{ color: "#ff4d5f" }} />
              </div>
              <h2 className="text-base font-semibold" style={{ color: "rgba(255,255,255,0.9)" }}>
                Item loeschen
              </h2>
            </div>
            <button
              onClick={onSchliessen}
              className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors hover:bg-white/8"
              style={{ color: "rgba(255,255,255,0.4)" }}
            >
              <X size={16} />
            </button>
          </div>

          {/* Modal-Body */}
          <div className="p-6 flex flex-col gap-5">
            {/* Warnhinweis */}
            <div
              className="flex items-start gap-3 p-4 rounded-xl"
              style={{
                background: "rgba(135, 0, 16, 0.12)",
                border: "1px solid rgba(135, 0, 16, 0.25)",
              }}
            >
              <AlertTriangle
                size={18}
                className="flex-shrink-0 mt-0.5"
                style={{ color: "#ff4d5f" }}
              />
              <div>
                <p className="text-sm font-medium mb-1" style={{ color: "rgba(255,255,255,0.85)" }}>
                  Aktion kann nicht rueckgaengig gemacht werden!
                </p>
                <p className="text-xs" style={{ color: "rgba(255,255,255,0.45)" }}>
                  Das Item wird dauerhaft aus der Datenbank geloescht.
                </p>
              </div>
            </div>

            {/* Item-Details */}
            <div
              className="p-4 rounded-xl"
              style={{
                background: "rgba(255, 255, 255, 0.04)",
                border: "1px solid rgba(255, 255, 255, 0.08)",
              }}
            >
              <p className="text-xs mb-1" style={{ color: "rgba(255,255,255,0.35)" }}>
                #{item.nr} — {item.typ === "bug" ? "Bug" : "Idee"}
              </p>
              <p className="text-sm font-semibold" style={{ color: "rgba(255,255,255,0.85)" }}>
                {item.name}
              </p>
              {item.beschreibung && (
                <p className="text-xs mt-1 line-clamp-2" style={{ color: "rgba(255,255,255,0.4)" }}>
                  {item.beschreibung}
                </p>
              )}
            </div>

            {/* Buttons */}
            <div className="flex gap-3">
              <button
                onClick={onSchliessen}
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
                onClick={handleBestaetigen}
                disabled={laden}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 disabled:opacity-50"
                style={{
                  background: laden
                    ? "rgba(135, 0, 16, 0.2)"
                    : "rgba(135, 0, 16, 0.35)",
                  border: "1px solid rgba(135, 0, 16, 0.55)",
                  color: "#ff4d5f",
                  boxShadow: laden ? "none" : "0 0 12px rgba(135, 0, 16, 0.3)",
                }}
              >
                {laden ? "Wird geloescht..." : "Endgueltig loeschen"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
