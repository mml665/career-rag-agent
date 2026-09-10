# RAG 文档解析与检索增强说明

## 目标

本模块用于回答两个核心问题：

1. 上传 PDF 后，系统如何判断它是文本型、扫描型、拍照型、图片混合型还是低质量文件。
2. 检索时系统到底按什么粒度召回，是按标题、段落、句子还是 chunk。

当前实现采用“文档体检 + 结构化切分 + 混合检索 + 可解释 metadata”的设计，不再把所有文件简单当纯文本处理。

## PDF 上传分类

上传 PDF 后先生成 `DocumentInspectionReport`，核心字段包括：

```text
document_type
parser_strategy
page_count
text_chars
avg_chars_per_page
image_count
image_pages
image_page_ratio
rotated_pages
has_text_layer
needs_ocr
requires_visual_review
quality_score
warnings
```

分类规则：

| 类型 | 判断依据 | 处理策略 |
| --- | --- | --- |
| `text_pdf` | 文本层较充分，图片占比低 | 直接走文本层解析 |
| `low_text_pdf` | 有文本层但文本密度低 | 文本层解析，同时提示人工复核 |
| `mixed_pdf` | 有文本层且图片页占比较高 | 文本层解析，图片内容后续可走 OCR 补充 |
| `scanned_or_photo_pdf` | 文本层为空或极少，页面以图片为主 | 标记 `needs_ocr=true`，需要 OCR 兜底 |
| `encrypted_pdf` | 加密且无法解密 | 拒绝解析，提示用户处理文件 |
| `damaged_pdf` | PDF 无法打开 | 拒绝解析，提示重新上传 |

当前项目不直接内置 PaddleOCR / OpenCV，原因是这两个依赖较重，部署复杂度较高。第一版先完成可稳定运行的分类和路由决策；生产增强版可以在 `needs_ocr=true` 时接入 OCR 服务。

## 歪斜、拍照和图片内容

当前可识别：

- PDF 页面是否有旋转角度：通过 `/Rotate` 判断，写入 `rotated_pages`。
- 是否疑似扫描或拍照件：通过文本密度和图片页占比判断。
- 是否需要视觉复核：扫描/拍照件或页面旋转时标记 `requires_visual_review=true`。

生产增强版可以继续补：

```text
PDF 渲染为图片
-> OpenCV 灰度化
-> 二值化 / 去噪
-> 文本边缘或 Hough 直线估计倾斜角
-> deskew 旋转回正
-> OCR
-> OCR 置信度评估
```

面试时要讲清楚：当前版本已经具备分类与策略选择能力，OCR 和 deskew 是预留扩展点，不把未实现内容说成已完成。

## 文档切分策略

系统不是按整篇文档检索，也不是只按单句检索，而是按带 metadata 的 chunk 检索。

当前切分链路：

```text
Markdown
-> 先按 # / ## / ### 标题切成章节
-> 每个章节再按段落 / 换行 / 句子递归切 chunk
-> chunk 保留 heading_path 和 section_title

TXT
-> 作为纯文本
-> 按段落 / 换行 / 句子递归切 chunk

PDF
-> 先按页提取文本
-> 保留 page 页码
-> 按段落 / 换行 / 句子递归切 chunk
```

递归分隔符顺序：

```python
["\n\n", "\n", "。", "！", "？", ". ", " ", ""]
```

含义：

```text
优先保持段落完整
段落太长再按换行
再按中文句子
再按英文句子
最后才按空格或字符硬切
```

## Chunk Metadata

每个 chunk 入库时会带上：

```text
chunk_id
chunk_index
source_name
heading_path
section_title
document_type
parser_strategy
chunk_strategy
token_count
quality_score
needs_ocr
page
```

这些字段用于：

- 检索结果展示来源。
- 解释为什么命中某个片段。
- 根据章节、页码或文档类型做过滤。
- 后续做检索评测和 bad case 分析。

## 检索流程

当前检索不是只走向量库，而是混合检索：

```text
用户问题
-> DashScope Embedding
-> Chroma 向量召回 top_k * 2
-> BM25 中文关键词召回 top_k * 2
-> RRF 融合排序
-> 使用原始向量相似度做阈值过滤
-> DashScope Rerank 精排
-> 返回 top_k chunks
-> 拼接 context 给 LLM 回答
```

向量检索解决语义相似问题，BM25 解决关键词、技术名词、公司名、岗位名、编号等精确命中问题。

## 为什么用 RRF

RRF 的作用是融合不同检索器的排名，而不是直接融合分数。因为向量相似度和 BM25 分数不在同一个数值空间，直接加权平均容易失真。

RRF 计算思路：

```text
score = weight / (rrf_k + rank + 1)
```

排名越靠前贡献越大。向量和 BM25 都召回的 chunk 会得到更高融合分。

## 阈值和 Rerank

RRF 主要负责排序，不适合作为相关性阈值。当前系统使用原始向量相似度做阈值过滤，避免 BM25 只命中少量关键词但语义不相关的片段进入最终上下文。

Rerank 失败时会降级为 RRF 排序结果，保证检索链路可用。

## 面试官可能追问

### PDF 解析

1. 如何判断 PDF 是文本型还是扫描型。
2. 如果 PDF 是歪斜拍照件怎么办。
3. 如果 PDF 里既有文字又有图片怎么办。
4. 如果图片里有重要文字怎么办。
5. 如果 PDF 是双栏排版，文本顺序乱怎么办。
6. 如果 PDF 是表格型简历或 JD，怎么处理。
7. OCR 识别错了怎么降低影响。
8. OCR 结果是否直接入库，需不需要人工确认。
9. PDF 加密、损坏、空白页怎么处理。
10. 如何衡量解析质量。

### Chunk 切分

1. 为什么不能整篇文档 embedding。
2. 为什么不能按单句切。
3. 标题信息会不会丢。
4. chunk_size 和 chunk_overlap 怎么选。
5. chunk 超过 embedding token 限制怎么办。
6. 不同类型文档是否应该使用不同切分策略。
7. 如何处理标题跨 chunk 的问题。
8. 如何处理表格和列表。
9. 如何避免重复 chunk。
10. 文档更新后旧 chunk 怎么删除。

### 检索排序

1. 向量检索和 BM25 分别解决什么问题。
2. 为什么要用 RRF，而不是简单加权分数。
3. Rerank 放在召回前还是召回后。
4. 阈值用 RRF 分还是向量分。
5. 查询里有公司名、岗位名、技术名词时怎么保证准确召回。
6. 检索不到答案时怎么避免模型胡编。
7. 多个来源冲突时怎么回答。
8. 如何评估 RAG 检索质量。
9. 如何记录 bad case。
10. 如何降低 embedding 和 rerank 成本。

### Agent 工程化

1. Agent 什么时候调用检索工具，什么时候调用岗位工具。
2. 工具调用失败如何兜底。
3. 长期记忆如何避免污染后续回答。
4. 哪些信息允许写入长期记忆。
5. 执行审计记录哪些字段。
6. 如何用审计日志做模型评测。
7. 如何防止简历定制编造经历。
8. 如何保证输出引用真实来源。

## 简历可写点

可以写成：

> 设计文档解析质量识别与结构化切分模块，上传 PDF 后基于文本密度、图片页占比、页面旋转和文本层可用性判断文本型、低文本型、图片混合型、扫描/拍照型、加密/损坏等文档类型，并选择文本层解析、人工复核或 OCR 兜底策略；优化 RAG chunk 入库 metadata，记录标题路径、页码、解析策略、token 数和质量分，提升检索结果的可解释性和复杂文档解析鲁棒性。

也可以拆成两条：

> 实现 PDF 文档体检与分类识别，基于文本密度、图片页占比和页面旋转等指标判断文本型、图片混合型、扫描/拍照型和低质量 PDF，为 OCR 兜底、人工复核和解析策略选择提供依据。

> 优化 RAG 文档切分策略，对 Markdown 按标题层级切分并保留 `heading_path`，对 PDF 保留页码和解析质量 metadata，再通过段落、换行、句子递归切分生成 chunk，使检索结果支持来源、章节、页码和质量分追踪。
