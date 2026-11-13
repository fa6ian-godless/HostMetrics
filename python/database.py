import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, List, Dict, Any


DB_PATH = Path(__file__).resolve().parent / "metrics.db"


@contextmanager
def get_database():
    
    connection = sqlite3.connect(DB_PATH, timeout = 10)
    
    connection.row_factory = sqlite3.Row
    
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    
    try:
        yield connection
        connection.commit()
    
    except Exception:
        connection.rollback()
        raise
    
    finally:
        connection.close()


def init_database() -> None:

    with get_database() as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL UNIQUE,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id        INTEGER NOT NULL,
                cpu_percent      REAL,
                cpu_cores        INTEGER,
                cpu_frequency    TEXT,
                cpu_average_load TEXT,
                memory_percent   REAL,
                memory_used      TEXT,
                memory_total     TEXT,
                swap_percent     REAL,
                swap_used        TEXT,
                swap_total       TEXT,
                storage_percent  REAL,
                storage_used     TEXT,
                storage_total    TEXT,
                upload_speed     TEXT,
                download_speed   TEXT,
                total_sent       TEXT,
                total_received   TEXT,
                uptime           TEXT,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_server_created
            ON metrics(server_id, created_at DESC)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_servers_name
            ON servers(name)
        """)


def get_or_create_server(name: str) -> int:

    with get_database() as connection:

        row = connection.execute(
            "SELECT id FROM servers WHERE name = ?", (name,)
        ).fetchone()

        if row:

            server_id = row["id"]
            
            connection.execute(
                "UPDATE servers SET last_seen = CURRENT_TIMESTAMP WHERE id = ?",
                (server_id,)
            )
            
            return server_id

        cursor = connection.execute(
            "INSERT INTO servers (name) VALUES (?)", (name,)
        )

        return cursor.lastrowid


def insert_metrics(server_id: int, data: Dict[str, Any]) -> None:

    cpu = data.get("cpu", {})
    memory = data.get("memory", {})
    swap = data.get("swap", {})
    storage = data.get("storage", {})
    network = data.get("network", {})


    def _to_float(value) -> Optional[float]:
        
        if value is None:
            return None
        
        try:
            return float(str(value).replace("%", "").strip())
        
        except (ValueError, TypeError):
            return None


    with get_database() as connection:
        
        connection.execute("""
            INSERT INTO metrics (
                server_id,
                cpu_percent, cpu_cores, cpu_frequency, cpu_average_load,
                memory_percent, memory_used, memory_total,
                swap_percent, swap_used, swap_total,
                storage_percent, storage_used, storage_total,
                upload_speed, download_speed,
                total_sent, total_received,
                uptime
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            server_id,
            _to_float(cpu.get("percent")),
            cpu.get("cores"),
            cpu.get("frequency"),
            cpu.get("average_load"),
            _to_float(memory.get("percent")),
            memory.get("used"),
            memory.get("total"),
            _to_float(swap.get("percent")),
            swap.get("used"),
            swap.get("total"),
            _to_float(storage.get("percent")),
            storage.get("used"),
            storage.get("total"),
            network.get("upload"),
            network.get("download"),
            network.get("total_send") or network.get("total_sent"),
            network.get("total_received"),
            data.get("uptime"),
        ))


def list_servers() -> List[Dict[str, Any]]:

    with get_database() as connection:
        
        rows = connection.execute("""
            SELECT id, name, created_at, last_seen
            FROM servers
            ORDER BY name
        """).fetchall()

    return [dict(row) for row in rows]


def get_latest_metrics(server_id: int) -> Optional[Dict[str, Any]]:

    with get_database() as connection:
        
        row = connection.execute("""
            SELECT *
            FROM metrics
            WHERE server_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (server_id,)).fetchone()
    
    return dict(row) if row else None


def get_all_latest_metrics() -> List[Dict[str, Any]]:

    with get_database() as connection:
        
        rows = connection.execute("""
            SELECT
                s.id   AS server_id,
                s.name AS name,
                s.last_seen,
                m.*
            FROM servers s
            LEFT JOIN metrics m ON m.id = (
                SELECT id
                FROM metrics
                WHERE server_id = s.id
                ORDER BY created_at DESC
                LIMIT 1
            )
            ORDER BY s.name
        """).fetchall()
    
    return [dict(row) for row in rows]


def cleanup_old_metrics(keep_per_server: int = 500) -> int:

    with get_database() as connection:

        rows = connection.execute("""
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY server_id
                           ORDER BY created_at DESC
                       ) AS rn
                FROM metrics
            ) WHERE rn > ?
        """, (keep_per_server,)).fetchall()

        if not rows:
            return 0

        ids = [row["id"] for row in rows]
        placeholders = ",".join("?" * len(ids))
        
        cursor = conn.execute(
            f"DELETE FROM metrics WHERE id IN ({placeholders})", ids
        )

        return cursor.rowcount


init_database()