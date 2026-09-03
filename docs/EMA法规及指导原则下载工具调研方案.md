# EMA 法规及指导原则下载整理工具：调研与实现方案

> 调研对象：参考 [Fiveo9/FDADownloader](https://github.com/Fiveo9/FDADownloader)，设计一个用于下载、整理和维护 EMA 监管文件、科学指导原则及相关欧盟法规资料的小工具。
>
> 调研日期：2026-09-02
>
> 结论先行：**值得做，而且 EMA 版本不应照搬 FDA 项目的 Selenium 浏览器方案。EMA 已经提供官方、结构化、定时更新的 JSON 数据，完全可以做成更稳定的自动增量同步工具。**

---

## 1. 项目目标

做一个面向 RA、注册、药政和研发人员的本地资料库工具，解决下面几个问题：

- EMA 指导原则分散在多个网页和文档页面中；
- 很难知道哪些文件是新增、更新或已经失效；
- PDF 下载后缺少统一文件名和分类；
- 同一份资料容易被重复下载；
- 本地文件和官方网页之间缺少对应关系；
- 手工维护 Excel 清单成本高，也容易漏项。

建议产品名称：

```text
EMA Regulatory Document Downloader & Organizer
```

中文可称为：

```text
EMA 监管文件下载整理工具
```

这里建议使用“监管文件”而不是只叫“法规下载器”，因为 EMA 的资料既包括科学指导原则，也包括程序性指南、反思文件、Q&A、公开声明和药品相关文件；真正的欧盟法律法规则主要属于 EUR-Lex/EudraLex 体系。

---

## 2. 参考项目 FDADownloader 的可复用经验

参考项目由两个主要脚本组成：

- `FDADownloader.py`：抓取 FDA 指导原则页面、提取元数据和下载链接、生成 Excel、记录下载成功和失败状态；
- `FDAOrganizer.py`：读取 Excel，根据关键词或机构分类，把下载文件复制到结构化目录，并生成带本地链接的索引 Excel。

它的优点很实用：

1. 下载和整理分成两个步骤；
2. 支持增量运行，已有文件可以跳过；
3. 有下载 manifest 和失败清单；
4. 文件名包含日期和标题；
5. 分类规则可以通过 CSV 调整；
6. 支持 dry-run；
7. 最终产物不只是散落的 PDF，而是带索引的本地资料库。

这些设计应该保留。

但以下实现方式不建议原样复制：

- 依赖 Selenium 和 Chrome；
- 依赖人工筛选网页过滤器；
- 依赖手动点击 “Show All”；
- 通过网页表格结构抓取数据；
- 把完整文件内容一次性读入内存；
- 只通过文件名模糊匹配判断是否已经下载。

FDA 项目的浏览器方式是为了适应 FDA 页面和反爬行为。EMA 当前提供了官方机器可读数据，因此应该优先使用官方 JSON。

---

## 3. EMA 官方数据源调研结果

### 3.1 EMA 官方 JSON 数据页

EMA 官方页面明确提供面向自动化系统的 JSON 数据。页面说明：

- EMA 网站数据以 JSON 格式提供；
- 数据可用于自动获取文档和元数据；
- JSON 文件每天更新两次；
- 更新时间约为 Amsterdam time 06:00 和 18:00；
- 文档数据包括产品信息、指导原则以及其他监管和程序性文件。

官方说明页：

```text
https://www.ema.europa.eu/en/about-us/about-website/download-website-data-json-data-format
```

### 3.2 全部英文文档 JSON

```text
https://www.ema.europa.eu/en/documents/report/documents-output-json-report_en.json
```

实测返回结构：

```json
{
  "meta": {
    "total_records": 70444,
    "timestamp": "2026-09-02T05:45:08Z"
  },
  "data": []
}
```

单条记录大致包含：

```json
{
  "id": "2406",
  "name": "Investigation of chiral active substances",
  "type": "scientific-guideline",
  "medicine_name": "",
  "ema_product_number": "",
  "status": "Adopted",
  "consultation_date": "",
  "first_published_date": "1993-10-01T01:00:00Z",
  "last_updated_date": "1993-10-01T01:00:00Z",
  "reference_number": "3CC29A",
  "document_url": "https://www.ema.europa.eu/en/documents/scientific-guideline/investigation-chiral-active-substances_en.pdf"
}
```

实测文档数量和类型统计：

| 文档类型 | 数量 |
|---|---:|
| 全部英文文档 | 70,444 |
| `scientific-guideline` | 2,726 |
| `regulatory-procedural-guideline` | 766 |
| `pip-decision` | 6,585 |
| `presentation` | 6,337 |
| `other` | 4,412 |
| `psusa` | 3,444 |
| `variation-report` | 3,297 |
| `referral` | 2,885 |
| `orphan-designation` | 2,420 |
| `product-information` | 2,212 |

这里最重要的是：**EMA 已经在数据中提供了文档类型和下载 URL，不需要从标题猜测哪些是指导原则。**

### 3.3 Guidance and information JSON

```text
https://www.ema.europa.eu/en/documents/report/general-json-report_en.json
```

实测元数据：

```json
{
  "meta": {
    "total_records": 2059,
    "timestamp": "2026-09-02T06:00:54Z"
  }
}
```

这个数据集主要包含 EMA 普通页面，例如：

- 监管说明页面；
- 指导信息页面；
- 预批准阶段指导；
- 费用、提交和程序说明；
- 科学指导原则总览页；
- 其他不属于具体 PDF 文档的官网信息。

它不能完全替代文档 JSON，但适合用来补充“入口页”和“解释页”。

### 3.4 与药品、翻译和其他数据的关系

EMA 官方数据页还列出了其他数据集，包括：

- 与集中授权药品相关的文档及翻译；
- 非 EPAR 文档和翻译；
- 转介程序；
- PIP；
- 孤儿药资格认定；
- PSUSA；
- DHPC；
- 药品短缺；
- 新闻和活动。

第一版不建议全部纳入，否则工具很快会从“指导原则下载器”膨胀成完整 EMA 数据镜像。应该先聚焦指导原则和监管程序性文件。

---

## 4. EMA 资料范围应该怎么定义

“EMA 法规”这个说法在实际使用中有几种可能含义，建议拆开处理。

### 4.1 第一优先级：科学指导原则

对应数据类型：

```text
scientific-guideline
```

重点领域包括：

- Quality；
- Non-clinical；
- Clinical efficacy and safety；
- Biologicals；
- Multidisciplinary；
- ICH；
- Herbal medicinal products；
- 诊断、疫苗、先进疗法等特殊领域。

EMA 科学指导原则页面说明，这些指南用于帮助申请人准备人用药品上市许可申请，并反映 EMA 和欧盟成员国对质量、安全性和有效性要求的协调解释。[4]

### 4.2 第二优先级：监管程序性指南

对应数据类型：

```text
regulatory-procedural-guideline
```

可能涉及：

- 上市许可申请程序；
- 变更和续展；
- 产品信息；
- 提交格式；
- eCTD；
- 监管程序；
- 公开咨询；
- 各类申请和沟通要求。

### 4.3 第三优先级：相关文件

可以作为可选类型：

```text
reflection-paper
position-paper
concept-paper
q-and-a
public-statement
```

这些文件有助于理解监管趋势，但不应和已采纳的正式指导原则混在同一个目录里。

### 4.4 真正的欧盟法律法规

例如：

- Regulation (EU) No 536/2014；
- Directive 2001/83/EC；
- Regulation (EU) 2019/6；
- Commission Implementing Regulations；
- EudraLex Volume 1、Volume 2、Volume 3。

这部分更适合后续增加独立数据源：

- EUR-Lex；
- European Commission；
- EudraLex。

不要把 EMA 的科学指南 JSON 和欧盟正式法律文本混为一类。更准确的产品名称是：

```text
EMA 监管文件、指导原则及相关欧盟法规资料下载工具
```

---

## 5. 推荐的整体工作流

```text
下载 EMA 官方 JSON
        ↓
保存 JSON 快照和时间戳
        ↓
解析、标准化、筛选文档类型
        ↓
读取本地 SQLite 索引
        ↓
比较新增 / 更新 / 未变更 / 失效记录
        ↓
下载新增或更新的 PDF
        ↓
临时文件写入 + 文件大小检查 + SHA-256
        ↓
按监管领域分类归档
        ↓
生成 Excel / CSV / HTML 索引
        ↓
输出本次同步报告
```

推荐把“发现文档”和“下载文件”分离：

```text
sync metadata
sync documents
organize
export
```

这样用户可以先预览会下载什么，再决定是否真正下载。

---

## 6. 推荐的目录结构

```text
EMA_Regulatory_Library/
├── 00_Index/
│   ├── ema_documents.sqlite3
│   ├── EMA_Document_Index.xlsx
│   ├── EMA_Document_Index.csv
│   └── sync_report_YYYYMMDD_HHMMSS.json
├── 01_Scientific_Guidelines/
│   ├── 01_Quality/
│   ├── 02_Nonclinical/
│   ├── 03_Clinical_Efficacy_Safety/
│   ├── 04_Biologicals/
│   ├── 05_Multidisciplinary/
│   ├── 06_ICH/
│   ├── 07_Herbal_Medicines/
│   └── 99_Uncategorized/
├── 02_Regulatory_Procedural_Guidelines/
├── 03_Reflection_Position_Concept_Papers/
├── 04_QA_Public_Statements/
├── 05_EU_Legislation_Optional/
├── 90_Raw_JSON/
│   ├── documents-output-json-report_en_YYYYMMDD.json
│   └── general-json-report_en_YYYYMMDD.json
└── 99_Failed_Downloads/
    ├── download_failures.csv
    └── download_manifest.csv
```

原始 JSON 快照建议保留。它们不仅能用于问题排查，也能帮助判断 EMA 官方数据是否发生了字段变化。

---

## 7. 文档数据模型

### 7.1 原始字段

保留 EMA 原始字段，不要过早丢弃：

```text
id
name
medicine_name
ema_product_number
type
status
consultation_date
first_published_date
last_updated_date
reference_number
document_url
translations
```

不同数据集的字段不完全相同，因此解析器需要允许字段缺失。

### 7.2 内部索引字段

建议 SQLite 增加这些本地字段：

```text
ema_id
name
document_type
status
reference_number
first_published_at
last_updated_at
official_url
source_dataset
local_path
local_filename
file_extension
http_status
content_type
file_size
sha256
download_status
downloaded_at
last_seen_at
is_archived
category
error_message
```

### 7.3 下载状态

建议使用有限状态，而不是只保存“成功/失败”：

```text
new
planned
downloaded
updated
skipped_unchanged
skipped_existing
no_download_url
http_error
invalid_content
checksum_error
write_error
```

这样用户能知道某条记录为什么没有得到本地文件。

---

## 8. 增量同步策略

不要只根据文件名判断是否已经下载，建议按以下优先级判断：

1. EMA 文档 ID；
2. 官方 URL；
3. 官方 `last_updated_date`；
4. HTTP `ETag` 或 `Last-Modified`；
5. 本地文件 SHA-256。

理想逻辑：

```text
本地没有 ema_id
    → 新文档，下载

本地有 ema_id，但 last_updated_date 变了
    → 更新文档，重新下载

日期没变，但远程 URL 变了
    → 重新下载

元数据没变，本地文件存在且哈希正常
    → 跳过

元数据没变，但本地文件丢失或损坏
    → 重新下载
```

文件更新时不要直接覆盖旧文件。推荐：

```text
目标文件.tmp
    ↓ 下载完成
检查 HTTP 状态、Content-Type、大小
    ↓
计算 SHA-256
    ↓
原子 rename 到正式文件
```

如果需要保留历史版本，可以使用：

```text
versions/
├── 20240115_reference_xxx.pdf
└── 20260902_reference_xxx.pdf
```

MVP 阶段可以先保留最新版本，SQLite 中记录历史同步时间；第二阶段再增加版本归档。

---

## 9. 文件命名建议

不建议只使用标题。EMA 的 `reference_number` 对注册人员很有价值。

推荐格式：

```text
{last_updated_yyyymmdd}__{reference_number}__{safe_title}.pdf
```

示例：

```text
20260902__EMA-CHMP-123456__Guideline-on-the-quality-of-medicinal-products.pdf
```

没有 reference number 时：

```text
20260902__scientific-guideline__Investigation-of-chiral-active-substances.pdf
```

文件名处理规则：

- 去除 `/ \ * ? : " < > |`；
- 合并多余空格；
- 限制标题长度；
- 保留原始标题在数据库和 Excel 中；
- Windows 下避免保留设备名和结尾句点；
- 文件名冲突时追加稳定短哈希，而不是随机数字。

例如：

```text
20260902__scientific-guideline__Investigation-of-chiral-active-substances__a81f2c.pdf
```

---

## 10. 分类方案

分类最好采用“字段优先、标题兜底”的方式。

### 10.1 第一层：按文档类型

```text
scientific-guideline              → 01_Scientific_Guidelines
regulatory-procedural-guideline   → 02_Regulatory_Procedural_Guidelines
reflection-paper                  → 03_Reflection_Position_Concept_Papers
position-paper                    → 03_Reflection_Position_Concept_Papers
concept-paper                     → 03_Reflection_Position_Concept_Papers
q-and-a                           → 04_QA_Public_Statements
public-statement                   → 04_QA_Public_Statements
```

### 10.2 第二层：按领域关键词

在科学指导原则目录内，可以采用可编辑 CSV：

```csv
Priority,Field,Keywords,Folder
10,Quality,"quality;manufacture;stability;impurity",01_Quality
20,Nonclinical,"non-clinical;toxicology;pharmacology",02_Nonclinical
30,Clinical,"clinical;efficacy;safety;trial",03_Clinical_Efficacy_Safety
40,Biologicals,"biological;vaccine;cell therapy;gene therapy",04_Biologicals
50,Multidisciplinary,"multidisciplinary;biosimilar;paediatric",05_Multidisciplinary
60,ICH,"ICH",06_ICH
70,Herbal,"herbal;HMPC",07_Herbal_Medicines
```

规则匹配时应优先检查 EMA 数据字段和 URL 路径，然后才匹配标题。标题关键词只能作为兜底，因为同一个词可能出现在不同主题中。

---

## 11. Excel 索引设计

继续提供 Excel 是有必要的，因为 RA 同事通常会直接筛选、排序和共享 Excel。

建议列：

| 列 | 说明 |
|---|---|
| EMA ID | EMA 文档 ID |
| Document name | 官方标题 |
| Type | 文档类型 |
| Status | Adopted、Draft 等 |
| Reference number | EMA 参考编号 |
| First published date | 首次发布日期 |
| Last updated date | 最后更新时间 |
| Official URL | 官方文档链接 |
| Local file | 本地文件路径 |
| Category | 本地分类 |
| Download status | 下载状态 |
| File size | 文件大小 |
| SHA-256 | 文件哈希 |
| Local hyperlink | Excel 本地超链接 |

建议工作表：

```text
All Documents
Scientific Guidelines
Regulatory Procedural
Draft and Consultation
Failed Downloads
Sync Summary
```

SQLite 是程序的真实数据源，Excel 是导出视图。不要把 Excel 作为唯一数据库，否则后续状态和版本管理会越来越难维护。

---

## 12. 命令行设计

### 12.1 最简用法

```bash
ema-downloader sync
```

默认行为：

- 获取官方 JSON；
- 筛选 `scientific-guideline` 和 `regulatory-procedural-guideline`；
- 下载新增或更新文档；
- 更新本地索引；
- 生成同步报告。

### 12.2 预览

```bash
ema-downloader sync --dry-run
```

只显示：

- 新增数量；
- 更新数量；
- 未变更数量；
- 待下载数量；
- 被过滤数量；
- 预计下载大小。

### 12.3 按类型筛选

```bash
ema-downloader sync \
  --types scientific-guideline regulatory-procedural-guideline
```

### 12.4 按状态筛选

```bash
ema-downloader sync --status adopted
```

### 12.5 按更新时间筛选

```bash
ema-downloader sync --updated-since 2025-01-01
```

### 12.6 关键词筛选

```bash
ema-downloader sync --keyword oncology
```

### 12.7 小批量验证

```bash
ema-downloader sync --limit 10
```

这个参数很重要，可以先验证下载行为，不要第一次运行就下载几千个文件。

### 12.8 只更新元数据

```bash
ema-downloader metadata
```

### 12.9 只下载已规划文件

```bash
ema-downloader download
```

### 12.10 整理和导出

```bash
ema-downloader organize
ema-downloader export --format xlsx
ema-downloader export --format csv
```

### 12.11 检查本地文件

```bash
ema-downloader verify
```

检查：

- 文件是否存在；
- 文件大小是否合理；
- 文件是否是 HTML 错误页；
- SHA-256 是否一致；
- 数据库路径是否仍然有效。

---

## 13. 下载器实现注意事项

### 13.1 不要把响应全部读入内存

错误方式：

```python
payload = response.read()
open(path, "wb").write(payload)
```

推荐流式下载：

```python
with response:
    with open(temp_path, "wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            digest.update(chunk)
```

### 13.2 防止把错误 HTML 保存成 PDF

下载完成后至少检查：

- HTTP 状态码是 2xx；
- `Content-Type` 是否合理；
- 文件大小是否大于最小阈值；
- PDF 是否以 `%PDF-` 开头；
- 文档 URL 后缀和实际内容是否一致。

### 13.3 重试和限速

建议：

- 连接错误重试 3 次；
- 429 或 503 使用指数退避；
- 默认并发数控制在 2～4；
- 提供 `--workers`；
- 在 User-Agent 中标识工具名称；
- 不要用高并发压 EMA 官方站点。

### 13.4 URL 失效

如果元数据有记录但 PDF 返回 404：

- 保留这条记录；
- 标记为 `http_error`；
- 写入失败清单；
- 不要删除旧的本地文件；
- 下次同步继续检查。

### 13.5 翻译文件

第一版建议只下载英文文件。翻译文件需要额外处理：

```text
translations: {
  "de": "...",
  "fr": "...",
  "es": "..."
}
```

可以后续增加：

```bash
ema-downloader sync --languages en zh? fr de
```

但 EMA 并不一定提供中文版本，所以语言列表必须以实际字段为准，不能假设每个文档都有所有语言。

---

## 14. 推荐项目结构

```text
EMADownloader/
├── ema_downloader/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── models.py
│   ├── ema_source.py
│   ├── normalizer.py
│   ├── database.py
│   ├── downloader.py
│   ├── organizer.py
│   ├── exporter.py
│   └── reporting.py
├── config/
│   ├── settings.toml
│   └── classification_rules.csv
├── tests/
│   ├── test_ema_source.py
│   ├── test_normalizer.py
│   ├── test_downloader.py
│   ├── test_organizer.py
│   └── fixtures/
├── README.md
├── pyproject.toml
├── LICENSE
└── .gitignore
```

推荐技术栈：

- Python 3.11+；
- `httpx` 或标准库 `urllib`；
- SQLite；
- `pandas` + `openpyxl`，用于 Excel 导出；
- `tqdm`，用于命令行进度；
- `pytest`，用于测试；
- 不依赖 Selenium。

如果要尽量降低安装门槛，也可以第一版只使用 Python 标准库，Excel 导出作为可选依赖。

---

## 15. MVP 范围

第一版不需要一次做成完整平台，建议以“可验证、可增量运行”为目标。

### 必须实现

- [ ] 下载 EMA 官方 documents JSON；
- [ ] 下载 general JSON；
- [ ] 筛选 `scientific-guideline`；
- [ ] 筛选 `regulatory-procedural-guideline`；
- [ ] 支持 `--limit`；
- [ ] 支持 `--dry-run`；
- [ ] 流式下载 PDF；
- [ ] 临时文件和原子重命名；
- [ ] HTTP 状态和 Content-Type 检查；
- [ ] SHA-256；
- [ ] SQLite 索引；
- [ ] 增量同步；
- [ ] 失败清单；
- [ ] 下载 manifest；
- [ ] 按类型和主题分类；
- [ ] Excel 索引；
- [ ] 本地超链接；
- [ ] 基础测试。

### 第二阶段

- [ ] 翻译文件；
- [ ] 草案和已采纳版本关联；
- [ ] 历史版本保留；
- [ ] PDF 文本提取；
- [ ] 全文搜索；
- [ ] HTML 报告；
- [ ] 定时任务；
- [ ] 邮件或 Telegram 更新通知；
- [ ] EUR-Lex/EudraLex 法规数据源；
- [ ] 简单 GUI。

---

## 16. 分阶段开发计划

### 阶段 A：数据源验证

目标：不下载大量文件，只确认接口稳定性。

1. 获取两个 EMA JSON；
2. 打印元数据；
3. 统计所有 `type`；
4. 筛选 10 条指导原则；
5. 检查每条 `document_url`；
6. 下载 1～3 个 PDF；
7. 检查文件头、大小和 PDF 可打开性。

验收条件：

- JSON 能成功获取；
- 字段解析稳定；
- 10 条记录中大多数有有效下载 URL；
- 下载的 PDF 不是错误 HTML；
- 失败项能明确记录原因。

### 阶段 B：本地索引和增量同步

1. 创建 SQLite；
2. 保存原始 JSON 快照；
3. 建立新增/更新/未变化判断；
4. 加入 SHA-256；
5. 实现失败重试；
6. 生成同步报告。

验收条件：

- 第二次运行不会重复下载未变化文件；
- 删除本地文件后能重新下载；
- 模拟更新时间变化时会重新下载；
- 失败记录不会被静默吞掉。

### 阶段 C：分类和 Excel

1. 引入分类规则 CSV；
2. 按类型和主题建立目录；
3. 导出 Excel；
4. 增加本地超链接；
5. 生成失败下载工作表。

验收条件：

- 目录结构可预测；
- 文件与数据库记录一一对应；
- Excel 能筛选和打开本地文件；
- dry-run 不会复制或覆盖文件。

### 阶段 D：扩展法规和更新通知

1. 增加 EUR-Lex/EudraLex；
2. 增加定时同步；
3. 只通知新增和更新项；
4. 增加版本历史；
5. 增加全文检索。

---

## 17. 风险和边界

### 17.1 官方 JSON 不是永久 API 契约

虽然 EMA 明确提供 JSON 文件，但仍然应该：

- 保存字段样本；
- 对缺失字段做兼容；
- 在字段变化时输出警告；
- 不把字段顺序写死；
- 每次同步记录 JSON timestamp。

### 17.2 “Adopted” 不等于永远有效

状态、发布日期和最后更新时间需要原样保存。工具不应该自行判断某个指南在法律意义上是否仍然有效，只负责下载和标记官方状态。

### 17.3 不能替代法规合规判断

工具只是资料获取和整理工具：

- 不构成法律意见；
- 不判断某项指南是否适用于具体项目；
- 不替代官方网页、法规原文或专业人员判断；
- 使用者需要检查官方最新版本。

### 17.4 资料总量可能很大

全量文档 70,000 多条，但核心指导原则约 3,500 条左右。默认只下载目标类型，避免用户第一次运行就产生大量无关资料。

### 17.5 不要默认镜像所有文件

应该明确区分：

```text
metadata sync     → 轻量、建议默认开启
core guidance     → 默认下载
related documents → 可选下载
all documents     → 高级选项
```

---

## 18. 和 FDA 版本的最终差异

| 项目 | FDA 参考项目 | EMA 建议方案 |
|---|---|---|
| 数据发现 | 网页表格 | 官方 JSON |
| 浏览器 | Selenium/Chrome | 不需要 |
| 人工操作 | 需要筛选和 Show All | 默认不需要 |
| 元数据 | 页面解析 | 官方字段 |
| 下载方式 | 浏览器或直链 | 流式 HTTP |
| 索引 | Excel | SQLite + Excel |
| 增量判断 | 文件名模糊匹配 | EMA ID + 更新时间 + 哈希 |
| 分类 | FDA 机构和主题 | 文档类型 + EMA 领域 |
| 失败处理 | CSV | SQLite 状态 + CSV 报告 |
| 版本追踪 | 较弱 | 可按更新时间和哈希追踪 |
| 扩展法规 | FDA 页面范围 | 可接 EUR-Lex/EudraLex |

结论是：

```text
保留 FDA 项目的产品思路，替换掉 FDA 项目的网页抓取实现。
```

---

## 19. 最终建议

这个项目值得做。最推荐的技术路线是：

```text
Python CLI
+ EMA 官方 JSON
+ SQLite 增量索引
+ 流式 PDF 下载
+ SHA-256 校验
+ CSV 分类规则
+ Excel 导出
```

第一版不要从 GUI 开始，也不要一开始做全量 EMA 镜像。先做一个能够稳定完成下面闭环的工具：

```text
获取官方清单
→ 选择 10 条
→ dry-run 预览
→ 下载 PDF
→ 校验文件
→ 分类归档
→ 生成 Excel
→ 再次运行时跳过未变化文件
```

只要这个闭环稳定，后续增加完整指导原则、翻译、法规、全文检索和通知都比较自然。

### 推荐的第一条验收命令

```bash
ema-downloader sync \
  --types scientific-guideline regulatory-procedural-guideline \
  --limit 10 \
  --dry-run
```

确认预览结果无误后：

```bash
ema-downloader sync \
  --types scientific-guideline regulatory-procedural-guideline \
  --limit 10
```

### 最终判断

**可以做，而且应该做成“自动同步本地监管资料库”，而不只是一个简单 PDF 下载脚本。**

FDADownloader 已经验证了“下载清单 + 归档整理 + Excel 索引”这个产品方向；EMA 官方 JSON 则提供了更好的数据基础，使 EMA 版本有机会做到更稳定、更少人工操作、更容易增量更新。

---

## 20. 调研来源

[1] [FDADownloader 项目](https://github.com/Fiveo9/FDADownloader)

[2] [FDADownloader.py](https://raw.githubusercontent.com/Fiveo9/FDADownloader/main/FDADownloader.py)

[3] [FDAOrganizer.py](https://raw.githubusercontent.com/Fiveo9/FDADownloader/main/FDAOrganizer.py)

[4] [EMA Scientific guidelines](https://www.ema.europa.eu/en/human-regulatory-overview/research-development/scientific-guidelines)

[5] [EMA Download website data in JSON data format](https://www.ema.europa.eu/en/about-us/about-website/download-website-data-json-data-format)

[6] [EMA All documents in English JSON data](https://www.ema.europa.eu/en/documents/report/documents-output-json-report_en.json)

[7] [EMA Guidance and information JSON data](https://www.ema.europa.eu/en/documents/report/general-json-report_en.json)

---

## 附录：当前调研中已验证的数据

2026-09-02 实测：

```text
All documents JSON:
  total_records = 70444
  timestamp = 2026-09-02T05:45:08Z

General JSON:
  total_records = 2059
  timestamp = 2026-09-02T06:00:54Z

Document types:
  scientific-guideline = 2726
  regulatory-procedural-guideline = 766
```

以上数量是本次访问官方 JSON 时的快照，后续会随 EMA 数据更新而变化，不能写死在程序逻辑中。
