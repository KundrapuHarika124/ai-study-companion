/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1B1F1E", mute: "#5F6663", line: "#DDE1DE", paper: "#F6F7F5", surface: "#FFFFFF",
        teal: { DEFAULT: "#2F5D62", soft: "#E7EFEE", deep: "#213F43" },
        amber: { DEFAULT: "#B7791F", soft: "#FBF1DC" },
        moss: { DEFAULT: "#2E7D5B", soft: "#E3F1EA" },
        rust: { DEFAULT: "#A93F2E", soft: "#F8E5E1" },
      },
      fontFamily: { sans: ["'IBM Plex Sans'", "system-ui", "sans-serif"], serif: ["'IBM Plex Serif'", "Georgia", "serif"] },
    },
  },
  plugins: [],
};
