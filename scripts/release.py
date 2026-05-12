"""Bump version, commit, tag, and push a new release.

Updates three files:
  pyproject.toml          version = "x.y.z"
  gui/__version__.py      VERSION = "x.y.z"
  gui/frontend/package.json   "version": "x.y.z"

Usage:
    python scripts/release.py 0.2.0
    python scripts/release.py 0.2.0 --message "adds data export"
    python scripts/release.py 0.1.9 --force          # overwrite existing tag
    python scripts/release.py 0.2.0 --dry-run        # preview only
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT    = ROOT / "pyproject.toml"
VERSION_PY   = ROOT / "gui" / "__version__.py"
PACKAGE_JSON = ROOT / "gui" / "frontend" / "package.json"

VERSION_FILES = [PYPROJECT, VERSION_PY, PACKAGE_JSON]

# ── Helpers ────────────────────────────────────────────────────────────────────

def die(msg: str) -> None:
	print(f"ERROR: {msg}", file=sys.stderr)
	sys.exit(1)


def git(*args: str, capture: bool = False, cwd: Path = ROOT) -> subprocess.CompletedProcess:
	return subprocess.run(
		["git", *args],
		capture_output=capture,
		text=True,
		cwd=cwd,
	)


def git_out(*args: str) -> str:
	return git(*args, capture=True).stdout.strip()


def parse_semver(raw: str) -> tuple[tuple[int, int, int], str]:
	"""Parse 'x.y.z' or 'vx.y.z'. Returns ((x,y,z), 'x.y.z')."""
	v = raw.lstrip("v")
	m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", v)
	if not m:
		die(f"'{raw}' is not a valid version — expected x.y.z")
	return (int(m[1]), int(m[2]), int(m[3])), v


def read_current_version() -> str:
	text = VERSION_PY.read_text()
	m = re.search(r'VERSION = "([^"]+)"', text)
	if not m:
		die(f"Could not parse current version from {VERSION_PY}")
	return m.group(1)


def tag_exists(tag: str) -> bool:
	return bool(git_out("tag", "--list", tag))


def remote_exists() -> bool:
	return bool(git_out("remote"))


def current_branch() -> str:
	return git_out("branch", "--show-current")


def staged_files() -> set[str]:
	"""Files currently in the index (staged for commit)."""
	out = git_out("diff", "--cached", "--name-only")
	return set(out.splitlines()) if out else set()


def unstaged_changes() -> str:
	"""Returns porcelain status of unstaged/untracked changes, or empty string."""
	out = git_out("status", "--porcelain")
	# filter out staged-only lines (lines starting with index column change)
	lines = [l for l in out.splitlines() if not l.startswith("M ") or True]
	return "\n".join(l for l in out.splitlines() if l[1] != " " or l[0] == "?")


# ── File updaters ──────────────────────────────────────────────────────────────

def update_pyproject(new_ver: str) -> None:
	text = PYPROJECT.read_text()
	new_text, n = re.subn(
		r'^(version\s*=\s*")[^"]+(")',
		rf"\g<1>{new_ver}\2",
		text,
		flags=re.MULTILINE,
	)
	if n == 0:
		die(f"Could not find version line in {PYPROJECT}")
	PYPROJECT.write_text(new_text)


def update_version_py(new_ver: str) -> None:
	text = VERSION_PY.read_text()
	new_text, n = re.subn(r'VERSION = "[^"]+"', f'VERSION = "{new_ver}"', text)
	if n == 0:
		die(f"Could not find VERSION in {VERSION_PY}")
	VERSION_PY.write_text(new_text)


def update_package_json(new_ver: str) -> None:
	text = PACKAGE_JSON.read_text()
	# Only replace the top-level "version" key (first occurrence)
	new_text, n = re.subn(
		r'^(\s*"version"\s*:\s*")[^"]+(")',
		rf"\g<1>{new_ver}\2",
		text,
		count=1,
		flags=re.MULTILINE,
	)
	if n == 0:
		die(f"Could not find version in {PACKAGE_JSON}")
	PACKAGE_JSON.write_text(new_text)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
	parser = argparse.ArgumentParser(
		description="Bump version, commit, tag, and push a release.",
		formatter_class=argparse.RawDescriptionHelpFormatter,
		epilog=__doc__,
	)
	parser.add_argument("version", help="New version, e.g. 0.2.0 or v0.2.0")
	parser.add_argument(
		"--message", "-m", default=None,
		help="Commit and tag message (default: 'bump to version vX.Y.Z')",
	)
	parser.add_argument(
		"--force", "-f", action="store_true",
		help="Overwrite existing tag and allow version downgrades",
	)
	parser.add_argument(
		"--no-push", action="store_true",
		help="Commit and tag locally, but do not push to remote",
	)
	parser.add_argument(
		"--dry-run", action="store_true",
		help="Show what would happen without making any changes",
	)
	args = parser.parse_args()

	new_tuple, new_ver = parse_semver(args.version)
	tag = f"v{new_ver}"
	cur_ver = read_current_version()
	cur_tuple, _ = parse_semver(cur_ver)
	message = args.message or f"bump to version v{new_ver}"
	dry = args.dry_run

	# ── Header ────────────────────────────────────────────────────────────
	print(f"  Current : v{cur_ver}")
	print(f"  New     : v{new_ver}")
	print(f"  Tag     : {tag}")
	print(f"  Message : {message}")
	if dry:
		print("  Mode    : DRY RUN")
	elif args.no_push:
		print("  Mode    : local only (--no-push)")
	print()

	# ── Validations ───────────────────────────────────────────────────────

	# Force confirmation
	if args.force and not dry:
		reasons = []
		if new_tuple < cur_tuple:
			reasons.append(f"downgrade from v{cur_ver} to v{new_ver}")
		elif new_tuple == cur_tuple:
			reasons.append(f"re-release of existing version v{new_ver}")
		if tag_exists(tag):
			reasons.append(f"overwrite existing tag {tag}")
		reason_str = " and ".join(reasons) if reasons else "force flag is set"
		print(f"WARNING: --force will {reason_str}.")
		if not args.no_push and remote_exists():
			print("         This will force-push the tag to the remote.")
		if not _confirm("Proceed?"):
			sys.exit("Aborted.")
		print()

	# Version ordering
	if new_tuple < cur_tuple and not args.force:
		die(
			f"v{new_ver} is older than current v{cur_ver}.\n"
			"       Use --force to allow a downgrade."
		)
	if new_tuple == cur_tuple and not args.force:
		die(
			f"v{new_ver} is the same as the current version.\n"
			"       Use --force to re-tag the current version."
		)

	# Existing tag
	if tag_exists(tag) and not args.force:
		die(
			f"Tag {tag} already exists.\n"
			"       Use --force to overwrite it."
		)

	# Branch
	branch = current_branch()
	if branch != "main":
		print(f"WARNING: You are on branch '{branch}', not 'main'.")
		if not _confirm("Continue?"):
			sys.exit("Aborted.")

	# Staged changes that aren't the version files
	rel_version_files = {str(f.relative_to(ROOT)) for f in VERSION_FILES}
	extra_staged = staged_files() - rel_version_files
	if extra_staged:
		print("WARNING: These staged changes will be included in the version commit:")
		for f in sorted(extra_staged):
			print(f"           {f}")
		if not _confirm("Include them?"):
			sys.exit("Aborted. Run 'git restore --staged .' to unstage, then retry.")

	# Uncommitted (unstaged) changes
	status = git_out("status", "--porcelain")
	unstaged = [
		l for l in status.splitlines()
		if l[1] in ("M", "D", "?")           # modified/deleted/untracked in worktree
		and l[3:] not in rel_version_files    # not one of the files we're about to write
	]
	if unstaged:
		print("WARNING: Uncommitted changes exist (not included in the release commit):")
		for l in unstaged:
			print(f"           {l}")
		if not _confirm("Continue anyway?"):
			sys.exit("Aborted.")

	# ── Dry-run exit ──────────────────────────────────────────────────────
	if dry:
		print("Would update:")
		for f in VERSION_FILES:
			print(f"  {f.relative_to(ROOT)}")
		print(f"Would commit:  \"{message}\"")
		action = "force-create" if args.force else "create"
		print(f"Would tag:     {action} {tag}")
		if args.no_push:
			print("Would skip push: --no-push")
		elif remote_exists():
			push_flags = " --force" if args.force else ""
			print(f"Would push:    origin/{branch}{push_flags}")
			print(f"Would push:    tag {tag}{push_flags}")
		else:
			print("Would skip push: no remote configured")
		return

	# ── Update files ──────────────────────────────────────────────────────
	print("Updating version files...")
	update_pyproject(new_ver)
	update_version_py(new_ver)
	update_package_json(new_ver)
	for f in VERSION_FILES:
		print(f"  ✓ {f.relative_to(ROOT)}")

	# ── Commit ────────────────────────────────────────────────────────────
	print("\nCommitting...")
	git("add", *[str(f) for f in VERSION_FILES])
	result = git("commit", "-m", message)
	if result.returncode != 0:
		die("git commit failed — see output above.")

	# ── Tag ───────────────────────────────────────────────────────────────
	print(f"\nTagging {tag}...")
	tag_args = ["tag", "-a", tag, "-m", message]
	if args.force:
		tag_args.append("--force")
	result = git(*tag_args)
	if result.returncode != 0:
		die("git tag failed — see output above.")

	# ── Push ──────────────────────────────────────────────────────────────
	force_flag = " --force" if args.force else ""

	if args.no_push:
		print(f"\n✓  v{new_ver} committed and tagged locally.")
		print(f"   To push when ready:")
		print(f"     git push origin {branch}{force_flag}")
		print(f"     git push origin {tag}{force_flag}")
		return

	if not remote_exists():
		print("\nNo remote configured — skipping push.")
		print(f"\n✓  v{new_ver} committed and tagged locally.")
		return

	print(f"\nPushing to origin/{branch}...")
	result = git("push", "origin", branch, *( ["--force"] if args.force else []))
	if result.returncode != 0:
		die(
			f"git push failed.\n"
			"       The version files and tag were committed locally. Fix the push issue and run:\n"
			f"         git push origin {branch}{force_flag}\n"
			f"         git push origin {tag}{force_flag}"
		)

	print(f"Pushing tag {tag}...")
	result = git("push", "origin", tag, *(["--force"] if args.force else []))
	if result.returncode != 0:
		die(
			f"Tag push failed.\n"
			"       The commit was pushed. Fix the issue and run:\n"
			f"         git push origin {tag}{force_flag}"
		)

	print(f"\n✓  Released v{new_ver}")


def _confirm(prompt: str) -> bool:
	try:
		return input(f"{prompt} [y/N] ").strip().lower() == "y"
	except (EOFError, KeyboardInterrupt):
		return False


if __name__ == "__main__":
	main()
