#!/usr/bin/env python3
"""Export a GitHub Pages demo JSON from ArangoDB query results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from arango import ArangoClient


ROOT = Path(__file__).resolve().parents[1]
WEB_DATA = ROOT / "web" / "demo-data.json"

DIRECT_EDGE_COLLECTIONS = [
    "question_article",
    "question_sentence",
    "question_answer",
    "question_entity",
    "cluster_question",
]


def collection_group(document_id: str) -> str:
    collection = document_id.split("/", 1)[0]
    return {
        "questions": "question",
        "articles": "article",
        "sentences": "sentence",
        "answers": "answer",
        "entities": "entity",
        "clusters": "cluster",
    }.get(collection, collection)


def document_label(document: dict[str, Any]) -> str:
    return str(
        document.get("question")
        or document.get("title")
        or document.get("text")
        or document.get("name")
        or document.get("_key")
        or document.get("_id")
        or ""
    )


def fetch_documents(db, document_ids: set[str]) -> list[dict[str, Any]]:
    if not document_ids:
        return []
    cursor = db.aql.execute(
        """
        FOR id IN @ids
          LET doc = DOCUMENT(id)
          FILTER doc != null
          RETURN doc
        """,
        bind_vars={"ids": sorted(document_ids)},
    )
    return list(cursor)


def export_demo(db, output: Path, demo_limit: int) -> None:
    questions = list(
        db.aql.execute(
            """
            FOR q IN questions
              SORT q.split, q._key
              LIMIT @limit
              RETURN q
            """,
            bind_vars={"limit": demo_limit},
        )
    )
    question_ids = {f"questions/{question['_key']}" for question in questions}

    direct_edges: list[dict[str, Any]] = []
    for collection in DIRECT_EDGE_COLLECTIONS:
        if collection == "cluster_question":
            query = f"FOR e IN {collection} FILTER e._to IN @question_ids RETURN e"
        else:
            query = f"FOR e IN {collection} FILTER e._from IN @question_ids RETURN e"
        direct_edges.extend(list(db.aql.execute(query, bind_vars={"question_ids": sorted(question_ids)})))

    article_ids = {edge["_to"] for edge in direct_edges if edge["_from"] in question_ids and edge["_to"].startswith("articles/")}
    support_sentence_ids = {edge["_to"] for edge in direct_edges if edge.get("label") == "supporting_fact"}
    article_sentence_edges = list(
        db.aql.execute(
            """
            FOR e IN article_sentence
              FILTER e._from IN @article_ids AND e._to IN @support_sentence_ids
              RETURN e
            """,
            bind_vars={"article_ids": sorted(article_ids), "support_sentence_ids": sorted(support_sentence_ids)},
        )
    )
    all_edges = direct_edges + article_sentence_edges

    wanted_ids = set(question_ids)
    for edge in all_edges:
        wanted_ids.add(edge["_from"])
        wanted_ids.add(edge["_to"])

    nodes = []
    for document in fetch_documents(db, wanted_ids):
        document_id = document["_id"]
        nodes.append(
            {
                **document,
                "id": document_id,
                "label": document_label(document),
                "group": collection_group(document_id),
            }
        )

    type_stats = list(
        db.aql.execute(
            """
            FOR q IN questions
              COLLECT name = q.type WITH COUNT INTO count
              SORT name
              RETURN { name, count }
            """
        )
    )
    cluster_stats = list(
        db.aql.execute(
            """
            FOR q IN questions
              COLLECT name = q.cluster WITH COUNT INTO count
              SORT name
              RETURN { name, count }
            """
        )
    )

    payload = {
        "dataset": "2WikiMultihopQA",
        "database": "ArangoDB",
        "source": "ArangoDB AQL export",
        "total_records": db.collection("questions").count(),
        "generated_from_records": db.collection("questions").count(),
        "demo_question_count": len(questions),
        "questions": questions,
        "nodes": nodes,
        "edges": [
            {
                "source": edge["_from"],
                "target": edge["_to"],
                "label": edge.get("label", ""),
                "fact": edge.get("fact", ""),
            }
            for edge in all_edges
        ],
        "stats": {
            "types": type_stats,
            "clusters": cluster_stats,
        },
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="http://localhost:8529")
    parser.add_argument("--username", default="root")
    parser.add_argument("--password", default="openSesame")
    parser.add_argument("--database", default="mhqa_arangodb")
    parser.add_argument("--demo-limit", type=int, default=100)
    parser.add_argument("--output", type=Path, default=WEB_DATA)
    args = parser.parse_args()

    client = ArangoClient(hosts=args.host)
    db = client.db(args.database, username=args.username, password=args.password)
    export_demo(db, args.output, args.demo_limit)
    print(f"Exported ArangoDB demo data to {args.output}")


if __name__ == "__main__":
    main()
