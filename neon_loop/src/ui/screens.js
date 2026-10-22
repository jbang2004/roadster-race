// Title, pause and results screens (DOM + menu wiring). index.js owns state and settings.
import { h } from './hud.js';
import { Menu } from './nav.js';
import { LAP_OPTIONS, DIFFICULTIES, CAMERAS, CONTROLS, LIVERY_COLORS, fmtTime, fmtTimeParts, fmtGap } from './format.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const kbd = (k) => `<span class="kbd">${esc(k)}</span>`;

function row(cls, zh, en, valueHtml = '') {
  const e = h('div', `mi ${cls}`, `<div class="l"><span class="zh">${zh}</span><span class="en">${en}</span></div>${valueHtml ? `<div class="v">${valueHtml}</div>` : ''}`);
  return e;
}
const choiceHtml = () => `<span class="ar" data-d="-1">‹</span><div class="val"><span class="zh"></span><span class="en"></span></div><span class="ar" data-d="1">›</span>`;
function setChoice(el, zh, en, single = false) {
  const v = el.querySelector('.val'); v.classList.toggle('single', single);
  v.querySelector('.zh').textContent = zh; v.querySelector('.en').textContent = en;
}

// ------------------------------------------------------------------ title
export function createTitle(root, { settings, onChange, onStart, onHelp, onShowroom }) {
  const el = h('div', 'scr nl-title');
  el.innerHTML = `<div class="shade"></div><div class="safe"></div>`;
  const safe = el.querySelector('.safe');

  safe.append(h('div', 'logo', `
    <div class="eye"><span>NIGHT STREET RACING · 2080</span></div>
    <h1 class="zh"><span class="fl1">霓</span><span class="fl2">虹</span><span>环</span><span>线</span></h1>
    <div class="sub">NEON <b>LOOP</b></div>
    <div class="tag">4.58 KM 都市环形街道赛 &nbsp;·&nbsp; 8 CARS &nbsp;·&nbsp; 1000 KW EV</div>`));

  const menuEl = h('div', 'menu');
  const iStart = row('primary', '开始比赛', 'START RACE');
  // the showroom entry is a compact pill on the right of START RACE (takes no vertical room: a seventh full row collides with the key hints)
  const iShow = row('show', '展厅', 'SHOWROOM');
  const u = (n) => `calc(var(--u) * ${n}px)`;
  Object.assign(iShow.style, { position: 'absolute', left: u(330), top: u(20), width: u(190), boxSizing: 'border-box', padding: `${u(7)} ${u(16)} ${u(8)} ${u(20)}`, border: '1px solid rgba(190,230,250,.26)', borderRadius: u(24) });
  const iLaps = row('sep', '圈数', 'LAPS', choiceHtml());
  const iDiff = row('', '对手难度', 'AI DIFFICULTY', choiceHtml());
  const iCam = row('', '视角', 'CAMERA', choiceHtml());
  const iVol = row('sep', '音量', 'SOUND VOLUME', `<span class="ar" data-d="-1">‹</span><div class="segs">${'<i></i>'.repeat(10)}</div><span class="ar" data-d="1">›</span>`);
  const iMus = row('', '音乐', 'MUSIC', choiceHtml());
  const iHelp = row('sep', '操作说明', 'CONTROLS');
  menuEl.append(iStart, ...(onShowroom ? [iShow] : []), iLaps, iDiff, iCam, iVol, iMus, iHelp);
  safe.append(menuEl);

  // controls panel
  const help = h('div', 'help');
  const col = (list) => list.map(c => `<div class="r"><div class="k">${c.keys.map(kbd).join('')}</div><div class="d"><span class="zh">${c.zh}</span><span class="en">${c.en}</span></div></div>`).join('');
  help.innerHTML = `<h3>操作说明</h3><div class="cap">CONTROLS</div>
    <div class="cols"><div><div class="sec"><span class="cap"><span class="zh">键盘</span>KEYBOARD</span></div>${col(CONTROLS.keyboard)}</div>
    <div><div class="sec"><span class="cap"><span class="zh">手柄</span>GAMEPAD</span></div>${col(CONTROLS.gamepad)}</div></div>
    <div class="back">${kbd('ESC')}&nbsp; 返回 BACK</div>`;
  safe.append(help);

  safe.append(h('div', 'hints', `
    <div class="hint">${kbd('↑')}${kbd('↓')}<span>选择 SELECT</span></div>
    <div class="hint">${kbd('←')}${kbd('→')}<span>调整 ADJUST</span></div>
    <div class="hint">${kbd('ENTER')}<span>确认 CONFIRM</span></div>
    <div class="hint">${kbd('ESC')}<span>返回 BACK</span></div>`));
  safe.append(h('div', 'ver', `<div>V0.1 · THREE.JS</div><div>RAIN · NIGHT · NEON</div>`));
  root.append(el);

  const items = [
    { id: 'start', el: iStart, kind: 'action' }, ...(onShowroom ? [{ id: 'showroom', el: iShow, kind: 'action' }] : []), { id: 'laps', el: iLaps, kind: 'choice' }, { id: 'difficulty', el: iDiff, kind: 'choice' },
    { id: 'camera', el: iCam, kind: 'choice' }, { id: 'volume', el: iVol, kind: 'slider' }, { id: 'music', el: iMus, kind: 'choice' },
    { id: 'help', el: iHelp, kind: 'action' },
  ];
  const cyc = (arr, i, d) => (i + d + arr.length) % arr.length;
  const segs = [...iVol.querySelectorAll('.segs i')];
  items.find(i => i.id === 'volume').setFromFraction = (f) => { settings.volume = Math.max(0, Math.min(1, Math.round(f * 10) / 10)); refresh(); onChange('volume'); };
  function refresh() {
    setChoice(iLaps, `${settings.laps} 圈`, `${settings.laps} ${settings.laps === 1 ? 'LAP' : 'LAPS'}`);
    const d = DIFFICULTIES.find(x => x.id === settings.difficulty) ?? DIFFICULTIES[1]; setChoice(iDiff, d.zh, d.en);
    const c = CAMERAS.find(x => x.id === settings.camera) ?? CAMERAS[0]; setChoice(iCam, c.zh, c.en);
    const n = Math.round(settings.volume * 10); segs.forEach((s, k) => { s.classList.toggle('o', k < n); s.style.height = `${34 + k * 7}%`; });
    setChoice(iMus, settings.music ? '开' : '关', settings.music ? 'ON' : 'OFF', true);
  }
  let helpOpen = false;
  const setHelp = (o) => { helpOpen = o; help.classList.toggle('on', o); onHelp?.(o); };
  const menu = new Menu(items, {
    onActivate(it) { if (it.id === 'start') onStart(); else if (it.id === 'showroom') onShowroom(); else if (it.id === 'help') setHelp(!helpOpen); else if (it.id === 'laps' || it.id === 'difficulty' || it.id === 'camera' || it.id === 'music') menu.adjust(1); },
    onAdjust(it, d) {
      if (it.id === 'laps') settings.laps = LAP_OPTIONS[cyc(LAP_OPTIONS, Math.max(0, LAP_OPTIONS.indexOf(settings.laps)), d)];
      else if (it.id === 'difficulty') settings.difficulty = DIFFICULTIES[cyc(DIFFICULTIES, Math.max(0, DIFFICULTIES.findIndex(x => x.id === settings.difficulty)), d)].id;
      else if (it.id === 'camera') settings.camera = CAMERAS[cyc(CAMERAS, Math.max(0, CAMERAS.findIndex(x => x.id === settings.camera)), d)].id;
      else if (it.id === 'volume') settings.volume = Math.max(0, Math.min(1, Math.round((settings.volume + d * 0.1) * 10) / 10));
      else if (it.id === 'music') settings.music = !settings.music;
      refresh(); onChange(it.id);
    },
    onBack() { if (helpOpen) setHelp(false); },
  });
  refresh();
  return { el, menu, refresh, setHelp, get helpOpen() { return helpOpen; } };
}

// ------------------------------------------------------------------ pause
export function createPause(root, { onResume, onRestart, onQuit }) {
  const el = h('div', 'scr nl-pause');
  el.innerHTML = `<div class="shade"></div><div class="safe"><div class="pbox">
      <div class="eye">RACE</div><h2 class="zh">暂停</h2><div class="sub">PAUSED</div><div class="mn"></div>
      <div class="stats"><div><span class="cap"><span class="zh">圈数</span>LAP</span><b class="num s-lap">1 / 3</b></div>
      <div><span class="cap"><span class="zh">位置</span>POS</span><b class="num s-pos">1 / 8</b></div>
      <div><span class="cap"><span class="zh">最快圈</span>BEST</span><b class="num s-best">--:--.---</b></div></div></div></div>`;
  const mn = el.querySelector('.mn');
  const iRes = row('', '继续', 'RESUME'), iRst = row('', '重新开始', 'RESTART'), iQuit = row('', '返回主菜单', 'QUIT TO MENU');
  mn.append(iRes, iRst, iQuit);
  root.append(el);
  const menu = new Menu([{ id: 'resume', el: iRes, kind: 'action' }, { id: 'restart', el: iRst, kind: 'action' }, { id: 'quit', el: iQuit, kind: 'action' }], {
    onActivate(it) { (it.id === 'resume' ? onResume : it.id === 'restart' ? onRestart : onQuit)(); },
    onBack: onResume,
  });
  const sl = el.querySelector('.s-lap'), sp = el.querySelector('.s-pos'), sb = el.querySelector('.s-best');
  return { el, menu, setInfo({ lap, laps, place, total, best }) { sl.textContent = `${lap} / ${laps}`; sp.textContent = `${place} / ${total}`; sb.textContent = fmtTime(best); } };
}

// ------------------------------------------------------------------ results
export function createResults(root, { onRestart, onQuit }) {
  const el = h('div', 'scr nl-results');
  el.innerHTML = `<div class="shade"></div><div class="safe"><div class="rbox">
    <div class="rhead"><div><div class="eye">RACE COMPLETE</div><h2 class="zh">比赛结束</h2></div>
      <div class="you"><div class="cap"><span class="zh">你的名次</span>YOUR RESULT</div><div class="p num"><span class="pn">1</span><i class="pe">ST</i></div></div></div>
    <table class="rtable"><thead><tr>
      <th class="pl"><div class="cap"><span class="zh">名次</span>POS</div></th>
      <th><div class="cap"><span class="zh">车手</span>DRIVER</div></th>
      <th class="tm"><div class="cap"><span class="zh">总时间</span>TOTAL</div></th>
      <th class="bt"><div class="cap"><span class="zh">最快圈</span>BEST LAP</div></th>
      <th class="gp"><div class="cap"><span class="zh">差距</span>GAP</div></th></tr></thead><tbody></tbody></table>
    <div class="rbtns"></div></div></div>`;
  const tbody = el.querySelector('tbody'), btns = el.querySelector('.rbtns');
  const bRst = h('div', 'btn', '<span class="zh">再来一场</span><span class="en">RACE AGAIN</span>');
  const bQuit = h('div', 'btn', '<span class="zh">返回主菜单</span><span class="en">MAIN MENU</span>');
  btns.append(bRst, bQuit);
  root.append(el);
  const menu = new Menu([{ id: 'restart', el: bRst, kind: 'action' }, { id: 'quit', el: bQuit, kind: 'action' }], {
    axis: 'h', onActivate(it) { (it.id === 'restart' ? onRestart : onQuit)(); }, onBack: onQuit,
  });
  const pn = el.querySelector('.pn'), pe = el.querySelector('.pe');
  let sig = '';
  const ord = (n) => (n % 100 >= 11 && n % 100 <= 13 ? 'TH' : { 1: 'ST', 2: 'ND', 3: 'RD' }[n % 10] ?? 'TH');
  /** rows: [{ place, name, livery, isMe, total (s|null), best (s|null), gap (s|null), fastest }] sorted by place */
  function render(rows) {
    const s = JSON.stringify(rows.map(r => [r.place, r.name, r.total, r.best, r.gap, r.fastest, r.isMe]));
    if (s === sig) return; sig = s;
    const me = rows.find(r => r.isMe);
    if (me) { pn.textContent = String(me.place); pe.textContent = ord(me.place); }
    tbody.innerHTML = rows.map((r) => {
      const [ta, tb] = r.total != null ? fmtTimeParts(r.total) : ['—', ''];
      const [ba, bb] = r.best != null ? fmtTimeParts(r.best) : ['—', ''];
      return `<tr class="${r.isMe ? 'me' : ''}"><td class="pl num ${r.place === 1 ? 'p1' : ''}">${r.place}</td>
        <td><div class="dr"><span class="sw" style="background:${LIVERY_COLORS[r.livery] ?? '#fff'}"></span><span class="nm zh">${esc(r.name)}</span></div></td>
        <td class="tm num ${r.total == null ? 'dnf' : ''}">${ta}<small>${tb}</small></td>
        <td class="bt num ${r.fastest ? 'fl' : ''}">${ba}<small>${bb}</small></td>
        <td class="gp num">${r.gap == null ? '' : r.gap === 0 ? '—' : fmtGap(Math.abs(r.gap), true)}</td></tr>`;
    }).join('');
  }
  return { el, menu, render, resetSig() { sig = ''; } };
}
