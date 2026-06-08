#!/usr/bin/env python3
"""Prepare 2WikiMultihopQA data for ArangoDB and the GitHub Pages demo."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
WEB_DATA = ROOT / "web" / "demo-data.json"
DEFAULT_DOWNLOAD_ZIP = Path.home() / "Downloads" / "data.zip"


def clean_key(value: Any, prefix: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_:-]+", "_", str(value).strip())[:180].strip("_")
    return text or prefix


def parse_jsonish(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        return json.loads(value)
    if value is None:
        return []
    return value


def extract_zip(zip_path: Path) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(RAW_DIR)


def find_sources() -> list[Path]:
    patterns = ["*.parquet", "*.jsonl", "*.json"]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(RAW_DIR.rglob(pattern))
        files.extend((ROOT / "data").glob(pattern))
    return sorted(
        path
        for path in files
        if not path.name.startswith(".") and "processed" not in path.parts and path.name != "demo-data.json"
    )


def load_records(path: Path, limit: int | None) -> list[dict[str, Any]]:
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
        if limit:
            df = df.head(limit)
        records = df.to_dict(orient="records")
    elif path.suffix == ".jsonl":
        records = []
        with path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if limit is not None and index >= limit:
                    break
                if line.strip():
                    records.append(json.loads(line))
    elif path.suffix == ".json":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            data = list(data.values())
        records = list(data[:limit] if limit else data)
    else:
        raise ValueError(f"Unsupported source: {path}")
    return [normalise_record(record, path.stem) for record in records]


def normalise_record(record: dict[str, Any], split: str) -> dict[str, Any]:
    context_raw = parse_jsonish(record.get("context", []))
    facts_raw = parse_jsonish(record.get("supporting_facts", []))
    evidences_raw = parse_jsonish(record.get("evidences", []))

    context = []
    for item in context_raw:
        if isinstance(item, dict):
            title = item.get("title", "")
            content = item.get("content", [])
        else:
            title = item[0] if len(item) > 0 else ""
            content = item[1] if len(item) > 1 else []
        context.append({"title": str(title), "content": [str(sentence) for sentence in content]})

    facts = []
    for item in facts_raw:
        if isinstance(item, dict):
            title = item.get("title", "")
            sent_id = item.get("sent_id", 0)
        else:
            title = item[0] if len(item) > 0 else ""
            sent_id = item[1] if len(item) > 1 else 0
        facts.append({"title": str(title), "sent_id": int(sent_id)})

    evidences = []
    for item in evidences_raw:
        if isinstance(item, dict):
            fact = item.get("fact", "")
            relation = item.get("relation", "")
            entity = item.get("entity", "")
        else:
            fact = item[0] if len(item) > 0 else ""
            relation = item[1] if len(item) > 1 else ""
            entity = item[2] if len(item) > 2 else ""
        evidences.append({"fact": str(fact), "relation": str(relation), "entity": str(entity)})

    return {
        "_id": str(record.get("_id") or record.get("id") or f"{split}_{clean_key(record.get('question', ''), 'q')}"),
        "split": split,
        "type": str(record.get("type", "unknown")),
        "question": str(record.get("question", "")),
        "answer": str(record.get("answer", "")),
        "context": context,
        "supporting_facts": facts,
        "evidences": evidences,
    }


def fallback_records() -> list[dict[str, Any]]:
    return [
        {
            "_id": "sample_bridge_001",
            "split": "sample",
            "type": "bridge",
            "question": "Which country is the birthplace of the director of Inception?",
            "answer": "United Kingdom",
            "context": [
                {
                    "title": "Inception",
                    "content": [
                        "Inception is a 2010 science fiction action film.",
                        "The film was written and directed by Christopher Nolan.",
                    ],
                },
                {
                    "title": "Christopher Nolan",
                    "content": [
                        "Christopher Nolan is a British and American filmmaker.",
                        "Nolan was born in London, England.",
                    ],
                },
            ],
            "supporting_facts": [
                {"title": "Inception", "sent_id": 1},
                {"title": "Christopher Nolan", "sent_id": 1},
            ],
            "evidences": [
                {"fact": "Inception was directed by Christopher Nolan.", "relation": "director", "entity": "Christopher Nolan"},
                {"fact": "Christopher Nolan was born in London, England.", "relation": "birthplace", "entity": "United Kingdom"},
            ],
        },
        {
            "_id": "sample_comparison_001",
            "split": "sample",
            "type": "comparison",
            "question": "Who was born earlier, Ada Lovelace or Alan Turing?",
            "answer": "Ada Lovelace",
            "context": [
                {"title": "Ada Lovelace", "content": ["Ada Lovelace was born on 10 December 1815."]},
                {"title": "Alan Turing", "content": ["Alan Turing was born on 23 June 1912."]},
            ],
            "supporting_facts": [
                {"title": "Ada Lovelace", "sent_id": 0},
                {"title": "Alan Turing", "sent_id": 0},
            ],
            "evidences": [
                {"fact": "Ada Lovelace was born in 1815.", "relation": "birth_date", "entity": "Ada Lovelace"},
                {"fact": "Alan Turing was born in 1912.", "relation": "birth_date", "entity": "Alan Turing"},
            ],
        },
    ]


def assign_clusters(records: list[dict[str, Any]], cluster_count: int) -> list[str]:
    if len(records) < 2:
        return ["cluster_0"] * len(records)
    count = max(2, min(cluster_count, len(records)))
    texts = [f"{row['type']} {row['question']} {row['answer']}" for row in records]
    matrix = TfidfVectorizer(stop_words="english", min_df=1, max_features=3000).fit_transform(texts)
    labels = KMeans(n_clusters=count, random_state=42, n_init="auto").fit_predict(matrix)
    return [f"cluster_{label}" for label in labels]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def count_source_records(path: Path) -> int:
    if path.suffix == ".parquet":
        return len(pd.read_parquet(path, columns=[]))
    if path.suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    if path.suffix == ".json":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return len(data)
    return 0


def build_outputs(records: list[dict[str, Any]], demo_limit: int, cluster_count: int, total_records: int | None = None) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    labels = assign_clusters(records, cluster_count)

    questions: list[dict[str, Any]] = []
    articles: dict[str, dict[str, Any]] = {}
    sentences: dict[str, dict[str, Any]] = {}
    answers: dict[str, dict[str, Any]] = {}
    entities: dict[str, dict[str, Any]] = {}
    clusters: dict[str, dict[str, Any]] = {}
    edges: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for record, cluster_id in zip(records, labels):
        q_key = clean_key(record["_id"], "question")
        q_id = f"questions/{q_key}"
        answer_key = clean_key(record["answer"], "answer")
        answer_id = f"answers/{answer_key}"
        cluster_doc_id = f"clusters/{cluster_id}"
        question_text = record["question"]
        support_lookup = {(fact["title"], fact["sent_id"]) for fact in record["supporting_facts"]}

        clusters.setdefault(cluster_id, {"_key": cluster_id, "name": cluster_id, "size": 0})
        clusters[cluster_id]["size"] += 1
        answers.setdefault(answer_key, {"_key": answer_key, "text": record["answer"]})
        questions.append(
            {
                "_key": q_key,
                "source_id": record["_id"],
                "split": record["split"],
                "type": record["type"],
                "question": question_text,
                "answer": record["answer"],
                "cluster": cluster_id,
                "support_count": len(record["supporting_facts"]),
                "context_count": len(record["context"]),
            }
        )
        edges["question_answer"].append({"_from": q_id, "_to": answer_id, "label": "answer"})
        edges["cluster_question"].append({"_from": cluster_doc_id, "_to": q_id, "label": "member"})

        for article in record["context"]:
            article_key = clean_key(article["title"], "article")
            article_id = f"articles/{article_key}"
            articles.setdefault(article_key, {"_key": article_key, "title": article["title"]})
            edges["question_article"].append({"_from": q_id, "_to": article_id, "label": "context"})

            for sent_id, sentence in enumerate(article["content"]):
                sentence_key = clean_key(f"{article['title']}_{sent_id}", "sentence")
                sentence_doc_id = f"sentences/{sentence_key}"
                is_support = (article["title"], sent_id) in support_lookup
                sentences.setdefault(
                    sentence_key,
                    {
                        "_key": sentence_key,
                        "title": article["title"],
                        "sent_id": sent_id,
                        "text": sentence,
                        "is_supporting_fact": is_support,
                    },
                )
                edges["article_sentence"].append({"_from": article_id, "_to": sentence_doc_id, "label": "has_sentence"})
                if is_support:
                    edges["question_sentence"].append({"_from": q_id, "_to": sentence_doc_id, "label": "supporting_fact"})

        for evidence in record["evidences"]:
            entity_key = clean_key(evidence["entity"], "entity")
            entity_id = f"entities/{entity_key}"
            entities.setdefault(entity_key, {"_key": entity_key, "name": evidence["entity"]})
            edges["question_entity"].append(
                {
                    "_from": q_id,
                    "_to": entity_id,
                    "label": evidence["relation"] or "evidence",
                    "fact": evidence["fact"],
                }
            )

    write_jsonl(PROCESSED_DIR / "questions.jsonl", questions)
    write_jsonl(PROCESSED_DIR / "articles.jsonl", list(articles.values()))
    write_jsonl(PROCESSED_DIR / "sentences.jsonl", list(sentences.values()))
    write_jsonl(PROCESSED_DIR / "answers.jsonl", list(answers.values()))
    write_jsonl(PROCESSED_DIR / "entities.jsonl", list(entities.values()))
    write_jsonl(PROCESSED_DIR / "clusters.jsonl", list(clusters.values()))
    for name, rows in edges.items():
        write_jsonl(PROCESSED_DIR / f"{name}.jsonl", rows)

    demo_records = questions[:demo_limit]
    demo_question_keys = {row["_key"] for row in demo_records}
    demo_nodes: dict[str, dict[str, Any]] = {}
    demo_edges: list[dict[str, Any]] = []

    def add_node(node_id: str, label: str, group: str, extra: dict[str, Any] | None = None) -> None:
        demo_nodes.setdefault(node_id, {"id": node_id, "label": label, "group": group, **(extra or {})})

    question_by_key = {row["_key"]: row for row in questions}
    article_by_key = articles
    sentence_by_key = sentences
    answer_by_key = answers
    entity_by_key = entities

    for q_key in demo_question_keys:
        q = question_by_key[q_key]
        add_node(f"questions/{q_key}", q["question"], "question", q)

    edge_sources = ["question_article", "question_sentence", "question_answer", "question_entity", "cluster_question"]
    wanted = {f"questions/{q}" for q in demo_question_keys}
    demo_question_ids = set(wanted)
    for edge_name in edge_sources:
        for edge in edges.get(edge_name, []):
            include = edge["_from"] in demo_question_ids or (
                edge_name == "cluster_question" and edge["_to"] in demo_question_ids
            )
            if include:
                wanted.add(edge["_from"])
                wanted.add(edge["_to"])
                demo_edges.append({"source": edge["_from"], "target": edge["_to"], "label": edge.get("label", edge_name), "fact": edge.get("fact", "")})

    support_sentence_ids = {edge["target"] for edge in demo_edges if edge["label"] == "supporting_fact"}
    wanted_article_ids = {node_id for node_id in wanted if node_id.startswith("articles/")}
    for edge in edges.get("article_sentence", []):
        if edge["_from"] in wanted_article_ids and edge["_to"] in support_sentence_ids:
            wanted.add(edge["_to"])
            demo_edges.append({"source": edge["_from"], "target": edge["_to"], "label": edge.get("label", "has_sentence"), "fact": ""})

    for node_id in sorted(wanted):
        collection, key = node_id.split("/", 1)
        if collection == "questions":
            continue
        if collection == "articles" and key in article_by_key:
            add_node(node_id, article_by_key[key]["title"], "article")
        elif collection == "sentences" and key in sentence_by_key:
            sentence = sentence_by_key[key]
            add_node(node_id, sentence["text"], "sentence", sentence)
        elif collection == "answers" and key in answer_by_key:
            add_node(node_id, answer_by_key[key]["text"], "answer")
        elif collection == "entities" and key in entity_by_key:
            add_node(node_id, entity_by_key[key]["name"], "entity")
        elif collection == "clusters" and key in clusters:
            add_node(node_id, key, "cluster", clusters[key])

    type_counts = Counter(row["type"] for row in questions)
    cluster_counts = Counter(row["cluster"] for row in questions)
    WEB_DATA.write_text(
        json.dumps(
            {
                "dataset": "2WikiMultihopQA",
                "database": "ArangoDB",
                "total_records": total_records if total_records is not None else len(records),
                "generated_from_records": len(records),
                "demo_question_count": len(demo_records),
                "questions": demo_records,
                "nodes": list(demo_nodes.values()),
                "edges": demo_edges,
                "stats": {
                    "types": [{"name": key, "count": value} for key, value in sorted(type_counts.items())],
                    "clusters": [{"name": key, "count": value} for key, value in sorted(cluster_counts.items())],
                },
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, default=DEFAULT_DOWNLOAD_ZIP, help="Downloaded data.zip path.")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum records to process for course demo.")
    parser.add_argument("--demo-limit", type=int, default=40, help="Questions embedded in GitHub Pages demo JSON.")
    parser.add_argument("--clusters", type=int, default=6, help="Number of TF-IDF/KMeans clusters.")
    parser.add_argument("--sample-fallback", action="store_true", help="Generate a small schema-compatible sample if no source files exist.")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if args.zip.exists():
        target_zip = RAW_DIR / args.zip.name
        if args.zip.resolve() != target_zip.resolve():
            shutil.copy2(args.zip, target_zip)
        extract_zip(target_zip)

    sources = find_sources()
    if not sources:
        if not args.sample_fallback:
            raise SystemExit("No dataset files found. Put data.zip in Downloads or files under data/raw.")
        records = fallback_records()
    else:
        total_records = sum(count_source_records(source) for source in sources)
        records = []
        remaining = args.limit
        for source in sources:
            if remaining <= 0:
                break
            loaded = load_records(source, remaining)
            records.extend(loaded)
            remaining = args.limit - len(records)

    build_outputs(records, args.demo_limit, args.clusters, total_records=locals().get("total_records", len(records)))
    print(f"Prepared {len(records)} records.")
    print(f"Processed files: {PROCESSED_DIR}")
    print(f"Web demo data: {WEB_DATA}")


if __name__ == "__main__":
    main()
