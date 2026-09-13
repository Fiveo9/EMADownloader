本文件记录值得关注的版本变更。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/)，并遵循[语义化版本](https://semver.org/lang/zh-CN/)。为降低个人维护成本，内容保持轻量。

开发中的改动先记入 `# [Unreleased]`，发版时再改为对应的版本号小节。

# \[Unreleased\]

# v0.1.3 - 2026-09-13

- 重构：Web 界面文档类型选择器全面升级为 5 级业务场景结构化分组——
  1. `1. 核心法规与指导原则 (CHMP)`：纯粹化保留通用核心三剑客（科学指南 `scientific-guideline`、监管程序指南 `regulatory-procedural-guideline`、问答文件 `medicine-qa`），点击全选即可精准覆盖 95% 以上通用法规检索需求；
  2. `2. 审评审批与科学结论`：涵盖公开审评报告 (EPAR)、科学结论、转介仲裁决议、孤儿药认定等审评技术材料；
  3. `3. 药物警戒与安全监管`：涵盖风险管理计划 (RMP)、致医务人员函 (DHPC)、定期安全性评估 (PSUSA) 等安全文件；
  4. `4. 草药与传统植物药 (HMPC)`：草药专论自立门户独立成组，与通用法规彻底解耦，适用于中草药与天然药物出海申报；
  5. `5. 日常行政、会议与审批流水`：包含 50,000+ 篇日常运营记录（会议日程纪要、演示培训 PPT、单药 PIP 审批决定、微小变更流水等），默认折叠并附带明显警示标语，防止全站镜像误选导致磁盘溢出。
- 新增：场景快捷预设按钮（Presets）——顶部提供「🎯 核心法规（推荐）」、「🔍 法规 + 审评调研」、「🛡️ 药物警戒专线」、「🌿 草药专论」及「🧹 清空已选」一键切换，解决多达 80+ 个选项难以选择的痛点。
- 新增：实时动态数量估算——选择器顶部实时显示已选类型数及预计覆盖文档量（例如“已选 3 个类型 · 预计覆盖约 4,012 份文档”），勾选行政流水类时动态点亮警告徽章。
- 新增：全量专业中文释义与悬浮业务说明（Tooltip）——86 种 EMA 原始技术 slug 全部映射规范中文名，鼠标悬停即时展示详细业务功能说明。
- 优化：文档库（Library）标签页下拉筛选菜单支持 `<optgroup>` 层次化分组，与选择器分类严格对齐。

# v0.1.2 - 2026-09-05

- 新增：Web 界面「设置」页与同步对话框使用同一份类型清单（数据源实际类型 + 文档数），并补充 README 文档类型速查表——此前设置页为静态 9 种、对话框为数据源生成的 86 种，口径不一致易造成理解困惑。
- 修复：问答文档归档与一级目录编号——`medicine-qa`（EMA 当前的问答类型标识）此前未映射、会落入其他目录；现与公开声明同归 `03_QA_Public_Statements`。同时移除数据源已不存在的旧类型标识（q-and-a / legislation / reflection-paper 等）的目录映射，并将一级目录编号紧凑化（`03_QA_Public_Statements`、`04_Other_Documents`）。README 资料库目录结构与架构图同步更新。
- 新增：同步对话框的类型选项按数据源实际类型生成——每次同步后统计各类型文档数（`90_Raw_JSON/type_distribution.json`，经 `/api/summary` 提供），选项按数量降序展示并标注数量，数据源中不存在的类型不再出现，"选了没结果"一眼可见。
- 修复：总览定时刷新（每 10 秒）会静默重置同步对话框中正在编辑的类型勾选——对话框打开期间不再重建选项，用户勾选实时保存、重建后恢复；类型字段增加「留空使用默认」提示。
- 修复：同步对话框打开时类型勾选框误勾选全部类型（与注释意图相反的 `concat` 笔误），现按设置中的默认文档类型勾选。
- 修复：同步对话框/设置的文档类型清单与 EMA 数据源实际标识对齐——`q-and-a`、`legislation`、`eu-legislation`、`reflection-paper`、`position-paper`、`concept-paper` 等旧标识在数据源中已不存在（问答文档现标识为 `medicine-qa`，反思/概念文件归入 `scientific-guideline`），按这些类型筛选会得到 0 条结果，导致"全选"与"按默认设置"的同步结果完全相同。默认选项改为数据源中真实存在的类型。

# v0.1.1 - 2026-09-05

- 修复：同步任务在「抓取数据源」阶段假死——EMA 反爬偶发 403 拦截代理出口 IP，且不稳定的代理连接可能以涓流速率传输导致读超时永不触发。现改为：403/429 时自动改用直连重试；每次尝试增加总耗时预算（`timeout × 3`，下限 90 秒），超时按失败重试；抓取阶段支持任务取消（Web 界面「取消任务」在卡住时可立即生效）。
- 修复：「取消任务」后长期停留在「等待当前文件完成」——进行中的下载现会在下一个数据块边界立即中止（几秒内），未开始的任务直接丢弃；取消的文件不计入失败统计。
- 修复：下载/抓取对"涓流式"停滞连接的鲁棒性——60 秒窗口内接收不足 64 KB 判定为停滞，中止当前尝试并自动重试。为此请求改用 `Accept-Encoding: identity` 并逐网络读取数据块（`iter_raw`），确保取消与停滞检查在每个读取间隙生效。
- 变更：User-Agent 改为纯浏览器标识（Chrome），不再附加 `EMADownloader/0.1.0` 标记；移除从未生效的 `network.user_agent` 配置项。
- 新增：Windows 免安装绿色版支持——PyInstaller 打包 `EMA文件库.exe`（onedir、双击启动并自动打开浏览器），frozen 模式下配置/资料库/分类规则锚定 exe 目录，端口被占用时自动顺延；`build_exe.bat` 一键本地构建，`release.yml` 在推送 `v*` 标签时自动构建并附到 GitHub Release。
- 新增：`启动Web界面.bat` 一键启动脚本（自动检测 Python 并安装依赖）。
- 新增：本地 Web 图形界面（`pip install -e ".[ui]"` 后运行 `ema-downloader-ui`），提供总览统计、文档库检索（关键词 / 类型 / 下载状态 + 分页 + 打开本地文件）、任务实时进度与日志、任务取消与历史记录；服务仅绑定 127.0.0.1，可选依赖仅为 Flask。
- 新增：Web 界面「设置」页，图形化管理网络参数（并发 / 超时 / 重试 / 代理）、默认筛选与存储 / 分类路径；仅写入 gitignored 的 `settings.local.toml` 覆盖层（保留已有键与注释，代理以掩码显示、不回传明文），保存即生效。
- 新增：`Downloader.download_batch` 与 `Downloader.verify_library` 支持协作式取消（`cancel_check` / `progress_callback` 参数），CLI 行为不变。
- 新增：`Database.get_documents` 分页参数 `offset`，以及 `count_documents` / `get_last_sync` / `get_filter_options` 查询。

# v0.1.0 - 2026-09-05

首个开源版本。

- 新增：基于 EMA 官方 JSON 数据源的元数据同步与增量识别（文档 ID / 更新时间 / SHA-256），支持断点续传。
- 新增：并发流式下载器，含 PDF 完整性校验、原子落地、429 指数退避与可配置请求延迟。
- 新增：两级自动化分类归档，规则可经 `config/classification_rules.csv` 自定义。
- 新增：多工作表 Excel（内置本地超链接）/ CSV / SQLite 索引导出，同步 JSON 审计报告与失败追踪。
- 新增：CLI 子命令 `sync` / `metadata` / `download` / `organize` / `export` / `verify`，支持 dry-run、limit、status、updated-since、keyword、proxy 等参数。
- 新增：GitHub Actions CI（ruff + pytest，Python 3.10–3.14）。
- 新增：SOCKS5 代理支持拆分为可选依赖（`pip install -e ".[socks]"`）。

