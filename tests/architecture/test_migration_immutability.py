"""NFR-05: merged migrations are append-only, verified against a committed checksum manifest."""
from pathlib import Path

import pytest

from scripts import migration_manifest as mm


def make_versions(directory: Path, files: dict[str, str]) -> Path:
    versions = directory / "versions"
    versions.mkdir(parents=True)
    for name, body in files.items():
        (versions / name).write_text(body)
    return directory


@pytest.mark.nfr05
def test_committed_migrations_match_the_manifest():
    problems = mm.verify(mm.load_manifest(), mm.current_files())
    assert problems == [], problems


@pytest.mark.nfr05
def test_editing_a_merged_migration_is_detected(tmp_path):
    root = make_versions(tmp_path, {"0001_a.py": "revision = '0001'\n"})
    manifest = mm.current_files(root)
    (root / "versions" / "0001_a.py").write_text("revision = '0001'\n# sneaky edit\n")
    problems = mm.verify(manifest, mm.current_files(root))
    assert any("modified in place" in p for p in problems)


@pytest.mark.nfr05
def test_deleting_or_renaming_a_merged_migration_is_detected(tmp_path):
    root = make_versions(tmp_path, {"0001_a.py": "x = 1\n"})
    manifest = mm.current_files(root)
    (root / "versions" / "0001_a.py").rename(root / "versions" / "0001_renamed.py")
    problems = mm.verify(manifest, mm.current_files(root))
    assert any("deleted or renamed" in p for p in problems)
    assert any("not registered" in p for p in problems)


@pytest.mark.nfr05
def test_replacing_a_migration_with_identical_name_but_new_content_is_detected(tmp_path):
    root = make_versions(tmp_path, {"0001_a.py": "x = 1\n"})
    manifest = mm.current_files(root)
    (root / "versions" / "0001_a.py").unlink()
    (root / "versions" / "0001_a.py").write_text("x = 2\n")
    assert mm.verify(manifest, mm.current_files(root))


@pytest.mark.nfr05
def test_appending_a_new_migration_is_allowed_and_requires_registration(tmp_path):
    root = make_versions(tmp_path, {"0001_a.py": "x = 1\n"})
    manifest = mm.current_files(root)
    (root / "versions" / "0002_b.py").write_text("x = 2\n")
    assert any("not registered" in p for p in mm.verify(manifest, mm.current_files(root)))
    updated = mm.append_new(manifest, mm.current_files(root))
    assert mm.verify(updated, mm.current_files(root)) == []
    assert updated["versions/0001_a.py"] == manifest["versions/0001_a.py"]


@pytest.mark.nfr05
def test_append_refuses_to_rewrite_existing_entries(tmp_path):
    root = make_versions(tmp_path, {"0001_a.py": "x = 1\n"})
    manifest = mm.current_files(root)
    (root / "versions" / "0001_a.py").write_text("x = 99\n")
    with pytest.raises(SystemExit):
        mm.append_new(manifest, mm.current_files(root))


@pytest.mark.nfr05
def test_manifest_cannot_be_rewritten_relative_to_the_target_branch():
    base = {"versions/0001_a.py": "aaa", "versions/0002_b.py": "bbb"}
    assert mm.verify_against_base(base, {**base, "versions/0003_c.py": "ccc"}) == []
    assert mm.verify_against_base(base, {"versions/0001_a.py": "aaa"})  # line removed
    assert mm.verify_against_base(base, {**base, "versions/0001_a.py": "tampered"})  # hash rewritten


@pytest.mark.nfr05
def test_line_endings_do_not_change_the_digest(tmp_path):
    lf, crlf = tmp_path / "lf.py", tmp_path / "crlf.py"
    lf.write_bytes(b"a = 1\nb = 2\n")
    crlf.write_bytes(b"a = 1\r\nb = 2\r\n")
    assert mm.file_digest(lf) == mm.file_digest(crlf)
