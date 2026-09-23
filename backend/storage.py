"""Minimal SQLite persistence for local MVP assessments and reports."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "intelliproctor.db"


def connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def initialize() -> None:
    with connection() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS assessments (
                id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT,
                status TEXT NOT NULL, baseline_json TEXT NOT NULL, score_percent REAL, correct_count INTEGER, total_questions INTEGER,
                FOREIGN KEY(candidate_id) REFERENCES candidates(id)
            );
            CREATE TABLE IF NOT EXISTS answers (
                assessment_id TEXT NOT NULL, question_id TEXT NOT NULL, selected_option INTEGER,
                is_correct INTEGER NOT NULL, PRIMARY KEY(assessment_id, question_id),
                FOREIGN KEY(assessment_id) REFERENCES assessments(id)
            );
            CREATE TABLE IF NOT EXISTS reports (
                assessment_id TEXT PRIMARY KEY, report_json TEXT NOT NULL, generated_at TEXT NOT NULL,
                FOREIGN KEY(assessment_id) REFERENCES assessments(id)
            );
        """)


def save_started(assessment_id: str, candidate: dict, started_at: str, baseline: dict) -> str:
    candidate_id = candidate.get("id") or assessment_id
    with connection() as db:
        db.execute("INSERT INTO candidates(id, name, email, created_at) VALUES(?, ?, ?, ?)", (candidate_id, candidate["name"], candidate["email"], started_at))
        db.execute("INSERT INTO assessments(id, candidate_id, started_at, status, baseline_json) VALUES(?, ?, ?, ?, ?)", (assessment_id, candidate_id, started_at, "IN_PROGRESS", json.dumps(baseline)))
    return candidate_id


def save_finished(assessment_id: str, status: str, ended_at: str, correct: int, total: int, results: list[dict]) -> None:
    with connection() as db:
        db.execute("UPDATE assessments SET ended_at=?, status=?, score_percent=?, correct_count=?, total_questions=? WHERE id=?", (ended_at, status, round(correct / total * 100, 1), correct, total, assessment_id))
        db.executemany("INSERT OR REPLACE INTO answers(assessment_id, question_id, selected_option, is_correct) VALUES(?, ?, ?, ?)", [(assessment_id, row["question_id"], row["selected_option"], int(row["is_correct"])) for row in results])


def save_report(assessment_id: str, report: dict, generated_at: str) -> None:
    with connection() as db:
        db.execute("INSERT OR REPLACE INTO reports(assessment_id, report_json, generated_at) VALUES(?, ?, ?)", (assessment_id, json.dumps(report), generated_at))


def saved_report(assessment_id: str) -> dict | None:
    with connection() as db:
        row = db.execute("SELECT report_json FROM reports WHERE assessment_id=?", (assessment_id,)).fetchone()
    return json.loads(row["report_json"]) if row else None
