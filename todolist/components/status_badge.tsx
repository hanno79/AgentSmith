/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: StatusBadge-Komponente mit Inline-Dropdown fuer Status-Aenderungen
 */

"use client"

import { useState, useRef, useEffect } from "react"
import { ChevronDown } from "lucide-react"
import { TodoStatus } from "@/types"

// Status-Konfiguration mit Farben
const STATUS_CONFIG: Record<TodoStatus, { label: string; bg: string; border: string; color: string }> = {
  offen: {
    label: "Offen",
    bg: "rgba(124, 124, 107, 0.2)",
    border: "rgba(124, 124, 107, 0.5)",
    color: "#9a9a87",
  },
  in_bearbeitung: {
    label: "In Bearbeitung",
    bg: "rgba(43, 51, 106, 0.3)",
    border: "rgba(61, 74, 150, 0.6)",
    color: "#818cf8",
  },
  erledigt: {
    label: "Erledigt",
    bg: "rgba(22, 163, 74, 0.2)",
    border: "rgba(22, 163, 74, 0.5)",
    color: "#4ade80",
  },
  verworfen: {
    label: "Verworfen",
    bg: "rgba(135, 0, 16, 0.2)",
    border: "rgba(135, 0, 16, 0.45)",
    color: "#f87171",
  },
}

// Alle moeglichen Status-Werte fuer das Dropdown
const ALLE_STATUS: TodoStatus[] = ["offen", "in_bearbeitung", "erledigt", "verworfen"]

interface StatusBadgeProps {
  status: TodoStatus
  onStatusChange: (neuerStatus: TodoStatus) => void
  disabled?: boolean
}

/**
 * Klickbares Status-Badge mit Inline-Dropdown fuer direkte Status-Aenderungen in der Tabelle.
 */
export default function StatusBadge({ status, onStatusChange, disabled = false }: StatusBadgeProps) {
  const [offen, setOffen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const config = STATUS_CONFIG[status]

  // Dropdown schliessen bei Klick ausserhalb
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOffen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  // Status-Aenderung verarbeiten
  const handleStatusWaehlen = (neuerStatus: TodoStatus) => {
    if (neuerStatus !== status) {
      onStatusChange(neuerStatus)
    }
    setOffen(false)
  }

  return (
    <div ref={ref} className="relative inline-block">
      {/* Badge-Button */}
      <button
        onClick={() => !disabled && setOffen(!offen)}
        disabled={disabled}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold transition-all duration-200"
        style={{
          background: config.bg,
          border: `1px solid ${config.border}`,
          color: config.color,
          cursor: disabled ? "default" : "pointer",
        }}
      >
        {config.label}
        {!disabled && (
          <ChevronDown
            size={10}
            strokeWidth={2.5}
            className={`transition-transform duration-200 ${offen ? "rotate-180" : ""}`}
          />
        )}
      </button>

      {/* Dropdown-Menu */}
      {offen && (
        <div
          className="absolute top-full mt-1.5 left-0 z-50 rounded-xl overflow-hidden min-w-[140px] fade-in"
          style={{
            background: "rgba(8, 11, 20, 0.97)",
            border: "1px solid rgba(255, 255, 255, 0.12)",
            boxShadow: "0 12px 40px rgba(0, 0, 0, 0.7)",
            backdropFilter: "blur(20px)",
          }}
        >
          {ALLE_STATUS.map((s) => {
            const cfg = STATUS_CONFIG[s]
            return (
              <button
                key={s}
                onClick={() => handleStatusWaehlen(s)}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-all duration-150 hover:bg-white/5"
              >
                {/* Farbiger Punkt als Indikator */}
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ background: cfg.color }}
                />
                <span style={{ color: s === status ? cfg.color : "rgba(255,255,255,0.75)" }}>
                  {cfg.label}
                </span>
                {s === status && (
                  <span className="ml-auto text-xs" style={{ color: cfg.color }}>
                    ✓
                  </span>
                )}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
