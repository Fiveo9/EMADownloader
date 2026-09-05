本文件记录值得关注的版本变更。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/)，并遵循[语义化版本](https://semver.org/lang/zh-CN/)。为降低个人维护成本，内容保持轻量。

开发中的改动先记入 `# [Unreleased]`，发版时再改为对应的版本号小节。

# \[Unreleased\]

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