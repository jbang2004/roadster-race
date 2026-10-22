// Chrome for the Playwright scripts: $CHROME, else the macOS Google Chrome, else Playwright's own Chromium
// (Linux / cloud: `npx playwright-core install --with-deps chromium`).
import fs from 'node:fs';

const MAC = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
export const CHROME = process.env.CHROME || (fs.existsSync(MAC) ? MAC : undefined);

// ANGLE on Metal is macOS only; without a GPU (cloud containers) WebGL needs SwiftShader
export const GPU_ARGS = process.platform === 'darwin'
  ? ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist']
  : ['--enable-gpu', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'];
