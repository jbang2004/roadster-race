// Chrome for the Playwright scripts: $CHROME, else the macOS Google Chrome, else a Chromium preinstalled in the
// cloud container, else Playwright's own Chromium (Linux: `npx playwright-core install --with-deps chromium`).
import fs from 'node:fs';

const MAC = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const CLOUD = '/opt/pw-browsers/chromium';
const isFile = p => { try { return fs.statSync(p).isFile(); } catch { return false; } };
export const CHROME = process.env.CHROME || [MAC, CLOUD].find(isFile);

// ANGLE on Metal is macOS only; without a GPU (cloud containers) WebGL needs SwiftShader
export const GPU_ARGS = process.platform === 'darwin'
  ? ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist']
  : ['--enable-gpu', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'];
