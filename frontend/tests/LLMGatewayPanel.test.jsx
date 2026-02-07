/**
 * Author: rahn
 * Datum: 02.02.2026
 * Version: 1.0
 * Beschreibung: Smoke- und Basis-Tests für LLMGatewayPanel (Agents, Rate-Limits).
 * # ÄNDERUNG [02.02.2026]: Komponenten-Test für LLMGatewayPanel ergänzt.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import LLMGatewayPanel from '../src/components/LLMGatewayPanel';

describe('LLMGatewayPanel', () => {
  it('rendert ohne Absturz (Smoke)', () => {
    render(
      <LLMGatewayPanel
        agents={[]}
        routerStatus={{ rate_limited_models: {} }}
      />
    );
    expect(screen.getByText(/LLM Gateway/i)).toBeDefined();
  });

  it('zeigt Agent-Liste und Rate-Limited-Bereich bei leeren Props', () => {
    render(
      <LLMGatewayPanel
        agents={[]}
        routerStatus={{}}
      />
    );
    expect(screen.getByRole('heading', { name: /LLM Gateway/i })).toBeTruthy();
  });

  it('zeigt einen Agent wenn übergeben', () => {
    const agents = [
      { role: 'coder', name: 'Coder', model: 'openai/gpt-4o' }
    ];
    render(
      <LLMGatewayPanel
        agents={agents}
        routerStatus={{ rate_limited_models: {} }}
        getModelDisplayName={(m) => m || ''}
        isModelRateLimited={() => false}
      />
    );
    expect(screen.getByText('Coder')).toBeTruthy();
  });

  it('ruft onAgentClick beim Klick auf einen Agent auf', () => {
    const onAgentClick = vi.fn();
    const agents = [
      { role: 'coder', name: 'Coder', model: 'gpt-4o' }
    ];
    render(
      <LLMGatewayPanel
        agents={agents}
        routerStatus={{ rate_limited_models: {} }}
        onAgentClick={onAgentClick}
      />
    );
    fireEvent.click(screen.getByText('Coder'));
    expect(onAgentClick).toHaveBeenCalledWith(agents[0]);
  });
});
