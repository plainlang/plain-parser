from plain_parser import project


def test_discover_files_before_subdirectories(tmp_path):
    (tmp_path / "tests" / "a").mkdir(parents=True)
    (tmp_path / "tests" / "z.plain").write_text("x")
    (tmp_path / "tests" / "a" / "b.plain").write_text("x")
    (tmp_path / "tests" / "notes.md").write_text("x")
    found = project.discover_test_plain_files(["tests"], str(tmp_path))
    assert [name for _, name in found] == ["tests/z.plain", "tests/a/b.plain"]


def test_discover_absolute_folder(tmp_path):
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "x.plain").write_text("x")
    found = project.discover_test_plain_files([str(tmp_path / "t")], str(tmp_path))
    assert [name for _, name in found] == ["t/x.plain"]
