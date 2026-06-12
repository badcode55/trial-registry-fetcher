#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


SYNC_PATHS = [
    ".gitignore",
    "README.md",
    "requirements.txt",
    "examples",
    "output/.gitkeep",
    "scripts/run_example.bat",
    "scripts/run_example.command",
    "scripts/run_example.sh",
    "scripts/sync_dev_to_main.bat",
    "scripts/sync_dev_to_main.py",
    "scripts/sync_dev_to_main.sh",
    "trial_registry",
    "umin_ctr_scraper.py",
]

DEV_ONLY_PATHS = [
    "PROJECT_PLAN.md",
    "tests",
    "跨注册库JSON canonical protocol JSON 设计.md",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync user-facing files from dev to main without copying dev-only docs/tests."
    )
    parser.add_argument("--source", default="dev", help="Source branch. Default: dev")
    parser.add_argument("--target", default="main", help="Target branch. Default: main")
    parser.add_argument("--push", action="store_true", help="Push target branch to origin after commit.")
    parser.add_argument(
        "--message",
        default="Sync user-facing files from dev",
        help="Commit message for the target branch.",
    )
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    original_branch = git(["branch", "--show-current"], repo).strip()
    if original_branch != args.source:
        raise SystemExit(f"Please run this from {args.source!r}; current branch is {original_branch!r}.")

    if git(["status", "--short", "--untracked-files=no"], repo).strip():
        raise SystemExit("Tracked files are not clean. Commit or stash changes before syncing.")

    try:
        git(["switch", args.target], repo)
        remove_dev_only_paths(repo)
        restore_paths_from_branch(repo, args.source, SYNC_PATHS)
        remove_generated_output(repo)
        stage_sync_changes(repo)
        if git(["diff", "--cached", "--quiet"], repo, check=False).returncode == 0:
            print(f"No user-facing changes to sync into {args.target}.")
        else:
            git(["commit", "-m", args.message], repo)
            print(f"Committed user-facing sync on {args.target}.")

        if args.push:
            git(["push", "origin", args.target], repo)
            print(f"Pushed {args.target} to origin.")
    finally:
        git(["switch", original_branch], repo, check=False)

    return 0


def restore_paths_from_branch(repo: Path, branch: str, paths: list[str]) -> None:
    for rel_path in paths:
        if path_exists_in_branch(repo, branch, rel_path):
            git(["checkout", branch, "--", rel_path], repo)
        else:
            remove_path(repo / rel_path)


def remove_dev_only_paths(repo: Path) -> None:
    for rel_path in DEV_ONLY_PATHS:
        remove_path(repo / rel_path)


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def remove_generated_output(repo: Path) -> None:
    output_dir = repo / "output"
    output_dir.mkdir(exist_ok=True)
    for child in output_dir.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def stage_sync_changes(repo: Path) -> None:
    # 只暂存精选同步路径，避免把使用者本地未跟踪笔记或临时文件带入 main。
    # Stage only the curated sync set so local untracked notes/temp files never leak into main.
    for rel_path in SYNC_PATHS:
        if (repo / rel_path).exists() or is_tracked(repo, rel_path):
            git(["add", "-A", "--", rel_path], repo)
    for rel_path in DEV_ONLY_PATHS:
        if (repo / rel_path).exists() or is_tracked(repo, rel_path):
            git(["add", "-A", "--", rel_path], repo)


def is_tracked(repo: Path, rel_path: str) -> bool:
    return git(["ls-files", "--error-unmatch", rel_path], repo, check=False).returncode == 0


def path_exists_in_branch(repo: Path, branch: str, rel_path: str) -> bool:
    return git(["cat-file", "-e", f"{branch}:{rel_path}"], repo, check=False).returncode == 0


def git(args: list[str], repo: Path, *, check: bool = True):
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise SystemExit(result.stderr.strip() or result.stdout.strip())
    return result.stdout if check else result


if __name__ == "__main__":
    raise SystemExit(main())
