/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./index.html"],
  theme: {
    extend: {
      colors: {
        darkbg: "#121214",
        cardbg: "#1a1a1e",
        cardhover: "#222228",
        limeaccent: "#d4ff32",
        mutedtext: "#8e8e93",
      },
    },
  },
  plugins: [],
}