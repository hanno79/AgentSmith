/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: FilterBar-Komponente fuer Suche, Typ- und Status-Filter
 */

"use client"

import { Search, X, RefreshCw } from "lucide-react"
import { FilterState, TodoTyp, TodoStatus } from "@/types"

interface FilterBarProps {
  filter: FilterState
  onFilterChange: (neuerFilter: FilterState) => void
}

// Typ-Filter-Optionen
const TYP_OPTIONEN: { wert: "alle" | TodoTyp; label: string }[] = [
  { wert: "alle", label: "Alle" },
  { wert: "bug", label: "Bug" },
  { wert: "idee", label: "Idee" },
]

// Status-Filter-Optionen
const STATUS_OPTIONEN: { wert: "alle" | TodoStatus; label: string }[] = [
  { wert: "alle", label: "Alle" },
  { wert: "offen", label: "Offen" },
  { wert: "in_bearbeitung", label: "In Bearbeitung" },
  { wert: "erledigt", label: "Erledigt" },
  { wert: "verworfen", label: "Verworfen" },
]

/**
 * Filter-Leiste mit Suchfeld, Typ- und Status-Toggles.
 */
export default function FilterBar({ filter, onFilterChange }: FilterBarProps) {
  // Suche aktualisieren
  const handleSuche = (wert: string) => {
    onFilterChange({ ...filter, suche: wert })
  }

  // Typ-Filter wechseln
  const handleTyp = (typ: "alle" | TodoTyp) => {
    onFilterChange({ ...filter, typ })
  }

  // Status-Filter wechseln
  const handleStatus = (status: "alle" | TodoStatus) => {
    onFilterChange({ ...filter, status })
  }

  // Alle Filter zuruecksetzen
  const handleReset = () => {
    onFilterChange({ suche: "", typ: "alle", status: "alle" })
  }

  // Pruefen ob Filter aktiv sind
  const filterAktiv = filter.suche !== "" || filter.typ !== "alle" || filter.status !== "alle"

  return (
    <div
      className="glass-panel rounded-2xl p-4 mb-4 flex flex-col gap-3"
    >
      {/* Erste Zeile: Suchfeld + Reset */}
      <div className="flex items-center gap-3">
        {/* Suchfeld */}
        <div className="relative flex-1">
          <Search
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
            style={{ color: "rgba(255,255,255,0.35)" }}
          />
          <input
            type="text"
            placeholder="Nach Name oder Beschreibung suchen..."
            value={filter.suche}
            onChange={(e) => handleSuche(e.target.value)}
            className="glass-input w-full pl-9 pr-9 py-2.5 rounded-xl text-sm"
          />
          {/* Loeschen-Button */}
          {filter.suche && (
            <button
              onClick={() => handleSuche("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/70 transition-colors"
            >
              <X size={14} />
            </button>
          )}
        </div>

        {/* Reset-Button */}
        {filterAktiv && (
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 hover:bg-white/8"
            style={{
              border: "1px solid rgba(255,255,255,0.12)",
              color: "rgba(255,255,255,0.55)",
            }}
          >
            <RefreshCw size={13} />
            Reset
          </button>
        )}
      </div>

      {/* Zweite Zeile: Typ- und Status-Filter */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Typ-Filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium mr-1" style={{ color: "rgba(255,255,255,0.4)" }}>
            Typ:
          </span>
          {TYP_OPTIONEN.map((opt) => (
            <button
              key={opt.wert}
              onClick={() => handleTyp(opt.wert)}
              className="px-3 py-1 rounded-lg text-xs font-medium transition-all duration-200"
              style={
                filter.typ === opt.wert
                  ? {
                      background: "rgba(43, 51, 106, 0.6)",
                      border: "1px solid rgba(61, 74, 150, 0.7)",
                      color: "#a5b4fc",
                      boxShadow: "0 0 12px rgba(43, 51, 106, 0.4)",
                    }
                  : {
                      background: "rgba(255, 255, 255, 0.04)",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      color: "rgba(255, 255, 255, 0.5)",
                    }
              }
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Trennlinie */}
        <div
          className="hidden sm:block h-5 w-px"
          style={{ background: "rgba(255,255,255,0.1)" }}
        />

        {/* Status-Filter */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs font-medium mr-1" style={{ color: "rgba(255,255,255,0.4)" }}>
            Status:
          </span>
          {STATUS_OPTIONEN.map((opt) => (
            <button
              key={opt.wert}
              onClick={() => handleStatus(opt.wert)}
              className="px-3 py-1 rounded-lg text-xs font-medium transition-all duration-200"
              style={
                filter.status === opt.wert
                  ? {
                      background: "rgba(43, 51, 106, 0.6)",
                      border: "1px solid rgba(61, 74, 150, 0.7)",
                      color: "#a5b4fc",
                      boxShadow: "0 0 12px rgba(43, 51, 106, 0.4)",
                    }
                  : {
                      background: "rgba(255, 255, 255, 0.04)",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      color: "rgba(255, 255, 255, 0.5)",
                    }
              }
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
