// All UI CSS. Sizes are in "design pixels" at 1600×900 and scale with --u (set from the viewport in index.js).
// Palette: cyan/white on dark glass; magenta for records; amber for warnings; red only for danger.
const U = (n) => `calc(var(--u) * ${n}px)`;

export function buildCSS() {
  return /* css */`
.nl-ui {
  --cy: #3ee8ff; --cy2: #8ff3ff; --mg: #ff49d6; --vi: #b88cff; --am: #ffb340; --rd: #ff3b52; --gr: #5dffc0;
  --tx: #eaf6ff; --dim: rgba(188,218,236,.58); --dim2: rgba(188,218,236,.34);
  --glass: rgba(5,10,18,.52); --line: rgba(130,225,255,.16);
  --f-sans: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", system-ui, sans-serif;
  --f-cjk: "PingFang SC", "Hiragino Sans GB", "Hiragino Sans", "Microsoft YaHei", -apple-system, "SF Pro Display", system-ui, sans-serif;
  --u: 1;
  position: fixed; inset: 0; z-index: 5; pointer-events: none; overflow: hidden;
  font-family: var(--f-sans); color: var(--tx); font-weight: 300;
  -webkit-font-smoothing: antialiased; text-rendering: geometricPrecision; user-select: none; -webkit-user-select: none;
  font-size: ${U(14)};
}
.nl-ui * { box-sizing: border-box; margin: 0; padding: 0; }
.nl-ui .zh { font-family: var(--f-cjk); letter-spacing: .06em; }
.nl-ui .en { font-family: var(--f-sans); text-transform: uppercase; letter-spacing: .26em; font-weight: 400; }
.nl-ui .num { font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1, "zero" 0; }
.nl-ui .cap { font-size: ${U(11)}; letter-spacing: .24em; text-transform: uppercase; color: var(--dim); font-weight: 400; white-space: nowrap; }
.nl-ui .cap .zh { font-size: ${U(12)}; letter-spacing: .2em; margin-right: ${U(8)}; color: rgba(214,236,248,.78); text-transform: none; font-weight: 400; }
.nl-ui .hide { display: none !important; }

/* ---------- full-screen atmospherics ---------- */
.nl-edge, .nl-edge2, .nl-flash, .nl-vig { position: absolute; inset: 0; pointer-events: none; }
.nl-edge { opacity: 0; will-change: opacity;
  box-shadow: inset 0 0 ${U(160)} ${U(12)} rgba(34,206,255,.46), inset 0 0 ${U(44)} 0 rgba(120,240,255,.26); }
.nl-edge2 { opacity: 0; will-change: opacity;
  background: linear-gradient(to top, rgba(255,60,120,.30), rgba(255,60,120,0) 22%), linear-gradient(to bottom, rgba(255,60,120,.10), rgba(255,60,120,0) 12%); }
.nl-flash { opacity: 0; background: radial-gradient(ellipse at 50% 50%, rgba(255,40,60,0) 40%, rgba(255,40,60,.55) 100%); will-change: opacity; }
.nl-vig { background: radial-gradient(ellipse 130% 120% at 50% 50%, rgba(0,0,0,0) 58%, rgba(1,3,8,.42) 100%); opacity: 0; transition: opacity .6s; }
.nl-vig.on { opacity: 1; }

/* ---------- HUD ---------- */
.nl-hud { position: absolute; left: 50%; top: 0; height: 100%; width: min(100%, calc(100vh * 1.92)); transform: translateX(-50%);
  opacity: 0; transition: opacity .6s ease; }
.nl-hud.on { opacity: 1; }
.nl-hud.dim { opacity: .35; }
.nl-hud .blk { position: absolute; }
.nl-hud .scrim { position: absolute; pointer-events: none; }
.scrim.tl { left: 0; top: 0; width: ${U(700)}; height: ${U(380)}; background: radial-gradient(ellipse 100% 100% at 0% 0%, rgba(2,5,10,.78) 0%, rgba(2,5,10,.46) 42%, rgba(2,5,10,0) 100%); }
.scrim.tr { right: 0; top: 0; width: ${U(640)}; height: ${U(380)}; background: radial-gradient(ellipse 100% 100% at 100% 0%, rgba(2,5,10,.78) 0%, rgba(2,5,10,.46) 42%, rgba(2,5,10,0) 100%); }
.scrim.bl { left: 0; bottom: 0; width: ${U(560)}; height: ${U(420)}; background: radial-gradient(ellipse 100% 100% at 0% 100%, rgba(2,5,10,.74) 0%, rgba(2,5,10,.42) 42%, rgba(2,5,10,0) 100%); }
.scrim.br { right: 0; bottom: 0; width: ${U(700)}; height: ${U(520)}; background: radial-gradient(ellipse 100% 100% at 100% 100%, rgba(2,5,10,.80) 0%, rgba(2,5,10,.48) 42%, rgba(2,5,10,0) 100%); }
.scrim.nt { left: 50%; top: ${U(60)}; width: ${U(1000)}; height: ${U(300)}; transform: translateX(-50%); background: radial-gradient(ellipse 50% 50% at 50% 50%, rgba(2,5,10,.72), rgba(2,5,10,0)); opacity: 0; transition: opacity .4s; }
.nl-hud.note-on .scrim.nt { opacity: 1; }
.scrim.bc { left: 50%; bottom: 0; width: ${U(900)}; height: ${U(150)}; transform: translateX(-50%); background: radial-gradient(ellipse 50% 100% at 50% 100%, rgba(2,5,10,.5), rgba(2,5,10,0)); }

.tl { left: ${U(56)}; top: ${U(40)}; display: flex; gap: ${U(46)}; align-items: flex-start; }
.stat .cap { display: flex; align-items: center; gap: 0; margin-bottom: ${U(2)}; }
.stat .cap::before { content: ""; width: ${U(18)}; height: 1px; background: var(--cy); margin-right: ${U(10)}; box-shadow: 0 0 ${U(6)} var(--cy); }
.stat .big { display: flex; align-items: baseline; line-height: 1; font-weight: 200; }
.stat .big b { font-weight: 200; font-size: ${U(92)}; letter-spacing: -.02em; text-shadow: 0 0 ${U(24)} rgba(62,232,255,.28); }
.stat .big i { font-style: normal; font-size: ${U(34)}; color: var(--dim); margin-left: ${U(8)}; font-weight: 300; }
.stat.pos .big b.up { animation: nl-bump .9s ease-out; }
.stat.pos .big b.dn { animation: nl-bumpd .9s ease-out; }
@keyframes nl-bump { 0% { color: var(--gr); transform: translateY(${U(-6)}); text-shadow: 0 0 ${U(30)} var(--gr); } 100% { color: var(--tx); transform: none; } }
@keyframes nl-bumpd { 0% { color: var(--am); transform: translateY(${U(6)}); text-shadow: 0 0 ${U(30)} var(--am); } 100% { color: var(--tx); transform: none; } }

.tr { right: ${U(56)}; top: ${U(40)}; text-align: right; min-width: ${U(300)}; }
.tr .cap { justify-content: flex-end; display: flex; margin-bottom: ${U(2)}; }
.tr .cur { font-size: ${U(58)}; font-weight: 200; line-height: 1.05; letter-spacing: -.01em; white-space: nowrap; text-shadow: 0 0 ${U(22)} rgba(62,232,255,.22); }
.tr .cur small { font-size: .62em; color: var(--dim); font-weight: 200; letter-spacing: 0; }
.tr .rule { height: 1px; margin: ${U(10)} 0 ${U(10)} auto; width: 100%; background: linear-gradient(to left, rgba(130,225,255,.5), rgba(130,225,255,0)); }
.tr .row { display: flex; justify-content: flex-end; align-items: baseline; gap: ${U(18)}; line-height: 1.5; }
.tr .row .cap { margin: 0; }
.tr .row .v { font-size: ${U(22)}; font-weight: 300; min-width: ${U(118)}; text-align: right; letter-spacing: .01em; }
.tr .row .v small { color: var(--dim); font-size: .78em; }
.tr .row.best .v { color: var(--vi); }
.tr .row.best .cap .zh { color: rgba(205,170,255,.9); }
.tr .row.best .v.flash { animation: nl-vflash 1.6s ease-out; }
@keyframes nl-vflash { 0%, 30% { color: #fff; text-shadow: 0 0 ${U(18)} var(--mg); } 100% { color: var(--vi); text-shadow: none; } }

.bl { left: ${U(56)}; bottom: ${U(44)}; }
.mapwrap { position: relative; width: ${U(232)}; height: ${U(232)}; border-radius: ${U(14)}; background: var(--glass); border: 1px solid var(--line);
  box-shadow: 0 ${U(10)} ${U(40)} rgba(0,0,0,.35), inset 0 0 ${U(30)} rgba(30,120,160,.10); overflow: hidden; }
.mapwrap canvas { position: absolute; inset: 0; width: 100%; height: 100%; }
.mapzone { margin-top: ${U(10)}; display: flex; align-items: baseline; gap: ${U(10)}; transition: opacity .4s; }
.mapzone .zh { font-size: ${U(15)}; color: rgba(225,243,252,.9); letter-spacing: .12em; }
.mapzone .en { font-size: ${U(10.5)}; color: var(--dim); letter-spacing: .24em; }

.br { right: ${U(48)}; bottom: ${U(40)}; width: ${U(396)}; }
.gauge { position: relative; width: ${U(396)}; height: ${U(312)}; }
.gauge svg { position: absolute; left: 0; top: 0; width: ${U(396)}; height: ${U(312)}; overflow: visible; }
.gauge .readout { position: absolute; left: 0; right: 0; top: ${U(96)}; text-align: center; }
.gauge .spd { font-size: ${U(116)}; font-weight: 200; line-height: 1; letter-spacing: -.035em; padding-right: ${U(8)};
  text-shadow: 0 0 ${U(14)} rgba(0,6,14,.55), 0 0 ${U(34)} rgba(62,232,255,.30); }
.gauge .unit { margin-top: ${U(2)}; display: flex; justify-content: center; align-items: baseline; gap: ${U(10)}; }
.gauge .unit .en { font-size: ${U(13)}; color: var(--cy2); letter-spacing: .42em; margin-right: -.2em; }
.gauge .unit .zh { font-size: ${U(12)}; color: var(--dim); }
.gauge .unit .mode { display: inline-block; min-width: ${U(22)}; height: ${U(22)}; line-height: ${U(21)}; text-align: center; border: 1px solid var(--dim2); border-radius: 50%; font-size: ${U(12)}; font-weight: 500; color: var(--dim); margin-right: ${U(6)}; align-self: center; }
.gauge .unit .mode.r { color: var(--am); border-color: var(--am); }
.power { position: relative; margin-top: ${U(-10)}; padding: 0 ${U(10)} 0 ${U(10)}; }
.power .hd { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: ${U(7)}; }
.power .hd .kw { font-size: ${U(17)}; font-weight: 300; letter-spacing: .02em; }
.power .hd .kw small { font-size: .62em; color: var(--dim); margin-left: ${U(4)}; letter-spacing: .2em; }
.power .hd .cap.reg { color: var(--gr); }
.power .bar { position: relative; height: ${U(5)}; background: rgba(160,220,240,.10); border-radius: 3px; overflow: hidden; }
.power .bar .zero { position: absolute; top: ${U(-2)}; bottom: ${U(-2)}; width: 1px; background: rgba(220,245,255,.55); z-index: 3; }
.power .bar .f { position: absolute; top: 0; bottom: 0; transform-origin: left center; will-change: transform; }
.power .bar .drv { background: linear-gradient(to right, var(--cy), #d8fbff); box-shadow: 0 0 ${U(10)} rgba(62,232,255,.7); }
.gas { position: relative; margin-top: ${U(12)}; padding: 0 ${U(10)}; transition: opacity .3s; }
.gas .hd { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: ${U(6)}; }
.gas .hd .sec { font-size: ${U(15)}; font-weight: 300; }
.gas .hd .sec small { font-size: .62em; color: var(--dim); margin-left: ${U(3)}; letter-spacing: .2em; }
.gas .bar { position: relative; height: ${U(4)}; background: rgba(200,225,255,.10); border-radius: 2px; overflow: hidden; }
.gas .bar .f { position: absolute; inset: 0; transform-origin: left center; will-change: transform;
  background: linear-gradient(to right, #7fa8d8, #e8f4ff); box-shadow: 0 0 ${U(8)} rgba(190,225,255,.45); }
.gas .bar i { position: absolute; top: 0; bottom: 0; width: 2px; margin-left: -1px; background: rgba(5,8,14,.85); z-index: 2; }
.gas.fill .bar .f { opacity: .7; }
.gas.on .cap, .gas.on .sec { color: #e8f4ff; text-shadow: 0 0 ${U(14)} rgba(190,225,255,.75); }
.gas.on .bar .f { background: linear-gradient(to right, #b8d8ff, #fff); box-shadow: 0 0 ${U(14)} rgba(220,240,255,.9); animation: nl-gas .12s linear infinite alternate; }
.gas.low .bar .f { background: linear-gradient(to right, #c0623a, var(--am)); box-shadow: 0 0 ${U(8)} rgba(255,179,64,.5); }
.gas.low .sec { color: var(--am); }
.gas.empty .cap, .gas.empty .sec { color: var(--rd); animation: nl-wrong .8s ease-in-out infinite; }
@keyframes nl-gas { from { opacity: 1; } to { opacity: .78; } }
.power .bar .reg { background: linear-gradient(to left, var(--gr), #2aa8a0); transform-origin: right center; box-shadow: 0 0 ${U(10)} rgba(93,255,192,.6); }

.gaps { left: 50%; bottom: ${U(30)}; transform: translateX(-50%); display: flex; gap: ${U(34)}; align-items: center; white-space: nowrap; }
.gap { display: flex; align-items: baseline; gap: ${U(10)}; padding: ${U(7)} ${U(16)}; background: var(--glass); border: 1px solid var(--line); border-radius: ${U(30)}; transition: opacity .3s; }
.gap .arr { font-size: ${U(11)}; color: var(--dim); }
.gap .nm { font-size: ${U(14)}; letter-spacing: .12em; color: rgba(225,243,252,.88); max-width: ${U(170)}; overflow: hidden; text-overflow: ellipsis; }
.gap .t { font-size: ${U(18)}; min-width: ${U(62)}; text-align: right; font-weight: 300; }
.gap.a .t { color: var(--am); }
.gap.b .t { color: var(--cy2); }
.gap.none { opacity: .22; }
.gap .sw { width: ${U(8)}; height: ${U(8)}; border-radius: 50%; align-self: center; }

.notes { left: 50%; top: ${U(150)}; transform: translateX(-50%); width: ${U(900)}; text-align: center; height: ${U(160)}; }
.note { position: absolute; left: 0; right: 0; top: 0; opacity: 0; display: flex; flex-direction: column; align-items: center; gap: ${U(4)}; }
.note .cap { color: var(--cy2); letter-spacing: .5em; font-size: ${U(13)}; font-weight: 500; text-shadow: 0 0 ${U(10)} rgba(0,4,10,.9); }
.note .main { font-size: ${U(50)}; font-weight: 300; line-height: 1.15; letter-spacing: .14em; text-shadow: 0 0 ${U(14)} rgba(0,5,12,.85), 0 0 ${U(30)} rgba(62,232,255,.55); }
.note .sub { font-size: ${U(21)}; color: rgba(228,244,252,.95); text-shadow: 0 0 ${U(12)} rgba(0,4,10,.9); letter-spacing: .08em; margin-top: ${U(2)}; }
.note .ln { width: ${U(420)}; height: 1px; margin-top: ${U(10)}; background: linear-gradient(to right, rgba(62,232,255,0), rgba(62,232,255,.8), rgba(62,232,255,0)); }
.note.rec .cap { color: var(--mg); } .note.rec .main { text-shadow: 0 0 ${U(14)} rgba(0,5,12,.85), 0 0 ${U(30)} rgba(255,73,214,.6); } .note.rec .ln { background: linear-gradient(to right, rgba(255,73,214,0), rgba(255,73,214,.9), rgba(255,73,214,0)); }
.note.up .cap { color: var(--gr); } .note.up .ln { background: linear-gradient(to right, rgba(93,255,192,0), rgba(93,255,192,.9), rgba(93,255,192,0)); }
.note.dn .cap { color: var(--am); } .note.dn .main { text-shadow: 0 0 ${U(26)} rgba(255,179,64,.4); } .note.dn .ln { background: linear-gradient(to right, rgba(255,179,64,0), rgba(255,179,64,.85), rgba(255,179,64,0)); }
.note.fin .cap { color: var(--am); } .note.fin .main { font-weight: 300; text-shadow: 0 0 ${U(30)} rgba(255,179,64,.5); } .note.fin .ln { background: linear-gradient(to right, rgba(255,179,64,0), rgba(255,179,64,.9), rgba(255,179,64,0)); }
.note.dist .main { font-size: ${U(30)}; letter-spacing: .3em; } .note.dist .cap { color: var(--dim); }
.note.show { animation: nl-note var(--dur, 2.8s) cubic-bezier(.2,.7,.2,1) forwards; }
@keyframes nl-note {
  0% { opacity: 0; transform: translateY(${U(10)}) scale(.985); letter-spacing: .3em; }
  9% { opacity: 1; transform: none; }
  84% { opacity: 1; }
  100% { opacity: 0; transform: translateY(${U(-6)}); }
}
.wrong { left: 50%; top: ${U(300)}; transform: translateX(-50%); text-align: center; opacity: 0; transition: opacity .25s; padding: ${U(30)} ${U(120)}; background: radial-gradient(ellipse 50% 50% at 50% 50%, rgba(18,0,4,.72), rgba(18,0,4,0)); }
.wrong.on { opacity: 1; animation: nl-wrong .7s steps(1) infinite; }
.wrong .main { font-size: ${U(84)}; font-weight: 300; letter-spacing: .3em; margin-right: -.3em; color: #ff5468; text-shadow: 0 0 ${U(12)} rgba(20,0,6,.9), 0 0 ${U(34)} rgba(255,59,82,.8); }
.wrong .cap { color: #ff7585; letter-spacing: .6em; margin-right: -.6em; font-size: ${U(14)}; font-weight: 500; }
@keyframes nl-wrong { 0% { opacity: 1; } 55% { opacity: .35; } }

.toast { right: ${U(56)}; top: ${U(246)}; text-align: right; opacity: 0; transition: opacity .35s; display: flex; gap: ${U(10)}; align-items: baseline; }
.toast.on { opacity: 1; }
.toast .zh { font-size: ${U(15)}; letter-spacing: .12em; }
.toast .cap { margin: 0; }

/* ---------- countdown ---------- */
.nl-count { position: absolute; left: 0; right: 0; top: 0; bottom: 0; display: flex; align-items: center; justify-content: center; pointer-events: none; padding-bottom: ${U(120)}; }
.cd { position: relative; text-align: center; opacity: 0; }
.cd .d { font-size: ${U(280)}; font-weight: 100; line-height: 1; letter-spacing: -.02em; text-shadow: 0 0 ${U(60)} rgba(62,232,255,.55), 0 0 ${U(10)} rgba(220,250,255,.5); }
.cd .ring { position: absolute; left: 50%; top: 50%; width: ${U(360)}; height: ${U(360)}; margin: ${U(-180)} 0 0 ${U(-180)}; border-radius: 50%; border: 1px solid rgba(62,232,255,.5); opacity: 0; }
.cd .sub { margin-top: ${U(-6)}; font-size: ${U(15)}; letter-spacing: .6em; color: var(--cy2); }
.cd.go .d { font-weight: 200; letter-spacing: .06em; background: linear-gradient(to bottom, #fff, #8ff3ff 70%, #3ee8ff); -webkit-background-clip: text; background-clip: text; color: transparent; text-shadow: none; filter: drop-shadow(0 0 ${U(30)} rgba(62,232,255,.7)); }
.cd.tick { animation: nl-cd 1s cubic-bezier(.15,.7,.2,1) forwards; }
.cd.tick .ring { animation: nl-ring 1s ease-out forwards; }
.cd.go.tick { animation: nl-go 1.5s cubic-bezier(.15,.7,.2,1) forwards; }
@keyframes nl-cd { 0% { opacity: 0; transform: scale(1.5); } 14% { opacity: 1; transform: scale(1); } 70% { opacity: 1; transform: scale(.96); } 100% { opacity: 0; transform: scale(.86); } }
@keyframes nl-go { 0% { opacity: 0; transform: scale(.8); } 12% { opacity: 1; transform: scale(1.06); } 28% { transform: scale(1); } 70% { opacity: 1; } 100% { opacity: 0; transform: scale(1.35); } }
@keyframes nl-ring { 0% { opacity: .9; transform: scale(.55); } 100% { opacity: 0; transform: scale(1.5); } }
.cd.hold { opacity: 1; animation: none; } .cd.hold .ring { opacity: .35; animation: none; }

/* ---------- screens (title / pause / results) ---------- */
.scr { position: absolute; inset: 0; opacity: 0; visibility: hidden; transition: opacity .55s ease, visibility 0s linear .55s; }
.scr.on { opacity: 1; visibility: visible; transition: opacity .55s ease, visibility 0s; }
.scr .safe { position: absolute; left: 50%; top: 0; height: 100%; width: min(100%, calc(100vh * 1.92)); transform: translateX(-50%); }

/* title */
.nl-title .shade { position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(to right, rgba(2,5,10,.88) 0%, rgba(2,5,10,.74) 26%, rgba(2,5,10,.30) 50%, rgba(2,5,10,0) 68%),
              linear-gradient(to top, rgba(2,5,10,.7), rgba(2,5,10,0) 28%), linear-gradient(to bottom, rgba(2,5,10,.55), rgba(2,5,10,0) 22%); }
.nl-title .logo { position: absolute; left: ${U(96)}; top: ${U(62)}; }
.logo .eye { display: flex; align-items: center; gap: ${U(14)}; margin-bottom: ${U(16)}; }
.logo .eye::before { content: ""; width: ${U(44)}; height: 1px; background: var(--cy); box-shadow: 0 0 ${U(8)} var(--cy); }
.logo .eye span { font-size: ${U(11.5)}; letter-spacing: .5em; color: var(--cy2); font-weight: 400; }
.logo h1 { font-family: var(--f-cjk); font-weight: 200; font-size: ${U(124)}; line-height: 1.02; letter-spacing: .12em; margin-left: ${U(-6)}; white-space: nowrap;
  color: #f2fdff; text-shadow: 0 0 ${U(10)} rgba(190,250,255,.65), 0 0 ${U(34)} rgba(40,210,255,.55), 0 0 ${U(90)} rgba(40,150,255,.35); }
.logo h1 span { display: inline-block; }
.logo h1 .fl1 { animation: nl-fl1 7.3s infinite; }
.logo h1 .fl2 { animation: nl-fl2 11.1s infinite; color: #ffe9fb; text-shadow: 0 0 ${U(10)} rgba(255,190,245,.7), 0 0 ${U(36)} rgba(255,73,214,.6), 0 0 ${U(90)} rgba(255,40,190,.35); }
@keyframes nl-fl1 { 0%, 88%, 100% { opacity: 1; } 89% { opacity: .28; } 90% { opacity: 1; } 91.5% { opacity: .5; } 92.5%, 99% { opacity: 1; } }
@keyframes nl-fl2 { 0%, 61%, 100% { opacity: 1; } 62% { opacity: .2; } 63% { opacity: .9; } 64% { opacity: .3; } 65.5% { opacity: 1; } 80% { opacity: 1; } 80.6% { opacity: .5; } 81.4% { opacity: 1; } }
.logo .sub { font-size: ${U(30)}; font-weight: 200; letter-spacing: .78em; margin-top: ${U(4)}; margin-left: ${U(4)}; color: rgba(225,245,255,.9); font-family: var(--f-sans); }
.logo .sub b { font-weight: 500; color: #fff; }
.logo .tag { margin-top: ${U(16)}; font-size: ${U(12)}; letter-spacing: .34em; color: rgba(205,230,244,.7); text-shadow: 0 0 ${U(10)} rgba(0,4,10,.9); }

.menu { position: absolute; left: ${U(96)}; top: ${U(352)}; width: ${U(520)}; }
.mi { position: relative; display: flex; align-items: center; padding: ${U(7)} ${U(18)} ${U(7)} ${U(22)}; cursor: pointer; pointer-events: auto; border-radius: ${U(4)};
  color: rgba(214,234,246,.74); transition: color .18s, background .18s; text-shadow: 0 0 ${U(12)} rgba(0,4,10,.8); }
.mi::before { content: ""; position: absolute; left: 0; top: 14%; bottom: 14%; width: 2px; background: var(--cy); box-shadow: 0 0 ${U(10)} var(--cy); opacity: 0; transform: scaleY(.3); transition: opacity .18s, transform .22s; }
.mi.f { color: #fff; background: linear-gradient(to right, rgba(62,232,255,.14), rgba(62,232,255,0) 92%); }
.mi.f::before { opacity: 1; transform: none; }
.mi .l { display: flex; flex-direction: column; gap: ${U(2)}; flex: 1; }
.mi .l .zh { font-size: ${U(21)}; font-weight: 300; letter-spacing: .16em; }
.mi .l .en { font-size: ${U(10)}; letter-spacing: .36em; color: var(--dim2); font-weight: 400; transition: color .18s; }
.mi.f .l .en { color: var(--cy2); }
.mi.primary { margin-bottom: ${U(10)}; padding-top: ${U(10)}; padding-bottom: ${U(12)}; }
.mi.primary .l .zh { font-size: ${U(40)}; font-weight: 200; letter-spacing: .24em; }
.mi.primary .l .en { font-size: ${U(12)}; letter-spacing: .5em; }
.mi .v { display: flex; align-items: center; gap: ${U(14)}; font-size: ${U(20)}; min-width: ${U(210)}; justify-content: flex-end; }
.mi .v .ar { font-size: ${U(17)}; color: var(--dim2); transition: color .18s, transform .18s; cursor: pointer; padding: 0 ${U(4)}; }
.mi.f .v .ar { color: var(--cy2); }
.mi .v .ar:hover { color: #fff; transform: scale(1.25); }
.mi .v .val { min-width: ${U(110)}; text-align: center; display: flex; flex-direction: column; align-items: center; gap: ${U(1)}; }
.mi .v .val .zh { font-size: ${U(20)}; letter-spacing: .12em; font-weight: 300; }
.mi .v .val .en { font-size: ${U(9)}; letter-spacing: .34em; color: var(--dim); }
.mi .v .val.single .zh { font-size: ${U(24)}; font-weight: 200; }
.segs { display: flex; gap: ${U(3.5)}; align-items: flex-end; height: ${U(22)}; }
.segs i { width: ${U(5)}; background: rgba(160,220,240,.22); border-radius: 1px; transition: background .15s, box-shadow .15s; }
.segs i.o { background: var(--cy); box-shadow: 0 0 ${U(7)} rgba(62,232,255,.8); }
.mi.f .segs i.o { background: #d8fbff; }
.mi.sep { margin-top: ${U(8)}; }

.hints { position: absolute; left: ${U(96)}; bottom: ${U(44)}; display: flex; gap: ${U(30)}; align-items: center; color: var(--dim); }
.hint { display: flex; align-items: center; gap: ${U(10)}; font-size: ${U(11)}; letter-spacing: .22em; }
.kbd { display: inline-block; min-width: ${U(24)}; padding: ${U(3)} ${U(8)}; text-align: center; border: 1px solid rgba(190,230,250,.4); border-bottom-width: 2px; border-radius: ${U(4)};
  font-size: ${U(11)}; color: rgba(225,243,252,.9); letter-spacing: .06em; font-weight: 500; font-family: var(--f-sans); text-transform: none; background: rgba(255,255,255,.04); }
.nl-title .ver { position: absolute; right: ${U(56)}; bottom: ${U(44)}; text-align: right; font-size: ${U(11)}; letter-spacing: .3em; color: var(--dim2); line-height: 1.9; }

.help { position: absolute; right: ${U(72)}; top: ${U(150)}; width: ${U(780)}; padding: ${U(30)} ${U(36)} ${U(22)}; background: rgba(4,9,16,.80); border: 1px solid var(--line); border-radius: ${U(16)};
  opacity: 0; transform: translateX(${U(24)}); transition: opacity .35s, transform .35s; pointer-events: none; box-shadow: 0 ${U(20)} ${U(80)} rgba(0,0,0,.5); }
.help.on { opacity: 1; transform: none; pointer-events: auto; }
.help h3 { font-weight: 200; font-size: ${U(30)}; letter-spacing: .24em; margin-bottom: ${U(4)}; font-family: var(--f-cjk); }
.help h3 + .cap { margin-bottom: ${U(6)}; }
.help .cols { display: grid; grid-template-columns: 1.25fr 1fr; gap: 0 ${U(40)}; }
.help .sec { margin: ${U(14)} 0 ${U(6)}; display: flex; align-items: center; gap: ${U(12)}; }
.help .sec::after { content: ""; flex: 1; height: 1px; background: var(--line); }
.help .r { display: flex; align-items: center; justify-content: space-between; gap: ${U(14)}; padding: ${U(7)} 0; border-bottom: 1px solid rgba(130,225,255,.07); }
.help .r .k { display: flex; gap: ${U(6)}; }
.help .r .d { text-align: right; display: flex; flex-direction: column; gap: ${U(1)}; }
.help .r .d .zh { font-size: ${U(16)}; letter-spacing: .12em; }
.help .r .d .en { font-size: ${U(9.5)}; letter-spacing: .26em; color: var(--dim); }
.help .back { margin-top: ${U(16)}; text-align: right; color: var(--dim); font-size: ${U(11)}; letter-spacing: .24em; }

/* pause */
.nl-pause .shade { position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 50%, rgba(2,5,10,.55), rgba(2,5,10,.82)); }
.pbox { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -52%); width: ${U(520)}; text-align: center; }
.pbox .eye { font-size: ${U(11.5)}; letter-spacing: .6em; color: var(--cy2); margin-bottom: ${U(8)}; }
.pbox h2 { font-family: var(--f-cjk); font-weight: 200; font-size: ${U(84)}; letter-spacing: .3em; margin-right: -.3em; text-shadow: 0 0 ${U(40)} rgba(62,232,255,.4); line-height: 1.1; }
.pbox .sub { margin: ${U(10)} 0 ${U(30)}; font-size: ${U(12)}; letter-spacing: .5em; color: var(--dim); }
.pbox .mi { justify-content: center; padding-left: ${U(18)}; text-align: center; }
.pbox .mi .l { align-items: center; flex: none; }
.pbox .mi::before { left: 50%; right: 50%; top: auto; bottom: ${U(2)}; width: auto; height: 1px; transform: scaleX(.2); transform-origin: center; }
.pbox .mi.f::before { left: 22%; right: 22%; transform: none; }
.pbox .mi.f { background: radial-gradient(ellipse at 50% 50%, rgba(62,232,255,.14), rgba(62,232,255,0) 70%); }
.pbox .mi .l .zh { font-size: ${U(26)}; letter-spacing: .3em; margin-right: -.3em; }
.pbox .stats { display: flex; justify-content: center; gap: ${U(40)}; margin-top: ${U(34)}; color: var(--dim); }
.pbox .stats div { display: flex; flex-direction: column; gap: ${U(3)}; align-items: center; }
.pbox .stats b { font-weight: 300; font-size: ${U(22)}; color: var(--tx); }

/* results */
.nl-results .shade { position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 46%, rgba(2,5,10,.78), rgba(2,5,10,.92)); }
.rbox { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); width: ${U(980)}; }
.rhead { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: ${U(22)}; }
.rhead .eye { font-size: ${U(11.5)}; letter-spacing: .6em; color: var(--cy2); margin-bottom: ${U(6)}; }
.rhead h2 { font-family: var(--f-cjk); font-weight: 200; font-size: ${U(66)}; letter-spacing: .24em; line-height: 1.05; text-shadow: 0 0 ${U(40)} rgba(62,232,255,.35); }
.rhead .you { text-align: right; }
.rhead .you .p { font-size: ${U(104)}; font-weight: 100; line-height: .9; letter-spacing: -.03em; text-shadow: 0 0 ${U(40)} rgba(62,232,255,.5); }
.rhead .you .p i { font-style: normal; font-size: .32em; letter-spacing: .02em; color: var(--dim); margin-left: ${U(6)}; font-weight: 300; }
.rtable { width: 100%; border-collapse: collapse; }
.rtable th { text-align: left; padding: 0 ${U(14)} ${U(10)}; font-weight: 400; border-bottom: 1px solid var(--line); }
.rtable th .cap { display: flex; flex-direction: column; gap: ${U(2)}; letter-spacing: .26em; font-size: ${U(9.5)}; }
.rtable th.tm .cap, .rtable th.bt .cap, .rtable th.gp .cap { margin-right: -.26em; }
.rtable th .cap .zh { font-size: ${U(12)}; margin: 0; }
.rtable td { padding: 0 ${U(14)}; height: ${U(43)}; font-size: ${U(20)}; border-bottom: 1px solid rgba(130,225,255,.07); white-space: nowrap; }
.rtable tr.me { background: linear-gradient(to right, rgba(62,232,255,.20), rgba(62,232,255,.07)); }
.rtable tr.me td { color: #fff; font-weight: 400; }
.rtable tr.me td:first-child { box-shadow: inset 2px 0 0 var(--cy); }
.rtable .pl { width: ${U(70)}; font-size: ${U(22)}; font-weight: 200; }
.rtable .pl.p1 { color: var(--am); }
.rtable .dr { display: flex; align-items: center; gap: ${U(14)}; height: ${U(43)}; }
.rtable .dr .sw { width: ${U(9)}; height: ${U(9)}; border-radius: 50%; flex: none; }
.rtable .dr .nm { letter-spacing: .1em; }
.rtable .tm, .rtable .bt, .rtable .gp { text-align: right; } .rtable th.tm, .rtable th.bt, .rtable th.gp { text-align: right; } .rtable th.tm .cap, .rtable th.bt .cap, .rtable th.gp .cap { align-items: flex-end; }
.rtable .gp { color: var(--dim); } .rtable .bt small, .rtable .tm small { color: var(--dim); font-size: .8em; }
.rtable .bt.fl { color: var(--vi); }
.rtable .bt.fl::after { content: "\\25C6"; font-size: .55em; margin-left: ${U(8)}; vertical-align: .35em; color: var(--vi); }
.rtable .dnf { color: var(--dim2); }
.rbtns { display: flex; gap: ${U(14)}; margin-top: ${U(26)}; justify-content: flex-end; }
.btn { position: relative; padding: ${U(13)} ${U(34)}; border: 1px solid rgba(190,235,255,.3); border-radius: ${U(40)}; cursor: pointer; pointer-events: auto; background: rgba(4,10,18,.55);
  display: flex; flex-direction: column; align-items: center; gap: ${U(2)}; transition: border-color .18s, background .18s, color .18s, box-shadow .18s; color: rgba(214,234,246,.75); }
.btn .zh { font-size: ${U(19)}; letter-spacing: .24em; margin-right: -.24em; font-weight: 300; }
.btn .en { font-size: ${U(9)}; letter-spacing: .38em; margin-right: -.38em; color: var(--dim); }
.btn.f { color: #fff; border-color: var(--cy); background: rgba(62,232,255,.14); box-shadow: 0 0 ${U(26)} rgba(62,232,255,.3), inset 0 0 ${U(14)} rgba(62,232,255,.12); }
.btn.f .en { color: var(--cy2); }
@media (prefers-reduced-motion: reduce) { .logo h1 .fl1, .logo h1 .fl2 { animation: none; } .wrong.on { animation: none; } }
`;
}
