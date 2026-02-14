import defaultTheme from 'tailwindcss/defaultTheme';

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', ...defaultTheme.fontFamily.sans],
        mono: ['JetBrains Mono', ...defaultTheme.fontFamily.mono],
      },
      colors: {
        base: '#0a0f1a',
        card: '#111827',
        'card-hover': '#1e293b',
        'text-primary': '#f1f5f9',
        'text-secondary': '#94a3b8',
        'text-muted': '#64748b',
        'accent-blue': '#3b82f6',
        'accent-red': '#ef4444',
        'accent-violet': '#8b5cf6',
        'border-subtle': '#1e293b',
        'border-hover': '#334155',
      },
    },
  },
  plugins: [],
};
