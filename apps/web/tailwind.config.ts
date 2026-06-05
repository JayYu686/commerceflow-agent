import type { Config } from "tailwindcss";

const config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172026",
        panel: "#f6f7f9",
        line: "#d8dde4",
        signal: "#0f766e",
        warning: "#b45309",
      },
    },
  },
  plugins: [],
} satisfies Config;

export default config;

