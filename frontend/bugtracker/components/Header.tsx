/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Atemberaubender Header mit Glassmorphismus-Effekt, Logo und Datum/Zeit
 */

'use client';

import React, { useState, useEffect } from 'react';
import { Bug, Clock } from 'lucide-react';

/**
 * Header-Komponente mit Echtzeit-Uhr und Glassmorphismus-Design
 */
export function Header() {
  // Zustand fuer aktuelle Zeit
  const [aktuelleZeit, setAktuelleZeit] = useState<string>('');
  const [aktuellesDatum, setAktuellesDatum] = useState<string>('');

  // Uhrzeit jede Sekunde aktualisieren
  useEffect(() => {
    const zeitAktualisieren = () => {
      const jetzt = new Date();
      setAktuelleZeit(
        jetzt.toLocaleTimeString('de-DE', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      );
      setAktuellesDatum(
        jetzt.toLocaleDateString('de-DE', {
          weekday: 'long',
          day: '2-digit',
          month: 'long',
          year: 'numeric',
        })
      );
    };

    zeitAktualisieren();
    const intervall = setInterval(zeitAktualisieren, 1000);

    // Aufraeum-Funktion
    return () => clearInterval(intervall);
  }, []);

  return (
    <header className="glas rounded-2xl px-8 py-6 mb-8 animate-slideUp">
      <div className="flex items-center justify-between">
        {/* Logo und Titel Bereich */}
        <div className="flex items-center gap-5">
          {/* Logo-Container */}
          <div className="relative flex items-center justify-center w-14 h-14 rounded-xl bg-[rgba(135,0,16,0.2)] border border-[rgba(135,0,16,0.35)] shadow-[0_0_20px_rgba(135,0,16,0.3)]">
            <Bug
              className="w-7 h-7 text-[#ff4d6d]"
              aria-hidden="true"
            />
            {/* Leuchtender Punkt Indikator */}
            <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-[#4ade80] shadow-[0_0_8px_rgba(74,222,128,0.8)] animate-pulse" />
          </div>

          {/* Titel und Untertitel */}
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              {/* Gradient-Text */}
              <span className="text-white">Bug</span>
              <span
                className="text-transparent bg-clip-text"
                style={{
                  backgroundImage: 'linear-gradient(135deg, #ff4d6d 0%, #c9184a 100%)',
                }}
              >
                Tracker
              </span>
            </h1>
            <p className="text-white/40 text-sm font-light mt-0.5">
              Fehler & Ideen verwalten
            </p>
          </div>
        </div>

        {/* Datum und Zeit Bereich */}
        <div className="flex items-center gap-3 px-5 py-3 rounded-xl bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)]">
          <Clock className="w-4 h-4 text-white/35" aria-hidden="true" />
          <div className="text-right">
            <div className="text-lg font-semibold text-white/80 tabular-nums tracking-wide">
              {aktuelleZeit}
            </div>
            <div className="text-xs text-white/35 font-light">
              {aktuellesDatum}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
