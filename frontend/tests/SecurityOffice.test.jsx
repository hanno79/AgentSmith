/**
 * Author: Codex
 * Datum: 26.02.2026
 * Beschreibung: Render-Test fuer SecurityOffice gegen malformed Security-Daten.
 */

import React from 'react';
import assert from 'assert/strict';
import { afterEach, describe, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

import SecurityOffice from '../src/SecurityOffice';

afterEach(() => {
  cleanup();
});

describe('SecurityOffice', () => {
  it('crasht nicht bei non-array vulnerabilities', () => {
    render(
      <SecurityOffice
        agentName="Security"
        status="Idle"
        logs={[]}
        onBack={vi.fn()}
        vulnerabilities={{ severity: 'critical' }}
        overallStatus="WARNING"
        scanResult="scan"
        model="model-x"
        scannedFiles={1}
        scanType="code_scan"
        iteration={1}
        blocking={false}
      />
    );

    assert.ok(screen.getByText('Security'));
    assert.ok(screen.getAllByText(/Findings/i).length >= 1);
  });
});
