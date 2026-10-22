// Showroom UI CSS. Restrained, commercial: neutral glass bar, thin type, one small accent. Same fonts / bilingual pattern as the game UI.
// Sizes are "design pixels" at 1600x900, scaled by --u (set in ui.js; 1 on phones).
const U = (n) => `calc(var(--u) * ${n}px)`;

export function buildShowroomCSS() {
  return /* css */`
.sr-ui {
  --tx: #f1f4f8; --dim: rgba(220,230,240,.62); --dim2: rgba(220,230,240,.36); --line: rgba(255,255,255,.10); --line2: rgba(255,255,255,.18);
  --glass: rgba(14,16,20,.58); --glass2: rgba(20,23,28,.72); --ac: #8fe9ff;
  --f-sans: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", system-ui, sans-serif;
  --f-cjk: "PingFang SC", "Hiragino Sans GB", "Hiragino Sans", "Microsoft YaHei", -apple-system, "SF Pro Display", system-ui, sans-serif;
  --u: 1;
  position: fixed; inset: 0; z-index: 6; pointer-events: none; overflow: hidden; color: var(--tx);
  font-family: var(--f-sans); font-weight: 300; -webkit-font-smoothing: antialiased; text-rendering: geometricPrecision;
  user-select: none; -webkit-user-select: none; font-size: ${U(14)};
}
.sr-ui *, .sr-ui *::before, .sr-ui *::after { box-sizing: border-box; margin: 0; padding: 0; }
.sr-ui button { font: inherit; color: inherit; background: none; border: 0; cursor: pointer; -webkit-tap-highlight-color: transparent; outline: none; }
.sr-ui .zh { font-family: var(--f-cjk); letter-spacing: .06em; }
.sr-ui .en { font-family: var(--f-sans); text-transform: uppercase; letter-spacing: .22em; font-weight: 400; }
.sr-ui .bi { display: flex; flex-direction: column; align-items: center; gap: ${U(3)}; line-height: 1.1; }
.sr-ui .bi .zh { font-size: ${U(14)}; font-weight: 400; color: var(--tx); }
.sr-ui .bi .en { font-size: ${U(8.5)}; color: var(--dim); letter-spacing: .24em; }
.sr-ui .glass { background: var(--glass); border: 1px solid var(--line); backdrop-filter: blur(${U(18)}) saturate(1.2); -webkit-backdrop-filter: blur(${U(18)}) saturate(1.2);
  box-shadow: 0 ${U(10)} ${U(40)} rgba(0,0,0,.28); }
.sr-ui .fade { transition: opacity .45s ease, transform .45s ease; }
.sr-ui.photo .sr-top, .sr-ui.photo .sr-bar, .sr-ui.photo .sr-pop, .sr-ui.photo .sr-hot, .sr-ui.photo .sr-card, .sr-ui.photo .sr-hint { opacity: 0 !important; pointer-events: none !important; }

/* ---------- top ---------- */
.sr-top { position: absolute; left: 0; right: 0; top: 0; display: flex; align-items: center; justify-content: space-between; padding: ${U(26)} ${U(34)}; }
.sr-top::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: ${U(120)}; background: linear-gradient(to bottom, rgba(0,0,0,.34), rgba(0,0,0,0)); pointer-events: none; }
.sr-back { pointer-events: auto; position: relative; display: flex; align-items: center; gap: ${U(12)}; padding: ${U(10)} ${U(18)} ${U(10)} ${U(14)}; border-radius: ${U(40)}; transition: background .25s; }
.sr-back:hover { background: rgba(255,255,255,.09); }
.sr-back .ch { font-size: ${U(22)}; line-height: 1; font-weight: 200; margin-top: ${U(-2)}; }
.sr-back .bi { align-items: flex-start; }
.sr-title { position: absolute; left: 50%; transform: translateX(-50%); text-align: center; top: ${U(26)}; pointer-events: none; }
.sr-title b { display: block; font-weight: 200; font-size: ${U(22)}; letter-spacing: .5em; margin-right: -.5em; text-shadow: 0 0 ${U(20)} rgba(0,0,0,.5); }
.sr-title span { display: block; margin-top: ${U(5)}; font-size: ${U(10)}; letter-spacing: .38em; margin-right: -.38em; color: var(--dim); font-weight: 400; }
.sr-name { position: relative; text-align: right; pointer-events: none; }
.sr-name .zh { font-size: ${U(14)}; font-weight: 400; }
.sr-name .en { display: block; font-size: ${U(9)}; color: var(--dim); margin-top: ${U(4)}; }

/* ---------- bar ---------- */
.sr-bar { position: absolute; left: 50%; bottom: ${U(30)}; transform: translateX(-50%); display: flex; align-items: stretch; gap: ${U(4)}; padding: ${U(7)}; border-radius: ${U(22)}; pointer-events: auto; }
.sr-bar .tab { position: relative; min-width: ${U(104)}; padding: ${U(11)} ${U(18)} ${U(12)}; border-radius: ${U(16)}; transition: background .25s; }
.sr-bar .tab:hover { background: rgba(255,255,255,.07); }
.sr-bar .tab.on { background: rgba(255,255,255,.12); }
.sr-bar .tab.on::after { content: ""; position: absolute; left: 50%; bottom: ${U(4)}; width: ${U(14)}; height: 1.5px; margin-left: ${U(-7)}; border-radius: 1px; background: var(--ac); box-shadow: 0 0 ${U(8)} var(--ac); }
.sr-bar .sep { width: 1px; margin: ${U(8)} ${U(3)}; background: var(--line); }
.sr-bar .tab.photo .zh::before { content: ""; display: inline-block; width: ${U(7)}; height: ${U(7)}; border-radius: 50%; border: 1.5px solid currentColor; margin-right: ${U(7)}; vertical-align: ${U(1)}; }

/* ---------- popovers ---------- */
.sr-pop { position: absolute; left: 50%; bottom: ${U(116)}; transform: translateX(-50%) translateY(${U(10)}); opacity: 0; pointer-events: none; border-radius: ${U(20)}; padding: ${U(16)}; transition: opacity .25s ease, transform .25s ease; max-width: calc(100vw - 24px); }
.sr-pop.on { opacity: 1; transform: translateX(-50%); pointer-events: auto; }
.sr-pop .hd { display: flex; align-items: baseline; gap: ${U(10)}; padding: 0 ${U(4)} ${U(12)}; }
.sr-pop .hd .zh { font-size: ${U(13)}; font-weight: 400; } .sr-pop .hd .en { font-size: ${U(9)}; color: var(--dim); }
.sr-grid { display: grid; gap: ${U(8)}; }
.sr-grid.views { grid-template-columns: repeat(4, ${U(118)}); }
.sr-grid.studios { grid-template-columns: repeat(3, ${U(150)}); }
.sr-chip { position: relative; padding: ${U(12)} ${U(10)} ${U(11)}; border-radius: ${U(13)}; border: 1px solid var(--line); background: rgba(255,255,255,.035); transition: background .2s, border-color .2s; }
.sr-chip:hover { background: rgba(255,255,255,.09); }
.sr-chip.on { border-color: rgba(143,233,255,.7); background: rgba(143,233,255,.09); }
.sr-chip .sw { display: block; height: ${U(46)}; border-radius: ${U(9)}; margin-bottom: ${U(10)}; border: 1px solid var(--line); }
.sr-swatches { display: flex; gap: ${U(14)}; padding: ${U(4)} ${U(6)} ${U(6)}; flex-wrap: wrap; justify-content: center; }
.sr-sw { position: relative; display: flex; flex-direction: column; align-items: center; gap: ${U(9)}; width: ${U(72)}; }
.sr-sw i { display: block; width: ${U(40)}; height: ${U(40)}; border-radius: 50%; border: 1px solid rgba(255,255,255,.28); box-shadow: inset 0 ${U(-6)} ${U(10)} rgba(0,0,0,.25), inset 0 ${U(5)} ${U(8)} rgba(255,255,255,.28); transition: transform .2s, box-shadow .2s; }
.sr-sw:hover i { transform: scale(1.06); }
.sr-sw.on i { box-shadow: 0 0 0 ${U(3)} rgba(14,16,20,.9), 0 0 0 ${U(4.5)} rgba(143,233,255,.85), inset 0 ${U(-6)} ${U(10)} rgba(0,0,0,.25), inset 0 ${U(5)} ${U(8)} rgba(255,255,255,.28); }
.sr-rows { display: grid; grid-template-columns: repeat(2, ${U(246)}); gap: ${U(6)} ${U(10)}; }
.sr-row { display: flex; align-items: center; justify-content: space-between; gap: ${U(14)}; padding: ${U(11)} ${U(14)}; border-radius: ${U(12)}; background: rgba(255,255,255,.035); border: 1px solid var(--line); text-align: left; transition: background .2s; }
.sr-row:hover { background: rgba(255,255,255,.08); }
.sr-row .bi { align-items: flex-start; }
.sr-row .sw2 { position: relative; flex: none; width: ${U(36)}; height: ${U(20)}; border-radius: ${U(10)}; background: rgba(255,255,255,.16); transition: background .25s; }
.sr-row .sw2::after { content: ""; position: absolute; left: ${U(2)}; top: ${U(2)}; width: ${U(16)}; height: ${U(16)}; border-radius: 50%; background: #fff; transition: transform .25s; box-shadow: 0 1px 3px rgba(0,0,0,.4); }
.sr-row.on .sw2 { background: var(--ac); } .sr-row.on .sw2::after { transform: translateX(${U(16)}); }

/* ---------- hotspots + card ---------- */
.sr-hot { position: absolute; inset: 0; transition: opacity .4s; }
.sr-hs { position: absolute; left: 0; top: 0; width: ${U(28)}; height: ${U(28)}; margin: ${U(-14)} 0 0 ${U(-14)}; border-radius: 50%; pointer-events: auto; opacity: 0; transition: opacity .3s; will-change: transform; border: 1.5px solid rgba(255,255,255,.55); background: rgba(255,255,255,.07); box-shadow: 0 0 0 1px rgba(0,0,0,.16), 0 0 ${U(9)} rgba(0,0,0,.36), inset 0 0 ${U(6)} rgba(0,0,0,.14); }
.sr-hs.vis { opacity: 1; }
.sr-hs::before { content: ""; position: absolute; left: 50%; top: 50%; width: ${U(5)}; height: ${U(5)}; margin: ${U(-2.5)} 0 0 ${U(-2.5)}; border-radius: 50%; background: rgba(255,255,255,.92); box-shadow: 0 0 ${U(4)} rgba(0,0,0,.35); transition: transform .25s; }
.sr-hs::after { content: ""; position: absolute; inset: ${U(-1.5)}; border-radius: 50%; border: 1px solid rgba(255,255,255,.4); animation: sr-pulse 2.8s ease-out infinite; }
.sr-hs:hover, .sr-hs.on { background: rgba(255,255,255,.16); border-color: rgba(255,255,255,.85); }
.sr-hs:hover::before, .sr-hs.on::before { transform: scale(1.3); background: #fff; }
@keyframes sr-pulse { 0% { transform: scale(.7); opacity: .7; } 80%, 100% { transform: scale(1.4); opacity: 0; } }
.sr-card { position: absolute; width: ${U(300)}; padding: ${U(18)} ${U(20)} ${U(18)}; border-radius: ${U(18)}; opacity: 0; transform: translateY(${U(8)}); pointer-events: none; transition: opacity .3s, transform .3s; }
.sr-card.on { opacity: 1; transform: none; pointer-events: auto; }
.sr-card h3 { display: flex; flex-direction: column; gap: ${U(5)}; margin-bottom: ${U(12)}; font-weight: 300; }
.sr-card h3 .zh { font-size: ${U(18)}; font-weight: 400; letter-spacing: .08em; } .sr-card h3 .en { font-size: ${U(9.5)}; color: var(--dim); }
.sr-card p { font-size: ${U(13)}; line-height: 1.72; color: rgba(236,242,248,.9); font-family: var(--f-cjk); letter-spacing: .03em; }
.sr-card p.e { margin-top: ${U(9)}; font-family: var(--f-sans); font-size: ${U(11.5)}; line-height: 1.6; color: var(--dim); letter-spacing: .01em; }
.sr-card .acts { display: flex; gap: ${U(8)}; margin-top: ${U(15)}; }
.sr-card .acts button { padding: ${U(9)} ${U(16)}; border-radius: ${U(30)}; border: 1px solid var(--line2); transition: background .2s; }
.sr-card .acts button:hover { background: rgba(255,255,255,.1); }
.sr-card .x { position: absolute; right: ${U(10)}; top: ${U(8)}; width: ${U(30)}; height: ${U(30)}; font-size: ${U(20)}; font-weight: 200; color: var(--dim); }

.sr-hint { position: absolute; left: 50%; bottom: ${U(118)}; transform: translateX(-50%); text-align: center; font-size: ${U(11)}; color: var(--dim); transition: opacity 1.2s; pointer-events: none; text-shadow: 0 0 ${U(10)} rgba(0,0,0,.6); white-space: nowrap; }
.sr-hint .en { display: block; font-size: ${U(8.5)}; margin-top: ${U(5)}; color: var(--dim2); }

/* ---------- photo mode ---------- */
.sr-ph { position: absolute; inset: 0; opacity: 0; pointer-events: none; transition: opacity .4s; }
.sr-ui.photo .sr-ph { opacity: 1; }
.sr-ph .exit { position: absolute; right: ${U(30)}; top: ${U(26)}; pointer-events: none; padding: ${U(10)} ${U(18)}; border-radius: ${U(40)}; }
.sr-ui.photo .sr-ph .exit { pointer-events: auto; }
.sr-ph .exit:hover { background: rgba(255,255,255,.09); }
.sr-ph .ap { position: absolute; left: 50%; bottom: ${U(30)}; transform: translateX(-50%); display: flex; align-items: center; gap: ${U(16)}; padding: ${U(12)} ${U(22)}; border-radius: ${U(40)}; pointer-events: none; opacity: .0; transition: opacity .4s; }
.sr-ui.photo .sr-ph .ap { pointer-events: auto; opacity: 1; }
.sr-ph .ap input[type=range] { -webkit-appearance: none; appearance: none; width: ${U(170)}; height: 2px; background: rgba(255,255,255,.3); border-radius: 2px; outline: none; }
.sr-ph .ap input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; width: ${U(16)}; height: ${U(16)}; border-radius: 50%; background: #fff; cursor: pointer; box-shadow: 0 1px 4px rgba(0,0,0,.5); }
.sr-ph .ap input[type=range]::-moz-range-thumb { width: ${U(16)}; height: ${U(16)}; border-radius: 50%; background: #fff; border: 0; cursor: pointer; }
.sr-ph .tip { position: absolute; left: 50%; top: ${U(34)}; transform: translateX(-50%); text-align: center; pointer-events: none; transition: opacity 1.2s; text-shadow: 0 0 ${U(10)} rgba(0,0,0,.6); }
.sr-ph .ring { position: absolute; width: ${U(70)}; height: ${U(70)}; margin: ${U(-35)} 0 0 ${U(-35)}; border: 1.5px solid rgba(255,255,255,.9); border-radius: 12%; opacity: 0; pointer-events: none; }
.sr-ph .ring.go { animation: sr-focus 1.5s ease-out forwards; }
@keyframes sr-focus { 0% { opacity: 0; transform: scale(1.8); } 18% { opacity: 1; transform: scale(1); } 70% { opacity: 1; transform: scale(1); } 100% { opacity: 0; transform: scale(.94); } }

/* ---------- loading ---------- */
.sr-load { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: ${U(14)}; background: #07080a; opacity: 1; transition: opacity .9s ease; pointer-events: auto; }
.sr-load.off { opacity: 0; pointer-events: none; }
.sr-load .zh { font-size: ${U(15)}; letter-spacing: .3em; } .sr-load .en { font-size: ${U(9.5)}; color: var(--dim); }
.sr-load .bar { width: ${U(180)}; height: 1px; background: rgba(255,255,255,.16); overflow: hidden; margin-top: ${U(8)}; }
.sr-load .bar i { display: block; height: 100%; width: 40%; background: rgba(255,255,255,.85); animation: sr-ld 1.4s ease-in-out infinite; }
@keyframes sr-ld { 0% { transform: translateX(-100%); } 100% { transform: translateX(250%); } }

/* ---------- phones ---------- */
@media (max-width: 760px), (max-aspect-ratio: 4/5) {
  .sr-ui { --u: 1; }
  .sr-top { padding: 14px 12px; }
  .sr-title { top: 16px; } .sr-title b { font-size: 16px; letter-spacing: .4em; } .sr-title span { font-size: 8.5px; }
  .sr-back { padding: 8px 12px 8px 8px; } .sr-back .bi .en { display: none; } .sr-back .bi .zh { font-size: 13px; }
  .sr-name { display: none; }
  .sr-bar { left: 8px; right: 8px; bottom: 12px; transform: none; justify-content: space-between; gap: 0; padding: 5px; border-radius: 18px; }
  .sr-bar .tab { min-width: 0; flex: 1; padding: 9px 2px 10px; }
  .sr-bar .tab .zh { font-size: 12.5px; } .sr-bar .tab .en { font-size: 7.5px; letter-spacing: .14em; }
  .sr-bar .sep { display: none; }
  .sr-pop { left: 8px; right: 8px; bottom: 76px; transform: translateY(10px); padding: 12px; border-radius: 18px; max-height: 52vh; overflow-y: auto; }
  .sr-pop.on { transform: none; }
  .sr-grid.views { grid-template-columns: repeat(4, 1fr); } .sr-grid.studios { grid-template-columns: repeat(3, 1fr); }
  .sr-chip { padding: 10px 4px 9px; } .sr-chip .sw { height: 34px; margin-bottom: 8px; }
  .sr-chip .bi .zh { font-size: 12px; } .sr-chip .bi .en { font-size: 7px; letter-spacing: .12em; }
  .sr-sw { width: 64px; } .sr-sw i { width: 38px; height: 38px; }
  .sr-rows { grid-template-columns: 1fr 1fr; gap: 6px; }
  .sr-row { padding: 9px 10px; gap: 8px; } .sr-row .sw2 { width: 32px; height: 18px; border-radius: 9px; } .sr-row .sw2::after { width: 14px; height: 14px; } .sr-row.on .sw2::after { transform: translateX(14px); }
  .sr-row .bi .zh { font-size: 12.5px; } .sr-row .bi .en { font-size: 7.5px; letter-spacing: .14em; }
  .sr-card { width: calc(100vw - 24px) !important; left: 12px !important; right: 12px; top: auto !important; bottom: 80px; padding: 16px; }
  .sr-card h3 .zh { font-size: 16px; } .sr-card p { font-size: 12.5px; } .sr-card p.e { font-size: 11px; }
  .sr-hs { width: 30px; height: 30px; margin: -15px 0 0 -15px; }
  .sr-hint { bottom: 82px; font-size: 10.5px; }
  .sr-ph .exit { right: 12px; top: 14px; } .sr-ph .ap { bottom: 18px; padding: 10px 16px; gap: 12px; } .sr-ph .ap input[type=range] { width: 130px; }
}
`;
}
