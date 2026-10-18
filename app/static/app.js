/* Reelpath interface. Every title, score, path and count is read from the API; nothing is invented here. */
"use strict";
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const VIEWS = ["home", "picks", "assistant", "catalog", "top", "users", "lab"];
const LIST_VIEWS = ["catalog", "top", "users"];
const MAX_CATALOG_OFFSET = 10000;
const taste = {
  rounds: [],
  answers: [],
  index: 0,
  personal: false,
  genre: "",
  results: [],
  posters: {},
  requestId: 0,
};
const state = {
  view: "home",
  offset: 0,
  limit: 12,
  metric: "rating",
  rows: [],
  loading: false,
  requestId: 0,
  genres: [],
  loaded: {},
};
let detailRequestId = 0;

function escapeText(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
}
const formatNumber = (value) =>
  new Intl.NumberFormat("en-US").format(Number(value) || 0);
/* MovieLens stores "Godfather, The (1972)"; show "The Godfather". */
function cleanTitle(title) {
  let text = String(title ?? "").replace(/\s*\(\d{4}(?:[–-]\d{4})?\)\s*$/, "");
  const alternate = text.match(/^(.+?)\s+\((?:a\.k\.a\.\s+)?[^()]+\)$/);
  if (alternate) text = alternate[1];
  const article = text.match(/^(.*), (The|A|An|Les|La|Le|L'|Il|El|Der|Die|Das)$/);
  if (article) text = article[2] + (article[2].endsWith("'") ? "" : " ") + article[1];
  return text;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  let result;
  try {
    result = await response.json();
  } catch {
    const error = new Error(
      response.status === 429
        ? "Too many requests. Wait a minute and try again. Your choices are kept."
        : "The service did not respond. Check that the local services are running.",
    );
    error.status = response.status;
    throw error;
  }
  if (!response.ok) {
    const detail = result.detail ?? result.message ?? "Request failed";
    const error = new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? "Check the values you entered and try again."
          : detail.message || "Check the values you entered and try again.",
    );
    error.status = response.status;
    error.code = detail?.code;
    throw error;
  }
  return result;
}

function notice(text) {
  $("#notice").textContent = text;
  $("#notice").hidden = !text;
}

/* ---------- Film cards ---------- */
/* posters.json maps movie_id → [TMDB file name, TMDB ID]; request only the size a slot needs. */
const TMDB_IMAGES = "https://image.tmdb.org/t/p/";
function posterUrl(movieId, size = "w342") {
  const entry = taste.posters[movieId];
  return entry ? `${TMDB_IMAGES}${size}/${entry[0]}` : null;
}
function posterImage(movieId, size) {
  const url = posterUrl(movieId, size);
  return url ? `<img src="${escapeText(url)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : "";
}
function posterArt(movie, size = "w342") {
  const hue = (Number(movie.movie_id) * 47) % 360;
  return `<span class="poster" data-size="${size}" style="--hue:${hue}">${posterImage(movie.movie_id, size)}<span class="poster-fallback">${escapeText(cleanTitle(movie.title))}</span></span>`;
}
/* The genre a visitor filtered by is always listed first, so a filtered result visibly matches it. */
function activeGenre() {
  if (state.view === "picks") return taste.genre;
  if (state.view === "assistant") return typeof assistant === "object" ? assistant.current?.plan?.genre : "";
  if (state.view === "users") return $("#user-genre").value;
  if (state.view === "catalog") return $("#genre").value;
  return "";
}
function genreLine(movie, limit = 3) {
  const preferred = activeGenre();
  const genres = [...(movie.genres || [])].sort((a, b) => (b === preferred) - (a === preferred));
  return escapeText(genres.slice(0, limit).join(" · ") || "No genre listed");
}
function card(movie, mode = "catalog") {
  const title = escapeText(cleanTitle(movie.title));
  const year = movie.year ? `<span class="year">${movie.year}</span>` : "";
  if (mode === "pick")
    return `<button class="film-card pickable" data-pick="${movie.movie_id}" aria-label="Choose ${title}">${posterArt(movie)}<span class="film-info"><span class="film-title">${title}</span><span class="film-meta">${year}${genreLine(movie, 2)}</span></span><span class="pick-badge" aria-hidden="true">I like this</span></button>`;
  let footer;
  if (mode === "match")
    footer = `<span class="signal">Linked to ${escapeText(movie.supporting_seeds)} of your picks</span><button class="link" data-why-pick="${movie.movie_id}">Why? →</button>`;
  else if (mode === "user")
    footer = `<span class="signal">${escapeText(movie.supporting_seeds || 0)} liked films point here</span><button class="link" data-evidence="${movie.movie_id}">Why? →</button>`;
  else if (mode === "community")
    footer = `<span class="signal">★ ${Number(movie.score).toFixed(2)} · ${formatNumber(movie.support)} ratings</span><button class="link" data-detail="${movie.movie_id}">Fans also liked →</button>`;
  else
    footer = `<button class="link" data-detail="${movie.movie_id}">Fans also liked →</button>`;
  return `<article class="film-card"><button class="poster-button" data-detail="${movie.movie_id}" aria-label="Open ${title}">${posterArt(movie)}</button><div class="film-info"><span class="film-title">${title}</span><span class="film-meta">${year}${genreLine(movie)}</span></div><div class="film-foot">${footer}</div></article>`;
}
function emptyState(text) {
  return `<div class="empty">${escapeText(text)}</div>`;
}
function skeleton(count) {
  return Array.from({ length: count }, () => '<div class="film-card skeleton"><span class="poster"></span><span class="line"></span><span class="line short"></span></div>').join("");
}

/* ---------- Navigation ---------- */
function setView(view, updateAddress = true) {
  if (!VIEWS.includes(view)) view = "home";
  const changed = state.view !== view;
  state.view = view;
  state.requestId++;
  state.loading = false;
  if (updateAddress && location.hash !== "#" + view)
    history.pushState(null, "", "#" + view);
  $$("[data-screen]").forEach((screen) => {
    screen.hidden = screen.dataset.screen !== view;
  });
  $$(".nav-item").forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  $("#site-nav").classList.remove("open");
  $("#menu-toggle").setAttribute("aria-expanded", "false");
  if (changed) {
    notice("");
    if ($("#detail-dialog").open) $("#detail-dialog").close();
    window.scrollTo({ top: 0, behavior: "instant" });
    document.title = view === "home" ? "Reelpath: find your next film" : `${$("#screen-" + view + " h1")?.textContent || "Reelpath"} · Reelpath`;
  }
  if (changed && ["assistant", "lab"].includes(view)) checkModel();
  if (LIST_VIEWS.includes(view) && (changed || !state.loaded[view])) return loadFilms();
}
window.addEventListener("hashchange", () => setView(location.hash.slice(1), false));

/* ---------- Data lists (catalog, top films, dataset users) ---------- */
function listPath(view) {
  if (view === "catalog") {
    const q = $("#search").value.trim();
    const genre = $("#genre").value;
    return `/api/movies?limit=${state.limit}&offset=${state.offset}&q=${encodeURIComponent(q)}${genre ? "&genre=" + encodeURIComponent(genre) : ""}`;
  }
  if (view === "top")
    return `/api/movies/trending?limit=20&metric=${state.metric}&window_days=365`;
  const user = Number($("#user-id").value);
  const genre = $("#user-genre").value;
  return $("#user-mode").value === "discover"
    ? `/api/users/${user}/discover?limit=${state.limit}`
    : `/api/users/${user}/recommendations?limit=${state.limit}${genre ? "&genre=" + encodeURIComponent(genre) : ""}`;
}
function renderRanking(items) {
  const pagerank = state.metric === "pagerank";
  return items
    .map(
      (movie, index) =>
        `<li class="rank-row"><span class="rank">${index + 1}</span><button class="rank-poster" data-detail="${movie.movie_id}" aria-label="Open ${escapeText(cleanTitle(movie.title))}">${posterArt(movie, "w92")}</button><div class="rank-text"><button class="film-title link-title" data-detail="${movie.movie_id}">${escapeText(cleanTitle(movie.title))}</button><span class="film-meta">${movie.year || ""} · ${genreLine(movie)}</span></div><div class="rank-value">${pagerank ? `<strong>${Number(movie.score).toFixed(2)}</strong><span>centrality</span>` : `<strong>★ ${Number(movie.score).toFixed(2)}</strong><span>${formatNumber(movie.support)} ratings</span>`}</div></li>`,
    )
    .join("");
}
async function loadFilms() {
  const requestId = ++state.requestId;
  const view = state.view;
  if (!LIST_VIEWS.includes(view)) return;
  const grid = $("#" + view + "-grid");
  state.loading = true;
  grid.classList.add("loading");
  if (view !== "top") grid.innerHTML = skeleton(view === "catalog" ? 6 : 4);
  notice("");
  const userId = Number($("#user-id").value);
  if (view === "users" && !(userId >= 1)) {
    state.loading = false;
    grid.classList.remove("loading");
    grid.innerHTML = emptyState("Enter a rater ID between 1 and 610.");
    return;
  }
  if (view === "users") loadFavourites(userId, requestId);
  try {
    const result = await api(listPath(view));
    if (requestId !== state.requestId) return;
    state.rows = result.items;
    state.loaded[view] = true;
    if (view === "top") {
      grid.innerHTML = renderRanking(result.items) || emptyState("No ranking available yet. Run make analytics.");
      $("#top-explain").textContent =
        state.metric === "pagerank"
          ? "PageRank on the film-similarity graph: a film ranks high when many strongly connected films point to it. It measures how central a film is, not how good it is."
          : "Average rating during the last 365 days of the dataset, adjusted toward the overall average so films with few ratings can’t win by luck (Bayesian average, at least 3 ratings).";
    } else if (view === "catalog") {
      grid.innerHTML = result.items.length
        ? result.items.map((movie) => card(movie, "catalog")).join("")
        : emptyState("No films match. Try a shorter title or another genre.");
      $("#show-more").hidden =
        result.items.length < state.limit ||
        state.offset + state.limit > MAX_CATALOG_OFFSET;
      $("#show-previous").hidden = state.offset === 0;
      $("#catalog-note").textContent = result.items.length
        ? `Showing ${formatNumber(state.offset + 1)}–${formatNumber(state.offset + result.items.length)}`
        : "";
    } else {
      const discover = result.method === "louvain_discovery";
      grid.innerHTML = result.items.length
        ? result.items.map((movie) => card(movie, discover ? "community" : "user")).join("")
        : emptyState("No recommendations for this rater with these filters.");
      $("#users-explain").textContent = discover
        ? `Films from the taste communities (Louvain clusters) where rater ${userId}’s favourites sit, excluding films they already rated.`
        : result.method === "item_cf"
          ? `Films similar to the ones rater ${userId} rated 4★ or more, excluding everything they already rated. Open “Why?” for the exact path.`
          : `Rater ${userId} has too little history, so these are well-rated films instead (not personalised).`;
    }
    if (result.fallback_reason) notice("Note: " + result.fallback_reason);
  } catch (error) {
    if (requestId !== state.requestId) return;
    notice(error.message);
    grid.innerHTML = emptyState(
      error.status === 404
        ? "That ID does not exist in the dataset."
        : "We couldn’t load this list. Check that the services are running.",
    );
  } finally {
    if (requestId === state.requestId) {
      state.loading = false;
      grid.classList.remove("loading");
    }
  }
}

async function loadFavourites(userId, requestId) {
  try {
    const result = await api(`/api/users/${userId}/favorites?limit=8`);
    if (requestId !== state.requestId) return;
    result.items.forEach((row) => state.rows.includes(row) || state.rows.push(row));
    $("#users-context-title").textContent = `What rater ${userId} loved`;
    $("#users-favourites").innerHTML = result.items
      .map(
        (movie) =>
          `<button class="strip-film" data-detail="${movie.movie_id}" aria-label="Open ${escapeText(cleanTitle(movie.title))}">${posterArt(movie, "w185")}<span class="strip-title">${escapeText(cleanTitle(movie.title))}</span><span class="strip-score">★ ${Number(movie.score).toFixed(1)}</span></button>`,
      )
      .join("");
    $("#users-context").hidden = !result.items.length;
  } catch {
    if (requestId === state.requestId) $("#users-context").hidden = true;
  }
}

/* ---------- Dialogs ---------- */
function openDetail(html) {
  const requestId = ++detailRequestId;
  $("#detail-content").innerHTML = html;
  if (!$("#detail-dialog").open) $("#detail-dialog").showModal();
  return requestId;
}
function currentDetail(requestId) {
  return requestId === detailRequestId && $("#detail-dialog").open;
}
function findMovie(movieId) {
  const pools = [
    state.rows,
    taste.results,
    taste.rounds.flat(),
    typeof assistant === "object" ? assistant.current?.items || [] : [],
  ];
  for (const pool of pools) {
    const movie = pool.find((row) => row.movie_id === movieId);
    if (movie) return movie;
  }
  return null;
}
function dialogHead(movie, movieId, label) {
  const base = movie || { movie_id: movieId, title: "Film " + movieId, genres: [] };
  return `<div class="detail-head">${posterArt(base, "w185")}<div><p class="kicker">${escapeText(label)}</p><h2 id="detail-title">${escapeText(cleanTitle(base.title))}</h2><p class="muted">${base.year || ""} ${base.genres?.length ? "· " + genreLine(base, 4) : ""}</p></div></div>`;
}
async function showSimilar(movieId) {
  const movie = findMovie(movieId);
  const heading = dialogHead(movie, movieId, "Fans also liked");
  const requestId = openDetail(heading + '<p class="muted">Finding films liked by the same people…</p>');
  try {
    const result = await api(`/api/movies/${movieId}/similar?limit=8`);
    if (!currentDetail(requestId)) return;
    result.items.forEach((row) => state.rows.includes(row) || state.rows.push(row));
    $("#detail-content").innerHTML =
      heading +
      (result.items.length
        ? `<p class="muted">People who rated this film 4★ or more also loved these. “Shared fans” counts those people.</p><ul class="similar-list">${result.items
            .map(
              (row) =>
                `<li><button class="similar-item" data-detail="${row.movie_id}">${posterArt(row, "w92")}<span><strong>${escapeText(cleanTitle(row.title))}</strong><small>${row.year || ""} · ${formatNumber(row.support)} shared fans</small></span><span class="meter" title="Similarity ${Number(row.score).toFixed(3)}" style="--value:${barWidth(row.score, result.items.map((r) => r.score))}%"></span></button></li>`,
            )
            .join("")}</ul>`
        : '<p class="muted">Not enough shared fans in this snapshot to link this film to others.</p>') +
      (taste.posters[movieId] ? `<p class="small muted"><a href="https://www.themoviedb.org/movie/${Number(taste.posters[movieId][1])}" target="_blank" rel="noopener noreferrer">Poster source on TMDB ↗</a></p>` : "");
  } catch (error) {
    if (currentDetail(requestId))
      $("#detail-content").innerHTML = heading + `<p class="error-text">${escapeText(error.message)}</p>`;
  }
}
async function showEvidence(movieId) {
  const user = Number($("#user-id").value);
  const movie = findMovie(movieId);
  const heading = dialogHead(movie, movieId, `Why for rater ${user}?`);
  const requestId = openDetail(heading + '<p class="muted">Following the graph…</p>');
  try {
    const result = await api(`/api/users/${user}/recommendations/${movieId}/explanation`);
    if (!currentDetail(requestId)) return;
    $("#detail-content").innerHTML =
      heading +
      (result.evidence.length
        ? `<p>Rater ${user} rated these films highly, and people who loved them also loved this one:</p>${reasonList(
            result.evidence.map((evidence) => ({
              movie_id: evidence.path[2].movie_id,
              title: evidence.path[2].title,
              support: evidence.support,
              similarity: evidence.similarity,
              note: `Rater ${user} gave it ${evidence.source_rating}★`,
            })),
          )}`
        : `<p>${escapeText(result.explanation)}</p>`) +
      `<p class="small muted">Path: Rater → RATED → film they liked → SIMILAR_TO → this film. Ratings are observed MovieLens data; similarity links come from Neo4j GDS (run ${escapeText(result.analytics_run_id || "none")}). ${escapeText(result.note)}</p>`;
  } catch (error) {
    if (currentDetail(requestId))
      $("#detail-content").innerHTML = heading + `<p class="error-text">${escapeText(error.message)}</p>`;
  }
}
/* Bars compare links within one list: the strongest link fills the bar. */
function barWidth(value, values) {
  const max = Math.max(...values.map(Number), 0);
  return max > 0 ? Math.max(6, Math.round((Number(value) / max) * 100)) : 0;
}
function reasonList(items) {
  return `<ul class="reason-list">${items
    .map(
      (item) =>
        `<li>${posterArt(item, "w92")}<span><strong>${escapeText(cleanTitle(item.title))}</strong><small>${formatNumber(item.support)} people loved both films${item.note ? " · " + escapeText(item.note) : ""}</small></span><span class="meter" title="Similarity ${Number(item.similarity).toFixed(3)}" style="--value:${barWidth(item.similarity, items.map((i) => i.similarity))}%"></span></li>`,
    )
    .join("")}</ul>`;
}
function reasonsHTML(movie) {
  return reasonList(
    (movie.reasons || []).slice(0, 5).map((reason) => ({
      movie_id: reason.seed_id,
      title: reason.seed_title,
      support: reason.support,
      similarity: reason.similarity,
    })),
  );
}
function showTasteEvidence(movieId) {
  const movie = taste.results.find((row) => row.movie_id === movieId);
  if (!movie) return;
  openDetail(
    dialogHead(movie, movieId, "Why this film?") +
      `<p>Because you picked ${movie.reasons?.length === 1 ? "this film" : `these ${movie.reasons?.length} films`}:</p>${reasonsHTML(movie)}<p class="small muted">“Loved” means rated 4★ or more by the same MovieLens rater. The bar shows how strong the link is. This is a connection in the data, not a guarantee you’ll like the film.</p>`,
  );
}

/* ---------- Quick picks ---------- */
function selectedPicks() {
  return taste.answers.filter((id) => id !== null && id !== undefined);
}
function renderRound() {
  const picked = selectedPicks().length;
  $("#taste-back").disabled = taste.index === 0;
  $("#round-label").textContent = `Round ${taste.index + 1} of 10`;
  $("#round-picks").textContent = picked ? ` · ${picked} ${picked === 1 ? "favourite" : "favourites"} so far` : " · Pick the one you like most";
  $("#round-bar").style.width = `${taste.index * 10}%`;
  $("#taste-finish").hidden = picked === 0;
  $("#taste-options").innerHTML = taste.rounds[taste.index].map((movie) => card(movie, "pick")).join("");
  $("#quiz-chosen").innerHTML = picked ? chosenHTML() : "";
}
function showPicksStage(stage) {
  $("#picks-intro").hidden = stage !== "intro";
  $("#taste-quiz").hidden = stage !== "quiz";
  $("#picks-results").hidden = stage !== "results";
}
async function startTaste() {
  const button = $("#start-taste");
  if (button.disabled) return;
  button.disabled = true;
  $("#taste-status").textContent = "Loading ten rounds of films…";
  try {
    const seed = crypto.getRandomValues(new Uint32Array(1))[0] % 2147483647;
    const result = await api(`/api/taste/rounds?seed=${seed}`);
    taste.rounds = result.rounds;
    taste.answers = [];
    taste.index = 0;
    taste.personal = false;
    taste.results = [];
    taste.genre = "";
    $("#taste-status").textContent = "";
    showPicksStage("quiz");
    renderRound();
  } catch (error) {
    $("#taste-status").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}
async function advanceTaste(movieId) {
  taste.answers[taste.index] = movieId;
  if (taste.index < 9) {
    taste.index++;
    renderRound();
    window.scrollTo({ top: $("#taste-quiz").offsetTop - 80, behavior: "smooth" });
    return;
  }
  await finishTaste();
}
async function finishTaste() {
  if (!selectedPicks().length) {
    $("#round-picks").textContent = " · Pick at least one film to get matches, then go back or start over.";
    return;
  }
  taste.personal = true;
  showPicksStage("results");
  renderChosen();
  renderGenreChips();
  await loadPicks();
}
function chosenHTML() {
  const chosen = taste.rounds.flat().filter((movie) => selectedPicks().includes(movie.movie_id));
  return (
    '<span class="muted small">Your picks:</span>' +
    chosen.map((movie) => `<span class="chosen" title="${escapeText(movie.title)}">${posterArt(movie, "w92")}<span>${escapeText(cleanTitle(movie.title))}</span></span>`).join("")
  );
}
function renderChosen() {
  $("#picks-chosen").innerHTML = chosenHTML();
}
function renderGenreChips() {
  $("#picks-genres").innerHTML = ["", ...state.genres]
    .map((genre) => `<button class="chip ${genre === taste.genre ? "active" : ""}" data-pick-genre="${escapeText(genre)}" aria-pressed="${genre === taste.genre}">${escapeText(genre || "All genres")}</button>`)
    .join("");
}
async function loadPicks() {
  const requestId = ++taste.requestId;
  const picks = selectedPicks();
  $("#picks-grid").innerHTML = skeleton(4);
  $("#picks-note").textContent = "Searching the graph…";
  try {
    const result = await api("/api/taste/recommendations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ movie_ids: picks, genre: taste.genre || null, limit: 12 }),
    });
    if (requestId !== taste.requestId) return;
    taste.results = result.items;
    $("#picks-grid").innerHTML = result.items.length
      ? result.items.map((movie) => card(movie, "match")).join("")
      : emptyState(`No ${taste.genre || ""} films are connected to your picks yet. Try “All genres” or pick more films.`);
    $("#picks-note").textContent = `${result.items.length} films connected to your ${picks.length} ${picks.length === 1 ? "pick" : "picks"}${taste.genre ? " · " + taste.genre : ""}. Strongest connections first.`;
  } catch (error) {
    if (requestId !== taste.requestId) return;
    $("#picks-grid").innerHTML = emptyState(error.message);
    $("#picks-note").textContent = "";
  }
}

/* ---------- Local model status ---------- */
const model = { requiresKey: false, requestId: 0 };
/* The key is optional: only servers started with REQUIRE_API_KEY=true ask for it. */
function modelHeaders(key) {
  const headers = { "Content-Type": "application/json" };
  if (String(key || "").trim()) headers["X-API-Key"] = String(key).trim();
  return headers;
}
function showKeyFields(show) {
  model.requiresKey = model.requiresKey || show;
  $("#assistant-key-field").hidden = !model.requiresKey;
  $("#lab-key-field").hidden = !model.requiresKey;
}
function renderModelStatus(status) {
  const name = `<code>${escapeText(status?.model || "qwen2.5-7b-instruct")}</code>`;
  let tone = "off";
  let html;
  if (!status) html = "Checking the local model…";
  else if (status.available && status.model_listed) {
    tone = "ready";
    html = `Local model ready · ${name}`;
  } else if (status.available) {
    tone = "warn";
    html = `LM Studio is running, but ${name} is not loaded. Load it, then <button type="button" class="link" data-check-model>check again</button>.`;
  } else
    html = `The local model is off. Open LM Studio, load ${name} and start the server on port 1234, then <button type="button" class="link" data-check-model>check again</button>.`;
  $$("[data-model-status]").forEach((node) => {
    node.dataset.tone = status ? tone : "checking";
    // Card rounds never call the model, so the assistant stays usable while only typed requests wait for it.
    const extra = tone !== "ready" && status && node.dataset.modelStatus === "assistant" ? " You can still choose films now; typed requests need the model." : "";
    node.innerHTML = `<span class="dot" aria-hidden="true"></span><span>${html}${extra}</span>`;
  });
}
async function checkModel() {
  const requestId = ++model.requestId;
  renderModelStatus(null);
  try {
    const status = await api("/api/model/status");
    if (requestId !== model.requestId) return;
    renderModelStatus(status);
    showKeyFields(Boolean(status.requires_key));
  } catch {
    if (requestId === model.requestId) renderModelStatus({ available: false });
  }
}

/* ---------- Query lab ---------- */
function syncKeys(source) {
  $$(".model-key").forEach((input) => {
    if (input !== source) input.value = source.value;
  });
}
function labTable(rows) {
  if (!rows.length) return emptyState("The query ran but found nothing. No result was invented.");
  const columns = Object.keys(rows[0]).filter((key) => !["reasons"].includes(key)).slice(0, 6);
  return `<div class="table-wrap"><table><thead><tr>${columns.map((c) => `<th>${escapeText(c)}</th>`).join("")}</tr></thead><tbody>${rows
    .map((row) => `<tr>${columns.map((c) => `<td>${escapeText(Array.isArray(row[c]) ? row[c].join(", ") : typeof row[c] === "number" && !Number.isInteger(row[c]) ? row[c].toFixed(3) : row[c])}</td>`).join("")}</tr>`)
    .join("")}</tbody></table></div>`;
}
async function askGraph() {
  const question = $("#question").value.trim();
  const output = $("#ask-result");
  if (!question) {
    output.innerHTML = '<p class="error-text">Type a question first, or click one of the examples.</p>';
    return;
  }
  const button = $("#ask-button");
  button.disabled = true;
  button.textContent = "Running…";
  output.innerHTML = `<div class="stage"><span class="stage-n">1</span><div><h3>Question</h3><p>${escapeText(question)}</p></div></div><p class="muted">The local model is reading the question…</p>`;
  try {
    const result = await api("/api/ask", {
      method: "POST",
      headers: modelHeaders($("#api-key").value),
      body: JSON.stringify({ question, limit: 10 }),
    });
    const plan = Object.entries(result.interpreted_intent).filter(([, value]) => value !== null && value !== undefined);
    output.innerHTML =
      `<div class="stage"><span class="stage-n">1</span><div><h3>Question</h3><p>${escapeText(question)}</p></div></div>` +
      `<div class="stage"><span class="stage-n">2</span><div><h3>Plan from the model</h3><div class="kv">${plan.map(([k, v]) => `<span><b>${escapeText(k)}</b> ${escapeText(v)}</span>`).join("")}</div></div></div>` +
      `<div class="stage"><span class="stage-n">3</span><div><h3>Checked Cypher template <small class="muted">#${escapeText(result.query_id)}</small></h3><pre>${escapeText(result.compiled_cypher)}</pre><details><summary>Bound parameters</summary><pre>${escapeText(JSON.stringify(result.parameters, null, 2))}</pre></details></div></div>` +
      `<div class="stage ok"><span class="stage-n">4</span><div><h3>Results from Neo4j</h3><p>${escapeText(result.explanation)}</p>${result.warnings.length ? `<p class="muted small">${escapeText(result.warnings.join(" "))}</p>` : ""}${labTable(result.rows)}</div></div>`;
  } catch (error) {
    if (error.status === 401) showKeyFields(true);
    output.innerHTML =
      `<div class="stage"><span class="stage-n">1</span><div><h3>Question</h3><p>${escapeText(question)}</p></div></div>` +
      `<div class="stage blocked"><span class="stage-n">✕</span><div><h3>${error.status === 422 ? "Rejected by a guardrail" : error.status === 401 ? "This server needs an access key" : error.status >= 503 ? "The local model is not responding" : "Could not run"}${error.status ? ` <small>HTTP ${error.status}</small>` : ""}</h3><p>${escapeText(error.message)}</p>${error.status === 422 ? "<p class=\"muted small\">Nothing was sent to the database. Only reviewed, read-only query templates can run.</p>" : ""}</div></div>`;
  } finally {
    button.disabled = false;
    button.textContent = "Run question";
  }
}

/* ---------- Events ---------- */
$$("[data-view]").forEach((button) =>
  button.addEventListener("click", (event) => {
    event.preventDefault?.();
    setView(button.dataset.view);
  }),
);
$("#menu-toggle").addEventListener("click", () => {
  const open = !$("#site-nav").classList.contains("open");
  $("#site-nav").classList.toggle("open", open);
  $("#menu-toggle").setAttribute("aria-expanded", String(open));
});
$("#catalog-form").addEventListener("submit", (event) => {
  event.preventDefault();
  state.offset = 0;
  loadFilms();
});
$("#genre").addEventListener("change", () => {
  state.offset = 0;
  loadFilms();
});
$("#users-form").addEventListener("submit", (event) => {
  event.preventDefault();
  loadFilms();
});
$("#user-mode").addEventListener("change", () => {
  $("#user-genre-field").hidden = $("#user-mode").value === "discover";
  loadFilms();
});
$("#user-genre").addEventListener("change", () => loadFilms());
$$("[data-metric]").forEach((button) =>
  button.addEventListener("click", () => {
    state.metric = button.dataset.metric;
    $$("[data-metric]").forEach((tab) => {
      tab.classList.toggle("active", tab === button);
      tab.setAttribute("aria-selected", String(tab === button));
    });
    loadFilms();
  }),
);
$("#show-previous").addEventListener("click", () => {
  if (state.view !== "catalog" || state.loading) return;
  state.offset = Math.max(0, state.offset - state.limit);
  loadFilms();
});
$("#show-more").addEventListener("click", () => {
  if (state.view !== "catalog" || state.loading || state.offset + state.limit > MAX_CATALOG_OFFSET) return;
  state.offset += state.limit;
  loadFilms();
});
document.addEventListener("click", (event) => {
  const target = event.target;
  if (!target.closest) return;
  const pick = target.closest("[data-pick]");
  const why = target.closest("[data-why-pick]");
  const evidence = target.closest("[data-evidence]");
  const detail = target.closest("[data-detail]");
  const genre = target.closest("[data-pick-genre]");
  const question = target.closest("[data-question]");
  if (target.closest("[data-check-model]")) {
    checkModel();
    return;
  }
  if (pick) advanceTaste(Number(pick.dataset.pick));
  else if (why) showTasteEvidence(Number(why.dataset.whyPick));
  else if (evidence) showEvidence(Number(evidence.dataset.evidence));
  else if (detail) showSimilar(Number(detail.dataset.detail));
  else if (genre) {
    taste.genre = genre.dataset.pickGenre;
    renderGenreChips();
    loadPicks();
  } else if (question) {
    $("#question").value = question.dataset.question;
    $("#question").focus();
  }
});
$("#detail-dialog").addEventListener("close", () => {
  detailRequestId++;
});
$("#close-detail").addEventListener("click", () => $("#detail-dialog").close());
$("#detail-dialog").addEventListener("click", (event) => {
  if (event.target === $("#detail-dialog")) $("#detail-dialog").close();
});
$("#start-taste").addEventListener("click", startTaste);
$("#taste-skip").addEventListener("click", () => advanceTaste(null));
$("#taste-finish").addEventListener("click", finishTaste);
$("#taste-back").addEventListener("click", () => {
  if (taste.index > 0) {
    taste.index--;
    taste.answers.length = taste.index;
    renderRound();
  }
});
/* Keyboard shortcuts while a quick-pick round is on screen. */
document.addEventListener("keydown", (event) => {
  if (state.view !== "picks" || $("#taste-quiz").hidden || event.metaKey || event.ctrlKey || event.altKey) return;
  if (event.target?.matches?.("input, textarea, select") || $("#detail-dialog").open) return;
  const options = taste.rounds[taste.index] || [];
  const number = Number(event.key);
  if (number >= 1 && number <= options.length) advanceTaste(options[number - 1].movie_id);
  else if (event.key === "s" || event.key === "S") advanceTaste(null);
  else if (event.key === "ArrowLeft") $("#taste-back").click?.();
  else return;
  event.preventDefault();
});
$("#picks-restart").addEventListener("click", () => {
  taste.requestId++;
  taste.rounds = [];
  taste.answers = [];
  taste.personal = false;
  taste.results = [];
  showPicksStage("intro");
  startTaste();
});
$("#lab-form").addEventListener("submit", (event) => {
  event.preventDefault();
  askGraph();
});
$$(".model-key").forEach((input) => input.addEventListener("input", () => syncKeys(input)));
document.addEventListener(
  "error",
  (event) => {
    if (event.target.matches?.(".poster img")) event.target.remove();
  },
  true,
);

/* ---------- Start-up ---------- */
async function loadStats() {
  try {
    const stats = await api("/api/system/status");
    $("#stat-movies").textContent = formatNumber(stats.movies);
    $("#stat-ratings").textContent = formatNumber(stats.ratings);
    $("#stat-users").textContent = formatNumber(stats.users);
    $("#stat-date").textContent = stats.as_of
      ? new Date(stats.as_of * 1000).toLocaleDateString("en-US", { month: "short", year: "numeric" })
      : "Not loaded";
    $("#health").classList.add("ready");
    state.genres = await api("/api/genres");
    $$(".genre-select").forEach((select) =>
      state.genres.forEach((genre) => {
        const option = document.createElement("option");
        option.value = genre;
        option.textContent = genre;
        select.append(option);
      }),
    );
    if (taste.personal) renderGenreChips();
  } catch (error) {
    notice("The graph database is not reachable yet. Start it with “make docker-run”, then reload. (" + error.message + ")");
  }
}
async function loadExample() {
  try {
    const result = await api("/api/movies/1/similar?limit=1");
    const top = result.items[0];
    if (!top) return;
    // Wrap the title onto at most two short lines inside the diagram box.
    const lines = [""];
    for (const word of cleanTitle(top.title).split(" ")) {
      const line = lines.at(-1);
      if (line && (line + " " + word).length > 15) lines.push(word);
      else lines[lines.length - 1] = line ? line + " " + word : word;
    }
    if (lines.length > 2) lines.splice(1, lines.length - 1, lines.slice(1).join(" ").slice(0, 14) + "…");
    $("#example-rec").innerHTML = lines.map((line, index) => `<tspan x="562" dy="${index ? 17 : 0}">${escapeText(line)}</tspan>`).join("");
    $("#example-rec").setAttribute("y", lines.length > 1 ? "70" : "78");
    $("#example-rec-label").setAttribute("y", lines.length > 1 ? "110" : "98");
    $("#example-fans").textContent = `${formatNumber(top.support)} loved both`;
    $("#graph-caption").textContent = `A real link from the graph: ${formatNumber(top.support)} MovieLens raters gave both Toy Story and ${cleanTitle(top.title)} 4★ or more.`;
  } catch {
    /* The diagram stays generic when the graph is unavailable. */
  }
}
async function loadHeroPosters() {
  try {
    const result = await api("/api/movies/trending?limit=24&metric=pagerank");
    const withPosters = result.items.filter((movie) => taste.posters[movie.movie_id]).slice(0, 9);
    $("#hero-posters").innerHTML = withPosters.map((movie) => posterArt(movie)).join("");
  } catch {
    /* The hero works without decoration. */
  }
}
function refreshPosters() {
  $$(".poster").forEach((node) => {
    const holder = node.closest("[data-pick],[data-detail]");
    const id = holder?.dataset.pick || holder?.dataset.detail;
    if (taste.posters[id] && !node.querySelector("img"))
      node.insertAdjacentHTML("afterbegin", posterImage(id, node.dataset.size));
  });
}
async function initialize() {
  setView(location.hash.slice(1), false);
  // Optional poster metadata must never block statistics, the quiz or lists.
  loadStats();
  loadExample();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch("/static/posters.json", { signal: controller.signal });
    if (response.ok) {
      taste.posters = await response.json();
      refreshPosters();
      loadHeroPosters();
    }
  } catch {
    /* Designed fallback covers remain usable. */
  } finally {
    clearTimeout(timeout);
  }
}
initialize();
