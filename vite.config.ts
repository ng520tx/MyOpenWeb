import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { execSync } from 'child_process';

function getApiProxyTarget() {
  if (process.env.MOW_API_TARGET) {
    return process.env.MOW_API_TARGET;
  }

  if (process.platform === 'win32') {
    try {
      const ip = execSync('wsl.exe hostname -I', { stdio: ['ignore', 'pipe', 'ignore'] })
        .toString()
        .trim()
        .split(/\s+/)[0];
      if (ip) {
        return `http://${ip}:8000`;
      }
    } catch {
      // Fall back to localhost when WSL is unavailable.
    }
  }

  return 'http://127.0.0.1:8000';
}

const apiProxyTarget = getApiProxyTarget();

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
});
