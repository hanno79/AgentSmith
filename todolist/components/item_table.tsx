/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: ItemTable-Komponente - Glas-Tabelle mit allen Todo-Items
 */

"use client"

import { useState } from "react"
import { Pencil, Trash2, PackageOpen } from "lucide-react"
import { TodoItem, TodoStatus } from "@/types"
import TypeBadge from "./type_badge"
import StatusBadge from "./status_badge"

interface ItemTableProps {
  items: TodoItem[]
  onEdit: (item: TodoItem) => void
  onDelete: (item: TodoItem) => void
  onStatusChange: (id: number, neuerStatus: TodoStatus) => void
  laden: boolean
}

/**
 * Zeigt alle Items in einer Glas-Tabelle mit Hover-Effekten und Aktionen.
 */
export default function ItemTable({
  items,
  onEdit,
  onDelete,
  onStatusChange,
  laden,
}: ItemTableProps) {
  const [tooltip, setTooltip] = useState<{ id: number; text: string } | null>(null)

  // Ladeanimation anzeigen
  if (laden) {
    return (
      <div className="glass-panel rounded-2xl overflow-hidden">
        <div className="p-8 flex flex-col items-center justify-center gap-4">
          {/* Skeleton-Loader */}
          {[1, 2, 3].map((i) => (
            <div key={i} className="w-full h-12 rounded-xl animate-pulse"
              style={{ background: "rgba(255,255,255,0.05)" }}
            />
          ))}
        </div>
      </div>
    )
  }

  // Leerer Zustand
  if (items.length === 0) {
    return (
      <div
        className="glass-panel rounded-2xl p-16 flex flex-col items-center justify-center gap-4 fade-in"
      >
        <div
          className="w-20 h-20 rounded-full flex items-center justify-center"
          style={{ background: "rgba(43, 51, 106, 0.2)" }}
        >
          <PackageOpen size={36} style={{ color: "rgba(255,255,255,0.3)" }} />
        </div>
        <div className="text-center">
          <p className="text-lg font-semibold mb-1" style={{ color: "rgba(255,255,255,0.6)" }}>
            Keine Items gefunden
          </p>
          <p className="text-sm" style={{ color: "rgba(255,255,255,0.3)" }}>
            Erstelle dein erstes Item mit dem Button oben rechts.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="glass-panel rounded-2xl overflow-hidden fade-in">
      <div className="overflow-x-auto">
        <table className="glass-table">
          <thead>
            <tr>
              <th className="w-16">NR</th>
              <th className="w-24">TYP</th>
              <th className="min-w-[160px]">NAME</th>
              <th className="min-w-[200px]">BESCHREIBUNG</th>
              <th className="w-40">STATUS</th>
              <th className="w-24 text-center">AKTIONEN</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="fade-in">
                {/* NR */}
                <td>
                  <span
                    className="font-mono text-sm font-medium px-2 py-1 rounded-lg"
                    style={{
                      color: "rgba(255,255,255,0.35)",
                      background: "rgba(255,255,255,0.04)",
                    }}
                  >
                    #{item.nr}
                  </span>
                </td>

                {/* TYP */}
                <td>
                  <TypeBadge typ={item.typ} />
                </td>

                {/* NAME */}
                <td>
                  <span className="font-semibold text-sm" style={{ color: "rgba(255,255,255,0.9)" }}>
                    {item.name}
                  </span>
                </td>

                {/* BESCHREIBUNG mit Tooltip */}
                <td>
                  <div
                    className="relative"
                    onMouseEnter={() =>
                      item.beschreibung && setTooltip({ id: item.id, text: item.beschreibung })
                    }
                    onMouseLeave={() => setTooltip(null)}
                  >
                    <span
                      className="text-sm block max-w-[260px] truncate cursor-default"
                      style={{ color: "rgba(255,255,255,0.45)" }}
                    >
                      {item.beschreibung || (
                        <em style={{ color: "rgba(255,255,255,0.2)" }}>Keine Beschreibung</em>
                      )}
                    </span>
                    {/* Tooltip bei langen Beschreibungen */}
                    {tooltip?.id === item.id && item.beschreibung.length > 40 && (
                      <div
                        className="absolute bottom-full mb-2 left-0 z-50 p-3 rounded-xl text-xs max-w-xs shadow-lg fade-in"
                        style={{
                          background: "rgba(8, 11, 20, 0.98)",
                          border: "1px solid rgba(255,255,255,0.12)",
                          color: "rgba(255,255,255,0.85)",
                          backdropFilter: "blur(20px)",
                          maxWidth: "280px",
                          wordBreak: "break-word",
                        }}
                      >
                        {item.beschreibung}
                      </div>
                    )}
                  </div>
                </td>

                {/* STATUS - Inline Dropdown */}
                <td>
                  <StatusBadge
                    status={item.status}
                    onStatusChange={(neuerStatus) => onStatusChange(item.id, neuerStatus)}
                  />
                </td>

                {/* AKTIONEN */}
                <td>
                  <div className="flex items-center justify-center gap-2">
                    {/* Bearbeiten-Button */}
                    <button
                      onClick={() => onEdit(item)}
                      className="w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200 group"
                      style={{
                        background: "rgba(43, 51, 106, 0.2)",
                        border: "1px solid rgba(43, 51, 106, 0.4)",
                        color: "rgba(165, 180, 252, 0.7)",
                      }}
                      title="Bearbeiten"
                    >
                      <Pencil
                        size={13}
                        strokeWidth={2}
                        className="group-hover:scale-110 transition-transform"
                      />
                    </button>

                    {/* Loeschen-Button */}
                    <button
                      onClick={() => onDelete(item)}
                      className="w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200 group"
                      style={{
                        background: "rgba(135, 0, 16, 0.15)",
                        border: "1px solid rgba(135, 0, 16, 0.35)",
                        color: "rgba(248, 113, 113, 0.7)",
                      }}
                      title="Loeschen"
                    >
                      <Trash2
                        size={13}
                        strokeWidth={2}
                        className="group-hover:scale-110 transition-transform"
                      />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Zeilenanzahl-Footer */}
      <div
        className="px-4 py-2.5 text-xs"
        style={{
          color: "rgba(255,255,255,0.3)",
          borderTop: "1px solid rgba(255,255,255,0.05)",
        }}
      >
        {items.length} {items.length === 1 ? "Item" : "Items"} angezeigt
      </div>
    </div>
  )
}
