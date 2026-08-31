import { resolve } from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import dts from 'vite-plugin-dts';

export default defineConfig(({ command }) => {
  const isLib = command === 'build';

  return {
    root: isLib ? undefined : resolve(__dirname),
    plugins: isLib
      ? [
          react(),
          dts({
            insertTypesEntry: true,
            rollupTypes: true,
          }),
        ]
      : [react()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
      },
    },
    build: isLib
      ? {
          lib: {
            entry: resolve(__dirname, 'src/index.ts'),
            name: 'RagProtectionConsoleCore',
            formats: ['es'],
            fileName: 'console-core',
          },
          rollupOptions: {
            external: ['react', 'react-dom', 'react/jsx-runtime'],
          },
          cssCodeSplit: false,
        }
      : undefined,
    server: {
      port: 5173,
      proxy: {
        '/health': 'http://localhost:8090',
        '/v1': 'http://localhost:8090',
        '/admin': 'http://localhost:8090',
        '/audit': 'http://localhost:8090',
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: true,
    },
  };
});
