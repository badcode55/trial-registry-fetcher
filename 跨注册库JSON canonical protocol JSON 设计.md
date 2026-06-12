# 跨注册库 JSON canonical protocol JSON 设计记录

## 当前原则

当前阶段不正式设计跨注册库 canonical protocol JSON。原因是不同注册库的数据结构和医学语义并不完全一致，过早统一可能导致错误映射。现在只记录 UMIN 与 NCT 中哪些字段可以稳定映射、哪些字段需要人工确认、哪些字段暂时不能映射。

这个文件只保留在 `dev` 分支，不同步到 `main`。后续每新增一个数据源，都需要更新本文件。

## NCT / ClinicalTrials.gov

### 来源专属输出

- `NCT_protocol.json`：兼容师姐 notebook 中 `_protocol.json` 的结构。
- `NCT_raw.json`：ClinicalTrials.gov API 原始 JSON。

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

## UMIN-CTR

### 来源专属输出

- `UMIN_protocol.json`：按 UMIN 网页自身 section/field 组织。

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

## 后续讨论问题

- canonical JSON 是否应该保留 `source_specific`，用于保存无法统一但有价值的原始字段。
- 结局字段是否只保留 primary/secondary/other，还是需要同时保留原注册库原文。
- 干预字段是否需要拆成 `arms` 与 `interventions`，还是统一为更宽松的文本/结构混合格式。
- 日期字段是否需要统一命名，并保留来源字段名作为注释或 metadata。
- 是否需要单独记录“字段映射置信度”，例如 stable / weak / source_specific。
