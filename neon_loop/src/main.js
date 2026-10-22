// Entry: ?scene=<name> picks src/scenes/<name>.js (default "full", the game).
import { App } from './core/app.js';

const scenes = import.meta.glob('./scenes/*.js');
const name = new URLSearchParams(location.search).get('scene') ?? 'full';
const app = new App(document.getElementById('app'));
const load = scenes[`./scenes/${name}.js`];
if (!load) throw new Error(`unknown scene "${name}" — have: ${Object.keys(scenes).join(', ')}`);
const mod = await load();
await mod.default(app);
app.start();
if (!window.__ready) await app.ready();
