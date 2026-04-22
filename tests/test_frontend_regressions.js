const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");


class FakeClassList {
  constructor(initial = []) {
    this.classes = new Set(initial);
  }

  add(...classNames) {
    classNames.forEach((className) => this.classes.add(className));
  }

  remove(...classNames) {
    classNames.forEach((className) => this.classes.delete(className));
  }

  contains(className) {
    return this.classes.has(className);
  }

  toggle(className) {
    if (this.classes.has(className)) {
      this.classes.delete(className);
      return false;
    }

    this.classes.add(className);
    return true;
  }
}


class FakeElement {
  constructor({ classNames = [] } = {}) {
    this.classList = new FakeClassList(classNames);
    this.style = {};
    this.dataset = {};
    this.innerHTML = "";
    this.textContent = "";
    this.value = "";
    this.disabled = false;
    this.children = [];
    this.listeners = new Map();
  }

  addEventListener(eventName, listener) {
    const listeners = this.listeners.get(eventName) || [];
    listeners.push(listener);
    this.listeners.set(eventName, listeners);
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  insertBefore(child) {
    this.children.unshift(child);
    return child;
  }

  querySelector() {
    return null;
  }

  querySelectorAll() {
    return [];
  }

  focus() {}
}


function loadMainJsContext({
  includeUploadArea = false,
  includeDocumentList = false,
  includeModelSettings = false,
} = {}) {
  const elementMap = new Map([
    ["chatMessages", new FakeElement()],
    ["messageInput", new FakeElement()],
    ["conversationList", new FakeElement()],
    ["settingsModal", new FakeElement()],
    ["loadingOverlay", new FakeElement()],
    ["kbWarning", new FakeElement()],
    ["welcomeScreen", new FakeElement()],
    ["statusIndicator", new FakeElement()],
    ["conversationCount", new FakeElement()],
    ["sendBtn", new FakeElement()],
    ["sidebar", new FakeElement()],
    ["panel-model", new FakeElement()],
  ]);

  if (includeUploadArea) {
    elementMap.set("uploadArea", new FakeElement());
    elementMap.set("fileInput", new FakeElement());
  }

  if (includeDocumentList) {
    elementMap.set("documentList", new FakeElement());
    elementMap.set("docCount", new FakeElement());
  }

  if (includeModelSettings) {
    [
      "llm-provider",
      "llm-base_url",
      "llm-api_key",
      "llm-model",
      "embedding-provider",
      "embedding-base_url",
      "embedding-api_key",
      "embedding-model",
      "param-temperature",
      "param-max_tokens",
      "param-top_p",
      "param-frequency_penalty",
      "param-presence_penalty",
      "param-chunk_size",
      "param-chunk_overlap",
      "param-retrieval_k",
    ].forEach((id) => {
      elementMap.set(id, new FakeElement());
    });
  }

  const documentListeners = new Map();
  const document = {
    getElementById(id) {
      return elementMap.get(id) || null;
    },
    addEventListener(eventName, listener) {
      documentListeners.set(eventName, listener);
    },
    querySelectorAll() {
      return [];
    },
    createElement() {
      return new FakeElement();
    },
    body: new FakeElement(),
  };

  const context = {
    console,
    confirm: () => true,
    alert: () => {},
    fetch: async () => ({
      json: async () => [],
    }),
    requestAnimationFrame: (callback) => callback(),
    setTimeout: (callback) => {
      callback();
      return 0;
    },
    clearTimeout: () => {},
    document,
    window: {
      currentUser: null,
      innerWidth: 1200,
      innerHeight: 800,
      location: { href: "" },
    },
  };

  vm.createContext(context);

  const script = fs.readFileSync(
    path.join(__dirname, "..", "static", "js", "main.js"),
    "utf8",
  );
  vm.runInContext(script, context);

  return context;
}


test("setupDragAndDrop tolerates student pages without upload controls", () => {
  const context = loadMainJsContext();
  assert.doesNotThrow(() => context.setupDragAndDrop());
});


test("student settings panel skips admin-only loaders", async () => {
  const context = loadMainJsContext();
  const calls = [];

  context.window.currentUser = { role: "student" };
  context.loadDocumentTree = async () => calls.push("documents");
  context.loadModelSettings = async () => calls.push("settings");
  context.loadStudentCategories = async () => calls.push("categories");
  context.loadStudentList = async () => calls.push("students");

  await context.toggleSettingsPanel();

  assert.deepEqual(calls, []);
});


test("renderDocumentList tolerates templates without legacy document list nodes", () => {
  const context = loadMainJsContext();
  assert.doesNotThrow(() => context.renderDocumentList([]));
});


test("parseSseBuffer keeps incomplete frames until they are complete", () => {
  const context = loadMainJsContext();
  const firstPass = context.parseSseBuffer('data: {"type":"chunk","content":"hel');
  assert.deepEqual(JSON.parse(JSON.stringify(firstPass.events)), []);
  assert.equal(firstPass.remainingBuffer, 'data: {"type":"chunk","content":"hel');

  const secondPass = context.parseSseBuffer(
    firstPass.remainingBuffer + 'lo"}\n\ndata: {"type":"done","sources":[]}\n\n',
  );

  assert.deepEqual(JSON.parse(JSON.stringify(secondPass.events)), [
    { type: "chunk", content: "hello" },
    { type: "done", sources: [] },
  ]);
  assert.equal(secondPass.remainingBuffer, "");
});


test("renderMessages forwards stored sources when reloading history", () => {
  const context = loadMainJsContext();
  const calls = [];

  context.appendMessage = (role, content, sources) => {
    calls.push({ role, content, sources });
  };

  context.renderMessages([
    {
      role: "assistant",
      content: "answer",
      sources: [{ source: "guide.pdf", content: "snippet" }],
    },
  ]);

  assert.deepEqual(calls, [
    {
      role: "assistant",
      content: "answer",
      sources: [{ source: "guide.pdf", content: "snippet" }],
    },
  ]);
});


test("renderModelSettings populates provider config inputs", () => {
  const context = loadMainJsContext({ includeModelSettings: true });

  context.renderModelSettings([
    { setting_key: "llm_provider", value: "openai_compatible" },
    { setting_key: "llm_base_url", value: "http://localhost:1234/v1" },
    { setting_key: "llm_api_key", value: "sk-local" },
    { setting_key: "llm_model", value: "qwen-local" },
    { setting_key: "embedding_provider", value: "openai_compatible" },
    { setting_key: "embedding_base_url", value: "http://localhost:1234/v1" },
    { setting_key: "embedding_api_key", value: "" },
    { setting_key: "embedding_model", value: "text-embedding-local" },
    { setting_key: "llm_temperature", value: 0.3 },
    { setting_key: "embedding_retrieval_k", value: 5 },
  ]);

  assert.equal(context.document.getElementById("llm-provider").value, "openai_compatible");
  assert.equal(context.document.getElementById("llm-base_url").value, "http://localhost:1234/v1");
  assert.equal(context.document.getElementById("llm-model").value, "qwen-local");
  assert.equal(context.document.getElementById("embedding-provider").value, "openai_compatible");
  assert.equal(context.document.getElementById("embedding-model").value, "text-embedding-local");
  assert.equal(context.document.getElementById("param-temperature").value, 0.3);
  assert.equal(context.document.getElementById("param-retrieval_k").value, 5);
});


test("saveModelSettings submits provider config together with numeric params", async () => {
  const context = loadMainJsContext({ includeModelSettings: true });
  const requests = [];

  context.fetch = async (_url, options = {}) => {
    if (options.body) {
      requests.push(JSON.parse(options.body));
      return {
        ok: true,
        json: async () => ({ success: true }),
      };
    }

    return {
      ok: true,
      json: async () => ({ success: true, settings: [] }),
    };
  };

  context.document.getElementById("llm-provider").value = "openai_compatible";
  context.document.getElementById("llm-base_url").value = "http://localhost:1234/v1";
  context.document.getElementById("llm-api_key").value = "";
  context.document.getElementById("llm-model").value = "qwen-local";
  context.document.getElementById("embedding-provider").value = "openai_compatible";
  context.document.getElementById("embedding-base_url").value = "http://localhost:1234/v1";
  context.document.getElementById("embedding-api_key").value = "";
  context.document.getElementById("embedding-model").value = "text-embedding-local";
  context.document.getElementById("param-temperature").value = "0.4";
  context.document.getElementById("param-max_tokens").value = "1024";
  context.document.getElementById("param-top_p").value = "0.9";
  context.document.getElementById("param-frequency_penalty").value = "0";
  context.document.getElementById("param-presence_penalty").value = "0";
  context.document.getElementById("param-chunk_size").value = "500";
  context.document.getElementById("param-chunk_overlap").value = "50";
  context.document.getElementById("param-retrieval_k").value = "3";

  await context.saveModelSettings();

  const submittedKeys = requests.map((request) => request.key);
  assert.ok(submittedKeys.includes("llm_provider"));
  assert.ok(submittedKeys.includes("llm_base_url"));
  assert.ok(submittedKeys.includes("llm_model"));
  assert.ok(submittedKeys.includes("embedding_provider"));
  assert.ok(submittedKeys.includes("embedding_base_url"));
  assert.ok(submittedKeys.includes("embedding_model"));
  assert.ok(submittedKeys.includes("llm_temperature"));
  assert.ok(submittedKeys.includes("embedding_retrieval_k"));
});
