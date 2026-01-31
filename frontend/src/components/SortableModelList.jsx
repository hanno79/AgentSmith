/**
 * Author: rahn
 * Datum: 29.01.2026
 * Version: 1.0
 * Beschreibung: Drag & Drop sortierbare Modell-Prioritätsliste für den Mainframe Hub.
 */
// # ÄNDERUNG [29.01.2026]: Neue Komponente für Modell-Reihenfolge per Drag & Drop — bessere UX für Prioritäten
// # ÄNDERUNG [31.01.2026]: Callback-Guards und Fehlerlogging ergänzt

import React from 'react';
// # ÄNDERUNG [29.01.2026]: Verwende @hello-pangea/dnd statt react-beautiful-dnd — React-19-kompatibel
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';

/**
 * Extrahiert den Modellnamen aus einer vollständigen Modell-ID.
 * z.B. "openrouter/meta-llama/llama-3.3-70b-instruct:free" -> "llama-3.3-70b-instruct:free"
 */
const getModelDisplayName = (modelId) => {
  if (!modelId) return '';
  const parts = modelId.split('/');
  return parts[parts.length - 1];
};

/**
 * Sortierbare Modell-Prioritätsliste.
 * Ermöglicht Drag & Drop um die Reihenfolge der Modelle zu ändern.
 *
 * Props:
 * - models: Array von Modell-IDs in Prioritätsreihenfolge
 * - onReorder: Callback wenn Liste neu sortiert wurde (neues Array)
 * - onRemove: Callback wenn ein Modell entfernt werden soll (modell-ID)
 * - maxModels: Maximale Anzahl Modelle (default 5)
 * - disabled: Wenn true, kein Drag & Drop möglich
 */
const SortableModelList = ({
  models = [],
  onReorder,
  onRemove,
  maxModels = 5,
  disabled = false
}) => {
  const logCallbackError = (funktion, error) => {
    const timestamp = new Date().toISOString();
    const details = error instanceof Error ? error.message : String(error);
    console.error(`[${timestamp}] [ERROR] ${funktion} - Callback fehlgeschlagen: ${details}`);
  };

  const handleDragEnd = (result) => {
    // Abbruch wenn kein Ziel oder disabled
    if (!result.destination || disabled) return;

    // Keine Änderung wenn am gleichen Platz
    if (result.source.index === result.destination.index) return;

    const items = Array.from(models);
    const [reordered] = items.splice(result.source.index, 1);
    items.splice(result.destination.index, 0, reordered);

    if (typeof onReorder !== 'function') return;
    try {
      onReorder(items);
    } catch (error) {
      logCallbackError('handleDragEnd', error);
    }
  };

  const handleRemove = (model, event) => {
    event.stopPropagation();
    if (disabled) return;
    if (typeof onRemove !== 'function') return;
    try {
      onRemove(model);
    } catch (error) {
      logCallbackError('handleRemove', error);
    }
  };

  if (models.length === 0) {
    return (
      <div className="sortable-model-list-empty">
        Keine Modelle ausgewählt. Klicke auf ein Modell rechts um es hinzuzufügen.
      </div>
    );
  }

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <Droppable droppableId="model-priority-list" isDropDisabled={disabled}>
        {(provided, snapshot) => (
          <div
            {...provided.droppableProps}
            ref={provided.innerRef}
            className={`sortable-model-list ${snapshot.isDraggingOver ? 'dragging-over' : ''}`}
          >
            {models.slice(0, maxModels).map((model, index) => (
              <Draggable
                key={model}
                draggableId={model}
                index={index}
                isDragDisabled={disabled}
              >
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.draggableProps}
                    {...provided.dragHandleProps}
                    className={`sortable-model-item ${index === 0 ? 'primary' : 'fallback'} ${snapshot.isDragging ? 'dragging' : ''}`}
                  >
                    <span className="drag-handle">⋮⋮</span>
                    <span className="priority-badge">
                      {index === 0 ? 'Primary' : `Fallback ${index}`}
                    </span>
                    <span className="model-name" title={model}>
                      {getModelDisplayName(model)}
                    </span>
                    <button
                      className="remove-btn"
                      onClick={(event) => handleRemove(model, event)}
                      title="Modell entfernen"
                      disabled={disabled}
                    >
                      ×
                    </button>
                  </div>
                )}
              </Draggable>
            ))}
            {provided.placeholder}
          </div>
        )}
      </Droppable>
    </DragDropContext>
  );
};

export default SortableModelList;
