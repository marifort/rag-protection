import { resolve } from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const proxyStaticCe = resolve(
  __dirname,
  '../../../rag-protection-proxy/rag_protection_proxy/ui/static/ce',
);

export default defineConfig(({ command }) => ({
  plugins: [react()],
  resolve: {
    alias: {
      '@rag-protection/console-core': resolve(__dirname, '../core/src/index.ts'),
    },
  },
  build: {
    outDir: proxyStaticCe,
    emptyOutDir: true,
  },
  base: command === 'build' ? '/ui/static/ce/' : '/',
  server: {
    port: 5174,
    proxy: {
      '/health': 'http://localhost:8090',
      '/v1': 'http://localhost:8090',
      '/admin': 'http://localhost:8090',
      '/audit': 'http://localhost:8090',
      '/metrics': 'http://localhost:8090',
      '/ui/static': 'http://localhost:8090',
      '/docs': 'http://localhost:8090',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: [resolve(__dirname, 'src/test/setup.ts')],
    css: true,
  },
}));
