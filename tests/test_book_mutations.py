"""Regression tests for stale bookshelf pages modifying the wrong book."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import web_app


class BookMutationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / "library"
        self.library.mkdir()
        self.settings = {"bookshelf_dir": str(self.library), "dst": str(self.library)}
        self.addCleanup(patch.stopall)
        patch.object(web_app, "load_settings", side_effect=lambda: dict(self.settings)).start()
        patch.object(web_app.db, "enabled", False).start()
        self.client = web_app.app.test_client()
        self.a = self.make_book("A")
        self.b = self.make_book("B")
        self.c = self.make_book("C")

    def make_book(self, name, parent=None):
        folder = (parent or self.library) / name
        folder.mkdir(parents=True)
        (folder / "book.txt").write_text(name, encoding="utf-8")
        (folder / "metadata.json").write_text(json.dumps({"title": name}), encoding="utf-8")
        return folder

    def books(self, suffix=""):
        response = self.client.get("/api/shelf" + suffix)
        self.assertEqual(response.status_code, 200)
        return {book["title"]: book for book in response.json["books"]}

    def mutate(self, book, method, *, suffix="", version=True):
        route = "metadata" if method == "POST" else "book"
        headers = {"If-Match": '"' + book["mutation_version"] + '"'} if version else {}
        return self.client.open(
            f"/api/{route}/{book['mutation_id']}{suffix}", method=method,
            headers=headers, json={"title": "Updated"} if method == "POST" else None,
        )

    def test_delete_keeps_original_target_after_indices_shift(self):
        old = self.books()["B"]
        shutil.rmtree(self.a)
        self.assertNotEqual(old["id"], self.books()["B"]["id"])
        response = self.mutate(old, "DELETE")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertFalse(self.b.exists())
        self.assertTrue(self.c.exists())

    def test_edit_keeps_original_target_after_indices_shift(self):
        old = self.books()["B"]
        shutil.rmtree(self.a)
        response = self.mutate(old, "POST")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(json.loads((self.b / "metadata.json").read_text())["title"], "Updated")
        self.assertEqual(json.loads((self.c / "metadata.json").read_text())["title"], "C")

    def test_removed_target_never_falls_back_to_current_index(self):
        old = self.books()["B"]
        shutil.rmtree(self.b)
        for method in ("DELETE", "POST"):
            with self.subTest(method=method):
                self.assertEqual(self.mutate(old, method).status_code, 404)
        self.assertTrue(self.c.exists())

    def test_changed_file_rejects_stale_requests(self):
        old = self.books()["B"]
        (self.b / "book.txt").write_text("replacement content")
        for method in ("DELETE", "POST"):
            with self.subTest(method=method):
                response = self.mutate(old, method)
                self.assertEqual(response.status_code, 412)
                self.assertFalse(response.json["success"])
        self.assertTrue(self.b.exists())

    def test_replaced_file_at_same_path_rejects_old_version(self):
        old = self.books()["B"]
        replacement = self.root / "replacement.txt"
        replacement.write_text("B")
        replacement.replace(self.b / "book.txt")
        self.assertEqual(self.mutate(old, "DELETE").status_code, 412)

    def test_metadata_edit_invalidates_other_open_forms(self):
        old = self.books()["B"]
        self.assertEqual(self.mutate(old, "POST").status_code, 200)
        self.assertEqual(self.mutate(old, "POST").status_code, 412)
        self.assertEqual(self.mutate(old, "DELETE").status_code, 412)

    def test_precondition_is_required_and_numeric_routes_fail_closed(self):
        old = self.books()["B"]
        for method in ("DELETE", "POST"):
            self.assertEqual(self.mutate(old, method, version=False).status_code, 428)
        self.assertEqual(self.client.delete("/api/book/1").status_code, 404)
        self.assertEqual(self.client.post("/api/metadata/1", json={"title": "Wrong"}).status_code, 404)
        self.assertTrue(self.b.exists())

    def test_uuid_is_unchanged_after_title_change_and_rescan(self):
        old = self.books()["B"]
        self.assertEqual(self.mutate(old, "POST").status_code, 200)
        new = self.books()["Updated"]
        self.assertEqual(old["mutation_id"], new["mutation_id"])
        self.assertNotEqual(old["mutation_version"], new["mutation_version"])

    def test_novel_shelf_has_the_same_stale_index_protection(self):
        novels = self.library / web_app.config.WEB_NOVELS_DIR
        first = self.make_book("Novel A", novels)
        target = self.make_book("Novel B", novels)
        old = self.books("?shelf=novels")["Novel B"]
        shutil.rmtree(first)
        response = self.mutate(old, "DELETE", suffix="?shelf=novels")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(target.exists())
        self.assertTrue(self.b.exists())

    def test_directory_override_cannot_redirect_mutations(self):
        other = self.root / "other"
        other.mkdir()
        target = self.make_book("Other", other)
        book = self.books("?dir=" + str(other))["Other"]
        self.assertIsNone(book["mutation_id"])
        old = self.books()["B"]
        self.assertEqual(self.mutate(old, "DELETE", suffix="?dir=" + str(other)).status_code, 200)
        self.assertTrue(target.exists())
        self.assertFalse(self.b.exists())

    def test_symlink_outside_library_has_no_mutation_credentials(self):
        outside = self.root / "outside.txt"
        outside.write_text("outside")
        (self.b / "book.txt").unlink()
        (self.b / "book.txt").symlink_to(outside)
        self.assertIsNone(self.books()["B"]["mutation_id"])


if __name__ == "__main__":
    unittest.main()
