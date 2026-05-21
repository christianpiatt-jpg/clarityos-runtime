"""
Tests for ELINS Unit 24 — evidence-directory allowlist + path
sanitization.

Layered coverage (>= 60 tests, target ~70):
    A. Core validation — valid paths
    B. Core rejection — bad inputs
    C. Containment + symlinks
    D. Cross-platform path quirks (slashes, trailing slash, normalization)
    E. Integration — analyze_and_store + endpoint
    F. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import os
import platform
import secrets
import sys
import tempfile
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_evidence_allowlist as al
import elins_persistence as ep


_IS_WINDOWS = sys.platform == "win32"


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture(autouse=True)
def _runs_dir_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runs_dir = tmp_path / "elins_runs"
    monkeypatch.setenv(ep._RUNS_DIR_ENV_VAR, str(runs_dir))
    yield runs_dir


@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    return TestClient(app_module.app)


def _make_user_session(app_module, username="alice"):
    import bcrypt
    import sessions_store
    import users_store

    pwd_hash = bcrypt.hashpw(b"test-pass-123", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return sid


def _auth(sid):
    return {"X-Session-ID": sid}


@pytest.fixture
def empty_allowlist(monkeypatch):
    """Re-monkeypatch the allowlist to an empty tuple, overriding the
    conftest.py autouse fixture that adds tmpdir. Lets negative-path
    tests prove rejection without using a contrived absolute path that
    might exist (e.g. ``C:\\Windows``)."""
    monkeypatch.setattr(al, "ALLOWED_EVIDENCE_DIRS", ())
    yield


@pytest.fixture
def restricted_allowlist(monkeypatch, tmp_path):
    """Set the allowlist to a single specific tmp subdirectory. Lets
    tests verify that paths INSIDE that subdir pass and paths OUTSIDE
    it (but still under tmpdir) fail."""
    root = tmp_path / "restricted_root"
    root.mkdir()
    monkeypatch.setattr(al, "ALLOWED_EVIDENCE_DIRS", (str(root),))
    yield root


# ===========================================================================
# A. Core validation — valid paths
# ===========================================================================
class TestValidPaths:
    def test_tmp_path_itself_is_allowed(self, tmp_path):
        # Conftest autouse fixture already added tempfile.gettempdir().
        result = al.validate_evidence_dir(str(tmp_path))
        assert isinstance(result, str)

    def test_returns_normalised_realpath(self, tmp_path):
        result = al.validate_evidence_dir(str(tmp_path))
        # Result must equal the realpath of the input (caller can use
        # this for both the scan and the metadata field).
        assert result == os.path.realpath(str(tmp_path))

    def test_nested_subdirectory_allowed(self, tmp_path):
        nested = tmp_path / "lvl1" / "lvl2" / "lvl3"
        nested.mkdir(parents=True)
        result = al.validate_evidence_dir(str(nested))
        assert os.path.commonpath(
            [result, os.path.realpath(str(tmp_path))]
        ) == os.path.realpath(str(tmp_path))

    def test_returned_path_is_absolute(self, tmp_path):
        result = al.validate_evidence_dir(str(tmp_path))
        assert os.path.isabs(result)

    def test_repeated_validation_same_result(self, tmp_path):
        a = al.validate_evidence_dir(str(tmp_path))
        b = al.validate_evidence_dir(str(tmp_path))
        assert a == b

    def test_restricted_root_allows_root_itself(self, restricted_allowlist):
        result = al.validate_evidence_dir(str(restricted_allowlist))
        assert result == os.path.realpath(str(restricted_allowlist))

    def test_restricted_root_allows_subdir(self, restricted_allowlist):
        sub = restricted_allowlist / "sub"
        sub.mkdir()
        result = al.validate_evidence_dir(str(sub))
        assert result == os.path.realpath(str(sub))


# ===========================================================================
# B. Core rejection — bad inputs
# ===========================================================================
class TestRejectionBasicTypes:
    def test_none_rejected(self):
        with pytest.raises(ValueError, match="non-empty string"):
            al.validate_evidence_dir(None)

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError, match="non-empty string"):
            al.validate_evidence_dir("")

    def test_int_rejected(self):
        with pytest.raises(ValueError, match="non-empty string"):
            al.validate_evidence_dir(42)

    def test_bytes_rejected(self):
        with pytest.raises(ValueError, match="non-empty string"):
            al.validate_evidence_dir(b"/evidence/run1")

    def test_list_rejected(self):
        with pytest.raises(ValueError, match="non-empty string"):
            al.validate_evidence_dir(["/evidence"])

    def test_dict_rejected(self):
        with pytest.raises(ValueError, match="non-empty string"):
            al.validate_evidence_dir({"path": "/evidence"})


class TestRejectionRelativePaths:
    @pytest.mark.parametrize("rel", [
        "relative/path",
        "evidence/run1",
        "./run1",
        "run_001",
    ])
    def test_relative_paths_rejected(self, rel):
        with pytest.raises(ValueError, match="must be absolute"):
            al.validate_evidence_dir(rel)


class TestRejectionTraversal:
    def test_dotdot_in_middle_rejected(self, tmp_path):
        bad = os.path.join(str(tmp_path), "..", "elsewhere")
        with pytest.raises(ValueError, match="parent-directory traversal"):
            al.validate_evidence_dir(bad)

    def test_dotdot_at_root_rejected(self):
        with pytest.raises(ValueError, match="parent-directory traversal"):
            al.validate_evidence_dir("/evidence/../etc")

    def test_multiple_dotdot_rejected(self, tmp_path):
        bad = os.path.join(str(tmp_path), "..", "..", "..")
        with pytest.raises(ValueError, match="parent-directory traversal"):
            al.validate_evidence_dir(bad)

    def test_dotdot_with_backslash_rejected(self):
        # Defensive: even on POSIX, a path containing a backslash-style
        # dotdot must be rejected.
        with pytest.raises(ValueError, match="parent-directory traversal"):
            al.validate_evidence_dir("/evidence/foo\\..\\bar")


class TestRejectionExistenceAndType:
    def test_nonexistent_path_rejected(self, tmp_path):
        bad = tmp_path / "does_not_exist"
        with pytest.raises(ValueError, match="not an existing directory"):
            al.validate_evidence_dir(str(bad))

    def test_file_not_directory_rejected(self, tmp_path):
        f = tmp_path / "afile.txt"
        f.write_text("not a directory", encoding="utf-8")
        with pytest.raises(ValueError, match="not an existing directory"):
            al.validate_evidence_dir(str(f))

    def test_empty_allowlist_rejects_everything(
        self, tmp_path, empty_allowlist,
    ):
        with pytest.raises(ValueError, match="not inside any allowlisted"):
            al.validate_evidence_dir(str(tmp_path))


class TestRejectionOutsideAllowlist:
    def test_path_outside_restricted_root_rejected(
        self, tmp_path, restricted_allowlist,
    ):
        # tmp_path is inside the system tmpdir, but the restricted
        # fixture overrode the allowlist to a SPECIFIC sub-root only.
        outside = tmp_path / "outside_dir"
        outside.mkdir()
        with pytest.raises(ValueError, match="not inside any allowlisted"):
            al.validate_evidence_dir(str(outside))

    def test_sibling_of_allowlist_rejected(self, tmp_path, monkeypatch):
        root = tmp_path / "real_root"
        root.mkdir()
        sibling = tmp_path / "real_root_sibling"
        sibling.mkdir()
        monkeypatch.setattr(al, "ALLOWED_EVIDENCE_DIRS", (str(root),))
        with pytest.raises(ValueError, match="not inside any allowlisted"):
            al.validate_evidence_dir(str(sibling))


# ===========================================================================
# C. Containment + symlinks
# ===========================================================================
class TestSymlinkBehavior:
    def _can_symlink(self, tmp_path):
        """Windows refuses symlink creation without admin or developer
        mode; gracefully skip those tests rather than fail spuriously."""
        if not _IS_WINDOWS:
            return True
        try:
            target = tmp_path / "_t"
            target.mkdir()
            link = tmp_path / "_l"
            os.symlink(str(target), str(link), target_is_directory=True)
            return True
        except (OSError, NotImplementedError):
            return False

    def test_symlink_inside_root_allowed(
        self, tmp_path, restricted_allowlist,
    ):
        if not self._can_symlink(tmp_path):
            pytest.skip("symlink creation not permitted on this system")
        target = restricted_allowlist / "real_target"
        target.mkdir()
        link = restricted_allowlist / "alias"
        os.symlink(str(target), str(link), target_is_directory=True)
        # Both target and link resolve under the restricted root.
        result = al.validate_evidence_dir(str(link))
        assert result == os.path.realpath(str(target))

    def test_symlink_escaping_root_rejected(
        self, tmp_path, restricted_allowlist,
    ):
        if not self._can_symlink(tmp_path):
            pytest.skip("symlink creation not permitted on this system")
        # Real target lives OUTSIDE the restricted root.
        outside = tmp_path / "external_target"
        outside.mkdir()
        # Symlink lives INSIDE the restricted root but points out.
        link = restricted_allowlist / "escape"
        os.symlink(str(outside), str(link), target_is_directory=True)
        with pytest.raises(ValueError, match="not inside any allowlisted"):
            al.validate_evidence_dir(str(link))


class TestContainmentEdgeCases:
    def test_path_equal_to_root_allowed(
        self, tmp_path, monkeypatch,
    ):
        root = tmp_path / "exact_root"
        root.mkdir()
        monkeypatch.setattr(al, "ALLOWED_EVIDENCE_DIRS", (str(root),))
        result = al.validate_evidence_dir(str(root))
        assert result == os.path.realpath(str(root))

    def test_path_parent_of_root_rejected(self, tmp_path, monkeypatch):
        root = tmp_path / "parent" / "real_root"
        root.mkdir(parents=True)
        # Allowlist has the inner root; caller passes the outer parent.
        monkeypatch.setattr(al, "ALLOWED_EVIDENCE_DIRS", (str(root),))
        outer = tmp_path / "parent"
        with pytest.raises(ValueError, match="not inside any allowlisted"):
            al.validate_evidence_dir(str(outer))

    def test_two_roots_first_matches(self, tmp_path, monkeypatch):
        a_root = tmp_path / "root_a"
        b_root = tmp_path / "root_b"
        a_root.mkdir()
        b_root.mkdir()
        monkeypatch.setattr(
            al, "ALLOWED_EVIDENCE_DIRS", (str(a_root), str(b_root)),
        )
        target = a_root / "x"
        target.mkdir()
        result = al.validate_evidence_dir(str(target))
        assert result == os.path.realpath(str(target))

    def test_two_roots_second_matches(self, tmp_path, monkeypatch):
        a_root = tmp_path / "root_a"
        b_root = tmp_path / "root_b"
        a_root.mkdir()
        b_root.mkdir()
        monkeypatch.setattr(
            al, "ALLOWED_EVIDENCE_DIRS", (str(a_root), str(b_root)),
        )
        target = b_root / "y"
        target.mkdir()
        result = al.validate_evidence_dir(str(target))
        assert result == os.path.realpath(str(target))

    def test_invalid_root_skipped_gracefully(self, tmp_path, monkeypatch):
        good = tmp_path / "good"
        good.mkdir()
        # Mix in non-string and empty entries; these must be skipped
        # rather than crashing the validator.
        monkeypatch.setattr(
            al, "ALLOWED_EVIDENCE_DIRS",
            (None, "", 42, str(good)),  # type: ignore[arg-type]
        )
        result = al.validate_evidence_dir(str(good))
        assert result == os.path.realpath(str(good))


# ===========================================================================
# D. Cross-platform path quirks
# ===========================================================================
class TestPathNormalisation:
    def test_repeated_slashes_handled(self, tmp_path):
        # POSIX: //tmp//foo and /tmp/foo are equivalent; on Windows the
        # backslash equivalent is normalised by os.path.normpath.
        sub = tmp_path / "doubled"
        sub.mkdir()
        weird = str(sub).replace(os.sep, os.sep + os.sep)
        # Some implementations preserve //, others collapse — either
        # way, normpath should yield a valid existing directory.
        result = al.validate_evidence_dir(weird)
        assert os.path.isdir(result)

    def test_trailing_separator_handled(self, tmp_path):
        sub = tmp_path / "with_trailing"
        sub.mkdir()
        result = al.validate_evidence_dir(str(sub) + os.sep)
        assert result == os.path.realpath(str(sub))

    def test_backslash_traversal_rejected(self):
        # Even on POSIX, a path with backslash-separated `..` must be
        # treated as a traversal attempt because the splitter folds
        # backslashes.
        with pytest.raises(ValueError, match="parent-directory traversal"):
            al.validate_evidence_dir("/evidence\\..\\etc")


@pytest.mark.skipif(not _IS_WINDOWS, reason="Windows-specific")
class TestWindowsSpecifics:
    def test_windows_drive_letter_works(self, tmp_path):
        # tmp_path on Windows already has C:\ prefix; just confirm the
        # validator handles it cleanly.
        result = al.validate_evidence_dir(str(tmp_path))
        assert result.startswith(("C:", "c:"))

    def test_windows_different_drive_rejected(
        self, tmp_path, monkeypatch,
    ):
        """An allowlist entry on a different drive must not be confused
        with a path on the current drive (commonpath raises ValueError
        across drives — the validator handles that)."""
        # Allowlist entry on a non-existent drive; even if the validator
        # ignores it for commonpath errors, it must reject the request
        # because no other root matches.
        monkeypatch.setattr(al, "ALLOWED_EVIDENCE_DIRS", (r"Z:\evidence",))
        with pytest.raises(ValueError, match="not inside any allowlisted"):
            al.validate_evidence_dir(str(tmp_path))


# ===========================================================================
# E. Integration — analyze_and_store + endpoint
# ===========================================================================
class TestAnalyzeAndStoreIntegration:
    def test_valid_dir_via_function(self, tmp_path):
        import elins_timeline_dashboard as etd
        out = etd.analyze_and_store(str(tmp_path), run_id="ok_run")
        assert "run_id" in out

    def test_invalid_dir_via_function_raises_value_error(
        self, tmp_path, empty_allowlist,
    ):
        import elins_timeline_dashboard as etd
        with pytest.raises(ValueError, match="evidence_dir_not_allowed"):
            etd.analyze_and_store(str(tmp_path), run_id="bad_run")

    def test_metadata_evidence_dir_is_normalized_realpath(self, tmp_path):
        import elins_timeline_dashboard as etd
        out = etd.analyze_and_store(str(tmp_path), run_id="meta_run")
        loaded = ep.load_comparison_result(out["run_id"])
        # metadata.evidence_dir reflects the canonical realpath form.
        assert loaded["metadata"]["evidence_dir"] == os.path.realpath(
            str(tmp_path),
        )

    def test_pairs_input_skips_validation(self):
        """A list of pairs (non-string input) must not trip the
        evidence-dir validator at all."""
        import elins_timeline_dashboard as etd
        from elins_regression_single_party import Timeline, TimePoint
        from elins_regression_economic_coercion import (
            TimelineEconomic, TimePointEconomic,
        )
        sp = Timeline(timeline_id="sp_z", points=(TimePoint(
            t="t0",
            regime_competition=0.5, autocratization=0.5,
            repression_index=0.5, digital_repression=0.5,
            perceived_threat=0.5, fear_signal=0.5,
            dissent_capacity=0.5, normative_constraint=0.5,
            support_buffer=0.5,
        ),))
        ec = TimelineEconomic(timeline_id="ec_z", points=(
            TimePointEconomic(
                t="t0",
                economic_pressure=0.5, material_insecurity=0.5,
                state_coercion=0.5, compliance_signal=0.5,
                resistance_capacity=0.5, support_buffer=0.5,
            ),))
        out = etd.analyze_and_store([(sp, ec)], run_id="pair_skips")
        # Should succeed with no allowlist interaction.
        loaded = ep.load_comparison_result(out["run_id"])
        assert loaded["metadata"]["source"] == "single"
        assert loaded["metadata"]["evidence_dir"] is None


class TestEndpointIntegration:
    _PATH = "/elins/regression/analyze_directory_and_store"

    def test_valid_dir_endpoint_returns_200(
        self, client, app_module, tmp_path,
    ):
        sid = _make_user_session(app_module)
        resp = client.post(
            self._PATH,
            json={"run_id": "ok_endpoint", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_invalid_dir_endpoint_returns_400(
        self, client, app_module, tmp_path, empty_allowlist,
    ):
        sid = _make_user_session(app_module)
        resp = client.post(
            self._PATH,
            json={"run_id": "bad_endpoint", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        assert resp.status_code == 400
        assert "evidence_dir_not_allowed" in str(resp.json())

    def test_metadata_endpoint_shows_normalized_evidence_dir(
        self, client, app_module, tmp_path,
    ):
        sid = _make_user_session(app_module)
        client.post(
            self._PATH,
            json={"run_id": "meta_endpoint", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        meta = client.get(
            "/elins/regression/run/meta_endpoint/metadata",
            headers=_auth(sid),
        ).json()
        assert meta["metadata"]["evidence_dir"] == os.path.realpath(
            str(tmp_path),
        )

    def test_listing_shows_normalized_evidence_dir(
        self, client, app_module, tmp_path,
    ):
        sid = _make_user_session(app_module)
        client.post(
            self._PATH,
            json={"run_id": "list_endpoint", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        body = client.get(
            "/elins/regression/runs", headers=_auth(sid),
        ).json()
        row = next(r for r in body if r["run_id"] == "list_endpoint")
        assert row["evidence_dir"] == os.path.realpath(str(tmp_path))

    def test_composite_endpoint_works_with_allowed_dir(
        self, client, app_module, tmp_path,
    ):
        sid = _make_user_session(app_module)
        client.post(
            self._PATH,
            json={"run_id": "composite_dir", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        body = client.post(
            "/elins/regression/run/composite",
            json={"run_ids": ["composite_dir"]}, headers=_auth(sid),
        ).json()
        assert body["metadata"][0]["source"] == "directory"
        assert body["metadata"][0]["evidence_dir"] == os.path.realpath(
            str(tmp_path),
        )

    def test_endpoint_relative_path_returns_400(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        resp = client.post(
            self._PATH,
            json={"run_id": "rel_run", "path": "relative/dir"},
            headers=_auth(sid),
        )
        # Either app.py's existence check returns 404 first (path doesn't
        # exist as relative), OR the validator returns 400. Either way,
        # not 200.
        assert resp.status_code != 200

    def test_endpoint_traversal_returns_400(
        self, client, app_module, tmp_path,
    ):
        sid = _make_user_session(app_module)
        bad = os.path.join(str(tmp_path), "..", "outside")
        # Create the outside path so the directory existence check
        # passes; the validator should still reject due to ``..``.
        os.makedirs(bad, exist_ok=True)
        resp = client.post(
            self._PATH,
            json={"run_id": "trav_run", "path": bad},
            headers=_auth(sid),
        )
        assert resp.status_code == 400
        assert "evidence_dir_not_allowed" in str(resp.json())


# ===========================================================================
# F. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_validate_evidence_dir_callable(self):
        assert callable(al.validate_evidence_dir)

    def test_allowed_evidence_dirs_is_tuple(self):
        # After autouse-fixture extension; type still tuple.
        assert isinstance(al.ALLOWED_EVIDENCE_DIRS, tuple)

    def test_default_allowlist_present_after_extension(self):
        # The autouse fixture extends the default; confirm both default
        # and tmpdir entry are present.
        assert "/evidence" in al.ALLOWED_EVIDENCE_DIRS
        assert "/var/evidence" in al.ALLOWED_EVIDENCE_DIRS
        assert tempfile.gettempdir() in al.ALLOWED_EVIDENCE_DIRS

    def test_error_prefix_constant_locked(self):
        assert al._ERROR_PREFIX == "evidence_dir_not_allowed"


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(al)

    def _code_only(self) -> str:
        import re as _re
        src = self._src()
        src = _re.sub(r'"""[\s\S]*?"""', "", src)
        src = _re.sub(r"'''[\s\S]*?'''", "", src)
        return src

    def test_no_logging(self):
        src = self._code_only()
        for forbidden in ("logging.", "logger.", "print("):
            assert forbidden not in src

    def test_no_network(self):
        src = self._code_only()
        for forbidden in ("import urllib", "import http",
                          "import requests", "import socket"):
            assert forbidden not in src

    def test_no_randomness(self):
        src = self._code_only()
        for forbidden in ("import random", "from random",
                          "import secrets", "from secrets",
                          "uuid."):
            assert forbidden not in src

    def test_no_llm_imports(self):
        src = self._code_only()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_only_os_path_io(self):
        """Validator may stat the filesystem (os.path.* helpers) but
        must never read or write file CONTENTS."""
        src = self._code_only()
        for forbidden in ("open(", "json.load", "json.dump",
                          "Path(", ".read_text", ".write_text"):
            assert forbidden not in src

    def test_no_subprocess_or_eval(self):
        src = self._code_only()
        for forbidden in ("subprocess", "exec(", "eval("):
            assert forbidden not in src

    def test_no_analytic_or_persistence_imports(self):
        """Allowlist module must be free of cross-unit dependencies —
        it's a pure security helper."""
        src = self._code_only()
        for forbidden in (
            "elins_persistence", "elins_run_diff", "elins_run_drift",
            "elins_run_summary", "elins_run_composite",
            "elins_timeline_dashboard",
        ):
            assert forbidden not in src
