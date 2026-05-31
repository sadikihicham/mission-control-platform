import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Palette états agents (Contract D) — réutilisée par le dashboard
        agent: {
          idle: "#6b7280",
          working: "#3b82f6",
          blocked: "#f59e0b",
          done: "#10b981",
          error: "#ef4444",
          stale: "#a855f7",
        },
      },
    },
  },
  plugins: [],
};

export default config;
