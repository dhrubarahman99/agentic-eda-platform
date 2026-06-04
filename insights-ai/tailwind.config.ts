import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        'theme-base':      'var(--bg-base)',
        'theme-surface':   'var(--bg-surface)',
        'theme-card':      'var(--bg-card)',
        'theme-raised':    'var(--bg-raised)',
        'theme-border':    'var(--border)',
        'theme-text':      'var(--text-primary)',
        'theme-secondary': 'var(--text-secondary)',
        'theme-muted':     'var(--text-muted)',
        background: '#0A0A0A',
        surface: '#111111',
        card: '#1A1A1A',
        border: '#2A2A2A',
        'purple-primary': '#7C3AED',
        'purple-light': '#A78BFA',
        'purple-glow': 'rgba(124, 58, 237, 0.15)',
        'pink-accent': '#EC4899',
        'amber-accent': '#F59E0B',
        'text-primary': '#FFFFFF',
        'text-secondary': '#A1A1AA',
        'text-muted': '#52525B',
        'success-green': '#10B981',
        'danger-red': '#EF4444',
      },
      borderRadius: {
        lg: '16px',
        md: '10px',
        pill: '999px',
      },
      boxShadow: {
        'purple-glow': '0 0 40px rgba(124, 58, 237, 0.25)',
        'purple-glow-sm': '0 0 20px rgba(124, 58, 237, 0.15)',
      },
    },
  },
  plugins: [],
}

export default config
