/* Verbatim from final_design.html: sound engine, 3D particle intro, intro controls (lines 1475-1833). */
/* --------------------------------------------------------------------------
   1. PROPER ANIME SOUND EFFECTS ENGINE (Multi-Layered Web Audio Synthesizer)
   -------------------------------------------------------------------------- */
let audioCtx = null;
let soundEnabled = true;

function initAudio() {
  if (!audioCtx) {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) audioCtx = new AudioContext();
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

// Auto-unlock audio on any user interaction so browser security never blocks sound
['click', 'pointerdown', 'keydown', 'touchstart'].forEach(evt => {
  window.addEventListener(evt, () => initAudio(), { once: true, passive: true });
});

// Sound: Ninja Hand-Sign Swish (Rapid slicing wind)
function sfxNinjaSwish() {
  if (!soundEnabled || (audioCtx && audioCtx.state !== "running")) return;
  const ctx = initAudio();
  if (!ctx) return;
  const bufferSize = ctx.sampleRate * 0.12;
  const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;

  const noise = ctx.createBufferSource();
  noise.buffer = buffer;
  const filter = ctx.createBiquadFilter();
  filter.type = 'bandpass';
  filter.frequency.setValueAtTime(3200, ctx.currentTime);
  filter.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.12);
  filter.Q.value = 4.0;

  const gain = ctx.createGain();
  gain.gain.setValueAtTime(0.4, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.12);

  noise.connect(filter);
  filter.connect(gain);
  gain.connect(ctx.destination);
  noise.start();
}

// Sound: Sharp Two-Finger Hand Seal Lock Snap
function sfxCrossSealSnap() {
  if (!soundEnabled || (audioCtx && audioCtx.state !== "running")) return;
  const ctx = initAudio();
  if (!ctx) return;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = 'triangle';
  osc.frequency.setValueAtTime(1400, ctx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(140, ctx.currentTime + 0.07);

  gain.gain.setValueAtTime(0.45, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.07);

  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.07);
  sfxNinjaSwish();
}

// Sound: Crackling Electric Yellow Chakra Sparks
function sfxElectricSpark() {
  if (!soundEnabled || (audioCtx && audioCtx.state !== "running")) return;
  const ctx = initAudio();
  if (!ctx) return;
  const now = ctx.currentTime;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = 'sawtooth';
  osc.frequency.setValueAtTime(2400 + Math.random() * 1200, now);
  osc.frequency.exponentialRampToValueAtTime(300, now + 0.06);
  gain.gain.setValueAtTime(0.2, now);
  gain.gain.exponentialRampToValueAtTime(0.001, now + 0.06);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start(now);
  osc.stop(now + 0.06);
}

// Sound: Deep Electric-Yellow Chakra Vortex Surge
function sfxChakraSurge() {
  if (!soundEnabled || (audioCtx && audioCtx.state !== "running")) return;
  const ctx = initAudio();
  if (!ctx) return;
  const now = ctx.currentTime;

  // Sub-bass layer
  const sub = ctx.createOscillator();
  const subGain = ctx.createGain();
  sub.type = 'sine';
  sub.frequency.setValueAtTime(55, now);
  sub.frequency.exponentialRampToValueAtTime(160, now + 1.4);
  subGain.gain.setValueAtTime(0.01, now);
  subGain.gain.linearRampToValueAtTime(0.35, now + 0.7);
  subGain.gain.exponentialRampToValueAtTime(0.001, now + 1.4);
  sub.connect(subGain);
  subGain.connect(ctx.destination);
  sub.start(now);
  sub.stop(now + 1.4);

  // High-frequency energy buzz (sawtooth + sweep filter)
  const buzz = ctx.createOscillator();
  const bGain = ctx.createGain();
  const filter = ctx.createBiquadFilter();
  buzz.type = 'sawtooth';
  buzz.frequency.setValueAtTime(120, now);
  buzz.frequency.exponentialRampToValueAtTime(520, now + 1.4);

  filter.type = 'bandpass';
  filter.frequency.setValueAtTime(300, now);
  filter.frequency.exponentialRampToValueAtTime(2200, now + 1.4);
  filter.Q.value = 5.0;

  bGain.gain.setValueAtTime(0.01, now);
  bGain.gain.linearRampToValueAtTime(0.28, now + 0.8);
  bGain.gain.exponentialRampToValueAtTime(0.001, now + 1.4);

  buzz.connect(filter);
  filter.connect(bGain);
  bGain.connect(ctx.destination);
  buzz.start(now);
  buzz.stop(now + 1.4);
}

// Sound: MASSIVE Anime Shadow Clone "POOF!" Explosion
function sfxShadowCloneBlast() {
  if (!soundEnabled || (audioCtx && audioCtx.state !== "running")) return;
  const ctx = initAudio();
  if (!ctx) return;
  const now = ctx.currentTime;

  // 1. Heavy bass impact thud (140Hz down to 28Hz)
  const boom = ctx.createOscillator();
  const boomGain = ctx.createGain();
  boom.type = 'sine';
  boom.frequency.setValueAtTime(140, now);
  boom.frequency.exponentialRampToValueAtTime(28, now + 0.45);
  boomGain.gain.setValueAtTime(0.85, now);
  boomGain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
  boom.connect(boomGain);
  boomGain.connect(ctx.destination);
  boom.start(now);
  boom.stop(now + 0.45);

  // 2. White-noise smoke eruption ("POOF/BAM!")
  const bufferSize = ctx.sampleRate * 0.55;
  const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;

  const noise = ctx.createBufferSource();
  noise.buffer = buffer;
  const filter = ctx.createBiquadFilter();
  filter.type = 'lowpass';
  filter.frequency.setValueAtTime(1200, now);
  filter.frequency.exponentialRampToValueAtTime(120, now + 0.55);

  const gain = ctx.createGain();
  gain.gain.setValueAtTime(0.75, now);
  gain.gain.exponentialRampToValueAtTime(0.001, now + 0.55);

  noise.connect(filter);
  filter.connect(gain);
  gain.connect(ctx.destination);
  noise.start(now);
}

// Sound: Spatial Teleport Pop for each clone
function sfxClonePop(panX = 0) {
  if (!soundEnabled || (audioCtx && audioCtx.state !== "running")) return;
  const ctx = initAudio();
  if (!ctx) return;
  const now = ctx.currentTime;

  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = 'sine';
  osc.frequency.setValueAtTime(480, now);
  osc.frequency.exponentialRampToValueAtTime(80, now + 0.12);

  gain.gain.setValueAtTime(0.35, now);
  gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);

  if (ctx.createStereoPanner) {
    const panner = ctx.createStereoPanner();
    panner.pan.value = panX;
    osc.connect(gain);
    gain.connect(panner);
    panner.connect(ctx.destination);
  } else {
    osc.connect(gain);
    gain.connect(ctx.destination);
  }
  osc.start(now);
  osc.stop(now + 0.12);
}

// Sound: Traditional Japanese Shinobi Pentatonic Chord
function sfxJapaneseChime() {
  if (!soundEnabled || (audioCtx && audioCtx.state !== "running")) return;
  const ctx = initAudio();
  if (!ctx) return;
  const notes = [293.66, 311.13, 392.00, 440.00, 587.33]; // D4, Eb4, G4, A4, D5
  notes.forEach((freq, idx) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    const start = ctx.currentTime + idx * 0.07;
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(freq, start);
    gain.gain.setValueAtTime(0.2, start);
    gain.gain.exponentialRampToValueAtTime(0.001, start + 0.45);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(start);
    osc.stop(start + 0.45);
  });
}

/* --------------------------------------------------------------------------
   2. 3D PARTICLE ENGINE & VOLUMETRIC SMOKE SIMULATION
   -------------------------------------------------------------------------- */
const intro = document.getElementById("intro");
const canvas3D = document.getElementById("intro-canvas-3d");
const g3d = canvas3D.getContext("2d");
let isIntroActive = false;
let timers = [];
let P = [];

function resize3DCanvas() {
  canvas3D.width = window.innerWidth;
  canvas3D.height = window.innerHeight;
}
window.addEventListener("resize", resize3DCanvas);
resize3DCanvas();

// Smoke / spark burst from a point (px, py are 0-1 screen fractions)
function burst(px, py, n, fast) {
  const cols = ["255,255,255", "255,237,0", "120,120,132", "40,40,50"];
  for (let i = 0; i < n; i++) {
    const a = Math.random() * Math.PI * 2;
    const sp = (fast ? 3 : 1.2) + Math.random() * (fast ? 9 : 3);
    P.push({
      x: innerWidth * px, y: innerHeight * py, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp,
      r: fast ? 24 + Math.random() * 46 : 2 + Math.random() * 3, l: 1, d: fast ? 0.016 : 0.03, c: cols[i % (fast ? 4 : 2)]
    });
  }
}

function render3DScene() {
  g3d.clearRect(0, 0, canvas3D.width, canvas3D.height);
  for (const p of P) {
    p.x += p.vx; p.y += p.vy; p.vx *= 0.95; p.vy *= 0.95; p.r += p.d > 0.02 ? 0 : 1.1; p.l -= p.d;
    if (p.l > 0) {
      g3d.fillStyle = "rgba(" + p.c + "," + p.l * 0.55 + ")";
      g3d.beginPath(); g3d.arc(p.x, p.y, p.r, 0, 6.283); g3d.fill();
    }
  }
  P = P.filter(p => p.l > 0);
  if (isIntroActive || P.length) requestAnimationFrame(render3DScene);
}

function sfxTaiko(v) {
  if (!soundEnabled || (audioCtx && audioCtx.state !== "running")) return;
  const c = initAudio(); if (!c) return;
  const t = c.currentTime, o = c.createOscillator(), g = c.createGain();
  o.type = "sine"; o.frequency.setValueAtTime(170, t); o.frequency.exponentialRampToValueAtTime(46, t + .3);
  g.gain.setValueAtTime(.95 * v, t); g.gain.exponentialRampToValueAtTime(.001, t + .55);
  o.connect(g); g.connect(c.destination); o.start(t); o.stop(t + .6);
  const len = c.sampleRate * .08, b = c.createBuffer(1, len, c.sampleRate), d = b.getChannelData(0);
  for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / len);
  const n = c.createBufferSource(), ng = c.createGain(); n.buffer = b; ng.gain.value = .45 * v;
  n.connect(ng); ng.connect(c.destination); n.start(t);
}
function sfxPoof() {
  if (!soundEnabled || (audioCtx && audioCtx.state !== "running")) return;
  const c = initAudio(); if (!c) return;
  const t = c.currentTime, len = c.sampleRate * .7, b = c.createBuffer(1, len, c.sampleRate), d = b.getChannelData(0);
  for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2);
  const n = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain();
  n.buffer = b; f.type = "lowpass"; f.frequency.setValueAtTime(5000, t); f.frequency.exponentialRampToValueAtTime(300, t + .6); g.gain.value = .7;
  n.connect(f); f.connect(g); g.connect(c.destination); n.start(t);
}

function flashNow() {
  intro.classList.remove("flash");
  void intro.offsetWidth;
  intro.classList.add("flash");
}

/* Timeline (3.7s): ring draws + kanji stamps -> title slams in -> clones split + smoke -> curtains open */
function start3DNarutoIntro() {
  document.documentElement.classList.add("intro-active");
  intro.classList.remove("p1", "p2", "p3", "p4", "q1", "q2", "q3", "q4", "inv", "flash");
  isIntroActive = true;
  P = [];
  resize3DCanvas();
  render3DScene();
  timers.forEach(clearTimeout);
  timers = [];
  const at = (ms, fn) => timers.push(setTimeout(fn, ms));

  at(100, () => { intro.classList.add("q1"); sfxTaiko(.8); });
  at(400, () => { intro.classList.add("q2"); sfxTaiko(.9); });
  at(700, () => { intro.classList.add("q3"); sfxTaiko(1.15); sfxChakraSurge(); });
  at(1100, () => { intro.classList.add("inv", "q4"); flashNow(); sfxShadowCloneBlast(); sfxPoof(); burst(0.5, 0.5, 100, true); });
  at(1180, () => intro.classList.remove("inv"));
  at(1800, () => { intro.classList.add("p1"); sfxNinjaSwish(); sfxChakraSurge(); });
  at(2250, () => { sfxCrossSealSnap(); burst(0.5, 0.44, 24, false); });
  at(2600, () => { intro.classList.add("p2"); sfxNinjaSwish(); });
  at(3250, () => { flashNow(); intro.classList.add("p3"); sfxPoof(); sfxShadowCloneBlast(); burst(0.5, 0.44, 90, true); });
  at(3450, () => sfxClonePop(-0.65));
  at(3600, () => sfxClonePop(0));
  at(3750, () => sfxClonePop(0.65));
  at(3950, () => sfxJapaneseChime());
  at(4400, () => { flashNow(); end3DNarutoIntro(); });
}

function end3DNarutoIntro() {
  if (!document.documentElement.classList.contains("intro-active") || intro.classList.contains("p4")) return;
  isIntroActive = false;
  timers.forEach(clearTimeout);
  intro.classList.add("p4");
  try { sessionStorage.setItem("kz_naruto_intro_seen", "1"); } catch (e) { }
  setTimeout(() => { document.documentElement.classList.remove("intro-active"); }, 800);
}

document.getElementById("btn-skip-intro").onclick = end3DNarutoIntro;
window.addEventListener("keydown", e => {
  if (e.key === "Escape" && document.documentElement.classList.contains("intro-active")) end3DNarutoIntro();
});

const soundToggleBtn = document.getElementById("btn-sound-toggle");
soundToggleBtn.onclick = () => {
  soundEnabled = !soundEnabled;
  soundToggleBtn.textContent = soundEnabled ? "🔊 Sound: ON" : "🔇 Sound: MUTED";
  if (soundEnabled) initAudio();
};

document.getElementById("btn-replay-intro").onclick = () => {
  initAudio();
  start3DNarutoIntro();
};

if (document.documentElement.classList.contains("intro-active")) {
  soundEnabled = true;
  initAudio();
  ["pointerdown", "keydown", "touchstart", "click"].forEach(ev =>
    window.addEventListener(ev, () => initAudio(), { once: true, passive: true }));
  start3DNarutoIntro();
}

/* Verbatim from final_design.html: toast + modal utilities and cursor/spotlight (lines 2026-2079). */
function closeModal(id) {
  document.getElementById(id).classList.remove("open");
}
function showToast(msg) {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerHTML = `<span>⚡</span> <div>${msg}</div>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

/* --------------------------------------------------------------------------
   10. MOUSE SPOTLIGHT & CURSOR
   -------------------------------------------------------------------------- */
window.addEventListener("pointermove", e => {
  const card = e.target.closest(".card");

  if (card) {
    const r = card.getBoundingClientRect();
    card.style.setProperty("--mx", (e.clientX - r.left) + "px");
    card.style.setProperty("--my", (e.clientY - r.top) + "px");
  }
});