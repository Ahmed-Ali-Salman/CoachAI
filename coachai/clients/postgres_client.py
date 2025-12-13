"""Postgres client for pgvector operations (embeddings insert/search)."""

import os
import json
from pathlib import Path
from typing import List, Any, Dict, Optional
import psycopg2
import psycopg2.extras


class PostgresClient:
    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or os.environ.get('SUPABASE_DB_URL')
        if not self.dsn:
            raise RuntimeError('SUPABASE_DB_URL must be set for PostgresClient')

        # Ensure logs directory exists for error logging
        try:
            Path('logs').mkdir(exist_ok=True)
        except Exception:
            pass

    def _vector_literal(self, vector: List[float]) -> str:
        """Return a pgvector literal string like '[0.1,0.2,...]'."""
        return '[' + ','.join(f'{float(x):.8f}' for x in vector) + ']'

    def _get_conn(self):
        try:
            return psycopg2.connect(self.dsn)
        except Exception as e:
            try:
                with open('logs/postgres_client.log', 'a', encoding='utf-8') as lf:
                    lf.write('---\n')
                    lf.write(f'Postgres connection failed: {repr(e)}\n')
            except Exception:
                pass
            return None

    def insert_embedding(self, source_table: str, source_id: str, vector: List[float], metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        conn = None
        try:
            conn = self._get_conn()
            if not conn:
                return None
            with conn:
                with conn.cursor() as cur:
                    vec = self._vector_literal(vector)
                    cur.execute(
                        "INSERT INTO embeddings (source_table, source_id, embedding, metadata) VALUES (%s, %s, %s::vector, %s) RETURNING id",
                        (source_table, source_id, vec, json.dumps(metadata or {}))
                    )
                    return cur.fetchone()[0]
        except Exception as e:
            try:
                with open('logs/postgres_client.log', 'a', encoding='utf-8') as lf:
                    lf.write('---\n')
                    lf.write('insert_embedding failed:\n')
                    lf.write(repr(e) + '\n')
            except Exception:
                pass
            return None

    def delete_embeddings_for_source(self, source_table: str, source_id: str) -> bool:
        conn = None
        try:
            conn = self._get_conn()
            if not conn:
                return False
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM embeddings WHERE source_table = %s AND source_id = %s",
                        (source_table, source_id)
                    )
            return True
        except Exception as e:
            try:
                with open('logs/postgres_client.log', 'a', encoding='utf-8') as lf:
                    lf.write('---\n')
                    lf.write('delete_embeddings_for_source failed:\n')
                    lf.write(repr(e) + '\n')
            except Exception:
                pass
            return False

    def vector_search(self, vector: List[float], source_table: str = 'lessons', top_k: int = 5) -> List[Dict[str, Any]]:
        conn = None
        try:
            conn = self._get_conn()
            if not conn:
                return []
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                vec = self._vector_literal(vector)
                # Use cosine distance operator (<=>) to match ivfflat index on vector_cosine_ops.
                cur.execute(
                    "SELECT source_id, metadata, embedding <=> %s::vector AS distance FROM embeddings WHERE source_table = %s ORDER BY embedding <=> %s::vector LIMIT %s",
                    (vec, source_table, vec, top_k)
                )
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            try:
                with open('logs/postgres_client.log', 'a', encoding='utf-8') as lf:
                    lf.write('---\n')
                    lf.write('vector_search failed:\n')
                    lf.write(repr(e) + '\n')
            except Exception:
                pass
            return []
