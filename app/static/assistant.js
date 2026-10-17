/* Conversation state is ephemeral; film lists always come from the graph, never from the model. */
"use strict";
const assistant = {
  seed: 42,
  choices: [],
  current: null,
  busy: false,
  generation: 0,
  pending: null,
};
function assistantStatus(text) {
  $("#assistant-status").textContent = text;
}
function assistantBusy(busy) {
  assistant.busy = busy;
  $$("#screen-assistant button, #assistant-message").forEach((node) => {
    node.disabled = busy;
  });
  $("#assistant-send").textContent = busy ? "Thinking…" : "Send";
  $("#assistant-transcript").classList.toggle("typing", busy);
}
function assistantMessage(role, text) {
  $("#assistant-transcript").insertAdjacentHTML(
    "beforeend",
    `<div class="bubble ${role === "visitor" ? "me" : "bot"}"><span class="who">${role === "visitor" ? "You" : "Assistant"}</span><p>${escapeText(text)}</p></div>`,
  );
  $("#assistant-transcript").scrollTop = $("#assistant-transcript").scrollHeight;
}
function assistantCard(movie, choose) {
  const title = escapeText(cleanTitle(movie.title));
  if (choose)
    return `<button class="film-card pickable" data-assistant-pick="${movie.movie_id}" aria-label="Choose ${title}">${posterArt(movie)}<span class="film-info"><span class="film-title">${title}</span><span class="film-meta">${movie.year || ""} ${genreLine(movie, 2)}</span></span><span class="pick-badge" aria-hidden="true">I like this</span></button>`;
  return `<article class="film-card"><button class="poster-button" data-assistant-evidence="${movie.movie_id}" aria-label="Why ${title}">${posterArt(movie)}</button><div class="film-info"><span class="film-title">${title}</span><span class="film-meta">${movie.year || ""} ${genreLine(movie, 2)}</span></div><div class="film-foot"><span class="signal">Linked to ${escapeText(movie.supporting_seeds)} of your picks</span><button class="link" data-assistant-evidence="${movie.movie_id}">Why? →</button></div></article>`;
}
function renderAssistant(result) {
  const choosing = result.stage === "choosing";
  const movies = choosing ? result.options : result.items;
  const picked = result.selected_movie_ids.length;
  $("#assistant-progress").textContent = choosing
    ? `Round ${result.round} of 10 · ${picked} ${picked === 1 ? "favourite" : "favourites"}`
    : `${picked} ${picked === 1 ? "favourite" : "favourites"} chosen`;
  $("#assistant-back").hidden = !assistant.choices.length;
  const anchor = result.selected_movies?.find((movie) => movie.movie_id === result.plan.anchor_movie_id);
  $("#assistant-filters").innerHTML = choosing
    ? `<span class="chip static">Choosing favourites</span>`
    : `<span class="chip static">${escapeText(result.plan.genre || "All genres")}</span><span class="chip static">${result.plan.algorithm === "similar_movies" ? "Like " + escapeText(cleanTitle(anchor?.title || "one favourite")) : "Based on all favourites"}</span>`;
  const heading = choosing
    ? "Which one do you like most?"
    : result.stage === "recommendations"
      ? "Films for you"
      : "The assistant needs a clearer request";
  const help = choosing
    ? "Click a film, or skip below the chat. Films you don’t pick are not counted as dislikes."
    : result.stage === "recommendations"
      ? "Strongest connections first. Click a poster to see why."
      : "Try one of the suggestions, or name a genre or one of your favourites.";
  $("#assistant-results").innerHTML =
    `<div class="panel-head"><h2>${heading}</h2><p class="muted">${escapeText(help)}</p></div>` +
    `<div class="film-grid ${choosing ? "five compact" : "compact"}">${movies.map((movie) => assistantCard(movie, choosing)).join("")}</div>` +
    (choosing ? '<button id="assistant-skip" class="button subtle">I don’t know these — skip →</button>' : "") +
    (result.stage === "recommendations" && !movies.length
      ? '<div class="empty">No connected films for this request. Try “All genres” or choose more favourites. Nothing was invented.</div>'
      : "");
  $("#assistant-plan").textContent = JSON.stringify(
    {
      decision: result.plan,
      method: result.method || "choosing favourites",
      analytics_run_id: result.analytics_run_id,
      trace_id: result.trace_id,
    },
    null,
    2,
  );
}
async function assistantTurn(message, event = "message", choices = assistant.choices) {
  if (assistant.busy) return;
  const key = $("#assistant-key").value.trim() || $("#api-key").value.trim();
  if (!key) {
    assistantStatus("Paste your local access key first. Quick picks works without a model or key.");
    return;
  }
  const generation = ++assistant.generation;
  const plan = assistant.current?.plan;
  const payload = {
    seed: assistant.seed,
    choices: [...choices],
    message,
    event,
    genre: plan?.genre || null,
    algorithm: plan?.algorithm || "graph_affinity",
    anchor_movie_id: plan?.anchor_movie_id || null,
  };
  // Going back can remove the reference film; the next plan must resolve it again.
  if (payload.anchor_movie_id !== null && !payload.choices.includes(payload.anchor_movie_id)) {
    payload.anchor_movie_id = null;
    payload.algorithm = "graph_affinity";
  }
  assistant.pending = { message, event, choices: [...choices] };
  assistantBusy(true);
  assistantStatus("The assistant is thinking. Your choices are kept…");
  $("#assistant-retry").hidden = true;
  try {
    const result = await api("/api/assistant/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": key },
      body: JSON.stringify(payload),
    });
    if (generation !== assistant.generation) return;
    assistant.choices = [...choices];
    assistant.current = result;
    assistant.pending = null;
    $("#assistant-connect").hidden = true;
    $("#assistant-workspace").hidden = false;
    if (message) assistantMessage("visitor", message);
    if (event === "start")
      assistantMessage(
        "model",
        "Hi! I’ll show you five films per round for ten rounds. Click the one you like most, or skip. After that, ask me for changes like “only comedies” or “more like <one of your picks>”.",
      );
    assistantMessage("model", result.message);
    renderAssistant(result);
    $("#assistant-message").value = "";
    assistantStatus(
      result.stage === "recommendations"
        ? `${result.items.length} films found in the graph. Ask for a change any time.`
        : "",
    );
  } catch (error) {
    if (generation !== assistant.generation) return;
    assistantStatus(
      error.status === 401
        ? "That access key was not accepted. Check APP_API_KEY in your .env file."
        : error.message,
    );
    $("#assistant-retry").hidden = false;
  } finally {
    if (generation === assistant.generation) assistantBusy(false);
  }
}
function assistantEvidence(movieId) {
  const movie = assistant.current?.items.find((row) => row.movie_id === movieId);
  if (!movie) return;
  openDetail(
    dialogHead(movie, movieId, "Why this film?") +
      `<p>Because you picked:</p>${reasonsHTML(movie)}<p class="small muted">“Loved” means rated 4★ or more by the same MovieLens rater. These are recorded connections, not a guarantee. Your choices did not create any MovieLens ratings.</p>`,
  );
}
$("#assistant-connect-form").addEventListener("submit", (event) => {
  event.preventDefault();
  assistant.seed = crypto.getRandomValues(new Uint32Array(1))[0] % 2147483647;
  assistantTurn("", "start", []);
});
$("#assistant-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const text = $("#assistant-message").value.trim();
  if (text) assistantTurn(text);
});
$("#assistant-back").addEventListener("click", () =>
  assistantTurn("Let me choose the previous round again.", "back", assistant.choices.slice(0, -1)),
);
$("#assistant-reset").addEventListener("click", () => {
  assistant.generation++;
  assistant.choices = [];
  assistant.current = null;
  assistant.pending = null;
  assistantBusy(false);
  $("#assistant-transcript").innerHTML = "";
  $("#assistant-results").innerHTML = "";
  $("#assistant-filters").innerHTML = "";
  $("#assistant-connect").hidden = false;
  $("#assistant-workspace").hidden = true;
  $("#assistant-retry").hidden = true;
  assistantStatus("");
});
$("#assistant-retry").addEventListener("click", () => {
  const pending = assistant.pending;
  if (pending) assistantTurn(pending.message, pending.event, pending.choices);
});
document.addEventListener("click", (event) => {
  if (!event.target.closest) return;
  const pick = event.target.closest("[data-assistant-pick]");
  const evidence = event.target.closest("[data-assistant-evidence]");
  const suggestion = event.target.closest("[data-assistant-message]");
  const skip = event.target.closest("#assistant-skip");
  if (pick && assistant.current?.stage === "choosing" && !assistant.busy) {
    const id = Number(pick.dataset.assistantPick);
    const movie = assistant.current.options.find((row) => row.movie_id === id);
    if (movie) assistantTurn(`I choose ${cleanTitle(movie.title)}.`, "pick", [...assistant.choices, id]);
  } else if (skip && !assistant.busy)
    assistantTurn("I don’t know these films — skip this round.", "pick", [...assistant.choices, null]);
  else if (evidence) assistantEvidence(Number(evidence.dataset.assistantEvidence));
  else if (suggestion) assistantTurn(suggestion.dataset.assistantMessage);
});
