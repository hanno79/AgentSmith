/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Root Layout fuer die TodoList Next.js App
 */

import type { Metadata } from "next"
import localFont from "next/font/local"
import "./globals.css"
import { Toaster } from "sonner"

// Geist-Schriftart laden (modern, nicht Standard)
const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
})

const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
})

// Seiten-Metadaten
export const metadata: Metadata = {
  title: "TodoList | Aufgabenverwaltung",
  description: "Moderne Aufgabenverwaltung mit Glassmorphismus-Design",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="de">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        {/* Toast-Benachrichtigungen (Sonner) */}
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: "rgba(13, 15, 32, 0.95)",
              border: "1px solid rgba(255,255,255,0.12)",
              color: "#fff",
              backdropFilter: "blur(20px)",
            },
          }}
        />
        {children}
      </body>
    </html>
  )
}
