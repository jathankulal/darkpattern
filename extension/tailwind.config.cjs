/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './entrypoints/**/*.{html,ts,tsx}',
    './src/**/*.{html,ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        severity: {
          info: '#64748b',    // Slate 500
          low: '#2563eb',     // Blue 600
          medium: '#d97706',  // Amber 600
          high: '#dc2626',    // Red 600
        },
      },
    },
  },
  plugins: [],
};
