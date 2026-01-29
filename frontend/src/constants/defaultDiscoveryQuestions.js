/**
 * Author: rahn
 * Datum: 29.01.2026
 * Version: 1.2
 * Beschreibung: Standardfragen für die Discovery-Phase.
 */
// ÄNDERUNG 29.01.2026: Standardfragen ausgelagert
// ÄNDERUNG 29.01.2026 v1.1: SCOPE und ERFOLGSKRITERIEN Fragen hinzugefügt
// ÄNDERUNG 29.01.2026 v1.2: DATENGRUNDLAGE und TIMELINE Fragen hinzugefügt

const defaultDiscoveryQuestions = {
  Analyst: [
    {
      id: 'analyst_purpose',
      question: 'Was ist der primäre Geschäftszweck dieses Projekts?',
      options: [
        { text: 'Interne Prozessoptimierung', value: 'internal', recommended: false },
        { text: 'Kundenprodukt / Externe Nutzung', value: 'customer', recommended: true, reason: 'Höhere Qualitätsanforderungen' },
        { text: 'Forschung / Prototyp', value: 'research', recommended: false },
        { text: 'Datenanalyse / Reporting', value: 'analytics', recommended: false }
      ],
      allowCustom: true,
      allowSkip: true
    },
    {
      id: 'analyst_users',
      question: 'Wer sind die Hauptnutzer des Systems?',
      options: [
        { text: 'Technische Mitarbeiter', value: 'technical', recommended: false },
        { text: 'Nicht-technische Endnutzer', value: 'non_technical', recommended: true, reason: 'Erfordert bessere UX' },
        { text: 'Administratoren', value: 'admins', recommended: false },
        { text: 'Externe Kunden', value: 'external', recommended: false }
      ],
      multiple: true,
      allowCustom: true
    },
    // ÄNDERUNG 29.01.2026: SCOPE Fragen
    {
      id: 'analyst_scope_in',
      question: 'Was gehört DEFINITIV zum Projektumfang (In-Scope)?',
      options: [
        { text: 'Kernfunktionalität gemäß Beschreibung', value: 'core', recommended: true, reason: 'Fokus auf das Wesentliche' },
        { text: 'Benutzeroberfläche / Frontend', value: 'ui', recommended: false },
        { text: 'API / Backend-Services', value: 'api', recommended: false },
        { text: 'Datenbank / Datenspeicherung', value: 'database', recommended: false }
      ],
      multiple: true,
      allowCustom: true
    },
    {
      id: 'analyst_scope_out',
      question: 'Was ist EXPLIZIT ausgeschlossen (Out-of-Scope)?',
      options: [
        { text: 'Mobile App', value: 'mobile', recommended: false },
        { text: 'Multi-Sprach-Support (i18n)', value: 'i18n', recommended: true, reason: 'Kann später ergänzt werden' },
        { text: 'Performance-Optimierung', value: 'performance', recommended: false },
        { text: 'Erweiterte Sicherheitsfeatures', value: 'security_advanced', recommended: false }
      ],
      multiple: true,
      allowCustom: true,
      allowSkip: true
    },
    // ÄNDERUNG 29.01.2026: ERFOLGSKRITERIEN Fragen
    {
      id: 'analyst_success_criteria',
      question: 'Woran messen wir den Projekterfolg?',
      options: [
        { text: 'Funktionalität vollständig implementiert', value: 'functionality', recommended: true, reason: 'Grundvoraussetzung' },
        { text: 'Alle Tests bestanden', value: 'tests_passed', recommended: false },
        { text: 'Performance-Ziele erreicht', value: 'performance', recommended: false },
        { text: 'Nutzerakzeptanz / Feedback positiv', value: 'user_acceptance', recommended: false }
      ],
      multiple: true,
      allowCustom: true
    }
  ],
  Coder: [
    {
      id: 'coder_language',
      question: 'Gibt es Vorgaben für die Programmiersprache?',
      options: [
        { text: 'Python', value: 'python', recommended: true, reason: 'Flexibel, große Community' },
        { text: 'JavaScript / TypeScript', value: 'javascript', recommended: false },
        { text: 'Java', value: 'java', recommended: false },
        { text: 'Keine Vorgabe - beste Wahl treffen', value: 'auto', recommended: false }
      ],
      allowCustom: true
    },
    {
      id: 'coder_deployment',
      question: 'Welche Deployment-Umgebung ist geplant?',
      options: [
        { text: 'Lokale Ausführung', value: 'local', recommended: true, reason: 'Einfachster Start' },
        { text: 'Cloud (AWS, Azure, GCP)', value: 'cloud', recommended: false },
        { text: 'Docker Container', value: 'docker', recommended: false },
        { text: 'Noch unklar', value: 'unknown', recommended: false }
      ]
    }
  ],
  Tester: [
    {
      id: 'tester_coverage',
      question: 'Welche Test-Abdeckung wird erwartet?',
      options: [
        { text: 'Minimal (nur kritische Pfade)', value: 'minimal', recommended: false },
        { text: 'Standard (Unit + Integration)', value: 'standard', recommended: true },
        { text: 'Umfassend (inkl. E2E)', value: 'comprehensive', recommended: false },
        { text: 'Keine automatisierten Tests', value: 'none', recommended: false }
      ]
    }
  ],
  Planner: [
    {
      id: 'planner_timeline',
      question: 'Wie ist der gewünschte Zeitrahmen?',
      options: [
        { text: 'So schnell wie möglich', value: 'asap', recommended: false },
        { text: '1-2 Wochen', value: 'short', recommended: true },
        { text: '1 Monat', value: 'medium', recommended: false },
        { text: 'Kein fester Termin', value: 'flexible', recommended: false }
      ]
    },
    // ÄNDERUNG 29.01.2026: TIMELINE Fragen
    {
      id: 'planner_milestones',
      question: 'Welche Meilensteine sind wichtig?',
      options: [
        { text: 'MVP / Proof of Concept', value: 'mvp', recommended: true, reason: 'Schnelles Feedback' },
        { text: 'Alpha-Version (intern testbar)', value: 'alpha', recommended: false },
        { text: 'Beta-Version (externe Tests)', value: 'beta', recommended: false },
        { text: 'Finale Produktionsversion', value: 'production', recommended: false }
      ],
      multiple: true,
      allowCustom: true
    },
    {
      id: 'planner_deadline',
      question: 'Gibt es einen festen Abgabetermin?',
      options: [
        { text: 'Ja, fester Termin (bitte angeben)', value: 'fixed', recommended: false },
        { text: 'Wunschtermin, aber flexibel', value: 'preferred', recommended: true, reason: 'Realistische Planung' },
        { text: 'Kein fester Termin', value: 'none', recommended: false },
        { text: 'Iterative Releases', value: 'iterative', recommended: false }
      ],
      allowCustom: true
    }
  ],
  'Data Researcher': [
    {
      id: 'researcher_sources',
      question: 'Welche Datenquellen sollen verwendet werden?',
      options: [
        { text: 'Interne Datenbanken', value: 'internal_db', recommended: true, reason: 'Direkter Zugriff' },
        { text: 'Externe APIs', value: 'external_api', recommended: false },
        { text: 'Dateien (CSV, Excel, JSON)', value: 'files', recommended: false },
        { text: 'Web Scraping', value: 'scraping', recommended: false }
      ],
      multiple: true,
      allowCustom: true
    },
    {
      id: 'researcher_volume',
      question: 'Welches Datenvolumen wird erwartet?',
      options: [
        { text: 'Klein (< 10.000 Datensätze)', value: 'small', recommended: true },
        { text: 'Mittel (10.000 - 1 Million)', value: 'medium', recommended: false },
        { text: 'Groß (> 1 Million)', value: 'large', recommended: false },
        { text: 'Noch unklar', value: 'unknown', recommended: false }
      ]
    },
    // ÄNDERUNG 29.01.2026: DATENGRUNDLAGE Fragen
    {
      id: 'researcher_data_availability',
      question: 'Liegen die benötigten Daten bereits vor?',
      options: [
        { text: 'Ja, vollständig verfügbar', value: 'available', recommended: true, reason: 'Schnellerer Start' },
        { text: 'Teilweise vorhanden', value: 'partial', recommended: false },
        { text: 'Müssen erst erhoben werden', value: 'collect', recommended: false },
        { text: 'Noch unklar', value: 'unknown', recommended: false }
      ],
      allowCustom: true
    },
    {
      id: 'researcher_data_quality',
      question: 'Wie ist die Datenqualität einzuschätzen?',
      options: [
        { text: 'Sauber und strukturiert', value: 'clean', recommended: true, reason: 'Weniger Aufbereitung' },
        { text: 'Benötigt Bereinigung', value: 'needs_cleaning', recommended: false },
        { text: 'Unbekannt / Muss geprüft werden', value: 'unknown', recommended: false },
        { text: 'Rohdaten ohne Struktur', value: 'raw', recommended: false }
      ]
    }
  ],
  Designer: [
    {
      id: 'designer_style',
      question: 'Welchen Designstil bevorzugst du?',
      options: [
        { text: 'Modern / Minimalistisch', value: 'modern', recommended: true, reason: 'Zeitgemäß und übersichtlich' },
        { text: 'Klassisch / Business', value: 'business', recommended: false },
        { text: 'Verspielt / Kreativ', value: 'creative', recommended: false },
        { text: 'Kein spezieller Stil', value: 'auto', recommended: false }
      ]
    },
    {
      id: 'designer_responsive',
      question: 'Welche Geräte sollen unterstützt werden?',
      options: [
        { text: 'Nur Desktop', value: 'desktop', recommended: false },
        { text: 'Desktop + Tablet', value: 'desktop_tablet', recommended: false },
        { text: 'Alle Geräte (Responsive)', value: 'responsive', recommended: true, reason: 'Maximale Reichweite' },
        { text: 'Mobile First', value: 'mobile_first', recommended: false }
      ]
    }
  ],
  Security: [
    {
      id: 'security_auth',
      question: 'Welche Authentifizierung wird benötigt?',
      options: [
        { text: 'Keine (öffentliche Anwendung)', value: 'none', recommended: false },
        { text: 'Einfache Anmeldung (Benutzername/Passwort)', value: 'basic', recommended: true },
        { text: 'OAuth / Social Login', value: 'oauth', recommended: false },
        { text: 'Enterprise SSO', value: 'sso', recommended: false }
      ]
    },
    {
      id: 'security_data',
      question: 'Welche Daten-Sensitivität liegt vor?',
      options: [
        { text: 'Öffentliche Daten', value: 'public', recommended: false },
        { text: 'Interne Daten', value: 'internal', recommended: true },
        { text: 'Personenbezogene Daten (DSGVO)', value: 'personal', recommended: false },
        { text: 'Hochsensible Daten', value: 'sensitive', recommended: false }
      ]
    }
  ]
};

export default defaultDiscoveryQuestions;
