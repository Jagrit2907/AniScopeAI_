/* AniScope AI screens rendered inside the final design.
   All data comes from the Python API (/api/*), which calls the original analytics in src/.
   Nothing here computes trends, sentiment, aspects or candidates; it only renders results. */
"use strict";

/* ------------------------------------------------------------------ utils */
const $ = (s, el = document) => el.querySelector(s);
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (v, d = 0) => (v === null || v === undefined || Number.isNaN(v)) ? "—" : Number(v).toLocaleString("en-IN", { maximumFractionDigits: d, minimumFractionDigits: d });
const pct = v => (v === null || v === undefined) ? "—" : `${v > 0 ? "+" : ""}${Number(v).toFixed(0)}%`;
const KIND_JA = {
  "Catalog metadata": "カタログメタデータ",
  "Observed": "観測実データ",
  "Calculated": "計算指標",
  "Interpretation": "示唆・解釈",
  "Hypothesis": "事業仮説",
  "Assumptions": "前提条件",
  "Why selected": "選定理由",
  "Visibility": "認知度"
};
const kind = (k, t) => `<span class="kind ${k}">${currentLang === "ja" ? (KIND_JA[t] || t) : t}</span>`;

function formatVisibility(v) {
  if (!v) return currentLang === "ja" ? "未計測" : "not measured";
  if (currentLang !== "ja") return v;
  if (v.includes("Not in the 2020 MAL snapshot")) {
    return "2020年MALスナップショットに対象データなし（後日公開、またはMAL未登録）— 認知度は未計測。";
  }
  const m = v.match(/^([\d,]+)\s+MAL members\s*\(2020 snapshot, global\)\s*—\s*percentile\s*(\d+)\s+among\s+(\d+)\s+(.+?)\s+titles\.?$/i);
  if (m) {
    return `MAL会員数 ${m[1]}人（2020年全世界スナップショット）— 類似作品（${m[4]}、計${m[3]}作品）中のパーセンタイル: 上位${m[2]}%`;
  }
  return v;
}

function formatExplanation(sr) {
  if (currentLang !== "ja" || !sr || !sr.explanation) return sr?.explanation || "";
  if (sr.abs_change === null || sr.abs_change === undefined) {
    return `「${sr.query}」の観測検索指数 (${sr.geo ? sr.geo + "市場" : "地域未指定"}): 観測数 ${sr.observations || sr.points?.length || 0}件。比較に必要な両期間の観測数が不足しています。`;
  }
  const dir = sr.abs_change > 0 ? "上昇" : sr.abs_change < 0 ? "低下" : "横ばい";
  const pctText = sr.pct_change !== null && sr.pct_change !== undefined ? ` (${sr.pct_change >= 0 ? "+" : ""}${Math.round(sr.pct_change)}%)` : "";
  return `実測値: 「${sr.query}」（${sr.geo ? sr.geo + "市場" : "地域未指定"}）の平均検索指数は、基準期間の ${sr.baseline_mean?.toFixed(1)} から直近期間の ${sr.recent_mean?.toFixed(1)} へと${dir}し、変動幅は ${sr.abs_change > 0 ? "+" : ""}${sr.abs_change.toFixed(1)} ポイント${pctText} です。※本指標は相対指数であり、視聴者数や購買者数を示す実数ではありません。`;
}

function formatReason(r) {
  if (currentLang !== "ja" || !r) return r;
  if (r.includes("Baseline average is 0")) {
    return "基準期間の平均が0のため、変動率(%)は定義されません。";
  }
  let m = r.match(/Baseline average is ([\d.]+) index points.*?below ([\d.]+)/i);
  if (m) {
    return `基準期間の平均指数が ${m[1]} ポイント（基準閾値 ${m[2]} 未満）のため、微小な変動による極端な数値の歪みを防ぐ目的で変動率(%)は非表示としています。`;
  }
  m = r.match(/Recent window has (\d+) observations.*?minimum (\d+)/i);
  if (m) {
    return `直近期間の観測数が ${m[1]} 件です（最低必要数: ${m[2]} 件）。`;
  }
  m = r.match(/Baseline window has (\d+) observations.*?minimum (\d+)/i);
  if (m) {
    return `基準期間の観測数が ${m[1]} 件です（最低必要数: ${m[2]} 件）。`;
  }
  m = r.match(/([\d.]+)% of observations in the two windows are 0/i);
  if (m) {
    return `比較両期間の観測データの ${m[1]}% が 0 または「<1」です — Googleの最小報告基準値を下回る頻度が高い状態です。`;
  }
  return r;
}

const GEM_LIMS_JA = {
  "Reviewer location is unknown: this is not evidence about Indian audiences.": "レビュアーの所在地は未特定です: インド在住の観客を対象としたデータではありません。",
  "Small sample: a few reviews can change the aspect stances.": "サンプル規模が小さいため、わずかなレビュー数の増減で要素のスタンス判定が変動する可能性があります。",
  "Aspect stances come from keyword matching and lexicon sentiment, not human coding.": "要素判定はキーワード一致と極性辞書による自動判定であり、人間による手動コーディングではありません。",
  "Mixed response does not imply the title is underrated, and criticism is not shown to cause low popularity.": "賛否両論は作品が過小評価されていることを意味するものではなく、また批判が認知度の低さの原因であると立証されたわけではありません。"
};
function formatGemLimitations(lims) {
  if (currentLang !== "ja" || !lims) return lims ? (Array.isArray(lims) ? lims.join(" ") : lims) : "";
  const arr = Array.isArray(lims) ? lims : [lims];
  return arr.map(l => {
    if (GEM_LIMS_JA[l]) return GEM_LIMS_JA[l];
    const m = l.match(/^Based on (\d+) review records from (.+?)\.$/);
    if (m) return `${m[2]} から取得された ${m[1]} 件のレビュー記録に基づきます。`;
    return l;
  }).join(" ");
}

const GEM_STEPS_JA = {
  "Test whether premise-led promotion (trailers, synopsis-first creatives) draws interest.": "基本設定やあらすじを前面に出したプロモーション（予告編、設定訴求クリエイティブ）が関心を惹くか検証。",
  "Test character-focused content: profiles, arc recaps, character polls.": "キャラクター主導コンテンツ（プロフィール、成長ストーリー振り返り、キャラ人気投票）の効果を検証。",
  "Test protagonist-led creatives and merchandise featuring the lead.": "主人公を主軸にしたクリエイティブやグッズ展開の受容性を検証。",
  "Test 'battle of wits' framing, puzzle or strategy community activities.": "「頭脳戦・心理戦」の打ち出しや、謎解き・戦略コミュニティ施策を検証。",
  "Test lore explainers, maps, art books or setting-focused collectibles.": "世界観解説、地図、アートブック、設定資料連動グッズの需要を検証。",
  "Test emotional-moment clips and watch-party style community events.": "感動シーンの切り抜きやウォッチパーティ形式のコミュニティイベントを検証。",
  "Test key-art prints, artbooks, and visual-led social content.": "キービジュアル複製原画、画集、作画訴求SNSコンテンツを検証。",
  "Test fight-highlight clips and action-figure style merchandise.": "バトルハイライト動画やアクションフィギュア等の商品展開を検証。",
  "Test quote-led social content; check subtitle/dub quality expectations.": "名セリフ引用SNS施策および字幕・吹替クオリティへの期待値を検証。",
  "Test soundtrack streaming promotion and music-event formats.": "劇伴・サントラのストリーミング訴求や音楽イベント形式を検証。",
  "Test 'complete series' binge positioning.": "「完結済み・一気見推奨」ポジショニングの訴求力を検証。",
  "Test meme-friendly short-form content.": "拡散性の高いコメディ系ショート動画コンテンツを検証。",
  "Investigate recap or curated-episode guides to address pacing complaints.": "テンポへの不満に対処するため、総集編やセレクション話数ガイドを検討。",
  "Investigate which arcs reviewers single out before promoting the whole series.": "シリーズ全体をプロモーションする前に、レビュアーが特に問題視したエピソード章を特定。",
  "Validate with an Indian audience sample before any commercial commitment.": "商業投資に踏み切る前に、必ずインド国内の観客サンプルによる実地検証を行ってください。"
};
function formatGemSteps(steps) {
  if (currentLang !== "ja" || !steps) return steps ? (Array.isArray(steps) ? steps.join(" ") : steps) : "";
  const arr = Array.isArray(steps) ? steps : [steps];
  return arr.map(s => GEM_STEPS_JA[s] || s).join(" ");
}
function formatGemWhy(c) {
  if (currentLang !== "ja" || !c) return c?.why || "";
  const praised = (c.praised || []).map(aspName).join("、");
  const crit = (c.criticised || []).map(aspName).join("、");
  const div = (c.divided || []).map(aspName).join("、");
  const parts = [];
  if (praised) parts.push(`レビュー層は主に「${praised}」を称賛`);
  if (crit) parts.push(`一方で「${crit}」には批判的`);
  else if (div) parts.push(`一方で「${div}」に関しては賛否両論`);
  if (c.mixed_share >= 0.3) parts.push(`全体の ${(c.mixed_share * 100).toFixed(0)}% が総合的に賛否または低評価`);
  return `読み込まれたレビューにおいて、${parts.join("、")}となっています。`;
}
const sfx = fn => { try { if (typeof fn === "function") fn(); } catch (e) { /* audio is optional */ } };

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {}, ...opts });
  let data = null;
  try { data = await res.json(); } catch (e) { /* non-JSON */ }
  if (!res.ok) {
    const d = data && data.detail;
    const msg = typeof d === "string" ? d : (d && d.message) || `Request failed (${res.status})`;
    const err = new Error(msg); err.status = res.status; err.detail = d; throw err;
  }
  return data;
}
const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body) });
const loading = (t = null) => {
  const def = currentLang === "ja" ? "読み込み中…" : "Loading…";
  return `<div class="loading"><span class="spinner"></span>${esc(t || def)}</div>`;
};

const toast = m => showToast(esc(m));
const S = { status: null, ws: null, aspects: [] };

/* ------------------------------------------------------------------ Shinigami */
const SHINIGAMI_STATES = {
  guide: { c: "#00f0ff", label: "Guide", labelJa: "ガイド", mouth: "M30 47 Q36 52 42 47", anim: "ShinigamiBob 3.2s ease-in-out infinite" },
  discovery: { c: "#ff7700", label: "Discovery", labelJa: "発見", mouth: "M29 46 Q36 55 43 46", anim: "ShinigamiHop 1.6s ease-in-out infinite" },
  caution: { c: "#ffcc00", label: "Caution", labelJa: "注意", mouth: "M31 49 L41 49", anim: "ShinigamiSway 2.6s ease-in-out infinite" },
};

function ShinigamiSvg(state) {
  const images = {
    guide: "/static/assets/companion/guide.png",
    discovery: "/static/assets/companion/discovery.png",
    caution: "/static/assets/companion/caution.png"
  };

  const labels = {
    guide: "Light Yagami — Guide",
    discovery: "Light Yagami — Discovery",
    caution: "Light Yagami — Caution"
  };

  const src = images[state] || images.guide;
  const label = labels[state] || labels.guide;

  return `<img
    class="shinigami-character"
    src="${src}"
    alt="${label}"
    title="${label}"
    onclick="this.closest('#Shinigami').classList.toggle('min')"
  >`;
}

/* Shinigami states come only from conditions computed on real API results:
   a real finding → Discovery; a real limitation → Caution; otherwise → Guide. */
function Shinigami({ cautions = [], discoveries = [], guide = "" }) {
  const isJa = currentLang === "ja";
  let state, msg, notes = [];
  if (discoveries.length) { state = "discovery"; msg = discoveries[0]; notes = cautions; }
  else if (cautions.length) { state = "caution"; msg = cautions[0]; notes = cautions.slice(1); }
  else { state = "guide"; msg = guide; }
  const el = $("#Shinigami");
  if (!el) return;
  const min = el.classList.contains("min");
  el.className = `Shinigami ${state}${min ? " min" : ""}`;
  const s = SHINIGAMI_STATES[state];
  el.innerHTML = `${ShinigamiSvg(state)}<div class="Shinigami-body"><span class="Shinigami-tag" style="background:${s.c}">Shinigami · ${isJa ? s.labelJa : s.label}</span><br>${esc(msg)}${notes.slice(0, 2).map(n => `<div class="Shinigami-notes">⚠ ${esc(n)}</div>`).join("")}</div>`;
  const character = $(".shinigami-character", el);
  if (character) {
    character.onclick = () => el.classList.toggle("min");
  }
}

/* ------------------------------------------------------------- workspace */
async function refreshWs() {
  S.ws = await api("/api/workspace");
  const bar = $("#ws-bar");
  const w = S.ws;
  const isJa = currentLang === "ja";
  bar.innerHTML = w.selected_label
    ? `<span>${isJa ? "調査中:" : "Investigating"}</span> <b>${esc(w.selected_label)}</b>${(w.selected_themes || []).length ? ` <span class="pill-badge">${esc(w.selected_themes.join(" · "))}</span>` : ""}
       <button class="linklike" onclick="openTitle('${esc(w.selected_anime_id)}')">${isJa ? "詳細" : "details"}</button>
       <button class="linklike" onclick="resetWorkspace()">${isJa ? "ワークスペース初期化" : "reset workspace"}</button>`
    : `<span>${isJa ? "作品が選択されていません — 司令塔で検索して選択してください。" : "No title selected — search one in the Command Center."}</span>`;
  return w;
}
async function selectTitle(id, goto) {
  await post("/api/workspace/select", { anime_id: id });
  sfx(window.sfxCrossSealSnap);
  await refreshWs();
  if (goto) location.hash = goto; else route();
}
async function resetWorkspace() {
  const isJa = currentLang === "ja";
  if (!confirm(isJa ? "選択中の作品、テーマ、企画案、前提条件、保存済み項目をリセットしますか？" : "Clear the selected title, themes, concept, plan, assumptions and saved items?")) return;
  await api("/api/workspace/reset", { method: "POST" });
  toast(isJa ? "ワークスペースをリセットしました。" : "Workspace cleared.");
  await refreshWs(); route();
}

async function openTitle(id) {
  const isJa = currentLang === "ja";
  const body = $("#title-modal-body");
  body.innerHTML = loading();
  $("#title-modal").classList.add("open");
  try {
    const d = await api(`/api/title/${encodeURIComponent(id)}`);
    const r = d.record;
    body.innerHTML = `<span class="pill-badge">${kind("observed", "Catalog metadata")}</span>
      <h3 style="font:800 20px 'Unbounded';margin:12px 0 4px">${esc(r.label)}</h3>
      <p class="hint" style="color:var(--mute)">${[r.season, r.episodes && r.episodes + (isJa ? "話" : " eps"), r.status].filter(Boolean).map(esc).join(" · ")}
        ${r.score ? ` · ${isJa ? "世界複数サイト評価" : "cross-site catalog score"} ${fmt(r.score, 2)}/10` : ""}</p>
      <div class="chips mt-s">${(r.tags || []).map(t => `<button>${esc(t)}</button>`).join("")}</div>
      ${r.synonyms?.length ? `<p class="note">${isJa ? "別名:" : "Also known as:"} ${esc(r.synonyms.join(", "))}</p>` : ""}
      <div class="statgrid mt">
        <div class="stat-box"><b>${fmt(d.trend_obs)}</b><span>${isJa ? "インド検索観測数" : "India trend observations"}</span></div>
        <div class="stat-box"><b>${fmt(d.reviews)}</b><span>${isJa ? "連携レビュー数" : "Linked review records"}</span></div>
        <div class="stat-box"><b>${r.mal_id ? esc(r.mal_id) : "—"}</b><span>MyAnimeList ID</span></div>
        <div class="stat-box"><b>${r.anilist_id ? esc(r.anilist_id) : "—"}</b><span>AniList ID</span></div>
      </div>
      ${d.visibility ? `<p class="note">${kind("observed", "Visibility")} ${esc(formatVisibility(d.visibility))}</p>` : ""}
      ${d.reviews === 0 ? `<p class="warn">${isJa ? "この作品にはレビューデータが連携されていないため、観客分析は利用できません。" : "No review evidence is linked to this title — audience findings are unavailable."}</p>` : ""}
      <p class="note">${isJa ? "参照元:" : "Sources:"} ${(r.sources || []).map(u => `<a href="${esc(u)}" target="_blank" rel="noopener" style="color:var(--chakra-cyan)">${esc(u.split("/")[2])}</a>`).join(" · ")}</p>
      <div class="row mt">
        <button class="btn btn-sm" onclick="closeModal('title-modal');selectTitle('${esc(r.anime_id)}','#/radar')">${isJa ? "トレンドを調査" : "Investigate trends"}</button>
        <button class="btn ghost btn-sm" onclick="closeModal('title-modal');selectTitle('${esc(r.anime_id)}','#/audience')">${isJa ? "観客データを分析" : "Audience evidence"}</button>
      </div>`;
  } catch (e) { body.innerHTML = `<div class="empty"><h3>${isJa ? "作品を読み込めませんでした" : "Could not load this title"}</h3>${esc(e.message)}</div>`; }
}

async function openStatus() {
  const body = $("#status-modal-body");
  body.innerHTML = loading();
  $("#status-modal").classList.add("open");
  const s = await api("/api/status"); S.status = s;
  body.innerHTML = statusHtml(s);
}
function statusHtml(s) {
  const isJa = currentLang === "ja";
  if (!s.catalog_ok) return catalogMissing(s);
  const c = s.coverage, m = s.summary;
  return `<h3 style="font:800 20px 'Unbounded';margin:0 0 6px">${isJa ? "データ連携状況" : "Data status"}</h3>
    <p class="hint" style="color:var(--mute)">${isJa ? "フォルダ:" : "Folder:"} <code>${esc(s.data_dir)}</code></p>
    <div class="statgrid mt">
      <div class="stat-box"><b>${fmt(m.records)}</b><span>${isJa ? "カタログ作品数 · スナップショット" : "Catalog records · snapshot"} ${esc(s.snapshot || "—")}</span></div>
      <div class="stat-box"><b>${fmt(c.trend_titles)}</b><span>${isJa ? `トレンドデータ保有 (${esc(c.trend_geos.join(", ") || "対象市場なし")})` : `Titles with trend data (${esc(c.trend_geos.join(", ") || "no market")})`}</span></div>
      <div class="stat-box"><b>${fmt(c.reviews)}</b><span>${isJa ? `レビュー総数 · ${fmt(c.review_titles)}作品` : `Reviews · ${fmt(c.review_titles)} titles`}</span></div>
      <div class="stat-box"><b>${fmt(c.visibility_titles)}</b><span>${isJa ? "MAL 2020認知度保有作品数" : "Titles with MAL 2020 visibility"}</span></div>
    </div>
    <ul class="mini-list mt">
      ${Object.entries(s.files).map(([k, v]) => `<li><b>${esc(k)}</b>: ${v ? esc(v) : `<span style="color:var(--kurama-red)">${isJa ? "未連携" : "not found"}</span>`}</li>`).join("")}
      <li><b>${isJa ? "レビュー分析キャッシュ" : "Review analysis cache"}</b>: ${s.analysis_cache ? (isJa ? "最新" : "up to date") : (isJa ? "未生成（初回レビュー読み込み時に自動作成）" : "not built (built automatically on first review load)")}</li>
      <li><b>${isJa ? "感情分析手法" : "Sentiment method"}</b>: ${esc(s.sentiment_method)}</li>
    </ul>
    <p class="note">${isJa ? "ライセンス:" : "Licence:"} ${esc(s.license || "—")}</p>`;
}
function catalogMissing(s) {
  const isJa = currentLang === "ja";
  return `<div class="empty"><h3>${isJa ? "カタログが読み込まれていません" : "Catalog not loaded"}</h3>${esc(s.catalog_error || "")}<br><br>
    ${isJa ? `<code>${esc(s.data_dir)}</code> に <code>anime_catalog_all_titles.csv</code> と <code>dataset_manifest.json</code> を配置するか、<code>.env</code> で <code>ANISCOPE_DATA_DIR</code> を設定して <code>python run_web.py</code> を再起動してください。`
      : `Put <code>anime_catalog_all_titles.csv</code> and <code>dataset_manifest.json</code> in <code>${esc(s.data_dir)}</code>, or set <code>ANISCOPE_DATA_DIR</code> in a <code>.env</code> file, then restart <code>python run_web.py</code>.`}</div>`;
}

/* ---------------------------------------------------------------- charts */
function lineChart(series, opt = {}) {
  // series: [{name, color, points:[{date,value}]}]; opt.bands: [{from,to,cls,label}]
  const W = opt.w || 720, H = opt.h || 280, L = 40, R = 14, T = 16, B = 30;
  const all = series.flatMap(s => s.points);
  if (!all.length) return `<div class="empty">No observations to plot.</div>`;
  const t = d => new Date(d + "T00:00:00Z").getTime();
  const x0 = Math.min(...all.map(p => t(p.date))), x1 = Math.max(...all.map(p => t(p.date)));
  const yMax = Math.max(10, ...all.map(p => p.value));
  const X = d => L + (x1 === x0 ? 0 : (t(d) - x0) / (x1 - x0)) * (W - L - R);
  const Y = v => T + (1 - v / yMax) * (H - T - B);
  let g = "";
  [0, .25, .5, .75, 1].forEach(f => { const v = Math.round(yMax * f); g += `<line class="gridl" x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}"/><text class="axis" x="${L - 6}" y="${Y(v) + 4}" text-anchor="end">${v}</text>`; });
  const y0 = new Date(x0).getUTCFullYear(), y1 = new Date(x1).getUTCFullYear();
  for (let y = y0; y <= y1 + 1; y++) { const tt = Date.UTC(y, 0, 1); if (tt >= x0 && tt <= x1) g += `<text class="axis" x="${X(new Date(tt).toISOString().slice(0, 10))}" y="${H - 8}" text-anchor="middle">${y}</text>`; }
  (opt.bands || []).forEach(b => {
    const a = X(b.from), z = X(b.to);
    g += `<rect class="${b.cls}" x="${Math.min(a, z)}" y="${T}" width="${Math.max(2, Math.abs(z - a))}" height="${H - T - B}"/><text class="band-t" x="${Math.min(a, z) + 4}" y="${T + 12}">${esc(b.label)}</text>`;
  });
  // Crosshair vertical line
  g += `<line class="chart-crosshair" style="display:none; pointer-events:none;" stroke="rgba(255,119,0,0.55)" stroke-dasharray="3 3" stroke-width="1.5" y1="${T}" y2="${H - B}"></line>`;
  series.forEach((s, i) => {
    const id = `lg${i}${Math.random().toString(36).slice(2, 7)}`;
    const d = s.points.map((p, j) => `${j ? "L" : "M"}${X(p.date).toFixed(1)} ${Y(p.value).toFixed(1)}`).join("");
    const color = s.color || ["#ff7700", "#00f0ff", "#10b981", "#ffcc00", "#c4b5fd"][i % 5];
    g += `<defs><linearGradient id="${id}" x1="0" x2="1"><stop offset="0" stop-color="${color}"/><stop offset="1" stop-color="${i ? color : "#ffcc00"}"/></linearGradient></defs>
      <path d="${d}" fill="none" stroke="url(#${id})" stroke-width="2.6" stroke-linejoin="round" style="filter:drop-shadow(0 0 6px ${color}88)"/>`;
    s.points.forEach(p => {
      const cx = X(p.date).toFixed(1), cy = Y(p.value).toFixed(1);
      g += `<g class="chart-point-group" data-series="${esc(s.name)}" data-date="${esc(p.date)}" data-val="${p.value}" data-color="${color}" data-cx="${cx}" data-cy="${cy}">
        <circle class="pt-dot" cx="${cx}" cy="${cy}" r="3.2" fill="${color}" style="pointer-events:none; transition: r .18s ease-out;"></circle>
        <circle class="pt-hit" cx="${cx}" cy="${cy}" r="15" fill="transparent" style="cursor:pointer;"></circle>
      </g>`;
    });
  });
  const legend = series.length > 1 ? `<div class="legend">${series.map((s, i) => `<span><i style="background:${s.color || ["#ff7700", "#00f0ff", "#10b981", "#ffcc00", "#c4b5fd"][i % 5]}"></i>${esc(s.name)}</span>`).join("")}</div>` : "";
  return `<svg class="chart line-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opt.label || "Trend chart")}">${g}</svg>${legend}`;
}
const QUAD_JA = {
  "Emerging: lower level, rising": "新興・急上昇（低水準・上昇中）",
  "Established and rising": "定着・拡大（高水準・上昇中）",
  "High level, flat or falling": "成熟・維持（高水準・横ばい/下降）",
  "Lower level, flat or falling": "低調（低水準・横ばい/下降）"
};

function scatter(points) {
  const isJa = currentLang === "ja";
  const W = 720, H = 300, L = 46, R = 20, T = 20, B = 36;
  const xs = points.map(p => p.recent_mean), ys = points.map(p => p.abs_change);
  const x1 = Math.max(10, ...xs) * 1.1, ya = Math.max(5, ...ys.map(Math.abs)) * 1.25;
  const X = v => L + v / x1 * (W - L - R), Y = v => T + (1 - (v + ya) / (2 * ya)) * (H - T - B);
  const med = [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];
  const col = { "Emerging: lower level, rising": "#10b981", "Established and rising": "#ffcc00", "High level, flat or falling": "#ff7700", "Lower level, flat or falling": "#9090a2" };
  let g = `<line class="gridl" x1="${L}" x2="${W - R}" y1="${Y(0)}" y2="${Y(0)}"/><line class="gridl" stroke-dasharray="4 4" x1="${X(med)}" x2="${X(med)}" y1="${T}" y2="${H - B}"/>
    <text class="axis" x="${(W) / 2}" y="${H - 6}" text-anchor="middle">${isJa ? "水準: 直近平均指数 (本エクスポート内)" : "Level: recent mean index (within this export)"}</text>
    <text class="axis" x="12" y="${H / 2}" transform="rotate(-90 12 ${H / 2})" text-anchor="middle">${isJa ? "モメンタム: 変動幅 (ポイント)" : "Momentum: change (points)"}</text>`;
  points.forEach(p => {
    const cx = X(p.recent_mean).toFixed(1), cy = Y(p.abs_change).toFixed(1);
    const qLabel = isJa ? (QUAD_JA[p.quadrant] || p.quadrant) : p.quadrant;
    g += `<g class="scatter-point-group" data-title="${esc(p.title)}" data-quad="${esc(qLabel)}" data-level="${p.recent_mean.toFixed(1)}" data-chg="${p.abs_change.toFixed(1)}" data-color="${col[p.quadrant]}">
      <circle class="sc-dot" cx="${cx}" cy="${cy}" r="7" fill="${col[p.quadrant]}" style="filter:drop-shadow(0 0 8px ${col[p.quadrant]}); pointer-events:none; transition: r .2s ease-out;"></circle>
      <circle class="sc-hit" cx="${cx}" cy="${cy}" r="18" fill="transparent" style="cursor:pointer;"></circle>
      <text class="axis" x="${cx}" y="${cy - 11}" text-anchor="middle" style="fill:var(--ink); pointer-events:none;">${esc(p.title.slice(0, 22))}</text>
    </g>`;
  });
  return `<svg class="chart scatter-chart" viewBox="0 0 ${W} ${H}">${g}</svg>
    <div class="legend">${Object.entries(col).map(([k, c]) => `<span><i style="background:${c}"></i>${esc(isJa ? (QUAD_JA[k] || k) : k)}</span>`).join("")}</div>`;
}
function histogram(rows) {
  const isJa = currentLang === "ja";
  if (!rows?.length) return `<p class="note">${isJa ? "レビューの評価スコアがありません。" : "No reviewer scores in these records."}</p>`;
  const max = Math.max(...rows.map(r => r.count));
  const all = Array.from({ length: 11 }, (_, i) => rows.find(r => r.score === i)?.count || 0);
  return `<div class="hist-container" style="display:grid;grid-template-columns:repeat(11,1fr);gap:6px;align-items:end;height:140px">${all.map((c, i) =>
    `<div class="hist-bar" data-score="${i}" data-count="${c}" style="height:${Math.max(2, c / max * 120)}px;border-radius:6px 6px 2px 2px;background:linear-gradient(180deg,var(--naruto-gold),var(--naruto-orange));box-shadow:0 0 10px rgba(255,119,0,.35);cursor:pointer;transition:transform .15s, filter .15s;"></div>`).join("")}</div>
    <div style="display:grid;grid-template-columns:repeat(11,1fr);gap:6px;font-size:11px;color:var(--mute);text-align:center;margin-top:4px">${all.map((_, i) => `<span>${i}</span>`).join("")}</div>`;
}

/* Tooltip & chart hover interactivity */
let _chartTooltipEl = null;
function getChartTooltip() {
  if (!_chartTooltipEl) {
    _chartTooltipEl = document.getElementById("chart-tooltip");
    if (!_chartTooltipEl) {
      _chartTooltipEl = document.createElement("div");
      _chartTooltipEl.id = "chart-tooltip";
      _chartTooltipEl.className = "chart-tooltip";
      document.body.appendChild(_chartTooltipEl);
    }
  }
  return _chartTooltipEl;
}
function positionChartTooltip(e, tt) {
  const pad = 14;
  const rect = tt.getBoundingClientRect();
  const w = rect.width || 170;
  const h = rect.height || 60;
  let x = e.clientX + 16;
  let y = e.clientY - h - 10;
  if (x + w > window.innerWidth - pad) x = e.clientX - w - 16;
  if (y < pad) y = e.clientY + 22;
  tt.style.left = `${Math.max(pad, x)}px`;
  tt.style.top = `${Math.max(pad, y)}px`;
}

document.addEventListener("pointermove", e => {
  const tt = getChartTooltip();
  const isJa = currentLang === "ja";

  // 1. Direct point hover on line chart
  const ptGroup = e.target.closest(".chart-point-group");
  if (ptGroup) {
    const sName = ptGroup.dataset.series;
    const date = ptGroup.dataset.date;
    const val = ptGroup.dataset.val;
    const col = ptGroup.dataset.color || "var(--naruto-orange)";

    const svg = ptGroup.closest("svg.line-chart");
    if (svg) {
      svg.querySelectorAll(".pt-dot").forEach(d => d.setAttribute("r", "3.2"));
      const dot = ptGroup.querySelector(".pt-dot");
      if (dot) dot.setAttribute("r", "6.5");
      const crosshair = svg.querySelector(".chart-crosshair");
      if (crosshair) {
        crosshair.setAttribute("x1", ptGroup.dataset.cx);
        crosshair.setAttribute("x2", ptGroup.dataset.cx);
        crosshair.style.display = "block";
      }
    }

    tt.innerHTML = `
      <div style="font-size:12px; font-weight:700; color:${col}; display:flex; align-items:center; gap:6px;">
        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${col};box-shadow:0 0 8px ${col};"></span>
        ${esc(sName)}
      </div>
      <div style="display:flex; align-items:baseline; gap:6px; margin:4px 0 2px;">
        <span style="font-size:20px; font-weight:900; color:var(--naruto-gold); font-family:'Unbounded',sans-serif;">${val}</span>
        <span style="font-size:11px; font-weight:700; color:var(--mute); text-transform:uppercase;">${isJa ? "指数" : "index"}</span>
      </div>
      <div style="font-size:11.5px; color:var(--mute); font-weight:500;">${isJa ? "観測日:" : "Date:"} <b style="color:var(--ink);">${date}</b></div>
    `;
    tt.style.display = "block";
    positionChartTooltip(e, tt);
    return;
  }

  // 2. Scatter plot point
  const scGroup = e.target.closest(".scatter-point-group");
  if (scGroup) {
    const title = scGroup.dataset.title;
    const quad = scGroup.dataset.quad;
    const level = scGroup.dataset.level;
    const chg = scGroup.dataset.chg;
    const col = scGroup.dataset.color || "var(--naruto-gold)";
    const dot = scGroup.querySelector(".sc-dot");
    if (dot) dot.setAttribute("r", "11");
    tt.innerHTML = `
      <div style="font-size:13px; font-weight:800; color:var(--ink);">${esc(title)}</div>
      <div style="display:flex; align-items:baseline; gap:8px; margin:4px 0 2px;">
        <span style="font-size:18px; font-weight:800; color:${col}; font-family:'Unbounded',sans-serif;">${+chg >= 0 ? '+' : ''}${chg} pts</span>
        <span style="font-size:11px; font-weight:600; color:var(--mute);">${isJa ? "変動" : "change"}</span>
      </div>
      <div style="font-size:11.5px; color:var(--mute);">${isJa ? "直近平均水準:" : "Recent Level:"} <b style="color:var(--naruto-gold);">${level}</b></div>
      <div style="font-size:11px; color:${col}; margin-top:2px; font-weight:600;">● ${esc(quad)}</div>
    `;
    tt.style.display = "block";
    positionChartTooltip(e, tt);
    return;
  }

  // 3. Histogram bar
  const histBar = e.target.closest(".hist-bar");
  if (histBar) {
    const score = histBar.dataset.score;
    const count = histBar.dataset.count;
    tt.innerHTML = `
      <div style="font-size:11px; font-weight:700; color:var(--mute); text-transform:uppercase; letter-spacing:.05em;">${isJa ? "レビュアースコア" : "Reviewer Rating"}</div>
      <div style="font-size:19px; font-weight:900; color:var(--naruto-gold); font-family:'Unbounded',sans-serif; margin:2px 0;">${isJa ? `評価点 ${score} / 10` : `Score ${score} / 10`}</div>
      <div style="font-size:12px; color:var(--ink);"><b style="color:var(--ink);">${count}</b> ${isJa ? "件のレビュー" : "reviews recorded"}</div>
    `;
    tt.style.display = "block";
    positionChartTooltip(e, tt);
    return;
  }

  // 4. Over a line-chart SVG area (tracking nearest points along x-axis)
  const chartSvg = e.target.closest("svg.line-chart");
  if (chartSvg) {
    const pts = Array.from(chartSvg.querySelectorAll(".chart-point-group"));
    if (pts.length) {
      const rect = chartSvg.getBoundingClientRect();
      const viewBox = chartSvg.viewBox.baseVal;
      const W = viewBox ? viewBox.width : rect.width;
      const mouseSvgX = (e.clientX - rect.left) / rect.width * W;

      let closest = pts[0];
      let minDx = Math.abs(+closest.dataset.cx - mouseSvgX);
      for (let i = 1; i < pts.length; i++) {
        const dx = Math.abs(+pts[i].dataset.cx - mouseSvgX);
        if (dx < minDx) {
          minDx = dx;
          closest = pts[i];
        }
      }

      if (minDx < 45) {
        const date = closest.dataset.date;
        const atDate = pts.filter(p => p.dataset.date === date);

        const crosshair = chartSvg.querySelector(".chart-crosshair");
        if (crosshair) {
          crosshair.setAttribute("x1", closest.dataset.cx);
          crosshair.setAttribute("x2", closest.dataset.cx);
          crosshair.style.display = "block";
        }

        pts.forEach(p => {
          const dot = p.querySelector(".pt-dot");
          if (dot) dot.setAttribute("r", p.dataset.date === date ? "6" : "3.2");
        });

        tt.innerHTML = `
          <div style="font-size:11px; font-weight:700; color:var(--mute); text-transform:uppercase; letter-spacing:.05em; margin-bottom:4px;">${isJa ? "観測日:" : "Date:"} <b style="color:var(--ink);">${date}</b></div>
          ${atDate.map(p => `
            <div style="display:flex; justify-content:space-between; align-items:center; gap:14px; margin-top:3px; font-size:12.5px;">
              <span style="color:${p.dataset.color}; display:flex; align-items:center; gap:6px; font-weight:600;">
                <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${p.dataset.color};box-shadow:0 0 6px ${p.dataset.color};"></span>
                ${esc(p.dataset.series)}
              </span>
              <b style="color:var(--naruto-gold); font-size:14px; font-family:'Unbounded',sans-serif;">${p.dataset.val}</b>
            </div>
          `).join("")}
        `;
        tt.style.display = "block";
        positionChartTooltip(e, tt);
        return;
      }
    }
  }

  // Not over any graph element
  if (tt) tt.style.display = "none";
  document.querySelectorAll(".chart-crosshair").forEach(c => c.style.display = "none");
  document.querySelectorAll(".pt-dot").forEach(d => d.setAttribute("r", "3.2"));
  document.querySelectorAll(".sc-dot").forEach(d => d.setAttribute("r", "7"));
});

document.addEventListener("pointerleave", () => {
  const tt = getChartTooltip();
  if (tt) tt.style.display = "none";
  document.querySelectorAll(".chart-crosshair").forEach(c => c.style.display = "none");
  document.querySelectorAll(".pt-dot").forEach(d => d.setAttribute("r", "3.2"));
  document.querySelectorAll(".sc-dot").forEach(d => d.setAttribute("r", "7"));
});
const quote = (q, neg) => `<div class="quote${neg ? " neg" : ""}">“${esc(q.text)}”<small>${currentLang === "ja" ? "引用" : "Excerpt"} · ${q.url ? `<a href="${esc(q.url)}" target="_blank" rel="noopener">${esc(q.source || (currentLang === "ja" ? "情報源" : "source"))}</a>` : esc(q.source || (currentLang === "ja" ? "情報源" : "source"))}${q.date ? " · " + esc(q.date) : ""}</small></div>`;
const relBadge = r => {
  const isJa = currentLang === "ja";
  const label = isJa ? (r === "sufficient" ? "十分" : r === "insufficient" ? "データ不足" : r) : r;
  return `<span class="rel ${esc(r)}">${esc(label)}</span>`;
};
const chg = v => v === null || v === undefined ? "—" : `<span class="${v > 0 ? "up" : v < 0 ? "down" : ""}">${v > 0 ? "▲" : v < 0 ? "▼" : ""} ${Math.abs(v).toFixed(1)}</span>`;
const viewHead = (tag, title, sub) => `<div class="view-head view-fade"><div class="hero-tag"><span></span>${esc(tag)}</div><h1>${esc(title)}</h1><p class="sub">${esc(sub)}</p></div>`;

/* ------------------------------------------------------------- title search */
function searchBox(id, onPick, placeholder = null) {
  const isJa = currentLang === "ja";
  const defPh = isJa ? "作品名または別名を入力（例: 葬送のフリーレン、Frieren）" : "Search a title or alternate title, e.g. Frieren";
  const ph = placeholder || defPh;
  setTimeout(() => {
    const inp = $(`#${id}-q`), out = $(`#${id}-r`);
    let tm;
    inp.addEventListener("input", () => {
      clearTimeout(tm);
      const q = inp.value.trim();
      if (!q) { out.innerHTML = ""; return; }
      tm = setTimeout(async () => {
        out.innerHTML = loading(isJa ? "4.1万件のカタログを検索中…" : "Searching 41k records…");
        try {
          const hits = await api(`/api/search?q=${encodeURIComponent(q)}`);
          out.innerHTML = hits.length ? hits.map(h => `<button data-id="${esc(h.anime_id)}"><span>${esc(h.label)}</span>
              <span><em class="${h.has_trends ? "y" : ""}">${h.has_trends ? (isJa ? "トレンドあり" : "TRENDS") : (isJa ? "トレンドなし" : "no trends")}</em> · <em class="${h.has_reviews ? "y" : ""}">${h.has_reviews ? (isJa ? "レビューあり" : "REVIEWS") : (isJa ? "レビューなし" : "no reviews")}</em></span></button>`).join("")
            : `<p class="note">${isJa ? `「${esc(q)}」に一致する作品が見つかりません。` : `No catalog records match “${esc(q)}”.`}</p>`;
          out.querySelectorAll("button").forEach(b => b.onclick = () => onPick(b.dataset.id));
        } catch (e) { out.innerHTML = `<p class="warn">${esc(e.message)}</p>`; }
      }, 250);
    });
  });
  return `<div class="scanner-input-box"><input type="text" id="${id}-q" placeholder="${esc(ph)}" autocomplete="off"></div><div class="results" id="${id}-r"></div>`;
}

/* =============================================================== I18N & THEME */
const I18N = {
  en: {
    nav_command: "📊 Command",
    nav_radar: "📈 Radar",
    nav_audience: "💬 Audience",
    nav_gems: "💎 Gems",
    nav_lab: "🎨 Lab",
    nav_planner: "🧭 Planner",
    nav_brief: "📄 Brief",
    btn_status: "Data Status",
    btn_replay: "⚡ Replay Intro",
    lang_btn: "日本語",
    theme_light: "☀️ Light",
    theme_dark: "🌙 Dark",
    hero_title: "TURN ANIME FANDOM INTO EVIDENCE.",
    hero_sub: "Measured India search interest, international review evidence and catalog visibility — turned into opportunity hypotheses a Japanese entertainment company can test. Every number below comes from the loaded data.",
    btn_open_radar: "Open Trending Radar →",
    btn_open_audience: "Audience Intelligence",
    btn_open_gems: "Hidden Gems",
    stat_catalog: "Catalog records",
    stat_trends: "Titles with India trend data",
    stat_reviews: "Review records",
    stat_visibility: "Titles with MAL 2020 visibility",
    pulse_title: "India Search Pulse",
    pulse_hint: "Recent window vs baseline, per tracked title. Select a title.",
    pm_latest: "Latest index",
    pm_change: "Change, recent vs baseline mean",
    pm_rel: "Reliability",
    rising_title: "Rising in India",
    rising_hint: "Largest measured relative rises (sufficient data only). Interest is not demand or revenue.",
    coverage_title: "Evidence Coverage",
    coverage_hint: "Which tracked titles have review evidence for Audience Intelligence and Hidden Gems — and what is in your workspace.",
    radar_head: "Audience discovery · Trending Radar",
    radar_sub: "Which titles are gaining attention in India?",
    radar_candidates: "Candidates",
    radar_observed: "Observed index",
    radar_compare: "Compare",
    radar_compare_hint: "Overlay up to 4 series. Levels are only comparable inside one export.",
    radar_filter_placeholder: "Filter tracked titles…",
    radar_clear: "Clear all",
    radar_empty_cmp: "Select up to 4 series above to overlay their trends.",
    radar_vis_mom: "Visibility vs momentum",
    aud_head: "Audience understanding · Audience Intelligence",
    aud_sub: "What do reviewers praise or criticise?",
    gems_head: "Hidden Gems & Mixed-Response Analyzer",
    gems_sub: "Strengths hiding behind mixed reception",
    lab_head: "Localized offerings · Creative Opportunity Lab",
    lab_sub: "From audience themes to a concept worth testing",
    planner_head: "Localization · Monetization · Distribution · Retention",
    planner_sub: "Shape an offer, expose every assumption",
    brief_head: "Deliverable · Opportunity Brief",
    brief_sub: "Decision support, not independent verification.",
    data_head: "Transparency · Data & Methods",
    data_sub: "Where every number comes from"
  },
  ja: {
    nav_command: "📊 司令塔",
    nav_radar: "📈 トレンド",
    nav_audience: "💬 観客分析",
    nav_gems: "💎 隠れた名作",
    nav_lab: "🎨 企画ラボ",
    nav_planner: "🧭 事業計画",
    nav_brief: "📄 提案書",
    btn_status: "データ状況",
    btn_replay: "⚡ OP再生",
    lang_btn: "English",
    theme_light: "☀️ ライト",
    theme_dark: "🌙 ダーク",
    hero_title: "アニメファンダムを、確固たる事業根拠へ。",
    hero_sub: "インド市場の検索トレンド、海外レビュー分析、カタログ認知度を統合。日本のエンタメ企業が即座に検証できる商業展開の仮説を提供します。表示されている数値はすべて実データに基づいています。",
    btn_open_radar: "トレンドレーダーを開く →",
    btn_open_audience: "観客インテリジェンス",
    btn_open_gems: "隠れた名作を探す",
    stat_catalog: "カタログ作品数",
    stat_trends: "インド検索データ作品数",
    stat_reviews: "レビュー総数",
    stat_visibility: "MAL認知度データ作品数",
    pulse_title: "インド検索パルス",
    pulse_hint: "対象作品ごとの基準値 vs 最近の検索トレンド変動。タイトルを選択してください。",
    pm_latest: "最新指標",
    pm_change: "最近 vs 基準値の変動",
    pm_rel: "信頼度",
    rising_title: "インドで急上昇中の作品",
    rising_hint: "計測された相対的な伸びが最も大きい作品群（十分なデータがある作品のみ）。",
    coverage_title: "分析データ網羅状況",
    coverage_hint: "観客インテリジェンスや隠れた名作分析に必要なレビューデータが揃っている作品一覧。",
    radar_head: "オーディエンス発掘 · トレンドレーダー",
    radar_sub: "インド市場で注目を集めている日本アニメ作品は？",
    radar_candidates: "分析候補タイトル",
    radar_observed: "観測された検索推移",
    radar_compare: "複数タイトルの比較",
    radar_compare_hint: "最大4作品を重ねて比較。※数値レベルは同一エクスポート内でのみ直接比較可能です。",
    radar_filter_placeholder: "タイトルを絞り込み…",
    radar_clear: "すべて解除",
    radar_empty_cmp: "上記から最大4作品を選択して推移を比較できます。",
    radar_vis_mom: "認知度 vs 成長性 (モメンタム)",
    aud_head: "観客理解 · 観客インテリジェンス",
    aud_sub: "レビュー層が賞賛・指摘するポイントは？",
    gems_head: "隠れた名作・賛否両論分析",
    gems_sub: "賛否両論の裏に隠された強みを発掘",
    lab_head: "現地向け展開 · クリエイティブラボ",
    lab_sub: "観客テーマから検証すべき企画コンセプトへ",
    planner_head: "現地化 · 収益化 · 流通 · ファン定着",
    planner_sub: "提供形態の具体化と前提条件の検証",
    brief_head: "成果物 · 事業機会提案書",
    brief_sub: "意思決定支援のための統合レポート。",
    data_head: "透明性 · データと手法",
    data_sub: "すべての数値の根拠と算出ロジック"
  }
};

let currentLang = localStorage.getItem("aniscope_lang") || "en";
function t(key) {
  return (I18N[currentLang] && I18N[currentLang][key]) || (I18N.en && I18N.en[key]) || key;
}

function updateNavText() {
  const isJa = currentLang === "ja";
  document.querySelectorAll("#nav-links a").forEach(a => {
    const v = a.dataset.view;
    if (v) a.textContent = t("nav_" + v);
  });
  const mob = $("#nav-mobile");
  if (mob) {
    Array.from(mob.options).forEach(opt => {
      const v = opt.value;
      if (v) opt.textContent = t("nav_" + v);
    });
  }
  const btnLang = $("#lang-btn-text");
  if (btnLang) btnLang.textContent = isJa ? "English" : "日本語";

  const btnReplay = $("#btn-replay-intro");
  if (btnReplay) btnReplay.textContent = t("btn_replay");

  const btnStatus = $("#btn-status");
  if (btnStatus) btnStatus.textContent = t("btn_status");

  const btnSkip = $("#btn-skip-intro");
  if (btnSkip) btnSkip.textContent = isJa ? "スキップ [Esc]" : "Skip Intro [Esc]";

  const curTheme = localStorage.getItem("aniscope_theme") || "dark";
  const btnTheme = $("#theme-btn-text");
  if (btnTheme) btnTheme.textContent = curTheme === "light" ? (isJa ? "🌙 ダーク" : "🌙 Dark") : (isJa ? "☀️ ライト" : "☀️ Light");

  const f1 = $("#footer-text-1"), f2 = $("#footer-text-2");
  if (f1) f1.innerHTML = isJa
    ? `<b>AniScope AI (観)</b> · <a href="#/data" style="color:var(--naruto-gold)">データと手法</a>`
    : `<b>AniScope AI (観)</b> · <a href="#/data" style="color:var(--naruto-gold)">Data &amp; Methods</a>`;
  if (f2) f2.textContent = isJa
    ? `観測データに基づく意思決定支援（予測値ではありません）。カタログ: Anime Offline Database (ODbL v1.0 + DbCL v1.0)`
    : `Decision support from observed data — not forecasts. Catalog: Anime Offline Database (ODbL v1.0 + DbCL v1.0).`;

  const lt = $(".logo-tag");
  if (lt) lt.textContent = isJa ? "日本 × インド" : "Japan × India";

  const inSub = $(".in-sub");
  if (inSub) inSub.textContent = isJa ? "インド向けアニメ市場インテリジェンス" : "ANIME AUDIENCE INTELLIGENCE FOR INDIA";
  const inChips = $(".in-chips");
  if (inChips) inChips.innerHTML = isJa
    ? `<span style="--i:0">📈 インド検索トレンド</span><span style="--i:1">💬 観客レビュー分析</span><span style="--i:2">💎 隠れた名作発掘</span>`
    : `<span style="--i:0">📈 India trend radar</span><span style="--i:1">💬 Review intelligence</span><span style="--i:2">💎 Hidden gems</span>`;
  if (typeof updateSoundToggleBtn === "function") updateSoundToggleBtn();

  document.title = isJa
    ? "AniScope AI · インド向けアニメ市場インテリジェンス"
    : "AniScope AI · Anime Audience Intelligence for India";
}

/* =============================================================== COMMAND */
async function viewCommand(el) {
  const isJa = currentLang === "ja";
  const s = await api("/api/status"); S.status = s;
  if (!s.catalog_ok) { el.innerHTML = `<header class="hero">${catalogMissing(s)}</header>`; Shinigami({ cautions: [isJa ? "アニメカタログが見つからないため、分析を開始できません。" : "I can't find the anime catalog, so nothing can be analysed yet."] }); return; }
  const c = s.coverage, m = s.summary;
  const tr = await api("/api/trends");
  const rows = (tr.rows || []).filter(r => r.reliability !== "insufficient");
  el.innerHTML = `
  <header class="hero view-fade">
    <h1>${t("hero_title")}</h1>
    <p class="sub">${t("hero_sub")}</p>
    <div class="cta-group">
      <a href="#/radar" class="btn">${t("btn_open_radar")}</a>
      <a href="#/audience" class="btn ghost">${t("btn_open_audience")}</a>
      <a href="#/gems" class="btn ghost">${t("btn_open_gems")}</a>
    </div>
    <div class="hero-stats">
      <div class="stat-box"><b>${fmt(m.records)}</b><span>${t("stat_catalog")} · ${isJa ? "スナップショット" : "snapshot"} ${esc(s.snapshot || "—")}</span></div>
      <div class="stat-box"><b>${fmt(c.trend_titles)}</b><span>${t("stat_trends")} · ${fmt(c.trend_exports)} ${isJa ? "件のエクスポート" : "exports"}</span></div>
      <div class="stat-box"><b>${fmt(c.reviews)}</b><span>${t("stat_reviews")} · ${fmt(c.review_titles)} ${isJa ? "作品" : "titles"}</span></div>
      <div class="stat-box"><b>${fmt(c.visibility_titles)}</b><span>${t("stat_visibility")}</span></div>
    </div>
  </header>
  ${rows.length ? `<div class="mq" aria-hidden="true"><div>${("<span>" + rows.map(r => `${esc(r.query.toUpperCase())} ${r.pct_change === null ? "" : (r.pct_change >= 0 ? "▲" : "▼") + Math.abs(r.pct_change).toFixed(0) + "%"}`).join(" ✦ ") + " ✦ </span>").repeat(4)}</div></div>` : ""}
  <main class="grid">
    <section class="card map" id="pulse">
      <div class="card-header"><div><h2>${t("pulse_title")}</h2>
        <p class="hint">${t("pulse_hint")}</p></div>
        <span class="pill-badge orange">● ${esc(tr.market || (isJa ? "対象市場なし" : "No market"))}</span></div>
      <div class="mapbody" style="align-items:start">
        <div class="list" id="pulse-list"></div>
        <div id="pulse-chart">${tr.empty ? `<div class="empty"><h3>${isJa ? "検索トレンドデータがありません" : "No trend observations"}</h3>${isJa ? "トレンドレーダーでGoogle Trendsデータをインポートしてください。" : "Import a Google Trends export in Trending Radar."}</div>` : ""}</div>
      </div>
      <div class="map-metrics"><div><b id="pm-v">—</b><span id="pm-n">${t("pm_latest")}</span></div><div><b id="pm-c">—</b><span>${t("pm_change")}</span></div><div><b id="pm-r">—</b><span id="pm-x">${t("pm_rel")}</span></div></div>
    </section>
    <section class="card merch" id="featured">
      <div class="card-header"><div><h2>${t("rising_title")}</h2><p class="hint">${t("rising_hint")}</p></div>
        <span class="pill-badge">${kind("calc", "Calculated")}</span></div>
      <div class="items" id="featured-grid"></div>
    </section>
    <section class="card flow" id="pipeline">
      <div class="card-header"><div><h2>${t("coverage_title")}</h2><p class="hint">${t("coverage_hint")}</p></div>
        <a class="btn ghost btn-sm" href="#/data">${isJa ? "データと手法" : "Data & Methods"}</a></div>
      <div class="cols" id="cov-cols">${loading()}</div>
    </section>
    <section class="card scanner-card" id="lookup">
      <div><span class="pill-badge orange" style="margin-bottom:12px">${isJa ? `カタログ検索 · ${fmt(m.records)}件` : `Catalog Search · ${fmt(m.records)} records`}</span>
        <h2>${isJa ? "データ根拠検索" : "Evidence Lookup"}</h2>
        <p class="hint">${isJa ? "作品名または別名で検索。利用可能な分析データと未連携データを即座に確認できます。" : "Search any title or alternate title. AniScope shows exactly which evidence exists for it — and what does not."}</p>
        ${searchBox("cc", id => showLookup(id))}</div>
      <div class="cert-preview" id="lookup-box"><div class="cert-status"><div class="cert-seal">観</div><div><h3 style="margin:0;font-size:17px;color:var(--ink)">${isJa ? "作品を選択" : "Pick a title"}</h3>
        <div style="font-size:12.5px;color:var(--mute)">${isJa ? "データの網羅状況がここに表示されます。" : "Evidence coverage appears here."}</div></div></div></div>
    </section>
    <section class="partners"><span>${isJa ? "データソース:" : "Data sources:"}</span>
      <b title="ODbL v1.0 + DbCL v1.0">Anime Offline Database</b><b title="${isJa ? "エクスポートごとの相対0-100指数" : "Relative 0–100 index per export"}">Google Trends · India</b>
      <b title="${isJa ? "2020年Kaggleスナップショット（全世界）" : "Kaggle snapshot, 2020, global users"}">MyAnimeList 2020</b><b title="${isJa ? "ルールベース感情極性辞書" : "Rule-based lexicon"}">VADER sentiment</b></section>
  </main>`;

  // pulse list + chart
  const list = $("#pulse-list");
  const pick = async i => {
    const r = rows[i];
    list.querySelectorAll("button").forEach((b, j) => b.classList.toggle("on", i === j));
    $("#pm-v").textContent = fmt(r.latest_value); $("#pm-n").textContent = isJa ? `最新検索指数 · ${r.query}` : `Latest index · ${r.query}`;
    $("#pm-c").innerHTML = pct(r.pct_change); $("#pm-r").textContent = isJa ? (r.reliability === "sufficient" ? "十分" : "データ不足") : r.reliability; $("#pm-x").textContent = isJa ? `信頼度 · ${r.export}` : `Reliability · ${r.export}`;
    sfx(window.sfxCrossSealSnap);
    try {
      const sr = await api(`/api/trends/series?anime_id=${encodeURIComponent(r.anime_id)}&query=${encodeURIComponent(r.query)}`);
      $("#pulse-chart").innerHTML = lineChart([{ name: r.query, points: sr.points }], {
        w: 460, h: 300, bands: [
          { from: sr.baseline_window[0], to: sr.baseline_window[1], cls: "band-b", label: isJa ? "基準期間" : "baseline" },
          { from: sr.recent_window[0], to: sr.recent_window[1], cls: "band-r", label: isJa ? "直近期間" : "recent" }]
      })
        + `<div class="row mt-s"><button class="btn btn-sm" id="pulse-go">${isJa ? `${esc(r.query)} を詳しく調査 →` : `Investigate ${esc(r.query)} →`}</button><button class="btn ghost btn-sm" id="pulse-d">${isJa ? "詳細" : "Details"}</button></div>`;
      $("#pulse-go").onclick = () => selectTitle(r.anime_id, "#/radar");
      $("#pulse-d").onclick = () => openTitle(r.anime_id);
    } catch (e) { $("#pulse-chart").innerHTML = `<p class="warn">${esc(e.message)}</p>`; }
  };
  rows.forEach((r, i) => { const b = document.createElement("button"); b.innerHTML = `<span>${esc(r.query)}</span> <em>${pct(r.pct_change)}</em>`; b.onclick = () => pick(i); list.appendChild(b); });
  if (rows.length) pick(0);

  // featured
  const rising = rows.filter(r => r.reliability === "sufficient" && r.pct_change > 0).sort((a, b) => b.pct_change - a.pct_change).slice(0, 4);
  const grads = ["#FF7700, #FFCC00", "#10B981, #064E3B", "#00F0FF, #3B82F6", "#F59E0B, #DC2626"];
  $("#featured-grid").innerHTML = rising.length ? rising.map((r, i) => `<div class="it">
      <div class="art-thumb" style="background:linear-gradient(135deg, ${grads[i]})"><span>${esc(r.query.slice(0, 1))}</span><span class="series-label">${esc(r.query.toUpperCase().slice(0, 22))}</span></div>
      <span class="verified-tag">${isJa ? "✓ インド実測データ" : "✓ Measured · India"}</span><h4>${esc(r.title)}</h4>
      <div class="price-line"><b>${pct(r.pct_change)}</b> · ${fmt(r.baseline_mean, 1)} → ${fmt(r.recent_mean, 1)} ${isJa ? "指数" : "index"}</div>
      <div class="it-actions"><button class="btn btn-sm" data-go="${esc(r.anime_id)}">${isJa ? "調査する" : "Investigate"}</button><button class="btn ghost btn-sm" data-d="${esc(r.anime_id)}">${isJa ? "詳細" : "Details"}</button></div></div>`).join("")
    : `<div class="empty" style="grid-column:span 2"><h3>${isJa ? "急上昇作品がありません" : "No measured rises"}</h3>${isJa ? "比較期間において十分なデータで上昇した作品はありません。" : "No series with sufficient data rose over the comparison window."}</div>`;
  $("#featured-grid").querySelectorAll("[data-go]").forEach(b => b.onclick = () => selectTitle(b.dataset.go, "#/radar"));
  $("#featured-grid").querySelectorAll("[data-d]").forEach(b => b.onclick = () => openTitle(b.dataset.d));

  // coverage columns
  const tracked = tr.rows || [];
  const covs = await Promise.all(tracked.map(r => api(`/api/title/${encodeURIComponent(r.anime_id)}`).then(d => ({ r, n: d.reviews })).catch(() => ({ r, n: 0 }))));
  const withRev = covs.filter(x => x.n > 0), without = covs.filter(x => x.n === 0);
  const ws = S.ws || {};
  const task = (x, cls) => `<div class="task-card ${cls}" data-id="${esc(x.r.anime_id)}"><div class="task-title">${esc(x.r.query)}</div>
      <div class="task-meta"><span>${esc(x.r.export)}</span><b>${x.n ? fmt(x.n) + (isJa ? "件のレビュー" : " reviews") : (isJa ? "レビュー0件" : "0 reviews")}</b></div></div>`;
  $("#cov-cols").innerHTML = `
    <div class="col"><div class="col-header"><h3>${isJa ? "✓ トレンド + レビューあり" : "✓ Trends + reviews"}</h3><span class="col-count">${withRev.length}</span></div>
      ${withRev.map(x => task(x, "paid")).join("") || `<p class="note">${isJa ? "追跡中の作品にレビューデータが連携されていません。<code>reviews.csv</code> をインポートしてください。" : "No tracked title has linked reviews yet. Import <code>reviews.csv</code> with <code>python scripts/ingest.py reviews-kaggle data/raw/reviews.csv</code>."}</p>`}</div>
    <div class="col"><div class="col-header"><h3>${isJa ? "⚠ トレンドのみ（レビューなし）" : "⚠ Trends only — no reviews"}</h3><span class="col-count">${without.length}</span></div>
      ${without.map(x => task(x, "")).join("") || `<p class="note">${isJa ? "すべての追跡中作品にレビューデータが存在します。" : "Every tracked title has review evidence."}</p>`}</div>
    <div class="col"><div class="col-header"><h3>${isJa ? "🎨 ワークスペース" : "🎨 Workspace"}</h3><span class="col-count">${[ws.selected_anime_id, ws.concept, ws.plan].filter(Boolean).length}</span></div>
      ${ws.selected_label ? `<div class="task-card active"><div class="task-title">${esc(ws.selected_label)}</div><div class="task-meta"><span>${isJa ? "選択中の作品" : "Selected title"}</span><b>${esc((ws.selected_themes || []).length)}${isJa ? "個のテーマ" : " themes"}</b></div></div>` : `<p class="note">${isJa ? "作品が選択されていません。" : "No title selected."}</p>`}
      ${ws.concept ? `<div class="task-card active" onclick="location.hash='#/lab'"><div class="task-title">${esc(ws.concept.working_title)}</div><div class="task-meta"><span>${isJa ? "企画コンセプト" : "Concept"}</span><b>${isJa ? "未検証" : "Unvalidated"}</b></div></div>` : ""}
      ${(ws.saved_briefs || []).slice(-2).map(b => `<div class="task-card paid" onclick="location.hash='#/brief'"><div class="task-title">${esc(b.title)}</div><div class="task-meta"><span>${isJa ? "保存済み提案書" : "Saved brief"}</span><b>${esc(b.generated_at)}</b></div></div>`).join("")}</div>`;
  $("#cov-cols").querySelectorAll(".task-card[data-id]").forEach(t => t.onclick = () => openTitle(t.dataset.id));

  const cautions = [], discoveries = [];
  if (!c.reviews) cautions.push(isJa ? "レビューデータが読み込まれていないため、全作品の観客評価（強み・批判点）は未把握の状態です。" : "No review evidence is loaded, so audience strengths and criticisms are unknown for every title.");
  else if (without.length) cautions.push(isJa ? `追跡中の${tracked.length}作品中、${without.length}作品にレビューデータが紐付いていません。` : `${without.length} of ${tracked.length} tracked titles have no linked review evidence; their audience findings stay unavailable.`);
  if (rising.length) discoveries.push(isJa ? `「${rising[0].query}」が${tr.market}市場において最も高い相対的な伸びを示しています: ${pct(rising[0].pct_change)} (${fmt(rising[0].baseline_mean, 1)} → ${fmt(rising[0].recent_mean, 1)} 指数)。※検索数は直ちに商業需要を示すものではありません。` : `${rising[0].query} shows the largest measured relative rise in ${tr.market}: ${pct(rising[0].pct_change)} (${fmt(rising[0].baseline_mean, 1)} → ${fmt(rising[0].recent_mean, 1)} index). Search interest is not demand.`);
  if (tr.multi_export) cautions.push(isJa ? `${tr.exports.length}個のGoogle Trendsエクスポートはそれぞれ独立した0-100スケールのため、比較には変動率(%)のみを使用しています。` : `The ${tr.exports.length} Trends exports have separate 0–100 scales, so only % changes are compared across them.`);
  Shinigami({ cautions, discoveries, guide: isJa ? "作品を検索するか、トレンドレーダーを開いて指数の推移を比較してください。" : "Search a title, or open Trending Radar to compare measured momentum." });
}

async function showLookup(id) {
  const isJa = currentLang === "ja";
  const box = $("#lookup-box");
  box.innerHTML = loading();
  try {
    const d = await api(`/api/title/${encodeURIComponent(id)}`);
    const r = d.record;
    box.style.borderColor = d.reviews || d.trend_obs ? "var(--leaf-green)" : "var(--naruto-gold)";
    box.innerHTML = `<div class="cert-status"><div class="cert-seal">観</div><div><h3 style="margin:0;font-size:17px;color:var(--ink)">${esc(r.label)}</h3>
      <div style="font-size:12.5px;color:${d.reviews ? "var(--leaf-green)" : "var(--naruto-gold)"}">${d.trend_obs ? (isJa ? "✓ インド検索トレンドデータあり" : "✓ India trend data") : (isJa ? "✗ トレンドデータ未連携" : "✗ No trend data")} · ${d.reviews ? "✓ " + fmt(d.reviews) + (isJa ? "件のレビュー" : " reviews") : (isJa ? "✗ レビューデータ未連携" : "✗ No review evidence")}</div></div></div>
      <div style="font-size:13px;line-height:1.7;color:var(--mute)"><b>${isJa ? "カタログ評価スコア:" : "Catalog score:"}</b> ${r.score ? fmt(r.score, 2) + "/10 (" + (isJa ? "世界複数サイト" : "global, cross-site") + ")" : "—"}<br>
      <b>${isJa ? "認知度:" : "Visibility:"}</b> ${esc(formatVisibility(d.visibility))}<br><b>IDs:</b> MAL ${esc(r.mal_id || "—")} · AniList ${esc(r.anilist_id || "—")}</div>
      <div class="row mt"><button class="btn btn-sm" id="lk-go">${isJa ? "この作品を調査対象に設定" : "Select for investigation"}</button><button class="btn ghost btn-sm" id="lk-d">${isJa ? "詳細を見る" : "Details"}</button></div>`;
    $("#lk-go").onclick = async () => { await selectTitle(r.anime_id); toast(isJa ? `「${r.label}」を選択しました。` : `Selected ${r.label}.`); };
    $("#lk-d").onclick = () => openTitle(r.anime_id);
  } catch (e) { box.innerHTML = `<p class="warn">${esc(e.message)}</p>`; }
}
/* ================================================================= RADAR */
async function viewRadar(el, params = {}) {
  const isJa = currentLang === "ja";
  const q = new URLSearchParams(params);
  const tr = await api(`/api/trends?${q}`);
  el.innerHTML = viewHead(t("radar_head"), t("radar_sub"),
    isJa ? "認知度（水準）とモメンタム（成長率）は、日付付きGoogle Trends実測データのみから個別に計測されます。推計や補完は一切行いません。"
      : "Visibility (level) and momentum (growth) are measured separately, from dated Google Trends observations only. Nothing is estimated or filled in.") +
    `<main class="grid" id="radar-grid"></main>`;
  const grid = $("#radar-grid");
  if (tr.empty) {
    grid.innerHTML = `<section class="card span-12"><div class="empty"><h3>${isJa ? "検索トレンドデータがまだありません" : "No trend observations yet"}</h3>${isJa ? "下のフォームからGoogle Trends CSV（地域: インド、過去5年間）をインポートしてください。" : "Import a Google Trends “Interest over time” CSV below (region India, past 5 years)."}</div></section>` + importTrendsCard();
    bindImportTrends(); Shinigami({ cautions: [isJa ? "日付付きの検索トレンドデータが存在しないため、成長率を算出できません。" : "No dated trend observations are loaded, so I cannot measure growth for any title."] }); return;
  }
  const rows = tr.rows;
  grid.innerHTML = `
    <section class="card span-12"><div class="fields c4">
      <label class="field">${isJa ? "対象市場（データに基づく）" : "Market (from the data)"}<select id="f-market">${tr.markets.map(m => `<option ${m === tr.market ? "selected" : ""}>${esc(m)}</option>`).join("")}</select></label>
      <label class="field">${isJa ? `比較期間 (${esc(tr.unit === "month" ? "ヶ月" : "週")})` : `Comparison window (${esc(tr.unit)}s)`}<input type="number" id="f-win" min="2" max="${tr.unit === "month" ? 24 : 52}" value="${esc(tr.window)}"></label>
      <label class="field">${isJa ? "開始日" : "From"}<input type="date" id="f-start" value="${esc(params.start || tr.date_min)}" min="${esc(tr.date_min)}" max="${esc(tr.date_max)}"></label>
      <label class="field">${isJa ? "終了日" : "To"}<input type="date" id="f-end" value="${esc(params.end || tr.date_max)}" min="${esc(tr.date_min)}" max="${esc(tr.date_max)}"></label></div>
      <p class="note">${isJa ? `${esc(tr.frequency === "monthly" ? "月次" : tr.frequency)}データ · 直近期間 = 最新データから直近${esc(tr.window)}${esc(tr.unit === "month" ? "ヶ月" : "週")}; 基準期間 = その直前の${esc(tr.window)}${esc(tr.unit === "month" ? "ヶ月" : "週")}。変動 = 直近平均 − 基準平均（同一エクスポート内でのみ直接比較可能）。` : `${esc(tr.frequency)} data · recent window = last ${esc(tr.window)} ${esc(tr.unit)}s up to the latest observation; baseline = the ${esc(tr.window)} before. Change = mean(recent) − mean(baseline), in index points, comparable only within one export.`} ${tr.multi_export ? (isJa ? "各エクスポートは独立した0-100スケールのため、変動率(%)で順位付けされます。" : "Ranked by % change (baseline ≥ 1 point) because the exports have separate scales.") : ""}</p></section>
    <section class="card span-12"><div class="card-header"><div><h2>${t("radar_candidates")} ${kind("calc", "Calculated")}</h2><p class="hint">${isJa ? "行をクリックすると推移グラフを表示。「信頼度不足」の系列は順位付けから除外されます。" : "Click a row to chart it. ‘Insufficient’ series are not ranked."}</p></div>
      <span class="pill-badge orange">${rows.length} ${isJa ? "系列" : "series"} · ${esc(tr.market)}</span></div>
      <div class="tbl-wrap"><table class="tbl"><thead><tr>
        <th>${isJa ? "作品名" : "Title"}</th><th>${isJa ? "検索クエリ" : "Query"}</th><th>${isJa ? "エクスポート" : "Export (own scale)"}</th><th>${isJa ? "最新値" : "Latest"}</th>
        <th>${isJa ? "基準平均" : "Baseline"}</th><th>${isJa ? "直近平均" : "Recent"}</th><th>${isJa ? "変動(pt)" : "Change (pts)"}</th><th>${isJa ? "変動率" : "Change %"}</th>
        <th>${isJa ? "観測数" : "Obs."}</th><th>${isJa ? "0値比率" : "Zeros in windows"}</th><th>${isJa ? "信頼度" : "Reliability"}</th>
      </tr></thead>
      <tbody>${rows.map((r, i) => `<tr class="click" data-i="${i}"><td>${esc(r.title)}</td><td>${esc(r.query)}</td><td>${esc(r.export)}</td><td class="num">${fmt(r.latest_value)}</td>
        <td class="num">${fmt(r.baseline_mean, 1)}</td><td class="num">${fmt(r.recent_mean, 1)}</td><td class="num">${chg(r.abs_change)}</td><td class="num">${pct(r.pct_change)}</td>
        <td class="num">${fmt(r.observations)}</td><td class="num">${fmt(r.zero_share * 100)}%</td><td>${relBadge(r.reliability)}</td></tr>`).join("")}</tbody></table></div></section>
    <div class="radar-split span-12">
    <section class="card"><div class="card-header"><div><h2>${t("radar_observed")} ${kind("observed", "Observed")}</h2><p class="hint" id="ch-sub">${isJa ? "系列を選択してください。" : "Select a series."}</p></div></div>
      <div id="chart"></div><div id="ch-exp"></div></section>
    <section class="card cmp-card"><div class="card-header"><div><h2>${t("radar_compare")}</h2><p class="hint">${t("radar_compare_hint")}</p></div>
      <div class="row" style="gap:10px;align-items:center"><button type="button" class="linklike" id="cmp-clear" style="display:none;font-size:12px">${t("radar_clear")}</button><span class="pill-badge orange" id="cmp-count">0 / 4</span></div></div>
      <div class="cmp-picker"><input type="text" class="inp" id="cmp-q" placeholder="${t("radar_filter_placeholder")}" autocomplete="off" aria-label="Filter tracked titles to compare"></div>
      <div class="chips mt" id="cmp-chips"></div>
      <div id="cmp-chart" class="mt"></div></section>
    </div>
    <section class="card span-12"><div class="card-header"><div><h2>${t("radar_vis_mom")} ${kind("interp", "Interpretation")}</h2>
      <p class="hint">${isJa ? "同一エクスポート内の作品のみ。「新興・急上昇」= 低水準・上昇傾向（将来予測ではなく調査候補の根拠）。" : "Titles inside one export only. ‘Emerging’ = lower level, rising — a reason to investigate, not a prediction."}</p></div>
      <label class="field" style="min-width:220px">${isJa ? "エクスポート" : "Export"}<select id="q-exp">${tr.exports.map(x => `<option>${esc(x)}</option>`).join("")}</select></label></div>
      <div id="quad">${loading()}</div></section>
    ${importTrendsCard()}`;
  const apply = () => viewRadar(el, { market: $("#f-market").value, [tr.unit === "month" ? "months" : "weeks"]: $("#f-win").value, start: $("#f-start").value, end: $("#f-end").value });
  ["f-market", "f-win", "f-start", "f-end"].forEach(id => $("#" + id).onchange = apply);
  const months = tr.unit === "month" ? tr.window : 6;
  const show = async i => {
    const r = rows[i];
    grid.querySelectorAll("tr.click").forEach(t => t.classList.toggle("on", +t.dataset.i === i));
    $("#ch-sub").textContent = `${r.title} — “${r.query}” · ${r.export}`;
    $("#chart").innerHTML = loading();
    const sr = await api(`/api/trends/series?anime_id=${encodeURIComponent(r.anime_id)}&query=${encodeURIComponent(r.query)}&months=${months}&start=${$("#f-start").value}&end=${$("#f-end").value}`);
    $("#chart").innerHTML = lineChart([{ name: r.query, points: sr.points }], {
      w: 1100, h: 400, bands: [
        { from: sr.baseline_window[0], to: sr.baseline_window[1], cls: "band-b", label: isJa ? "基準期間" : "baseline" },
        { from: sr.recent_window[0], to: sr.recent_window[1], cls: "band-r", label: isJa ? "直近期間" : "recent" }]
    });
    $("#ch-exp").innerHTML = `<p class="note">${kind("calc", "Calculated")} ${esc(formatExplanation(sr))}</p>${sr.reasons.map(x => `<p class="warn">⚠ ${esc(formatReason(x))}</p>`).join("")}
      <p class="note">${isJa ? "情報源:" : "Source:"} ${esc(sr.source)} · ${isJa ? "市場:" : "market:"} ${esc(sr.geo || (isJa ? "未指定" : "unspecified"))}</p>
      <div class="row mt-s"><button class="btn btn-sm" id="ch-go">${isJa ? "この作品を調査する →" : "Investigate this title →"}</button><button class="btn ghost btn-sm" id="ch-d">${isJa ? "詳細" : "Details"}</button></div>`;
    $("#ch-go").onclick = () => selectTitle(r.anime_id, "#/audience");
    $("#ch-d").onclick = () => openTitle(r.anime_id);
    sfx(window.sfxCrossSealSnap);
  };
  grid.querySelectorAll("tr.click").forEach(t => t.onclick = () => show(+t.dataset.i));
  const selIdx = rows.findIndex(r => S.ws && r.anime_id === S.ws.selected_anime_id);
  show(selIdx >= 0 ? selIdx : 0);
  const cmpSel = [];
  const cmpQ = $("#cmp-q"), cmpChips = $("#cmp-chips"), cmpClear = $("#cmp-clear");
  const drawCompare = async () => {
    $("#cmp-count").textContent = `${cmpSel.length} / 4`;
    if (cmpClear) cmpClear.style.display = cmpSel.length ? "inline-block" : "none";
    renderChips();
    if (!cmpSel.length) {
      $("#cmp-chart").innerHTML = `<div class="empty" style="padding:28px 20px;text-align:center;color:var(--mute)">${t("radar_empty_cmp")}</div>`;
      return;
    }
    $("#cmp-chart").innerHTML = loading();
    const series = await Promise.all(cmpSel.map(async j => {
      const r = rows[j];
      const sr = await api(`/api/trends/series?anime_id=${encodeURIComponent(r.anime_id)}&query=${encodeURIComponent(r.query)}`);
      return { name: `${r.query} (${r.export.replace("trends_india_", "")})`, points: sr.points, exp: r.export };
    }));
    const exps = new Set(series.map(x => x.exp));
    $("#cmp-chart").innerHTML = lineChart(series, { w: 1100, h: 480, label: isJa ? "比較推移グラフ" : "Comparison chart" }) + (exps.size > 1 ? `<p class="warn">${isJa ? "⚠ 異なるエクスポート: 数値レベルではなくグラフ形状を比較してください。" : "⚠ Different exports: compare shapes, not levels."}</p>` : "");
  };
  const renderChips = () => {
    const q = cmpQ.value.trim().toLowerCase();
    const hits = rows.map((r, i) => ({ r, i })).filter(({ r }) => !q || r.query.toLowerCase().includes(q) || r.title.toLowerCase().includes(q));
    cmpChips.innerHTML = hits.length ? hits.map(({ r, i }) => {
      const active = cmpSel.includes(i);
      return `<button type="button" data-i="${i}" class="${active ? "active" : ""}" title="${esc(r.title)} · ${r.export.replace("trends_india_", "")}">${esc(r.query)}</button>`;
    }).join("") : `<p class="note" style="margin:6px 0">${isJa ? "該当する作品が見つかりません。" : "No tracked title matches."}</p>`;
    cmpChips.querySelectorAll("button").forEach(b => {
      b.onclick = () => {
        const i = +b.dataset.i;
        if (cmpSel.includes(i)) cmpSel.splice(cmpSel.indexOf(i), 1);
        else if (cmpSel.length < 4) cmpSel.push(i);
        else return toast(isJa ? "比較できるのは最大4作品までです。" : "Compare up to 4 series.");
        drawCompare();
      };
    });
  };
  if (cmpClear) cmpClear.onclick = () => { cmpSel.length = 0; drawCompare(); };
  cmpQ.oninput = renderChips;
  cmpQ.onkeydown = e => { if (e.key === "Escape") { cmpQ.value = ""; renderChips(); } };
  drawCompare();
  const quad = async () => {
    const pts = await api(`/api/trends/quadrant?export=${encodeURIComponent($("#q-exp").value)}&market=${encodeURIComponent(tr.market)}&months=${months}`);
    $("#quad").innerHTML = pts.length >= 3 ? scatter(pts) : `<p class="note">${isJa ? "このエクスポートで散布図を描画するには、十分なデータを持つ作品が少なくとも3件必要です。" : "Needs at least three series with enough observations in this export."}</p>`;
  };
  $("#q-exp").onchange = quad; quad();
  bindImportTrends();
  const suff = rows.filter(r => r.reliability === "sufficient" && r.pct_change !== null);
  const top = [...suff].sort((a, b) => b.pct_change - a.pct_change)[0];
  const cautions = [];
  if (tr.market !== "India") cautions.push(isJa ? `これらのデータはインドではなく「${tr.market}」のものです。` : `These observations are for '${tr.market}', not India.`);
  if (tr.multi_export) cautions.push(isJa ? `${tr.exports.length}個のエクスポートは個別に正規化されているため、異なるエクスポート間での数値比較はできません。` : `The ${tr.exports.length} exports were scaled separately and share no anchor title, so index levels are not scalable between them.`);
  if (!suff.length) cautions.push(isJa ? "十分な観測数を持つ系列がないため、信頼性の高い成長率を算出できません。" : "No series has enough observations in both windows for a reliable growth figure.");
  Shinigami({ cautions, discoveries: top && top.pct_change > 0 ? [isJa ? `「${top.query}」が最も高い相対的成長を示しています: ${pct(top.pct_change)} (${fmt(top.baseline_mean, 1)} → ${fmt(top.recent_mean, 1)})。※検索数は直ちに売上や需要を意味するものではありません。` : `${top.query} shows the largest measured relative rise: ${pct(top.pct_change)} (${fmt(top.baseline_mean, 1)} → ${fmt(top.recent_mean, 1)}). Search interest is not demand or revenue.`] : [], guide: isJa ? "行を選択するとグラフを描画します。" : "Select a row to chart it." });
}

const importTrendsCard = () => {
  const isJa = currentLang === "ja";
  return `<section class="card span-12 no-print"><div class="card-header"><div><h2>${isJa ? "トレンドデータのインポート" : "Import trend data"}</h2>
  <p class="hint">${isJa ? "Google Trends CSV（日付、値、作品名/IDを含むCSV）。<code>data/mappings/trend_query_map.csv</code> または完全一致で照合されます。" : "Google Trends CSV (native export or any CSV with date, value and title/anime_id columns). Titles link through the verified map in <code>data/mappings/trend_query_map.csv</code> or by exact title."}</p></div></div>
  <div class="fields c3"><label class="field">${isJa ? "CSVファイル" : "CSV file"}<input type="file" id="tr-file" accept=".csv"></label>
  <label class="field">${isJa ? "対象地域（ファイルに地域情報がない場合）" : "Market (only if the file has no geography)"}<input type="text" id="tr-geo" placeholder="${isJa ? "例: India（不明な場合は空欄）" : "e.g. India — leave blank if unsure"}"></label>
  <div class="field">&nbsp;<button class="btn" id="tr-imp">${isJa ? "検証してインポート" : "Validate &amp; import"}</button></div></div><div id="tr-rep"></div></section>`;
};
function bindImportTrends() {
  const b = $("#tr-imp"); if (!b) return;
  const isJa = currentLang === "ja";
  b.onclick = async () => {
    const f = $("#tr-file").files[0]; if (!f) return toast(isJa ? "まずCSVファイルを選択してください。" : "Choose a CSV file first.");
    const fd = new FormData(); fd.append("file", f); fd.append("geo", $("#tr-geo").value);
    $("#tr-rep").innerHTML = loading(isJa ? "検証中…" : "Validating…");
    try {
      const r = await api("/api/import/trends", { method: "POST", body: fd }); const p = r.report;
      $("#tr-rep").innerHTML = `<p class="note">${esc(p.file)}: <b>${p.valid}</b> of ${p.rows_read} rows valid · titles: ${esc(p.titles.join(", ") || "none")} · ${esc(p.date_min || "")} → ${esc(p.date_max || "")}</p>
        ${Object.entries(p.rejected).map(([k, v]) => `<p class="warn">✗ ${v}: ${esc(k)}</p>`).join("")}${(p.unmatched || []).length ? `<p class="warn">Unlinked titles: ${esc(p.unmatched.join(", "))} — add them to the query map.</p>` : ""}
        ${r.notes.map(n => `<p class="note">ℹ ${esc(n)}</p>`).join("")}`;
      if (p.valid) { toast(isJa ? `${p.valid}件の観測データをインポートしました。` : `Imported ${p.valid} observations (store: ${r.store_total}).`); sfx(window.sfxJapaneseChime); }
    } catch (e) { $("#tr-rep").innerHTML = `<p class="warn">${esc(e.message)}</p>`; }
  };
}

/* ============================================================== AUDIENCE */
const ASPECT_JA = {
  "Story & premise": "ストーリー・設定",
  "Character development": "登場人物の成長",
  "Protagonist": "主人公の魅力",
  "Intelligent / strategic conflict": "頭脳戦・心理戦",
  "World-building": "世界観・設定の深さ",
  "Pacing": "テンポ・展開速度",
  "Emotional impact": "感動・感情移入",
  "Visuals & animation": "作画・アニメーション",
  "Action & fights": "アクション・戦闘シーン",
  "Dialogue": "会話・台詞回し",
  "Repetitive conflicts": "マンネリ・展開重複",
  "Music & sound": "音楽・音響・声優",
  "Ending": "結末・最終回",
  "Humour": "ユーモア・ギャグ"
};
const STANCE_JA = {
  "mostly praised": "称賛多数",
  "mostly criticised": "批判多数",
  "divided": "賛否両論"
};
const aspName = a => currentLang === "ja" ? (ASPECT_JA[a] || a) : a;
const stName = s => currentLang === "ja" ? (STANCE_JA[s] || s) : s;

async function viewAudience(el) {
  const isJa = currentLang === "ja";
  const ws = S.ws;
  el.innerHTML = viewHead(t("aud_head"), t("aud_sub"),
    isJa ? "読み込まれたレビューテキストから抽出された感情と14のストーリー要素（実際の引用付き）。※海外レビューはインド国内の観客データとは異なります。" : "Sentiment and storytelling aspects extracted from the loaded review text, with verbatim excerpts. International reviews are not Indian audience evidence.") +
    `<main class="grid"><section class="card span-12"><div class="card-header"><div><h2>${isJa ? "作品を選択" : "Choose a title"}</h2><p class="hint">${isJa ? "バッジはトレンドやレビューの有無を示します。" : "Badges show which records carry trends or reviews."}</p></div></div>${searchBox("au", id => selectTitle(id))}</section>
     <div class="span-12" id="au-body"></div></main>`;
  const body = $("#au-body");
  if (!ws.selected_anime_id) { body.innerHTML = ""; Shinigami({ guide: isJa ? "作品を選択すると、その作品の観客評価データが表示されます。" : "Select a title to see the audience evidence that actually belongs to it." }); return; }
  body.innerHTML = loading(isJa ? "レビュー分析データを読み込み中…" : "Loading review analysis…");
  const d = await api(`/api/audience/${encodeURIComponent(ws.selected_anime_id)}`);
  const ov = d.overview, r = d.record;
  if (!ov.records) {
    body.innerHTML = `<section class="card"><h2>${esc(r.label)}</h2><div class="empty mt"><h3>${isJa ? "この作品にはレビューデータが連携されていません" : "No linked review evidence for this title"}</h3>
      ${isJa ? "カタログメタデータは観客の評価根拠ではありません。現在のデータストアにはこの作品に紐付くレビューが存在しないため、称賛・批判・感情傾向は表示されません（推計による補完は行われません）。" : "Catalog metadata is not audience evidence. The current review store has no rows linked to this title, so praise, criticism and sentiment are unavailable — nothing is estimated."}
      ${S.status && S.status.coverage.reviews ? "" : `<br><br>${isJa ? "レビューが読み込まれていません。<code>python scripts/ingest.py reviews-kaggle data/raw/reviews.csv</code> を実行してください。" : "No reviews are loaded at all. Run <code>python scripts/ingest.py reviews-kaggle data/raw/reviews.csv</code>."}`}</div>
      ${d.visibility ? `<p class="note">${kind("observed", "Visibility")} ${esc(formatVisibility(d.visibility))}</p>` : ""}</section>${importReviewsCard()}`;
    bindImportReviews();
    Shinigami({ cautions: [isJa ? `「${r.title}」にはカタログメタデータはありますがレビューが未連携のため、観客の反応を把握できません。` : `${r.title} has catalog metadata but no linked review evidence, so I can't describe audience response.`] }); return;
  }
  const aspects = d.aspects || [];
  const maxv = Math.max(1, ...aspects.map(a => Math.max(a.positive, a.negative)));
  const rc = d.reception || {};
  body.innerHTML = `<main class="grid">
    ${sentimentTesterCard()}
    <section class="card span-12"><div class="card-header"><div><h2>${esc(r.label)}</h2><p class="hint">${kind("observed", "Observed")} ${isJa ? "この作品の実データのみを表示しています。" : "Evidence that belongs to this title only."}</p></div>
      <button class="btn ghost btn-sm" onclick="openTitle('${esc(r.anime_id)}')">${isJa ? "カタログ詳細" : "Catalog details"}</button></div>
      <div class="statgrid"><div class="stat-box"><b>${fmt(ov.records)}</b><span>${isJa ? "レビュー件数" : "Review records"}</span></div>
        <div class="stat-box"><b>${esc((ov.sources || []).length)}</b><span>${esc((ov.sources || []).join(", "))}</span></div>
        <div class="stat-box"><b>${ov.score_mean === null ? "—" : fmt(ov.score_mean, 1)}</b><span>${isJa ? "平均レビュアースコア /10" : "Mean reviewer score /10"}${ov.score_std === null ? "" : " · sd " + fmt(ov.score_std, 1)}</span></div>
        <div class="stat-box"><b>${fmt(ov.india_tagged)}</b><span>${isJa ? "インド地域タグ付きレビュー" : "India-tagged reviews"}</span></div></div>
      <p class="note">${isJa ? "期間:" : "Dates:"} ${esc(ov.date_min || (isJa ? "未記録" : "undated"))}${ov.date_max ? " → " + esc(ov.date_max) : ""}${ov.undated ? ` (${fmt(ov.undated)}${isJa ? "件日付なし" : " undated"})` : ""} · ${isJa ? "言語:" : "Languages:"} ${esc((ov.languages || []).join(", ") || (isJa ? "未記録" : "not recorded"))} · ${isJa ? `地域判明: ${fmt(ov.with_geography)} / ${fmt(ov.records)}件` : `Reviewer geography known for ${fmt(ov.with_geography)} of ${fmt(ov.records)}.`}</p>
      ${ov.records < d.min_reviews ? `<p class="warn">⚠ ${isJa ? `レビュー件数が${d.min_reviews}件未満のため、作品レベルの分析基準値を下回っています。` : `Fewer than ${d.min_reviews} reviews — below the threshold for a title-level finding.`}</p>` : ""}</section>
    <section class="card span-5"><h2>${isJa ? "総合評価傾向" : "Overall reception"} ${kind("calc", "Calculated")}</h2>
      <div class="statgrid mt" style="grid-template-columns:repeat(3,1fr)"><div class="stat-box"><b style="color:var(--leaf-green)">${fmt(rc.positive || 0)}</b><span>${isJa ? "高評価" : "Positive"}</span></div>
      <div class="stat-box"><b>${fmt(rc.mixed || 0)}</b><span>${isJa ? "賛否両論" : "Mixed"}</span></div><div class="stat-box"><b style="color:var(--kurama-red)">${fmt(rc.negative || 0)}</b><span>${isJa ? "低評価" : "Negative"}</span></div></div>
      <p class="note">${isJa ? `レビュアー自身のスコア（7点以上が高評価、4点以下が低評価、それ以外が賛否）またはテキスト感情極性。手法: ${esc(d.method)}。` : `Reviewer's own score when present (≥7 positive, ≤4 negative, else mixed); otherwise text sentiment. ${esc(d.method)}.`}</p>
      <h3 class="mt" style="font:700 14px 'Manrope',sans-serif;color:var(--mute)">${isJa ? "レビュアースコア分布" : "Reviewer score distribution"}</h3>${histogram(d.score_hist)}</section>
    <section class="card span-7"><h2>${isJa ? "ストーリー要素別分析" : "Storytelling aspects"} ${kind("interp", "Interpretation")}</h2>
      <p class="hint">${isJa ? "要素ごとの批判件数 ← → 称賛件数" : "Reviews criticising ← → reviews praising, per aspect."}</p>
      <div class="dbars mt">${aspects.map(a => `<div class="dbar"><span class="lab" title="${esc(a.aspect)}">${esc(aspName(a.aspect))}</span>
        <span class="neg"><span style="width:${a.negative / maxv * 100}%" title="${a.negative} ${isJa ? "件の批判" : "criticising"}"></span></span>
        <span class="pos"><span style="width:${a.positive / maxv * 100}%" title="${a.positive} ${isJa ? "件の称賛" : "praising"}"></span></span><span class="st">${esc(stName(a.stance))}</span></div>`).join("") || `<p class='note'>${isJa ? "要素キーワードが見つかりません。" : "No aspect keywords found."}</p>`}</div>
      <p class="note">${isJa ? `要素 = 文中のキーワード一致; 極性 = 該当文の感情スコア（≥0.25高評価、≤−0.25低評価）。1レビューにつき1回カウント。スタンス確定には≥${d.min_mentions}件の極性レビューが必要です。` : `Aspect = keyword match in a sentence; polarity = that sentence's sentiment (≥0.25 positive, ≤−0.25 negative). Counted once per review. A stance needs ≥${d.min_mentions} polar reviews.`}</p></section>
    <section class="card span-12"><div class="card-header"><div><h2>${isJa ? "要素別の実証テキスト・引用" : "Evidence by aspect"}</h2><p class="hint">${isJa ? "企画ラボ・事業計画・提案書に引き継ぐテーマを選択して保存してください。" : "Pick themes to carry into the Creative Lab, Planner and Brief, then save."}</p></div>
      <button class="btn btn-sm" id="th-save">${isJa ? "選択したテーマを保存" : "Save selected themes"}</button></div>
      <div class="chips" id="th">${aspects.map(a => `<button data-a="${esc(a.aspect)}" class="${(ws.selected_themes || []).includes(a.aspect) ? "active" : ""}">${esc(aspName(a.aspect))} · ${esc(stName(a.stance))}</button>`).join("")}</div>
      <label class="field mt" style="max-width:360px">${isJa ? "引用文を表示する要素:" : "Show excerpts for"}<select id="ex-a">${aspects.map(a => `<option value="${esc(a.aspect)}">${esc(aspName(a.aspect))}</option>`).join("")}</select></label>
      <div class="fields c2 mt" id="ex"></div><p class="note">${isJa ? "引用文は読み込まれたレビューテキストからの抜粋です。" : "Excerpts are verbatim sentences from the loaded reviews (shortened with … where long)."}</p></section>
  </main>`;
  bindSentimentTester();
  const showEx = a => {
    const x = d.excerpts[a]; if (!x) return;
    $("#ex").innerHTML = `<div><h3 style="font:700 14px 'Manrope',sans-serif;color:var(--leaf-green)">${isJa ? `称賛 · ${x.n_pos}件のレビュー` : `Praise · ${x.n_pos} review(s)`}</h3>${x.positive.map(q => quote(q)).join("") || `<p class='note'>${isJa ? "称賛の記述はありません。" : "No praising sentences."}</p>`}</div>
      <div><h3 style="font:700 14px 'Manrope',sans-serif;color:var(--kurama-red)">${isJa ? `批判・指摘 · ${x.n_neg}件のレビュー` : `Criticism · ${x.n_neg} review(s)`}</h3>${x.negative.map(q => quote(q, true)).join("") || `<p class='note'>${isJa ? "批判の記述はありません。" : "No criticising sentences."}</p>`}</div>`;
  };
  $("#ex-a").onchange = e => showEx(e.target.value);
  if (aspects.length) showEx(aspects[0].aspect);
  $("#th").querySelectorAll("button").forEach(b => b.onclick = () => { b.classList.toggle("active"); $("#ex-a").value = b.dataset.a; showEx(b.dataset.a); });
  $("#th-save").onclick = async () => {
    const themes = [...$("#th").querySelectorAll("button.active")].map(b => b.dataset.a);
    try {
      await post(`/api/audience/${encodeURIComponent(r.anime_id)}/themes`, { themes }); await refreshWs(); sfx(window.sfxJapaneseChime);
      toast(themes.length ? (isJa ? `${themes.length}個のテーマをワークスペースに保存しました。` : `Saved ${themes.length} theme(s) as the workspace finding.`) : (isJa ? "テーマをクリアしました。" : "Themes cleared."));
    } catch (e) { toast("⚠ " + e.message); }
  };
  const praised = aspects.filter(a => a.stance === "mostly praised").map(a => a.aspect), crit = aspects.filter(a => a.stance === "mostly criticised").map(a => a.aspect);
  const cautions = [];
  if (ov.records < d.min_reviews) cautions.push(isJa ? `レビュー件数が${ov.records}件のみで、作品分析に必要な${d.min_reviews}件を下回っています。` : `Only ${ov.records} review(s) — below the ${d.min_reviews} needed for a title-level finding.`);
  if (!ov.india_tagged) cautions.push(isJa ? "これらのレビューはインド在住の視聴者によるものと検証されていません。" : "These reviews are not verified as coming from Indian viewers.");
  Shinigami({ cautions, discoveries: praised.length && ov.records >= d.min_reviews ? [isJa ? `${ov.records}件のレビューにおいて、${praised.slice(0, 2).map(aspName).join("、")}が高く評価されています${crit.length ? `（一方、${crit.slice(0, 2).map(aspName).join("、")}には批判的な声もあります）` : ""}。` : `In ${ov.records} reviews, ${praised.slice(0, 2).join(", ")} ${praised.length > 1 ? "are" : "is"} mostly praised${crit.length ? ` while ${crit.slice(0, 2).join(", ")} ${crit.length > 1 ? "are" : "is"} mostly criticised` : ""}.`] : [], guide: isJa ? "引き継ぎたいテーマを選択してください。" : "Pick the themes you want to carry forward." });
}

function sentimentTesterCard() {
  const isJa = currentLang === "ja";
  return `
    <section class="card span-12" id="ml-sentiment-card">
      <h2>${isJa ? "🤖 学習済みML感情分析" : "🤖 Trained ML Sentiment Analyzer"}</h2>
      <p class="hint">
        ${isJa
      ? "レビュー文を入力し、学習済みモデルの予測を確認します。"
      : "Enter a review and inspect the prediction from your trained model."}
      </p>
      <label class="field mt">
        ${isJa ? "レビュー文" : "Review text"}
        <textarea id="ml-review-text" rows="4"
          placeholder="${isJa
      ? "ここにレビューを入力…"
      : "e.g. The story was amazing, but the ending felt rushed…"}"></textarea>
      </label>
      <div class="row mt">
        <button class="btn" id="ml-predict-btn">
          ${isJa ? "感情を予測" : "Predict sentiment"}
        </button>
      </div>
      <div id="ml-prediction-result" class="mt"></div>
      <p class="note">
        ${isJa
      ? "予測はモデルの出力であり、インド国内の観客全体を代表するものではありません。"
      : "Predictions are model outputs, not proof of sentiment among Indian audiences."}
      </p>
    </section>`;
}

function bindSentimentTester() {
  const btn = $("#ml-predict-btn");
  if (!btn) return;

  btn.onclick = async () => {
    const input = $("#ml-review-text");
    const result = $("#ml-prediction-result");
    const isJa = currentLang === "ja";
    const text = input?.value.trim();

    if (!text) {
      result.innerHTML = `<p class="warn">${isJa ? "レビュー文を入力してください。" : "Enter a review first."
        }</p>`;
      return;
    }

    btn.disabled = true;
    result.innerHTML = loading(
      isJa ? "モデルで予測中…" : "Running model prediction…"
    );

    try {
      const response = await post("/api/ml/sentiment", { text });
      const prediction = response.data || response.result || response;
      const label = prediction.label ?? prediction.sentiment ?? "Unavailable";
      const probabilities =
        prediction.probabilities || prediction.probs || {};

      const probabilityHtml = Object.entries(probabilities)
        .map(([name, value]) => {
          const number = Number(value);
          const percentage = number <= 1
            ? number * 100
            : number;

          return `<div class="note">
            ${esc(name)}: <b>${percentage.toFixed(1)}%</b>
          </div>`;
        })
        .join("");

      result.innerHTML = `
        <div class="stat-box">
          <span>${isJa ? "モデルの予測" : "Model prediction"}</span>
          <b>${esc(label)}</b>
        </div>
        ${probabilityHtml}
        <p class="note">
          ${isJa ? "モデルID" : "Model ID"}:
          ${esc(prediction.model_id || prediction.model || "—")}
        </p>`;
    } catch (error) {
      result.innerHTML = `<p class="warn">
        ${isJa ? "予測に失敗しました: " : "Prediction failed: "}
        ${esc(error.message)}
      </p>`;
    } finally {
      btn.disabled = false;
    }
  };
}

const importReviewsCard = () => {
  const isJa = currentLang === "ja";
  return `<section class="card no-print mt"><h2>${isJa ? "レビューデータのインポート" : "Import review evidence"}</h2>
  <p class="hint">${isJa ? "レビューテキストと作品名/IDを含む小規模CSV。650MBのKaggleデータには <code>python scripts/ingest.py reviews-kaggle data/raw/reviews.csv</code> を使用してください。" : "Small CSVs (e.g. AniList export) with review text and a title or id column. For the 650 MB Kaggle <code>reviews.csv</code> use the chunked command: <code>python scripts/ingest.py reviews-kaggle data/raw/reviews.csv</code>."}</p>
  <div class="fields c3 mt"><label class="field">${isJa ? "CSVファイル" : "CSV file"}<input type="file" id="rv-file" accept=".csv"></label><label class="field">${isJa ? "情報源名（CSV内にない場合）" : "Source name (if no source column)"}<input type="text" id="rv-src" placeholder="e.g. AniList"></label>
  <div class="field">&nbsp;<button class="btn" id="rv-imp">${isJa ? "検証してインポート" : "Validate &amp; import"}</button></div></div><div id="rv-rep"></div></section>`;
};
function bindImportReviews() {
  const b = $("#rv-imp"); if (!b) return;
  const isJa = currentLang === "ja";
  b.onclick = async () => {
    const f = $("#rv-file").files[0]; if (!f) return toast(isJa ? "まずCSVファイルを選択してください。" : "Choose a CSV file first.");
    const fd = new FormData(); fd.append("file", f); fd.append("source", $("#rv-src").value); fd.append("cap", "30");
    $("#rv-rep").innerHTML = loading(isJa ? "検証・分析中…" : "Validating and analysing…");
    try {
      const r = await api("/api/import/reviews", { method: "POST", body: fd }); const p = r.report;
      $("#rv-rep").innerHTML = `<p class="note"><b>${p.rows_valid}</b> of ${p.rows_read} rows valid · store: ${r.store_total}</p>${Object.entries(p.rejected).map(([k, v]) => `<p class="warn">✗ ${v}: ${esc(k)}</p>`).join("")}${p.notes.map(n => `<p class="note">ℹ ${esc(n)}</p>`).join("")}`;
      if (p.rows_valid) { toast(isJa ? `${p.rows_valid}件のレビューをインポートしました。` : `Imported ${p.rows_valid} reviews.`); route(); }
    } catch (e) { $("#rv-rep").innerHTML = `<p class="warn">${esc(e.message)}</p>`; }
  };
}

/* ================================================================== GEMS */
async function viewGems(el, params = {}) {
  const isJa = currentLang === "ja";
  if (!S.aspects.length) S.aspects = await api("/api/aspects");
  const minr = params.min_reviews || 5, asp = params.aspect || "", low = params.low_visibility === "true";
  el.innerHTML = viewHead(t("gems_head"), t("gems_sub"),
    isJa ? "一部のストーリー要素が高く評価されつつ、他要素で賛否が分かれている作品群。調査対象候補を特定します。" : "Titles where some storytelling aspects are mostly praised and others criticised or divided. Candidates for investigation — never ‘underrated’ verdicts.") +
    `<main class="grid"><section class="card span-12"><div class="fields c3">
      <label class="field">${isJa ? "1作品あたりの最小レビュー数" : "Minimum reviews per title"}<input type="number" id="g-min" min="3" max="100" value="${esc(minr)}"></label>
      <label class="field">${isJa ? "評価要素（称賛多数を条件とする）" : "Storytelling element (must be mostly praised)"}<select id="g-asp"><option value="">${isJa ? "(すべて)" : "(any)"}</option>${S.aspects.map(a => `<option value="${esc(a.aspect)}" ${a.aspect === asp ? "selected" : ""}>${esc(aspName(a.aspect))}</option>`).join("")}</select></label>
      <label class="field">${isJa ? "認知度フィルター" : "Visibility filter"}<select id="g-low"><option value="false">${isJa ? "全タイトル" : "All titles"}</option><option value="true" ${low ? "selected" : ""}>${isJa ? "認知度低位作品のみ（MAL 2020 50パーセンタイル以下）" : "Only lower-visibility (≤ 50th percentile, MAL 2020)"}</option></select></label></div></section>
      <div class="span-12" id="g-out">${loading(isJa ? "作品をスクリーニング中…" : "Screening titles…")}</div></main>`;
  const go = () => viewGems(el, { min_reviews: $("#g-min").value, aspect: $("#g-asp").value, low_visibility: $("#g-low").value });
  ["g-min", "g-asp", "g-low"].forEach(id => $("#" + id).onchange = go);
  const r = await api(`/api/gems?min_reviews=${minr}&aspect=${encodeURIComponent(asp)}&low_visibility=${low}`);
  const out = $("#g-out");
  if (r.empty) {
    out.innerHTML = `<section class="card"><div class="empty"><h3>${isJa ? "レビューデータの連携待ち" : "Analyzer waiting for review evidence"}</h3>${isJa ? "レビューが読み込まれていません。<code>python scripts/ingest.py reviews-kaggle data/raw/reviews.csv</code> を実行してください。" : "No reviews are loaded. Run <code>python scripts/ingest.py reviews-kaggle data/raw/reviews.csv</code>."}
      ${isJa ? `本分析ツールは作品あたり≥${esc(minr)}件のレビューおよび要素あたり≥3件の極性レビューが必要です。` : `The analyzer needs ≥${esc(minr)} reviews per title and ≥3 polar reviews per aspect before it reports anything.`}</div></section>`;
    Shinigami({ cautions: [isJa ? "レビューデータが読み込まれていないため、分析対象がありません。" : "No review evidence is loaded, so the analyzer has nothing to examine."] }); return;
  }
  if (!r.candidates.length) {
    out.innerHTML = `<section class="card"><div class="empty"><h3>${isJa ? "該当する候補作品がありません" : "No candidates"}</h3>${isJa ? `レビュー≥${esc(minr)}件の${fmt(r.eligible)}作品中、指定条件（${asp ? `「${aspName(asp)}」が高評価` : ""}${low ? "・認知度低位" : ""}）に該当する作品はありません。` : `None of the ${fmt(r.eligible)} title(s) with ≥${esc(minr)} reviews meets the mixed-response pattern${asp ? ` with ‘${esc(asp)}’ praised` : ""}${low ? " among lower-visibility titles" : ""}.`}</div></section>`;
    Shinigami({ cautions: [isJa ? `現在のフィルター条件に該当する作品がありません（対象候補: ${fmt(r.eligible)}作品）。` : `No title meets the pattern under these filters (${fmt(r.eligible)} eligible).`] }); return;
  }
  out.innerHTML = `<p class="note">${isJa ? `対象${fmt(r.eligible)}作品中、${fmt(r.total)}件が候補に該当${r.total > 20 ? "（コントラスト指標上位20件を表示）" : ""}。` : `${fmt(r.total)} candidate(s) of ${fmt(r.eligible)} eligible titles${r.total > 20 ? "; showing the 20 with the highest contrast index" : ""}.`}</p>` +
    r.candidates.map((c, i) => `<section class="card mt"><div class="card-header"><div><h2>${esc(c.title)}</h2>
      <p class="hint">${kind("calc", "Why selected")} ${esc(formatGemWhy(c))}</p></div><span class="pill-badge orange" title="${isJa ? "最高評価要素の高評価率から最低評価要素の高評価率を引いた値（実験的指標）。" : "Best praised aspect's positive share minus the weakest aspect's. Experimental, not validated, not commercial potential."}">${isJa ? "コントラスト指数" : "Contrast"} ${c.contrast_index ?? "—"} · ${isJa ? "実験的指標" : "experimental"}</span></div>
      <div class="statgrid"><div class="stat-box"><b>${fmt(c.n_reviews)}</b><span>${isJa ? "対象レビュー件数（データ量）" : "Supporting reviews (evidence volume, not popularity)"}</span></div>
        <div class="stat-box"><b>${fmt(c.mixed_share * 100)}%</b><span>${isJa ? "総合評価が賛否または低評価の割合" : "Mixed or negative overall"}</span></div>
        <div class="stat-box"><b>${c.score_mean === null ? "—" : fmt(c.score_mean, 1)}</b><span>${isJa ? "平均レビュアースコア" : "Mean reviewer score"}${c.score_std === null ? "" : " · sd " + fmt(c.score_std, 1)}</span></div>
        <div class="stat-box"><b>${c.catalog_score ? fmt(c.catalog_score, 2) : "—"}</b><span>${isJa ? "世界カタログスコア" : "Catalog score (global)"}</span></div></div>
      <p class="note">${kind("observed", "Visibility")} ${c.india_trend ? (isJa ? `インド検索指数 ${fmt(c.india_trend.latest)} (最新, ${esc(c.india_trend.date)})。` : `India search index ${fmt(c.india_trend.latest)} (latest, ${esc(c.india_trend.date)}). `) : (isJa ? "インド検索トレンドデータなし。" : "No India trend observations. ")}${esc(formatVisibility(c.visibility))}</p>
      <div class="row mt-s"><span class="note" style="margin:0">${isJa ? "評価されている点:" : "Praised:"}</span><div class="chips">${c.praised.map(a => `<button class="active">${esc(aspName(a))}</button>`).join("")}</div>
        <span class="note" style="margin:0">${isJa ? "批判・賛否が分かれる点:" : "Criticised / divided:"}</span><div class="chips">${c.criticised.concat(c.divided).map(a => `<button>${esc(aspName(a))}</button>`).join("") || "—"}</div></div>
      <div class="fields c2 mt"><div>${c.praise.map(q => quote(q)).join("")}</div><div>${c.criticism.map(q => quote(q, true)).join("")}</div></div>
      <p class="note">${kind("hyp", "Hypothesis")} ${esc(formatGemSteps(c.next_steps))}</p>
      <p class="note">${isJa ? "制約事項:" : "Limitations:"} ${esc(formatGemLimitations(c.limitations))}</p>
      <div class="row mt-s"><button class="btn btn-sm" data-use="${i}">${isJa ? "この分析結果をワークスペースに適用" : "Use this finding in the workspace"}</button><button class="btn ghost btn-sm" onclick="openTitle('${esc(c.anime_id)}')">${isJa ? "詳細" : "Details"}</button></div></section>`).join("");
  out.querySelectorAll("[data-use]").forEach(b => b.onclick = async () => {
    const c = r.candidates[+b.dataset.use];
    try {
      await post(`/api/gems/${encodeURIComponent(c.anime_id)}/use`, { praised: c.praised, criticised: c.criticised, why: c.why, n_reviews: c.n_reviews });
      await refreshWs(); sfx(window.sfxJapaneseChime); toast(isJa ? "分析結果を保存しました — 企画ラボ・事業計画・提案書で利用可能です。" : "Finding saved — available in the Creative Lab, Planner and Brief.");
    } catch (e) { toast("⚠ " + e.message); }
  });
  Shinigami({ discoveries: [isJa ? `レビュー数が十分な${r.eligible}作品中、${r.total}作品で批判・賛否と並行して高く評価された要素が確認されました。各作品の制約事項を確認してください。` : `${r.total} of ${r.eligible} titles with enough reviews show praised aspects alongside criticism or mixed reception. Read each one's limitations.`], cautions: [isJa ? "レビュアーの所在地は未特定です（インド国内の視聴者データではありません）。" : "Reviewer location is unknown: these are not Indian audience findings."] });
}

/* =================================================================== LAB */
async function viewLab(el) {
  const isJa = currentLang === "ja";
  if (!S.aspects.length) S.aspects = await api("/api/aspects");
  const ws = await refreshWs();
  const f = ws.selected_finding, c = ws.concept;
  const sel = new Set(ws.selected_themes || []);
  const objList = isJa
    ? [["Original series pitch", "オリジナルアニメ企画"], ["Short-form web series", "ショートWebシリーズ"], ["Spin-off / side story", "スピンオフ / 外伝企画"], ["Campaign or promotional story", "プロモーション連動ストーリー"], ["Community event narrative", "ファンイベント用ストーリー"]]
    : [["Original series pitch", "Original series pitch"], ["Short-form web series", "Short-form web series"], ["Spin-off / side story", "Spin-off / side story"], ["Campaign or promotional story", "Campaign or promotional story"], ["Community event narrative", "Community event narrative"]];

  el.innerHTML = viewHead(t("lab_head"), t("lab_sub"),
    isJa ? "観客の評価テーマに直結した透明なルールベースの企画コンセプト設計。" : "A transparent, rules-based concept builder. Every draft is traceable to its themes and is never presented as validated or legally cleared.") +
    `<main class="grid">
    <section class="card span-12"><h2>${isJa ? "1 · 入力条件" : "1 · Inputs"}</h2>
      <p class="hint mt-s">${isJa ? "ストーリーテーマ" : "Storytelling themes"} ${f ? (isJa ? "（分析結果から自動反映）" : "(prefilled from your finding)") : ""}</p><div class="chips mt-s" id="lab-th">${S.aspects.map(a => `<button data-a="${esc(a.aspect)}" class="${sel.has(a.aspect) ? "active" : ""}" title="${esc(a.description)}">${esc(aspName(a.aspect))}</button>`).join("")}</div>
      <div class="fields c2 mt"><label class="field">${isJa ? "企画目標" : "Creative objective"}<select id="lab-obj">${objList.map(([val, label]) => `<option value="${esc(val)}">${esc(label)}</option>`).join("")}</select></label>
        <label class="field">${isJa ? "想定ターゲット層の仮説" : "Target audience hypothesis"}<input id="lab-aud" placeholder="${isJa ? "例: 頭脳戦アニメを好むインドの大学生" : "e.g. Indian college students who follow strategy anime"}"></label></div>
      <div class="fields c2 mt"><label class="field">${isJa ? "この企画が応える観客インサイト" : "Audience insight this concept responds to"}<textarea id="lab-ins" placeholder="${isJa ? "例: 心理戦や駆け引きが高評価される一方、テンポの遅さが指摘されている" : "e.g. Reviewers praise strategic duels but criticise slow pacing"}">${esc(f ? f.summary : "")}</textarea></label>
        <label class="field">${isJa ? "舞台設定・方向性（任意）" : "Optional setting / direction"}<textarea id="lab-dir" placeholder="${isJa ? "空欄の場合は自動設定されます" : "Leave blank for a generated setting"}"></textarea></label></div>
      <div class="row mt"><button class="btn" id="lab-build">${isJa ? "企画コンセプトを生成" : "Build concept"}</button><button class="btn ghost" id="lab-var" ${c ? "" : "disabled"}>${isJa ? "別バリエーションを試す" : "Try another variation"}</button></div></section>
    <section class="card span-4"><h2 style="font-size:17px">${kind("observed", "Observed")}</h2><p class="hint mt-s">${esc(f ? f.summary : (isJa ? "観客分析結果が未選択です。" : "No audience observation selected."))}</p></section>
    <section class="card span-4"><h2 style="font-size:17px">${kind("interp", "Interpretation")}</h2><p class="hint mt-s">${f && (f.praised?.length || f.criticised?.length) ? esc(isJa ? `強調要素: ${(f.praised || []).map(aspName).join("、") || "—"}。${f.criticised?.length ? "改善要素: " + f.criticised.map(aspName).join("、") + "。" : ""}` : `Emphasise ${(f.praised || []).join(", ") || "—"}. ${f.criticised?.length ? "Design around " + f.criticised.join(", ") + "." : ""}`) : (isJa ? "観客分析結果がないため解釈はありません。" : "No interpretation without an audience observation.")}</p></section>
    <section class="card span-4"><h2 style="font-size:17px">${kind("hyp", "Hypothesis")}</h2><p class="hint mt-s" id="lab-hyp">${esc(c ? c.core_premise : (isJa ? "コンセプトはまだ生成されていません。" : "No concept built yet."))}</p></section>
    <section class="card span-12" id="lab-draft"></section>
  </main>`;
  $("#lab-th").querySelectorAll("button").forEach(b => b.onclick = () => b.classList.toggle("active"));
  const inputs = () => ({ themes: [...$("#lab-th").querySelectorAll("button.active")].map(b => b.dataset.a), insight: $("#lab-ins").value, audience: $("#lab-aud").value, objective: $("#lab-obj").value, direction: $("#lab-dir").value });
  const build = async variation => {
    const p = inputs(); if (!p.themes.length) return toast(isJa ? "少なくとも1つのテーマを選択してください。" : "Select at least one theme.");
    try { const cc = await post("/api/concept", { ...p, variation }); sfx(window.sfxCrossSealSnap); renderDraft(cc); $("#lab-hyp").textContent = cc.core_premise; $("#lab-var").disabled = false; } catch (e) { toast("⚠ " + e.message); }
  };
  $("#lab-build").onclick = () => build(0);
  $("#lab-var").onclick = async () => { const w = await api("/api/workspace"); build((w.concept_variation || 0) + 1); };
  renderDraft(c);
  Shinigami({ cautions: f ? [] : [isJa ? "観客分析結果が未選択のため、ここでの企画案は実データ主導ではなく探索的なドラフトとなります。" : "No audience finding is selected, so any concept here is exploratory, not evidence-led."], discoveries: f ? [isJa ? `根拠データ: ${f.summary}` : `Grounded in: ${f.summary}`] : [], guide: isJa ? "テーマと企画目標を選択し、編集可能なドラフトを生成してください。" : "Choose themes and an objective, then build a draft you can edit." });
}

function renderDraft(c) {
  const isJa = currentLang === "ja";
  const box = $("#lab-draft");
  if (!c) { box.innerHTML = `<div class="empty"><h3>${isJa ? "企画ドラフトがありません" : "No concept yet"}</h3>${isJa ? "テーマを選択して「企画コンセプトを生成」を押してください。" : "Choose themes and press <b>Build concept</b>."}</div>`; return; }
  box.innerHTML = `<div class="card-header"><div><h2>${isJa ? "3 · 企画ドラフト" : "3 · Concept draft"}</h2><p class="hint">${esc(c.method)} · ${isJa ? "バリエーション" : "Variation"} ${esc(c.variation)} · ${esc(c.validation_status)}</p></div></div>
    <div class="fields c2"><label class="field">${isJa ? "仮タイトル" : "Working title"}<input id="cd-wt" value="${esc(c.working_title)}"></label><label class="field">${isJa ? "ログライン / 基本設定" : "Core premise"}<textarea id="cd-cp">${esc(c.core_premise)}</textarea></label></div>
    <div class="fields c2 mt"><label class="field">${isJa ? "主人公像" : "Central character"}<textarea id="cd-cc">${esc(c.central_character)}</textarea></label><label class="field">${isJa ? "主要な葛藤・対立" : "Main conflict"}<textarea id="cd-mc">${esc(c.main_conflict)}</textarea></label></div>
    <label class="field mt">${isJa ? "テーマ / 感情のフック" : "Emotional / thematic hook"}<input id="cd-hk" value="${esc(c.hook)}"></label>
    <div class="fields c2 mt"><label class="field">${isJa ? "強調すべき強み（1行に1つ）" : "Strengths to emphasise (one per line)"}<textarea id="cd-st">${esc((c.strengths_to_emphasise || []).join("\n"))}</textarea></label>
      <label class="field">${isJa ? "回避すべきリスク・弱点（1行に1つ）" : "Risks / weaknesses to avoid (one per line)"}<textarea id="cd-rk">${esc((c.risks_to_avoid || []).join("\n"))}</textarea></label></div>
    <label class="field mt">${isJa ? "想定読者・視聴者仮説" : "Audience hypothesis"}<input id="cd-ah" value="${esc(c.audience_hypothesis)}"></label>
    <p class="note"><b>${isJa ? "着想元テーマ:" : "Inspired by themes:"}</b> ${esc((c.inspired_by_themes || []).map(aspName).join(", "))} · <b>${isJa ? "検討理由:" : "Why explored:"}</b> ${esc(c.why_explored)}</p>
    <p class="note">${isJa ? "一般的なジャンル要素から構成されたドラフトです。既存作品のキャラクターやプロットを無断利用するものではありませんが、法的クリアランスや市場検証は未実施です。" : "Built from generic genre ingredients; it does not reuse characters, plots or dialogue from existing works, but it is not legally reviewed, audience-tested or commercially validated."}</p>
    <div class="row mt"><button class="btn" id="cd-save">${isJa ? "企画を保存" : "Save concept"}</button><button class="btn ghost" id="cd-plan">${isJa ? "事業計画へ送る →" : "Send to Business Planner →"}</button></div>`;
  const edited = () => ({
    ...c, working_title: $("#cd-wt").value, core_premise: $("#cd-cp").value, central_character: $("#cd-cc").value, main_conflict: $("#cd-mc").value,
    hook: $("#cd-hk").value, strengths_to_emphasise: $("#cd-st").value.split("\n").filter(Boolean), risks_to_avoid: $("#cd-rk").value.split("\n").filter(Boolean), audience_hypothesis: $("#cd-ah").value
  });
  $("#cd-save").onclick = async () => { try { await post("/api/concept/save", edited()); sfx(window.sfxJapaneseChime); toast(isJa ? "企画をワークスペースに保存しました。" : "Concept saved to the workspace."); } catch (e) { toast("⚠ " + e.message); } };
  $("#cd-plan").onclick = async () => { try { await post("/api/workspace", { concept: edited() }); location.hash = "#/planner"; } catch (e) { toast("⚠ " + e.message); } };
}

/* =============================================================== PLANNER */
const AREAS_DEF = {
  localization: {
    en: {
      title: "Localization",
      options: ["Hindi subtitle test", "Regional-language subtitle test (e.g. Tamil, Telugu, Bengali)", "Hindi dub pilot episode", "Localized trailer and key art", "Cultural-context explainer content", "Indian creator co-hosted watch-through", "Regional campaign in one metro first"],
      note: "Hypotheses to test. AniScope has no verified data on Indian language preferences."
    },
    ja: {
      title: "ローカライズ・言語ローカル展開",
      options: ["ヒンディー語字幕テスト", "地域言語字幕テスト（タミル語・テルグ語・ベンガル語等）", "ヒンディー語吹替パイロット話", "ローカライズ版予告編・キービジュアル", "文化的背景・設定解説コンテンツ", "インド現地のクリエイター共催ウォッチパーティ", "主要大都市圏での先行テストキャンペーン"],
      note: "検証すべき仮説。AniScopeにはインド言語選好に関する検証済み確定データはありません。"
    }
  },
  monetization: {
    en: {
      title: "Monetization & Merchandise",
      options: ["Licensed apparel", "Limited-edition collectible", "Art book / print", "Digital wallpaper or sticker pack (micropayment)", "Ad-supported free episodes", "Paid fan event / screening", "Premium community membership", "Co-branded product with a local brand"],
      note: "Illustrative offers. No licence, supplier or partnership is implied to exist."
    },
    ja: {
      title: "マネタイズ・商品化（グッズ・物販）",
      options: ["公式ライセンスアパレル", "数量限定コレクターズアイテム・フィギュア", "公式アートブック・限定複製原画", "デジタル壁紙・スタンプパック（少額課金）", "広告つき無料配信エピソード", "有料ファン上映イベント・オフ会", "プレミアムコミュニティ会員権", "インド現地ブランドとのコラボ商品"],
      note: "例示的なオファー案です。ライセンス、サプライチェーン、提携関係の成立を保証するものではありません。"
    }
  },
  distribution: {
    en: {
      title: "Distribution",
      options: ["Short-form clips on social video platforms", "Partnership with Indian anime creators / communities", "College club and campus events", "Comic-con / pop-culture event presence", "E-commerce marketplace storefront", "Streaming platform availability check (licensing question)", "Small-scale landing-page demand test"],
      note: "Promotional distribution is separate from content licensing; neither is verified."
    },
    ja: {
      title: "流通・配信・プロモーション",
      options: ["ショート動画プラットフォーム向け切り抜きクリップ", "インド現地アニメ系インフルエンサー・コミュニティとの提携", "大学アニメ同好会・キャンパスイベント展開", "コミコン / ポップカルチャー展示会への出展", "ECマーケットプレイス公式ストアフロント", "配信プラットフォームの配信権・空き枠確認", "小規模ランディングページによる事前需要テスト"],
      note: "プロモーション配信とコンテンツ放映権・配信権ライセンスは別個の課題です。"
    }
  },
  retention: {
    en: {
      title: "Community Retention",
      options: ["Weekly episode discussion threads", "Fan art / cosplay challenges", "Recurring limited drops", "Loyalty points for repeat purchases", "Members-only events", "Seasonal anniversary campaign"],
      note: "Proposed metrics only (repeat participation, returning users). No outcomes are observed."
    },
    ja: {
      title: "コミュニティ継続・リテンション",
      options: ["週刊エピソード感想・考察スレッド", "ファンアート / コスプレコンテスト", "定期的な期間限定グッズドロップ", "リピート購入向けロイヤルティポイント", "会員限定オンラインイベント", "シーズン記念・周年キャンペーン"],
      note: "想定指標（リピート率、継続率）に基づく提案です。実績値ではありません。"
    }
  }
};
const DEMO = { target_audience: 200000, reach_rate_pct: 10, conversion_rate_pct: 2, price: 799, variable_cost: 350, fixed_costs: 150000, currency: "INR", duration_weeks: 8, is_demo: true };

const START_MAP = {
  "Selected title": { en: "Selected title", ja: "選択中の作品" },
  "Audience finding": { en: "Audience finding", ja: "観客分析結果" },
  "Creative concept": { en: "Creative concept", ja: "企画コンセプト" },
  "Manual business idea": { en: "Manual business idea", ja: "手動入力アイデア" },
  "選択中の作品": { en: "Selected title", ja: "選択中の作品" },
  "観客分析結果": { en: "Audience finding", ja: "観客分析結果" },
  "企画コンセプト": { en: "Creative concept", ja: "企画コンセプト" },
  "手動入力アイデア": { en: "Manual business idea", ja: "手動入力アイデア" }
};

const BRIEF_SECS_JA = {
  "Executive summary": "エグゼクティブサマリー",
  "Evidence base: observed signals": "データ根拠: 観測された実データ",
  "Audience intelligence: praise & friction": "観客インテリジェンス: 称賛と批判の構造",
  "Creative opportunity hypothesis": "クリエイティブ機会の仮説",
  "Commercial validation experiments": "商業検証実験の設計",
  "Illustrative economics & assumptions": "収支試算モデルと前提条件",
  "Risks and limitations": "リスクと制約事項",
  "Validation roadmap & next steps": "検証ロードマップと今後のステップ"
};

async function viewPlanner(el) {
  const isJa = currentLang === "ja";
  const ws = await refreshWs();
  const plan = ws.plan || {}, a = ws.assumptions || {}, vp = ws.validation_plan || {}, f = ws.selected_finding, c = ws.concept;
  const startKey = START_MAP[plan.start]?.en || "Selected title";
  const startOptions = [
    { key: "Selected title", label: isJa ? "選択中の作品" : "Selected title" },
    { key: "Audience finding", label: isJa ? "観客分析結果" : "Audience finding" },
    { key: "Creative concept", label: isJa ? "企画コンセプト" : "Creative concept" },
    { key: "Manual business idea", label: isJa ? "手動入力アイデア" : "Manual business idea" }
  ];

  const userAreas = {};
  Object.entries(AREAS_DEF).forEach(([k, def]) => {
    const currentDef = isJa ? def.ja : def.en;
    const otherDef = isJa ? def.en : def.ja;
    userAreas[k] = {
      title: currentDef.title,
      note: currentDef.note,
      options: currentDef.options.map((opt, idx) => {
        const active = (plan[k] || []).includes(opt) || (plan[k] || []).includes(otherDef.options[idx]);
        return { opt, active };
      })
    };
  });

  const fieldDefs = isJa ? [
    ["currency", "通貨 (Currency)", "select"],
    ["target_audience", "ターゲット想定規模 (人数)"],
    ["reach_rate_pct", "リーチ率 (%)"],
    ["conversion_rate_pct", "転換率・購買率 (%)"],
    ["price", "商品・サービス単価"],
    ["variable_cost", "1件あたり変動費"],
    ["fixed_costs", "固定キャンペーン・開発費"],
    ["duration_weeks", "施策期間 (週)"]
  ] : [
    ["currency", "Currency", "select"],
    ["target_audience", "Target audience (people)"],
    ["reach_rate_pct", "Reach rate (%)"],
    ["conversion_rate_pct", "Conversion rate (%)"],
    ["price", "Price per unit"],
    ["variable_cost", "Variable cost per unit"],
    ["fixed_costs", "Fixed campaign / development cost"],
    ["duration_weeks", "Campaign duration (weeks)"]
  ];

  const vpDefs = isJa ? [
    ["hypothesis", "検証仮説"],
    ["audience", "検証対象ターゲット"],
    ["method", "検証手法"],
    ["offer", "提案オファー / メッセージ"],
    ["metric", "成功基準指標"],
    ["threshold", "次の投資を判断する基準値"],
    ["risks", "主なリスク"],
    ["unknowns", "残された不確実性・未知数"]
  ] : [
    ["hypothesis", "Hypothesis"],
    ["audience", "Target audience"],
    ["method", "Test method"],
    ["offer", "Proposed offer or message"],
    ["metric", "Success metric"],
    ["threshold", "Result that justifies further investigation"],
    ["risks", "Major risks"],
    ["unknowns", "Remaining unknowns"]
  ];

  el.innerHTML = viewHead(t("planner_head"), t("planner_sub"),
    isJa ? "オファー内容を具体化し、前提条件とユニットエコノミクスを算出します。すべての数値は入力に基づく例示的試算です。" : "Explore a possible commercial experiment and decide what to validate before committing resources. All figures are illustrative estimates from your inputs.") +
    `<main class="grid">
    <section class="card span-12"><h2>${isJa ? "1 · 起点と事業仮説" : "1 · Starting point & hypothesis"}</h2>
      <div class="chips mt" id="pl-start">${startOptions.map(s => `<button data-key="${s.key}" class="${s.key === startKey ? "active" : ""}">${esc(s.label)}</button>`).join("")}</div>
      <p class="note" id="pl-ev"></p>
      <label class="field mt">${isJa ? "事業アイデア（手動入力）" : "Business idea (manual start)"}<input id="pl-man" value="${esc(plan.manual_idea || "")}"></label>
      <label class="field mt">${isJa ? "機会仮説（未検証）" : "Opportunity hypothesis (unvalidated)"}<textarea id="pl-hyp" placeholder="${esc(ws.selected_label ? (isJa ? `例: 『${ws.selected_label}』のインドファン層は、${(f?.praised || ["その魅力的なテーマ"]).join("、")}を活かしたオファーに関心を示す。` : `e.g. Indian fans of ${ws.selected_label} will engage with an offer built around ${(f?.praised || ["its strongest themes"]).join(", ")}.`) : (isJa ? "例: インドの大学生ファン層が限定アートプリントを事前予約する" : "e.g. Indian college fans will pre-order a limited art print"))}">${esc(plan.hypothesis || "")}</textarea></label></section>
    <section class="card span-12"><h2>${isJa ? "2 · オファー設計" : "2 · Offer design"}</h2><div class="cols mt" style="grid-template-columns:repeat(2,1fr)">${Object.entries(userAreas).map(([k, aData]) => `<div class="col"><div class="col-header"><h3>${esc(aData.title)}</h3><span class="col-count" id="cnt-${k}">${aData.options.filter(o => o.active).length}</span></div>
      <p class="note" style="margin-top:0">${esc(aData.note)}</p><div class="chips" data-area="${k}">${aData.options.map(({ opt, active }) => `<button class="${active ? "active" : ""}">${esc(opt)}</button>`).join("")}</div>
      <label class="field mt">${isJa ? "検討メモ / 選定理由" : "Notes / rationale"}<textarea data-note="${k}">${esc(plan[k + "_note"] || "")}</textarea></label></div>`).join("")}</div>
      <div class="row mt"><button class="btn" id="pl-save">${isJa ? "計画を保存" : "Save plan"}</button></div></section>
    <section class="card span-12"><div class="card-header"><div><h2>${isJa ? "3 · 収支試算モデル" : "3 · Illustrative economics"} ${kind("assume", isJa ? "前提条件" : "Assumptions")}</h2><p class="hint">${isJa ? "ターゲット規模 → リーチ数 → 想定顧客数。デモ数値はダミー値であり、実際のインド市場調査データではありません。" : "Target audience → reached → customers. Demo values are arbitrary placeholders, not Indian market data."}</p></div>
      <button class="btn ghost btn-sm" id="pl-demo">${isJa ? "デモ前提数値を読込" : "Load demo assumptions"}</button></div>
      <div class="fields c4">${fieldDefs.map(([k, l, typ]) =>
      typ === "select" ? `<label class="field">${l}<select id="a-${k}">${["INR", "JPY", "USD"].map(x => `<option ${a[k] === x ? "selected" : ""}>${x}</option>`).join("")}</select></label>`
        : `<label class="field">${l}<input type="number" min="0" step="any" id="a-${k}" value="${esc(a[k] ?? 0)}"></label>`).join("")}</div>
      <div id="calc-out" class="mt"></div>
      <details class="mt"><summary style="cursor:pointer;color:var(--naruto-gold);font-weight:700">${isJa ? "算出計算式" : "Formulas used"}</summary><div id="formulas"></div></details>
      <label class="field mt">${isJa ? "前提数値の根拠・情報源はどこですか？" : "Where do these assumptions come from?"}<input id="pl-src" value="${esc(plan.assumption_source || "")}" placeholder="${isJa ? "例: チーム推定値、学生60名アンケート、現地パートナー見積もり" : "e.g. team estimate; survey of 60 students; partner quote"}"></label></section>
    <section class="card span-12"><div class="card-header"><div><h2>${isJa ? "4 · 商業検証実験の設計" : "4 · Validation experiment"} ${kind("hyp", isJa ? "事業仮説" : "Hypothesis")}</h2><p class="hint">${isJa ? "実験は未実施です。検証結果は本ツールの出力ではなく、実際のテストから得られる必要があります。" : "No experiment has been run. Results must come from a real test, never from this tool."}</p></div>
      <button class="btn ghost btn-sm" id="vp-sug">${isJa ? "選択内容から提案文を生成" : "Suggest from my selections"}</button></div>
      <div class="fields c2">${vpDefs.map(([k, l]) =>
          `<label class="field">${l}<textarea id="vp-${k}">${esc(vp[k] || "")}</textarea></label>`).join("")}</div>
      <div class="row mt"><button class="btn" id="vp-save">${isJa ? "検証計画を保存" : "Save validation plan"}</button><a class="btn ghost" href="#/brief">${isJa ? "事業機会提案書を生成 →" : "Generate the Opportunity Brief →"}</a></div></section>
  </main>`;

  const evText = k => {
    const norm = START_MAP[k]?.en || k;
    if (norm === "Selected title") {
      return ws.selected_label
        ? `${kind("observed", isJa ? "観測実データ" : "Observed")} ${esc(ws.selected_label)}`
        : (isJa ? "作品が選択されていません — コマンドセンターで作品を選択してください。" : "No title selected — choose one in the Command Center.");
    }
    if (norm === "Audience finding") {
      return f
        ? `${kind("observed", isJa ? "観測実データ" : "Observed")} ${esc(f.summary)}`
        : (isJa ? "観客インテリジェンスで分析結果が選択されていません。" : "No finding selected in Audience Intelligence.");
    }
    if (norm === "Creative concept") {
      return c
        ? `${kind("hyp", isJa ? "事業仮説" : "Hypothesis")} <b>${esc(c.working_title)}</b> — ${esc(c.core_premise)}`
        : (isJa ? "クリエイティブラボで企画が作成されていません。" : "No concept built in the Creative Lab.");
    }
    return isJa ? "下記に事業アイデアを手動で入力してください。" : "Describe the idea below.";
  };

  let st = startKey;
  $("#pl-ev").innerHTML = evText(st);
  $("#pl-start").querySelectorAll("button").forEach(b => b.onclick = () => {
    $("#pl-start").querySelectorAll("button").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    st = b.dataset.key;
    $("#pl-ev").innerHTML = evText(st);
  });
  document.querySelectorAll("[data-area]").forEach(g => g.querySelectorAll("button").forEach(b => b.onclick = () => {
    b.classList.toggle("active");
    $("#cnt-" + g.dataset.area).textContent = g.querySelectorAll("button.active").length;
  }));

  const collectPlan = () => {
    const p = { start: st, manual_idea: $("#pl-man").value, hypothesis: $("#pl-hyp").value, assumption_source: $("#pl-src").value };
    document.querySelectorAll("[data-area]").forEach(g => { p[g.dataset.area] = [...g.querySelectorAll("button.active")].map(b => b.textContent); });
    document.querySelectorAll("[data-note]").forEach(t => { p[t.dataset.note + "_note"] = t.value; });
    return p;
  };

  $("#pl-save").onclick = async () => {
    try {
      await post("/api/workspace", { plan: collectPlan() });
      sfx(window.sfxJapaneseChime);
      toast(isJa ? "事業計画をワークスペースに保存しました。" : "Plan saved to the workspace.");
    } catch (e) { toast("⚠ " + e.message); }
  };
  $("#pl-src").onchange = () => post("/api/workspace", { plan: collectPlan() });

  const keys = ["currency", "target_audience", "reach_rate_pct", "conversion_rate_pct", "price", "variable_cost", "fixed_costs", "duration_weeks"];
  let isDemo = !!a.is_demo;
  const runCalc = async () => {
    const body = {}; keys.forEach(k => body[k] = k === "currency" ? $("#a-" + k).value : Number($("#a-" + k).value || 0));
    body.is_demo = isDemo && keys.every(k => k === "currency" || Number(DEMO[k]) === body[k]);
    try {
      const r = await post("/api/calc", body); const x = r.result, cur = body.currency;
      $("#formulas").innerHTML = r.formulas.map(([n, fm]) => `<div class="formula">${esc(n)} = ${esc(fm)}</div>`).join("");
      if (x.errors.length) { $("#calc-out").innerHTML = x.errors.map(e => `<p class="warn">✗ ${esc(e)}</p>`).join(""); return; }
      if (!body.target_audience) {
        $("#calc-out").innerHTML = `<p class="note">${isJa ? "ターゲット規模と比率を入力すると試算結果が表示されます。" : "Enter a target audience and rates to see illustrative results."}</p>`;
        return;
      }
      $("#calc-out").innerHTML = `${body.is_demo ? `<p class="warn">${isJa ? "⚠ デモ用の試算前提です。実際の意思決定前に実地調査データに置き換えてください。" : "⚠ Showing DEMO assumptions. Replace them with researched figures before using the results."}</p>` : ""}${x.warnings.map(w => `<p class="warn">⚠ ${esc(w)}</p>`).join("")}
        <div class="statgrid" style="grid-template-columns:repeat(5,1fr)"><div class="stat-box"><b>${fmt(x.reached)}</b><span>${isJa ? "リーチ想定人数" : "Reached people"}</span></div><div class="stat-box"><b>${fmt(x.customers)}</b><span>${isJa ? "想定顧客数" : "Customers"}</span></div>
        <div class="stat-box"><b>${cur} ${fmt(x.gross_revenue)}</b><span>${isJa ? "総売上" : "Gross revenue"}</span></div><div class="stat-box"><b>${cur} ${fmt(x.contribution)}</b><span>${isJa ? "限界利益" : "Contribution"}</span></div>
        <div class="stat-box"><b style="color:${x.result_after_fixed < 0 ? "var(--kurama-red)" : "var(--naruto-gold)"}">${cur} ${fmt(x.result_after_fixed)}</b><span>${isJa ? "固定費差引後損益" : "Result after fixed costs"}</span></div></div>
        <div class="funnel mt">${[[isJa ? "ターゲット規模" : "Target audience", body.target_audience], [isJa ? "リーチ数" : "Reached", x.reached], [isJa ? "顧客数" : "Customers", x.customers]].map(([l, v]) => `<div style="width:${Math.max(1, v / body.target_audience * 100)}%">${l}: ${fmt(v)}</div>`).join("")}</div>
        <p class="note">${esc(x.label)}${x.break_even_customers ? (isJa ? ` 損益分岐点: 約 ${fmt(x.break_even_customers)} 顧客。` : ` Break-even: about ${fmt(x.break_even_customers)} customers.`) : ""}</p>`;
    } catch (e) { $("#calc-out").innerHTML = `<p class="warn">${esc(e.message)}</p>`; }
  };
  keys.forEach(k => $("#a-" + k).onchange = runCalc);
  $("#pl-demo").onclick = () => { keys.forEach(k => $("#a-" + k).value = DEMO[k]); isDemo = true; runCalc(); };
  runCalc();

  $("#vp-sug").onclick = () => {
    const p = collectPlan();
    const offer = (p.monetization[0] || p.distribution[0] || p.localization[0] || (isJa ? "提案オファー案" : "the proposed offer"));
    const s = isJa ? {
      hypothesis: p.hypothesis,
      audience: "1つのチャネルを通じてリーチ可能なインドのファン層（例: 大学アニメサークルやクリエイターコミュニティ）",
      method: `「${offer}」に関する2週間のランディングページ / 事前予約テスト。ローカライズ訴求と標準訴求のA/Bテストを実施。`,
      offer,
      metric: "訪問者あたりの登録率または事前予約率（ローカライズ訴求 vs 標準訴求の比較）",
      threshold: "テスト実施前に基準値を決定（例: 試算モデルで想定した転換率を上回る予約率）",
      risks: "サンプル規模が小さくバイアスがある可能性。キャンパス層がインド全体を代表しない可能性。ライセンス未許諾。",
      unknowns: "大規模展開時の支払意欲、地域別の嗜好差、現地パートナーの対応力。"
    } : {
      hypothesis: p.hypothesis,
      audience: "Indian fans reachable through one channel (e.g. a college club or creator community)",
      method: `Two-week landing-page / pre-order test for '${offer}', with one localized and one standard message (A/B).`,
      offer,
      metric: "Sign-up or pre-order rate per visitor; compare localized vs standard message.",
      threshold: "Decide the threshold before the test (e.g. pre-order rate above the conversion rate assumed in the calculator).",
      risks: "Small, self-selected sample; campus audience may not represent wider India; licensing not yet confirmed.",
      unknowns: "Willingness to pay at scale; regional differences; partner availability."
    };
    Object.entries(s).forEach(([k, v]) => $("#vp-" + k).value = v);
    toast(isJa ? "選択肢に基づき検証計画の提案文を入力しました。編集して保存してください。" : "Suggested plan filled in — edit, then save.");
  };

  $("#vp-save").onclick = async () => {
    const v = {};
    ["hypothesis", "audience", "method", "offer", "metric", "threshold", "risks", "unknowns"].forEach(k => v[k] = $("#vp-" + k).value);
    try {
      await post("/api/workspace", { validation_plan: v });
      sfx(window.sfxJapaneseChime);
      toast(isJa ? "検証計画を保存しました。" : "Validation plan saved.");
    } catch (e) { toast("⚠ " + e.message); }
  };

  const cautions = [];
  if (!f) cautions.push(isJa ? "観客分析結果が紐付いていません — 本計画はまだデータ根拠に基づいた設計になっていません。" : "No audience finding is attached — this plan is not evidence-led yet.");
  cautions.push(isJa ? "売上・収支試算は入力された前提条件に完全に依存します。" : "Revenue figures depend entirely on the assumptions you enter.");
  Shinigami({ cautions, guide: isJa ? "起点を決め、オファーを選択し、ご自身の前提数値で試算を検証してください。" : "Pick a starting point, choose offers, then test the economics with your own assumptions." });
}

/* ================================================================= BRIEF */
async function viewBrief(el) {
  const isJa = currentLang === "ja";
  const b = await api("/api/brief");
  const st = S.status || await api("/api/status");
  el.innerHTML = viewHead(t("brief_head"), b.title,
    isJa ? `本ワークスペースから ${b.generated_at} に生成。意思決定支援用サマリー。` : `Generated ${b.generated_at} from this workspace only. Decision support, not independent verification.`) +
    `<main class="grid"><section class="card span-12 no-print"><div class="row">
      <button class="btn" id="br-re">${t("brief_regen")}</button><button class="btn ghost" id="br-save">${t("brief_save")}</button>
      <a class="btn ghost" href="/api/brief.md">${isJa ? "Markdownダウンロード" : "Download Markdown"}</a>${st.pdf_available ? `<a class="btn ghost" href="/api/brief.pdf">${isJa ? "PDFダウンロード" : "Download PDF"}</a>` : `<span class="note">${isJa ? "PDF出力には reportlab が必要です。" : "PDF needs reportlab."}</span>`}
      <button class="btn ghost" onclick="window.print()">${t("brief_print")}</button></div>
      <div class="row mt-s"><span class="note" style="margin:0">${isJa ? "データエクスポート:" : "Tabular exports:"}</span><a class="linklike" href="/api/export/aspects.csv">${isJa ? "作品評価側面 CSV" : "Aspect findings CSV"}</a>
        <a class="linklike" href="/api/export/trends.csv">${isJa ? "トレンド指標 CSV" : "Trend metrics CSV"}</a><a class="linklike" href="/api/export/assumptions.csv">${isJa ? "収支前提・試算 CSV" : "Assumptions &amp; estimates CSV"}</a></div>
      <p class="note">${isJa ? "入力内容を修正:" : "To revise inputs:"} <a class="linklike" href="#/command">${isJa ? "作品選択" : "title"}</a> · <a class="linklike" href="#/audience">${isJa ? "根拠とテーマ" : "evidence &amp; themes"}</a> · <a class="linklike" href="#/lab">${isJa ? "企画" : "concept"}</a> · <a class="linklike" href="#/planner">${isJa ? "オファー・前提・検証" : "offer, assumptions, test"}</a></p></section>
    ${Object.entries(b.sections).map(([h, items], i) => {
      const title = isJa ? (BRIEF_SECS_JA[h] || h) : h;
      return `<section class="card span-12 brief-sec ${h === "Risks and limitations" ? "risk" : ""}">
        <h2 style="font-size:18px">${i + 1}. ${esc(title)}</h2>
        <ul class="mt-s">${items.map(x => `<li>${esc(x)}</li>`).join("")}</ul>
      </section>`;
    }).join("")}
  </main>`;
  $("#br-re").onclick = () => { route(); toast(isJa ? "現在のワークスペースから提案書を再生成しました。" : "Brief regenerated from the current workspace."); };
  $("#br-save").onclick = async () => { try { await api("/api/brief/save", { method: "POST" }); sfx(window.sfxJapaneseChime); toast(isJa ? "提案書を保存しました。" : "Brief saved to the workspace."); } catch (e) { toast("⚠ " + e.message); } };
  document.querySelectorAll('a[href^="/api/export/"]').forEach(a => a.onclick = async ev => {
    ev.preventDefault(); const r = await fetch(a.href); if (!r.ok) return toast(isJa ? "このセクションにはまだエクスポートするデータがありません。" : "Nothing to export yet for this section.");
    const blob = await r.blob(); const u = URL.createObjectURL(blob); const t = document.createElement("a"); t.href = u; t.download = a.href.split("/").pop(); t.click(); URL.revokeObjectURL(u);
  });
  Shinigami(b.gaps.length
    ? { cautions: [isJa ? `この提案書には ${b.gaps.length} 件のデータギャップ（不足点）があります。「リスクと制約事項」を確認してください。` : `This brief has ${b.gaps.length} evidence gap(s), listed under Risks and limitations.`] }
    : { discoveries: [isJa ? "すべての項目に入力・根拠データが存在します。ただし依然として実地検証が必要な仮説です。" : "Every section has supporting inputs. It is still a set of hypotheses for validation."] });
}

/* ================================================================== DATA */
async function viewData(el) {
  const isJa = currentLang === "ja";
  const s = await api("/api/status"); S.status = s;
  el.innerHTML = viewHead(t("data_head"), t("data_sub"),
    isJa ? "ファイル、網羅性、インポート履歴、手法およびライセンス。" : "Files, coverage, imports, methods and licences.") +
    `<main class="grid"><section class="card span-12">${statusHtml(s)}</section>
    <section class="card span-6"><h2>${isJa ? "最近のインポート履歴" : "Recent imports"}</h2>${s.import_log.length ? `<div class="tbl-wrap mt"><table class="tbl"><thead><tr>
      <th>${isJa ? "日時" : "When"}</th><th>${isJa ? "種類" : "Kind"}</th><th>${isJa ? "ファイル名" : "File"}</th><th>${isJa ? "有効行数" : "Valid"}</th><th>${isJa ? "読込行数" : "Read"}</th></tr></thead><tbody>
      ${s.import_log.slice().reverse().map(e => `<tr><td>${esc((e.imported_at || "").slice(0, 16))}</td><td>${esc(e.kind)}</td><td>${esc(e.file)}</td><td class="num">${fmt(e.rows_valid)}</td><td class="num">${fmt(e.rows_read)}</td></tr>`).join("")}</tbody></table></div>` : `<p class='note'>${isJa ? "インポート履歴はありません。" : "No imports yet."}</p>`}</section>
    <section class="card span-6"><h2>${isJa ? "分析手法と算出定義" : "Methods"}</h2><ul class="mini-list mt">
      <li><b>${isJa ? "トレンドモメンタム" : "Trend momentum"}</b> — ${isJa ? "直近期間とその直前の同等期間（月次データの場合は月数）を比較。基準平均が1ポイント以上の場合のみ変動率(%)を算出。十分な期間がないものは除外、欠損期間の補完は一切行いません。" : "recent window vs the preceding window of equal length (months for monthly data); % change only when the baseline mean ≥ 1 point; insufficient windows are not ranked; missing periods are never filled."}</li>
      <li><b>${isJa ? "感情分析" : "Sentiment"}</b> — ${esc(s.sentiment_method)}.</li>
      <li><b>${isJa ? "作品評価側面 (Aspects)" : "Aspects"}</b> — ${isJa ? "文ごとのキーワード分類辞書 ＋ 文単位の極性判定。1レビューにつき1回カウント。" : "sentence keyword taxonomy + sentence sentiment, counted once per review."}</li>
      <li><b>${isJa ? "Hidden Gems (隠れた名作)" : "Hidden Gems"}</b> — ${isJa ? "レビュー件数5件以上、称賛が優勢な側面があり、かつ批判/賛否両論の側面がある、または30%以上の低評価/賛否両論レビューが存在する作品。コントラスト指数は実験的指標です。" : "≥5 reviews, a mostly-praised aspect, and a criticised/divided aspect or ≥30% mixed/negative reviews. Contrast index is experimental."}</li>
      <li><b>${isJa ? "企画コンセプト" : "Concepts"}</b> — ${isJa ? "ルールベース生成（外部AI不使用）。" : "rules-based; no external AI."} <b>${isJa ? "収支計算機" : "Calculator"}</b> — ${isJa ? "前提数値から透明性をもって算出されるファネル計算。" : "transparent funnel from your assumptions."}</li></ul>
      <p class="note">${isJa ? "CLIコマンド:" : "Commands:"} <code>python scripts/ingest.py status</code> · <code>trends …</code> · <code>reviews-kaggle data/raw/reviews.csv</code> · <code>audit-mal</code> · <code>analyse</code></p></section></main>`;
  Shinigami({ guide: isJa ? "AniScope内のすべての数値は、ここに一覧表示されているファイルに遡って検証可能です。" : "Every figure in AniScope traces back to a file listed here." });
}

/* ================================================================ ROUTER */
const VIEWS = { command: viewCommand, radar: viewRadar, audience: viewAudience, gems: viewGems, lab: viewLab, planner: viewPlanner, brief: viewBrief, data: viewData };
async function route() {
  const name = (location.hash.replace(/^#\/?/, "").split("?")[0]) || "command";
  const fn = VIEWS[name] || viewCommand;
  document.querySelectorAll("#nav-links a").forEach(a => a.classList.toggle("on", a.dataset.view === name));
  $("#nav-mobile").value = VIEWS[name] ? name : "command";
  const isJa = currentLang === "ja";
  const el = $("#view");
  el.innerHTML = loading();
  try { await fn(el); }
  catch (e) {
    el.innerHTML = e.detail && e.detail.code === "catalog_missing"
      ? `<header class="hero">${catalogMissing({ catalog_error: e.detail.message, data_dir: e.detail.data_dir })}</header>`
      : `<div class="empty mt"><h3>${isJa ? "エラーが発生しました" : "Something went wrong"}</h3>${esc(e.message)}</div>`;
    Shinigami({ cautions: [e.message] });
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}
window.addEventListener("hashchange", route);
$("#nav-mobile").onchange = e => location.hash = "#/" + e.target.value;
$("#btn-status").onclick = () => { sfx(window.sfxCrossSealSnap); openStatus(); };

const btnLang = $("#btn-lang-toggle");
if (btnLang) {
  btnLang.onclick = () => {
    currentLang = currentLang === "en" ? "ja" : "en";
    localStorage.setItem("aniscope_lang", currentLang);
    sfx(window.sfxCrossSealSnap);
    toast(currentLang === "ja" ? "言語を日本語に切り替えました" : "Language switched to English");
    updateNavText();
    route();
  };
}

const btnTheme = $("#btn-theme-toggle");
if (btnTheme) {
  btnTheme.onclick = () => {
    const curTheme = localStorage.getItem("aniscope_theme") || "dark";
    const nextTheme = curTheme === "light" ? "dark" : "light";
    localStorage.setItem("aniscope_theme", nextTheme);
    if (nextTheme === "light") {
      document.documentElement.classList.add("light-theme");
    } else {
      document.documentElement.classList.remove("light-theme");
    }
    sfx(window.sfxCrossSealSnap);
    toast(nextTheme === "light" ? (currentLang === "ja" ? "ライトモードに切り替えました" : "Switched to Light mode") : (currentLang === "ja" ? "ダークモードに切り替えました" : "Switched to Dark mode"));
    updateNavText();
  };
}

document.querySelectorAll(".modal-overlay").forEach(m => m.addEventListener("click", e => { if (e.target === m) m.classList.remove("open"); }));

(async () => {
  try {
    updateNavText();
    if (localStorage.getItem("aniscope_theme") === "light") {
      document.documentElement.classList.add("light-theme");
    }
    await refreshWs();
  } catch (e) { /* catalog may be missing */ }
  route();
})();
