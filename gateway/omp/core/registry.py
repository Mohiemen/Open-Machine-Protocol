"""Machine registry loading (/etc/omp/registry.yaml shape from the docs)."""
from __future__ import annotations

import pathlib
import re

import yaml

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,62}$")


class RegistryError(ValueError):
    pass


def load_registry(path: str | pathlib.Path) -> dict:
    data = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8")) or {}
    machines = data.get("machines", [])
    if not isinstance(machines, list):
        raise RegistryError("machines must be a list")
    seen = set()
    for i, m in enumerate(machines):
        where = f"machines[{i}]"
        for key in ("machine_id", "adapter"):
            if key not in m:
                raise RegistryError(f"{where}: missing {key}")
        mid = m["machine_id"]
        if not _ID.fullmatch(mid):
            raise RegistryError(
                f"{where}: machine_id {mid!r} must match {_ID.pattern}"
            )
        if mid in seen:
            raise RegistryError(f"{where}: duplicate machine_id {mid!r}")
        seen.add(mid)
        loc = m.get("location")
        if loc is not None and "site" not in loc:
            raise RegistryError(f"{where}: location.site is required when "
                                "location is given")
        m.setdefault("config", {})
    return data
