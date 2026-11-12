"""The installer's own promises: it finds the newest hython, never overwrites local.toml, and --check changes nothing."""
import importlib.util
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cvcops_install", ROOT / "tools" / "install.py")
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


def fake_houdini(root, *versions):
    for v in versions:
        exe = root / f"Houdini {v}" / "bin" / "hython.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"")


def test_newest_houdini_comes_first(tmp_path):
    fake_houdini(tmp_path, "21.0.773", "22.0.90", "22.0.492", "22.0.368")
    found = install.hython_candidates(platform="win32", env={}, roots=[tmp_path])
    assert [install.version_key(p) for p in found] == [(22, 0, 492), (22, 0, 368), (22, 0, 90), (21, 0, 773)]


def test_no_houdini_is_not_an_error(tmp_path):
    assert install.hython_candidates(platform="win32", env={}, roots=[tmp_path]) == []


def checkout(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "cvcops"\n', encoding="utf-8")
    (tmp_path / "local.toml.example").write_text((ROOT / "local.toml.example").read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_local_toml_is_plain_utf8_and_parses(tmp_path):
    root = checkout(tmp_path)
    assert install.write_local_toml(root, Path("C:/Program Files/Side Effects Software/Houdini 22.0.492/bin/hython.exe"))
    raw = (root / "local.toml").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "a byte-order mark makes tomllib refuse the file (FACTS K18)"
    assert tomllib.loads(raw.decode("utf-8"))["hython"].endswith("Houdini 22.0.492/bin/hython.exe")


def test_an_existing_local_toml_is_never_overwritten(tmp_path):
    root = checkout(tmp_path)
    (root / "local.toml").write_text('hython = "mine"\n', encoding="utf-8")
    assert install.write_local_toml(root, Path("/opt/hfs22.0.492/bin/hython")) is False
    assert (root / "local.toml").read_text(encoding="utf-8") == 'hython = "mine"\n'


def test_check_changes_nothing(tmp_path):
    root = checkout(tmp_path)
    before = sorted(p.name for p in root.iterdir())
    assert install.main(["--check", "--no-houdini"], root=root) in (0, 3)      # 3 only where uv is absent
    assert sorted(p.name for p in root.iterdir()) == before


def test_outside_a_checkout_it_knows(tmp_path):
    assert install.in_checkout(ROOT) and not install.in_checkout(tmp_path)


# ---- REL.release.install: the release's promises ----------------------------------------------------------------
def _install():
    import importlib.util
    spec = importlib.util.spec_from_file_location("cvcops_install", ROOT / "tools" / "install.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_package_folder_uses_the_houdini_variable_first():
    m = _install()
    got = m.packages_folder(env={"HOUDINI_USER_PREF_DIR": "C:/prefs/houdini__HVER__"}, hython=None)
    assert got.as_posix() == "C:/prefs/houdini22.0/packages"


def test_the_package_folder_never_falls_back_to_home(monkeypatch):
    m = _install()
    monkeypatch.setattr(m, "documents_folder", lambda: m.Path("D:/Users/someone/Documents"))
    got = m.packages_folder(env={}, hython=None)
    assert got.as_posix() == "D:/Users/someone/Documents/houdini22.0/packages"
    assert "HOME" not in got.as_posix()


def test_packages_argument_wins(tmp_path):
    m = _install()
    rc = m.main(["--check", "--packages", str(tmp_path), "--no-selftest", "--no-houdini"])
    assert rc == 0
    assert not any(tmp_path.iterdir())


def test_check_writes_nothing(tmp_path, monkeypatch):
    m = _install()
    before = sorted(p.name for p in ROOT.iterdir())
    rc = m.main(["--check", "--packages", str(tmp_path), "--no-selftest"])
    assert rc == 0
    assert sorted(p.name for p in ROOT.iterdir()) == before


def test_the_asset_is_rebuilt_only_when_the_stamp_differs():
    m = _install()
    built, matches, recorded, current = m.build_state(ROOT)
    assert built is True
    assert recorded == current, "the committed asset should match the tree it was built from"
    assert matches is True


def test_a_downloaded_installer_clones_the_release_tag(monkeypatch, tmp_path):
    m = _install()
    calls = []

    class Result:
        returncode = 0

    monkeypatch.setattr(m, "in_checkout", lambda root=None: False)
    monkeypatch.setattr(m, "shutil", type("S", (), {"which": staticmethod(lambda name: "git")}))
    monkeypatch.setattr(m, "run", lambda cmd, cwd, quiet=False: calls.append(cmd) or Result())
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: Result())
    monkeypatch.chdir(tmp_path)
    m.main([])
    assert calls and calls[0][:5] == ["git", "clone", "--depth", "1", "--branch"]
    assert m.RELEASE_TAG in calls[0]
