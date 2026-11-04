import asyncio
import json
from abc import ABC
import time
from typing import Any, Iterable

from core.config import get_settings
from langgraph.store.base import BaseStore, Item
from langgraph.store import base as store_base
from pymilvus import DataType, FieldSchema, Collection, utility, CollectionSchema
from src.infra.milvus_client import connect_milvus, MILVUS_ALIAS
from langchain_community.embeddings import DashScopeEmbeddings
from datetime import datetime
from loguru import logger

settings = get_settings()
COLLECTION_NAME = "agent_long_term_memory"
DIM = 1024 # text-embedding-v3

SearchItem = store_base.SearchItem


class MilvusStore(BaseStore, ABC):
    """LangGraph 长期记忆 Store，底层用 Milvus + DashScope Embedding。"""
    def __init__(self) -> None:
        connect_milvus()
        self._embedding = DashScopeEmbeddings(
            model="text-embedding-v3",
            dashscope_api_key=settings.DASHSCOPE_API_KEY,
        )
        self._ensure_collection()

    def _ensure_collection(self):
        if utility.has_collection(COLLECTION_NAME, using=MILVUS_ALIAS):
            self._collection = Collection(COLLECTION_NAME, using=MILVUS_ALIAS)
            self._collection.load()
            return

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=256),
            FieldSchema(name="namespace", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="key", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="value_json", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIM),
            FieldSchema(name="created_at", dtype=DataType.INT64),
        ]
        schema = CollectionSchema(fields, description="agent long-term memory")
        self._collection = Collection(COLLECTION_NAME, schema, using=MILVUS_ALIAS)

        self._collection.create_index(
            field_name="embedding",
            index_params={
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128},
                "metric_type": "COSINE",
            }
        )

        self._collection.load()
        logger.info(f"Collection {COLLECTION_NAME} created.")

    # ---------- 同步接口（BaseStore 要求）----------
    def batch(self, ops: Iterable[Any]) -> list[Any]:
        """
        LangGraph 在同步工具线程里会调 batch。
        线程中没有事件循环，必须用 asyncio.run() 新建一个。
        """
        return asyncio.run(self.abatch(ops))

    async def abatch(self, ops: Iterable[Any]) -> list[Any]:
        results = []
        for op in ops:
            op_type = type(op).__name__
            if op_type == "PutOp":
                if op.value is None:
                    await self._adelete(op.namespace, op.key)
                    results.append(None)
                else:
                    await self._aput(op.namespace, op.key, op.value)
                    results.append(None)
            elif op_type == "GetOp":
                results.append(await self._aget(op.namespace, op.key))
            elif op_type == "SearchOp":
                results.append(
                    await self._asearch(op.namespace_prefix, op.query, op.limit or 5)
                )
            else:
                results.append(None)
        return results

    async def _aput(self, namespace: tuple, key: str, value: dict) -> None:
        doc_id = self._make_id(namespace, key)
        ns = "/".join(str(x) for x in namespace)
        value_json = json.dumps(value, ensure_ascii=False)
        # 对整个 value 做 embedding，后续语义检索靠它
        vector = self._embedding.embed_query(value_json)

        # Milvus 无原生 upsert：先删再插
        self._collection.delete(expr=f'id == "{doc_id}"')
        self._collection.insert([
            [doc_id],
            [ns],
            [key],
            [value_json],
            [vector],
            [int(time.time() * 1000)],
        ])
        self._collection.flush()

    async def _aget(self, namespace: tuple, key: str) -> Item | None:
        doc_id = self._make_id(namespace, key)
        res = self._collection.query(
            expr=f'id == "{doc_id}"',
            output_fields=["namespace", "key", "value_json", "created_at"],
        )
        if not res:
            return None
        row = res[0]
        return Item(
            namespace=tuple(row["namespace"].split("/")),
            key=row["key"],
            value=json.loads(row["value_json"]),
            created_at=datetime.fromtimestamp(row["created_at"] / 1000),
            updated_at=datetime.fromtimestamp(row["created_at"] / 1000),
        )

    async def _adelete(self, namespace: tuple, key: str) -> None:
        doc_id = self._make_id(namespace, key)
        self._collection.delete(expr=f'id == "{doc_id}"')
        self._collection.flush()

    async def _asearch(
            self, namespace_prefix: tuple, query: str | None, limit: int
    ) -> list[SearchItem]:
        ns_prefix = "/".join(str(x) for x in namespace_prefix)
        expr = f'namespace like "{ns_prefix}%"'

        if query:
            vector = self._embedding.embed_query(query)
            hits = self._collection.search(
                data=[vector],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"nprobe": 16}},
                limit=limit,
                expr=expr,
                output_fields=["namespace", "key", "value_json", "created_at"],
            )
            items = []
            for hit in hits[0]:
                entity = hit.entity
                created_ms = entity.get("created_at")
                created_dt = datetime.fromtimestamp(created_ms / 1000)
                items.append(
                    SearchItem(
                        namespace=tuple(entity.get("namespace").split("/")),
                        key=entity.get("key"),
                        value=json.loads(entity.get("value_json")),
                        score=hit.score,
                        created_at=created_dt,
                        updated_at=created_dt,
                    )
                )
            return items

        # 无 query：仅按 namespace 前缀列举
        rows = self._collection.query(
            expr=expr,
            output_fields=["namespace", "key", "value_json", "created_at"],
            limit=limit,
        )
        return [
            SearchItem(
                namespace=tuple(r["namespace"].split("/")),
                key=r["key"],
                value=json.loads(r["value_json"]),
                score=None,
                created_at=datetime.fromtimestamp(r["created_at"] / 1000),
                updated_at=datetime.fromtimestamp(r["created_at"] / 1000),
            )
            for r in rows
        ]

    @staticmethod
    def _make_id(namespace: tuple, key: str) -> str:
        ns = "/".join(str(x) for x in namespace)
        return f"{ns}/{key}"
