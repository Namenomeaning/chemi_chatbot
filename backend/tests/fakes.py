import sqlite3
from pathlib import Path
from types import SimpleNamespace


class Statement:
    def __init__(self, db, sql, args=()):
        self.db, self.sql, self.args = db, sql, args

    def bind(self, *args):
        return Statement(self.db, self.sql, args)

    async def all(self):
        rows = self.db.connection.execute(self.sql, self.args).fetchall()
        return SimpleNamespace(results=[dict(row) for row in rows])

    async def first(self):
        rows = (await self.all()).results
        return rows[0] if rows else None

    async def run(self):
        self.db.connection.execute(self.sql, self.args)
        self.db.connection.commit()
        return SimpleNamespace(success=True)


class FakeD1:
    def __init__(self, path=":memory:"):
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        schema = Path(__file__).parents[1] / "schema.sql"
        self.connection.executescript(schema.read_text())

    def prepare(self, sql):
        return Statement(self, sql)


class FakeR2:
    def __init__(self):
        self.objects = {}
        self.reads = []

    async def put(self, key, data):
        self.objects[key] = bytes(data)

    async def get(self, key):
        self.reads.append(key)
        if key not in self.objects:
            return None
        data = self.objects[key]

        async def array_buffer():
            return data

        return SimpleNamespace(arrayBuffer=array_buffer)


class FakeLimiter:
    def __init__(self, limit=10):
        self.counts = {}
        self.limit_count = limit

    async def limit(self, options):
        key = options["key"]
        self.counts[key] = self.counts.get(key, 0) + 1
        return SimpleNamespace(success=self.counts[key] <= self.limit_count)
