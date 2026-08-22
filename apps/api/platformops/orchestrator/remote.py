"""Strict, target-bound remote connection helpers.

Remote credentials are deliberately not part of the inventory model.  Callers
may provide a short-lived key/password for one operation or a reference to an
operator-managed secret (``env://...`` or ``file://...``).  The adapter turns
those references into process-local material only while the SSH command is
running and removes temporary files on exit.

The helper is intentionally small and synchronous because the existing
orchestrators submit synchronous probes from async job callbacks.  It is the
single place where SSH command-line options are assembled; in particular,
there is no insecure host-key fallback and no local-Docker fallback.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import hashlib
import os
import re
import shlex
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence


class RemoteAuthError(ValueError):
    """A remote target cannot be safely authenticated."""


_SHA256_FINGERPRINT = re.compile(r"^SHA256:[A-Za-z0-9+/]+={0,2}$")
_REF = re.compile(r"^(env|file)://[^\s]+$")


def _is_valid_fingerprint(value: str) -> bool:
    if not _SHA256_FINGERPRINT.fullmatch(value):
        return False
    try:
        padded = value[7:] + "=" * (-len(value[7:]) % 4)
        return len(base64.b64decode(padded.encode("ascii"), validate=True)) == hashlib.sha256().digest_size
    except (ValueError, binascii.Error):
        return False


def _node_value(node: Any, *names: str, default: str = "") -> str:
    for name in names:
        value = getattr(node, name, None)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _ephemeral_dir() -> Path:
    """Return the operator-approved ephemeral mount, creating it if needed."""

    configured = os.environ.get("PLATFORMOPS_EPHEMERAL_DIR", "/tmp/platformops-ephemeral")
    path = Path(configured).expanduser()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, stat.S_IRWXU)
    return path


def _resolve_reference(reference: str, *, kind: str) -> str:
    """Resolve an operator-owned reference without accepting inline secrets."""

    value = str(reference or "").strip()
    if not value:
        return ""
    if not _REF.fullmatch(value):
        raise RemoteAuthError(f"{kind} must be an env:// or file:// secret reference")
    scheme, target = value.split("://", 1)
    if scheme == "env":
        # Restrict names so a caller cannot use a reference as an arbitrary
        # environment expression.  The value itself is never persisted.
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", target):
            raise RemoteAuthError(f"invalid {kind} environment reference")
        resolved = os.environ.get(target, "")
    else:
        path = Path(target).expanduser()
        resolved_path = path.resolve()
        if not _is_approved_secret_path(resolved_path):
            raise RemoteAuthError(f"{kind} file reference is outside an approved ephemeral mount")
        if not path.is_file():
            raise RemoteAuthError(f"{kind} reference is unavailable")
        try:
            resolved = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RemoteAuthError(f"{kind} reference could not be read") from exc
    if not resolved:
        raise RemoteAuthError(f"{kind} reference is empty or revoked")
    return resolved


def _is_approved_secret_path(path: Path) -> bool:
    roots = [
        _ephemeral_dir().resolve(),
        Path("/run/secrets").resolve(),
        Path("/app/data").resolve(),
        Path("/app/data/secrets").resolve(),
        Path("/app/data/keys").resolve(),
        Path("data/secrets").resolve(),
        Path("data/keys").resolve(),
    ]
    extra_mount = os.environ.get("PLATFORMOPS_SECRET_MOUNT", "").strip()
    if extra_mount:
        roots.append(Path(extra_mount).expanduser().resolve())
    return any(path == root or root in path.parents for root in roots)


def _fingerprint(key_line: str) -> str:
    """Calculate the OpenSSH SHA256 fingerprint for a known_hosts key line."""

    fields = key_line.split()
    if len(fields) < 3 or not fields[1].startswith(("ssh-", "ecdsa-", "sk-", "rsa-")):
        raise RemoteAuthError("known-hosts entry has no supported public key")
    try:
        raw = base64.b64decode(fields[2].encode("ascii"), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RemoteAuthError("known-hosts entry contains an invalid public key") from exc
    digest = base64.b64encode(hashlib.sha256(raw).digest()).decode("ascii").rstrip("=")
    return f"SHA256:{digest}"


def _validate_known_hosts(path: Path, fingerprint: str) -> None:
    expected = str(fingerprint or "").strip()
    if not _is_valid_fingerprint(expected):
        raise RemoteAuthError("host_key_fingerprint must be an OpenSSH SHA256 fingerprint")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RemoteAuthError("known-hosts reference is unavailable") from exc
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            if _fingerprint(line) == expected:
                return
        except RemoteAuthError:
            continue
    raise RemoteAuthError("configured host key fingerprint does not match known host")


def _scan_known_hosts(host: str, fingerprint: str = "") -> Path:
    """Scan a host key into an ephemeral file and pin it to the configured fingerprint."""

    if not host:
        raise RemoteAuthError("remote host is required")
    expected = str(fingerprint or "").strip()
    fd, raw_path = tempfile.mkstemp(prefix="known-hosts-", dir=_ephemeral_dir(), text=True)
    os.close(fd)
    path = Path(raw_path)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    try:
        proc = subprocess.run(
            ["ssh-keyscan", "-T", "8", "-t", "ed25519,rsa", host],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
        if proc.returncode != 0 or not (proc.stdout or "").strip():
            raise RemoteAuthError("host key scan failed")
        path.write_text(proc.stdout, encoding="utf-8")
        if expected:
            _validate_known_hosts(path, expected)
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


@dataclass
class RemoteCommand:
    argv: list[str]
    env: dict[str, str]


@contextlib.contextmanager
def ssh_command(
    node: Any,
    remote_command: str | Sequence[str],
    *,
    ephemeral_key: str | None = None,
    ephemeral_password: str | None = None,
    timeout: int = 10,
) -> Iterator[RemoteCommand]:
    """Yield a strict SSH command and child environment for one operation.

    ``ephemeral_key`` and ``ephemeral_password`` are request-scoped only.  A
    node's persisted fields are references (not material); ``ssh_private_key``
    must never be passed to an ORM constructor or job command.
    """

    host = _node_value(node, "host")
    user = _node_value(node, "ssh_user", default="ubuntu")
    if not host or host.lower() in {"localhost", "127.0.0.1", "0.0.0.0"}:
        raise RemoteAuthError("ssh_command requires a non-loopback remote host")
    fingerprint = _node_value(node, "host_key_fingerprint", "ssh_host_key_fingerprint")
    known_hosts_ref = _node_value(node, "known_hosts_ref", "ssh_known_hosts_ref")
    key_ref = _node_value(node, "ssh_key_path")
    secret_ref = _node_value(node, "secret_ref", "ssh_secret_ref")
    auth_mode = _node_value(node, "auth_mode", default="ssh_key").lower()
    temp_paths: list[Path] = []
    env = os.environ.copy()
    try:
        if known_hosts_ref:
            if known_hosts_ref.startswith("file://"):
                known_hosts_path = Path(known_hosts_ref[7:]).expanduser()
            else:
                raise RemoteAuthError("known_hosts_ref must be a file:// reference")
            if not known_hosts_path.is_file():
                raise RemoteAuthError("known-hosts reference is unavailable")
            _validate_known_hosts(known_hosts_path, fingerprint)
        else:
            known_hosts_path = _scan_known_hosts(host, fingerprint)
            temp_paths.append(known_hosts_path)

        key_path: Path | None = None
        key_value = ephemeral_key
        if key_value is None and secret_ref and auth_mode not in {"password", "ssh_password"}:
            key_value = _resolve_reference(secret_ref, kind="SSH secret")
        if key_value:
            handle = tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", prefix="ssh-key-", dir=_ephemeral_dir(), delete=False
            )
            key_path = Path(handle.name)
            try:
                handle.write(key_value.strip() + "\n")
            finally:
                handle.close()
            os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
            temp_paths.append(key_path)
        elif key_ref:
            key_path = Path(key_ref).expanduser()
            if not _is_approved_secret_path(key_path.resolve()):
                raise RemoteAuthError("SSH key reference is outside an approved ephemeral mount")
            if not key_path.is_file():
                raise RemoteAuthError("SSH key reference is unavailable or revoked")

        password_value = ephemeral_password
        if password_value is None and secret_ref and auth_mode in {"password", "ssh_password"}:
            password_value = _resolve_reference(secret_ref, kind="SSH password")

        argv = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={known_hosts_path}",
            "-o",
            "BatchMode=yes" if not password_value else "BatchMode=no",
            "-o",
            f"ConnectTimeout={max(1, int(timeout))}",
        ]
        if password_value:
            fd, raw_path = tempfile.mkstemp(prefix="ssh-password-", dir=_ephemeral_dir(), text=True)
            os.close(fd)
            password_file = Path(raw_path)
            password_file.write_text(password_value, encoding="utf-8")
            os.chmod(password_file, stat.S_IRUSR | stat.S_IWUSR)
            temp_paths.append(password_file)
            fd, raw_path = tempfile.mkstemp(prefix="ssh-askpass-", dir=_ephemeral_dir(), text=True)
            os.close(fd)
            askpass = Path(raw_path)
            askpass.write_text(
                "#!/bin/sh\nexec cat \"$PLATFORMOPS_SSH_PASSWORD_FILE\"\n", encoding="utf-8"
            )
            os.chmod(askpass, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            temp_paths.append(askpass)
            env["PLATFORMOPS_SSH_PASSWORD_FILE"] = str(password_file)
            env["SSH_ASKPASS"] = str(askpass)
            env["SSH_ASKPASS_REQUIRE"] = "force"
            env.setdefault("DISPLAY", "platformops:0")
            argv.extend(
                [
                    "-o",
                    "PasswordAuthentication=yes",
                    "-o",
                    "PubkeyAuthentication=no",
                    "-o",
                    "PreferredAuthentications=password",
                ]
            )
        elif key_path:
            argv.extend(["-i", str(key_path)])
        argv.append(f"{shlex.quote(user)}@{shlex.quote(host)}")
        if isinstance(remote_command, str):
            argv.append(remote_command)
        else:
            argv.append(shlex.join([str(item) for item in remote_command]))
        yield RemoteCommand(argv=argv, env=env)
    finally:
        for path in reversed(temp_paths):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        for key in ("PLATFORMOPS_SSH_PASSWORD_FILE", "SSH_ASKPASS", "SSH_ASKPASS_REQUIRE"):
            env.pop(key, None)


def run_ssh(
    node: Any,
    remote_command: str | Sequence[str],
    *,
    ephemeral_key: str | None = None,
    ephemeral_password: str | None = None,
    timeout: int = 10,
) -> subprocess.CompletedProcess[str]:
    """Run one strict remote command; credentials never enter argv/output."""

    with ssh_command(
        node,
        remote_command,
        ephemeral_key=ephemeral_key,
        ephemeral_password=ephemeral_password,
        timeout=timeout,
    ) as command:
        return subprocess.run(
            command.argv,
            capture_output=True,
            text=True,
            timeout=max(1, timeout + 2),
            env=command.env,
        )


def get_or_create_cluster_ssh_key() -> tuple[Path, str]:
    """Ensure the PlatformOps control plane has a persistent ed25519 keypair in data/keys/."""
    key_dir = Path("/app/data/keys") if Path("/app/data").exists() else Path("data/keys")
    key_dir.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(Exception):
        os.chmod(key_dir, 0o700)
    key_path = key_dir / "platformops_cluster_ed25519"
    pub_path = key_dir / "platformops_cluster_ed25519.pub"
    if not key_path.is_file() or not pub_path.is_file():
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-f", str(key_path), "-N", "", "-C", "platformops-cluster-key", "-q"],
            check=True,
        )
        with contextlib.suppress(Exception):
            os.chmod(key_path, 0o600)
            os.chmod(pub_path, 0o644)
    return key_path, pub_path.read_text(encoding="utf-8").strip()


def bootstrap_node_authorized_keys(node: Any, password: str | None = None) -> bool:
    """Inject cluster public key into remote authorized_keys using password auth."""
    host = _node_value(node, "host")
    if not host or host.lower() in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return False
    pw = password or _node_value(node, "ssh_password")
    if not pw and getattr(node, "ssh_secret_ref", None):
        with contextlib.suppress(Exception):
            pw = _resolve_reference(node.ssh_secret_ref, kind="SSH password")
    if not pw:
        return False
    key_path, pub_key = get_or_create_cluster_ssh_key()
    remote_cmd = (
        f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && "
        f"grep -qF '{pub_key}' ~/.ssh/authorized_keys || echo '{pub_key}' >> ~/.ssh/authorized_keys"
    )
    res = run_ssh(node, remote_cmd, ephemeral_password=pw, timeout=15)
    return res.returncode == 0


def strict_ansible_options(node: Any) -> str:
    """Return safe Ansible SSH options for a persisted job command preview."""

    host = _node_value(node, "host")
    fingerprint = _node_value(node, "host_key_fingerprint", "ssh_host_key_fingerprint")
    if not host or host.lower() in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return ""
    known_hosts_ref = _node_value(node, "known_hosts_ref", "ssh_known_hosts_ref")
    if known_hosts_ref and known_hosts_ref.startswith("file://"):
        known_hosts_path = Path(known_hosts_ref[7:]).expanduser()
        if known_hosts_path.is_file() and fingerprint:
            return (
                " --ssh-common-args="
                + shlex.quote(f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={known_hosts_path}")
            )
    return " --ssh-common-args=" + shlex.quote("-o StrictHostKeyChecking=accept-new")


def strict_known_hosts_path(node: Any) -> Path:
    """Resolve and verify the pinned known_hosts file for a remote target."""

    fingerprint = _node_value(node, "host_key_fingerprint", "ssh_host_key_fingerprint")
    if not _is_valid_fingerprint(fingerprint):
        raise RemoteAuthError("host_key_fingerprint is required for remote Ansible")
    known_hosts_ref = _node_value(node, "known_hosts_ref", "ssh_known_hosts_ref")
    if not known_hosts_ref.startswith("file://"):
        raise RemoteAuthError("known_hosts_ref is required for remote Ansible")
    known_hosts_path = Path(known_hosts_ref[7:]).expanduser()
    if not known_hosts_path.is_file():
        raise RemoteAuthError("known_hosts_ref is unavailable for remote Ansible")
    _validate_known_hosts(known_hosts_path, fingerprint)
    return known_hosts_path


__all__ = [
    "RemoteAuthError",
    "RemoteCommand",
    "bootstrap_node_authorized_keys",
    "get_or_create_cluster_ssh_key",
    "run_ssh",
    "ssh_command",
    "strict_ansible_options",
    "strict_known_hosts_path",
]
