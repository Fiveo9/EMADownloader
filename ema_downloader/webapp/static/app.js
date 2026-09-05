/* EMA 监管文件库 - 前端逻辑（无依赖，原生 JS） */
"use strict";

const $ = (sel) => document.querySelector(sel);

/* ---------- 常量与文案 ---------- */

const TYPE_OPTIONS = [
  ["scientific-guideline", "科学指南"],
  ["regulatory-procedural-guideline", "监管程序指南"],
  ["reflection-paper", "反思文件"],
  ["position-paper", "立场文件"],
  ["concept-paper", "概念文件"],
  ["q-and-a", "问答文件"],
  ["public-statement", "公开声明"],
  ["legislation", "立法文件"],
  ["eu-legislation", "EU 立法"],
];

const DL_STATUSES = {
  "new": ["新文档", "gray"],
  "planned": ["已计划", "info"],
  "downloaded": ["已下载", "ok"],
  "updated": ["已更新", "ok"],
  "skipped_unchanged": ["无变化", "gray"],
  "skipped_existing": ["已存在", "gray"],
  "no_download_url": ["无下载链接", "gray"],
  "http_error": ["HTTP 错误", "err"],
  "invalid_content": ["内容无效", "err"],
  "checksum_error": ["校验失败", "err"],
  "write_error": ["写入失败", "err"],
};

const ERROR_STATUSES = ["http_error", "invalid_content", "checksum_error", "write_error"];

const TASK_TYPES = { sync: "同步", organize: "整理", export: "导出", verify: "校验" };
const TASK_PHASES = {
  queued: "排队中",
  fetching: "抓取数据源",
  planning: "增量分析",
  downloading: "下载文件",
  organizing: "整理文件",
  exporting: "导出索引",
  verifying: "完整性校验",
  done: "完成",
};
const TASK_STATES = {
  pending: ["等待中", "info"],
  running: ["运行中", "info"],
  success: ["成功", "ok"],
  failed: ["失败", "err"],
  cancelled: ["已取消", "warn"],
};

/* ---------- 工具函数 ---------- */

function esc(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  let data = {};
  try { data = await res.json(); } catch (_) { /* empty body */ }
  if (!res.ok) {
    const message = data && data.error ? data.error : `请求失败 (${res.status})`;
    const err = new Error(message);
    err.status = res.status;
    err.details = data && data.details;
    throw err;
  }
  return data;
}

function formatBytes(size) {
  const n = Number(size) || 0;
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function fmtDate(value) {
  return value ? String(value).slice(0, 10) : "—";
}

function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d) ? esc(iso) : d.toLocaleString("zh-CN", { hour12: false });
}

function fmtDuration(seconds) {
  const s = Number(seconds) || 0;
  if (s < 60) return `${s.toFixed(0)} 秒`;
  const m = Math.floor(s / 60);
  return `${m} 分 ${Math.round(s % 60)} 秒`;
}

let toastTimer = null;
function showToast(message, isError) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.toggle("error", Boolean(isError));
  el.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 3200);
}

function typeLabel(value) {
  const found = TYPE_OPTIONS.find(([v]) => v === value);
  return found ? found[1] : (value || "—");
}

function dlBadge(status, extraTitle) {
  const [label, cls] = DL_STATUSES[status] || [status || "未知", "gray"];
  const title = extraTitle ? ` title="${esc(extraTitle)}"` : "";
  return `<span class="badge ${cls}"${title}>${esc(label)}</span>`;
}

function openLibraryPath(relPath) {
  const url = relPath ? `/api/open?path=${encodeURIComponent(relPath)}` : "/api/open";
  fetchJSON(url).catch((e) => showToast(e.message, true));
}

/* ---------- 标签页切换 ---------- */

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

function switchTab(name) {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === `tab-${name}`));
  if (name === "library") loadDocs();
  if (name === "tasks") tick();
  if (name === "settings") loadSettings();
}

/* ---------- 总览 ---------- */

async function refreshSummary() {
  let data;
  try {
    data = await fetchJSON("/api/summary");
  } catch (e) {
    $("#summary-cards").innerHTML = `<div class="card"><div class="label">服务不可用</div><div class="value warn">—</div></div>`;
    return;
  }

  const c = data.counts || {};
  const downloaded = (c.status_downloaded || 0) + (c.status_updated || 0);
  const failed = ERROR_STATUSES.reduce((sum, s) => sum + (c[`status_${s}`] || 0), 0);
  const pending = (c.status_new || 0) + (c.status_planned || 0);
  const cards = [
    ["文档总数", c.total || 0, ""],
    ["科学指南", c["type_scientific-guideline"] || 0, ""],
    ["监管程序指南", c["type_regulatory-procedural-guideline"] || 0, ""],
    ["已下载", downloaded, "ok"],
    ["待下载", pending, ""],
    ["下载失败", failed, failed > 0 ? "warn" : ""],
  ];
  $("#summary-cards").innerHTML = cards
    .map(([label, value, cls]) => `
      <div class="card">
        <div class="label">${esc(label)}</div>
        <div class="value ${cls}">${esc(value)}</div>
      </div>`)
    .join("");

  renderLastSync(data.last_sync);

  const cfg = data.config || {};
  $("#config-info").innerHTML = `
    <div>资料库目录：<code>${esc(data.library_dir || "")}</code></div>
    <div>默认文档类型：<code>${esc((cfg.default_types || []).map(typeLabel).join("、")) || "全部"}</code></div>
    <div>并发下载数：<code>${esc(cfg.workers ?? "—")}</code></div>
    <div>代理：<code>${esc(cfg.proxy || "未配置")}</code></div>`;

  populateTypeSelects(data);
}

function renderLastSync(last) {
  const el = $("#last-sync");
  if (!last) {
    el.innerHTML = "暂无同步记录，点击「开始同步」完成首次抓取。";
    return;
  }
  el.innerHTML = `
    <div>时间：${esc(fmtTime(last.timestamp))}${last.summary && last.summary.dry_run ? "（Dry-run 预览）" : ""}</div>
    <div>匹配记录：${esc(last.total_records ?? 0)} 条，其中
      新 ${esc(last.new_planned ?? 0)} / 更新 ${esc(last.updated_planned ?? 0)} / 无变化 ${esc(last.skipped_unchanged ?? 0)}</div>
    <div>下载：成功 <span class="badge ok">${esc(last.downloaded_success ?? 0)}</span>
      失败 <span class="badge ${Number(last.downloaded_failed) > 0 ? "err" : "gray"}">${esc(last.downloaded_failed ?? 0)}</span></div>
    <div>耗时：${esc(fmtDuration(last.duration_seconds))}</div>`;
}

/* ---------- 文档库 ---------- */

const docState = { page: 1, pageSize: 50, total: 0 };

function populateTypeSelects(summaryData) {
  const typeSelect = $("#doc-type");
  const currentType = typeSelect.value;
  const known = new Set(TYPE_OPTIONS.map(([v]) => v));
  (summaryData.filter_options?.types || []).forEach((t) => known.add(t));

  typeSelect.innerHTML =
    `<option value="">全部类型</option>` +
    [...known].map((v) => `<option value="${esc(v)}">${esc(typeLabel(v))}</option>`).join("");
  typeSelect.value = currentType;

  // 同步对话框中的类型勾选框（默认勾选配置中的 default_types）
  const defaults = new Set((summaryData.config?.default_types || []).concat([...known]));
  const box = $("#sync-types");
  const checked = box.dataset.checked ? new Set(box.dataset.checked.split(",")) : defaults;
  box.innerHTML = [...known]
    .map((v) => `
      <label><input type="checkbox" value="${esc(v)}" ${checked.has(v) ? "checked" : ""}>
        ${esc(typeLabel(v))}</label>`)
    .join("");
}

async function loadDocs() {
  const params = new URLSearchParams();
  const keyword = $("#doc-keyword").value.trim();
  const type = $("#doc-type").value;
  const dlStatus = $("#doc-dl-status").value;
  if (keyword) params.set("keyword", keyword);
  if (type) params.set("types", type);
  if (dlStatus) params.set("download_statuses", dlStatus);
  params.set("page", docState.page);
  params.set("page_size", docState.pageSize);

  let data;
  try {
    data = await fetchJSON(`/api/documents?${params}`);
  } catch (e) {
    $("#doc-tbody").innerHTML = `<tr><td colspan="7" class="muted center">加载失败：${esc(e.message)}</td></tr>`;
    return;
  }

  docState.total = data.total;
  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
  if (docState.page > totalPages) docState.page = totalPages;

  $("#doc-total").textContent = `共 ${data.total} 条`;
  $("#page-info").textContent = `第 ${data.page} / ${totalPages} 页`;
  $("#page-prev").disabled = data.page <= 1;
  $("#page-next").disabled = data.page >= totalPages;

  const rows = data.documents.map((d) => {
    const parentDir = d.local_path && d.local_path.includes("/") ? d.local_path.split("/").slice(0, -1).join("/") : "";
    const actions = [];
    if (d.local_path) {
      actions.push(`<button class="icon-btn" data-action="open-file" data-path="${esc(d.local_path)}">打开</button>`);
      actions.push(`<button class="icon-btn" data-action="open-folder" data-path="${esc(parentDir)}">文件夹</button>`);
    }
    if (d.official_url) {
      actions.push(`<a class="icon-btn" href="${esc(d.official_url)}" target="_blank" rel="noopener">官网</a>`);
    }
    return `
      <tr>
        <td class="doc-title" title="${esc(d.name)}">${esc(d.name)}</td>
        <td>${esc(typeLabel(d.document_type))}</td>
        <td>${esc(d.sub_category || d.category || "—")}</td>
        <td>${esc(fmtDate(d.last_updated_at))}</td>
        <td class="num">${d.file_size ? esc(formatBytes(d.file_size)) : "—"}</td>
        <td>${dlBadge(d.download_status, d.error_message)}</td>
        <td><div class="row-actions">${actions.join("") || "—"}</div></td>
      </tr>`;
  });

  $("#doc-tbody").innerHTML = rows.length
    ? rows.join("")
    : `<tr><td colspan="7" class="muted center">没有符合条件的文档</td></tr>`;
}

$("#doc-tbody").addEventListener("click", (event) => {
  const btn = event.target.closest("[data-action]");
  if (!btn) return;
  if (btn.dataset.action === "open-file") openLibraryPath(btn.dataset.path);
  if (btn.dataset.action === "open-folder") openLibraryPath(btn.dataset.path);
});

$("#btn-doc-search").addEventListener("click", () => { docState.page = 1; loadDocs(); });
$("#doc-keyword").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { docState.page = 1; loadDocs(); }
});
$("#doc-type").addEventListener("change", () => { docState.page = 1; loadDocs(); });
$("#doc-dl-status").addEventListener("change", () => { docState.page = 1; loadDocs(); });
$("#page-prev").addEventListener("click", () => { docState.page -= 1; loadDocs(); });
$("#page-next").addEventListener("click", () => { docState.page += 1; loadDocs(); });

/* DL 状态筛选下拉 */
$("#doc-dl-status").innerHTML =
  `<option value="">全部下载状态</option>` +
  Object.entries(DL_STATUSES).map(([v, [label]]) => `<option value="${esc(v)}">${esc(label)}</option>`).join("");

/* ---------- 操作按钮 ---------- */

async function startTask(type, params, confirmText) {
  if (confirmText && !window.confirm(confirmText)) return;
  try {
    await fetchJSON("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, params }),
    });
    showToast("任务已启动");
    switchTab("tasks");
    tick();
  } catch (e) {
    showToast(e.message, true);
  }
}

$("#btn-sync").addEventListener("click", () => $("#sync-dialog").showModal());
$("#btn-organize").addEventListener("click", () =>
  startTask("organize", {}, "重新整理将按分类规则移动本地文件，确定继续？"));
$("#btn-export").addEventListener("click", () => startTask("export", {}));
$("#btn-verify").addEventListener("click", () => startTask("verify", {}));
$("#btn-open-library").addEventListener("click", () => openLibraryPath(""));

/* ---------- 同步对话框 ---------- */

$("#sync-cancel").addEventListener("click", () => $("#sync-dialog").close());

$("#sync-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const params = {};
  const types = [...document.querySelectorAll("#sync-types input:checked")].map((el) => el.value);
  if (types.length) params.types = types;
  const status = $("#sync-status").value.trim();
  if (status) params.status = status;
  const keyword = $("#sync-keyword").value.trim();
  if (keyword) params.keyword = keyword;
  const since = $("#sync-updated-since").value;
  if (since) params.updated_since = since;
  const limit = parseInt($("#sync-limit").value, 10);
  if (limit > 0) params.limit = limit;
  const workers = parseInt($("#sync-workers").value, 10);
  if (workers > 0) params.workers = workers;
  const proxy = $("#sync-proxy").value.trim();
  if (proxy) params.proxy = proxy;
  if ($("#sync-dry-run").checked) params.dry_run = true;

  const dryRun = Boolean(params.dry_run);
  $("#sync-dialog").close();
  await startTask("sync", params,
    dryRun ? "开始 Dry-run 预览（不下载文件）？" : "开始同步？首次全量同步耗时较长。");
});

/* ---------- 设置页 ---------- */

const PROXY_MASK = "********";
let settingsOverridden = {};
let settingsSnapshot = null;

const SETTINGS_FIELD_IDS = {
  "network.workers": "#set-workers",
  "network.timeout": "#set-timeout",
  "network.max_retries": "#set-max-retries",
  "network.retry_delay": "#set-retry-delay",
  "network.request_delay": "#set-request-delay",
  "network.proxy": "#set-proxy",
  "filters.default_types": "#set-types-label",
  "filters.default_status": "#set-status",
  "filters.default_languages": "#set-languages",
  "storage.library_dir": "#set-library-dir",
  "classification.rules_file": "#set-rules-file",
};

function splitList(text) {
  return String(text || "").split(",").map((s) => s.trim()).filter(Boolean);
}

function isOverridden(key) {
  const [section, field] = key.split(".");
  return (settingsOverridden[section] || []).includes(field);
}

function markOverridden() {
  Object.entries(SETTINGS_FIELD_IDS).forEach(([key, sel]) => {
    const anchor = $(sel);
    if (!anchor) return;
    const label = anchor.tagName === "LABEL"
      ? anchor
      : (document.querySelector(`label[for="${anchor.id}"]`) || anchor);
    let badge = label.querySelector(".override-badge");
    if (isOverridden(key)) {
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "badge info override-badge";
        badge.textContent = "已覆盖";
        badge.title = "该值来自 settings.local.toml 个人覆盖文件";
        label.appendChild(badge);
      }
    } else if (badge) {
      badge.remove();
    }
  });
}

async function loadSettings() {
  let data;
  try {
    data = await fetchJSON("/api/settings");
  } catch (e) {
    $("#settings-msg").textContent = `加载失败：${e.message}`;
    return;
  }
  settingsOverridden = data.overridden || {};
  settingsSnapshot = data.values;
  const v = data.values;
  $("#set-workers").value = v.network.workers;
  $("#set-timeout").value = v.network.timeout;
  $("#set-max-retries").value = v.network.max_retries;
  $("#set-retry-delay").value = v.network.retry_delay;
  $("#set-request-delay").value = v.network.request_delay;
  $("#set-proxy").value = v.network.proxy;

  const known = new Set(TYPE_OPTIONS.map(([val]) => val));
  (v.filters.default_types || []).forEach((t) => known.add(t));
  const current = new Set(v.filters.default_types || []);
  $("#set-types").innerHTML = [...known]
    .map((val) => `
      <label><input type="checkbox" value="${esc(val)}" ${current.has(val) ? "checked" : ""}>
        ${esc(typeLabel(val))}</label>`)
    .join("");
  $("#set-status").value = (v.filters.default_status || []).join(", ");
  $("#set-languages").value = (v.filters.default_languages || []).join(", ");
  $("#set-library-dir").value = v.storage.library_dir;
  $("#set-rules-file").value = v.classification.rules_file;

  markOverridden();
  $("#settings-local-note").textContent = `覆盖文件：${data.local_path}`;
  $("#settings-msg").textContent = "";
}

$("#btn-save-settings").addEventListener("click", async () => {
  const updates = {};
  const network = {};
  const numericFields = [
    ["#set-workers", "workers"],
    ["#set-timeout", "timeout"],
    ["#set-max-retries", "max_retries"],
    ["#set-retry-delay", "retry_delay"],
    ["#set-request-delay", "request_delay"],
  ];
  numericFields.forEach(([sel, name]) => {
    const raw = $(sel).value.trim();
    if (raw === "") return; // 留空不提交
    const n = Number(raw);
    network[name] = Number.isNaN(n) ? raw : n; // 非法值交给后端校验并提示
  });
  const proxy = $("#set-proxy").value;
  if (proxy !== PROXY_MASK) {
    network.proxy = proxy.trim(); // 空串 = 清除代理；新值 = 覆盖
  }
  if (Object.keys(network).length) updates.network = network;

  updates.filters = {
    default_types: [...document.querySelectorAll("#set-types input:checked")].map((el) => el.value),
    default_status: splitList($("#set-status").value),
    default_languages: splitList($("#set-languages").value),
  };

  const libDir = $("#set-library-dir").value.trim();
  if (libDir) updates.storage = { library_dir: libDir };
  const rulesFile = $("#set-rules-file").value.trim();
  if (rulesFile) updates.classification = { rules_file: rulesFile };

  // 只提交真正改动的字段，保持覆盖文件最小化
  const changed = {};
  Object.entries(updates).forEach(([section, fields]) => {
    const kept = {};
    Object.entries(fields).forEach(([field, value]) => {
      const oldValue = settingsSnapshot && settingsSnapshot[section] && settingsSnapshot[section][field];
      if (JSON.stringify(oldValue) !== JSON.stringify(value)) kept[field] = value;
    });
    if (Object.keys(kept).length) changed[section] = kept;
  });

  if (!Object.keys(changed).length) {
    showToast("没有需要保存的改动");
    return;
  }

  const btn = $("#btn-save-settings");
  btn.disabled = true;
  try {
    await fetchJSON("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changed),
    });
    showToast("设置已保存并立即生效");
    await loadSettings();
    refreshSummary();
  } catch (e) {
    let message = e.message;
    if (Array.isArray(e.details) && e.details.length) {
      message += "：" + e.details.map((d) => `${d.section}.${d.field} ${d.message}`).join("；");
    }
    showToast(message, true);
  } finally {
    btn.disabled = false;
  }
});

/* ---------- 任务轮询 ---------- */

let lastLogCount = 0;

function renderCurrentTask(task) {
  const el = $("#current-task");
  if (!task) {
    el.innerHTML = "当前没有运行中的任务";
    lastLogCount = 0;
    return;
  }
  const [stateLabel, stateCls] = TASK_STATES[task.state] || [task.state, "gray"];
  const phaseLabel = TASK_PHASES[task.phase] || task.phase || "";
  const percent = task.progress.total
    ? Math.min(100, Math.round((task.progress.done / task.progress.total) * 100))
    : 0;
  const indeterminate = !task.progress.total;

  el.innerHTML = `
    <div class="progress-meta">
      <strong>${esc(TASK_TYPES[task.type] || task.type)}</strong>
      <span>${esc(phaseLabel)} · <span class="badge ${stateCls}">${esc(stateLabel)}</span></span>
    </div>
    <div class="progress-wrap">
      <div class="progress-bar ${indeterminate ? "indeterminate" : ""}">
        <div class="fill" style="width: ${indeterminate ? 35 : percent}%"></div>
      </div>
      <div class="progress-meta">
        <span>${task.progress.total ? `${task.progress.done} / ${task.progress.total}` : "处理中…"}</span>
        <span class="current" title="${esc(task.current_item)}">${esc(task.current_item)}</span>
      </div>
    </div>
    <div class="progress-meta">
      <span>开始于 ${esc(fmtTime(task.started_at))}</span>
      ${task.state === "running" || task.state === "pending"
        ? `<button id="btn-cancel-task" class="btn small danger">取消任务</button>` : ""}
    </div>
    <div class="log-box" id="log-box">${esc((task.logs || []).join("\n"))}</div>`;

  const cancelBtn = $("#btn-cancel-task");
  if (cancelBtn) {
    cancelBtn.addEventListener("click", async () => {
      try {
        await fetchJSON(`/api/tasks/${task.id}/cancel`, { method: "POST" });
        showToast("已请求取消，等待当前文件完成…");
      } catch (e) {
        showToast(e.message, true);
      }
    });
  }

  const logBox = $("#log-box");
  if (logBox) {
    const nearBottom = logBox.scrollHeight - logBox.scrollTop - logBox.clientHeight < 40;
    if ((task.logs || []).length !== lastLogCount || nearBottom === false) {
      if (nearBottom) logBox.scrollTop = logBox.scrollHeight;
    }
    lastLogCount = (task.logs || []).length;
  }
}

function taskResultSummary(task) {
  const s = task.stats || {};
  switch (task.type) {
    case "sync":
      return `新 ${s.new_planned ?? 0} / 更新 ${s.updated_planned ?? 0} / 成功 ${s.downloaded_success ?? 0} / 失败 ${s.downloaded_failed ?? 0}`
        + (s.dry_run ? "（dry-run）" : "");
    case "organize":
      return `移动 ${s.moved ?? 0} 个文件`;
    case "verify":
      return s.issues ? `发现 ${s.issues} 个问题` : "全部通过";
    case "export":
      return `导出 ${Object.keys(task.result || {}).length} 个文件`;
    default:
      return "";
  }
}

function renderTaskHistory(tasks) {
  const finished = tasks.filter((t) => !["pending", "running"].includes(t.state));
  const rows = finished.map((t) => {
    const [stateLabel, stateCls] = TASK_STATES[t.state] || [t.state, "gray"];
    const duration = t.stats && t.stats.duration_seconds != null
      ? t.stats.duration_seconds
      : (Date.parse(t.finished_at) - Date.parse(t.started_at)) / 1000;
    const detail = t.error
      ? ` title="${esc(t.error)}"`
      : (t.result && t.result.excel ? ` title="报告: ${esc(t.result.excel)}"` : "");
    return `
      <tr${detail}>
        <td>${esc(fmtTime(t.started_at))}</td>
        <td>${esc(TASK_TYPES[t.type] || t.type)}</td>
        <td><span class="badge ${stateCls}">${esc(stateLabel)}</span></td>
        <td>${esc(taskResultSummary(t))}</td>
        <td>${duration > 0 ? esc(fmtDuration(duration)) : "—"}</td>
        <td>${t.state === "failed" ? "⚠" : ""}</td>
      </tr>`;
  });
  $("#task-history-tbody").innerHTML = rows.length
    ? rows.join("")
    : `<tr><td colspan="6" class="muted center">暂无任务记录</td></tr>`;
}

async function tick() {
  let data;
  try {
    data = await fetchJSON("/api/tasks");
  } catch (_) {
    return; // 服务暂不可达时静默跳过
  }
  const active = data.tasks.find((t) => t.state === "pending" || t.state === "running");
  const indicator = $("#global-task-indicator");

  if (active) {
    try {
      const detail = await fetchJSON(`/api/tasks/${active.id}`);
      renderCurrentTask(detail);
      indicator.classList.remove("hidden");
      $("#global-task-text").textContent =
        `${TASK_TYPES[detail.type] || detail.type} · ${TASK_PHASES[detail.phase] || ""} ` +
        (detail.progress.total ? `${detail.progress.done}/${detail.progress.total}` : "");
      setActionsDisabled(true);
      window.__activeTaskId = detail.id;
    } catch (_) { /* 任务刚结束导致 404 时忽略 */ }
  } else {
    if (window.__activeTaskId) {
      window.__activeTaskId = null;
      refreshSummary();   // 任务刚完成，刷新总览统计
    }
    renderCurrentTask(null);
    indicator.classList.add("hidden");
    setActionsDisabled(false);
  }
  renderTaskHistory(data.tasks);
}

function setActionsDisabled(disabled) {
  ["#btn-sync", "#btn-organize", "#btn-export", "#btn-verify"].forEach((sel) => {
    $(sel).disabled = disabled;
  });
}

/* ---------- 初始化 ---------- */

refreshSummary();
loadDocs();
tick();
setInterval(tick, 1500);
setInterval(refreshSummary, 10000);
