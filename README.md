# 文献注册信息抓取工具

这个工具用于读取一份“文献 PDF 文件名 + 注册 ID”的清单，并自动抓取或记录已接入注册网站的信息。当前完整抓取支持 `UMIN...`、`NCT...` 和 CTIS/EU CT 编号；`ISRCTN...` 和部分详情 URL 可抓取网页证据；中国 CDE 可在显式开启 Chrome/CDP 兜底时尝试自动通过浏览器取得搜索页和详情页；其他注册库先支持稳定 ID 识别、可追溯查询链接、来源专属 protocol JSON 和明确失败/待搜索状态。暂时不会根据文献题目、关键词或 PDF 文件名自动搜索注册库。

## 这个程序会做什么

- 读取 `examples/literature_ids.txt` 这样的清单。
- 对 `UMIN...` 编号，到 UMIN-CTR 获取研究注册信息。
- 对 `NCT...` 编号，到 ClinicalTrials.gov 获取研究注册信息。
- 对 `ISRCTN...` 编号，直连 ISRCTN 详情页并提取页面文本和粗结构化 section。
- 对 CTIS/EU CT 编号，例如 `2025-523616-36-00`，调用 CTIS 公开搜索 API，唯一精确匹配时保存 raw JSON、来源专属 protocol JSON 和 CSV。
- 对中国 CDE `CTR...` 编号，默认纯 HTTP 被阻断时记录 `blocked_by_site`；如果设置 `TRIAL_REGISTRY_ENABLE_CHROME_CDP=1`，程序会尝试拉起本机 Chrome，经 CDP 读取搜索结果和详情 HTML，成功后保存 `ChinaDrugTrials_protocol.json`、raw HTML/text 和 CSV。
- 对 `ChiCTR...`、中国 CDE `CTR...`、`ACTRN...`、`EudraCT...` 编号，生成可追溯状态记录；只有抓到详情页/数据源时才生成来源专属 protocol JSON 和 CSV。
- 对 `not found`，记录为 `not_found`，表示当前没有找到注册 ID。
- 生成 Excel 可以直接打开的 CSV 文件，中文和日文不应乱码。
- 对已抓到详情的数据额外保存来源专属 protocol JSON 和 raw evidence，方便后续讨论统一 JSON 格式。

## 项目结构

```text
.
├── README.md                         使用说明
├── PROJECT_PLAN.md                   开发计划，仅 dev 分支保留
├── 跨注册库JSON canonical protocol JSON 设计.md
│                                      统一 JSON 设计记录，仅 dev 分支保留
├── requirements.txt                  Python 依赖列表
├── examples/
│   └── literature_ids.txt            示例输入清单
├── output/
│   └── .gitkeep                      输出目录占位文件，运行结果不会提交到 git
├── scripts/
│   ├── run_example.sh                macOS/Linux 终端运行脚本
│   ├── run_example.command           macOS 双击运行脚本
│   └── run_example.bat               Windows 运行脚本
├── trial_registry/                   程序代码
│   ├── cli.py                        命令行入口
│   ├── runner.py                     批量处理、导出和索引逻辑
│   ├── input_readers.py              读取 TXT 输入清单
│   ├── registry_ids.py               判断 UMIN、NCT、ChiCTR、ACTRN 等 ID 类型
│   ├── sources/                      不同注册网站的适配器
│   └── exporters/                    CSV、JSON、Markdown、TXT 导出器
└── tests/                            自动测试，仅 dev 分支保留
```

## 第一次使用

请先确认电脑已经安装 Python 3。

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

Windows 如果 `python` 可用，也可以运行：

```bat
python -m pip install -r requirements.txt
```

## 一键运行示例

macOS 或 Linux 终端：

```bash
bash scripts/run_example.sh
```

macOS 也可以双击：

```text
scripts/run_example.command
```

Windows：

```bat
scripts\run_example.bat
```

脚本会读取：`examples/literature_ids.txt` 并把结果写入：`output/`

## 手动运行示例

批量处理示例输入：

```bash
python3 -m trial_registry.cli --input-file examples/literature_ids.txt --input-format txt --formats csv --output-dir output
```

单独查询一个 UMIN ID：

```bash
python3 -m trial_registry.cli UMIN000019339 --formats csv --output-dir output
```

单独查询一个 NCT ID：

```bash
python3 -m trial_registry.cli NCT00508690 --formats csv --output-dir output
```

单独查询一个 link-only 注册 ID：

```bash
python3 -m trial_registry.cli CTR20223406 --formats csv --output-dir output
```

中国 CDE 如果需要启用浏览器兜底：

```bash
TRIAL_REGISTRY_ENABLE_CHROME_CDP=1 python3 -m trial_registry.cli CTR20223406 --formats csv --output-dir output
```

这个兜底需要本机已安装 Google Chrome 或 Microsoft Edge，并且 `node` 命令可用。不开启该环境变量时，CDE 遇到 WAF/JS challenge 会保持 `blocked_by_site`，不会生成 CSV 或 `ChinaDrugTrials_protocol.json`。

## 如何查看结果

运行后，先打开总索引：

```text
output/index.csv
```

总索引中每一行对应输入清单中的一篇文献。常见状态如下：

- `saved`：已经抓取并保存结果。
- `search_required`：已识别注册库，但还需要实现 ID 到详情页的自动解析；这类行不会生成 CSV 或 `*_protocol.json`。
- `blocked_by_site`：已识别注册库，但当前网站需要动态表单、session 或浏览器/人工确认，程序不会伪装成成功。
- `not_found`：输入清单中标记为未找到注册 ID。
- `pending_source_integration`：这个注册网站还没有接入。
- `invalid_input`：输入行格式不符合要求。

如果某一行是 `saved`，请查看这一列：

```text
result_csv
```

它会指向该文献单独生成的 CSV 文件。

每个成功查询会生成一个独立目录，例如：

```text
output/11_hata_2016_nct00508690/
```

NCT 查询目录中通常包含：

```text
11_hata_2016_nct00508690.csv
NCT_protocol.json
NCT_raw.json
manifest.json
```

UMIN 查询目录中通常包含：

```text
11_ikeda_2016_umin000019339.csv
UMIN_protocol.json
UMIN_raw.html
manifest.json
```

`NCT_protocol.json` 兼容之前使用的 `_protocol.json` 结构，同时包含 `protocol_sections`、`results_sections`、`source_specific` 和 `raw_evidence_files`。`UMIN_protocol.json` 按 UMIN 网页自己的字段结构保存，不强行套用 NCT 的字段含义。

其他注册库在抓到详情页/数据源后会生成来源专属文件，例如：

```text
ISRCTN_protocol.json
ChiCTR_protocol.json
ChinaDrugTrials_protocol.json
ANZCTR_protocol.json
EUCTR_protocol.json
CTIS_protocol.json
```

来源专属 JSON 至少包含：

```text
source_registry
registration_number
source_file
detail_url
fetched_at
fetch_status
protocol_sections
results_sections
source_specific
raw_evidence_files
```

其中 `fetch_status` 表示当前状态：`fetched` 代表已抓取详情证据，`search_required` 代表还需要从搜索页解析唯一详情，`blocked_by_site` 代表当前网站有动态表单、session 或反爬限制。`results_sections` 会保存网站/API 中可见的结果、publication、outcome 或不良事件相关区块；如果没有查到则为空。

## 当前来源可用性分类

这里的“可获得”指程序能从输入 ID 或详情 URL 抓到真实 trial 详情，并生成 CSV、来源专属 `*_protocol.json` 和 raw evidence。没有抓到真实详情时，只写 `manifest.json` 和 `index.csv` 状态行，不生成 CSV 或 `*_protocol.json`。

### 默认可以获得

这些来源不需要额外环境变量，也不需要浏览器模拟访问；只要网络可访问、注册库返回公开数据，直接运行命令即可保存结果。

| 数据源 | ID 示例 | 当前获取方式 | 成功输出 |
| --- | --- | --- | --- |
| ClinicalTrials.gov | `NCT00508690` | 直接请求 ClinicalTrials.gov API：`/api/v2/studies/{NCT_ID}`。 | CSV、`NCT_protocol.json`、`NCT_raw.json` |
| UMIN-CTR | `UMIN000019339` | 程序提交 UMIN 搜索表单，取得 `recptno` 后进入详情页。 | CSV、`UMIN_protocol.json`、`UMIN_raw.html` |
| ISRCTN | `ISRCTN12345678` | 直接请求 `https://www.isrctn.com/{ISRCTN_ID}`。 | CSV、`ISRCTN_protocol.json`、raw HTML/text |
| CTIS / EU CT | `2025-523616-36-00` | 调用 CTIS 公开搜索 API，按 EU CT number 精确匹配。 | CSV、`CTIS_protocol.json`、`CTIS_raw.json` |

### 一定条件下可以获得

这些来源已经有 ID 识别、搜索结果解析和详情页保存逻辑，但能否自动保存取决于搜索页是否返回可解析的唯一匹配，或用户是否直接提供详情页 URL。

| 数据源 | ID 示例 | 可以获得的条件 | 不能满足条件时 |
| --- | --- | --- | --- |
| ChiCTR | `ChiCTR2600126676` | 搜索页返回唯一精确匹配，并能解析到 `showprojEN.html?proj=...`；或者用户直接输入 ChiCTR 详情页 URL。 | 记录 `search_required`，不生成 CSV 或 `ChiCTR_protocol.json`。 |
| ANZCTR | `ACTRN12626000671369` | 搜索页返回唯一精确匹配，并能解析到 `TrialReview.aspx?id=...`；或者用户直接输入 ANZCTR 详情页 URL。 | 记录 `search_required`，不生成 CSV 或 `ANZCTR_protocol.json`。 |
| EUCTR | `EudraCT 2015-005614-30` | 旧 EUCTR 搜索页返回可解析的 country-specific trial URL，或用户直接输入 `/ctr-search/trial/...` 详情页 URL。 | 记录 `search_required`，不生成 CSV 或 `EUCTR_protocol.json`。 |

这些来源的字段解析目前仍以通用表格/标题抽取为主，后续还需要继续做来源专属字段表解析和 live 稳定性验证。

### 需要浏览器模拟访问

中国 CDE 当前需要浏览器兜底。默认纯 HTTP 访问会遇到 WAF/JS challenge，程序会保守记录 `blocked_by_site`，不会伪造成抓取成功。

| 数据源 | ID 示例 | 可以获得的条件 | 成功输出 |
| --- | --- | --- | --- |
| 中国 CDE / CTR | `CTR20223406` | 设置 `TRIAL_REGISTRY_ENABLE_CHROME_CDP=1`；本机安装 Google Chrome 或 Microsoft Edge；`node` 命令可用；网站当时未要求验证码、登录或其他人工操作。 | CSV、`ChinaDrugTrials_protocol.json`、`ChinaDrugTrials_raw.html`、`ChinaDrugTrials_raw.txt` |

CDE 浏览器兜底会用 Chrome/CDP 读取搜索页，解析 `getDetail(this.id)` 对应的详情参数，再读取详情 HTML。只有详情页字段校验通过后才会保存结果；否则记录 `blocked_by_site`、`search_required` 或 `parse_failed`。

## 输入文件格式

TXT 文件每行写一篇文献：

```text
- 11 Ikeda 2016.pdf: UMIN000019339
- 11 Arezzo 2021.pdf: NCT04438655
- 11 Example China.pdf: CTR20223406
- 11 Example Europe.pdf: EudraCT 2015-005614-30
- 11 Example CTIS.pdf: 2025-523616-36-00
- 11 Horie 2007.pdf: not found
```

冒号左边是文献文件名，右边是注册 ID 或 `not found`。

## 开发说明

新增注册网站时，主要做三件事：

1. 在 `trial_registry/registry_ids.py` 增加 ID 识别规则。
2. 在 `trial_registry/sources/` 增加一个新的 `RegistrySource` 适配器。
3. 在 dev 分支的设计记录文档中记录该来源和其他来源之间可映射、弱映射、不可映射的字段。

如果新来源需要额外 JSON 文件，请在 source adapter 中实现 `write_sidecar_files`，不要把来源判断写进主流程。

## 测试

开发分支可以运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_umin_ctr_unittest -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_multi_registry_ids_unittest -v
```
