"""Clean Linux Docker bind directories must be owned by the installing host user."""

from scripts import setup


def test_existing_environment_still_prepares_bind_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("PRESERVE_THIS=existing\n")
    setup.main()
    assert (tmp_path / "data").is_dir()
    assert (tmp_path / "artifacts").is_dir()
    assert (tmp_path / ".env").read_text() == "PRESERVE_THIS=existing\n"
