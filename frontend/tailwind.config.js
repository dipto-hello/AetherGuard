/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#0B0D12',
        surface: '#12151C',
        surfaceCard: '#191D26',
        borderSubtle: '#252A36',
        borderStrong: '#363D4D',
        inkPrimary: '#F1F5F9',
        inkMuted: '#94A3B8',
        statusAllowed: '#2EA043',
        statusApproval: '#D29922',
        statusBlocked: '#F85149',
        brandAccent: '#A5B4FC',
        brandEmerald: '#2EA043',
        brandAmber: '#D29922',
        brandRuby: '#F85149',
        brandCyan: '#A5B4FC',
        // Admin console: neutral graphite + indigo accent (shifted light so dark text on brand-500 passes AA); status colors stay semantic.
        brand: { 200: '#E0E7FF', 300: '#C7D2FE', 400: '#A5B4FC', 500: '#818CF8', 800: '#3730A3', 950: '#1E1B4B' },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', '"Noto Sans Bengali"', 'monospace'],
        sans: ['"Noto Sans Bengali"', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
