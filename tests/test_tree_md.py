import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import tree_md


class TreeMdTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name) / "sample-project"

        for path in (
            "docs/guide.md",
            "src/app.py",
            "src/nested/deep.txt",
            ".git/config",
            "node_modules/pkg/index.js",
            ".gitignore",
            "README.md",
            "image.png",
            "my notes.md",
        ):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x", encoding="utf-8")

    def test_default_tree_ignores_noise(self) -> None:
        node, errors = tree_md.collect(
            self.root, excludes=tree_md.DEFAULT_EXCLUDES
        )
        self.assertEqual(errors, [])
        expected = "\n".join(
            [
                "sample-project/",
                "├── docs/",
                "│   └── guide.md",
                "├── src/",
                "│   ├── nested/",
                "│   │   └── deep.txt",
                "│   └── app.py",
                "├── .gitignore",
                "├── image.png",
                "├── my notes.md",
                "└── README.md",
            ]
        )
        self.assertEqual(tree_md.render_tree(node), expected)

    def test_summary_counts(self) -> None:
        node, _ = tree_md.collect(self.root, excludes=tree_md.DEFAULT_EXCLUDES)
        markdown = tree_md.build_markdown(node)
        self.assertIn("3 directories, 7 files", markdown)
        self.assertTrue(markdown.endswith("\n"))

    def test_list_format_creates_relative_links(self) -> None:
        node, _ = tree_md.collect(self.root, excludes=tree_md.DEFAULT_EXCLUDES)
        rendered = tree_md.render_list(node, self.root)
        self.assertIn("- **sample-project/**", rendered)
        self.assertIn("    - [guide.md](docs/guide.md)", rendered)
        self.assertIn("[deep.txt](src/nested/deep.txt)", rendered)
        self.assertIn("[my notes.md](my%20notes.md)", rendered)

    def test_exclude_glob(self) -> None:
        node, _ = tree_md.collect(
            self.root,
            excludes=(*tree_md.DEFAULT_EXCLUDES, "*.md"),
        )
        rendered = tree_md.render_tree(node)
        self.assertNotIn("guide.md", rendered)
        self.assertNotIn("README.md", rendered)
        self.assertIn("app.py", rendered)
        self.assertIn("docs/", rendered)

    def test_exclude_relative_path(self) -> None:
        node, _ = tree_md.collect(
            self.root,
            excludes=(*tree_md.DEFAULT_EXCLUDES, "docs/*"),
        )
        rendered = tree_md.render_tree(node)
        self.assertNotIn("guide.md", rendered)
        self.assertIn("docs/", rendered)

    def test_max_depth(self) -> None:
        node, _ = tree_md.collect(
            self.root,
            max_depth=1,
            excludes=tree_md.DEFAULT_EXCLUDES,
        )
        rendered = tree_md.render_tree(node)
        self.assertIn("├── docs/", rendered)
        self.assertIn("├── src/", rendered)
        self.assertIn("README.md", rendered)
        self.assertNotIn("guide.md", rendered)
        self.assertNotIn("app.py", rendered)

    def test_dirs_only(self) -> None:
        node, _ = tree_md.collect(
            self.root,
            excludes=tree_md.DEFAULT_EXCLUDES,
            dirs_only=True,
        )
        rendered = tree_md.render_tree(node)
        self.assertNotIn(".gitignore", rendered)
        self.assertNotIn("app.py", rendered)
        self.assertIn("    └── nested/", rendered)
        self.assertIn("3 directories, 0 files", tree_md.build_markdown(node))

    def test_output_file_and_list_links(self) -> None:
        output = self.root / "docs" / "STRUCTURE.md"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = tree_md.main(
                [str(self.root), "--format", "list", "-o", str(output)]
            )

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Wrote", stderr.getvalue())
        content = output.read_text(encoding="utf-8")
        self.assertIn("# Directory Structure", content)
        self.assertIn("[guide.md](guide.md)", content)
        self.assertIn("[README.md](../README.md)", content)

        # The generated file itself is not listed on a later run.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
            io.StringIO()
        ):
            tree_md.main([str(self.root), "--format", "list", "-o", str(output)])
        self.assertNotIn("STRUCTURE.md", output.read_text(encoding="utf-8"))

    def test_timestamp_only_when_requested(self) -> None:
        node, _ = tree_md.collect(self.root, excludes=tree_md.DEFAULT_EXCLUDES)
        self.assertNotIn("_Generated:", tree_md.build_markdown(node))
        self.assertIn(
            "_Generated:",
            tree_md.build_markdown(node, timestamp=True),
        )

    def test_no_title_option(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
            io.StringIO()
        ):
            code = tree_md.main([str(self.root), "--no-title"])

        self.assertEqual(code, 0)
        self.assertFalse(stdout.getvalue().startswith("# "))
        self.assertTrue(stdout.getvalue().startswith("```text"))


if __name__ == "__main__":
    unittest.main()
