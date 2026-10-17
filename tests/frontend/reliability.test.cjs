/* Behavioral regression tests for delayed browser requests; no browser/network dependencies. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const vm = require("node:vm");
const source = readFileSync("app/static/app.js", "utf8");
const tick = () => new Promise((resolve) => setImmediate(resolve));
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
};
const response = (data, ok = true) => ({ ok, json: async () => data });
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
    this.classList = { add() {}, remove() {}, toggle() {} };
  }
  addEventListener(name, fn) {
    (this.events[name] ??= []).push(fn);
  }
  append() {}
  insertAdjacentHTML(_where, html) {
    this.innerHTML += html;
  }
  scrollIntoView() {}
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
  const element = (selector) => {
    if (!nodes.has(selector)) nodes.set(selector, new Element());
    return nodes.get(selector);
  };
  element("#user-id").value = "42";
  const context = vm.createContext({
    console,
    setTimeout,
    clearTimeout,
    AbortController,
    document: {
      querySelector: element,
      querySelectorAll: () => [],
      addEventListener() {},
      createElement: () => new Element(),
    },
    fetch: (path) => {
      requests.push(path);
      if (path === "/static/posters.json") return posters;
      if (path === "/api/system/status")
        return Promise.resolve(response({ movies: 10, ratings: 20, users: 3 }));
      if (path === "/api/genres") return Promise.resolve(response([]));
      const request = deferred();
      pending.set(path, request);
      return request.promise;
    },
  });
  const pending = new Map();
  vm.runInContext(source, context);
  return {
    element,
    requests,
    pending,
    run: (code) => vm.runInContext(code, context),
  };
}
const item = (title, id) => ({
  movie_id: id,
  title,
  year: 2000,
  genres: ["Drama"],
  score: 0.3,
  support: 5,
});

test("a slow catalog response cannot replace the newer ranking view", async () => {
  const browser = page();
  await tick();
  const old = browser.run("setView('catalog')");
  const latest = browser.run("setView('trending')");
  const ranking = browser.pending.get(
    "/api/movies/trending?limit=8&window_days=365",
  );
  assert.ok(ranking, "the latest navigation must start its own request");
  ranking.resolve(
    response({
      items: [item("NEW RANKING", 2)],
      method: "historical_activity",
    }),
  );
  await latest;
  browser.pending
    .get("/api/movies?limit=8&offset=0&q=")
    .resolve(response({ items: [item("OLD CATALOG", 1)] }));
  await old;
  assert.match(browser.element("#movie-grid").innerHTML, /NEW RANKING/);
  assert.doesNotMatch(browser.element("#movie-grid").innerHTML, /OLD CATALOG/);
  assert.match(
    browser.element("#result-note").textContent,
    /historical snapshot/,
  );
});

test("a late film-detail result cannot append to a different film", async () => {
  const browser = page();
  await tick();
  const old = browser.run("showSimilar(1)");
  const latest = browser.run("showSimilar(2)");
  browser.pending
    .get("/api/movies/2/similar?limit=6")
    .resolve(response({ items: [item("SECOND FILM RESULT", 3)] }));
  await latest;
  browser.pending
    .get("/api/movies/1/similar?limit=6")
    .resolve(response({ items: [item("FIRST FILM RESULT", 4)] }));
  await old;
  assert.match(
    browser.element("#detail-content").innerHTML,
    /SECOND FILM RESULT/,
  );
  assert.doesNotMatch(
    browser.element("#detail-content").innerHTML,
    /FIRST FILM RESULT/,
  );
  assert.doesNotMatch(
    browser.element("#detail-content").innerHTML,
    /Finding films/,
  );
});

test("a failed old detail request cannot contaminate a newer dialog", async () => {
  const browser = page();
  await tick();
  const old = browser.run("showSimilar(1)");
  const latest = browser.run("showSimilar(2)");
  browser.pending
    .get("/api/movies/2/similar?limit=6")
    .resolve(response({ items: [item("CURRENT FILM", 3)] }));
  await latest;
  browser.pending
    .get("/api/movies/1/similar?limit=6")
    .resolve(response({ detail: "OLD REQUEST FAILED" }, false));
  await old;
  assert.doesNotMatch(
    browser.element("#detail-content").innerHTML,
    /OLD REQUEST FAILED/,
  );
});

test("closing a dialog invalidates a pending detail response", async () => {
  const browser = page();
  await tick();
  const request = browser.run("showSimilar(1)");
  browser.element("#detail-dialog").close();
  browser.pending
    .get("/api/movies/1/similar?limit=6")
    .resolve(response({ items: [item("LATE RESULT", 2)] }));
  await request;
  assert.doesNotMatch(
    browser.element("#detail-content").innerHTML,
    /LATE RESULT/,
  );
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
  const path = "/api/movies?limit=8&offset=1008&q=";
  assert.ok(browser.requests.includes(path));
  browser.pending.get(path).resolve(response({ items: [] }));
  await tick();
});

test("an obsolete list failure cannot replace a successful newer view", async () => {
  const browser = page();
  await tick();
  const old = browser.run("setView('catalog')");
  const current = browser.run("setView('trending')");
  browser.pending
    .get("/api/movies/trending?limit=8&window_days=365")
    .resolve(response({ items: [item("CURRENT RESULTS", 2)] }));
  await current;
  browser.pending
    .get("/api/movies?limit=8&offset=0&q=")
    .resolve(response({ detail: "OBSOLETE ERROR" }, false));
  await old;
  assert.match(browser.element("#movie-grid").innerHTML, /CURRENT RESULTS/);
  assert.doesNotMatch(browser.element("#notice").textContent, /OBSOLETE ERROR/);
});
