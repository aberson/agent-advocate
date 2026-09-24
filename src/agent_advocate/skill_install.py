"""User-scoped, checkout-bound Codex skill packages."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

from .store import ConflictError, RequestError, SetupError


SKILL_NAMES = (
    "assign-advocate",
    "status-inquisition",
    "coordination-cowbell",
    "model-mother",
    "advocate-wrap",
)
MANIFEST_NAME = "agent-advocate-install.json"
OWNER = "agent-advocate"
SCHEMA_VERSION = 1
_MANAGED_FILES = {"SKILL.md", MANIFEST_NAME}
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_STAGE_OWNER = ".agent-advocate-owner"
_LOCK_NAME = ".agent-advocate-install.lock"
_CONTRACT_DIGEST = re.compile(r"Shared contract SHA-256: `([0-9a-f]{64})`")


@contextlib.contextmanager
def _transaction_lock(parent: Path):
    """Serialize publishers and recovery; the OS releases this on process exit."""

    lock = parent / _LOCK_NAME
    if _is_link(lock) or (lock.exists() and not lock.is_file()):
        raise ConflictError(f"refusing unsafe skill install lock: {lock}")
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(lock, flags, 0o600)
    with os.fdopen(descriptor, "r+b") as handle:
        path_info = lock.lstat()
        file_info = os.fstat(handle.fileno())
        if (_is_link(lock) or not stat.S_ISREG(path_info.st_mode)
                or (path_info.st_dev, path_info.st_ino) != (file_info.st_dev, file_info.st_ino)):
            raise ConflictError(f"refusing unsafe skill install lock: {lock}")
        if handle.read() not in {b"", b"0"}:
            raise ConflictError(f"refusing foreign skill install lock: {lock}")
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _is_link(path: Path) -> bool:
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        return True
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _safe_directory(path: Path, *, create: bool) -> None:
    """Check each existing component before creating anything below the user home."""

    home = Path.home().absolute()
    if not path.is_relative_to(home):
        raise SetupError("user skill directory must be under the current user home")
    for part in (home, home / ".agents", home / ".agents" / "skills"):
        if not part.is_relative_to(path) and not path.is_relative_to(part):
            continue
        if create and not part.exists():
            try:
                part.mkdir(exist_ok=True)
            except FileExistsError:
                # Another writer may have put a non-directory at this path.
                pass
        if _is_link(part):
            raise SetupError(f"refusing linked user skill directory: {part}")
        if part.exists() and not part.is_dir():
            raise SetupError(f"user skill directory component is not a directory: {part}")
    if path.resolve(strict=False) != path:
        raise SetupError(f"user skill directory redirects outside its expected path: {path}")


def user_skill_dir(*, create: bool = False) -> Path:
    path = Path.home().absolute() / ".agents" / "skills"
    _safe_directory(path, create=create)
    return path


def _source_file(checkout: Path, name: str) -> Path:
    return checkout / ".agents" / "skills" / name / "SKILL.md"


def _source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_available(checkout: Path, name: str) -> bool:
    if not checkout.is_dir() or checkout.resolve(strict=False) != checkout:
        return False
    required = (
        checkout / "pyproject.toml",
        checkout / "uv.lock",
        checkout / "documentation" / "skill-contract.md",
        _source_file(checkout, name),
    )
    return all(path.is_file() and path.resolve(strict=False).is_relative_to(checkout) for path in required)


def _validate_source(value: str) -> Path:
    if not value.strip():
        raise RequestError("source checkout must not be empty")
    try:
        checkout = Path(value).expanduser().resolve(strict=True)
    except OSError as error:
        raise RequestError(f"source checkout is unavailable: {value}") from error
    if not checkout.is_dir():
        raise RequestError(f"source checkout is not a directory: {checkout}")
    for name in SKILL_NAMES:
        if not _source_available(checkout, name):
            raise RequestError(f"source checkout is missing files for {name}: {checkout}")
    return checkout


def _manifest(checkout: Path, name: str) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "owner": OWNER,
        "skill_name": name,
        "source_checkout": str(checkout),
        "source_sha256": _source_hash(_source_file(checkout, name)),
    }


def _wrapper(name: str, contract_sha256: str) -> str:
    return f"""---
name: {name}
description: Checkout-bound Agent Advocate {name} skill for explicitly named work.
---

This is an installed Agent Advocate wrapper. Before acting, read the adjacent
`{MANIFEST_NAME}` and validate `schema_version: 1`, `owner: agent-advocate`,
`skill_name: {name}`, the absolute resolved `source_checkout`, and the
`source_sha256` SHA-256 digest of the named source skill file. Require
`pyproject.toml`, `uv.lock`, and `documentation/skill-contract.md` in that
checkout. The canonical source skill is
`<resolved-checkout>/.agents/skills/{name}/SKILL.md` and the shared contract is
`<resolved-checkout>/documentation/skill-contract.md`.
Shared contract SHA-256: `{contract_sha256}`. Hash its bytes and require this
exact digest before reading or following either source file. Read both before doing
anything for a run; follow their instructions. Do not derive the checkout from
the current working directory or from this installed wrapper's location.

If the checkout is missing, either digest changed, or a required
file cannot be read, stop and report repair needed: run
`uv run --project <resolved-checkout> --locked agent-advocate skills install --source-checkout <resolved-checkout>`
from a valid checkout, then check `skills status`. Do not select another
checkout or use a bare CLI. For every run CLI request, use exactly
`uv run --project <resolved-checkout> --locked agent-advocate`.
Keep request files and the private store outside all Git worktrees.
"""


def _read_owned(package: Path, name: str) -> tuple[dict[str, object] | None, str]:
    if _is_link(package):
        return None, "unsafe_link"
    if not package.exists():
        return None, "missing"
    if not package.is_dir():
        return None, "foreign"
    children = list(package.iterdir())
    if any(_is_link(child) for child in children):
        return None, "unsafe_link"
    if any(child.name not in _MANAGED_FILES or not child.is_file() for child in children):
        return None, "foreign"
    manifest_path = package / MANIFEST_NAME
    if not manifest_path.is_file():
        return None, "foreign"
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None, "foreign"
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "owner", "skill_name", "source_checkout", "source_sha256"
    }:
        return None, "foreign"
    source = value["source_checkout"]
    try:
        resolved_source = Path(source).resolve(strict=False) if isinstance(source, str) else None
    except (OSError, ValueError):
        resolved_source = None
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != SCHEMA_VERSION
        or value["owner"] != OWNER
        or value["skill_name"] != name
        or not isinstance(source, str)
        or not Path(source).is_absolute()
        or str(Path(source)) != source
        or resolved_source != Path(source)
        or not isinstance(value["source_sha256"], str)
        or not _DIGEST.fullmatch(value["source_sha256"])
    ):
        return None, "foreign"
    return value, "owned"


def _state(package: Path, name: str) -> dict[str, object]:
    manifest, ownership = _read_owned(package, name)
    result: dict[str, object] = {"name": name, "state": ownership}
    if manifest is None:
        return result
    source = Path(str(manifest["source_checkout"]))
    result["source_checkout"] = str(source)
    try:
        source_available = _source_available(source, name)
        source_digest = _source_hash(_source_file(source, name)) if source_available else None
        contract_digest = _source_hash(source / "documentation" / "skill-contract.md") if source_available else None
    except OSError:
        source_available = False
        source_digest = None
    if not source_available:
        result["state"] = "source_missing"
    elif source_digest != manifest["source_sha256"]:
        result["state"] = "source_drift"
    elif not (package / "SKILL.md").is_file():
        result["state"] = "owned_incomplete"
    else:
        try:
            wrapper = (package / "SKILL.md").read_text(encoding="utf-8")
            match = _CONTRACT_DIGEST.search(wrapper)
            if match is None or wrapper != _wrapper(name, match.group(1)):
                result["state"] = "wrapper_drift"
            elif contract_digest != match.group(1):
                result["state"] = "contract_drift"
            else:
                result["state"] = "ready"
        except (OSError, UnicodeError):
            result["state"] = "wrapper_drift"
    return result


def _partial_package(package: Path) -> bool:
    """A marked stage may contain a candidate interrupted before its manifest."""

    if _is_link(package) or not package.is_dir():
        return False
    return all(
        child.name in _MANAGED_FILES and not _is_link(child) and child.is_file()
        for child in package.iterdir()
    )


def _stage_packages(stage: Path) -> list[tuple[Path, str, str]] | None:
    """Recognize a stage only when its contents have a safe recovery path.

    All staged packages may be partly deleted if they contain only managed
    regular files. A backup is disposable only while its live target is owned;
    an absent target requires a complete owned backup for restoration.
    """

    if not stage.name.startswith(".agent-advocate-stage-") or _is_link(stage) or not stage.is_dir():
        return None
    try:
        children = list(stage.iterdir())
        owner = stage / _STAGE_OWNER
        # An interruption between mkdir and the first marker write leaves an
        # empty directory; removing it cannot discard package content.
        if not children:
            return []
        if _is_link(owner) or not owner.is_file():
            return None
        marker = owner.read_bytes()
        expected_marker = (OWNER + "\n").encode("utf-8")
        if marker not in {expected_marker, (OWNER + "\r\n").encode("utf-8")}:
            # The first marker write can be interrupted. Only an otherwise
            # empty stage with a valid prefix is safe to discard.
            return [] if len(children) == 1 and expected_marker.startswith(marker) else None
        packages: list[tuple[Path, str, str]] = []
        for child in children:
            if child.name == _STAGE_OWNER:
                continue
            name = child.name.removesuffix(".backup").removesuffix(".discard")
            kind = "backup" if child.name.endswith(".backup") else (
                "discard" if child.name.endswith(".discard") else "candidate"
            )
            if name not in SKILL_NAMES or child.name != name + ("." + kind if kind != "candidate" else ""):
                return None
            if not _partial_package(child):
                return None
            if kind == "backup":
                target_state = _read_owned(stage.parent / name, name)[1]
                if target_state == "missing":
                    if _read_owned(child, name)[1] != "owned":
                        return None
                elif target_state != "owned":
                    return None
            packages.append((child, name, kind))
        return packages
    except (OSError, UnicodeError):
        return None


def _partial_stages(parent: Path) -> list[dict[str, str]]:
    if not parent.exists():
        return []
    return [
        {
            "path": str(stage),
            "state": "recoverable" if _stage_packages(stage) is not None else "conflict",
        }
        for stage in parent.iterdir()
        if stage.name.startswith(".agent-advocate-stage-")
    ]


def _remove_owned_stage(stage: Path) -> None:
    contents = _stage_packages(stage)
    if contents is None:
        raise ConflictError(f"refusing stage with unknown content: {stage}")
    for package, _, _ in contents:
        if not _partial_package(package):
            raise ConflictError(f"refusing changed staged skill package: {package}")
        shutil.rmtree(package)
    owner = stage / _STAGE_OWNER
    if owner.exists():
        owner.unlink()
    stage.rmdir()


def _recover_stage(stage: Path, parent: Path) -> None:
    contents = _stage_packages(stage)
    if contents is None:
        raise ConflictError(f"refusing stage with unknown content: {stage}")
    # Restore only absent targets. An owned target may be a later successful
    # refresh; replacing it with an older backup would regress that refresh.
    for backup, name, kind in contents:
        if kind != "backup":
            continue
        target = parent / name
        _, state = _read_owned(target, name)
        if state == "missing":
            if _read_owned(backup, name)[1] != "owned":
                raise ConflictError(f"cannot restore incomplete skill backup: {backup}")
            backup.rename(target)
        elif state != "owned":
            raise ConflictError(f"refusing changed skill package: {target}")
    _remove_owned_stage(stage)


def skills_status() -> dict[str, object]:
    parent = user_skill_dir()
    skills = [_state(parent / name, name) for name in SKILL_NAMES]
    partial_stages = _partial_stages(parent)
    return {
        "skill_dir": str(parent),
        "all_ready": not partial_stages and all(item["state"] == "ready" for item in skills),
        "skills": skills,
        "partial_stages": partial_stages,
    }


def _preflight(parent: Path) -> None:
    for name in SKILL_NAMES:
        _, state = _read_owned(parent / name, name)
        if state not in {"missing", "owned"}:
            raise ConflictError(f"refusing {state} skill package: {parent / name}")


def install_skills(source_checkout: str) -> dict[str, object]:
    checkout = _validate_source(source_checkout)
    parent = user_skill_dir(create=True)
    with _transaction_lock(parent):
        return _install_skills_locked(checkout, parent)


def _install_skills_locked(checkout: Path, parent: Path) -> dict[str, object]:
    _preflight(parent)
    try:
        for item in _partial_stages(parent):
            _recover_stage(Path(item["path"]), parent)
    except OSError as error:
        raise SetupError(f"skill stage recovery failed; run skills status and retry: {error}") from error
    stage = Path(tempfile.mkdtemp(prefix=".agent-advocate-stage-", dir=parent))
    try:
        (stage / _STAGE_OWNER).write_text(OWNER + "\n", encoding="utf-8", newline="\n")
        for name in SKILL_NAMES:
            package = stage / name
            package.mkdir()
            (package / "SKILL.md").write_text(
                _wrapper(name, _source_hash(checkout / "documentation" / "skill-contract.md")),
                encoding="utf-8", newline="\n",
            )
            (package / MANIFEST_NAME).write_text(
                json.dumps(_manifest(checkout, name), indent=2, sort_keys=True) + "\n",
                encoding="utf-8", newline="\n",
            )
            if _state(package, name)["state"] != "ready":
                raise RequestError(f"source changed while staging {name}; retry install")
        _preflight(parent)
        for name in SKILL_NAMES:
            target = parent / name
            backup = stage / (name + ".backup")
            _, ownership = _read_owned(target, name)
            if ownership not in {"missing", "owned"}:
                raise ConflictError(f"refusing changed skill package: {target}")
            if ownership == "owned":
                target.rename(backup)
            try:
                (stage / name).rename(target)
            except OSError:
                if backup.exists() and not target.exists():
                    backup.rename(target)
                raise
        if any(_state(parent / name, name)["state"] != "ready" for name in SKILL_NAMES):
            raise SetupError("skill install is incomplete; run skills status and retry")
        _remove_owned_stage(stage)
    except OSError as error:
        raise SetupError(f"skill install failed; run skills status and retry: {error}") from error
    result = skills_status()
    if not result["all_ready"]:
        raise SetupError("skill install is incomplete; run skills status and retry")
    return result


def uninstall_skills() -> dict[str, object]:
    parent = user_skill_dir()
    if not parent.exists():
        return {"removed": [], **skills_status()}
    with _transaction_lock(parent):
        return _uninstall_skills_locked(parent)


def _uninstall_skills_locked(parent: Path) -> dict[str, object]:
    _preflight(parent)
    try:
        for item in _partial_stages(parent):
            _recover_stage(Path(item["path"]), parent)
    except OSError as error:
        raise SetupError(f"skill stage recovery failed; run skills status and retry: {error}") from error
    _preflight(parent)
    removed: list[str] = []
    stage = Path(tempfile.mkdtemp(prefix=".agent-advocate-stage-", dir=parent))
    try:
        (stage / _STAGE_OWNER).write_text(OWNER + "\n", encoding="utf-8", newline="\n")
        for name in SKILL_NAMES:
            target = parent / name
            manifest, _ = _read_owned(target, name)
            if manifest is None:
                continue
            # Check ownership and links immediately before removal.
            current, ownership = _read_owned(target, name)
            if ownership != "owned" or current != manifest:
                raise ConflictError(f"refusing changed skill package: {target}")
            target.rename(stage / (name + ".discard"))
            removed.append(name)
        _remove_owned_stage(stage)
    except OSError as error:
        raise SetupError(f"skill uninstall failed; run skills status and retry: {error}") from error
    return {"removed": removed, **skills_status()}
