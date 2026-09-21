import type { Config } from 'tailwindcss'

export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: 'hsl(var(--card))',
        muted: 'hsl(var(--muted))',
        'muted-foreground': 'hsl(var(--muted-foreground))',
        primary: 'hsl(var(--primary))',
        'primary-foreground': 'hsl(var(--primary-foreground))',
      },
      boxShadow: { soft: '0 14px 40px rgba(31, 41, 55, 0.08)' },
      keyframes: {
        blink: { '50%': { opacity: '0' } },
        pulseRing: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(64,158,255,.3)' },
          '50%': { boxShadow: '0 0 0 7px rgba(64,158,255,0)' },
        },
      },
      animation: {
        blink: 'blink 1s step-end infinite',
        'pulse-ring': 'pulseRing 1.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
} satisfies Config
