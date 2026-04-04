/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        'edge-gold': '#d4a017',
        'edge-pink': '#f72585',
        'edge-teal': '#00d4aa',
        'edge-blue': '#38bdf8',
        'edge-bg': '#0a0a0f',
        'edge-surface': '#1a1a1a',
      },
    },
  },
  plugins: [],
}
