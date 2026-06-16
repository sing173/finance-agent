"""轻量 Repository 基类 — 通过 dataclass 自动生成 INSERT/SELECT 字段列表"""
from __future__ import annotations

import sqlite3
from dataclasses import fields
from typing import Generic, TypeVar

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """通用 SQLite Repository，从 dataclass 字段推导 SQL 列名。

    新增表字段时，只需修改 dataclass —— INSERT / SELECT 字段列表自动生成，
    消除 Issue #46/#48 这类"新增列漏改某处 SQL"的回归风险。
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        table: str,
        model_cls: type[T],
        pk: str = "id",
        insert_exclude: list[str] | None = None,
    ):
        self.conn = conn
        self.table = table
        self.model_cls = model_cls
        self.pk = pk
        self._all_cols = [f.name for f in fields(model_cls)]
        self._insert_cols = [
            c for c in self._all_cols if c not in (insert_exclude or [])
        ]
        # 保存原始 row_factory 以便恢复，仅在必要时设置 sqlite3.Row
        self._saved_row_factory = conn.row_factory
        if conn.row_factory is not sqlite3.Row:
            conn.row_factory = sqlite3.Row

    def _build_instance(self, row: sqlite3.Row) -> T:
        """从 DB row 构造 model 实例。优先使用 from_db_row（含类型转换），回退到 **kwargs。"""
        if hasattr(self.model_cls, 'from_db_row'):
            return self.model_cls.from_db_row(row)
        return self.model_cls(**row)

    # ── SQL 生成 ──

    def _insert_sql(
        self,
        extra_cols: list[str] | None = None,
        or_ignore: bool = False,
    ) -> str:
        cols = self._insert_cols + (extra_cols or [])
        placeholders = ", ".join("?" * len(cols))
        keyword = "INSERT OR IGNORE" if or_ignore else "INSERT"
        return f"{keyword} INTO {self.table} ({', '.join(cols)}) VALUES ({placeholders})"

    def _select_sql(
        self,
        select_cols: list[str] | None = None,
        where: str = "",
        order_by: str = "",
        limit: str = "",
    ) -> str:
        cols = select_cols or self._all_cols
        sql = f"SELECT {', '.join(cols)} FROM {self.table}"
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {limit}"
        return sql

    # ── 通用 CRUD ──

    def insert(self, obj: T, *, extra: dict | None = None) -> None:
        vals = [getattr(obj, c) for c in self._insert_cols]
        extra_cols: list[str] = []
        if extra:
            for k, v in extra.items():
                vals.append(v)
                extra_cols.append(k)
        sql = self._insert_sql(extra_cols=extra_cols)
        self.conn.execute(sql, vals)

    def insert_or_ignore(self, obj: T, *, extra: dict | None = None) -> None:
        vals = [getattr(obj, c) for c in self._insert_cols]
        extra_cols: list[str] = []
        if extra:
            for k, v in extra.items():
                vals.append(v)
                extra_cols.append(k)
        sql = self._insert_sql(extra_cols=extra_cols, or_ignore=True)
        self.conn.execute(sql, vals)

    def find_by_pk(self, pk_value) -> T | None:
        row = self.conn.execute(
            self._select_sql(where=f"{self.pk} = ?"), (pk_value,)
        ).fetchone()
        return self._build_instance(row) if row else None

    def find_all(
        self,
        select_cols: list[str] | None = None,
        where: str = "",
        params: tuple = (),
        order_by: str = "",
        limit: str = "",
    ) -> list[T]:
        rows = self.conn.execute(
            self._select_sql(
                select_cols=select_cols,
                where=where,
                order_by=order_by,
                limit=limit,
            ),
            params,
        ).fetchall()
        return [self._build_instance(r) for r in rows]

    def delete_by_pk(self, pk_value) -> None:
        self.conn.execute(
            f"DELETE FROM {self.table} WHERE {self.pk} = ?", (pk_value,)
        )

    def select(
        self,
        select_cols: list[str] | None = None,
        where: str = "",
        params: tuple = (),
        order_by: str = "",
        limit: str = "",
    ) -> list[T]:
        """公共 SELECT：返回 model 实例列表。供外部调用，无需访问 _select_sql。"""
        return self.find_all(
            select_cols=select_cols,
            where=where,
            params=params,
            order_by=order_by,
            limit=limit,
        )

    def insert_many(self, objects: list[T], *, extra: dict | None = None) -> None:
        """批量 INSERT（executemany）。所有对象共享相同列列表。"""
        extra_cols = list(extra.keys()) if extra else []
        sql = self._insert_sql(extra_cols=extra_cols)
        batch = []
        for obj in objects:
            vals = [getattr(obj, c) for c in self._insert_cols]
            if extra:
                vals.extend(extra.values())
            batch.append(vals)
        self.conn.executemany(sql, batch)
