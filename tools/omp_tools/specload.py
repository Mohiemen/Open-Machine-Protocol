"""Locates and loads the normative spec artifacts (docs/spec/).

Search order for the spec directory:
1. explicit --spec-dir / spec_dir argument
2. OMP_SPEC_DIR environment variable
3. docs/spec relative to the repository root containing this package
   (editable install layout)
4. docs/spec, then spec, relative to the current working directory
"""
from __future__ import annotations

import json
import os
import pathlib
from functools import lru_cache

from jsonschema import Draft202012Validator

CORE_EVENT_TYPES = frozenset(
    {
        "run_start",
        "run_end",
        "cycle_complete",
        "start",
        "stop",
        "error",
        "alarm",
        "state_change",
        "maintenance_flag",
    }
)


def find_spec_dir(spec_dir: str | os.PathLike | None = None) -> pathlib.Path:
    candidates: list[pathlib.Path] = []
    if spec_dir:
        candidates.append(pathlib.Path(spec_dir))
    if os.environ.get("OMP_SPEC_DIR"):
        candidates.append(pathlib.Path(os.environ["OMP_SPEC_DIR"]))
    pkg_root = pathlib.Path(__file__).resolve().parent.parent.parent
    candidates.append(pkg_root / "docs" / "spec")
    candidates.append(pathlib.Path.cwd() / "docs" / "spec")
    candidates.append(pathlib.Path.cwd() / "spec")
    for c in candidates:
        if (c / "schemas" / "core" / "envelope.json").is_file():
            return c
    tried = "\n  ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        f"OMP spec directory not found; tried:\n  {tried}\n"
        "Pass --spec-dir or set OMP_SPEC_DIR."
    )


class Spec:
    """Loaded core schemas plus profile constraint data."""

    def __init__(self, spec_dir: pathlib.Path):
        self.spec_dir = spec_dir
        core = spec_dir / "schemas" / "core"
        self.validators: dict[str, Draft202012Validator] = {}
        for f in sorted(core.glob("*.json")):
            schema = json.loads(f.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            self.validators[f.stem] = Draft202012Validator(schema)
        self.profiles: dict[str, dict] = {}
        profiles_dir = spec_dir / "profiles"
        if profiles_dir.is_dir():
            for pdir in sorted(profiles_dir.iterdir()):
                if not pdir.is_dir() or pdir.name.startswith("_"):
                    continue
                events_f = pdir / "events.json"
                phases_f = pdir / "phases.json"
                if not events_f.is_file():
                    continue
                events = json.loads(events_f.read_text(encoding="utf-8"))["events"]
                phases = (
                    json.loads(phases_f.read_text(encoding="utf-8"))["phases"]
                    if phases_f.is_file()
                    else {}
                )
                self.profiles[pdir.name] = {
                    "events": {
                        name: Draft202012Validator(spec_["payload"])
                        for name, spec_ in events.items()
                    },
                    "phases": {
                        name: Draft202012Validator(spec_["params"])
                        for name, spec_ in phases.items()
                    },
                }

    # ------------------------------------------------------------------
    def profile_errors(self, envelope: dict,
                       forward_compatible: bool = False) -> list[str]:
        """Constraints from the declared profile (spec section 8.4:
        a message valid under core but invalid under its profile is invalid).

        `forward_compatible` selects the *consumer* reading of spec section 9:
        "Consumers MUST accept unknown profile event types under a known
        profile major version, treating them as opaque events." Profiles add
        event types, phases, and channels in MINOR releases, so a consumer
        running profile 0.1 will legitimately receive 0.2 vocabulary and must
        not reject it - dropping it is the "hard-coding profiles" mistake the
        Platform Ingestion guide calls out.

        Gateways validate strictly (the default): they emit against the
        profile package they ship, so an unknown type there is a bug or a
        misconfiguration, not forward compatibility.

        Unknown *profiles* yield no errors in either mode - the profile
        reference pattern is checked by the envelope schema.
        """
        name = envelope["profile"].split("/")[0]
        prof = self.profiles.get(name)
        if prof is None:
            return []
        body = envelope["body"]
        errors: list[str] = []
        if envelope["schema"] == "event":
            event_type = body.get("event_type")
            if event_type in CORE_EVENT_TYPES:
                pass
            elif event_type in prof["events"]:
                validator = prof["events"][event_type]
                errors += [
                    f"payload: {e.message}"
                    for e in validator.iter_errors(body.get("payload", {}))
                ]
            elif not forward_compatible:
                errors.append(
                    f"event_type {event_type!r} not in core or profile {name!r}"
                )
        elif envelope["schema"] == "process_run":
            for i, phase in enumerate(body.get("phases", [])):
                pname = phase.get("name")
                if pname not in prof["phases"]:
                    if not forward_compatible:   # phases are added in minors too
                        errors.append(f"phases[{i}]: {pname!r} not defined by {name!r}")
                else:
                    validator = prof["phases"][pname]
                    errors += [
                        f"phases[{i}].params: {e.message}"
                        for e in validator.iter_errors(phase.get("params", {}))
                    ]
        return errors


@lru_cache(maxsize=4)
def _load(spec_dir_str: str) -> Spec:
    return Spec(pathlib.Path(spec_dir_str))


def load_spec(spec_dir: str | os.PathLike | None = None) -> Spec:
    return _load(str(find_spec_dir(spec_dir)))
