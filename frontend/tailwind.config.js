/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ivory: '#F4EFE6',
        softpaper: '#EAE3D6',
        ink: {
          DEFAULT: '#15130F',
          secondary: '#4A453D',
          muted: '#706A61',
          light: '#A39C91',
        },
        vermilion: {
          DEFAULT: '#E8472B',
          deep: '#C23A20',
          light: '#FCEBE8',
        },
        ochre: {
          DEFAULT: '#C8962A',
          deep: '#9E741B',
          light: '#F9F3E5',
        },
        moss: {
          DEFAULT: '#3F6B4F',
          deep: '#2F503B',
          light: '#EAF1ED',
        },
      },
      fontFamily: {
        editorial: ['Fraunces', 'Georgia', 'serif'],
        sans: ['"Instrument Sans"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        'ticket': '0 8px 30px rgba(21, 19, 15, 0.08)',
        'lift': '0 12px 32px rgba(21, 19, 15, 0.12)',
        'pressed': 'inset 0 2px 4px rgba(21, 19, 15, 0.15)',
      },
    },
  },
  plugins: [],
};
