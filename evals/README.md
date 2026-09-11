# Career RAG 评测

这个目录提供不依赖在线 LLM 的离线评测入口，也支持在需要时接入当前本地 Agent 做 live 评测。它把“项目里实现了混合检索和 Agent 工具编排”变成可复现的指标。

## 评测覆盖范围

- RAG 检索：Recall@K、MRR@K、Hit Rate@K。
- Agent 轨迹：工具选择准确率、工具召回率、调用顺序、工具错误、最大调用次数。
- 最终答案：必含关键词、禁用词、成功状态是否符合预期。
- 人工反馈：准确率代理指标、问题分布、可处理 Bad Case。

## 运行本地检索评测

在项目根目录执行：

```bash
python evals/retrieval_eval.py --live --k 5 --output evals/latest_metrics.json
```

`--live` 会读取当前本地 Chroma/BM25 索引，不会调用聊天模型。首次运行前应确认 `data/chroma` 和 `data/bm25` 已经存在。

## 使用固定结果做 CI 评测

结果文件格式：

```json
{
  "results": [
    {
      "case_id": "resume_001",
      "results": [{"source": "简历写作规范.md", "score": 0.91}]
    }
  ]
}
```

执行：

```bash
python evals/retrieval_eval.py --results evals/results.json --k 5
```

`golden_set.json` 只是起始样本。正式写入简历前，应扩展到至少 50 条人工标注问题，并分别比较向量检索、BM25、RRF 和 Rerank 配置。

## 运行 Agent 离线评测

固定结果文件格式：

```json
{
  "results": [
    {
      "case_id": "agent_jobs_001",
      "answer": "当前保存了 2 个岗位。",
      "success": true,
      "steps": [{"tool_name": "list_jobs"}]
    }
  ]
}
```

执行：

```bash
python evals/agent_eval.py --results evals/agent_results.json --output evals/latest_agent_metrics.json
```

也可以接当前 Agent 运行 live 评测：

```bash
python evals/agent_eval.py --live --output evals/latest_agent_metrics.json
```

`agent_golden_set.json` 目前覆盖资料问答、岗位列表、岗位匹配、简历定制和个人档案读取。正式引用指标前，应把真实用户问题和审计日志中的失败样本扩充进去。

## 汇总匹配反馈 Bad Case

匹配分析页面会记录人工反馈，例如证据不相关、漏匹配技能、幻觉表述、引用错误等。可以用下面命令把反馈汇总成可复盘指标：

```bash
python evals/match_feedback_eval.py --input data/career/match_feedback.json
```

输出包括：

- `accuracy_proxy`：人工标注为准确的比例，可作为匹配质量的代理指标。
- `issue_distribution`：各类问题分布，用于判断下一轮优化方向。
- `actionable_cases`：需要修复或沉淀进评测集的 Bad Case。

这部分和检索评测结合后，可以形成“线上反馈 -> Bad Case -> golden set -> 调参/改提示词/改工具 -> 回归评测”的迭代闭环。

## 推荐迭代流程

1. 从 Agent 审计日志和页面反馈中筛选失败样本。
2. 将稳定可复现的问题写入 `agent_golden_set.json` 或 `golden_set.json`。
3. 调整工具描述、Prompt、检索参数或业务校验逻辑。
4. 运行离线评测，确认 pass rate、tool recall、Recall@K 等指标没有回退。
5. 再用少量 live case 验证真实 Agent 表现。
