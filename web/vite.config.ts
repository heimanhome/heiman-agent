import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tsconfigPaths from "vite-tsconfig-paths";
import { traeBadgePlugin } from 'vite-plugin-trae-solo-badge';
import { resolve } from 'path';
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, statSync } from 'fs';

export default defineConfig({
  build: {
    sourcemap: 'hidden',
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
      },
    },
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['tests/**/*.test.ts', 'tests/**/*.test.tsx'],
    setupFiles: ['./tests/test-setup.tsx'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
    },
  },
  plugins: [
    react(),
    traeBadgePlugin({
      variant: 'dark',
      position: 'bottom-right',
      prodOnly: true,
      clickable: true,
      clickUrl: 'https://www.trae.ai/solo?showJoin=1',
      autoTheme: true,
      autoThemeTarget: '#root'
    }), 
    tsconfigPaths(),
    {
      name: 'copy-locales',
      buildStart() {
        this.addWatchFile(resolve(__dirname, 'src/i18n/locales'));
      },
      generateBundle(options) {
        const localesDir = resolve(__dirname, 'src/i18n/locales');
        const outDir = resolve(options.dir || 'dist', 'locales');
        
        if (!existsSync(outDir)) {
          mkdirSync(outDir, { recursive: true });
        }
        
        const copyDir = (src: string, dest: string) => {
          if (!existsSync(dest)) {
            mkdirSync(dest, { recursive: true });
          }
          const files = readdirSync(src);
          files.forEach(file => {
            const srcPath = resolve(src, file);
            const destPath = resolve(dest, file);
            const stat = statSync(srcPath);
            if (stat.isDirectory()) {
              copyDir(srcPath, destPath);
            } else {
              const content = readFileSync(srcPath);
              writeFileSync(destPath, content);
            }
          });
        };
        
        copyDir(localesDir, outDir);
      },
    },
  ],
})
