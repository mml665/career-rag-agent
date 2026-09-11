# Career RAG 评测

这个目录提供一个不依赖在线 LLM 的检索评测入口。它把“项目里实现了混合检索”变成可复现的 Recall@K、MRR@K 和 Hit Rate@K 指标。

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
