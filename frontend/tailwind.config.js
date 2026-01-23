/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "primary": "#137fec",
        "background-light": "#f6f7f8",
        "background-dark": "#101922",
        "card-dark": "#1c2127",
        "border-dark": "#283039",
      },
      fontFamily: {
        "display": ["Inter", "sans-serif"],
        "mono": ["monospace"]
      },
      backgroundImage: {
        'grid-pattern': "linear-gradient(to right, #283039 1px, transparent 1px), linear-gradient(to bottom, #283039 1px, transparent 1px)",
      }
    },
  },
  plugins: [],
}
