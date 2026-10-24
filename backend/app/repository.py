from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from array import array
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from .config import Settings
from .models import Citation
from .parser import parse_markdown


class KnowledgeRepository:
    def __init__(self, settings: Settings):
        self.settings = settings
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(settings.db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._initialize()

    def _initialize(self) -> None:
        self.connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY,
                path TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                directory TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '[]',
                content_hash TEXT NOT NULL,
                modified_at REAL NOT NULL,
                indexed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                heading TEXT NOT NULL,
                content TEXT NOT NULL,
                line_start INTEGER NOT NULL,
                line_end INTEGER NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                content, heading, title, tags, path,
                content=''
            );
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS chunk_embeddings (
                chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
                model TEXT NOT NULL,
                vector BLOB NOT NULL,
                PRIMARY KEY (chunk_id, model)
            );
            """
        )
        self.connection.commit()

    def _files(self) -> list[Path]:
        files: list[Path] = []
        for name in self.settings.content_dirs:
            folder = self.settings.root / name
            if folder.exists():
                files.extend(path for path in folder.rglob("*.md") if path.is_file())
        return sorted(files)

    def rebuild(self) -> dict[str, int]:
        indexed_files = indexed_chunks = skipped_files = removed_files = 0
        current_paths: set[str] = set()
        for path in self._files():
            relative = path.relative_to(self.settings.root).as_posix()
            current_paths.add(relative)
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            existing = self.connection.execute("SELECT id, content_hash FROM documents WHERE path = ?", (relative,)).fetchone()
            if existing and existing["content_hash"] == digest:
                skipped_files += 1
                continue
            parsed = parse_markdown(path)
            directory = relative.split("/", 1)[0]
            now = datetime.now(timezone.utc).isoformat()
            with self.connection:
                if existing:
                    chunk_ids = [row[0] for row in self.connection.execute("SELECT id FROM chunks WHERE document_id = ?", (existing["id"],))]
                    for chunk_id in chunk_ids:
                        self.connection.execute("DELETE FROM chunks_fts WHERE rowid = ?", (chunk_id,))
                        self.connection.execute("DELETE FROM chunk_embeddings WHERE chunk_id = ?", (chunk_id,))
                    self.connection.execute("DELETE FROM chunks WHERE document_id = ?", (existing["id"],))
                    self.connection.execute(
                        "UPDATE documents SET title=?, directory=?, tags=?, content_hash=?, modified_at=?, indexed_at=? WHERE id=?",
                        (parsed.title, directory, json.dumps(parsed.tags, ensure_ascii=False), digest, path.stat().st_mtime, now, existing["id"]),
                    )
                    document_id = existing["id"]
                else:
                    cursor = self.connection.execute(
                        "INSERT INTO documents(path,title,directory,tags,content_hash,modified_at,indexed_at) VALUES(?,?,?,?,?,?,?)",
                        (relative, parsed.title, directory, json.dumps(parsed.tags, ensure_ascii=False), digest, path.stat().st_mtime, now),
                    )
                    document_id = cursor.lastrowid
                for chunk in parsed.chunks:
                    cursor = self.connection.execute(
                        "INSERT INTO chunks(document_id,heading,content,line_start,line_end) VALUES(?,?,?,?,?)",
                        (document_id, chunk.heading, chunk.content, chunk.line_start, chunk.line_end),
                    )
                    chunk_id = cursor.lastrowid
                    self.connection.execute(
                        "INSERT INTO chunks_fts(rowid,content,heading,title,tags,path) VALUES(?,?,?,?,?,?)",
                        (chunk_id, chunk.content, chunk.heading, parsed.title, " ".join(parsed.tags), relative),
                    )
                    indexed_chunks += 1
            indexed_files += 1

        stale = self.connection.execute("SELECT id, path FROM documents").fetchall()
        with self.connection:
            for document in stale:
                if document["path"] not in current_paths:
                    chunk_ids = [row[0] for row in self.connection.execute("SELECT id FROM chunks WHERE document_id = ?", (document["id"],))]
                    for chunk_id in chunk_ids:
                        self.connection.execute("DELETE FROM chunks_fts WHERE rowid = ?", (chunk_id,))
                        self.connection.execute("DELETE FROM chunk_embeddings WHERE chunk_id = ?", (chunk_id,))
                    self.connection.execute("DELETE FROM chunks WHERE document_id = ?", (document["id"],))
                    self.connection.execute("DELETE FROM documents WHERE id = ?", (document["id"],))
                    removed_files += 1
            now = datetime.now(timezone.utc).isoformat()
            self.connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('last_indexed_at', ?)", (now,))
        return {"indexed_files": indexed_files, "indexed_chunks": indexed_chunks, "skipped_files": skipped_files, "removed_files": removed_files}

    def chunks_missing_embeddings(self, model: str, limit: int = 16) -> list[tuple[int, str]]:
        rows = self.connection.execute(
            """
            SELECT c.id, c.heading, c.content
            FROM chunks c
            LEFT JOIN chunk_embeddings e ON e.chunk_id = c.id AND e.model = ?
            WHERE e.chunk_id IS NULL
            ORDER BY c.id
            LIMIT ?
            """,
            (model, limit),
        ).fetchall()
        return [(int(row["id"]), f'{row["heading"]}\n{row["content"]}') for row in rows]

    def save_embeddings(self, model: str, items: list[tuple[int, list[float]]]) -> None:
        with self.connection:
            for chunk_id, vector in items:
                payload = array("f", vector).tobytes()
                self.connection.execute(
                    "INSERT OR REPLACE INTO chunk_embeddings(chunk_id,model,vector) VALUES(?,?,?)",
                    (chunk_id, model, payload),
                )

    def embedding_count(self, model: str) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM chunk_embeddings WHERE model = ?", (model,)).fetchone()[0])

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or not left:
            return -1.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        return dot / (left_norm * right_norm) if left_norm and right_norm else -1.0

    def semantic_search(
        self,
        vector: list[float],
        model: str,
        limit: int = 10,
        directory: str = "",
        tag: str = "",
    ) -> list[Citation]:
        conditions = ["e.model = ?"]
        params: list[object] = [model]
        if directory:
            conditions.append("d.directory = ?")
            params.append(directory)
        if tag:
            conditions.append("d.tags LIKE ?")
            params.append(f'%"{tag}"%')
        rows = self.connection.execute(
            f"""
            SELECT c.id, d.title, d.path, d.tags, c.heading, c.content,
                   c.line_start, c.line_end, 0 AS rank, e.vector
            FROM chunk_embeddings e
            JOIN chunks c ON c.id = e.chunk_id
            JOIN documents d ON d.id = c.document_id
            WHERE {' AND '.join(conditions)}
            """,
            params,
        ).fetchall()
        ranked: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            stored_array = array("f")
            stored_array.frombytes(row["vector"])
            stored = list(stored_array)
            score = self._cosine(vector, stored)
            if score > 0:
                ranked.append((score, row))
        ranked.sort(key=lambda item: item[0], reverse=True)
        citations: list[Citation] = []
        for score, row in ranked[:limit]:
            citation = self._citation(row)
            citation.score = round(score, 4)
            citations.append(citation)
        return citations

    @staticmethod
    def _fts_query(query: str) -> str:
        tokens = [token.strip('"*') for token in query.replace("'", " ").split() if token.strip('"*')]
        return " OR ".join(f'"{token}"' for token in tokens[:12])

    def search(self, query: str, limit: int = 10, directory: str = "", tag: str = "") -> list[Citation]:
        fts_query = self._fts_query(query)
        if not fts_query:
            return []
        conditions = ["chunks_fts MATCH ?"]
        params: list[object] = [fts_query]
        if directory:
            conditions.append("d.directory = ?")
            params.append(directory)
        if tag:
            conditions.append("d.tags LIKE ?")
            params.append(f'%"{tag}"%')
        params.append(limit)
        rows = self.connection.execute(
            f"""
            SELECT c.id, d.title, d.path, d.tags, c.heading, c.content, c.line_start, c.line_end, bm25(chunks_fts, 1.0, 0.5, 0.7, 0.3, 0.2) AS rank
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.rowid
            JOIN documents d ON d.id = c.document_id
            WHERE {' AND '.join(conditions)}
            ORDER BY rank
            LIMIT ?
            """,
            params,
        ).fetchall()
        # SQLite's default unicode tokenizer is excellent for Latin text but may
        # treat a whole Chinese sentence as one token. A contained-text fallback
        # keeps short Chinese queries useful while FTS5 still handles ranking.
        if len(rows) < limit:
            tokens = [token for token in query.split() if token][:12]
            like_conditions = []
            like_params: list[object] = []
            for token in tokens:
                like_conditions.append("(c.content LIKE ? OR c.heading LIKE ? OR d.title LIKE ?)")
                pattern = f"%{token}%"
                like_params.extend([pattern, pattern, pattern])
            extra_conditions = [f"({' OR '.join(like_conditions)})"] if like_conditions else []
            if directory:
                extra_conditions.append("d.directory = ?")
                like_params.append(directory)
            if tag:
                extra_conditions.append("d.tags LIKE ?")
                like_params.append(f'%"{tag}"%')
            excluded = [row["id"] for row in rows]
            if excluded:
                extra_conditions.append(f"c.id NOT IN ({','.join('?' for _ in excluded)})")
                like_params.extend(excluded)
            like_params.append(limit - len(rows))
            fallback = self.connection.execute(
                f"""
                SELECT c.id, d.title, d.path, d.tags, c.heading, c.content, c.line_start, c.line_end, 0 AS rank
                FROM chunks c JOIN documents d ON d.id = c.document_id
                WHERE {' AND '.join(extra_conditions)}
                ORDER BY d.modified_at DESC, c.line_start
                LIMIT ?
                """,
                like_params,
            ).fetchall()
            rows = [*rows, *fallback]
        return [self._citation(row) for row in rows]

    def recent_chunks(self, limit: int = 10) -> list[Citation]:
        rows = self.connection.execute(
            """
            SELECT c.id, d.title, d.path, d.tags, c.heading, c.content, c.line_start, c.line_end, 0 AS rank
            FROM chunks c JOIN documents d ON d.id = c.document_id
            ORDER BY d.modified_at DESC, c.line_start LIMIT ?
            """, (limit,)
        ).fetchall()
        return [self._citation(row) for row in rows]

    def _citation(self, row: sqlite3.Row) -> Citation:
        excerpt = row["content"].strip()
        if len(excerpt) > 420:
            excerpt = excerpt[:417].rstrip() + "…"
        file_without_suffix = str(Path(row["path"]).with_suffix("")).replace("\\", "/")
        url = f"obsidian://open?vault={quote(self.settings.vault_name)}&file={quote(file_without_suffix)}"
        rank = float(row["rank"] or 0)
        return Citation(
            chunk_id=row["id"], note_name=row["title"], path=row["path"], heading=row["heading"],
            line_start=row["line_start"], line_end=row["line_end"], excerpt=excerpt,
            tags=json.loads(row["tags"]), score=round(abs(rank), 4), obsidian_url=url,
        )

    def stats(self) -> dict:
        documents = self.connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunks = self.connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        directories = [dict(row) for row in self.connection.execute("SELECT directory AS name, COUNT(*) AS count FROM documents GROUP BY directory ORDER BY count DESC")]
        tag_counts: dict[str, int] = {}
        for row in self.connection.execute("SELECT tags FROM documents"):
            for tag in json.loads(row[0]):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        tags = [{"name": name, "count": count} for name, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:20]]
        last = self.connection.execute("SELECT value FROM metadata WHERE key='last_indexed_at'").fetchone()
        return {"documents": documents, "chunks": chunks, "tags": tags, "directories": directories, "last_indexed_at": last[0] if last else None, "root": str(self.settings.root), "read_only": True}
