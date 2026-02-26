/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: StatsBar-Komponente mit 5 Glas-Karten fuer Statistiken
 */

"use client"

import { Bug, Lightbulb, CheckCircle2, List, AlertCircle } from "lucide-react"
import { StatsData } from "@/types"

interface StatsBarProps {
  stats: StatsData
}

// Konfiguration fuer jede Statistik-Karte
interface StatKarteConfig {
  label: string
  wert: number
  icon: React.ReactNode
  farbe: string
  glowFarbe: string
  bg: string
}

/**
 * Zeigt eine Statistik-Leiste mit 5 Glas-Karten: Gesamt, Bugs, Ideen, Offen, Erledigt.
 */
export default function StatsBar({ stats }: StatsBarProps) {
  const karten: StatKarteConfig[] = [
    {
      label: "Gesamt",
      wert: stats.gesamt,
      icon: <List size={18} strokeWidth={1.8} />,
      farbe: "rgba(255, 255, 255, 0.75)",
      glowFarbe: "rgba(255, 255, 255, 0.15)",
      bg: "rgba(255, 255, 255, 0.07)",
    },
    {
      label: "Bugs",
      wert: stats.bugs,
      icon: <Bug size={18} strokeWidth={1.8} />,
      farbe: "#ff4d5f",
      glowFarbe: "rgba(135, 0, 16, 0.4)",
      bg: "rgba(135, 0, 16, 0.12)",
    },
    {
      label: "Ideen",
      wert: stats.ideen,
      icon: <Lightbulb size={18} strokeWidth={1.8} />,
      farbe: "#22d3ee",
      glowFarbe: "rgba(6, 182, 212, 0.3)",
      bg: "rgba(6, 182, 212, 0.08)",
    },
    {
      label: "Offen",
      wert: stats.offen,
      icon: <AlertCircle size={18} strokeWidth={1.8} />,
      farbe: "#9a9a87",
      glowFarbe: "rgba(124, 124, 107, 0.3)",
      bg: "rgba(124, 124, 107, 0.08)",
    },
    {
      label: "Erledigt",
      wert: stats.erledigt,
      icon: <CheckCircle2 size={18} strokeWidth={1.8} />,
      farbe: "#4ade80",
      glowFarbe: "rgba(22, 163, 74, 0.3)",
      bg: "rgba(22, 163, 74, 0.08)",
    },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
      {karten.map((karte) => (
        <div
          key={karte.label}
          className="glass-panel rounded-2xl p-4 flex items-center gap-3 transition-all duration-300 hover:scale-[1.02] cursor-default group"
          style={{
            background: karte.bg,
          }}
        >
          {/* Icon */}
          <div
            className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300 group-hover:scale-110"
            style={{
              background: `${karte.glowFarbe}`,
              color: karte.farbe,
            }}
          >
            {karte.icon}
          </div>

          {/* Zahlen und Label */}
          <div>
            <div
              className="text-2xl font-bold leading-none mb-0.5"
              style={{ color: karte.farbe }}
            >
              {karte.wert}
            </div>
            <div className="text-xs font-medium" style={{ color: "rgba(255,255,255,0.45)" }}>
              {karte.label}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
