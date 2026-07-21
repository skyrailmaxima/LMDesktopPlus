from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path
from typing import Any

from .util import app_config_dir, app_data_dir, atomic_write_json, executable, read_json, safe_name, spawn

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


class AgentRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or app_config_dir() / "agents.json"
        loaded = read_json(self.path, [])
        self._agents = self._normalize(loaded if isinstance(loaded, list) and loaded else DEFAULT_AGENTS)
        self.save()
        self.ensure_directories()

    @staticmethod
    def _normalize(rows: list[Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name", "")).strip().lower()
            if not safe_name(name) or name in seen:
                continue
            command = raw.get("command", [name])
            if isinstance(command, str):
                command = shlex.split(command)
            if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
                command = [name]
            seen.add(name)
            result.append({
                "name": name,
                "label": str(raw.get("label") or name.title())[:80],
                "command": command,
                "workspace": str(raw.get("workspace") or "~/work"),
                "sandbox": bool(raw.get("sandbox", False)),
                "network": bool(raw.get("network", True)),
                "description": str(raw.get("description") or "")[:240],
            })
        return result

    def save(self) -> None:
        atomic_write_json(self.path, self._agents)

    def ensure_directories(self) -> None:
        for agent in self._agents:
            self.agent_home(agent["name"]).mkdir(parents=True, exist_ok=True)
            self.workspace(agent).mkdir(parents=True, exist_ok=True)

    def list(self) -> list[dict[str, Any]]:
        result = []
        for agent in self._agents:
            row = dict(agent)
            row["available"] = executable(agent["command"][0]) is not None
            row["home"] = str(self.agent_home(agent["name"]))
            row["workspace_resolved"] = str(self.workspace(agent))
            row["sandbox_available"] = executable("bwrap") is not None
            result.append(row)
        return result

    def get(self, name: str) -> dict[str, Any] | None:
        return next((dict(x) for x in self._agents if x["name"] == name), None)

    @staticmethod
    def workspace(agent: dict[str, Any]) -> Path:
        return Path(os.path.expandvars(os.path.expanduser(agent["workspace"]))).resolve()

    @staticmethod
    def agent_home(name: str) -> Path:
        return (app_data_dir() / "agents" / name).resolve()

    def launcher_argv(self, name: str) -> list[str]:
        return [sys.executable, "-m", "lmdesktopplus", "--agent-run", name]

    def launch(self, name: str) -> dict[str, Any]:
        agent = self.get(name)
        if not agent:
            return {"ok": False, "error": "unknown agent"}
        if not executable(agent["command"][0]):
            return {"ok": False, "error": f"{agent['command'][0]} is not installed"}
        workspace = self.workspace(agent)
        workspace.mkdir(parents=True, exist_ok=True)
        argv = self.launcher_argv(name)
        terminal = executable("kitty") or executable("gnome-terminal") or executable("x-terminal-emulator") or executable("xfce4-terminal")
        if not terminal:
            return {"ok": False, "error": "no supported terminal emulator found"}
        base = Path(terminal).name
        if base == "kitty":
            cmd = [terminal, "--directory", str(workspace), "--hold", *argv]
        elif base == "gnome-terminal":
            cmd = [terminal, f"--working-directory={workspace}", "--", *argv]
        elif base == "xfce4-terminal":
            cmd = [terminal, f"--working-directory={workspace}", "--hold", "--command", shlex.join(argv)]
        else:
            cmd = [terminal, "-e", shlex.join(argv)]
        return {"ok": True, "pid": spawn(cmd, cwd=workspace), "agent": name}

    def exec_agent(self, name: str) -> int:
        agent = self.get(name)
        if not agent:
            print(f"Unknown agent: {name}", file=sys.stderr)
            return 2
        command = agent["command"]
        binary = executable(command[0])
        if not binary:
            print(f"Agent executable is not installed: {command[0]}", file=sys.stderr)
            return 127
        command = [binary, *command[1:]]
        workspace = self.workspace(agent)
        home = self.agent_home(name)
        workspace.mkdir(parents=True, exist_ok=True)
        home.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env["HOME"] = str(home)
        env["LMDP_AGENT"] = name
        env["LMDP_WORKSPACE"] = str(workspace)
        os.chdir(workspace)

        if agent.get("sandbox") and executable("bwrap"):
            argv = self._bubblewrap_argv(agent, command, workspace, home)
            os.execvpe(argv[0], argv, env)
        os.execvpe(command[0], command, env)
        return 127

    @staticmethod
    def _bubblewrap_argv(agent: dict[str, Any], command: list[str], workspace: Path, home: Path) -> list[str]:
        bwrap = executable("bwrap") or "bwrap"
        argv = [
            bwrap, "--die-with-parent", "--new-session", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        ]
        for path in ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc", "/opt"):
            if Path(path).exists():
                argv += ["--ro-bind", path, path]
        for path in (Path("/run/user") / str(os.getuid()), Path("/var/lib/dbus")):
            if path.exists():
                argv += ["--ro-bind", str(path), str(path)]
        argv += [
            "--bind", str(home), str(home),
            "--bind", str(workspace), str(workspace),
            "--setenv", "HOME", str(home),
            "--setenv", "LMDP_AGENT", str(agent["name"]),
            "--chdir", str(workspace),
        ]
        if not agent.get("network", True):
            argv.append("--unshare-net")
        argv += ["--", *command]
        return argv
