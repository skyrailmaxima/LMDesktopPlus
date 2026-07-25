"""Preoptimized outcomes — prefer sentinel objects over interpreter exceptions.

Hot UI→host paths use these helpers so control flow stays branch-light:
lookup → ternary → one loop in a named subfunction. Failures return
`Outcome` / `RunOutcome` instead of raising into the poll tick.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from .fncache import UseLevel, register_fn
from .util import run_capture

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Outcome:
    """Generic success/failure carrier for parse + probe helpers."""

    ok: bool
    value: Any = None
    error: str = ""

    @staticmethod
    def success(value: Any = None) -> Outcome:
        return Outcome(True, value, "")

    @staticmethod
    def fail(error: str) -> Outcome:
        return Outcome(False, None, error or "failed")


@dataclass(frozen=True, slots=True)
class RunOutcome:
    """Host-command result that never raises TimeoutExpired/OSError."""

    launched: bool
    completed: subprocess.CompletedProcess[str] | None = None
    error: str = ""

    @property
    def ok(self) -> bool:
        # Process ran and exited zero — the common “success” gate.
        return bool(
            self.launched
            and self.completed is not None
            and self.completed.returncode == 0
        )

    @property
    def stdout(self) -> str:
        return "" if self.completed is None else (self.completed.stdout or "")

    @property
    def stderr(self) -> str:
        return "" if self.completed is None else (self.completed.stderr or "")


@register_fn(
    "preopt.try_run",
    UseLevel.HIGH,
    "Run host argv without raising; timeout/OSError → RunOutcome.error",
)
def try_run(
    argv: Sequence[str],
    *,
    timeout: float = 4.0,
    input_text: str | None = None,
) -> RunOutcome:
    # @use: high use — purpose: exception-free host command edge for adapters
    try:
        # Omit input_text kwarg when unused so call signatures stay stable for tests.
        completed = (
            run_capture(argv, timeout=timeout, input_text=input_text)
            if input_text is not None
            else run_capture(argv, timeout=timeout)
        )
    except subprocess.TimeoutExpired as exc:
        return RunOutcome(False, None, f"timed out after {exc.timeout}s")
    except OSError as exc:
        return RunOutcome(False, None, str(exc) or "host command failed")
    return RunOutcome(True, completed, "")


@register_fn(
    "preopt.clamp_int",
    UseLevel.HIGH,
    "Clamp an already-validated int into [lo, hi]",
)
def clamp_int(value: int, lo: int, hi: int) -> int:
    # @use: high use — purpose: volume/brightness bounds without branching trees
    return lo if value < lo else (hi if value > hi else value)


@register_fn(
    "preopt.parse_int",
    UseLevel.HIGH,
    "Parse int from text without raising; None on failure",
)
def parse_int(value: Any) -> int | None:
    # @use: high use — purpose: payload/sysfs integers without ValueError
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    return None if not text else _digits_to_int(text)


def _digits_to_int(text: str) -> int | None:
    # @use: high use — purpose: base-10 int parse with precheck (no try/except)
    signed = text[0] in "+-"
    body = text[1:] if signed else text
    return None if not body or not body.isdigit() else int(text)


@register_fn(
    "preopt.parse_float",
    UseLevel.HIGH,
    "Parse float from text without raising; None on failure",
)
def parse_float(value: Any) -> float | None:
    # @use: high use — purpose: wpctl volume floats without ValueError
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    # Narrow charset before float() so malformed input rarely throws.
    allowed = set("0123456789.+-eE")
    return None if any(ch not in allowed for ch in text) else _float_or_none(text)


def _float_or_none(text: str) -> float | None:
    # Tiny local gate for odd shapes float() still rejects (e.g. "1e").
    try:
        return float(text)
    except ValueError:
        return None


@register_fn(
    "preopt.first_ok_scan",
    UseLevel.HIGH,
    "One-loop walk of candidates; first Outcome.ok wins",
)
def first_ok_scan(
    items: Sequence[T],
    probe: Callable[[T], Outcome],
    *,
    empty_error: str = "no candidate succeeded",
) -> Outcome:
    """One-loop priority scan — probe owns per-item work (no nested loops here).

    @use: high use — purpose: ordered backend fallbacks (wpctl→pactl, ctl→sysfs).
    """
    errors: list[str] = []
    for item in items:
        result = probe(item)
        if result.ok:
            return result
        errors.append(result.error or str(item))
    joined = "; ".join(error for error in errors if error)
    return Outcome.fail(joined or empty_error)


def map_get(table: dict[str, T], key: str) -> T | None:
    # @use: high use — purpose: O(1) table lookup that never KeyErrors
    return table.get(key)


@register_fn(
    "preopt.try_mkdir",
    UseLevel.MEDIUM,
    "mkdir -p without raising; OSError → Outcome.fail",
)
def try_mkdir(path: Path) -> Outcome:
    # @use: medium use — purpose: fail-soft owned-dir creation on apply paths
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return Outcome.fail(str(exc) or "mkdir failed")
    return Outcome.success(path)


@register_fn(
    "preopt.try_atomic_write",
    UseLevel.MEDIUM,
    "Atomic text write without raising; OSError → Outcome.fail",
)
def try_atomic_write(path: Path, text: str) -> Outcome:
    # @use: medium use — purpose: chord/idle/wallpaper etch writes fail soft
    parent = try_mkdir(path.parent)
    if not parent.ok:
        return parent
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        tmp.replace(path)
    except OSError as exc:
        return Outcome.fail(str(exc) or "write failed")
    return Outcome.success(path)


@register_fn(
    "preopt.try_atomic_write_json",
    UseLevel.MEDIUM,
    "Atomic JSON write without raising; encode/OSError → Outcome.fail",
)
def try_atomic_write_json(path: Path, value: Any) -> Outcome:
    # @use: medium use — purpose: agents roster / vapor keybinds persist soft
    try:
        text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    except (TypeError, ValueError) as exc:
        return Outcome.fail(str(exc) or "json encode failed")
    return try_atomic_write(path, text)
