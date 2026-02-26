/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Hilfsfunktionen fuer den BugTracker (CSS-Klassen-Merging)
 */

import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Kombiniert CSS-Klassen mit clsx und tailwind-merge
 * Verhindert Konflikte bei Tailwind-Klassen
 */
export function cn(...eingaben: ClassValue[]): string {
  return twMerge(clsx(eingaben));
}

/**
 * Formatiert ein Datum in deutsches Format
 */
export function formatieresDatum(datumString: string): string {
  try {
    const datum = new Date(datumString);
    return datum.toLocaleDateString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  } catch {
    return datumString;
  }
}

/**
 * Kuerzt einen Text auf eine maximale Laenge mit Ellipsis
 */
export function kuerzeText(text: string, maxLaenge: number = 80): string {
  if (text.length <= maxLaenge) return text;
  return text.substring(0, maxLaenge).trim() + '...';
}
