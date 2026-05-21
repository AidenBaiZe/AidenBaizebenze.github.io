# OCT: 2WikiMultihopQA + ArangoDB 多跳问答演示

本项目完成课程任务：选择课程范围内的一种 NoSQL 数据库管理多跳问答数据，并建立 GitHub Pages 演示网页，支持多跳过程查询、检索、简单聚类和可视化。

## 技术选择

- 数据集：2WikiMultihopQA
- 数据库：ArangoDB
- 数据库类型：多模型 NoSQL，兼具文档数据库和图数据库能力
- 查询语言：AQL
- 网页托管：GitHub Pages
- 网页实现：HTML + CSS + JavaScript，读取静态导出的 `web/demo-data.json`

选择 ArangoDB 的原因是它可以在一个数据库内同时管理原始问答文档、实体关系图、证据句路径和聚类结果，避免 MongoDB + Neo4j + 搜索引擎的多系统复杂度。

## 目录结构

```text
OCT/
  arango/
    queries.aql          # 多跳查询、检索、聚类 AQL 示例
    schema.md            # ArangoDB 数据模型
  data/
    raw/                 # 放置下载或解压后的原始数据
    processed/           # 生成的 ArangoDB JSONL 导入文件
  docs/
    report.md            # 中文课程报告草稿
  scripts/
    prepare_dataset.py   # 解压/读取数据、建模、聚类、导出网页数据
    import_arango.py     # 导入 ArangoDB
  web/
    index.html           # GitHub Pages 页面
    styles.css
    app.js
    demo-data.json       # 网页演示数据，由脚本生成
```

## 使用 nosql 环境

```bash
conda activate nosql
cd /Users/keweisu/Documents/school/NoSQL/OCT
python -m pip install -r requirements.txt
```

当前环境已经安装过 `pyarrow`、`scikit-learn` 和 `python-arango`。

## 准备数据

如果浏览器下载的文件是 `/Users/keweisu/Downloads/data.zip`，运行：

```bash
conda run -n nosql python scripts/prepare_dataset.py --zip ~/Downloads/data.zip --limit 5000 --demo-limit 80
```

脚本会：

- 把 `data.zip` 复制到 `OCT/data/raw/`；
- 解压 zip；
- 读取 `parquet/json/jsonl` 数据；
- 生成 ArangoDB 可导入的 JSONL 文件；
- 用 TF-IDF + KMeans 做简单聚类；
- 生成 GitHub Pages 使用的 `web/demo-data.json`。

当前 GitHub Pages 为了加载速度，前端只嵌入 10 条问题的多跳图演示；页面中的 `total records` 显示全量原始数据条数，`indexed records` 显示当前生成 ArangoDB JSONL 时处理的记录数。当前版本已经对全部 192606 条记录生成 ArangoDB JSONL。

GitHub 普通 Git 单文件限制为 100MB，因此仓库中较大的 `train.json` 和部分全量 `data/processed/*.jsonl` 文件使用分片保存。克隆后运行：

```bash
cd data
./restore_train.sh
cd processed
./restore_processed.sh
```

如果真实数据还没有下载完成，可以先运行样例验证：

```bash
conda run -n nosql python scripts/prepare_dataset.py --sample-fallback
```

## 导入 ArangoDB

先确保本机或远程有 ArangoDB 服务，例如地址为 `http://localhost:8529`。

```bash
conda run -n nosql python scripts/import_arango.py \
  --host http://localhost:8529 \
  --username root \
  --password openSesame \
  --database oct_multihop \
  --truncate
```

导入后会创建：

- vertex collections：`questions`、`articles`、`sentences`、`answers`、`entities`、`clusters`
- edge collections：`question_article`、`article_sentence`、`question_sentence`、`question_answer`、`question_entity`、`cluster_question`
- graph：`reasoning_graph`

## 本地预览网页

```bash
cd /Users/keweisu/Documents/school/NoSQL/OCT
python -m http.server 8000 -d web
```

然后打开：

```text
http://localhost:8000
```

## GitHub Pages 部署

如果使用普通项目仓库，把 `OCT/web` 目录作为 GitHub Pages 站点目录，在仓库 Settings -> Pages 中选择：

- Source: Deploy from a branch
- Branch: main
- Folder: `/web`

如果使用专门的 Pages 仓库，也可以把 `web/` 中的 `index.html`、`styles.css`、`app.js`、`demo-data.json` 直接放到仓库根目录。

当前演示已推送到：

```text
https://aidenbaize.github.io/AidenBaizebenze.github.io/
```
