/**
 * Author: Codex
 * Datum: 26.02.2026
 * Beschreibung: Unit-Tests fuer SecurityCalculations mit Fokus auf Typrobustheit.
 */

import assert from 'assert/strict';
import { describe, it } from 'vitest';

import {
  getThreatIntel,
  getMitigationTargets,
  getDefconLevel,
  getNodeStatus,
  getDefconColorClass
} from '../src/utils/SecurityCalculations';

describe('SecurityCalculations', () => {
  it('gruppiert Mitigation-Targets korrekt', () => {
    const targets = getMitigationTargets({
      vulnerabilities: [
        { severity: 'critical' },
        { severity: 'high' },
        { severity: 'critical' },
        { severity: 'low' }
      ],
      hasData: true
    });

    const byName = Object.fromEntries(targets.map((t) => [t.name, t.patches]));
    assert.equal(byName['Critical Issues'], 2);
    assert.equal(byName['High Priority'], 1);
    assert.equal(byName['Low Priority'], 1);
  });

  it('bleibt stabil bei falschem vulnerabilities-Format', () => {
    const targets = getMitigationTargets({
      vulnerabilities: { severity: 'critical' },
      hasData: true
    });
    assert.deepEqual(targets, []);
  });

  it('berechnet Threat-Intel auch bei invalidem Input ohne Exception', () => {
    const intel = getThreatIntel({
      vulnerabilities: null,
      overallStatus: 'WARNING',
      scannedFiles: 3,
      hasData: true,
      isScanning: false
    });

    assert.equal(typeof intel.activeThreats, 'number');
    assert.equal(typeof intel.suspicious, 'number');
    assert.equal(typeof intel.secured, 'number');
  });

  it('liefert DEFCON Standby ohne Daten', () => {
    const defcon = getDefconLevel();
    assert.equal(defcon.level, 5);
    assert.equal(defcon.color, 'slate');
  });

  it('liefert Node-Unknown ohne Daten', () => {
    const nodes = getNodeStatus();
    assert.equal(nodes.length, 4);
    nodes.forEach((node) => assert.equal(node.status, 'unknown'));
  });

  it('unterstuetzt DEFCON Farben fuer ping/dot/icon', () => {
    assert.equal(getDefconColorClass('red', 'icon'), 'text-red-400');
    assert.equal(getDefconColorClass('red', 'ping'), 'bg-red-400');
    assert.equal(getDefconColorClass('red', 'dot'), 'bg-red-500');
  });
});

