"""Vapor//matrix agent peer roster (Tranche 5 CRUD).

Typology nomenclature
---------------------
| Term    | Meaning |
|---------|---------|
| peer    | One agent definition (name, command, workspace, sandbox…) |
| roster  | The `agents.json` catalog of peers |
| weave   | Normalize / dedupe raw roster rows into safe peers |
| tune    | Validate allowlisted command argv for a peer |
| forge   | Create a new peer (API op alias: create) |
| retune  | Update an existing peer (API op alias: update) |
| melt    | Delete a peer from the roster (API op alias: delete) |
| scan    | List peers with availability for the UI |
| spawn   | Launch a peer in a terminal (existing launch path) |
| etch    | Build Bubblewrap argv (sandbox remains unchanged) |
"""

from __future__ import annotations

import os
import re
import shlex
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .util import (
    app_config_dir,
    app_data_dir,
    atomic_write_json,
    executable,
    read_json,
    safe_name,
    spawn,
)

# Matrix defaults seeded when agents.json is missing or empty.
DEFAULT_AGENTS: list[dict[str, Any]] = [
    {
        "name": "claude",
        "label": "Claude",
        "command": ["claude"],
        "workspace": "~/work",
        "sandbox": True,
        "network": True,
        "description": "General coding and research agent",
    },
    {
        "name": "cursor",
        "label": "Cursor",
        "command": ["cursor"],
        "workspace": "~/work",
        "sandbox": False,
        "network": True,
        "description": "Cursor editor / composer launcher",
    },
    {
        "name": "aider",
        "label": "Aider",
        "command": ["aider"],
        "workspace": "~/work",
        "sandbox": True,
        "network": True,
        "description": "Terminal pair-programming agent",
    },
]

# Refuse shells / interpreters that turn argv into arbitrary code execution.
_DENIED_PEER_BINARIES = frozenset(
    {
        "bash",
        "sh",
        "zsh",
        "dash",
        "fish",
        "python",
        "python3",
        "perl",
        "ruby",
        "node",
        "sudo",
        "pkexec",
        "env",
        "xargs",
    }
)

# Reject shell metacharacters in raw command strings before shlex split.
_SHELL_METACHARS = re.compile(r"[;|&`$<>(){}\\\\\"'*?\n\r]")

# Each argv token after the binary: flags and simple values only (no paths).
_ARGV_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+/=@:-]{0,127}$|^--?[A-Za-z0-9][A-Za-z0-9._+/=@:-]{0,126}$")

# Cap peer command length so the UI cannot ship huge argv vectors.
_MAX_PEER_ARGV = 12


def tune_peer_argv(raw: Any) -> list[str] | None:
    """Validate and normalize a peer command into an allowlisted argv list.

    Accepts a string (shlex-split) or a list of strings. The first token must be
    a bare binary name (`safe_name`); paths, shells, and metacharacters are refused.
    """
    # Reject non-string / non-list payloads immediately.
    if isinstance(raw, str):
        # Empty or metachar-bearing strings never become peer commands.
        text = raw.strip()
        if not text or _SHELL_METACHARS.search(text):
            return None
        # Split like a shell would, without executing anything.
        try:
            tokens = shlex.split(text)
        except ValueError:
            return None
    elif isinstance(raw, list):
        # Copy so callers cannot mutate our result later.
        tokens = list(raw)
    else:
        return None

    # Require at least a binary name and enforce a hard length cap.
    if not tokens or len(tokens) > _MAX_PEER_ARGV:
        return None
    # Every token must be a non-empty string.
    if not all(isinstance(token, str) and token for token in tokens):
        return None

    # Binary must be a safe bare name — no directories, no denial-listed shells.
    binary = tokens[0].strip().lower()
    if not safe_name(binary) or "/" in tokens[0] or "\\" in tokens[0]:
        return None
    if binary in _DENIED_PEER_BINARIES:
        return None

    # Remaining tokens: allowlisted flag/value shapes only (no path traversal).
    tuned = [binary]
    for token in tokens[1:]:
        if "/" in token or "\\" in token or _SHELL_METACHARS.search(token):
            return None
        if not _ARGV_TOKEN_RE.match(token):
            return None
        tuned.append(token)
    return tuned


def weave_peer_roster(rows: list[Any]) -> list[dict[str, Any]]:
    """Normalize raw roster rows into safe peer dicts; drop duplicates and bad names."""
    result: list[dict[str, Any]] = []
    # Track names already accepted so later duplicates are skipped.
    seen: set[str] = set()
    for raw in rows:
        # Skip anything that is not a mapping.
        if not isinstance(raw, dict):
            continue
        # Peer ids are lower-case safe_name values.
        name = str(raw.get("name", "")).strip().lower()
        if not safe_name(name) or name in seen:
            continue
        # Command may arrive as a string or list; fall back to [name] if invalid.
        command = tune_peer_argv(raw.get("command", [name]))
        if command is None:
            command = [name] if safe_name(name) and name not in _DENIED_PEER_BINARIES else None
        if command is None:
            continue
        # Mark name consumed before appending the woven peer.
        seen.add(name)
        result.append(
            {
                "name": name,
                "label": str(raw.get("label") or name.title())[:80],
                "command": command,
                "workspace": str(raw.get("workspace") or "~/work")[:240],
                "sandbox": bool(raw.get("sandbox", False)),
                "network": bool(raw.get("network", True)),
                "description": str(raw.get("description") or "")[:240],
            }
        )
    return result


def dispatch_peer_op(
    registry: "AgentRegistry",
    op: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Route roster CRUD through a vapor op map (create/update/delete aliases)."""
    # Normalize op token for the lookup table.
    key = str(op or "").strip().lower()
    # Map both plan names and vapor typology names onto registry methods.
    handlers: Mapping[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "create": registry.forge_peer,
        "forge": registry.forge_peer,
        "update": registry.retune_peer,
        "retune": registry.retune_peer,
        "delete": registry.melt_peer,
        "melt": registry.melt_peer,
    }
    handler = handlers.get(key)
    # Unknown ops fail soft with a stable shape for the HTTP layer.
    if handler is None:
        return {"ok": False, "error_code": "unavailable", "error": f"unknown agents op: {op}"}
    return handler(payload)


class AgentRegistry:
    """Owned peer roster persisted at `~/.config/lmdesktopplus/agents.json`."""

    def __init__(self, path: Path | None = None) -> None:
        # Resolve roster path (tests inject a tempfile).
        self.path = path or app_config_dir() / "agents.json"
        # Load JSON; empty/missing files fall back to matrix defaults.
        loaded = read_json(self.path, [])
        seed = loaded if isinstance(loaded, list) and loaded else DEFAULT_AGENTS
        # Weave raw rows into validated peers.
        self._peers = weave_peer_roster(seed)
        # Persist the woven roster so on-disk shape stays canonical.
        self.save()
        # Ensure per-peer home/workspace directories exist.
        self.ensure_directories()

    def save(self) -> None:
        """Atomically write the current peer roster to disk."""
        # Write peers only (no availability fields).
        atomic_write_json(self.path, self._peers)

    def ensure_directories(self) -> None:
        """Create home and workspace directories for every peer in the roster."""
        for peer in self._peers:
            # Agent-private HOME under XDG data.
            self.peer_home(peer["name"]).mkdir(parents=True, exist_ok=True)
            # Expand and create the configured workspace path.
            self.peer_workspace(peer).mkdir(parents=True, exist_ok=True)

    def scan_peers(self) -> list[dict[str, Any]]:
        """Return UI-facing peer rows with availability and resolved paths."""
        result = []
        for peer in self._peers:
            # Copy so callers cannot mutate the in-memory roster.
            row = dict(peer)
            # Binary presence on PATH.
            row["available"] = executable(peer["command"][0]) is not None
            # Resolved home / workspace for display.
            row["home"] = str(self.peer_home(peer["name"]))
            row["workspace_resolved"] = str(self.peer_workspace(peer))
            # Bubblewrap presence for sandbox badge.
            row["sandbox_available"] = executable("bwrap") is not None
            result.append(row)
        return result

    # Compat alias used by older call sites / state snapshot.
    list = scan_peers

    def fetch_peer(self, name: str) -> dict[str, Any] | None:
        """Return a copy of one peer by name, or None if missing."""
        # Linear scan is fine for small rosters.
        return next((dict(peer) for peer in self._peers if peer["name"] == name), None)

    # Compat alias.
    get = fetch_peer

    @staticmethod
    def peer_workspace(peer: dict[str, Any]) -> Path:
        """Expand ~/$VARS in the peer workspace string and resolve the path."""
        # expanduser/expandvars then resolve for a stable absolute path.
        return Path(os.path.expandvars(os.path.expanduser(peer["workspace"]))).resolve()

    # Compat alias.
    workspace = peer_workspace

    @staticmethod
    def peer_home(name: str) -> Path:
        """Return the scoped HOME directory for a peer under app data."""
        # Keep peer homes isolated under the LMDP data tree.
        return (app_data_dir() / "agents" / name).resolve()

    # Compat alias.
    agent_home = peer_home

    def launcher_argv(self, name: str) -> list[str]:
        """Build the argv that re-enters this process to exec a peer."""
        # --agent-run is handled in main.py → exec_peer.
        return [sys.executable, "-m", "lmdesktopplus", "--agent-run", name]

    def forge_peer(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a new peer from a validated payload (API: create / forge)."""
        # Name is required and must be a fresh safe_name.
        name = str(payload.get("name", "")).strip().lower()
        if not safe_name(name):
            return {"ok": False, "error_code": "invalid_argument", "error": "invalid peer name"}
        if self.fetch_peer(name) is not None:
            return {"ok": False, "error_code": "invalid_argument", "error": "peer already exists"}
        # Command must pass the allowlist tuner.
        command = tune_peer_argv(payload.get("command", [name]))
        if command is None:
            return {"ok": False, "error_code": "invalid_argument", "error": "invalid peer command"}
        # Weave a single-row roster to apply label/workspace caps consistently.
        woven = weave_peer_roster(
            [
                {
                    "name": name,
                    "label": payload.get("label"),
                    "command": command,
                    "workspace": payload.get("workspace") or "~/work",
                    "sandbox": payload.get("sandbox", False),
                    "network": payload.get("network", True),
                    "description": payload.get("description") or "",
                }
            ]
        )
        if not woven:
            return {"ok": False, "error_code": "invalid_argument", "error": "peer rejected"}
        # Append, persist, and ensure directories for the new peer.
        self._peers.append(woven[0])
        self.save()
        self.ensure_directories()
        return {"ok": True, "peer": self.fetch_peer(name), "agents": self.scan_peers()}

    def retune_peer(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Update fields on an existing peer (API: update / retune)."""
        # Name selects the peer; it cannot be renamed through this op.
        name = str(payload.get("name", "")).strip().lower()
        if not safe_name(name):
            return {"ok": False, "error_code": "invalid_argument", "error": "invalid peer name"}
        # Find the in-place roster index.
        index = next((i for i, peer in enumerate(self._peers) if peer["name"] == name), None)
        if index is None:
            return {"ok": False, "error_code": "invalid_argument", "error": "unknown peer"}
        current = dict(self._peers[index])
        # Optional command retune — omit payload key to keep the old argv.
        if "command" in payload:
            command = tune_peer_argv(payload.get("command"))
            if command is None:
                return {
                    "ok": False,
                    "error_code": "invalid_argument",
                    "error": "invalid peer command",
                }
            current["command"] = command
        # Optional scalar fields with the same caps as weave.
        if "label" in payload:
            current["label"] = str(payload.get("label") or name.title())[:80]
        if "workspace" in payload:
            current["workspace"] = str(payload.get("workspace") or "~/work")[:240]
        if "sandbox" in payload:
            current["sandbox"] = bool(payload.get("sandbox"))
        if "network" in payload:
            current["network"] = bool(payload.get("network"))
        if "description" in payload:
            current["description"] = str(payload.get("description") or "")[:240]
        # Re-weave through the roster normalizer for a final safety pass.
        woven = weave_peer_roster([current])
        if not woven:
            return {"ok": False, "error_code": "invalid_argument", "error": "peer rejected"}
        self._peers[index] = woven[0]
        self.save()
        self.ensure_directories()
        return {"ok": True, "peer": self.fetch_peer(name), "agents": self.scan_peers()}

    def melt_peer(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Remove a peer from the roster (API: delete / melt). Does not wipe HOME."""
        # Name selects which peer dissolves from the roster.
        name = str(payload.get("name", "")).strip().lower()
        if not safe_name(name):
            return {"ok": False, "error_code": "invalid_argument", "error": "invalid peer name"}
        before = len(self._peers)
        # Filter the peer out; leave on-disk home/workspace untouched.
        self._peers = [peer for peer in self._peers if peer["name"] != name]
        if len(self._peers) == before:
            return {"ok": False, "error_code": "invalid_argument", "error": "unknown peer"}
        self.save()
        return {"ok": True, "melted": name, "agents": self.scan_peers()}

    def spawn_peer(self, name: str) -> dict[str, Any]:
        """Launch a peer inside a supported terminal emulator."""
        # Resolve peer definition first.
        peer = self.fetch_peer(name)
        if not peer:
            return {"ok": False, "error": "unknown agent"}
        # Refuse spawn when the binary is not on PATH.
        if not executable(peer["command"][0]):
            return {"ok": False, "error": f"{peer['command'][0]} is not installed"}
        # Ensure workspace exists before opening the terminal.
        workspace = self.peer_workspace(peer)
        workspace.mkdir(parents=True, exist_ok=True)
        # Re-enter this package with --agent-run for sandbox/exec handling.
        argv = self.launcher_argv(name)
        # Prefer kitty, then GNOME/XFCE/generic terminal wrappers.
        terminal = (
            executable("kitty")
            or executable("gnome-terminal")
            or executable("x-terminal-emulator")
            or executable("xfce4-terminal")
        )
        if not terminal:
            return {"ok": False, "error": "no supported terminal emulator found"}
        base = Path(terminal).name
        # Terminal-specific argv shapes (hold / working-directory flags differ).
        if base == "kitty":
            cmd = [terminal, "--directory", str(workspace), "--hold", *argv]
        elif base == "gnome-terminal":
            cmd = [terminal, f"--working-directory={workspace}", "--", *argv]
        elif base == "xfce4-terminal":
            cmd = [terminal, f"--working-directory={workspace}", "--hold", "--command", shlex.join(argv)]
        else:
            cmd = [terminal, "-e", shlex.join(argv)]
        # Detach the terminal process and return its pid.
        return {"ok": True, "pid": spawn(cmd, cwd=workspace), "agent": name}

    # Compat alias for /api/v1/agents/launch.
    launch = spawn_peer

    def exec_peer(self, name: str) -> int:
        """Replace this process with the peer command (optionally under bwrap)."""
        peer = self.fetch_peer(name)
        if not peer:
            print(f"Unknown agent: {name}", file=sys.stderr)
            return 2
        command = peer["command"]
        # Resolve the binary to an absolute path for exec.
        binary = executable(command[0])
        if not binary:
            print(f"Agent executable is not installed: {command[0]}", file=sys.stderr)
            return 127
        command = [binary, *command[1:]]
        workspace = self.peer_workspace(peer)
        home = self.peer_home(name)
        workspace.mkdir(parents=True, exist_ok=True)
        home.mkdir(parents=True, exist_ok=True)
        # Scoped environment: peer HOME + LMDP markers.
        env = dict(os.environ)
        env["HOME"] = str(home)
        env["LMDP_AGENT"] = name
        env["LMDP_WORKSPACE"] = str(workspace)
        os.chdir(workspace)

        # Sandbox path: etch bwrap argv when requested and available.
        if peer.get("sandbox") and executable("bwrap"):
            argv = self.etch_bubblewrap_argv(peer, command, workspace, home)
            os.execvpe(argv[0], argv, env)
        # Host-session path: exec the peer directly.
        os.execvpe(command[0], command, env)
        return 127

    # Compat alias for --agent-run.
    exec_agent = exec_peer

    @staticmethod
    def etch_bubblewrap_argv(
        peer: dict[str, Any],
        command: list[str],
        workspace: Path,
        home: Path,
    ) -> list[str]:
        """Build Bubblewrap argv for a sandboxed peer (rules unchanged from prior releases)."""
        # Prefer the resolved bwrap binary; fall back to PATH name.
        bwrap = executable("bwrap") or "bwrap"
        # Base isolation: new session, unshared namespaces, fresh /tmp.
        argv = [
            bwrap,
            "--die-with-parent",
            "--new-session",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
        ]
        # Read-only host roots that agents typically need.
        for path in ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc", "/opt"):
            if Path(path).exists():
                argv += ["--ro-bind", path, path]
        # Session bus / runtime dirs when present.
        for path in (Path("/run/user") / str(os.getuid()), Path("/var/lib/dbus")):
            if path.exists():
                argv += ["--ro-bind", str(path), str(path)]
        # Writable peer home + workspace; set HOME and chdir.
        argv += [
            "--bind",
            str(home),
            str(home),
            "--bind",
            str(workspace),
            str(workspace),
            "--setenv",
            "HOME",
            str(home),
            "--setenv",
            "LMDP_AGENT",
            str(peer["name"]),
            "--chdir",
            str(workspace),
        ]
        # Optional network lock when the peer opted out.
        if not peer.get("network", True):
            argv.append("--unshare-net")
        # Command follows the classic `--` separator.
        argv += ["--", *command]
        return argv

    # Compat alias.
    _bubblewrap_argv = etch_bubblewrap_argv
