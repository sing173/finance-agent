"""Tests for repo/base.py — BaseRepository CRUD + batch + row_factory。"""
import sqlite3
from dataclasses import dataclass
from typing import Optional

import pytest

from finance_agent_backend.repo.base import BaseRepository


@dataclass
class SampleModel:
    name: str = ""
    value: int = 0
    id: Optional[int] = None


@pytest.fixture
def repo(tmp_path):
    """创建带 sample 表的 BaseRepository。"""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, value INTEGER)")
    conn.commit()
    return BaseRepository(conn, "sample", SampleModel, pk="id", insert_exclude=["id"])


class TestRowFactory:
    """row_factory 自动校验。"""

    def test_auto_sets_row_factory(self, tmp_path):
        """构造函数自动设置 sqlite3.Row。"""
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        assert conn.row_factory is None
        BaseRepository(conn, "t", SampleModel)
        assert conn.row_factory is sqlite3.Row

    def test_preserves_existing_row_factory(self, tmp_path):
        """已有 sqlite3.Row 不重复设置。"""
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        BaseRepository(conn, "t", SampleModel)
        assert conn.row_factory is sqlite3.Row


class TestInsert:
    """单条 INSERT。"""

    def test_insert_and_find_by_pk(self, repo):
        repo.insert(SampleModel(name="foo", value=42))
        repo.conn.commit()
        row = repo.find_by_pk(1)
        assert row is not None
        assert row.name == "foo"
        assert row.value == 42

    def test_insert_with_extra(self, repo):
        """extra 参数添加额外列。"""
        repo.conn.execute("ALTER TABLE sample ADD COLUMN extra TEXT DEFAULT ''")
        repo.conn.commit()
        repo.insert(SampleModel(name="bar", value=10), extra={"extra": "hello"})
        repo.conn.commit()
        row = repo.find_by_pk(1)
        assert row.name == "bar"

    def test_insert_or_ignore_duplicate(self, repo):
        """UNIQUE 冲突时静默忽略。"""
        repo.conn.execute("CREATE UNIQUE INDEX idx_name ON sample(name)")
        repo.conn.commit()
        repo.insert(SampleModel(name="dup", value=1))
        repo.insert_or_ignore(SampleModel(name="dup", value=2))
        repo.conn.commit()
        rows = repo.find_all()
        assert len(rows) == 1
        assert rows[0].value == 1


class TestInsertMany:
    """批量 executemany INSERT。"""

    def test_insert_many_basic(self, repo):
        objects = [SampleModel(name=f"item_{i}", value=i) for i in range(10)]
        repo.insert_many(objects)
        repo.conn.commit()
        rows = repo.find_all()
        assert len(rows) == 10
        assert rows[0].name == "item_0"
        assert rows[9].value == 9

    def test_insert_many_with_extra(self, repo):
        """批量插入 + extra 列。"""
        repo.conn.execute("ALTER TABLE sample ADD COLUMN tag TEXT DEFAULT ''")
        repo.conn.commit()
        objects = [SampleModel(name="a", value=1), SampleModel(name="b", value=2)]
        repo.insert_many(objects, extra={"tag": "batch"})
        repo.conn.commit()
        rows = repo.find_all()
        assert len(rows) == 2

    def test_insert_many_empty(self, repo):
        """空列表不报错。"""
        repo.insert_many([])
        repo.conn.commit()
        assert len(repo.find_all()) == 0


class TestSelect:
    """公共 select() 方法。"""

    def test_select_all(self, repo):
        repo.insert(SampleModel(name="a", value=1))
        repo.insert(SampleModel(name="b", value=2))
        repo.conn.commit()
        rows = repo.select()
        assert len(rows) == 2

    def test_select_with_where(self, repo):
        repo.insert(SampleModel(name="match", value=1))
        repo.insert(SampleModel(name="skip", value=2))
        repo.conn.commit()
        rows = repo.select(where="name = ?", params=("match",))
        assert len(rows) == 1
        assert rows[0].name == "match"

    def test_select_with_order_by(self, repo):
        repo.insert(SampleModel(name="b", value=2))
        repo.insert(SampleModel(name="a", value=1))
        repo.conn.commit()
        rows = repo.select(order_by="name ASC")
        assert rows[0].name == "a"
        assert rows[1].name == "b"

    def test_select_with_limit(self, repo):
        for i in range(5):
            repo.insert(SampleModel(name=f"item_{i}", value=i))
        repo.conn.commit()
        rows = repo.select(limit="2")
        assert len(rows) == 2

    def test_select_with_select_cols(self, repo):
        repo.insert(SampleModel(name="test", value=99))
        repo.conn.commit()
        rows = repo.select(select_cols=["name"])
        assert len(rows) == 1
        assert rows[0].name == "test"


class TestFindAll:
    """find_all() — select() 的底层实现。"""

    def test_find_all_empty(self, repo):
        assert repo.find_all() == []

    def test_find_all_with_params(self, repo):
        repo.insert(SampleModel(name="x", value=10))
        repo.insert(SampleModel(name="y", value=20))
        repo.conn.commit()
        rows = repo.find_all(where="value > ?", params=(15,))
        assert len(rows) == 1
        assert rows[0].name == "y"


class TestDelete:
    """delete_by_pk。"""

    def test_delete_existing(self, repo):
        repo.insert(SampleModel(name="del_me", value=1))
        repo.conn.commit()
        repo.delete_by_pk(1)
        repo.conn.commit()
        assert repo.find_by_pk(1) is None

    def test_delete_nonexistent(self, repo):
        """删除不存在的 pk 不报错。"""
        repo.delete_by_pk(999)
        repo.conn.commit()
