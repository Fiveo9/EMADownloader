/* EMA 监管文件库 - 前端逻辑（无依赖，原生 JS） */
"use strict";

const $ = (sel) => document.querySelector(sel);

/* ---------- 常量与文案 ---------- */

/* 业务大类分组定义：将 EMA 官方 80+ 种类型按药政实际业务场景归入 5 级分组 */
const TYPE_GROUPS = [
  {
    id: "guidelines",
    title: "1. 核心法规与指导原则 (CHMP)",
    badge: "CHMP 核心 · 推荐",
    badgeClass: "ok",
    desc: "EMA/CHMP (人用药品委员会) 人用药品上市申报、CMC质量、临床与非临床指导原则、ICH规范及程序指南，覆盖 95% 以上法规检索需求。",
    defaultExpanded: true,
  },
  {
    id: "assessment",
    title: "2. 审评审批与科学结论",
    badge: "调研 · 审评参考",
    badgeClass: "info",
    desc: "EMA 对具体药品的公共评估报告 (EPAR)、仲裁决议、科学结论及孤儿药资格认定等审评技术材料。",
    defaultExpanded: true,
  },
  {
    id: "safety",
    title: "3. 药物警戒与安全监管",
    badge: "PV · 安全专线",
    badgeClass: "warn",
    desc: "药品全生命周期风险管理计划 (RMP)、致医务人员安全警示函 (DHPC) 及定期安全性更新 (PSUSA)。",
    defaultExpanded: true,
  },
  {
    id: "herbal",
    title: "4. 草药与传统植物药 (HMPC)",
    badge: "HMPC 专论",
    badgeClass: "ok",
    desc: "HMPC (草药药品委员会) 发布的欧盟草药专论标准、技术评估报告与委员会意见，适用于传统中草药与天然植物药物。",
    defaultExpanded: true,
  },
  {
    id: "administrative",
    title: "5. 日常行政、会议与审批流水",
    badge: "50,000+ 篇 · 慎选",
    badgeClass: "err",
    desc: "日常会议日程纪要、培训演示 PPT、单药 PIP 审批决定、微小变更流水等日常运营文件，量极大且非法规规范。",
    defaultExpanded: false,
  },
];

/* 场景快捷预设：供一键切换推荐勾选组合 */
const TYPE_PRESETS = [
  {
    id: "core-guidelines",
    title: "🎯 核心法规（推荐）",
    types: [
      "scientific-guideline",
      "regulatory-procedural-guideline",
      "medicine-qa",
    ],
  },
  {
    id: "guidelines-assessment",
    title: "🔍 法规 + 审评调研",
    types: [
      "scientific-guideline",
      "regulatory-procedural-guideline",
      "medicine-qa",
      "assessment-report",
      "scientific-conclusion",
      "referral",
      "public-statement",
    ],
  },
  {
    id: "safety-pv",
    title: "🛡️ 药物警戒专线",
    types: [
      "rmp",
      "rmp-summary",
      "dhpc",
      "psusa",
      "prac-recommendation",
    ],
  },
  {
    id: "herbal-medicines",
    title: "🌿 草药专论",
    types: [
      "herbal-monograph",
      "herbal-report",
      "herbal-opinion",
      "herbal-summary",
      "herbal-references",
    ],
  },
  {
    id: "clear",
    title: "🧹 清空已选",
    types: [],
  },
];

/* 86 种 EMA 文档类型的专业中文标签、分组与悬浮业务说明字典 */
const TYPE_META = {
  // 1. 核心法规与指导原则 (CHMP)
  "scientific-guideline": { group: "guidelines", label: "科学指南", tip: "EMA/CHMP 人用药品核心技术指南（质量CMC、非临床、临床安全性与有效性、ICH等）" },
  "regulatory-procedural-guideline": { group: "guidelines", label: "监管程序指南", tip: "上市许可申请、变更、续展、eCTD 提交规范等合规操作程序" },
  "medicine-qa": { group: "guidelines", label: "问答文件 (Q&A)", tip: "EMA 官方针对具体指南或实操执行难点发布的答疑解惑" },

  // 2. 审评审批与技术结论 (assessment)
  "assessment-report": { group: "assessment", label: "公开评估报告 (EPAR)", tip: "欧洲公共评估报告技术正文，新药上市核心技术审评依据" },
  "scientific-conclusion": { group: "assessment", label: "科学结论与修订建议", tip: "CHMP/PRAC 审查后作出的科学结论及说明书修订指令" },
  "referral": { group: "assessment", label: "转介程序决议", tip: "欧盟成员国之间产生安全/有效性争议时的统一仲裁程序文件" },
  "public-statement": { group: "assessment", label: "公开声明", tip: "EMA 就产品安全、撤市或突发监管事件发布的正式通告" },
  "smop-initial": { group: "assessment", label: "首次上市推荐摘要", tip: "Initial Summary of Opinion，CHMP 建议批准新药上市的首次通告" },
  "smop": { group: "assessment", label: "委员会意见摘要", tip: "Summary of Opinion，CHMP 就适应症扩展或变更的正式意见" },
  "scientific-discussion": { group: "assessment", label: "科学讨论 (早期 EPAR)", tip: "早期 EPAR 报告中关于药学、非临床和临床评价的详细讨论" },
  "scientific-discussion-variation": { group: "assessment", label: "变更科学讨论", tip: "重大变更申请的技术审评讨论记录" },
  "orphan-designation": { group: "assessment", label: "孤儿药资格认定", tip: "EMA 授予罕见病药物资格认定及市场独占保护的决定" },
  "orphan-maintenance-report": { group: "assessment", label: "孤儿药维持报告", tip: "上市时核实罕见病药物是否继续符合孤儿药标准的审查报告" },
  "orphan-maintenance-report-post": { group: "assessment", label: "上市后孤儿药维持报告", tip: "上市后阶段孤儿药资格维持状态的审查报告" },
  "orphan-review": { group: "assessment", label: "孤儿药审查摘要", tip: "孤儿药资格审查的简要总结" },
  "withdrawal-report": { group: "assessment", label: "撤回申请评估报告", tip: "申请人在获批前主动撤回上市申请的技术评估报告" },
  "withdrawal-letter": { group: "assessment", label: "撤回申请公函", tip: "药企向 EMA 说明撤回申报理由的正式信函" },
  "chmp-annex": { group: "assessment", label: "CHMP 意见附件", tip: "人用药品委员会正式意见的附录与技术条件" },
  "conditions-member-states": { group: "assessment", label: "成员国附加上市条件", tip: "欧盟各成员国针对特定药品附加的上市后要求" },
  "opinion-on-any-scientific-matter": { group: "assessment", label: "特别科学咨询意见", tip: "按欧盟法规针对重大前沿科学议题发表的咨询意见" },
  "mrl-report": { group: "assessment", label: "最高残留限量报告 (MRL)", tip: "动物用药在食品动物组织中的最大残留限量技术报告" },
  "mrl-opinion": { group: "assessment", label: "最高残留限量意见", tip: "兽药委员会 (CVMP) 针对 MRL 的正式推荐意见" },
  "mrl-summary": { group: "assessment", label: "最高残留限量摘要", tip: "MRL 技术标准的简明总结" },
  "mrl-divergent-opinion": { group: "assessment", label: "MRL 专家分歧意见", tip: "委员会专家就 MRL 投票时提出的少数派不同意见" },

  // 3. 药物警戒与安全监管 (safety)
  "rmp": { group: "safety", label: "风险管理计划 (RMP)", tip: "药品全生命周期安全性监测与风险最小化措施" },
  "rmp-summary": { group: "safety", label: "风险管理计划公众摘要", tip: "面向公众发布的 RMP 简明公开版本" },
  "dhpc": { group: "safety", label: "致医务人员函 (DHPC)", tip: "重大用药安全隐患、严重不良反应或召回直接发给医生的警示函" },
  "psusa": { group: "safety", label: "定期安全性评估 (PSUSA)", tip: "定期安全性更新报告 (PSUR) 单一评估程序的技术审查结论" },
  "prac-recommendation": { group: "safety", label: "PRAC 安全委员会建议", tip: "药物警戒风险评估委员会 (PRAC) 的安全审查与行动建议" },
  "additional-monitoring": { group: "safety", label: "附加监测说明 (黑三角)", tip: "需要重点监测的新药/生物药黑三角附加监测说明" },
  "medication-error": { group: "safety", label: "用药差错防范文件", tip: "防止药品混淆、处方或给药差错的专项指引" },
  "covid-19-vaccine-safety-update": { group: "safety", label: "新冠疫苗安全月度更新", tip: "新冠疫苗安全性月度追踪与统计报告" },

  // 4. 草药与传统植物药 (HMPC)
  "herbal-monograph": { group: "herbal", label: "草药专论", tip: "HMPC 发布的欧盟中草药专论标准与安全性评价规范" },
  "herbal-report": { group: "herbal", label: "草药评估报告", tip: "草药专论配套的技术依据与完整安全性评估报告" },
  "herbal-opinion": { group: "herbal", label: "草药委员会意见", tip: "草药药品委员会 (HMPC) 针对草药制剂的技术裁定" },
  "herbal-summary": { group: "herbal", label: "草药公众摘要", tip: "面向公众和患者的草药药效与用药安全总结" },
  "herbal-references": { group: "herbal", label: "草药参考文献", tip: "草药专论评估中引用的科学文献目录" },
  "herbal-call-data": { group: "herbal", label: "草药数据征集", tip: "编制草药专论草案前向行业公开征集有效性/安全性数据" },
  "herbal-comments": { group: "herbal", label: "草药征求意见反馈", tip: "草药指南在征求意见期收到的行业反馈汇总" },
  "herbal-list-entry": { group: "herbal", label: "草药清单条目", tip: "欧盟传统草药制剂法定清单技术条目" },

  // 5. 日常行政、会议与审批流水 (administrative)
  "pip-decision": { group: "administrative", label: "儿科计划 (PIP) 决定", tip: "【量大 6500+】儿科研究计划单个药品批准/豁免行政决定书" },
  "presentation": { group: "administrative", label: "幻灯片 / 培训 PPT", tip: "【量大 6300+】EMA 外部研讨会、培训及工作坊幻灯片" },
  "other": { group: "administrative", label: "其他杂项文件", tip: "【量大 4400+】官方未明确归类的其他行政/附件文件" },
  "variation-report": { group: "administrative", label: "常规变更报告", tip: "【量大 3300+】已批准微小/常规变更的技术与行政记录" },
  "procedural-steps-after": { group: "administrative", label: "批准后程序步骤记录", tip: "【量大 3200+】上市许可批准后的行政步骤与时间线" },
  "agenda": { group: "administrative", label: "会议日程", tip: "【量大 2300+】各科学委员会日常月度会议议程列表" },
  "overview": { group: "administrative", label: "产品与主题概览", tip: "【量大 2200+】EMA 官网产品或监管主题的文字综述页" },
  "all-authorised-presentations": { group: "administrative", label: "所有上市包装规格", tip: "【量大 2200+】药品在欧盟批准的所有包装规格与剂型清单" },
  "product-information": { group: "administrative", label: "产品信息 (说明书/标签)", tip: "【量大 2200+】SmPC 说明书、标签与包装传单合集文本" },
  "report": { group: "administrative", label: "综合报告 / 工作总结", tip: "【量大 1800+】EMA 发布的一般性行政工作总结与统计报告" },
  "press-release": { group: "administrative", label: "新闻稿", tip: "【量大 1700+】EMA 面向媒体公开发布的新闻通告" },
  "minutes": { group: "administrative", label: "会议纪要", tip: "【量大 1500+】CHMP / PRAC / CAT 等委员会会议的正式纪要" },
  "committee-report": { group: "administrative", label: "委员会工作报告", tip: "各科学委员会月度工作动态与审批统计" },
  "template-form": { group: "administrative", label: "申请表格与模板", tip: "监管申报、变更申请及问答填报的标准格式模板" },
  "procedural-steps-before": { group: "administrative", label: "批准前程序步骤记录", tip: "上市许可审评过程中的行政程序时间线" },
  "comments": { group: "administrative", label: "公众征询反馈汇总", tip: "外部公众对指南草案提交的所有评论意见合集" },
  "pip-discontinuation": { group: "administrative", label: "PIP 终止决定", tip: "儿科研究计划终止履行的行政批复" },
  "product-information-tracked-changes": { group: "administrative", label: "产品信息修订标记版", tip: "说明书修改前后的对比划线标记版本" },
  "newsletter": { group: "administrative", label: "官方通讯简报", tip: "定期发布的行业监管简报" },
  "work-programme": { group: "administrative", label: "工作规划 / 预算计划", tip: "EMA 多年期工作规划与委员会年度行动方案" },
  "steps-after-cutoff": { group: "administrative", label: "截点后程序记录", tip: "审评时间截点后的行政程序步骤" },
  "pip-compliance": { group: "administrative", label: "PIP 合规性核查报告", tip: "上市申报前对儿科计划执行情况的合规核对" },
  "sop": { group: "administrative", label: "EMA 内部 SOP", tip: "EMA 机构内部运营的标准作业程序" },
  "annual-report": { group: "administrative", label: "EMA 年度报告", tip: "欧洲药品管理局历年官方年度工作总览报告" },
  "pip-summary": { group: "administrative", label: "PIP 简要说明", tip: "儿科研究计划的公众简述" },
  "leaflet": { group: "administrative", label: "患者用药指导传单", tip: "面向患者的用药安全或疾病普及传单" },
  "procurement": { group: "administrative", label: "招投标采购公告", tip: "EMA 机构采购与商业招标公告" },
  "recruitment": { group: "administrative", label: "招聘公告", tip: "EMA 人员招聘岗位说明" },
  "win": { group: "administrative", label: "工作指导书 (WIN)", tip: "EMA 内部业务操作细则 (Work Instruction)" },
  "position": { group: "administrative", label: "立场文件", tip: "EMA 针对特定前沿监管热点问题阐述的原则立场" },
};

function typeMeta(value) {
  if (TYPE_META[value]) return TYPE_META[value];
  let group = "administrative";
  if (value && value.startsWith("herbal-")) group = "herbal";
  return {
    group,
    label: value || "—",
    tip: value || "",
  };
}

function typeLabel(value) {
  return typeMeta(value).label;
}

const TYPE_OPTIONS = Object.entries(TYPE_META).map(([k, v]) => [k, v.label]);

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

/* 最近一次 /api/summary 数据，供设置页与同步对话框共用同一份类型清单 */
let latestSummary = null;

/* 构建类型选项列表 [{value, label, tip, group, count}]：
 * 聚合官方数据源统计（type_distribution.json）、数据库现有类型与元数据字典。 */
function buildTypeOptions(summaryData, fallbackExtra = []) {
  const dist = (summaryData && summaryData.feed_types && summaryData.feed_types.counts) || null;
  const optionsMap = new Map();

  if (dist && Object.keys(dist).length) {
    for (const [v, n] of Object.entries(dist)) {
      const meta = typeMeta(v);
      optionsMap.set(v, {
        value: v,
        label: meta.label,
        tip: meta.tip,
        group: meta.group,
        count: n,
      });
    }
  }

  // 确保所有内置已知类型及 fallbackExtra 在选项集合中都有一席之地
  const allKnown = new Set([
    ...Object.keys(TYPE_META),
    ...(summaryData?.filter_options?.types || []),
    ...fallbackExtra,
  ]);
  for (const v of allKnown) {
    if (!optionsMap.has(v)) {
      const meta = typeMeta(v);
      optionsMap.set(v, {
        value: v,
        label: meta.label,
        tip: meta.tip,
        group: meta.group,
        count: (dist && dist[v]) != null ? dist[v] : null,
      });
    }
  }

  return Array.from(optionsMap.values());
}

/* 将类型按 5 个业务维度分组，并设定合理的排序权重 */
function groupTypeOptions(options) {
  const grouped = {
    guidelines: [],
    assessment: [],
    safety: [],
    herbal: [],
    administrative: [],
  };

  for (const item of options) {
    const g = item.group || "administrative";
    if (grouped[g]) {
      grouped[g].push(item);
    } else {
      grouped.administrative.push(item);
    }
  }

  // 1. 核心指南组 (CHMP)：科学指南 > 监管程序指南 > 问答
  const coreOrder = [
    "scientific-guideline",
    "regulatory-procedural-guideline",
    "medicine-qa",
  ];
  grouped.guidelines.sort((a, b) => {
    const ia = coreOrder.indexOf(a.value);
    const ib = coreOrder.indexOf(b.value);
    if (ia !== -1 && ib !== -1) return ia - ib;
    if (ia !== -1) return -1;
    if (ib !== -1) return 1;
    return (b.count || 0) - (a.count || 0);
  });

  // 2. 审评技术组：评估报告 > 科学结论 > 转介程序 > 公开声明 > 意见摘要
  const assessOrder = [
    "assessment-report",
    "scientific-conclusion",
    "referral",
    "public-statement",
    "smop-initial",
    "smop",
    "orphan-designation",
  ];
  grouped.assessment.sort((a, b) => {
    const ia = assessOrder.indexOf(a.value);
    const ib = assessOrder.indexOf(b.value);
    if (ia !== -1 && ib !== -1) return ia - ib;
    if (ia !== -1) return -1;
    if (ib !== -1) return 1;
    return (b.count || 0) - (a.count || 0);
  });

  // 3. 警戒组：RMP > RMP摘要 > DHPC > PSUSA > PRAC建议
  const safetyOrder = ["rmp", "rmp-summary", "dhpc", "psusa", "prac-recommendation"];
  grouped.safety.sort((a, b) => {
    const ia = safetyOrder.indexOf(a.value);
    const ib = safetyOrder.indexOf(b.value);
    if (ia !== -1 && ib !== -1) return ia - ib;
    if (ia !== -1) return -1;
    if (ib !== -1) return 1;
    return (b.count || 0) - (a.count || 0);
  });

  // 4. 草药专论组 (HMPC)：专论 > 评估报告 > 委员会意见 > 公众摘要 > 参考文献等
  const herbalOrder = [
    "herbal-monograph",
    "herbal-report",
    "herbal-opinion",
    "herbal-summary",
    "herbal-references",
    "herbal-call-data",
    "herbal-comments",
    "herbal-list-entry",
  ];
  grouped.herbal.sort((a, b) => {
    const ia = herbalOrder.indexOf(a.value);
    const ib = herbalOrder.indexOf(b.value);
    if (ia !== -1 && ib !== -1) return ia - ib;
    if (ia !== -1) return -1;
    if (ib !== -1) return 1;
    return (b.count || 0) - (a.count || 0);
  });

  // 5. 日常行政组：按数量降序排
  grouped.administrative.sort((a, b) => (b.count || 0) - (a.count || 0));

  return grouped;
}

/* 实时计算并更新类型选择器的勾选数量与文档数预估摘要 */
function updateTypePickerSummary(container) {
  if (!container) return;
  const summaryEl = $(`#${container.id}-summary`);
  if (!summaryEl) return;

  const checkedBoxes = container.querySelectorAll("input:checked");
  const count = checkedBoxes.length;
  let totalDocs = 0;
  let hasAdmin = false;

  checkedBoxes.forEach((cb) => {
    totalDocs += Number(cb.dataset.count) || 0;
    if (cb.dataset.group === "administrative") {
      hasAdmin = true;
    }
  });

  if (count === 0) {
    summaryEl.innerHTML = `已选 <strong>0</strong> 项 <span class="muted">（留空将使用系统默认配置）</span>`;
  } else {
    let html = `已选 <strong>${count}</strong> 个类型 · 预计覆盖约 <strong>${totalDocs.toLocaleString()}</strong> 份文档`;
    if (hasAdmin) {
      html += ` <span class="badge warn" style="margin-left:8px;" title="包含日常会议、PPT或单药批文等日常运营文件">⚠️ 包含海量行政个案</span>`;
    }
    summaryEl.innerHTML = html;
  }
}

/* 渲染按业务分级卡片呈现的复选框列表 */
function renderTypeCheckboxGroup(container, options, checkedSet) {
  const grouped = groupTypeOptions(options);

  let html = "";
  for (const group of TYPE_GROUPS) {
    const items = grouped[group.id] || [];
    if (!items.length) continue;

    const checkedInGroup = items.filter((it) => checkedSet.has(it.value));
    const isDetails = group.id === "administrative";
    const openAttr = isDetails ? (checkedInGroup.length > 0 ? " open" : "") : "";

    const cardTag = isDetails ? "details" : "div";
    const headerTag = isDetails ? "summary" : "div";

    html += `
      <${cardTag} class="type-group-card group-${esc(group.id)}" data-group-id="${esc(group.id)}"${openAttr}>
        <${headerTag} class="type-group-header">
          <div class="type-group-title">
            <span>${esc(group.title)}</span>
            <span class="badge ${esc(group.badgeClass)} type-group-badge">${esc(group.badge)}</span>
          </div>
          <div class="type-group-actions">
            <button type="button" class="btn-group-action" data-action="select" data-group="${esc(group.id)}">全选本组</button>
            <button type="button" class="btn-group-action" data-action="deselect" data-group="${esc(group.id)}">清空本组</button>
          </div>
        </${headerTag}>
        <div class="type-group-desc">${esc(group.desc)}</div>
        ${isDetails ? `<div class="type-warning-banner">⚠️ 提示：日常行政、会议与审批流水包含 50,000+ 篇文件（会议纪要、PPT、单药批文等），非全站镜像需求不建议全选。</div>` : ""}
        <div class="type-items-grid">
          ${items
            .map(
              (it) => `
            <label class="type-item" title="${esc(it.tip ? `${it.label} [${it.value}]\n${it.tip}` : it.value)}">
              <input type="checkbox" value="${esc(it.value)}" data-group="${esc(group.id)}" data-count="${it.count || 0}" ${
                checkedSet.has(it.value) ? "checked" : ""
              }>
              <span class="type-title">${esc(it.label)}</span>
              ${it.count != null ? `<span class="type-count">(${esc(String(it.count))})</span>` : ""}
            </label>`
            )
            .join("")}
        </div>
      </${cardTag}>`;
  }

  container.innerHTML = html;
  updateTypePickerSummary(container);
}

const HAS_FEED_COUNTS = (s) => s && s.feed_types && Object.keys(s.feed_types.counts || {}).length > 0;

function populateTypeSelects(summaryData) {
  latestSummary = summaryData;
  const typeSelect = $("#doc-type");
  const currentType = typeSelect.value;
  const options = buildTypeOptions(summaryData, summaryData.filter_options?.types || []);
  const grouped = groupTypeOptions(options);

  // 文档库标签页中的下拉筛选：按 4 级业务分组结构化呈现
  let html = `<option value="">全部类型</option>`;
  for (const group of TYPE_GROUPS) {
    const items = grouped[group.id] || [];
    if (!items.length) continue;
    html += `<optgroup label="${esc(group.title)}">`;
    for (const item of items) {
      html += `<option value="${esc(item.value)}">${esc(item.label)}${item.count != null ? ` (${item.count})` : ""}</option>`;
    }
    html += `</optgroup>`;
  }
  typeSelect.innerHTML = html;
  typeSelect.value = currentType;

  // 同步对话框中的类型勾选框：默认勾选设置中的 default_types（而非全部类型）。
  // 对话框打开期间不重建，避免总览定时刷新（每 10 秒）静默重置用户勾选；
  // 用户勾选变化实时存入 data-checked（见下方 change 监听），重建时按其恢复。
  const box = $("#sync-types");
  if (!$("#sync-dialog").open) {
    const defaults = new Set(summaryData.config?.default_types || []);
    const checked = typeof box.dataset.checked === "string"
      ? new Set(box.dataset.checked.split(",").filter(Boolean))
      : defaults;
    renderTypeCheckboxGroup(box, options, checked);
  }
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

/* ---------- 类型选择器交互与预设事件绑定 ---------- */

function bindTypePickerEvents(containerId) {
  const container = $(`#${containerId}`);
  if (!container) return;

  container.addEventListener("change", () => {
    container.dataset.checked = [...container.querySelectorAll("input:checked")].map((el) => el.value).join(",");
    updateTypePickerSummary(container);
  });

  container.addEventListener("click", (e) => {
    const btn = e.target.closest(".btn-group-action");
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();

    const groupId = btn.dataset.group;
    const action = btn.dataset.action;
    const inputs = container.querySelectorAll(`input[data-group="${groupId}"]`);
    inputs.forEach((input) => {
      input.checked = action === "select";
    });

    if (groupId === "administrative") {
      const details = container.querySelector("details.group-administrative");
      if (details && action === "select") details.open = true;
    }

    container.dataset.checked = [...container.querySelectorAll("input:checked")].map((el) => el.value).join(",");
    updateTypePickerSummary(container);
  });
}

function initPresetToolbars() {
  document.querySelectorAll(".type-picker-presets").forEach((toolbar) => {
    toolbar.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-preset]");
      if (!btn) return;
      e.preventDefault();
      const targetId = toolbar.dataset.target;
      const container = $(`#${targetId}`);
      if (!container) return;

      const presetId = btn.dataset.preset;
      const preset = TYPE_PRESETS.find((p) => p.id === presetId);
      if (!preset) return;

      const targetSet = new Set(preset.types);
      const inputs = container.querySelectorAll('input[type="checkbox"]');
      inputs.forEach((input) => {
        input.checked = targetSet.has(input.value);
      });

      const adminDetails = container.querySelector("details.group-administrative");
      if (adminDetails) {
        const adminChecked = adminDetails.querySelectorAll("input:checked").length > 0;
        adminDetails.open = adminChecked;
      }

      container.dataset.checked = [...container.querySelectorAll("input:checked")].map((el) => el.value).join(",");
      updateTypePickerSummary(container);
    });
  });
}

bindTypePickerEvents("sync-types");
bindTypePickerEvents("set-types");
initPresetToolbars();

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

  // 默认文档类型：与同步对话框使用同一份类型清单（数据源实际类型 + 文档数）
  const setBox = $("#set-types");
  const current = new Set(v.filters.default_types || []);
  const options = buildTypeOptions(latestSummary, v.filters.default_types || []);
  if (HAS_FEED_COUNTS(latestSummary)) setBox.title = "括号内为该类型在最近一次同步数据源中的文档数";
  renderTypeCheckboxGroup(setBox, options, current);
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
        showToast("已请求取消，正在停止下载…");
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
