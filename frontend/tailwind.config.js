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
        background: '#0B0E14',
        surface: '#111620',
        surfaceCard: '#151B27',
        borderSubtle: '#1F2736',
        borderStrong: '#2E394D',
        inkPrimary: '#E6EDF3',
        inkMuted: '#8B949E',
        statusAllowed: '#2EA043',
        statusApproval: '#D29922',
        statusBlocked: '#F85149',
        brandAccent: '#38BDF8',
        brandEmerald: '#2EA043',
        brandAmber: '#D29922',
        brandRuby: '#F85149',
        brandCyan: '#38BDF8',
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', '"Noto Sans Bengali"', 'monospace'],
        sans: ['"Noto Sans Bengali"', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
