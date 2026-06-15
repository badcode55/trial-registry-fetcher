# 跨注册库 JSON canonical protocol JSON 设计记录

## 当前原则

当前阶段不正式设计跨注册库 canonical protocol JSON。原因是不同注册库的数据结构和医学语义并不完全一致，过早统一可能导致错误映射。现在先为已经抓到详情页/API 数据的来源输出来源专属 JSON，并记录各来源中哪些字段可以稳定映射、哪些字段需要人工确认、哪些字段暂时只能作为来源专属信息保存。仅有搜索页链接、还没有解析到详情页的数据，不生成来源专属 JSON。

这个文件只保留在 `dev` 分支，不同步到 `main`。后续每新增一个数据源，都需要更新本文件。

## 来源专属 JSON 通用外壳

每个来源的 `*_protocol.json` 都保留来源自己的字段结构，不强行套用其他注册库格式。只有 `fetch_status=fetched` 的记录会生成该文件。为了便于后续比较，每个文件至少包含以下通用外壳：

- `source_registry`：注册库名称，stable，可映射到未来 canonical `source_registry`。
- `registration_number`：注册号，stable，可映射到未来 canonical `registration_number`。
- `source_file`：输入清单中的文献文件名，stable，可映射到未来 canonical `source_file`。
- `detail_url`：详情页或当前最接近的查询 URL，stable，可映射到未来 canonical `detail_url`。
- `fetched_at`：抓取时间，source_specific，用于审计。
- `fetch_status`：`fetched`、`search_required`、`blocked_by_site`、`ambiguous`、`parse_failed` 等，stable，可映射到未来 canonical `fetch_status`。
- `fetch_note`：失败或限制说明，source_specific。
- `protocol_sections`：注册方案/登记信息，weak。字段名保留来源原文，后续再决定 canonical 字段。
- `results_sections`：注册库中公开的结果、结果链接、publication、不良事件等信息，weak。先保存，不在本阶段强行统一。
- `source_specific`：来源特有元数据、URL、raw API 模块等，source_specific。
- `raw_evidence_files`：raw JSON、HTML、text 等证据文件路径，stable，用于追溯。

## NCT / ClinicalTrials.gov

### 来源专属输出

- `NCT_protocol.json`：兼容师姐 notebook 中 `_protocol.json` 的结构。
- `NCT_raw.json`：ClinicalTrials.gov API 原始 JSON。
- 新增通用外壳字段：`protocol_sections` 保存完整 `protocolSection`；`results_sections` 保存 API 中的 `resultsSection`，如果存在；`source_specific.derivedSection` 保存 NCT 特有派生模块。

### 可稳定映射

- 注册号：`registration_number`, `identification.nct_id`
- 注册库：`source_registry`
- 文献文件：`source_file`
- 标题：`identification.brief_title`, `identification.official_title`
- 机构/申办方：`identification.organization`, `identification.lead_sponsor`
- 研究状态：`status.overall_status`
- 日期：`status.start_date`, `status.primary_completion_date`, `status.completion_date`, `status.first_submit_date`, `status.first_post_date`, `status.last_update_submit_date`, `status.last_update_post_date`
- 设计：`design.study_type`, `design.allocation`, `design.intervention_model`, `design.primary_purpose`, `design.masking`
- 疾病/条件：`conditions`
- 干预组和干预措施：`arms`, `interventions`
- 结局：`outcomes.primary`, `outcomes.secondary`, `outcomes.other`
- 纳排标准：`eligibility.criteria`, `eligibility.sex`, `eligibility.minimum_age`, `eligibility.maximum_age`
- 联系人和地点：`contacts_locations`

### 弱映射或需确认

- `design.phases` 与其他注册库中的“研究阶段”不一定等价。
- `design.who_masked` 在其他来源中可能不存在，或只以文本描述出现。
- `oversight.has_dmc`、FDA 相关字段不一定适用于非美国注册库。
- NCT 的 `arms` 是结构化数组，其他来源可能只有自由文本。

### 暂时不可映射或来源依赖强

- ClinicalTrials.gov API 中的模块命名不应直接作为跨来源 canonical 字段名。
- `NCT_raw.json` 中的 `derivedSection` 属于 NCT 特有结构，暂不纳入统一设计。
- `results_sections` 中的 participant flow、baseline、outcome measures、adverse events 后续需要单独设计 results canonical JSON，本阶段只保留来源结构。

## UMIN-CTR

### 来源专属输出

- `UMIN_protocol.json`：按 UMIN 网页自身 section/field 组织。
- `UMIN_raw.html`：UMIN 详情页原始 HTML。
- 新增通用外壳字段：`protocol_sections` 保存非结果类 UMIN section；`results_sections` 保存 `Result`、publication、outcome/result 相关 section；`source_specific.meta` 保存 summary table。

### 可稳定映射

- 注册号：`registration_number`, `identification.umin_id`
- receipt number：`receipt_number`
- 注册库：`source_registry`
- 文献文件：`source_file`
- 标题：`identification.public_title`, `identification.scientific_title`
- 地区：`identification.region`
- 研究状态：`status.recruitment_status`
- 日期：`status.registered_date`, `status.date_of_disclosure`, `status.last_modified_on`, `status.anticipated_trial_start_date`, `status.last_follow_up_date`
- 疾病/条件：`condition`
- 目的：`objectives`
- 研究设计：`design`
- 干预：`intervention`
- 结局：`outcomes.primary`, `outcomes.secondary`
- 纳排标准：`eligibility`
- 联系人：`contacts`
- 机构/资助：`organizations`
- 结果和相关信息：`result`, `related_information`

### 弱映射或需确认

- UMIN `Developmental phase` 与 NCT `phases` 是否可合并，需要专业判断。
- UMIN `Randomization`, `Blinding`, `Control` 可对应 NCT design 字段，但枚举值和详细程度不同。
- UMIN `Interventions/Control_1...10` 是文本块，和 NCT 结构化 `arms/interventions` 不完全等价。
- UMIN `Date of disclosure` 与 NCT `first_post_date` 概念接近，但需要确认是否可统一。

### 暂时不可映射或来源依赖强

- UMIN 没有 NCT 的 `protocolSection` 模块结构。
- UMIN 没有稳定的 NCT `oversight` 字段组。
- UMIN 的机构字段和 NCT locations/contact 结构不同，不应强行合并。
- UMIN `Result.Results` 和 publication 链接是否属于 results canonical 模块，需要和实际使用场景确认。

## ISRCTN

### 来源专属输出

- `ISRCTN_protocol.json`：按页面可见区块、表格和标题文本保存。
- `ISRCTN_raw.html` / `ISRCTN_raw.txt`：详情页原始 HTML 和抽取文本，只有成功抓取详情页时生成。

### 字段记录

- `registration_number`：ISRCTN 编号，stable。
- `protocol_sections.page.title`：页面标题，weak，可映射到 trial title。
- `protocol_sections` 中从表格/标题抽取的条件、干预、结局、纳排、地点等字段：weak，后续需要基于真实页面 fixture 确认字段名稳定性。
- `results_sections`：页面中包含 result/outcome/publication/adverse 等关键词的区块，unknown，本阶段先按来源结构保存。
- `source_specific.urls`：搜索/详情 URL 和抓取模式，source_specific。

### 需要确认

- ISRCTN 页面不同年代记录的 section 名称是否稳定。
- ISRCTN 公开结果信息与 protocol outcome 字段的边界需要人工确认。

## ChiCTR

### 来源专属输出

- `ChiCTR_protocol.json`：按 ChiCTR 详情页字段表或页面区块保存。
- `ChiCTR_raw.html` / `ChiCTR_raw.txt`：只有输入详情 URL 或后续实现 ID 到详情页唯一解析时生成。

### 字段记录

- `registration_number`：ChiCTR 注册号或详情页项目号，stable。
- `detail_url`：详情页 URL；当前 ID 输入时多为搜索 URL，weak。
- `fetch_status`：当前 ID 输入通常为 `search_required`；详情 URL 抓取成功时为 `fetched`。
- `protocol_sections`：ChiCTR 字段表原始字段，weak，待真实 fixture 后细分标题、疾病、设计、干预、结局、纳排等。
- `results_sections`：页面中结果、publication、outcome 相关字段，unknown。
- `source_specific.urls`：搜索 URL、项目详情 URL 候选，source_specific。

### 需要确认

- `ChiCTR...` 注册号到 `showprojEN.html?proj=...` 的唯一解析规则。
- 中英文详情页字段是否一一对应，未来 canonical 映射应优先使用哪种语言。

## 中国 CDE / CTR

### 来源专属输出

- `ChinaDrugTrials_protocol.json`：按 CDE 页面字段保存。
- `ChinaDrugTrials_raw.html` / `ChinaDrugTrials_raw.txt`：只有详情页成功抓取时生成。

### 字段记录

- `registration_number`：`CTR########` 编号，stable。
- `detail_url`：当前保存搜索 URL 和详情候选入口，weak。
- `fetch_status`：当前 ID 输入为 `blocked_by_site`，表示需要 session、动态表单或浏览器兜底后才能确认详情。
- `protocol_sections`：CDE 字段表原始字段，weak，待 fixture 后细分试验题目、适应症、药物、申办者、设计、入排标准等。
- `results_sections`：CDE 页面如果公开结果信息则保存，unknown。
- `source_specific.urls`：搜索 URL、详情候选 URL、抓取限制说明，source_specific。

### 需要确认

- CDE 搜索请求参数、session/cookie 与反爬行为是否允许稳定自动化。
- CDE 字段属于药物临床试验登记，和国际 registry 字段不完全等价，需谨慎映射。

## ANZCTR

### 来源专属输出

- `ANZCTR_protocol.json`：按 ANZCTR `TrialReview.aspx` 页面字段组织。
- `ANZCTR_raw.html` / `ANZCTR_raw.txt`：详情页成功抓取时生成。

### 字段记录

- `registration_number`：`ACTRN...` 编号或详情页 numeric id，stable/weak，取决于输入是否为注册号。
- `fetch_status`：ID 输入当前为 `search_required`；详情 URL 成功时为 `fetched`。
- `protocol_sections`：ANZCTR 页面字段，如 public title、health condition、intervention、outcomes、eligibility、sponsors、contacts，weak。
- `results_sections`：页面中 result/publication/outcome 相关区块，unknown。
- `source_specific.urls`：前端搜索 URL、详情 URL，source_specific。

### 需要确认

- `ACTRN...` 到 `TrialReview.aspx?id=...` 的稳定搜索/API 路径。
- ANZCTR outcome 字段通常是 planned outcomes，是否和 results module 分开需要人工确认。

## EUCTR

### 来源专属输出

- `EUCTR_protocol.json`：按 EU Clinical Trials Register 页面字段组织。
- `EUCTR_raw.html` / `EUCTR_raw.txt`：详情页或 country-specific record 成功抓取时生成。

### 字段记录

- `registration_number`：EudraCT ID，stable。
- `detail_url`：搜索 URL、results URL 或 country trial URL，weak。
- `fetch_status`：ID 输入当前为 `search_required`；直接详情 URL 成功时为 `fetched`。
- `protocol_sections`：EUCTR 字段，如 trial identification、sponsor、medical condition、population、endpoints、IMP/intervention，weak。
- `results_sections`：EUCTR results 页面字段，weak，未来可能进入 results canonical JSON。
- `source_specific.urls`：search URL、results URL、country record URL，source_specific。

### 需要确认

- 同一 EudraCT ID 多国家记录的保存策略：建议全部保存为多个 match，不只取第一条。
- results 页面和 protocol 页面字段来源不同，后续 canonical JSON 应明确来源。

## CTIS

### 来源专属输出

- `CTIS_protocol.json`：按 CTIS 公开页面/API 字段组织。
- `CTIS_raw.html` / `CTIS_raw.txt` 或 raw JSON：详情页/API 成功抓取时生成。

### 字段记录

- `registration_number`：EU CT number，stable。
- `detail_url`：CTIS 公共搜索 URL 或详情 URL，weak。
- `fetch_status`：当前 ID 输入为 `search_required`，后续若被前端策略、登录或反爬阻断则记录 `blocked_by_site`。
- `protocol_sections`：CTIS 公开字段，如 trial identification、sponsor、medical condition、trial design、arms、endpoints、population，weak。
- `results_sections`：CTIS 公开结果信息，unknown，本阶段先来源专属保存。
- `source_specific.urls`：搜索参数、前端/API 发现信息，source_specific。

### 需要确认

- CTIS 公共搜索是否有稳定 API 可用，或必须浏览器自动化。
- EU CT number 与旧 EudraCT ID 的关系不应在本阶段强行合并。

## 后续讨论问题

- canonical JSON 是否应该保留 `source_specific`，用于保存无法统一但有价值的原始字段。
- 结局字段是否只保留 primary/secondary/other，还是需要同时保留原注册库原文。
- 干预字段是否需要拆成 `arms` 与 `interventions`，还是统一为更宽松的文本/结构混合格式。
- 日期字段是否需要统一命名，并保留来源字段名作为注释或 metadata。
- 是否需要单独记录“字段映射置信度”，例如 stable / weak / source_specific。
- results canonical JSON 是否独立于 protocol canonical JSON 设计，避免把 planned outcomes 和 actual measured results 混在一起。
