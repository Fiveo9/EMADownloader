# EMA Regulatory Document Downloader & Organizer
### EMA 监管文件及科学指导原则下载整理工具

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-brightgreen.svg)](https://www.python.org/)

面向注册法规（RA）、药政申报、医学研发与质量保证团队的自动化 EMA 资料库同步与管理工具。基于 EMA 官方结构化 JSON 数据源，实现科学指导原则与监管程序性文件的增量同步、流式下载、完整性校验、两级层级分类归档以及多工作表带本地超链接的 Excel/CSV 索引生成。

参考项目：[Fiveo9/FDADownloader](https://github.com/Fiveo9/FDADownloader)

---

## 核心特性

- **官方 JSON 数据驱动**：无需 Selenium 浏览器仿真或 DOM 网页抓取，直接利用 EMA 官方定时更新的机器可读 JSON 数据源（每日两次更新，包含 70,000+ 文档元数据）。
- **智能增量同步**：基于 EMA ID、官方更新时间戳、URL 变动以及文件 SHA-256 哈希比对，自动识别新增、更新或未变动文件，支持断点续传与重试，再次运行毫秒级跳过已下载未变动文档。
- **流式下载与安全校验**：
  - 流式分块（1MB chunk）写入临时文件 `.tmp`，下载完成后执行原子重命名（`os.replace`）；
  - 自动检测 HTTP 状态、Content-Type 与文件大小；
  - 验证 `%PDF-` 魔法文件头，防止反爬 WAF 返回的 HTML 错误页/跳转页被误存为伪损坏 PDF；
  - 实时计算并比对 SHA-256 校验和。
- **两级自动化分类体系**：
  - **第一级（文档类型）**：科学指导原则（`01_Scientific_Guidelines`）、监管程序性指南（`02_Regulatory_Procedural_Guidelines`）、反思/概念文件（`03_Reflection_Position_Concept_Papers`）、Q&A/声明（`04_QA_Public_Statements`）等；
  - **第二级（科学领域）**：支持外部 CSV 规则配置（优先级、参考号/URL/标题关键词），细分为 Quality（质量）、Nonclinical（非临床）、Clinical（临床有效与安全）、Biologicals（生物制品/疫苗）、Multidisciplinary（多学科/生物类似药）、ICH、Herbal（草药）等。
- **结构化索引导出**：
  - 自动生成 SQLite 索引数据库（`ema_documents.sqlite3`）；
  - 导出多工作表格式化 Excel 索引（`EMA_Document_Index.xlsx`），包含：*All Documents*、*Scientific Guidelines*、*Regulatory Procedural*、*Draft and Consultation*、*Failed Downloads*、*Sync Summary*，内置一键打开本地文件的 `=HYPERLINK(...)` 超链接；
  - 导出完整清单 `download_manifest.csv` 与错误记录 `download_failures.csv`。
- **代理与网络自适应**：原生支持 HTTP/SOCKS 代理、环境变量（`HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY`）及本地常用代理自动探测。

---

## 目录结构

```text
EMA_Regulatory_Library/
├── 00_Index/
│   ├── ema_documents.sqlite3               # SQLite 本地元数据索引库
│   ├── EMA_Document_Index.xlsx             # 多工作表格式化 Excel 索引（带超链接）
│   ├── EMA_Document_Index.csv              # CSV 索引清单
│   └── sync_report_YYYYMMDD_HHMMSS.json    # 本次同步详细报告
├── 01_Scientific_Guidelines/               # 科学指导原则
│   ├── 01_Quality/                         # 质量/CMC
│   ├── 02_Nonclinical/                     # 非临床药理毒理
│   ├── 03_Clinical_Efficacy_Safety/        # 临床有效性与安全性
│   ├── 04_Biologicals/                     # 生物制品与疫苗
│   ├── 05_Multidisciplinary/               # 多学科/生物类似药
│   ├── 06_ICH/                             # ICH 协调指南
│   ├── 07_Herbal_Medicines/                # 草药制品
│   └── 99_Uncategorized/                   # 未分类科学指南
├── 02_Regulatory_Procedural_Guidelines/    # 监管与程序性指导原则
├── 03_Reflection_Position_Concept_Papers/  # 反思/立场/概念文件
├── 04_QA_Public_Statements/                # 问答与公开声明
├── 05_EU_Legislation_Optional/             # 欧盟法规
├── 90_Raw_JSON/                            # 官方原始 JSON 快照
│   └── documents-output-json-report_en_YYYYMMDD.json
└── 99_Failed_Downloads/                    # 失败与审计日志
    ├── download_failures.csv               # 失败记录与原因
    └── download_manifest.csv               # 本地文件清单与哈希
```

---

## 安装说明

### 1. 运行环境要求
- Python 3.10 或更高版本（支持 Python 3.10 / 3.11 / 3.12 / 3.13 / 3.14）

### 2. 安装项目与依赖

```bash
git clone https://github.com/Fiveo9/EMADownloader.git
cd "EMA Downloader"

# 安装生产与开发依赖
pip install -e .
```

---

## 快速上手与使用示例

### 1. 预览同步（Dry-run）
只获取官方元数据并进行分析规划，不下载任何实际 PDF 文件：

```bash
ema-downloader sync \
  --types scientific-guideline regulatory-procedural-guideline \
  --limit 10 \
  --dry-run
```

### 2. 执行小批量同步
下载首批 10 份指导原则并生成 Excel 索引：

```bash
ema-downloader sync \
  --types scientific-guideline regulatory-procedural-guideline \
  --limit 10
```

再次运行相同命令，工具将自动比对哈希与更新时间，智能跳过已存在且未发生变化的文件：

```bash
ema-downloader sync \
  --types scientific-guideline regulatory-procedural-guideline \
  --limit 10
# 输出：Skipped Documents: 10 unchanged (0 downloaded, 0 errors)
```

### 3. 按条件筛选同步

- **按发布/更新状态筛选**（如仅已采纳的正式指南）：
  ```bash
  ema-downloader sync --status Adopted
  ```
- **按最后更新时间筛选**（增量同步最近更新）：
  ```bash
  ema-downloader sync --updated-since 2025-01-01
  ```
- **按关键词检索**：
  ```bash
  ema-downloader sync --keyword oncology
  ```
- **调整并发下载线程数**（默认 3 个线程，温和请求官方服务器）：
  ```bash
  ema-downloader sync --workers 4
  ```

### 4. 其它子命令

- **仅更新元数据（不下载 PDF）**：
  ```bash
  ema-downloader metadata
  ```
- **单独下载已规划或失败的文件**：
  ```bash
  ema-downloader download --limit 50
  ```
- **根据规则重新整理分类目录**：
  ```bash
  ema-downloader organize
  ```
- **重新导出 Excel/CSV 索引**：
  ```bash
  ema-downloader export --format all
  ```
- **校验本地所有文件完整性（大小、%PDF- 文件头、SHA-256）**：
  ```bash
  ema-downloader verify
  ```

---

## 配置说明

项目支持通过 `config/settings.toml` 和 `config/classification_rules.csv` 进行灵活定制：

### `config/settings.toml`
```toml
[sources]
documents_url = "https://www.ema.europa.eu/en/documents/report/documents-output-json-report_en.json"
general_url = "https://www.ema.europa.eu/en/documents/report/general-json-report_en.json"

[storage]
library_dir = "EMA_Regulatory_Library"

[network]
user_agent = "Mozilla/5.0 ... EMADownloader/0.1.0"
timeout = 30.0
workers = 3
# 留空将自动尝试系统代理及 127.0.0.1:7890
proxy = ""

[filters]
default_types = [
    "scientific-guideline",
    "regulatory-procedural-guideline"
]
```

### `config/classification_rules.csv`
定义指导原则第二层领域的匹配优先级和关键词：

```csv
Priority,Field,Keywords,Folder
10,Quality,"quality;manufacture;stability;impurity;specification;active substance",01_Quality
20,Nonclinical,"non-clinical;toxicology;pharmacology;safety pharmacology",02_Nonclinical
30,Clinical,"clinical;efficacy;safety;trial;endpoint;pharmacovigilance",03_Clinical_Efficacy_Safety
40,Biologicals,"biological;vaccine;cell therapy;gene therapy;atmp;plasma",04_Biologicals
50,Multidisciplinary,"multidisciplinary;biosimilar;paediatric;combination",05_Multidisciplinary
60,ICH,"ICH;q1;q2;q3;q4;s1;s2;s3;e1;e2;e3;e6;m1;m4",06_ICH
70,Herbal,"herbal;HMPC;traditional herbal;plant",07_Herbal_Medicines
```

---

## 测试套件

运行完整自动化测试（包含配置、规范化、分类、数据库操作、流式下载、Excel 导出与命令行全链路）：

```bash
pytest
```

---

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。
