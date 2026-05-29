# 智能选岗及简历定制 Agent

> 基于 RAG + Tool Calling 的智能求职工作流系统

管理真实履历与岗位 JD，分析技能匹配度，针对岗位生成不虚构经历的简历建议，记录投递进展。支持参考资料库的 RAG 检索问答。

## 系统架构

```text
┌─────────────────────────────────────────────────────────┐
│                    Streamlit 前端                         │
│  个人档案 │ 岗位库 │ 匹配分析 │ 简历定制 │ 投递记录 │ 资料库 │ 智能助手  │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP (api_client.py)
┌────────────────────────▼────────────────────────────────┐
│                  FastAPI 后端 (45+ 端点)                  │
│  /api/profile  /api/jobs  /api/analyses  /api/library   │
│  /api/evidence /api/resume-versions /api/applications   │
└──────┬─────────────────────┬────────────────────────────┘
       │                     │
┌──────▼──────┐     ┌───────▼────────┐
│ CareerStore │     │  RagAssistant  │
│  (SQLite)   │     │                │
└──────┬──────┘     └───┬────┬───┬───┘
       │                │    │   │
       │         ┌──────┘    │   └──────┐
       │         ▼           ▼          ▼
       │    Chroma 向量库  BM25 索引   DashScope API
       │                  (jieba)    (qwen3.6-plus)
       │                              (Embedding)
       │
┌──────▼──────────────────────────────────────────┐
│              Tool Calling Agent                   │
│  search_knowledge │ ask_knowledge │ list_jobs    │
│  get_job │ analyze_match │ list_evidence         │
│  tailor_resume │ get_profile                     │
└─────────────────────────────────────────────────┘
```

## 核心技术

| 技术 | 用途 |
|------|------|
| **FastAPI** | RESTful 后端，45+ 端点，Pydantic 校验，异步处理 |
| **Streamlit** | 交互式前端，7 个功能页面 |
| **SQLite** | 生产存储（简历、岗位、匹配、投递） |
| **Chroma** | 向量数据库，存储文档 Embedding |
| **BM25 + jieba** | 关键词检索，中文分词 |
| **RRF 融合** | 混合检索排序（向量 + BM25） |
| **DashScope Rerank** | gte-rerank 模型重排序 |
| **LangChain Tool Calling** | ReAct 循环，8 个工具自主决策调用 |
| **DashScope qwen3.6-plus** | 聊天模型，结构化抽取与生成 |
| **DashScope Embedding** | 多模态 Embedding，文档向量化 |
| **python-docx / reportlab** | 简历导出 Word / PDF |

## 快速开始

### 环境准备

```bash
conda create -n agent python=3.11
conda activate agent
pip install -r requirements.txt
```

### 配置环境变量

复制 `.env.example` 为 `.env`，填入阿里云百炼 API Key：

```env
DASHSCOPE_API_KEY=your_dashscope_api_key_here
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen3.6-plus
OPENAI_EMBEDDING_MODEL=tongyi-embedding-vision-flash-2026-03-06
```

### 启动服务

需要同时启动 **后端 API** 和 **前端界面**：

**终端 1 — 启动 FastAPI 后端：**

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

启动后可访问 http://localhost:8000/docs 查看 API 文档。

**终端 2 — 启动 Streamlit 前端：**

```bash
python -m streamlit run app.py
```

默认访问 http://localhost:8501。

**命令行模式（可选）：**

```bash
python cli.py
```

### 启动流程说明

```text
1. FastAPI 后端启动
   → 加载 .env 配置
   → 初始化 CareerStore（SQLite: data/career.db）
   → 初始化 RagAssistant（Chroma 向量库 + BM25 索引）
   → 注册 45+ REST 端点

2. Streamlit 前端启动
   → 通过 api_client.py 连接 http://localhost:8000
   → 渲染 7 个功能页面
   → 所有业务逻辑通过 HTTP 调用后端

3. 用户操作流程
   个人档案 → 岗位库 → 匹配分析 → 简历定制 → 投递记录
       ↑                                    ↓
       └──── 采纳定制结果写回档案 ←──────────┘
```

## 功能页面

### 1. 个人档案

- 基本信息管理（姓名、联系方式、求职意向）
- 履历证据管理（教育背景、技能、项目经历、获奖、求职条件）
- 上传简历自动解析回填（PDF / Markdown / TXT）
- 证据经用户确认后才作为匹配和定制的依据

### 2. 岗位库

- 手动填写或上传 JD 文件（PDF / Markdown / TXT）
- AI 自动提取公司、岗位、地点、必备技能、加分技能
- 原始 JD 文本保留，提取结果可复核

### 3. 匹配分析

- 关键词基线分析（必备技能 70% + 加分技能 30%）
- 混合分析（关键词 60% + 语义 40%）+ AI 证据解释
- 匹配历史保留，履历变化后旧分析标记为需重算
- 跨岗位匹配度对比表格

### 4. 简历定制

- 选择目标岗位和已确认履历，生成定制表述
- 输出适配判断、推荐表述、证据依据、缺口提示
- 保存为岗位定制版本，或采纳写入个人档案
- 导出 Word / PDF 格式简历

### 5. 投递记录

- 关联岗位 + 简历版本 + 匹配分析
- 状态跟踪：准备投递 → 已投递 → 笔试 → 面试 → Offer → 结束
- 复盘备注

### 6. 参考资料库

- 文档管理：上传 / 删除 / 重建索引
- 资料问答：基于上传资料的 RAG 问答
- 检索调试：查看召回片段和相关度分数
- 摘要与历史：生成资料摘要，管理问答历史

### 7. 智能助手

- 自然语言对话，AI 自主调用工具完成任务
- 支持多步工具调用（ReAct 循环，最多 10 轮）
- 可跨页面操作：查岗位、分析匹配、定制简历、查档案

## 检索架构

```text
用户查询
    │
    ├──► 向量检索 (Chroma + DashScope Embedding)
    │       └─ 相似度分数 (0~1)
    │
    ├──► BM25 关键词检索 (jieba 分词)
    │       └─ TF-IDF 分数
    │
    ▼
RRF 融合排序
    ├─ vector_weight / (rrf_k + rank + 1)
    └─ bm25_weight / (rrf_k + rank + 1)
    │
    ▼
min_relevance_score 阈值过滤（基于原始向量分数）
    │
    ▼
DashScope Rerank 重排序（gte-rerank）
    │
    ▼
最终结果（top_k）
```

参数可在 Streamlit 侧边栏实时调整：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `enable_bm25` | true | 是否启用 BM25 关键词检索 |
| `bm25_weight` | 0.3 | BM25 在 RRF 中的权重 |
| `vector_weight` | 0.7 | 向量在 RRF 中的权重 |
| `rrf_k` | 60 | RRF 常数 |
| `min_relevance_score` | 0.45 | 最低相关性阈值 |
| `enable_rerank` | true | 是否启用 Rerank |
| `rerank_top_n` | 10 | Rerank 候选数量 |

## 数据存储

### SQLite（生产存储）

```text
data/career.db
├── candidate_profile    个人基本信息（单行）
├── profile_evidence     履历证据（按 category 分组）
├── job_postings         岗位 JD
├── match_analyses       匹配分析结果
├── resume_versions      定制简历版本
├── applications         投递记录
└── rag_history          问答历史
```

外键关联：`match_analyses.job_id → job_postings`，`applications.job_id → job_postings`，级联删除。

### JSON 回退（开发/测试）

当未指定 `db_path` 时，`CareerStore` 回退到 JSON 文件存储：

```text
data/career/
├── candidate_profile.json
├── profile_evidence.json
├── job_postings.json
├── match_analyses.json
├── application_records.json
└── resume_versions.json
```

### 数据迁移

如果之前使用 JSON 存储，可通过迁移脚本一次性导入 SQLite：

```bash
python migrate_json_to_sqlite.py
```

该脚本会读取 `data/career/` 下的 JSON 文件和 `data/history.jsonl`，写入 `data/career.db`。迁移是幂等的，重复执行不会产生重复数据。

迁移完成后，`api/deps.py` 中的 `CareerStore(db_path=Path("data/career.db"))` 会自动使用 SQLite。JSON 文件保留作为备份，不再被读取。

## API 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/profile` | 读取/保存个人档案 |
| GET | `/api/evidence` | 列出履历证据 |
| POST | `/api/evidence` | 添加证据 |
| PUT | `/api/evidence/{id}` | 更新证据 |
| DELETE | `/api/evidence/{id}` | 删除证据 |
| POST | `/api/evidence/sections` | 按栏目批量保存 |
| DELETE | `/api/evidence/section/{category}` | 删除整个栏目 |
| GET/POST | `/api/jobs` | 列出/添加岗位 |
| DELETE | `/api/jobs/{id}` | 删除岗位 |
| GET/POST | `/api/analyses` | 列出/运行匹配分析 |
| PUT | `/api/analyses/{id}` | 增强分析（语义分数） |
| DELETE | `/api/analyses/{id}` | 删除分析 |
| GET/POST | `/api/resume-versions` | 列出/添加定制版本 |
| DELETE | `/api/resume-versions/{id}` | 删除版本 |
| GET/POST/PUT | `/api/applications` | 列出/添加/更新投递记录 |
| DELETE | `/api/applications/{id}` | 删除记录 |
| POST | `/api/library/ask` | 资料问答 |
| GET | `/api/library/search` | 检索调试 |
| POST | `/api/library/index` | 重建索引 |
| POST | `/api/library/upload` | 上传文件 |
| GET/DELETE | `/api/library/documents` | 管理文档 |
| POST | `/api/library/extract-resume` | 解析简历文件 |
| POST | `/api/library/extract-job-text` | 解析 JD 文本 |
| POST | `/api/library/extract-job-file` | 解析 JD 文件 |
| POST | `/api/library/semantic-match` | 语义匹配分析 |
| POST | `/api/library/tailor-resume` | 定制简历 |
| POST | `/api/library/export-resume` | 导出 Word/PDF |
| POST | `/api/library/agent` | 智能助手对话 |
| POST | `/api/library/summarize` | 生成资料摘要 |
| GET/DELETE | `/api/library/history` | 管理问答历史 |

## 目录结构

```text
├── app.py                    # Streamlit 前端（7 个页面）
├── api/                      # FastAPI 后端
│   ├── main.py               # 应用工厂 + 全局异常处理
│   ├── deps.py               # 依赖注入（CareerStore / RagAssistant 单例）
│   ├── models.py             # Pydantic 请求/响应模型
│   └── routes/               # 路由模块
│       ├── profile.py        # 个人档案
│       ├── evidence.py       # 履历证据
│       ├── jobs.py           # 岗位管理
│       ├── analyses.py       # 匹配分析
│       ├── resume_versions.py # 简历版本
│       ├── applications.py   # 投递记录
│       ├── library.py        # 资料库 + Agent + 导出
│       └── history.py        # 问答历史
├── api_client.py             # HTTP 客户端（镜像 CareerStore/RagAssistant 接口）
├── career_store.py           # 业务数据 CRUD（SQLite / JSON 双模式）
├── db.py                     # SQLite 数据库层
├── rag_agent.py              # RAG 核心：检索、问答、提取、匹配、定制
├── agent.py                  # Tool Calling Agent（ReAct 循环）
├── tools.py                  # 8 个 LangChain 工具定义
├── bm25_index.py             # BM25 关键词索引
├── resume_export.py          # 简历导出 Word / PDF
├── cli.py                    # 命令行界面
├── migrate_json_to_sqlite.py # JSON → SQLite 迁移脚本
├── tests/                    # 40 项自动化测试
├── data/                     # 运行时数据
│   ├── career.db             # SQLite 数据库
│   ├── uploads/              # 上传的参考资料
│   ├── resume_uploads/       # 导入的简历文件
│   ├── job_uploads/          # 导入的 JD 文件
│   ├── chroma/               # Chroma 向量库
│   ├── bm25/                 # BM25 索引
│   └── history.jsonl         # 问答历史
└── documents/                # 手动放入的参考资料
```

## 效果截图

> TODO: 补充各页面截图

| 页面 | 截图 |
|------|------|
| 个人档案 | ![个人档案](docs/screenshots/profile.png) |
| 岗位库 | ![岗位库](docs/screenshots/jobs.png) |
| 匹配分析 | ![匹配分析](docs/screenshots/analysis.png) |
| 简历定制 | ![简历定制](docs/screenshots/resume.png) |
| 智能助手 | ![智能助手](docs/screenshots/agent.png) |

## 运行测试

```bash
python -m unittest discover tests -v
```

## 重要说明

- 聊天模型（`qwen3.6-plus`）和嵌入模型（`tongyi-embedding-vision-flash`）不能混用。聊天模型负责理解问题和生成回答，嵌入模型负责将文本转换为向量。
- 所有 AI 生成的简历建议都基于用户已确认的履历证据，不会凭空补充经历。
- 匹配分析在履历变化后会标记为需重算，旧结果保留为历史供对比。
