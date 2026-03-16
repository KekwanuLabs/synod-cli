"""Unit tests for the auto_context module.

Focuses on the query-analysis layer (pure functions, no I/O) and the
newly-added import-detection feature, plus a lightweight integration test
for gather_auto_context using a real temp directory.
"""

import asyncio
from pathlib import Path

import pytest

from synod.core.auto_context import (
    AutoContextConfig,
    _extract_import_file_candidates,
    _import_candidates_to_file_mentions,
    analyze_query_for_context,
    gather_auto_context,
)


# ============================================================================
# _extract_import_file_candidates
# ============================================================================


class TestExtractImportFileCandidates:
    """Tests for the import-statement extraction helper."""

    # --- Python from-import ---

    def test_python_from_import_simple(self):
        """from utils import helper  ->  'utils' candidate."""
        result = _extract_import_file_candidates("from utils import helper")
        assert "utils" in result

    def test_python_from_import_dotted(self):
        """from database.connection import DB  ->  'database/connection'."""
        result = _extract_import_file_candidates("from database.connection import DB")
        assert "database/connection" in result

    def test_python_from_import_deeply_nested(self):
        """from a.b.c import X  ->  'a/b/c'."""
        result = _extract_import_file_candidates("from a.b.c import X")
        assert "a/b/c" in result

    def test_python_relative_import_stripped(self):
        """from .models import User  ->  leading dot stripped  ->  'models'."""
        result = _extract_import_file_candidates("from .models import User")
        assert "models" in result

    def test_python_double_relative_import_stripped(self):
        """from ..utils import helper  ->  'utils'."""
        result = _extract_import_file_candidates("from ..utils import helper")
        assert "utils" in result

    def test_python_stdlib_filtered_out(self):
        """stdlib modules (os, sys, re, …) must not appear in candidates."""
        for stdlib_mod in ["os", "sys", "re", "json", "pathlib", "asyncio"]:
            result = _extract_import_file_candidates(f"from {stdlib_mod} import something")
            assert stdlib_mod not in result, f"stdlib module '{stdlib_mod}' should be filtered"

    def test_python_plain_import_simple(self):
        """import mymodule  ->  'mymodule'."""
        result = _extract_import_file_candidates("import mymodule")
        assert "mymodule" in result

    def test_python_plain_import_dotted(self):
        """import pkg.sub  ->  'pkg/sub'."""
        result = _extract_import_file_candidates("import pkg.sub")
        assert "pkg/sub" in result

    def test_python_plain_import_stdlib_filtered(self):
        """import os should yield no candidates."""
        result = _extract_import_file_candidates("import os")
        assert "os" not in result

    # --- JS / TS from-import ---

    def test_js_relative_import_single_quotes(self):
        """import foo from './utils'  ->  'utils'."""
        result = _extract_import_file_candidates("import foo from './utils'")
        assert "utils" in result

    def test_js_relative_import_double_quotes(self):
        """import { bar } from \"../lib/helpers\"  ->  'lib/helpers'."""
        result = _extract_import_file_candidates('import { bar } from "../lib/helpers"')
        assert "lib/helpers" in result

    def test_js_non_relative_import_ignored(self):
        """Bare package names like 'react' must not be included."""
        result = _extract_import_file_candidates("import React from 'react'")
        assert "react" not in result

    def test_js_require_relative(self):
        """require('./config')  ->  'config'."""
        result = _extract_import_file_candidates("const cfg = require('./config')")
        assert "config" in result

    def test_js_require_non_relative_ignored(self):
        """require('express') must not be included."""
        result = _extract_import_file_candidates("const express = require('express')")
        assert "express" not in result

    # --- Deduplication ---

    def test_deduplication(self):
        """Same module appearing twice should produce one candidate."""
        query = "from utils import a\nfrom utils import b"
        result = _extract_import_file_candidates(query)
        assert result.count("utils") == 1

    # --- No imports ---

    def test_no_imports_in_query(self):
        """Plain prose should yield an empty list."""
        result = _extract_import_file_candidates("How do I sort a list in Python?")
        assert result == []

    # --- Inline code / backtick context ---

    def test_import_in_backtick_code(self):
        """Import inside backtick-fenced code fragment should be detected."""
        query = "Fix the bug in `from database import connection`"
        result = _extract_import_file_candidates(query)
        assert "database" in result


# ============================================================================
# _import_candidates_to_file_mentions
# ============================================================================


class TestImportCandidatesToFileMentions:
    """Tests for the candidate -> file-path expansion helper."""

    def test_bare_name_expands_to_multiple_extensions(self):
        """'utils' should expand to utils.py, utils.ts, etc."""
        result = _import_candidates_to_file_mentions(["utils"])
        assert "utils.py" in result
        assert "utils.ts" in result
        assert "utils.js" in result

    def test_path_with_extension_passed_through(self):
        """Candidate that already has an extension should not get duplicated."""
        result = _import_candidates_to_file_mentions(["utils.py"])
        assert "utils.py" in result
        # Should not also produce utils.py.py
        assert "utils.py.py" not in result

    def test_nested_path_expands_correctly(self):
        """'database/connection' should expand to database/connection.py etc."""
        result = _import_candidates_to_file_mentions(["database/connection"])
        assert "database/connection.py" in result
        assert "database/connection.ts" in result

    def test_empty_input(self):
        """Empty input list should return an empty list."""
        assert _import_candidates_to_file_mentions([]) == []

    def test_py_comes_before_ts(self):
        """Python extension should appear before TypeScript (priority order)."""
        result = _import_candidates_to_file_mentions(["mymod"])
        py_idx = next(i for i, v in enumerate(result) if v == "mymod.py")
        ts_idx = next(i for i, v in enumerate(result) if v == "mymod.ts")
        assert py_idx < ts_idx


# ============================================================================
# analyze_query_for_context  (unit — no filesystem)
# ============================================================================


class TestAnalyzeQueryForContext:
    """Tests for the main query analysis function."""

    # --- file_mentions ---

    def test_explicit_file_path_detected(self):
        """A file path in the query must appear in file_mentions."""
        result = analyze_query_for_context("Look at src/auth.py for the bug")
        assert any("auth.py" in m for m in result["file_mentions"])

    def test_explicit_ts_file_detected(self):
        result = analyze_query_for_context("Check ./config.ts")
        assert any("config.ts" in m for m in result["file_mentions"])

    # --- import_mentions ---

    def test_python_from_import_in_import_mentions(self):
        """from-import module path should populate import_mentions."""
        result = analyze_query_for_context("Fix `from database import connection`")
        assert "database" in result["import_mentions"]

    def test_import_mentions_empty_for_plain_prose(self):
        result = analyze_query_for_context("What is the meaning of life?")
        assert result["import_mentions"] == []

    # --- import-derived paths flow into file_mentions ---

    def test_import_derived_paths_in_file_mentions(self):
        """Import-derived candidate paths must be merged into file_mentions."""
        result = analyze_query_for_context("Fix `from database import connection`")
        assert any("database" in m for m in result["file_mentions"])

    def test_no_duplicate_when_explicit_and_import_overlap(self):
        """If the user mentions both database.py and `from database import x`,
        database.py should appear exactly once in file_mentions."""
        result = analyze_query_for_context(
            "See database.py: `from database import connection`"
        )
        database_py_count = result["file_mentions"].count("database.py")
        assert database_py_count == 1

    # --- symbol_mentions ---

    def test_camelcase_symbol_detected(self):
        result = analyze_query_for_context("Where is UserService defined?")
        assert "UserService" in result["symbol_mentions"]

    def test_snake_case_symbol_detected(self):
        result = analyze_query_for_context("The function parse_config is broken")
        assert "parse_config" in result["symbol_mentions"]

    def test_common_words_not_symbols(self):
        """Common English words should not appear in symbol_mentions."""
        result = analyze_query_for_context("What is the answer?")
        for word in ["the", "and", "for"]:
            assert word not in result["symbol_mentions"]

    # --- is_code_query ---

    def test_is_code_query_true_for_explicit_file(self):
        result = analyze_query_for_context("Look at utils.py")
        assert result["is_code_query"] is True

    def test_is_code_query_true_for_import_statement(self):
        result = analyze_query_for_context("from utils import helper")
        assert result["is_code_query"] is True

    def test_is_code_query_true_for_code_keyword(self):
        result = analyze_query_for_context("There is a bug in my code")
        assert result["is_code_query"] is True

    def test_is_code_query_false_for_plain_prose(self):
        result = analyze_query_for_context("Tell me about the Roman Empire")
        assert result["is_code_query"] is False

    # --- keywords ---

    def test_keywords_extracted(self):
        result = analyze_query_for_context("fix authentication timeout")
        assert "fix" in result["keywords"]
        assert "authentication" in result["keywords"]
        assert "timeout" in result["keywords"]

    def test_stopwords_excluded_from_keywords(self):
        result = analyze_query_for_context("What is the problem?")
        for stopword in ["what", "the", "is"]:
            assert stopword not in result["keywords"]

    def test_keywords_limited_to_ten(self):
        """keywords list should be capped at 10 items."""
        long_query = " ".join(f"word{i}" for i in range(20))
        result = analyze_query_for_context(long_query)
        assert len(result["keywords"]) <= 10


# ============================================================================
# gather_auto_context  (integration — real filesystem via temp_dir)
# ============================================================================


class TestGatherAutoContextIntegration:
    """Integration tests for gather_auto_context using temp directories."""

    def test_explicit_file_mention_resolved(self, temp_dir):
        """A file explicitly named in the query should be gathered."""
        target = temp_dir / "auth.py"
        target.write_text("def login(user): pass")

        files, paths = asyncio.get_event_loop().run_until_complete(
            gather_auto_context(
                f"Look at auth.py for the bug",
                root_path=str(temp_dir),
            )
        )

        assert "auth.py" in paths
        assert "auth.py" in files

    def test_import_statement_resolves_to_file(self, temp_dir):
        """A Python from-import should cause the referenced module to be gathered."""
        db_file = temp_dir / "database.py"
        db_file.write_text("class Connection: pass")

        files, paths = asyncio.get_event_loop().run_until_complete(
            gather_auto_context(
                "Fix the bug in `from database import Connection`",
                root_path=str(temp_dir),
            )
        )

        assert "database.py" in paths
        assert "database.py" in files

    def test_dotted_import_resolves_nested_file(self, temp_dir):
        """from pkg.module import X should resolve pkg/module.py."""
        pkg_dir = temp_dir / "pkg"
        pkg_dir.mkdir()
        mod_file = pkg_dir / "module.py"
        mod_file.write_text("def X(): pass")

        files, paths = asyncio.get_event_loop().run_until_complete(
            gather_auto_context(
                "from pkg.module import X is broken",
                root_path=str(temp_dir),
            )
        )

        assert "pkg/module.py" in paths

    def test_non_code_query_returns_empty(self, temp_dir):
        """A purely natural-language query should return no context."""
        files, paths = asyncio.get_event_loop().run_until_complete(
            gather_auto_context(
                "Tell me about the French Revolution",
                root_path=str(temp_dir),
            )
        )

        assert files == {}
        assert paths == []

    def test_memory_hints_resolve_files(self, temp_dir):
        """Memory hints pointing at real files should be gathered."""
        hint_file = temp_dir / "helpers.py"
        hint_file.write_text("def util(): pass")

        files, paths = asyncio.get_event_loop().run_until_complete(
            gather_auto_context(
                "There is a bug in my code",
                root_path=str(temp_dir),
                memory_hints=["helpers.py"],
            )
        )

        assert "helpers.py" in paths

    def test_max_files_limit_respected(self, temp_dir):
        """gather_auto_context should not return more files than max_files."""
        for i in range(10):
            (temp_dir / f"mod{i}.py").write_text(f"# module {i}")

        cfg = AutoContextConfig(max_files=3)
        files, paths = asyncio.get_event_loop().run_until_complete(
            gather_auto_context(
                "from mod0 import a; from mod1 import b; from mod2 import c; "
                "from mod3 import d; from mod4 import e",
                root_path=str(temp_dir),
                config=cfg,
            )
        )

        assert len(paths) <= 3

    def test_content_has_line_numbers_by_default(self, temp_dir):
        """With default config, file content should include line-number prefixes."""
        f = temp_dir / "hello.py"
        f.write_text("print('hi')")

        files, paths = asyncio.get_event_loop().run_until_complete(
            gather_auto_context(
                "Look at hello.py",
                root_path=str(temp_dir),
            )
        )

        assert "hello.py" in files
        # Default includes line numbers in "   1| " format
        assert "1|" in files["hello.py"]
