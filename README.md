# 智能选岗及简历定制 Agent

这是一个从 RAG 资料问答底座演进出的求职工作流应用：管理真实履历与岗位 JD，分析技能匹配，针对岗位生成不虚构经历的简历建议，并记录投递进展。PDF、Markdown、TXT 的 RAG 检索能力保留为参考资料库。

当前版本默认使用阿里云百炼 DashScope：

- 聊天模型：`qwen3.6-plus`
- 嵌入模型：`tongyi-embedding-vision-flash-2026-03-06`
- 兼容地址：`https://dashscope.aliyuncs.com/compatible-mode/v1`

## 你会练到什么

- LLM 调用：`ChatOpenAI` 连接 DashScope OpenAI 兼容接口
- Embedding：DashScope 多模态 Embedding HTTP 接口
- 文档加载：PDF / Markdown / TXT
- 文档切分：`RecursiveCharacterTextSplitter`
- 向量库：Chroma
- RAG：检索片段后再生成回答
- Agent 工具雏形：检索、问答、总结、列来源、历史记录
- 求职业务数据：姓名/联系方式/求职意向、整页履历与岗位 JD 持久化管理
- 简历解析回填：上传 PDF / Markdown / TXT 简历，由模型提取基础信息与履历草稿，确认后入档
- JD 导入解析：上传 PDF / Markdown / TXT 或粘贴文本，调用模型回填公司、岗位、地点与要求，保存前可人工复核
- 岗位匹配：保留关键词覆盖基线，并可叠加 Embedding 语义分数与基于证据的模型解释
- 匹配历史：履历新增、修改或删除后保留旧分析并标记为需重算，方便比较前后效果
- 简历定制：依据目标 JD 和已确认履历生成推荐表述，可保存为岗位定制版本或核验后写入档案
- 投递管理：维护投递状态、关联所用定制简历版本，并记录复盘备注
- 稳定交互：功能页保持当前位置，长耗时操作限制在当前工作区；定制表述经人工核验后可写入个人档案

## 快速开始

```powershell
conda activate Agent
pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `.env`，填入你的阿里云百炼 API Key：

```env
DASHSCOPE_API_KEY=your_dashscope_api_key_here
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen3.6-plus
OPENAI_EMBEDDING_MODEL=tongyi-embedding-vision-flash-2026-03-06
```

启动界面：

```powershell
python -m streamlit run app.py
```

命令行体验：

```powershell
python 11.py
```

## 使用方式

1. 在“个人档案”上传已有简历自动回填草稿，或手动填写姓名、联系方式和履历内容；模型提取内容需核对确认后再保存。
2. 在“岗位库”上传岗位 PDF / Markdown / TXT 或粘贴 JD；调用模型回填岗位草稿，复核后保存。
3. 在“匹配分析”先运行关键词基线；配置 API Key 后可运行混合分析，比较关键词分数、语义分数与模型解释；履历变化后的旧分析会作为历史保留。
4. 在“简历定制”选择岗位和已确认履历，生成针对岗位的改写建议；可保存岗位定制版本，也可核对真实后采纳到个人档案。
5. 在“投递记录”关联已保存的定制版本，并维护投递状态与复盘备注。
6. 在“参考资料库”上传简历写作规范或公司资料，重建索引后进行有来源的问答、检索和总结；摘要与问答历史支持单条删除或全部清空。

## 重要说明

聊天模型和嵌入模型不能随意混用。聊天模型负责理解问题和生成回答，例如 `qwen3.6-plus`；嵌入模型负责把文本片段转换成固定维度向量，例如 `tongyi-embedding-vision-flash-2026-03-06`。像 MiMo-V2.5-Pro 这类生成模型不适合作为 Chroma 的嵌入模型。

## 推荐练习

- 用 3-5 篇你熟悉的资料测试事实型问题。
- 提一个资料中没有答案的问题，观察是否会明确说“资料中未找到相关信息”。
- 调整 Chunk size、Overlap、Top K，比较答案质量。
- 调整最低相关性，在“参考资料库”的“检索调试”中观察候选片段分数以及哪些片段会进入回答上下文。
- 修改 `rag_agent.py` 里的 prompt，观察引用和拒答效果变化。

## 目录说明

- `app.py`：Streamlit 小应用。
- `rag_agent.py`：RAG 核心逻辑、简历/JD 提取、语义匹配解释和 DashScope embedding 适配器。
- `career_store.py`：个人履历证据、岗位 JD、混合匹配、定制版本与投递记录的结构化存储。
- `11.py`：命令行版本。
- `documents/`：手动放资料的位置。
- `data/uploads/`：网页上传文件保存位置。
- `data/resume_uploads/`：导入个人档案的原始简历文件。
- `data/job_uploads/`：导入岗位库的原始 JD 文件。
- `data/career/`：个人档案、岗位、匹配分析、定制版本及投递记录数据。
- `data/chroma/`：Chroma 向量库。
- `data/history.jsonl`：问答历史记录。
- `docs/`：智能求职 Agent 的设计文档。
- `面试/`：项目面试总结与复习资料。
