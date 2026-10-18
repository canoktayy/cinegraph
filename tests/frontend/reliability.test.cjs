/* Behavioral regression tests for delayed browser requests; no browser/network dependencies. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const vm = require("node:vm");
const source = readFileSync("app/static/app.js", "utf8");
const assistantSource = readFileSync("app/static/assistant.js", "utf8");
const SCREENS = ["home", "picks", "assistant", "catalog", "top", "users", "lab"];
const tick = () => new Promise((resolve) => setImmediate(resolve));
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
};
const response = (data, ok = true, status = ok ? 200 : 422) => ({
  ok,
  status,
  json: async () => data,
});
class Element {
  constructor() {
    this.value = "";
    this.hidden = false;
    this.disabled = false;
    this.innerHTML = "";
    this.textContent = "";
    this.open = false;
    this.dataset = {};
    this.events = {};
    this.style = {};
    this.classList = { add() {}, remove() {}, toggle() {}, contains: () => false };
  }
  addEventListener(name, fn) {
    (this.events[name] ??= []).push(fn);
  }
  setAttribute() {}
  append() {}
  focus() {}
  insertAdjacentHTML(_where, html) {
    this.innerHTML += html;
  }
  showModal() {
    this.open = true;
  }
  close() {
    this.open = false;
    for (const listener of this.events.close ?? []) listener({ target: this });
  }
}
function page({ posters = Promise.resolve(response({})) } = {}) {
  const nodes = new Map();
  const requests = [];
  const bodies = new Map();
  const headers = new Map();
  const pending = new Map();
  const documentEvents = {};
  const element = (selector) => {
    if (!nodes.has(selector)) nodes.set(selector, new Element());
    return nodes.get(selector);
  };
  const screens = SCREENS.map((name) => {
    const node = element("#screen-" + name);
    node.dataset.screen = name;
    return node;
  });
  element("#user-id").value = "42";
  element("#user-mode").value = "recommendations";
  const context = vm.createContext({
    console,
    setTimeout,
    clearTimeout,
    AbortController,
    Intl,
    crypto: {
      getRandomValues(array) {
        array[0] = 42;
        return array;
      },
    },
    location: { hash: "" },
    history: { pushState() {} },
    window: { addEventListener() {}, scrollTo() {} },
    document: {
      querySelector: element,
      querySelectorAll: (selector) =>
        selector === "[data-screen]" ? screens : selector === "[data-model-status]" ? [element("[data-model-status]")] : [],
      addEventListener(name, fn) {
        (documentEvents[name] ??= []).push(fn);
      },
      createElement: () => new Element(),
    },
    fetch: (path, options = {}) => {
      requests.push(path);
      bodies.set(path, options.body);
      headers.set(path, options.headers);
      if (path === "/static/posters.json") return posters;
      if (path === "/api/system/status")
        return Promise.resolve(response({ movies: 10, ratings: 20, users: 3 }));
      if (path === "/api/genres") return Promise.resolve(response(["Comedy", "Drama"]));
      const request = deferred();
      pending.set(path, request);
      return request.promise;
    },
  });
  vm.runInContext(source, context);
  return {
    element,
    requests,
    bodies,
    headers,
    pending,
    run: (code) => vm.runInContext(code, context),
    key: (key, target = { matches: () => false }) => {
      let prevented = false;
      for (const listener of documentEvents.keydown ?? [])
        listener({ key, target, preventDefault: () => (prevented = true) });
      return prevented;
    },
  };
}
const item = (title, id) => ({
  movie_id: id,
  title,
  year: 2000,
  genres: ["Drama"],
  score: 0.3,
  support: 5,
  supporting_seeds: 1,
  reasons: [{ seed_id: 1, seed_title: "Seed (1999)", similarity: 0.2, support: 9 }],
});
const CATALOG = "/api/movies?limit=12&offset=0&q=";
const TOP = "/api/movies/trending?limit=20&metric=rating&window_days=365";

test("a slow catalog response cannot replace the newer ranking view", async () => {
  const browser = page();
  await tick();
  const old = browser.run("setView('catalog')");
  const latest = browser.run("setView('top')");
  const ranking = browser.pending.get(TOP);
  assert.ok(ranking, "the latest navigation must start its own request");
  ranking.resolve(response({ items: [item("NEW RANKING", 2)], method: "historical_activity" }));
  await latest;
  browser.pending.get(CATALOG).resolve(response({ items: [item("OLD CATALOG", 1)] }));
  await old;
  assert.match(browser.element("#top-grid").innerHTML, /NEW RANKING/);
  assert.doesNotMatch(browser.element("#catalog-grid").innerHTML, /OLD CATALOG/);
  assert.equal(browser.run("state.view"), "top");
});

test("a late film-detail result cannot append to a different film", async () => {
  const browser = page();
  await tick();
  const old = browser.run("showSimilar(1)");
  const latest = browser.run("showSimilar(2)");
  browser.pending.get("/api/movies/2/similar?limit=8").resolve(response({ items: [item("SECOND FILM RESULT", 3)] }));
  await latest;
  browser.pending.get("/api/movies/1/similar?limit=8").resolve(response({ items: [item("FIRST FILM RESULT", 4)] }));
  await old;
  const html = browser.element("#detail-content").innerHTML;
  assert.match(html, /SECOND FILM RESULT/);
  assert.doesNotMatch(html, /FIRST FILM RESULT/);
  assert.doesNotMatch(html, /Finding films/);
});

test("a failed old detail request cannot contaminate a newer dialog", async () => {
  const browser = page();
  await tick();
  const old = browser.run("showSimilar(1)");
  const latest = browser.run("showSimilar(2)");
  browser.pending.get("/api/movies/2/similar?limit=8").resolve(response({ items: [item("CURRENT FILM", 3)] }));
  await latest;
  browser.pending.get("/api/movies/1/similar?limit=8").resolve(response({ detail: "OLD REQUEST FAILED" }, false));
  await old;
  assert.doesNotMatch(browser.element("#detail-content").innerHTML, /OLD REQUEST FAILED/);
});

test("closing a dialog invalidates a pending detail response", async () => {
  const browser = page();
  await tick();
  const request = browser.run("showSimilar(1)");
  browser.element("#detail-dialog").close();
  browser.pending.get("/api/movies/1/similar?limit=8").resolve(response({ items: [item("LATE RESULT", 2)] }));
  await request;
  assert.doesNotMatch(browser.element("#detail-content").innerHTML, /LATE RESULT/);
});

test("optional poster metadata does not block graph initialization", async () => {
  const posters = deferred();
  const browser = page({ posters: posters.promise });
  await tick();
  assert.ok(browser.requests.includes("/api/system/status"));
  posters.resolve(response({}));
  await tick();
});

test("catalog pagination continues past 1,000 instead of wrapping to page one", async () => {
  const browser = page();
  await tick();
  browser.run("state.view='catalog';state.offset=1000");
  browser.element("#show-more").events.click[0]();
  const path = "/api/movies?limit=12&offset=1012&q=";
  assert.ok(browser.requests.includes(path));
  browser.pending.get(path).resolve(response({ items: [] }));
  await tick();
});

test("an obsolete list failure cannot replace a successful newer view", async () => {
  const browser = page();
  await tick();
  const old = browser.run("setView('catalog')");
  const current = browser.run("setView('top')");
  browser.pending.get(TOP).resolve(response({ items: [item("CURRENT RESULTS", 2)] }));
  await current;
  browser.pending.get(CATALOG).resolve(response({ detail: "OBSOLETE ERROR" }, false));
  await old;
  assert.match(browser.element("#top-grid").innerHTML, /CURRENT RESULTS/);
  assert.doesNotMatch(browser.element("#notice").textContent, /OBSOLETE ERROR/);
});

test("navigation shows exactly one screen and keeps quick-pick choices", async () => {
  const browser = page();
  await tick();
  const visible = () => SCREENS.filter((name) => !browser.element("#screen-" + name).hidden);
  assert.deepEqual(visible(), ["home"]);
  browser.run("taste.rounds = [[{movie_id:1,title:'One'}]]; taste.answers=[1]");
  const catalog = browser.run("setView('catalog')");
  assert.deepEqual(visible(), ["catalog"]);
  browser.pending.get(CATALOG).resolve(response({ items: [] }));
  await catalog;
  await browser.run("setView('lab')");
  assert.deepEqual(visible(), ["lab"]);
  await browser.run("setView('picks')");
  assert.deepEqual(visible(), ["picks"]);
  assert.equal(browser.run("taste.answers[0]"), 1);
  await browser.run("setView('not-a-page')");
  assert.deepEqual(visible(), ["home"]);
});

test("leaving a pending list for the query lab invalidates its response", async () => {
  const browser = page();
  const catalog = browser.run("setView('catalog')");
  await browser.run("setView('lab')");
  browser.pending.get(CATALOG).resolve(response({ items: [item("OBSOLETE", 1)] }));
  await catalog;
  assert.doesNotMatch(browser.element("#catalog-grid").innerHTML, /OBSOLETE/);
  assert.equal(browser.element("#screen-catalog").hidden, true);
});

test("a delayed quiz start cannot move the visitor away from the current screen", async () => {
  const browser = page();
  const quiz = browser.run("startTaste()");
  await browser.run("setView('lab')");
  browser.pending.get("/api/taste/rounds?seed=42").resolve(response({ rounds: [[item("FILM", 1)]] }));
  await quiz;
  assert.equal(browser.element("#screen-lab").hidden, false);
  assert.equal(browser.element("#screen-picks").hidden, true);
  assert.equal(browser.run("state.view"), "lab");
  assert.equal(browser.element("#taste-quiz").hidden, false, "the quiz is ready when the visitor returns");
});

test("finishing early without a favourite never requests recommendations", async () => {
  const browser = page();
  await tick();
  browser.run("taste.rounds=[[{movie_id:1,title:'One'}],[{movie_id:2,title:'Two'}]]; taste.answers=[null]");
  await browser.run("finishTaste()");
  assert.ok(!browser.requests.includes("/api/taste/recommendations"));
  assert.match(browser.element("#round-picks").textContent, /at least one/);
});

test("quick-pick results post only real selections and re-query a chosen genre", async () => {
  const browser = page();
  await tick();
  browser.run("taste.rounds=[[{movie_id:1,title:'One'}],[{movie_id:2,title:'Two'}]]; taste.answers=[1,null]");
  const finish = browser.run("finishTaste()");
  await tick();
  const first = JSON.parse(browser.bodies.get("/api/taste/recommendations"));
  assert.deepEqual(first.movie_ids, [1]);
  assert.equal(first.genre, null);
  browser.pending.get("/api/taste/recommendations").resolve(response({ items: [item("<b>Match</b>", 5)] }));
  await finish;
  assert.match(browser.element("#picks-grid").innerHTML, /&lt;b&gt;Match/);
  assert.equal(browser.element("#picks-results").hidden, false);
  browser.run("taste.genre='Comedy'");
  const filtered = browser.run("loadPicks()");
  await tick();
  assert.equal(JSON.parse(browser.bodies.get("/api/taste/recommendations")).genre, "Comedy");
  browser.pending.get("/api/taste/recommendations").resolve(response({ items: [] }));
  await filtered;
  assert.match(browser.element("#picks-grid").innerHTML, /No Comedy films/);
});

test("MovieLens titles are shown in natural reading order", () => {
  const browser = page();
  assert.equal(browser.run("cleanTitle('Godfather, The (1972)')"), "The Godfather");
  assert.equal(browser.run("cleanTitle('Seven (a.k.a. Se7en) (1995)')"), "Seven");
  assert.equal(browser.run("cleanTitle(\"Femme Nikita, La (Nikita) (1990)\")"), "La Femme Nikita");
  assert.equal(browser.run("cleanTitle('Toy Story (1995)')"), "Toy Story");
});

test("the query lab shows a guardrail rejection without database results", async () => {
  const browser = page();
  await tick();
  browser.element("#question").value = "DELETE all nodes";
  const ask = browser.run("askGraph()");
  browser.pending
    .get("/api/ask")
    .resolve(response({ detail: { code: "unsafe_request", message: "Only bounded catalog read queries are allowed" } }, false, 422));
  await ask;
  const html = browser.element("#ask-result").innerHTML;
  assert.match(html, /Rejected by a guardrail/);
  assert.match(html, /HTTP 422/);
  assert.doesNotMatch(html, /Results from Neo4j/);
});

function conversationPage() {
  const browser = page();
  browser.run(assistantSource);
  browser.element("#assistant-key").value = "local-test-key";
  return browser;
}
const assistantResult = (stage = "choosing") => ({
  stage,
  message: "Choose a favourite.",
  options: [item("Choice", 1)],
  items: [],
  round: 1,
  selected_movie_ids: [],
  selected_movies: [],
  plan: { algorithm: "graph_affinity", genre: null, anchor_movie_id: null },
  analytics_run_id: "test-run",
  trace_id: "test-trace",
});
test("failed assistant choices are retained for retry rather than silently advanced", async () => {
  const browser = conversationPage();
  const request = browser.run("assistantTurn('I choose Choice.', 'pick', [1])");
  browser.pending.get("/api/assistant/turn").resolve(response({ detail: "Model unavailable" }, false, 503));
  await request;
  assert.equal(browser.run("assistant.choices.length"), 0);
  assert.equal(browser.run("assistant.pending.choices[0]"), 1);
  assert.equal(browser.element("#assistant-retry").hidden, false);
  assert.match(browser.element("#assistant-status").textContent, /Model unavailable/);
});
test("assistant card input cannot send duplicate turns while a model call is pending", async () => {
  const browser = conversationPage();
  const first = browser.run("assistantTurn('', 'start', [])");
  await browser.run("assistantTurn('duplicate')");
  assert.equal(browser.requests.filter((path) => path === "/api/assistant/turn").length, 1);
  browser.pending.get("/api/assistant/turn").resolve(response(assistantResult()));
  await first;
  assert.equal(browser.element("#assistant-workspace").hidden, false);
});
test("assistant success escapes model text and can finish after navigation without changing the screen", async () => {
  const browser = conversationPage();
  const first = browser.run("assistantTurn('', 'start', [])");
  await browser.run("setView('lab')");
  browser.pending
    .get("/api/assistant/turn")
    .resolve(response({ ...assistantResult(), message: "<script>untrusted</script>" }));
  await first;
  assert.equal(browser.run("state.view"), "lab");
  assert.equal(browser.element("#screen-assistant").hidden, true);
  assert.doesNotMatch(browser.element("#assistant-transcript").innerHTML, /<script>/);
  assert.match(browser.element("#assistant-transcript").innerHTML, /&lt;script&gt;/);
});
test("a server that requires a key reveals the key fields and explains where to find it", async () => {
  const browser = conversationPage();
  browser.element("#assistant-key-field").hidden = true;
  browser.element("#lab-key-field").hidden = true;
  const request = browser.run("assistantTurn('', 'start', [])");
  browser.pending.get("/api/assistant/turn").resolve(response({ detail: "A valid X-API-Key is required" }, false, 401));
  await request;
  assert.match(browser.element("#assistant-status").textContent, /APP_API_KEY/);
  assert.match(browser.element("#assistant-connect-status").textContent, /APP_API_KEY/, "visible before the chat opens");
  assert.equal(browser.element("#assistant-key-field").hidden, false);
  assert.equal(browser.element("#lab-key-field").hidden, false);
});
test("the assistant works without any key on a local install", async () => {
  const browser = page();
  browser.run(assistantSource);
  const request = browser.run("assistantTurn('', 'start', [])");
  assert.ok(browser.requests.includes("/api/assistant/turn"), "no key is required before sending");
  assert.equal(browser.headers.get("/api/assistant/turn")["X-API-Key"], undefined);
  browser.pending.get("/api/assistant/turn").resolve(response(assistantResult()));
  await request;
  assert.equal(browser.element("#assistant-workspace").hidden, false);
});
test("the model status says plainly whether the local model is ready", async () => {
  const browser = page();
  await tick();
  const offline = browser.run("checkModel()");
  assert.match(browser.element("[data-model-status]").innerHTML, /Checking/);
  browser.pending.get("/api/model/status").resolve(response({ available: false, model: "qwen", requires_key: false }));
  await offline;
  const node = browser.element("[data-model-status]");
  assert.match(node.innerHTML, /local model is off/);
  assert.match(node.innerHTML, /data-check-model/);
  assert.equal(node.dataset.tone, "off");
  const ready = browser.run("checkModel()");
  browser.pending.get("/api/model/status").resolve(response({ available: true, model_listed: true, model: "qwen", requires_key: true }));
  await ready;
  assert.match(node.innerHTML, /Local model ready/);
  assert.equal(browser.element("#lab-key-field").hidden, false, "a key-protected server shows the key field up front");
});

test("number keys pick a film, S skips, and picks so far stay visible during the quiz", async () => {
  const browser = page();
  await tick();
  browser.run(
    "taste.rounds=[[{movie_id:1,title:'One'},{movie_id:2,title:'Godfather, The (1972)'}],[{movie_id:3,title:'Three'}],[{movie_id:4,title:'Four'}]]; taste.answers=[]; taste.index=0",
  );
  await browser.run("setView('picks')");
  browser.run("showPicksStage('quiz'); renderRound()");
  assert.equal(browser.key("2"), true);
  assert.equal(browser.run("taste.answers[0]"), 2);
  assert.match(browser.element("#quiz-chosen").innerHTML, /The Godfather/);
  assert.equal(browser.key("s"), true);
  assert.equal(browser.run("taste.answers[1]"), null);
  assert.equal(browser.key("9"), false, "keys beyond the offered films are ignored");
  assert.equal(browser.key("1", { matches: () => true }), false, "typing in a field is never hijacked");
  browser.run("setView('catalog')");
  assert.equal(browser.key("1"), false, "shortcuts only work on the quick-picks screen");
});
