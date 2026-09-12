# Career RAG 评测

这个目录提供不依赖在线 LLM 的离线评测入口，也支持在需要时接入当前本地 Agent 做 live 评测。它把“项目里实现了混合检索和 Agent 工具编排”变成可复现的指标。

## 评测覆盖范围

- RAG 检索：Recall@K、MRR@K、Hit Rate@K。
- Agent 轨迹：工具选择准确率、工具召回率、调用顺序、工具错误、最大调用次数。
- 最终答案：必含关键词、禁用词、成功状态是否符合预期。
- 人工反馈：准确率代理指标、问题分布、可处理 Bad Case。

## 多测评集可信度设计

`agent_eval_suites.json` 和 `retrieval_eval_suites.json` 把评测样本拆成多套 suite，而不是把所有 case 混成一个总分：

- `seed`：核心链路种子集，只能证明基础流程可回归。
- `directional`：中文改写、相近意图和不同资料来源，用于观察检索调参趋势。
- `regression`：真实业务工作流回归集，用于防止已修复流程退化。
- `robustness`：否定表达、错误 job_id、只读意图等异常或防误调用场景。

统一运行入口：

```bash
python evals/multi_eval.py --live-agent --live-retrieval --k 5 --output evals/latest_multi_metrics.json
```

多测评的 RAG 默认使用 `--retrieval-mode bm25_only`，作为稳定、离线的关键词召回基线。需要评估真实向量检索、BM25 融合和 Rerank 时使用：

```bash
python evals/multi_eval.py --live-retrieval --retrieval-mode hybrid_live --k 5
```

多测评默认使用 `--agent-tool-mode fixture_tools`，即真实执行 Agent 路由、工具选择和错误处理，但把资料问答、简历定制这类 LLM 生成型工具替换成稳定 fixture 输出，适合 CI 和面试演示。若要评估真实在线工具效果：

```bash
python evals/multi_eval.py --live-agent --agent-tool-mode live_tools --live-retrieval --k 5
```

如果要单独评估模型自主工具选择能力，可以关闭确定性路由：

```bash
python evals/multi_eval.py --live-agent --agent-routing-modes llm_autonomy --output evals/latest_multi_metrics.json
```

也可以同时跑两种模式：

```bash
python evals/multi_eval.py --live-agent --agent-routing-modes deterministic_first llm_autonomy --live-retrieval --k 5
```

报告会分别输出每个 suite 的指标、目标值达成情况和 `confidence_note`。简历或面试中不要只说 overall 100%，应说明样本规模、suite 类型和路由模式。

## 运行本地检索评测

在项目根目录执行：

```bash
python evals/retrieval_eval.py --live --k 5 --output evals/latest_metrics.json
```

`--live` 会读取当前本地 Chroma/BM25 索引，不会调用聊天模型。首次运行前应确认 `data/chroma` 和 `data/bm25` 已经存在。

如果只想跑稳定离线关键词基线：

```bash
python evals/retrieval_eval.py --live --retrieval-mode bm25_only --k 5
```

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

默认 `--routing-mode deterministic_first` 会先走确定性工具路由，再回退到 LLM Tool Calling。若要测试纯模型自主工具选择：

```bash
python evals/agent_eval.py --live --routing-mode llm_autonomy --output evals/latest_agent_metrics.json
```

单项 Agent 脚本默认使用真实工具输出。需要稳定回归测试时可使用：

```bash
python evals/agent_eval.py --live --tool-mode fixture_tools --output evals/latest_agent_metrics.json
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
