/* MovieGraph demo. All titles, scores, paths and statistics come from the API. */
"use strict";
const $ = (selector) => document.querySelector(selector);
const taste = {
  demo: false,
  rounds: [],
  answers: [],
  index: 0,
  personal: false,
  posters: {},
};
const state = {
  view: "recommendations",
  offset: 0,
  limit: 8,
  rows: [],
  loading: false,
  requestId: 0,
};
const MAX_CATALOG_OFFSET = 10000;
let detailRequestId = 0;
const palettes = [
  ["#c4cfc3", "#718b7b", "#213f37"],
  ["#e3cbb1", "#be7858", "#4f3529"],
  ["#b8c5cd", "#587582", "#203d4b"],
  ["#c5c1cf", "#79718b", "#39334c"],
  ["#ddd8b4", "#a6a16b", "#4b4a29"],
  ["#d5bcb4", "#a36c66", "#542f30"],
  ["#bacdca", "#558c86", "#1c4945"],
  ["#d4cdbf", "#9a8b6c", "#484034"],
];
const copy = {
  recommendations: [
    "For you",
    "A few stories for you",
    "Follow your taste.<br><em>Find your next story.</em>",
  ],
  discover: [
    "Taste communities",
    "People like you. Films beyond you.",
    "Shared tastes.<br><em>Unexpected discoveries.</em>",
  ],
  trending: [
    "The long view",
    "Stories that made a connection",
    "Great stories linger.<br><em>See the long view.</em>",
  ],
  catalog: [
    "Explore the catalog",
    "A whole world of stories",
    "Every film, a doorway.<br><em>Where will you go?</em>",
  ],
};
function escapeText(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
}
async function api(path, options = {}) {
  const response = await fetch(path, options);
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error("The service returned an unreadable response.");
  }
  if (!response.ok) {
    const detail = result.detail ?? result.message ?? "Request failed";
    throw new Error(
      typeof detail === "string" ? detail : JSON.stringify(detail),
    );
  }
  return result;
}
function notice(text) {
  $("#notice").textContent = text;
  $("#notice").hidden = !text;
}
const descriptions = {
  recommendations:
    "Choose films you love to get recommendations with visible reasons. Your choices stay in this tab.",
  discover:
    "Explore unseen films in an anonymous MovieLens user's strongest taste communities. This is a research demonstration.",
  trending:
    "Activity during the historical snapshot's final year. These rankings are not live trends.",
  catalog:
    "Search the complete MovieLens film catalog, filter by genre and explore similar films.",
};
async function setView(view, updateAddress = true) {
  if (!(view in copy) && view !== "ask") view = "recommendations";
  const changed = state.view !== view;
  state.view = view;
  state.requestId++;
  state.loading = false;
  if (changed) {
    state.offset = 0;
    $("#genre").value = "";
    $("#search").value = "";
    state.rows = [];
    $("#movie-grid").innerHTML = "";
    if ($("#detail-dialog").open) $("#detail-dialog").close();
  }
  if (updateAddress && location.hash !== "#" + view)
    history.pushState(null, "", "#" + view);
  document.querySelectorAll(".nav-item").forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  const home = view === "recommendations";
  const results = view !== "ask" && (!home || taste.personal || taste.demo);
  $("#welcome-screen").hidden = !home || taste.rounds.length > 0 || taste.demo;
  $("#graph-stats").hidden = !home || taste.rounds.length > 0 || taste.demo;
  $("#taste-section").hidden = !home;
  $("#start-taste").hidden = !taste.rounds.length && !taste.demo;
  $("#taste-quiz").hidden =
    !home || !taste.rounds.length || taste.personal || taste.demo;
  $("#collection").hidden = !results;
  $("#ask-screen").hidden = view !== "ask";
  $("#demo-user-control").hidden = !(
    view === "discover" ||
    (home && taste.demo)
  );
  $("#genre-control").hidden = !["catalog", "recommendations"].includes(view);
  $("#search-control").hidden = view !== "catalog";
  $("#filter-form").hidden = view === "trending";
  $("#breadcrumb").textContent =
    view === "ask" ? "Ask the graph" : copy[view][0];
  if (view !== "ask") {
    $("#collection-title").textContent =
      home && taste.demo
        ? "Anonymous user recommendations."
        : copy[view][1].replace(/\.$/, "") + ".";
    $("#page-description").textContent =
      home && taste.demo
        ? "Research demo using the selected MovieLens user, not your personal choices."
        : descriptions[view];
    $("#page-caption").textContent = home
      ? "YOUR NEXT FRAME"
      : "RESEARCH / " + copy[view][0].toUpperCase();
  }
  notice("");
  window.scrollTo({ top: 0, behavior: "instant" });
  if (results) return loadFilms();
}
window.addEventListener("hashchange", () =>
  setView(location.hash.slice(1), false),
);

function card(movie, index) {
  const palette = palettes[Math.abs(movie.movie_id) % palettes.length];
  const title = movie.title.replace(/\s*\(\d{4}\)\s*$/, "");
  const score =
    Number.isFinite(movie.score) &&
    !(taste.personal && state.view === "recommendations")
      ? movie.score.toFixed(2)
      : null;
  const activeGenre = $("#genre").value;
  const genres =
    [...(movie.genres || [])]
      .sort((a, b) =>
        a === activeGenre ? -1 : b === activeGenre ? 1 : a.localeCompare(b),
      )
      .slice(0, 2)
      .join(" / ") || "Unclassified";
  return `<article class="movie-card"><button class="movie-art variant-${movie.movie_id % 5}" data-detail="${movie.movie_id}" aria-label="Explore ${escapeText(movie.title)}" style="--poster-bg:${palette[0]};--poster-color:${palette[1]};--poster-ink:${palette[2]}">${taste.posters[movie.movie_id] ? `<img class="real-poster" src="${escapeText(taste.posters[movie.movie_id].image)}" alt="${escapeText(title)} film image" loading="lazy" referrerpolicy="no-referrer">` : ""}<span class="art-stripes"></span><span class="film-number">FRAME / ${String(index + 1 + state.offset).padStart(2, "0")}</span><span class="film-year">${movie.year || "—"}</span><span class="poster-type ${title.length > 50 ? "long-title" : ""}"><span class="poster-caption">A MOVIEGRAPH SELECTION</span>${escapeText(title)}</span></button><div class="movie-meta"><div><span class="movie-title">${escapeText(title)}</span><span class="movie-genre">${escapeText(genres)}</span></div>${score ? `<span class="movie-score">✧ ${score}</span>` : ""}</div><div class="movie-bottom"><button class="why-button" ${state.view === "recommendations" ? "data-evidence" : "data-detail"}="${movie.movie_id}">${state.view === "recommendations" ? "Why this film?" : "Follow the connection"} ↗</button><span class="support-label">${taste.personal && state.view === "recommendations" ? escapeText(movie.supporting_seeds) + " of your picks" : movie.support ? escapeText(movie.support) + " signals" : "CATALOG"}</span></div></article>`;
}
async function loadFilms() {
  const requestId = ++state.requestId;
  const view = state.view;
  const personal = taste.personal && view === "recommendations";
  const selected = taste.answers.filter((id) => id !== null);
  state.loading = true;
  $("#movie-grid").classList.add("loading");
  notice("");
  try {
    const user = Number($("#user-id").value);
    const genre = $("#genre").value;
    const q = $("#search").value.trim();
    let path;
    if (view === "catalog")
      path = `/api/movies?limit=${state.limit}&offset=${state.offset}&q=${encodeURIComponent(q)}&genre=${encodeURIComponent(genre)}`;
    else if (view === "trending")
      path = `/api/movies/trending?limit=${state.limit}&window_days=365`;
    else if (view === "discover")
      path = `/api/users/${user}/discover?limit=${state.limit}`;
    else
      path = `/api/users/${user}/recommendations?limit=${state.limit}${genre ? "&genre=" + encodeURIComponent(genre) : ""}`;
    // An absent filter must remain absent, rather than the empty string genre.
    path = path.replace(/&genre=$/, "");
    const result = personal
      ? await api("/api/taste/recommendations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            movie_ids: selected,
            genre: genre || null,
            limit: state.limit,
          }),
        })
      : await api(path);
    if (requestId !== state.requestId) return;
    state.rows = result.items;
    $("#show-more").hidden =
      view !== "catalog" ||
      result.items.length < state.limit ||
      state.offset + state.limit > MAX_CATALOG_OFFSET;
    $("#show-previous").hidden = view !== "catalog" || state.offset === 0;
    $("#movie-grid").innerHTML = result.items.length
      ? result.items.map(card).join("")
      : '<div class="empty-state">No matching films. Try another genre or change your selections.</div>';
    const method = (result.method || "catalog").replaceAll("_", " ");
    $("#method-note").textContent = personal
      ? "Based on your choices"
      : method.charAt(0).toUpperCase() + method.slice(1);
    $("#result-note").textContent =
      `${result.items.length} films · ${view === "catalog" ? "catalog snapshot" : view === "trending" ? "historical snapshot" : "user " + user + " · " + method}`;
    if (personal) {
      $("#collection-title").textContent = "Your next watch.";
      $("#result-note").textContent =
        `${result.items.length} recommendations · based on ${selected.length} ${selected.length === 1 ? "film" : "films"} you chose`;
    }
    if (result.fallback_reason) notice("Fallback: " + result.fallback_reason);
  } catch (error) {
    if (requestId !== state.requestId) return;
    notice(error.message);
    $("#movie-grid").innerHTML =
      '<div class="empty-state">We couldn’t follow that connection.<br><small>Check the graph service or try another user.</small></div>';
    $("#result-note").textContent = "Request could not be completed";
  } finally {
    if (requestId === state.requestId) {
      state.loading = false;
      $("#movie-grid").classList.remove("loading");
    }
  }
}
async function loadStats() {
  try {
    const stats = await api("/api/system/status");
    for (const field of ["movies", "ratings", "users"])
      $("#stat-" + field).textContent = new Intl.NumberFormat("en-US").format(
        stats[field],
      );
    $("#snapshot-date").textContent = stats.as_of
      ? new Date(stats.as_of * 1000).toLocaleDateString("en-US", {
          month: "short",
          year: "numeric",
        })
      : "Not seeded";
    document.querySelector(".health-dot").classList.add("ready");
    const genres = await api("/api/genres");
    genres.forEach((genre) => {
      const option = document.createElement("option");
      option.value = genre;
      option.textContent = genre;
      $("#genre").append(option);
    });
  } catch (error) {
    notice(error.message);
    $("#snapshot-date").textContent = "Graph unavailable";
  }
}
function openDetail(html) {
  const requestId = ++detailRequestId;
  $("#detail-content").innerHTML = html;
  if (!$("#detail-dialog").open) $("#detail-dialog").showModal();
  return requestId;
}
function currentDetail(requestId) {
  return requestId === detailRequestId && $("#detail-dialog").open;
}
async function showSimilar(movieId) {
  if (taste.personal && state.view === "recommendations") {
    showTasteEvidence(movieId);
    return;
  }
  const film = state.rows.find((row) => row.movie_id === movieId);
  const heading = `<div class="detail-label">FOLLOW THE CONNECTION</div><h2 class="detail-heading">${escapeText(film?.title || "Movie " + movieId)}</h2>`;
  const requestId = openDetail(
    heading +
      '<p class="detail-copy">Finding films with overlapping positive raters…</p>',
  );
  try {
    const result = await api(`/api/movies/${movieId}/similar?limit=6`);
    if (!currentDetail(requestId)) return;
    $("#detail-content").innerHTML =
      heading +
      `<div class="similar-list">${result.items.map((row) => `<div class="similar-item">${escapeText(row.title)}<small>Similarity ${row.score.toFixed(3)} · ${row.support} shared positive raters</small></div>`).join("") || "<p>No supported similarity neighbors in this snapshot.</p>"}</div><p class="detail-copy">Shrunk Jaccard similarity · scores are not probabilities.</p><button class="primary-link" data-evidence="${movieId}">Why for demo user ${escapeText($("#user-id").value)}? ↗</button>`;
  } catch (error) {
    if (currentDetail(requestId))
      $("#detail-content").innerHTML =
        heading + `<p class="error-text">${escapeText(error.message)}</p>`;
  }
}
async function showEvidence(movieId) {
  if (taste.personal && state.view === "recommendations") {
    showTasteEvidence(movieId);
    return;
  }
  const user = Number($("#user-id").value);
  const requestId = openDetail(
    '<div class="detail-label">VISIBLE REASONS</div><h2 class="detail-heading">Every recommendation has a path.</h2><p class="detail-copy">Following the graph…</p>',
  );
  try {
    const result = await api(
      `/api/users/${user}/recommendations/${movieId}/explanation`,
    );
    if (!currentDetail(requestId)) return;
    $("#detail-content").innerHTML =
      `<div class="detail-label">EVIDENCE / USER ${user} → FILM ${movieId}</div><h2 class="detail-heading">A reason, not a guess.</h2><p class="detail-copy">${escapeText(result.explanation)}</p>${result.evidence.map((evidence) => `<div class="evidence-path"><h4>${escapeText(evidence.path[2].title)}</h4><div class="path-nodes"><span class="path-node">User ${user}</span><span class="path-arrow">RATED →</span><span class="path-node">Movie ${evidence.path[2].movie_id}</span><span class="path-arrow">SIMILAR_TO →</span><span class="path-node">Movie ${movieId}</span></div><div class="evidence-stats"><span>Rating ${evidence.source_rating}</span><span>Similarity ${evidence.similarity.toFixed(3)}</span><span>${evidence.support} shared raters</span><span>Contribution ${evidence.contribution.toFixed(3)}</span></div></div>`).join("")}<p class="detail-copy">Observed ratings + derived similarity. ${escapeText(result.note)}<br>Run: ${escapeText(result.analytics_run_id || "none")}</p>`;
  } catch (error) {
    if (currentDetail(requestId))
      $("#detail-content").innerHTML =
        `<h2 class="detail-heading">Connection unavailable.</h2><p class="error-text">${escapeText(error.message)}</p>`;
  }
}
async function askGraph() {
  const question = $("#question").value.trim();
  const key = $("#api-key").value.trim();
  if (!question || !key) {
    $("#ask-result").hidden = false;
    $("#ask-result").textContent =
      "Add your local access key and a question first.";
    return;
  }
  const button = $("#ask-button");
  button.disabled = true;
  button.textContent = "Following the graph…";
  $("#ask-result").hidden = false;
  $("#ask-result").textContent =
    "The local model is interpreting your question. No model-generated query will run unchecked.";
  try {
    const result = await api("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": key },
      body: JSON.stringify({
        question,
        user_id: Number($("#user-id").value),
        limit: 10,
      }),
    });
    $("#ask-result").innerHTML =
      `<strong>${escapeText(result.explanation)}</strong><br>${escapeText(result.warnings.join(" "))}<details><summary>View the validated Cypher and graph evidence ↗</summary><pre>${escapeText(result.compiled_cypher)}</pre><pre>${escapeText(JSON.stringify(result.rows, null, 2))}</pre></details>`;
  } catch (error) {
    $("#ask-result").innerHTML =
      `<span class="error-text">${escapeText(error.message)}</span>`;
  } finally {
    button.disabled = false;
    button.innerHTML = "Follow the evidence <span>↗</span>";
  }
}
document
  .querySelectorAll("[data-view]")
  .forEach((button) =>
    button.addEventListener("click", () => setView(button.dataset.view)),
  );
$("#filter-form").addEventListener("submit", (event) => {
  event.preventDefault();
  state.offset = 0;
  loadFilms();
});
$("#show-previous").addEventListener("click", () => {
  if (state.view !== "catalog" || state.loading) return;
  state.offset = Math.max(0, state.offset - state.limit);
  loadFilms();
});
$("#show-more").addEventListener("click", () => {
  if (
    state.view !== "catalog" ||
    state.loading ||
    state.offset + state.limit > MAX_CATALOG_OFFSET
  )
    return;
  state.offset += state.limit;
  loadFilms();
});
document.addEventListener("click", (event) => {
  const evidence = event.target.closest("[data-evidence]");
  const detail = event.target.closest("[data-detail]");
  if (evidence) showEvidence(Number(evidence.dataset.evidence));
  else if (detail) showSimilar(Number(detail.dataset.detail));
});
$("#detail-dialog").addEventListener("close", () => {
  detailRequestId++;
});
$("#close-detail").addEventListener("click", () => $("#detail-dialog").close());
$("#detail-dialog").addEventListener("click", (event) => {
  if (event.target === $("#detail-dialog")) $("#detail-dialog").close();
});
$("#ask-button").addEventListener("click", askGraph);
document.querySelectorAll("[data-question]").forEach((button) =>
  button.addEventListener("click", () => {
    $("#question").value = button.dataset.question;
    $("#question").focus();
  }),
);
function showTasteEvidence(movieId) {
  const movie = state.rows.find((row) => row.movie_id === movieId);
  if (!movie) return;
  openDetail(
    `<div class="detail-label">YOUR CHOICES → GRAPH CONNECTIONS → THIS FILM</div><h2 class="detail-heading">Why ${escapeText(movie.title)}?</h2><p class="detail-copy">You selected these films. MovieLens viewers who liked them also liked this recommendation.</p>${(
      movie.reasons || []
    )
      .slice(0, 3)
      .map(
        (reason) =>
          `<div class="evidence-path"><h4>Because you chose ${escapeText(reason.seed_title)}</h4><p>${reason.support} shared positive raters connect the two films.</p><small>Graph similarity: ${reason.similarity.toFixed(3)}</small></div>`,
      )
      .join(
        "",
      )}${taste.posters[movieId] ? `<p class="detail-copy"><a href="${escapeText(taste.posters[movieId].source)}" target="_blank" rel="noopener noreferrer">Film image source: ${escapeText(taste.posters[movieId].page_title)} on TMDB ↗</a></p>` : ""}<p class="detail-copy">The score combines graph similarities across all your selections. It is not a star rating or a probability. Unchosen films were not treated as dislikes.</p>`,
  );
}
function renderRound() {
  $("#taste-back").disabled = taste.index === 0;
  $("#round-label").textContent =
    `Round ${taste.index + 1} of 10 · ${taste.answers.filter((id) => id !== null).length} favourites selected`;
  $("#round-progress").value = taste.index;
  $("#taste-options").innerHTML = taste.rounds[taste.index]
    .map((movie, index) =>
      card(movie, index)
        .replaceAll("data-detail=", "data-pick=")
        .replaceAll('aria-label="Explore ', 'aria-label="Choose ')
        .replace(
          /<div class="movie-bottom">[\s\S]*?<\/div><\/article>/,
          "</article>",
        ),
    )
    .join("");
  $("#taste-status").textContent =
    "Pick one favourite, or skip. No account needed.";
}
async function startTaste() {
  const button = $("#start-taste");
  if (button.disabled) return;
  button.disabled = true;
  try {
    const seed = crypto.getRandomValues(new Uint32Array(1))[0] % 2147483647;
    const result = await api(`/api/taste/rounds?seed=${seed}`);
    taste.rounds = result.rounds;
    taste.answers = [];
    taste.index = 0;
    taste.personal = false;
    taste.demo = false;
    state.requestId++;
    state.loading = false;
    $("#movie-grid").classList.remove("loading");
    $("#collection").hidden = true;
    $("#taste-quiz").hidden = false;
    $("#start-taste").textContent = "Start again ↻";
    renderRound();
    await setView(state.view, false);
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
    return;
  }
  if (!taste.answers.some((id) => id !== null)) {
    $("#taste-status").textContent =
      "Choose at least one film to get personal recommendations. Go back or start again.";
    return;
  }
  taste.personal = true;
  $("#collection").hidden = false;
  $("#taste-quiz").hidden = true;
  $("#taste-status").textContent =
    "Your picks are ready. Your selections stay in this tab; no account or source ratings are created.";
  $("#demo-user-control").hidden = true;
  $("#genre").value = "";
  $("#search").value = "";
  await setView("recommendations");
}
$("#start-taste").addEventListener("click", startTaste);
$("#hero-start").addEventListener("click", startTaste);
$("#taste-skip").addEventListener("click", () => advanceTaste(null));
$("#taste-back").addEventListener("click", () => {
  if (taste.index > 0) {
    taste.index--;
    taste.answers.length = taste.index;
    renderRound();
  }
});
$("#demo-mode").addEventListener("click", () => {
  taste.personal = false;
  taste.demo = true;
  $("#demo-user-control").hidden = false;
  $("#taste-status").textContent =
    "Research demo: recommendations now use the selected anonymous MovieLens user.";
  setView("recommendations");
});
document.addEventListener("click", (event) => {
  const pick = event.target.closest("[data-pick]");
  if (pick) advanceTaste(Number(pick.dataset.pick));
});
document.addEventListener(
  "error",
  (event) => {
    if (event.target.matches?.(".real-poster")) event.target.remove();
  },
  true,
);
async function initialize() {
  setView(location.hash.slice(1), false);
  // Optional decoration must not block graph statistics or the preference quiz.
  loadStats();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch("/static/posters.json", {
      signal: controller.signal,
    });
    if (response.ok) {
      taste.posters = await response.json();
      document.querySelectorAll(".movie-art").forEach((button) => {
        const id = button.dataset.detail || button.dataset.pick;
        const poster = taste.posters[id];
        if (poster && !button.querySelector(".real-poster")) {
          const title = button
            .getAttribute("aria-label")
            .replace(/^(Choose|Explore) /, "");
          button.insertAdjacentHTML(
            "afterbegin",
            `<img class="real-poster" src="${escapeText(poster.image)}" alt="${escapeText(title)} film image" loading="lazy" referrerpolicy="no-referrer">`,
          );
        }
      });
    }
  } catch {
    /* Designed covers remain usable without poster metadata. */
  } finally {
    clearTimeout(timeout);
  }
}
initialize();
