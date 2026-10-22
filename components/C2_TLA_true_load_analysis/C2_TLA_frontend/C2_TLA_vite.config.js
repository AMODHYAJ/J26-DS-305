import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: process.env.C2_TLA_WEB_OUTPUT,
    emptyOutDir: false,
    assetsDir: 'C2_TLA_assets',
    rolldownOptions: {
      input: { C2_TLA_index:path.resolve('C2_TLA_index.html'), C2_TLA_C3_index:path.resolve('C2_TLA_C3_index.html') },
      output: {
        entryFileNames: 'C2_TLA_assets/C2_TLA_app-[hash].js',
        chunkFileNames: 'C2_TLA_assets/C2_TLA_chunk-[hash].js',
        assetFileNames: 'C2_TLA_assets/C2_TLA_asset-[hash][extname]',
      },
    },
  },
});
