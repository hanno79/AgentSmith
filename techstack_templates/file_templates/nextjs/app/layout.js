import './globals.css';

export const metadata = {
  title: 'Projekt',
  description: 'Erstellt mit Next.js',
};

export default function RootLayout({ children }) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
