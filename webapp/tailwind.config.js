/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        sakura: {
          blush: '#FFE4EC',
          light: '#FFD1DC',
          pink: '#FFB7C5',
          rose: '#E75480',
          darkrose: '#C71585',
          cream: '#FFF8F5',
          plum: '#5B3A4A',
          plumdark: '#3D2030',
          darkbg: '#1F1018',
          darkcard: '#2D1724',
          darkcardsoft: '#3A1E2E',
        },
      },
      fontFamily: {
        body: ['Nunito', 'Quicksand', 'sans-serif'],
        logo: ['Pacifico', 'cursive'],
      },
      boxShadow: {
        'sakura-sm': '0 2px 10px rgba(231, 84, 128, 0.08)',
        'sakura': '0 8px 25px rgba(231, 84, 128, 0.15)',
        'sakura-lg': '0 12px 35px rgba(231, 84, 128, 0.22)',
      },
      borderRadius: {
        '2xl': '18px',
        '3xl': '24px',
      },
      animation: {
        'petal-fall': 'fall 8s linear infinite',
        'heart-pop': 'heartPop 0.35s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
      },
      keyframes: {
        fall: {
          '0%': { transform: 'translateY(-10%) rotate(0deg)', opacity: '0.9' },
          '100%': { transform: 'translateY(110vh) rotate(360deg)', opacity: '0' },
        },
        heartPop: {
          '0%': { transform: 'scale(1)' },
          '50%': { transform: 'scale(1.35)' },
          '100%': { transform: 'scale(1)' },
        },
        scaleIn: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
