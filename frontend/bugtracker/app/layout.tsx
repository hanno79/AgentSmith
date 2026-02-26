/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Root-Layout der BugTracker Anwendung mit Sora-Schriftart
 */

import type { Metadata } from 'next';
import { Sora } from 'next/font/google';
import './globals.css';

// Sora Schriftart laden
const sora = Sora({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700', '800'],
  variable: '--schriftart-sora',
  display: 'swap',
});

// Metadaten der Anwendung
export const metadata: Metadata = {
  title: 'BugTracker - Fehler & Ideen verwalten',
  description: 'Modernes Bugtracking-System fuer Entwicklungsteams',
};

/**
 * Root-Layout Komponente - Umschliessende Struktur fuer alle Seiten
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="de" className={sora.variable}>
      <body
        className="min-h-screen bg-[#0a0b14] text-white antialiased"
        style={{ fontFamily: 'Sora, sans-serif' }}
      >
        {children}
      </body>
    </html>
  );
}
