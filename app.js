const state = {
  data: null,
  selectedId: null,
  filter: "all",
  query: "",
  view: "graph",
};

const groupColor = {
  question: "#006b67",
  article: "#3b6ea8",
  sentence: "#c78b20",
  entity: "#7b4fb5",
  answer: "#2f8a45",
  cluster: "#697386",
};

const els = {
  search: document.querySelector("#searchInput"),
  resultList: document.querySelector("#resultList"),
  recordCount: document.querySelector("#recordCount"),
  nodeCount: document.querySelector("#nodeCount"),
  questionTitle: document.querySelector("#questionTitle"),
  answerText: document.querySelector("#answerText"),
  indexedCount: document.querySelector("#indexedCount"),
  demoCount: document.querySelector("#demoCount"),
  graphSvg: document.querySelector("#graphSvg"),
  supportList: document.querySelector("#supportList"),
  relationList: document.querySelector("#relationList"),
  typeChart: document.querySelector("#typeChart"),
  clusterChart: document.querySelector("#clusterChart"),
};

function short(text, size = 76) {
  if (!text) return "";
  return text.length > size ? `${text.slice(0, size - 1)}…` : text;
}

function questionNodeId(question) {
  return `questions/${question._key}`;
}

function filteredQuestions() {
  const query = state.query.trim().toLowerCase();
  return state.data.questions.filter((item) => {
    const typeOk = state.filter === "all" || item.type === state.filter;
    const queryOk =
      !query ||
      item.question.toLowerCase().includes(query) ||
      item.answer.toLowerCase().includes(query) ||
      item.cluster.toLowerCase().includes(query) ||
      item.type.toLowerCase().includes(query);
    return typeOk && queryOk;
  });
}

function setSelected(id) {
  state.selectedId = id;
  render();
}

function selectedQuestion() {
  return state.data.questions.find((item) => questionNodeId(item) === state.selectedId) || state.data.questions[0];
}

function connectedSubgraph(rootId) {
  const nodes = new Map(state.data.nodes.map((node) => [node.id, node]));
  const allEdges = state.data.edges;
  const direct = allEdges.filter((edge) => edge.source === rootId || edge.target === rootId);
  const supportSentenceIds = new Set(direct.filter((edge) => edge.label === "supporting_fact").map((edge) => edge.target));
  const supportArticleIds = new Set(
    allEdges
      .filter((edge) => edge.label === "has_sentence" && supportSentenceIds.has(edge.target))
      .map((edge) => edge.source),
  );
  const selectedEdges = direct.filter((edge) => {
    if (edge.label === "context") return supportArticleIds.has(edge.target);
    if (edge.label !== "evidence") return true;
    return true;
  });
  const selectedNodes = new Set([rootId]);

  selectedEdges.forEach((edge) => {
    selectedNodes.add(edge.source);
    selectedNodes.add(edge.target);
  });

  allEdges.forEach((edge) => {
    if (edge.label === "has_sentence" && supportSentenceIds.has(edge.target) && supportArticleIds.has(edge.source)) {
      selectedEdges.push(edge);
      selectedNodes.add(edge.source);
      selectedNodes.add(edge.target);
    }
  });

  const uniqueEdges = Array.from(new Map(selectedEdges.map((edge) => [`${edge.source}->${edge.target}:${edge.label}`, edge])).values());
  return {
    nodes: Array.from(selectedNodes).map((id) => nodes.get(id)).filter(Boolean),
    edges: uniqueEdges,
  };
}

function renderResults() {
  const results = filteredQuestions();
  els.resultList.innerHTML = "";
  results.forEach((item) => {
    const id = questionNodeId(item);
    const button = document.createElement("button");
    button.className = `result-item${id === state.selectedId ? " active" : ""}`;
    button.addEventListener("click", () => setSelected(id));
    button.innerHTML = `
      <strong>${short(item.question, 115)}</strong>
      <span>${short(item.answer, 85)}</span>
      <span class="tag-row">
        <span class="tag">${item.type}</span>
        <span class="tag">${item.cluster}</span>
        <span class="tag">${item.support_count} facts</span>
      </span>
    `;
    els.resultList.appendChild(button);
  });
}

function renderHeader(question) {
  els.questionTitle.textContent = question.question;
  els.answerText.textContent = `Answer: ${question.answer} | Type: ${question.type} | Cluster: ${question.cluster}`;
}

function renderGraph(question) {
  const rootId = questionNodeId(question);
  const { nodes, edges } = connectedSubgraph(rootId);
  const svg = els.graphSvg;
  const width = svg.clientWidth || 900;
  const height = svg.clientHeight || 600;
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.max(170, Math.min(width, height) * 0.34);

  const root = nodes.find((node) => node.id === rootId);
  const rest = nodes.filter((node) => node.id !== rootId);
  const positioned = new Map();
  positioned.set(rootId, { ...root, x: cx, y: cy });
  const groupOrder = { article: 0, sentence: 1, entity: 2, answer: 3, cluster: 4 };
  rest.sort((left, right) => (groupOrder[left.group] ?? 9) - (groupOrder[right.group] ?? 9));
  rest.forEach((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(1, rest.length) - Math.PI / 2;
    const ring = node.group === "sentence" ? radius + 45 : radius;
    positioned.set(node.id, {
      ...node,
      x: cx + Math.cos(angle) * ring,
      y: cy + Math.sin(angle) * ring,
    });
  });

  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = `
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#98a3ae"></path>
      </marker>
    </defs>
  `;

  edges.forEach((edge) => {
    const source = positioned.get(edge.source);
    const target = positioned.get(edge.target);
    if (!source || !target) return;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", source.x);
    line.setAttribute("y1", source.y);
    line.setAttribute("x2", target.x);
    line.setAttribute("y2", target.y);
    line.setAttribute("stroke", "#b4bec8");
    line.setAttribute("stroke-width", "1.4");
    line.setAttribute("marker-end", "url(#arrow)");
    svg.appendChild(line);

    if (edge.label !== "has_sentence") {
      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", (source.x + target.x) / 2);
      label.setAttribute("y", (source.y + target.y) / 2 - 5);
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("class", "edge-label");
      label.textContent = short(edge.label, 18);
      svg.appendChild(label);
    }
  });

  positioned.forEach((node) => {
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", node.x);
    circle.setAttribute("cy", node.y);
    circle.setAttribute("r", node.group === "question" ? "24" : "17");
    circle.setAttribute("fill", groupColor[node.group] || "#697386");
    circle.setAttribute("stroke", "#fff");
    circle.setAttribute("stroke-width", "3");
    svg.appendChild(circle);

    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", node.x);
    text.setAttribute("y", node.y + (node.group === "question" ? 40 : 32));
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("class", "node-label");
    text.textContent = short(node.label, node.group === "sentence" ? 34 : 28);
    svg.appendChild(text);
  });
}

function renderEvidence(question) {
  const rootId = questionNodeId(question);
  const { nodes, edges } = connectedSubgraph(rootId);
  const nodeById = new Map(nodes.map((node) => [node.id, node]));

  const supportEdges = edges.filter((edge) => edge.source === rootId && edge.label === "supporting_fact");
  els.supportList.innerHTML = "";
  supportEdges.forEach((edge) => {
    const node = nodeById.get(edge.target);
    if (!node) return;
    const item = document.createElement("li");
    item.innerHTML = `<strong>${node.title || "Evidence"}</strong>: ${node.label}`;
    els.supportList.appendChild(item);
  });
  if (!els.supportList.children.length) {
    els.supportList.innerHTML = "<li>No supporting fact in current demo subset.</li>";
  }

  const relationEdges = edges.filter((edge) => edge.source === rootId && edge.fact);
  els.relationList.innerHTML = "";
  relationEdges.forEach((edge) => {
    const node = nodeById.get(edge.target);
    const item = document.createElement("li");
    item.innerHTML = `<strong>${edge.label}</strong> -> ${node ? node.label : edge.target}<br>${edge.fact}`;
    els.relationList.appendChild(item);
  });
  if (!els.relationList.children.length) {
    els.relationList.innerHTML = "<li>No evidence relation in current demo subset.</li>";
  }
}

function renderBars(container, rows) {
  const max = Math.max(1, ...rows.map((row) => row.count));
  container.innerHTML = "";
  rows.forEach((row) => {
    const bar = document.createElement("div");
    bar.className = "bar";
    bar.innerHTML = `
      <span>${row.name}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${(row.count / max) * 100}%"></span></span>
      <strong>${row.count}</strong>
    `;
    container.appendChild(bar);
  });
}

function renderCharts() {
  renderBars(els.typeChart, state.data.stats.types);
  renderBars(els.clusterChart, state.data.stats.clusters);
}

function render() {
  if (!state.data) return;
  if (!state.selectedId && state.data.questions.length) {
    state.selectedId = questionNodeId(state.data.questions[0]);
  }
  const question = selectedQuestion();
  els.recordCount.textContent = state.data.total_records || state.data.generated_from_records;
  els.indexedCount.textContent = state.data.generated_from_records;
  els.demoCount.textContent = state.data.demo_question_count || state.data.questions.length;
  els.nodeCount.textContent = state.data.nodes.length;
  renderResults();
  renderHeader(question);
  renderGraph(question);
  renderEvidence(question);
  renderCharts();
}

document.querySelectorAll("[data-filter]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-filter]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.filter = button.dataset.filter;
    render();
  });
});

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-view]").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".view").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.view = button.dataset.view;
    document.querySelector(`#${state.view}View`).classList.add("active");
    render();
  });
});

els.search.addEventListener("input", (event) => {
  state.query = event.target.value;
  const first = filteredQuestions()[0];
  if (first) state.selectedId = questionNodeId(first);
  render();
});

fetch(`./demo-data.json?v=${Date.now()}`, { cache: "no-store" })
  .then((response) => response.json())
  .then((data) => {
    state.data = data;
    render();
  })
  .catch((error) => {
    els.resultList.innerHTML = `<p>demo-data.json 未生成：${error.message}</p>`;
  });
