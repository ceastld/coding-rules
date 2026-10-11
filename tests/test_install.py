import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


INSTALLER = Path(__file__).resolve().parent.parent / "scripts" / "install.py"


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = self.root / "repository"
        self.project = self.root / "project"
        self.project.mkdir()
        scripts = self.repository / "scripts"
        scripts.mkdir(parents=True)
        self.installer = scripts / "install.py"
        shutil.copyfile(INSTALLER, self.installer)

    def skill(self, name="alpha"):
        directory = self.repository / "skills" / name
        (directory / "references").mkdir(parents=True)
        (directory / "SKILL.md").write_text("See [guide](references/guide.md).\n", encoding="utf-8")
        (directory / "references" / "guide.md").write_text("Guide\n", encoding="utf-8")
        (directory / "references" / "sample.bin").write_bytes(bytes(range(256)))
        (directory / "empty").mkdir()
        return directory

    def run_install(self, *names, project=None):
        return subprocess.run(
            [sys.executable, "-B", str(self.installer), "--project", str(project or self.project), "--skill", *names],
            cwd=self.root, capture_output=True,
        )

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))

    def target(self, name="alpha"):
        return self.project / ".agents" / "skills" / name

    def installer_module(self):
        spec = importlib.util.spec_from_file_location("test_installer", self.installer)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_copies_complete_skill_and_relative_references_from_repository(self):
        source = self.skill()
        self.assert_success(self.run_install("alpha"))
        target = self.target()
        for original in source.rglob("*"):
            copied = target / original.relative_to(source)
            self.assertEqual(copied.is_dir(), original.is_dir())
            if original.is_file():
                self.assertEqual(copied.read_bytes(), original.read_bytes())
        self.assertFalse((self.project / "AGENTS.md").exists())

    def test_installs_multiple_skills(self):
        self.skill("alpha")
        self.skill("beta")
        self.assert_success(self.run_install("alpha", "beta"))
        self.assertTrue((self.target("alpha") / "SKILL.md").is_file())
        self.assertTrue((self.target("beta") / "SKILL.md").is_file())
        self.assertEqual(sorted(path.name for path in self.target().parent.iterdir()), ["alpha", "beta"])

    def test_all_selections_preflight_before_writing(self):
        self.skill()
        for invalid in ("missing", "no-skill-file"):
            with self.subTest(invalid=invalid):
                (self.repository / "skills" / "no-skill-file").mkdir(exist_ok=True)
                self.assertNotEqual(self.run_install("alpha", invalid).returncode, 0)
                self.assertFalse((self.project / ".agents").exists())

    def test_different_existing_skill_is_preserved_without_partial_install(self):
        self.skill("alpha")
        self.skill("beta")
        existing = self.target("beta")
        existing.mkdir(parents=True)
        sentinel = existing / "SKILL.md"
        sentinel.write_bytes(b"User's existing skill\n")
        os.utime(sentinel, ns=(1234567890000000000, 1234567890000000000))
        before = sentinel.stat().st_mtime_ns
        self.assertNotEqual(self.run_install("alpha", "beta").returncode, 0)
        self.assertFalse(self.target("alpha").exists())
        self.assertEqual(sentinel.read_bytes(), b"User's existing skill\n")
        self.assertEqual(sentinel.stat().st_mtime_ns, before)

    def test_identical_reinstall_does_not_rewrite_files_or_directories(self):
        self.skill()
        self.assert_success(self.run_install("alpha"))
        paths = [self.target(), *self.target().rglob("*")]
        for path in paths:
            os.utime(path, ns=(1234567890000000000, 1234567890000000000))
        before = {path: path.stat().st_mtime_ns for path in paths}
        self.assert_success(self.run_install("alpha", "alpha"))
        self.assertEqual({path: path.stat().st_mtime_ns for path in paths}, before)

    def test_malicious_skill_names_are_rejected_without_writes(self):
        self.skill()
        for name in ("..", ".", "../alpha", "alpha/child", "alpha\\child", "C:\\alpha", "/alpha", "NUL", "foo."):
            with self.subTest(name=name):
                self.assertNotEqual(self.run_install(name).returncode, 0)
                self.assertFalse((self.project / ".agents").exists())

    def test_staging_failure_leaves_no_partial_skills(self):
        self.skill("alpha")
        self.skill("beta")
        module = self.installer_module()
        copytree = module.shutil.copytree

        def fail_beta(source, destination, *args, **kwargs):
            if Path(source).name == "beta":
                raise OSError("模拟第二个 skill 复制失败")
            return copytree(source, destination, *args, **kwargs)

        with mock.patch.object(module.shutil, "copytree", side_effect=fail_beta):
            with self.assertRaises(OSError):
                module.install(self.project, ["alpha", "beta"])
        self.assertFalse((self.project / ".agents").exists())

    def test_later_rename_failure_rolls_back_new_skills(self):
        self.skill("alpha")
        self.skill("beta")
        module = self.installer_module()
        rename = Path.rename

        def fail_beta(path, destination):
            if destination.name == "beta":
                raise OSError("模拟第二个 skill 重命名失败")
            return rename(path, destination)

        with mock.patch.object(Path, "rename", autospec=True, side_effect=fail_beta):
            with self.assertRaises(OSError):
                module.install(self.project, ["alpha", "beta"])
        self.assertFalse((self.project / ".agents").exists())

    def symlink(self, link, destination):
        try:
            link.symlink_to(destination, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            if os.name != "nt":
                self.skipTest("当前环境不支持目录符号链接：" + str(error))
            # Windows junctions need no symlink privilege. Both ends stay within
            # this test's own temporary root; Python 3.9+ rmtree never follows them.
            for path in (link, destination):
                path.resolve().relative_to(self.root.resolve())
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(destination)], capture_output=True,
            )
            if result.returncode:
                self.skipTest("当前环境不支持目录符号链接或 junction")
            self.assertEqual(link.resolve(), destination.resolve())

    def test_target_parent_symlink_cannot_escape_project(self):
        self.skill()
        outside = self.root / "outside"
        outside.mkdir()
        sentinel = outside / "keep.txt"
        sentinel.write_bytes(b"keep")
        self.symlink(self.project / ".agents", outside)
        self.assertNotEqual(self.run_install("alpha").returncode, 0)
        self.assertEqual(list(outside.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_existing_skill_symlink_cannot_escape_project(self):
        self.skill()
        outside = self.root / "outside"
        outside.mkdir()
        self.target().parent.mkdir(parents=True)
        self.symlink(self.target(), outside)
        self.assertNotEqual(self.run_install("alpha").returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

    def test_nonexistent_project_is_not_created(self):
        self.skill()
        missing = self.root / "missing-project"
        self.assertNotEqual(self.run_install("alpha", project=missing).returncode, 0)
        self.assertFalse(missing.exists())

    def test_project_and_skill_options_are_required(self):
        for args in ([], ["--project", str(self.project)], ["--skill", "alpha"]):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, "-B", str(self.installer), *args], capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertFalse((self.project / ".agents").exists())


if __name__ == "__main__":
    unittest.main()
