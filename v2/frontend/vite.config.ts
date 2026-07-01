/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { svelteTesting } from "@testing-library/svelte/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [svelte(), svelteTesting()],
  // Tauri expects the dev server on a fixed port and fails if it moves.
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    watch: { ignored: ["**/src-tauri/**"] },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.{test,spec}.{ts,js}"],
    restoreMocks: true,
    coverage: {
      provider: "v8",
      include: ["src/lib/**/*.{ts,svelte}"],
      exclude: ["src/lib/**/*.{test,spec}.ts"],
    },
  },
});
