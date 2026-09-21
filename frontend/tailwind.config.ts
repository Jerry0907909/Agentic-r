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
        surface: 'hsl(var(--surface))',
        muted: 'hsl(var(--muted))',
        'muted-foreground': 'hsl(var(--muted-foreground))',
        primary: 'hsl(var(--primary))',
        'primary-foreground': 'hsl(var(--primary-foreground))',
        accent: 'hsl(var(--accent))',
        'accent-foreground': 'hsl(var(--accent-foreground))',
        graph: 'hsl(var(--graph))',
        document: 'hsl(var(--document))',
        mock: 'hsl(var(--mock))',
        success: 'hsl(var(--success))',
        danger: 'hsl(var(--danger))',
      },
      boxShadow: {
        soft: '0 10px 30px rgba(48, 64, 55, 0.07)',
        lifted: '0 18px 50px rgba(39, 55, 46, 0.12)',
      },
      keyframes: {
        blink: { '50%': { opacity: '0' } },
        pulseRing: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(63,111,97,.3)' },
          '50%': { boxShadow: '0 0 0 7px rgba(63,111,97,0)' },
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
