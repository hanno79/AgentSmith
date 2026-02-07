/**
 * Author: rahn
 * Datum: 31.01.2026
 * Version: 1.0
 * Beschreibung: Unit-Tests für SortableModelList (Drag & Drop, Entfernen, Rendering).
 * # ÄNDERUNG [31.01.2026]: Basis-Tests für Modell-UI und Callbacks ergänzt.
 */

import React from 'react';
import assert from 'assert/strict';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, vi, beforeEach } from 'vitest';

let latestOnDragEnd = null;

vi.mock('@hello-pangea/dnd', () => ({
  DragDropContext: ({ onDragEnd, children }) => {
    latestOnDragEnd = onDragEnd;
    return <div data-testid="dnd-context">{children}</div>;
  },
  Droppable: ({ children }) => (
    <div data-testid="droppable">
      {children(
        { droppableProps: {}, innerRef: () => {}, placeholder: null },
        { isDraggingOver: false }
      )}
    </div>
  ),
  Draggable: ({ children, draggableId, index }) => (
    <div data-testid={`draggable-${draggableId}`}>
      {children(
        { innerRef: () => {}, draggableProps: {}, dragHandleProps: {} },
        { isDragging: false, index }
      )}
    </div>
  )
}));

import SortableModelList from '../src/components/SortableModelList';

const MODELS = [
  'openrouter/meta-llama/llama-3.3-70b-instruct:free',
  'openrouter/google/gemini-3-pro',
  'openrouter/x-ai/grok-4.1-fast'
];

describe('SortableModelList', () => {
  beforeEach(() => {
    latestOnDragEnd = null;
  });

  it('rendert Primary/Fallback Badges und kürzt Modell-IDs', () => {
    render(
      <SortableModelList
        models={MODELS}
        onReorder={vi.fn()}
        onRemove={vi.fn()}
        maxModels={2}
      />
    );

    assert.ok(screen.getByText('Primary'), 'Erwartet: Primary Badge wird angezeigt');
    assert.ok(screen.getByText('Fallback 1'), 'Erwartet: Fallback 1 Badge wird angezeigt');
    assert.ok(
      screen.getByText('llama-3.3-70b-instruct:free'),
      'Erwartet: Modellname ohne Prefix wird angezeigt'
    );
    assert.ok(
      screen.getByText('gemini-3-pro'),
      'Erwartet: Modellname ohne Prefix wird angezeigt'
    );
    assert.equal(
      screen.queryByText('grok-4.1-fast'),
      null,
      'Erwartet: Modelle über maxModels werden nicht gerendert'
    );
  });

  it('ruft onReorder mit neuer Reihenfolge auf', () => {
    const onReorder = vi.fn();
    render(
      <SortableModelList
        models={MODELS}
        onReorder={onReorder}
        onRemove={vi.fn()}
      />
    );

    assert.equal(typeof latestOnDragEnd, 'function', 'Erwartet: DragEnd-Handler ist verfügbar');

    latestOnDragEnd({
      source: { index: 0 },
      destination: { index: 2 }
    });

    assert.equal(onReorder.mock.calls.length, 1, 'Erwartet: onReorder wurde genau einmal aufgerufen');
    assert.deepEqual(
      onReorder.mock.calls[0][0],
      [MODELS[1], MODELS[2], MODELS[0]],
      'Erwartet: Neue Reihenfolge entspricht Drag-Ergebnis'
    );
  });

  it('verhindert Reorder bei identischer Position', () => {
    const onReorder = vi.fn();
    render(
      <SortableModelList
        models={MODELS}
        onReorder={onReorder}
        onRemove={vi.fn()}
      />
    );

    latestOnDragEnd({
      source: { index: 1 },
      destination: { index: 1 }
    });

    assert.equal(onReorder.mock.calls.length, 0, 'Erwartet: onReorder wird nicht aufgerufen');
  });

  it('ruft onRemove beim Entfernen auf', () => {
    const onRemove = vi.fn();
    render(
      <SortableModelList
        models={MODELS}
        onReorder={vi.fn()}
        onRemove={onRemove}
      />
    );

    const removeButtons = screen.getAllByTitle('Modell entfernen');
    fireEvent.click(removeButtons[0]);

    assert.equal(onRemove.mock.calls.length, 1, 'Erwartet: onRemove wird genau einmal aufgerufen');
    assert.equal(
      onRemove.mock.calls[0][0],
      MODELS[0],
      'Erwartet: onRemove erhält das entfernte Modell'
    );
  });

  it('blockiert Reorder und Remove im disabled Zustand', () => {
    const onReorder = vi.fn();
    const onRemove = vi.fn();
    render(
      <SortableModelList
        models={MODELS}
        onReorder={onReorder}
        onRemove={onRemove}
        disabled
      />
    );

    latestOnDragEnd({
      source: { index: 0 },
      destination: { index: 1 }
    });
    const removeButtons = screen.getAllByTitle('Modell entfernen');
    fireEvent.click(removeButtons[0]);

    assert.equal(onReorder.mock.calls.length, 0, 'Erwartet: onReorder wird im disabled Zustand nicht aufgerufen');
    assert.equal(onRemove.mock.calls.length, 0, 'Erwartet: onRemove wird im disabled Zustand nicht aufgerufen');
  });
});
