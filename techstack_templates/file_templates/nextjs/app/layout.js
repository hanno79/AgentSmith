import './globals.css';

export const metadata = {
  title: 'Projekt',
  description: 'Erstellt mit Next.js',
};

// AENDERUNG 10.02.2026: Fix 46 — suppressHydrationWarning auf html+body
// ROOT-CAUSE-FIX: Browser-Extensions injizieren Attribute → Hydration-Mismatch
export default function RootLayout({ children }) {
  return (
    <html lang="de" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
