import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: ".",
  server: {
    host: "0.0.0.0",
    port: 3000,
  },
  optimizeDeps: {
    include: ["react", "react-dom", "lucide-react", "axios"],
  },
  plugins: [react()],
});
