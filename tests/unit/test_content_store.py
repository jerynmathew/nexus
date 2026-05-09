from __future__ import annotations

import time
from pathlib import Path

from nexus.dashboard.views import ContentStore


class TestContentStore:
    def test_store_and_get(self, tmp_path: Path) -> None:
        store = ContentStore(views_dir=str(tmp_path / "views"))
        view_id = store.store("<p>Hello</p>", title="Test")
        assert len(view_id) == 8

        html = store.get(view_id)
        assert html is not None
        assert "<p>Hello</p>" in html
        assert "Test" in html
        assert "Nexus" in html

    def test_get_missing(self, tmp_path: Path) -> None:
        store = ContentStore(views_dir=str(tmp_path / "views"))
        assert store.get("nonexistent") is None

    def test_expired_returns_none(self, tmp_path: Path) -> None:
        store = ContentStore(views_dir=str(tmp_path / "views"), ttl_hours=0)
        view_id = store.store("content")
        time.sleep(0.1)
        assert store.get(view_id) is None

    def test_cleanup_removes_old(self, tmp_path: Path) -> None:
        store = ContentStore(views_dir=str(tmp_path / "views"), ttl_hours=0)
        store.store("old content")
        time.sleep(0.1)
        removed = store.cleanup()
        assert removed >= 1

    def test_html_wrapper(self, tmp_path: Path) -> None:
        store = ContentStore(views_dir=str(tmp_path / "views"))
        view_id = store.store("<b>Bold</b>", title="My Title")
        html = store.get(view_id)
        assert html is not None
        assert "<!DOCTYPE html>" in html
        assert "My Title" in html
        assert "<b>Bold</b>" in html
