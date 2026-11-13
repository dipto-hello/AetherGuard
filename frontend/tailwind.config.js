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
        background: '#0A1120',
        surface: '#0F1829',
        surfaceCard: '#152036',
        borderSubtle: '#1E2B42',
        borderStrong: '#2D3D59',
        inkPrimary: '#F1F5F9',
        inkMuted: '#94A3B8',
        statusAllowed: '#2EA043',
        statusApproval: '#D29922',
        statusBlocked: '#F85149',
        brandAccent: '#60A5FA',
        brandEmerald: '#2EA043',
        brandAmber: '#D29922',
        brandRuby: '#F85149',
        brandCyan: '#60A5FA',
        // Trust-blue brand scale; status colors (emerald/amber/red) stay semantic.
        brand: { 200: '#BFDBFE', 300: '#93C5FD', 400: '#60A5FA', 500: '#3B82F6', 800: '#1E40AF', 950: '#0B1A33' },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', '"Noto Sans Bengali"', 'monospace'],
        sans: ['"Noto Sans Bengali"', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
