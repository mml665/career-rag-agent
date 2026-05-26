# 智能求职 Agent 数据模型设计

## 改造目标

将当前通用资料问答底座升级为“智能选岗及简历定制 Agent”。系统需要区分两类证据来源：

```text
个人履历证据：用于证明用户确实具备的技能和经历
岗位 JD 证据：用于描述岗位要求、工作地点和投递条件
```

所有岗位匹配结论和简历修改建议都必须引用这两类原始证据，不能凭空补充经历。

## 核心实体

### `CandidateProfile`：个人基本信息

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `name` | `str` | 姓名 |
| `phone` | `str` | 手机号 |
| `email` | `str` | 邮箱 |
| `city` | `str` | 当前所在地 |
| `target_role` | `str` | 求职意向 |
| `preferred_locations` | `str` | 期望工作地点 |
| `homepage` | `str` | 个人主页、GitHub 或作品链接 |
| `summary` | `str` | 个人简介 |

该信息用于简历头部和求职管理，不作为技能匹配得分的证据。

### `ProfileEvidence`：个人履历证据

界面上以一张个人档案表单维护五个固定栏目；存储时，每个非空栏目对应一条 `ProfileEvidence`，供匹配和简历定制引用。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `evidence_id` | `str` | 证据唯一标识 |
| `category` | `str` | `education` / `skill` / `project` / `award` / `availability` |
| `content` | `str` | 可供检索和引用的事实描述 |
| `source_file` | `str` | 来源文件 |
| `source_page` | `int \| null` | PDF 页码，可为空 |
| `verified` | `bool` | 用户是否确认该信息可写入简历 |

### `JobPosting`：岗位信息

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `job_id` | `str` | 岗位唯一标识 |
| `company` | `str` | 公司名称 |
| `title` | `str` | 岗位名称 |
| `location` | `str` | 城市/地点 |
| `source_url` | `str \| null` | JD 来源链接 |
| `raw_description` | `str` | 原始 JD 文本 |
| `required_skills` | `list[str]` | 必备技能 |
| `preferred_skills` | `list[str]` | 加分技能 |
| `internship_requirements` | `list[str]` | 实习时间、年级等条件 |
| `created_at` | `str` | 添加时间 |

### `MatchAnalysis`：岗位匹配分析

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `analysis_id` | `str` | 分析唯一标识 |
| `job_id` | `str` | 被分析岗位 |
| `score` | `float` | 当前综合匹配分数，用于排序 |
| `matched_requirements` | `list[str]` | 有证据支持的必备技能 |
| `missing_requirements` | `list[str]` | 暂无履历证据的必备技能缺口 |
| `matched_preferred_skills` | `list[str]` | 有证据支持的加分技能 |
| `missing_preferred_skills` | `list[str]` | 暂无履历证据的加分技能缺口 |
| `evidence_ids` | `list[str]` | 支撑结论的个人证据 |
| `evidence_map` | `dict[str, list[str]]` | 每项技能对应的履历证据 |
| `resume_suggestions` | `list[str]` | 仅基于已有事实的修改建议 |
| `analysis_type` | `str` | `keyword` 或 `hybrid` |
| `keyword_score` | `float \| null` | 关键词覆盖基线分数 |
| `semantic_score` | `float \| null` | JD 与履历证据的语义匹配分数 |
| `semantic_evidence_ids` | `list[str]` | 语义匹配靠前的证据 |
| `model_explanation` | `str` | 仅依据履历证据生成的解释 |
| `is_stale` | `bool` | 分析后履历是否已发生变化 |
| `invalidated_at` | `str` | 被标记为历史结果的时间 |
| `created_at` | `str` | 分析时间 |

### `ResumeVersion`：岗位定制简历版本

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `version_id` | `str` | 定制版本唯一标识 |
| `job_id` | `str` | 面向的岗位 |
| `name` | `str` | 用户可识别的版本名称 |
| `content` | `str` | 可直接使用或继续编辑的推荐表述 |
| `target_category` | `str` | 适合写入的履历栏目 |
| `fit_assessment` | `str` | 生成时的审核判断 |
| `evidence_basis` | `str` | 生成时使用的证据说明 |
| `gap_notes` | `str` | 生成时提示的事实缺口 |
| `created_at` | `str` | 创建时间 |

### `ApplicationRecord`：投递记录

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `application_id` | `str` | 投递记录唯一标识 |
| `job_id` | `str` | 对应岗位 |
| `analysis_id` | `str \| null` | 使用的匹配分析 |
| `resume_version` | `str \| null` | 投递时使用的简历版本名称快照 |
| `resume_version_id` | `str \| null` | 关联的 `ResumeVersion`；版本删除后解除关联 |
| `status` | `str` | `planned` / `submitted` / `written_test` / `interview` / `offer` / `closed` |
| `submitted_at` | `str \| null` | 投递时间 |
| `notes` | `str` | 复盘说明 |

## 数据流

```text
上传简历/项目材料 -> 模型回填个人档案草稿 -> 用户确认 -> 保存 ProfileEvidence
粘贴或上传岗位 JD -> 模型提取结构字段 -> 用户复核 -> 保存 JobPosting
选择岗位 -> 关键词覆盖基线 + 可选语义匹配/证据解释 -> 保存 MatchAnalysis
选择岗位 -> 生成基于证据的简历建议 -> 保存 ResumeVersion -> 关联 ApplicationRecord
```

## 第一版边界

- 第一版由用户导入岗位 JD，不自动批量抓取招聘平台。
- 第一版输出匹配建议和简历修改建议，不自动向外部平台提交申请。
- 模型只能依据 `verified=true` 的履历证据提出可写入简历的表述。
- 匹配结果必须展示履历来源与 JD 要求来源，便于用户复核。
- 岗位库支持上传 PDF、Markdown、TXT 或粘贴 JD；聊天模型从原文提取公司、岗位、地点、必备技能、加分技能和实习条件，原始文本保留在 `raw_description`，结果由用户复核后才保存。
- 匹配分析支持关键词基线和混合模式：基线只匹配已确认履历，必备技能权重为 70%，加分技能权重为 30%；混合模式以关键词分数 60% 和 Embedding 语义分数 40% 组成综合分数，并生成受证据约束的解释。
- 个人档案包含基础信息与固定履历栏目，不要求额外填写标题；基础信息可直接回填编辑，履历编辑区默认留空并仅在用户主动载入时回填已保存内容。保存履历后按类别形成证据，履历内容变化时旧匹配分析保留为历史并标记需重新生成。
- 个人档案支持上传 PDF、Markdown 或 TXT 简历自动提取并回填；提取结果默认是未确认草稿，不直接成为匹配证据。
- 简历定制将目标 JD 与用户选择的已确认履历交给聊天模型，结构化输出适配判断、推荐表述、证据依据与缺口提示；缺少证据的技能不得写入推荐表述。
- 推荐表述可以独立保存为 `ResumeVersion`，供同一岗位投递记录关联；删除版本会解除链接，但保留记录中的版本名称快照。
- 适配判断、证据依据和缺口提示仅用于审核，不进入履历写入框；只有推荐表述在用户编辑并确认属实后，才能追加到个人档案中的指定栏目。
- 资料问答、检索与摘要能力归入“参考资料库”，用于简历写作规范、公司资料或学习文档，不代替结构化履历和岗位记录。

## 后续工具设计

```text
list_profile_evidence   查看可引用的履历证据
add_job_posting         保存和解析岗位 JD
list_job_postings       查看已收集岗位
analyze_job_match       生成匹配分析与技能缺口
analyze_semantic_match  以向量相似度和模型解释增强关键词基线
tailor_resume           基于证据生成定制修改建议
save_resume_version     保存岗位定制简历版本
record_application      保存投递状态并关联简历版本
```
