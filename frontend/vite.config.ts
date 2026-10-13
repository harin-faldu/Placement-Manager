import { fileURLToPath, URL } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

const PASSWORDS = [
  "ADMIN_PASSWORD",
  "OFFICER_PASSWORD",
  "COORDINATOR_PASSWORD",
  "RECRUITER_PASSWORD",
  "STUDENT_PASSWORD",
];

export default defineConfig(({ mode }) => {
  const fileEnv = loadEnv(mode, fileURLToPath(new URL("..", import.meta.url)), "");
  const define: Record<string, string> = {};
  for (const key of PASSWORDS) {
    const value = process.env[`VITE_${key}`] || fileEnv[key] || "";
    define[`import.meta.env.VITE_${key}`] = JSON.stringify(value);
  }
  return {
    plugins: [react()],
    define,
    server: {
      port: 5173,
      proxy: { "/api": "http://localhost:8000" },
    },
  };
});
