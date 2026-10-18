import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { viteSingleFile } from 'vite-plugin-singlefile';
import { fileURLToPath } from 'node:url';

// The prototype reads AIA's generated design tokens and self-hosted fonts from
// apps/web directly, so it never carries a second copy of the token source.
const repoRoot = fileURLToPath(new URL('../..', import.meta.url));

export default defineConfig({
  plugins: [react(), viteSingleFile()],
  server: { fs: { allow: [repoRoot] } },
  build: { outDir: 'dist', assetsInlineLimit: 100_000_000, cssCodeSplit: false },
});
