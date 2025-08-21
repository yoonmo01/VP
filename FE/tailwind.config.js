// tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        investigate: {
          bg: "#0A0B0F",
          panel: "#151822",
          border: "#223241",
          text: "#E8F5FF",
          sub: "#A6BDC7",
          blurple: "#00D4FF",
          accent: "#00FFD1",
          warn: "#FF4757",
          gold: "#FFD700",
        },
      },
      fontFamily: {
        appsans: [
          "PyeojinGothic-Bold",
          "AppSans",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
        appheading: [
          "PyeojinGothic-Bold",
          "AppHeading",
          "AppSans",
          "system-ui",
          "sans-serif",
        ],
      },
      boxShadow: {
        "neon-md":
          "0 14px 48px rgba(0,212,255,0.12), 0 0 28px rgba(0,212,255,0.06)",
        "glass-strong": "0 10px 30px rgba(2,6,12,0.6)",
      },
      borderRadius: {
        "3xl-custom": "18px",
      },
    },
  },
  plugins: [],
};
