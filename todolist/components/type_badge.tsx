/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: TypeBadge-Komponente fuer Bug- und Idee-Badges
 */

"use client"

import { Bug, Lightbulb } from "lucide-react"
import { TodoTyp } from "@/types"

interface TypeBadgeProps {
  typ: TodoTyp
}

/**
 * Zeigt ein farbiges Badge fuer den Typ eines Items (Bug oder Idee).
 */
export default function TypeBadge({ typ }: TypeBadgeProps) {
  // Bug: Rot mit Bug-Icon
  if (typ === "bug") {
    return (
      <span
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
        style={{
          background: "rgba(135, 0, 16, 0.25)",
          border: "1px solid rgba(135, 0, 16, 0.5)",
          color: "#ff4d5f",
        }}
      >
        <Bug size={11} strokeWidth={2.5} />
        Bug
      </span>
    )
  }

  // Idee: Cyan/Hellblau mit Gluehbirnen-Icon
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
      style={{
        background: "rgba(6, 182, 212, 0.2)",
        border: "1px solid rgba(6, 182, 212, 0.45)",
        color: "#22d3ee",
      }}
    >
      <Lightbulb size={11} strokeWidth={2.5} />
      Idee
    </span>
  )
}
