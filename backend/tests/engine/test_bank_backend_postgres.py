"""Backend-банк: сверка задач про транзакции с настоящим PostgreSQL.

Тест необязательный: запускается, только если задан FSP_BANK_PG_DSN и установлен psycopg.
Пример (одноразовый контейнер):
    docker run -d --rm --name fsp-bank-pg -e POSTGRES_PASSWORD=pg -p 15499:5432 postgres:16-alpine
    FSP_BANK_PG_DSN="postgresql://postgres:pg@localhost:15499/postgres" pytest -k postgres
Каждый вариант разыгрывается в двух сессиях по шагам из условия; команда, которая ждёт
блокировку, выполняется в отдельном потоке, а следующие шаги другой сессии идут дальше.
"""

import os
import random
import threading

import pytest

from app.testing.engine.bank.backend import concurrency, sql

DSN = os.environ.get("FSP_BANK_PG_DSN")
psycopg = pytest.importorskip("psycopg") if DSN else None
pytestmark = pytest.mark.skipif(not DSN, reason="FSP_BANK_PG_DSN не задан")


class _Session:
    """Сессия psycopg; команды выполняются в фоне, чтобы видеть ожидание блокировок."""

    def __init__(self):
        self.conn = psycopg.connect(DSN, autocommit=True)
        self.thread: threading.Thread | None = None
        self.result = None
        self.failed = False

    def submit(self, sql_text: str, params=None):
        self.wait()
        if self.failed:
            return

        def run():
            try:
                cur = self.conn.execute(sql_text, params)
                self.result = (cur.fetchall() if cur.description else None, cur.rowcount)
            except psycopg.errors.SerializationFailure:
                self.failed = True
                self.conn.execute("ROLLBACK")

        self.thread = threading.Thread(target=run)
        self.thread.start()
        self.thread.join(0.4)  # не дождались — команда ждёт блокировку, идём дальше

    def wait(self):
        if self.thread is not None:
            self.thread.join(10)
            assert not self.thread.is_alive(), "команда зависла"
            self.thread = None

    def close(self):
        self.wait()
        self.conn.close()


def _prepare(table: str, col: str, rid: int, value: int):
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(f"DROP TABLE IF EXISTS {table}")
        c.execute(f"CREATE TABLE {table} (id int PRIMARY KEY, {col} int, version int DEFAULT 0)")
        c.execute(f"INSERT INTO {table} (id, {col}) VALUES (%s, %s)", (rid, value))
        c.execute("CREATE TABLE IF NOT EXISTS orders (id int)")


def test_isolation_read_matches_postgres():
    tid = "backend.sql_isolation_read"
    for seed in range(40):
        _, d = sql._make_isolation(random.Random(f"{tid}#{seed}"))
        _prepare(d["table"], d["col"], d["row_id"], d["b0"])
        sessions = {"T1": _Session(), "T2": _Session()}
        try:
            for step in d["steps"]:
                who, text = step.split(": ", 1)
                sessions[who].submit(text.split("--")[0].strip())
            t1 = sessions["T1"]
            t1.wait()
            assert t1.result[0][0][0] == d["answer"], d["steps"]
        finally:
            for s in sessions.values():
                s.close()


def test_lost_update_matches_postgres():
    tid = "backend.lost_update"
    for seed in range(40):
        _, d = concurrency._make_lost_update(random.Random(f"{tid}#{seed}"))
        table, col, rid = d["table"], d["col"], d["rid"]
        _prepare(table, col, rid, d["b0"])
        sessions = {"T1": _Session(), "T2": _Session()}
        reads: dict[str, tuple] = {}
        begin = "BEGIN" if d["level"] == "READ COMMITTED" else f"BEGIN ISOLATION LEVEL {d['level']}"
        try:
            for who, action, amount in d["steps"]:
                s = sessions[who]
                if action in ("upd_set", "upd_opt"):
                    s.wait()  # значение для UPDATE приложение берёт из прочитанного
                    if not s.failed:
                        reads[who] = s.result[0][0]
                if action == "begin":
                    s.submit(begin)
                elif action == "read":
                    s.submit(f"SELECT {col} FROM {table} WHERE id = %s", (rid,))
                elif action == "read_fu":
                    s.submit(f"SELECT {col} FROM {table} WHERE id = %s FOR UPDATE", (rid,))
                elif action == "read_ver":
                    s.submit(f"SELECT {col}, version FROM {table} WHERE id = %s", (rid,))
                elif action == "upd_atomic":
                    s.submit(f"UPDATE {table} SET {col} = {col} - %s WHERE id = %s", (amount, rid))
                elif action == "upd_set" and not s.failed:
                    s.submit(
                        f"UPDATE {table} SET {col} = %s WHERE id = %s",
                        (reads[who][0] - amount, rid),
                    )
                elif action == "upd_opt" and not s.failed:
                    s.submit(
                        f"UPDATE {table} SET {col} = %s, version = version + 1 "
                        "WHERE id = %s AND version = %s",
                        (reads[who][0] - amount, rid, reads[who][1]),
                    )
                elif action == "commit":
                    s.submit("COMMIT")
            for s in sessions.values():
                s.wait()
            with psycopg.connect(DSN, autocommit=True) as c:
                final = c.execute(f"SELECT {col} FROM {table} WHERE id = %s", (rid,)).fetchone()[0]
            assert final == d["answer"], (d["kind"], d["level"], final)
        finally:
            for s in sessions.values():
                s.close()
