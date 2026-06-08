# 2WikiMultihopQA 多跳问答数据的 ArangoDB 管理与可视化

## 1. 任务目标

本项目从课程数据库范围中选择 ArangoDB，对 2WikiMultihopQA 多跳问答数据集进行管理，并构建 GitHub Pages 演示网页。系统支持数据检索、多跳推理路径查询、简单聚类和可视化展示。

## 2. 数据集

数据集选择 2WikiMultihopQA。该数据集面向多跳问答任务，每条样本包含问题、答案、上下文文章、supporting facts 和 evidence relation。核心字段包括：

- `_id`：问题编号
- `type`：问题类型，例如 comparison、compositional、inference 或 bridge comparison
- `question`：自然语言问题
- `context`：候选 Wikipedia 页面及句子
- `supporting_facts`：推理所需的关键证据句
- `evidences`：实体和关系形式的证据链
- `answer`：标准答案

该结构天然具有图关系特征，适合用图数据库或多模型数据库表达。

## 3. 数据库选择

本项目选择 ArangoDB，而不是多个数据库组合。

原因如下：

- ArangoDB 同时支持文档模型和图模型，可以用一个数据库完成原始文档存储和多跳关系查询。
- AQL 支持图遍历，适合表达 `Question -> Article -> Sentence -> Answer/Entity` 的多跳路径。
- ArangoDB 可以对问题、答案、句子字段建立索引，用于关键词检索。
- 聚类结果可以作为普通文档集合保存，并通过边连接到问题节点。
- 相比 MongoDB、Cassandra、HBase 等，ArangoDB 更适合多跳问答这种关系密集型数据。
- 相比 Neo4j，ArangoDB 对原始 JSON 文档和图关系的统一管理更方便。

## 4. 系统架构

由于 GitHub Pages 只支持静态网页托管，不能直接部署 ArangoDB 服务或后端 API，因此本项目采用“ArangoDB 本地数据库管理 + AQL 查询 + JSON 导出 + GitHub Pages 前端展示”的架构。

完整数据首先导入 ArangoDB，在 ArangoDB 中建立文档集合、边集合和 `reasoning_graph`；多跳查询、检索和聚类统计由 AQL 和 Python 脚本完成。随后将部分演示数据导出为 `demo-data.json`，由静态网页读取并完成交互式检索和可视化展示。

```text
2WikiMultihopQA 原始数据
        ↓
prepare_dataset.py 清洗、抽取实体、构造节点和边
        ↓
ArangoDB 文档集合 + 边集合 + reasoning_graph
        ↓
AQL 多跳查询 / 关键词检索 / 聚类统计
        ↓
export_demo_from_arango.py 导出 demo-data.json
        ↓
GitHub Pages 前端检索、路径图、证据展示、聚类可视化
```

## 5. 数据模型设计

项目使用一个 ArangoDB 数据库 `mhqa_arangodb` 和一个图 `reasoning_graph`。

顶点集合：

- `questions`：存储问题、答案、类型、数据划分、聚类编号等。
- `articles`：存储 Wikipedia 页面标题。
- `sentences`：存储文章中的句子和句子编号。
- `answers`：存储答案文本。
- `entities`：存储 evidence 中涉及的实体。
- `clusters`：存储简单聚类结果。

边集合：

- `question_article`：问题关联上下文文章。
- `article_sentence`：文章包含句子。
- `question_sentence`：问题关联 supporting facts。
- `question_answer`：问题对应答案。
- `question_entity`：问题关联证据实体和关系。
- `cluster_question`：聚类结果关联问题。

典型多跳路径：

```text
Question -> Article -> Sentence
Question -> Entity
Question -> Answer
Cluster -> Question -> Supporting Sentence
```

## 6. 查询、检索与聚类

检索功能通过问题、答案、类型和聚类编号进行关键词过滤，AQL 示例见 `arango/queries.aql`。

多跳过程查询使用 ArangoDB 图遍历：

```aql
LET q = DOCUMENT(CONCAT("questions/", @question_key))
FOR v, e, p IN 1..3 OUTBOUND q
  question_article, article_sentence, question_sentence, question_answer, question_entity
  RETURN {
    vertex: v,
    edge: e,
    path: p.vertices[*]._id
  }
```

该查询可以返回 `Question -> Article -> Sentence`、`Question -> Entity` 和 `Question -> Answer` 等路径，网页中的 Graph 视图展示的就是这类 reasoning path 的静态导出结果。

简单聚类使用 `question + answer + type` 文本构建 TF-IDF 向量，然后用 KMeans 聚类。聚类编号写入 `questions.cluster`，同时创建 `clusters` 集合和 `cluster_question` 边。

## 7. 网页可视化

网页位于 `web/` 目录，可由 GitHub Pages 托管。主要功能包括：

- 搜索问题、答案、类型和聚类编号。
- 按 comparison / compositional / inference / bridge comparison 类型过滤。
- 展示选中问题的多跳推理路径图。
- 展示 supporting facts 和 evidence relations。
- 展示问题类型分布和聚类分布柱状图。

网页读取 `web/demo-data.json`。该文件可以由 `scripts/export_demo_from_arango.py` 从 ArangoDB 查询结果导出，适合 GitHub Pages 静态演示。由于 GitHub Pages 是静态网页，前端嵌入 100 条问题的图结构用于交互演示；原始 `train/dev/test` 全量数据已保存在仓库中，且全部 192606 条记录均已生成 ArangoDB JSONL 导入文件。页面同时展示全量原始记录数、全量索引记录数和前端演示子集规模。

## 8. 运行流程

```bash
conda activate nosql
cd <project-root>
python -m pip install -r requirements.txt
python scripts/prepare_dataset.py --zip ~/Downloads/data.zip --limit 999999 --demo-limit 100
python scripts/import_arango.py --host http://localhost:8529 --username root --password openSesame --database mhqa_arangodb --truncate
python scripts/export_demo_from_arango.py --host http://localhost:8529 --username root --password openSesame --database mhqa_arangodb --demo-limit 100 --output web/demo-data.json
python -m http.server 8000 -d web
```

浏览器访问：

```text
http://localhost:8000
```

## 9. 答辩说明

本项目使用 ArangoDB 单数据库完成 2WikiMultihopQA 数据管理。文档模型保存问题、上下文和答案，图模型表达问题、文章、句子、实体和聚类之间的关系。AQL 图遍历实现多跳过程查询，TF-IDF + KMeans 实现简单聚类，GitHub Pages 页面负责检索和可视化展示。

如果被问到“为什么网页没有直接连接数据库”，可以说明：GitHub Pages 是静态托管环境，不能运行数据库服务或后端 API，因此数据库管理和 AQL 查询在本地 ArangoDB 中完成，网页展示的是从数据库导出的查询结果快照。这种架构保留了数据库管理和查询过程，同时满足 GitHub Pages 在线演示要求。
