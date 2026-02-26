/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Hauptseite der TodoList-WebApp mit State-Management und CRUD-Operationen
 */

"use client"

import { useState, useEffect, useMemo, useCallback } from "react"
import { toast } from "sonner"
import { Plus } from "lucide-react"
import { TodoItem, CreateItemInput, UpdateItemInput, FilterState, StatsData, TodoStatus } from "@/types"
import StatsBar from "@/components/stats_bar"
import FilterBar from "@/components/filter_bar"
import ItemTable from "@/components/item_table"
import AddItemModal from "@/components/add_item_modal"
import EditItemModal from "@/components/edit_item_modal"
import DeleteConfirmModal from "@/components/delete_confirm_modal"

/**
 * Hauptseite: Verwaltet alle Items, Filter und Modal-Zustände
 */
export default function HomePage() {
  // Items-State
  const [items, setItems] = useState<TodoItem[]>([])
  const [laden, setLaden] = useState(true)

  // Filter-State
  const [filter, setFilter] = useState<FilterState>({
    suche: "",
    typ: "alle",
    status: "alle",
  })

  // Modal-States
  const [addModalOffen, setAddModalOffen] = useState(false)
  const [editItem, setEditItem] = useState<TodoItem | null>(null)
  const [deleteItem, setDeleteItem] = useState<TodoItem | null>(null)

  // ============================================================
  // Items laden beim ersten Rendern
  // ============================================================
  const ladeItems = useCallback(async () => {
    try {
      setLaden(true)
      const response = await fetch("/api/items")
      if (!response.ok) throw new Error("Laden fehlgeschlagen")
      const { data } = await response.json()
      setItems(data || [])
    } catch (fehler) {
      console.error("Fehler beim Laden:", fehler)
      toast.error("Items konnten nicht geladen werden.")
    } finally {
      setLaden(false)
    }
  }, [])

  useEffect(() => {
    ladeItems()
  }, [ladeItems])

  // ============================================================
  // CRUD-Operationen
  // ============================================================

  // Neues Item erstellen
  const addItem = async (input: CreateItemInput) => {
    const response = await fetch("/api/items", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })

    if (!response.ok) {
      const { error } = await response.json()
      throw new Error(error || "Erstellen fehlgeschlagen")
    }

    const { data } = await response.json()
    setItems((prev) => [data, ...prev])
    toast.success(`Item "${data.name}" erfolgreich erstellt.`)
  }

  // Item aktualisieren
  const updateItem = async (id: number, input: UpdateItemInput) => {
    const response = await fetch(`/api/items/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })

    if (!response.ok) {
      const { error } = await response.json()
      throw new Error(error || "Aktualisierung fehlgeschlagen")
    }

    const { data } = await response.json()
    setItems((prev) => prev.map((item) => (item.id === id ? data : item)))
    toast.success(`Item "${data.name}" erfolgreich aktualisiert.`)
  }

  // Status direkt in der Tabelle aendern
  const statusAendern = async (id: number, neuerStatus: TodoStatus) => {
    try {
      const response = await fetch(`/api/items/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: neuerStatus }),
      })

      if (!response.ok) throw new Error("Status-Aenderung fehlgeschlagen")

      const { data } = await response.json()
      setItems((prev) => prev.map((item) => (item.id === id ? data : item)))
      toast.success(`Status geaendert zu "${data.status}".`)
    } catch (fehler) {
      console.error("Status-Aenderung Fehler:", fehler)
      toast.error("Status konnte nicht geaendert werden.")
    }
  }

  // Item loeschen
  const deleteItemById = async (id: number) => {
    const response = await fetch(`/api/items/${id}`, { method: "DELETE" })

    if (!response.ok) {
      const { error } = await response.json()
      throw new Error(error || "Loeschen fehlgeschlagen")
    }

    const geloeschtesItem = items.find((item) => item.id === id)
    setItems((prev) => prev.filter((item) => item.id !== id))
    toast.success(`Item "${geloeschtesItem?.name || "Unbekannt"}" geloescht.`)
  }

  // ============================================================
  // Gefilterte Items berechnen
  // ============================================================
  const gefilterteItems = useMemo(() => {
    return items.filter((item) => {
      // Typ-Filter
      if (filter.typ !== "alle" && item.typ !== filter.typ) return false
      // Status-Filter
      if (filter.status !== "alle" && item.status !== filter.status) return false
      // Suchfilter (Name und Beschreibung)
      if (filter.suche.trim()) {
        const suchterm = filter.suche.toLowerCase()
        const trefferName = item.name.toLowerCase().includes(suchterm)
        const trefferBeschreibung = item.beschreibung.toLowerCase().includes(suchterm)
        if (!trefferName && !trefferBeschreibung) return false
      }
      return true
    })
  }, [items, filter])

  // ============================================================
  // Statistiken berechnen
  // ============================================================
  const stats: StatsData = useMemo(() => ({
    gesamt: items.length,
    bugs: items.filter((i) => i.typ === "bug").length,
    ideen: items.filter((i) => i.typ === "idee").length,
    offen: items.filter((i) => i.status === "offen").length,
    erledigt: items.filter((i) => i.status === "erledigt").length,
  }), [items])

  // ============================================================
  // Rendering
  // ============================================================
  return (
    <main className="min-h-screen relative overflow-x-hidden">
      {/* Animierte Hintergrund-Glow-Highlights */}
      <div
        className="fixed top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full pointer-events-none"
        style={{
          background: "radial-gradient(circle, rgba(43,51,106,0.18) 0%, transparent 70%)",
          filter: "blur(40px)",
          zIndex: 0,
        }}
      />
      <div
        className="fixed bottom-[-10%] right-[-5%] w-[500px] h-[500px] rounded-full pointer-events-none"
        style={{
          background: "radial-gradient(circle, rgba(135,0,16,0.12) 0%, transparent 70%)",
          filter: "blur(40px)",
          zIndex: 0,
        }}
      />
      <div
        className="fixed top-[40%] right-[20%] w-[400px] h-[400px] rounded-full pointer-events-none"
        style={{
          background: "radial-gradient(circle, rgba(43,51,106,0.08) 0%, transparent 70%)",
          filter: "blur(60px)",
          zIndex: 0,
        }}
      />

      {/* Haupt-Content */}
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1
              className="text-3xl font-bold tracking-tight mb-1"
              style={{ color: "rgba(255,255,255,0.95)" }}
            >
              TodoList
            </h1>
            <p className="text-sm" style={{ color: "rgba(255,255,255,0.4)" }}>
              Bugs und Ideen verwalten und tracken
            </p>
          </div>

          {/* Neues Item hinzufuegen Button */}
          <button
            onClick={() => setAddModalOffen(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 hover:scale-[1.03]"
            style={{
              background: "rgba(43, 51, 106, 0.45)",
              border: "1px solid rgba(61, 74, 150, 0.55)",
              color: "#a5b4fc",
              boxShadow: "0 0 20px rgba(43, 51, 106, 0.35)",
            }}
          >
            <Plus size={16} strokeWidth={2.5} />
            Neues Item
          </button>
        </div>

        {/* Statistik-Leiste */}
        <StatsBar stats={stats} />

        {/* Filter-Leiste */}
        <FilterBar filter={filter} onFilterChange={setFilter} />

        {/* Tabelle */}
        <ItemTable
          items={gefilterteItems}
          onEdit={(item) => setEditItem(item)}
          onDelete={(item) => setDeleteItem(item)}
          onStatusChange={statusAendern}
          laden={laden}
        />
      </div>

      {/* Modals */}
      <AddItemModal
        offen={addModalOffen}
        onSchliessen={() => setAddModalOffen(false)}
        onHinzufuegen={addItem}
      />

      <EditItemModal
        item={editItem}
        onSchliessen={() => setEditItem(null)}
        onSpeichern={updateItem}
      />

      <DeleteConfirmModal
        item={deleteItem}
        onSchliessen={() => setDeleteItem(null)}
        onBestaetigen={deleteItemById}
      />
    </main>
  )
}
