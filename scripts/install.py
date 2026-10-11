#!/usr/bin/env python3
"""Copy selected repository skills into an existing project's .agents/skills."""

import argparse
import hashlib
import re
import shutil
import sys
import tempfile
from pathlib import Path


SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {
    prefix + str(number) for prefix in ("COM", "LPT") for number in range(1, 10)
}


class InstallError(Exception):
    pass


def inside(path, root):
    try:
        path.resolve().relative_to(root.resolve())
    except (ValueError, OSError, RuntimeError):
        raise InstallError("路径逃出项目或无法解析：" + str(path))


def manifest(directory, boundary, source=False):
    """Include empty directories and file bytes; ignore timestamps and permissions."""
    inside(directory, boundary)
    if source and directory.is_symlink():
        raise InstallError("源 skill 不得包含符号链接：" + str(directory))
    result = {}
    for path in sorted(directory.rglob("*")):
        inside(path, boundary)
        if path.is_symlink():
            raise InstallError("skill 不得包含符号链接：" + str(path))
        relative = path.relative_to(directory).as_posix()
        if path.is_dir():
            result[relative] = ("directory",)
        elif path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            result[relative] = ("file", digest.digest())
        else:
            raise InstallError("skill 包含不支持的文件：" + str(path))
    return result


def install(project, names):
    project = Path(project).expanduser().resolve()
    if not project.is_dir():
        raise InstallError("--project 必须是已存在的项目目录：" + str(project))
    base = project / ".agents" / "skills"
    inside(base, project)
    pending = []
    unchanged = []
    for name in dict.fromkeys(names):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name) or name.upper() in RESERVED_NAMES:
            raise InstallError("非法 skill 名称：" + name)
        source = SKILLS_ROOT / name
        if not source.is_dir() or not (source / "SKILL.md").is_file():
            raise InstallError("源 skill 不存在或缺少 SKILL.md：" + name)
        expected = manifest(source, SKILLS_ROOT, source=True)
        destination = base / name
        inside(destination, project)
        if destination.exists() or destination.is_symlink():
            if not destination.is_dir() or manifest(destination, project) != expected:
                raise InstallError("已有 skill 内容不同，未覆盖：" + str(destination))
            unchanged.append(name)
        else:
            pending.append((name, source, destination, expected))

    # Every selection has passed preflight before creating any project paths.
    if not pending:
        return [], unchanged
    created_parents = [path for path in (project / ".agents", base) if not path.exists()]
    stages = []
    installed = []
    try:
        base.mkdir(parents=True, exist_ok=True)
        inside(base, project)
        for name, source, destination, expected in pending:
            stage = Path(tempfile.mkdtemp(prefix="." + name + ".stage-", dir=base))
            stages.append(stage)
            shutil.copytree(source, stage, dirs_exist_ok=True)
            if manifest(stage, project) != expected:
                raise InstallError("复制期间源 skill 内容发生变化：" + name)
        for (_, _, destination, _), stage in zip(pending, stages):
            inside(destination, project)
            if destination.exists() or destination.is_symlink():
                raise InstallError("安装期间目标出现，未覆盖：" + str(destination))
            stage.rename(destination)
            installed.append(destination)
    except Exception:
        for destination in reversed(installed):
            inside(destination, project)
            shutil.rmtree(destination)
        raise
    finally:
        for stage in stages:
            if stage.exists():
                inside(stage, project)
                shutil.rmtree(stage)
        for path in reversed(created_parents):
            try:
                path.rmdir()  # Only remove directories that we created and left empty.
            except OSError:
                pass
    return [path.name for path in installed], unchanged


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="已存在的项目目录")
    parser.add_argument("--skill", required=True, nargs="+", help="skills/ 下的一个或多个目录名")
    args = parser.parse_args()
    try:
        installed, unchanged = install(args.project, args.skill)
    except (InstallError, OSError, RuntimeError) as error:
        print("安装失败：" + str(error), file=sys.stderr)
        return 1
    for name in installed:
        print("已安装：" + name)
    for name in unchanged:
        print("内容相同，保持原样：" + name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
