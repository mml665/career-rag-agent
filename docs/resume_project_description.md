# 简历项目描述

## 项目名称

基于 RAG 与 Tool Calling 的智能选岗及简历定制 Agent

## 一句话介绍

一个面向求职场景的前后端分离 Agent 应用，支持个人履历管理、岗位 JD 解析、岗位匹配分析、简历定制生成、投递记录管理和参考资料库 RAG 问答。

## 简历版项目描述

设计并实现一个智能求职工作台，围绕“个人档案 -> 岗位库 -> 匹配分析 -> 简历定制 -> 投递记录”的求职流程构建完整业务闭环。系统前端采用 Vue3 + TypeScript + Element Plus，后端采用 FastAPI + SQLite，AI 能力接入阿里云 DashScope。RAG 部分使用 DashScope Embedding、Chroma、BM25、RRF 融合排序和 Rerank 完成资料检索问答；Agent 部分基于 LangChain Tool Calling 封装岗位查询、履历证据、匹配分析、简历定制和资料库问答等工具，实现多步任务自动执行。

## 技术栈写法

Vue3、TypeScript、Vite、Element Plus、Pinia、Vue Router、FastAPI、Pydantic、SQLite、LangChain Tool Calling、DashScope、Chroma、BM25、jieba、RRF、Rerank、python-docx、reportlab

## 亮点写法

- 设计并实现前后端分离架构，使用 Vue3 + TypeScript 构建求职工作台，FastAPI 提供个人档案、岗位库、匹配分析、简历版本、投递记录和资料库等 REST API。
- 实现基于 RAG 的参考资料库，支持 PDF / Markdown / TXT 文档解析、切分、Embedding、Chroma 入库、来源引用和问答历史管理。
- 构建向量检索 + BM25 的混合召回流程，使用 RRF 融合排序，并通过相似度阈值与 Rerank 提升检索准确性。
- 基于 LangChain Tool Calling 封装 8 个业务工具，使智能助手能够自动调用岗位查询、履历证据、匹配分析、简历定制和资料库问答能力。
- 实现基于已确认履历证据的岗位匹配和简历定制，避免模型凭空编造经历，并支持定制版本保存及 Word / PDF 导出。
- 使用 SQLite 管理业务数据，Chroma 管理向量数据，补充单元测试覆盖 Agent、Embedding、检索阈值、岗位解析、履历证据和简历定制等核心逻辑。

## 面试讲解思路

1. 先讲业务闭环：这个项目不是单纯聊天，而是围绕真实求职流程做了数据管理、分析、生成和记录。
2. 再讲 RAG：资料进入系统后会解析、切分、向量化、写入 Chroma；提问时先召回，再拼成 context 给模型生成答案。
3. 再讲混合检索：向量适合语义相似，BM25 适合关键词和编号精确匹配，RRF 用来融合两路结果。
4. 再讲 Agent：Agent 不直接回答所有问题，而是根据用户意图调用工具，比如查询岗位、读取履历、做匹配分析。
5. 最后讲工程化：前后端分离、SQLite 持久化、导出能力、测试覆盖和异常兜底。

## 可量化表述

- 封装 8 个 Tool Calling 工具，覆盖岗位、履历、匹配分析、简历定制和资料库问答。
- 实现 7 个前端功能页面，覆盖完整求职工作流。
- 单元测试覆盖 Agent、RAG、Embedding、岗位解析、履历证据、历史管理等核心模块。
- 支持 Word / PDF 简历导出，支持本地资料库重建索引和检索调试。
