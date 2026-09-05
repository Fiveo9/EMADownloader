本文件记录值得关注的版本变更。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/)，并遵循[语义化版本](https://semver.org/lang/zh-CN/)。为降低个人维护成本，内容保持轻量。

开发中的改动先记入 `# [Unreleased]`，发版时再改为对应的版本号小节。

# \[Unreleased\]

# v0.1.0 - 2026-09-05

首个开源版本。

- 新增：基于 EMA 官方 JSON 数据源的元数据同步与增量识别（文档 ID / 更新时间 / SHA-256），支持断点续传。
- 新增：并发流式下载器，含 PDF 完整性校验、原子落地、429 指数退避与可配置请求延迟。
- 新增：两级自动化分类归档，规则可经 `config/classification_rules.csv` 自定义。
- 新增：多工作表 Excel（内置本地超链接）/ CSV / SQLite 索引导出，同步 JSON 审计报告与失败追踪。
- 新增：CLI 子命令 `sync` / `metadata` / `download` / `organize` / `export` / `verify`，支持 dry-run、limit、status、updated-since、keyword、proxy 等参数。
- 新增：GitHub Actions CI（ruff + pytest，Python 3.10–3.14）。
- 新增：SOCKS5 代理支持拆分为可选依赖（`pip install -e ".[socks]"`）。