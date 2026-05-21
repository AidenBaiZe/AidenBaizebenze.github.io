# 数据目录

本目录保存 2WikiMultihopQA 数据。

- `dev.json`：验证集原始数据。
- `test.json`：测试集原始数据。
- `train.json`：训练集原始数据。本地保留完整文件，但 GitHub 普通 Git 单文件限制为 100MB，因此提交到 GitHub 时使用 `train.json.part-*` 分片。
- `restore_train.sh`：在 GitHub 克隆后运行，用分片恢复 `train.json`。
- `processed/`：由 `scripts/prepare_dataset.py` 生成的 ArangoDB JSONL 导入文件。
- `processed/restore_processed.sh`：在 GitHub 克隆后恢复被分片的全量 ArangoDB JSONL 文件。

恢复训练集：

```bash
cd data
./restore_train.sh
```

恢复全量 ArangoDB JSONL：

```bash
cd data/processed
./restore_processed.sh
```
