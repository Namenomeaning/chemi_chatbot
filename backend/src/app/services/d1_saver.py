import base64
from collections.abc import AsyncIterator, Sequence
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from langgraph.checkpoint.serde.types import TASKS


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


class D1Saver(BaseCheckpointSaver[str]):
    """Stores LangGraph checkpoints in a Cloudflare D1 database (async only)."""

    def __init__(self, db: Any) -> None:
        super().__init__()
        self.db = db

    async def _all(self, sql: str, *params: Any) -> list[dict]:
        result = await self.db.prepare(sql).bind(*params).all()
        rows = result.results
        return rows.to_py() if hasattr(rows, "to_py") else list(rows)

    async def _run(self, sql: str, *params: Any) -> None:
        await self.db.prepare(sql).bind(*params).run()

    async def _tuple(self, row: dict) -> CheckpointTuple:
        thread_id, ns, cid, parent = row["thread_id"], row["checkpoint_ns"], row["checkpoint_id"], row["parent_id"]
        writes = await self._all(
            "SELECT task_id, channel, type, value FROM writes "
            "WHERE thread_id=? AND checkpoint_ns=? AND checkpoint_id=? ORDER BY task_id, idx",
            thread_id, ns, cid,
        )
        sends: list[dict] = []
        if parent:
            sends = await self._all(
                "SELECT type, value FROM writes WHERE thread_id=? AND checkpoint_ns=? "
                "AND checkpoint_id=? AND channel=? ORDER BY task_path, task_id, idx",
                thread_id, ns, parent, TASKS,
            )
        checkpoint = {
            **self.serde.loads_typed((row["type"], base64.b64decode(row["checkpoint"]))),
            "pending_sends": [self.serde.loads_typed((s["type"], base64.b64decode(s["value"]))) for s in sends],
        }
        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_ns": ns, "checkpoint_id": cid}},
            checkpoint=checkpoint,
            metadata=self.serde.loads_typed((row["metadata_type"], base64.b64decode(row["metadata"]))),
            pending_writes=[
                (w["task_id"], w["channel"], self.serde.loads_typed((w["type"], base64.b64decode(w["value"]))))
                for w in writes
            ],
            parent_config=(
                {"configurable": {"thread_id": thread_id, "checkpoint_ns": ns, "checkpoint_id": parent}}
                if parent
                else None
            ),
        )

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        conf = config["configurable"]
        thread_id, ns = conf["thread_id"], conf.get("checkpoint_ns", "")
        if cid := get_checkpoint_id(config):
            rows = await self._all(
                "SELECT * FROM checkpoints WHERE thread_id=? AND checkpoint_ns=? AND checkpoint_id=?",
                thread_id, ns, cid,
            )
        else:
            rows = await self._all(
                "SELECT * FROM checkpoints WHERE thread_id=? AND checkpoint_ns=? "
                "ORDER BY checkpoint_id DESC LIMIT 1",
                thread_id, ns,
            )
        return await self._tuple(rows[0]) if rows else None

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        sql, params = "SELECT * FROM checkpoints WHERE 1=1", []
        if config:
            sql += " AND thread_id=?"
            params.append(config["configurable"]["thread_id"])
            if (ns := config["configurable"].get("checkpoint_ns")) is not None:
                sql += " AND checkpoint_ns=?"
                params.append(ns)
        if before and (bid := get_checkpoint_id(before)):
            sql += " AND checkpoint_id<?"
            params.append(bid)
        sql += " ORDER BY checkpoint_id DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        for row in await self._all(sql, *params):
            item = await self._tuple(row)
            if filter and not all(item.metadata.get(k) == v for k, v in filter.items()):
                continue
            yield item

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        conf = config["configurable"]
        thread_id, ns = conf["thread_id"], conf.get("checkpoint_ns", "")
        c = checkpoint.copy()
        c.pop("pending_sends", None)
        ctype, cdata = self.serde.dumps_typed(c)
        mtype, mdata = self.serde.dumps_typed(get_checkpoint_metadata(config, metadata))
        await self._run(
            "INSERT OR REPLACE INTO checkpoints "
            "(thread_id, checkpoint_ns, checkpoint_id, parent_id, type, checkpoint, metadata_type, metadata) "
            "VALUES (?,?,?,?,?,?,?,?)",
            thread_id, ns, checkpoint["id"], conf.get("checkpoint_id") or "", ctype, _b64(cdata), mtype, _b64(mdata),
        )
        return {"configurable": {"thread_id": thread_id, "checkpoint_ns": ns, "checkpoint_id": checkpoint["id"]}}

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        conf = config["configurable"]
        thread_id, ns, cid = conf["thread_id"], conf.get("checkpoint_ns", ""), conf["checkpoint_id"]
        for idx, (channel, value) in enumerate(writes):
            widx = WRITES_IDX_MAP.get(channel, idx)
            vtype, vdata = self.serde.dumps_typed(value)
            verb = "INSERT OR REPLACE" if widx < 0 else "INSERT OR IGNORE"
            await self._run(
                f"{verb} INTO writes (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value, task_path) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                thread_id, ns, cid, task_id, widx, channel, vtype, _b64(vdata), task_path,
            )
