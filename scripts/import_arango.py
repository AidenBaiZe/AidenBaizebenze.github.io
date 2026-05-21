#!/usr/bin/env python3
"""Import processed 2WikiMultihopQA graph documents into ArangoDB."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from arango import ArangoClient


ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"

VERTEX_COLLECTIONS = ["questions", "articles", "sentences", "answers", "entities", "clusters"]
EDGE_COLLECTIONS = [
    "question_article",
    "article_sentence",
    "question_sentence",
    "question_answer",
    "question_entity",
    "cluster_question",
]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def ensure_database(client: ArangoClient, db_name: str, username: str, password: str):
    sys_db = client.db("_system", username=username, password=password)
    if not sys_db.has_database(db_name):
        sys_db.create_database(db_name)
    return client.db(db_name, username=username, password=password)


def ensure_collections(db) -> None:
    for name in VERTEX_COLLECTIONS:
        if not db.has_collection(name):
            db.create_collection(name)
    for name in EDGE_COLLECTIONS:
        if not db.has_collection(name):
            db.create_collection(name, edge=True)


def ensure_graph(db, graph_name: str) -> None:
    if db.has_graph(graph_name):
        graph = db.graph(graph_name)
    else:
        graph = db.create_graph(graph_name)
    definitions = {
        "question_article": ("questions", ["articles"]),
        "article_sentence": ("articles", ["sentences"]),
        "question_sentence": ("questions", ["sentences"]),
        "question_answer": ("questions", ["answers"]),
        "question_entity": ("questions", ["entities"]),
        "cluster_question": ("clusters", ["questions"]),
    }
    for edge_collection, (from_collection, to_collections) in definitions.items():
        if not graph.has_edge_definition(edge_collection):
            graph.create_edge_definition(
                edge_collection=edge_collection,
                from_vertex_collections=[from_collection],
                to_vertex_collections=to_collections,
            )


def truncate(db) -> None:
    for name in EDGE_COLLECTIONS + VERTEX_COLLECTIONS:
        if db.has_collection(name):
            db.collection(name).truncate()


def import_collection(db, name: str) -> int:
    docs = read_jsonl(PROCESSED_DIR / f"{name}.jsonl")
    if not docs:
        return 0
    collection = db.collection(name)
    collection.import_bulk(docs, on_duplicate="replace")
    return len(docs)


def ensure_indexes(db) -> None:
    db.collection("questions").add_persistent_index(fields=["type", "cluster"], sparse=False)
    db.collection("questions").add_persistent_index(fields=["answer"], sparse=False)
    db.collection("sentences").add_persistent_index(fields=["title", "sent_id"], sparse=False)
    db.collection("entities").add_persistent_index(fields=["name"], sparse=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="http://localhost:8529")
    parser.add_argument("--username", default="root")
    parser.add_argument("--password", default="openSesame")
    parser.add_argument("--database", default="oct_multihop")
    parser.add_argument("--graph", default="reasoning_graph")
    parser.add_argument("--truncate", action="store_true")
    args = parser.parse_args()

    client = ArangoClient(hosts=args.host)
    db = ensure_database(client, args.database, args.username, args.password)
    ensure_collections(db)
    ensure_graph(db, args.graph)
    if args.truncate:
        truncate(db)

    for name in VERTEX_COLLECTIONS + EDGE_COLLECTIONS:
        count = import_collection(db, name)
        print(f"{name}: {count}")
    ensure_indexes(db)
    print(f"Imported into database '{args.database}', graph '{args.graph}'.")


if __name__ == "__main__":
    main()
