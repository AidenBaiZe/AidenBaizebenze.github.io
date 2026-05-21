# ArangoDB 数据模型

本项目只使用一个数据库：ArangoDB。选择理由是它同时支持文档模型、图模型和 AQL 查询，能覆盖 2WikiMultihopQA 的原始问答数据管理、多跳路径查询、检索、聚类和可视化导出。

## Vertex collections

- `questions`：问题、答案、类型、split、cluster、support_count。
- `articles`：Wikipedia 页面标题。
- `sentences`：页面中的句子，包含 `title`、`sent_id`、`text`、`is_supporting_fact`。
- `answers`：标准答案。
- `entities`：证据链中的实体。
- `clusters`：简单文本聚类结果。

## Edge collections

- `question_article`：问题关联候选上下文文章。
- `article_sentence`：文章包含句子。
- `question_sentence`：问题的 supporting facts。
- `question_answer`：问题对应答案。
- `question_entity`：问题证据链实体和关系。
- `cluster_question`：聚类包含的问题。

## 多跳示例

典型路径如下：

```text
Question -> Article -> Sentence
Question -> Entity -> Evidence relation
Question -> Answer
Cluster -> Question -> Supporting Sentence
```

这些路径可以用 `FOR v, e, p IN 1..3 OUTBOUND ...` 查询，并直接导出为网页中的图节点和边。
