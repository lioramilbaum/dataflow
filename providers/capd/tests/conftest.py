from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

import pulumi
import pulumi.runtime


@dataclass
class ResourceRecord:
    typ: str
    name: str
    inputs: dict[str, Any]          # post-fill outputs (as before)
    program_inputs: dict[str, Any]  # raw inputs from the program, before mock fills metadata.name


class Recorder(pulumi.runtime.Mocks):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.resources: list[ResourceRecord] = []

    def new_resource(self, args: pulumi.runtime.MockResourceArgs) -> tuple[str, dict]:
        if not args.custom:
            return (args.name + "-id", args.inputs)
        program_inputs = dict(args.inputs)   # snapshot before any mutation
        meta = dict(args.inputs.get("metadata") or {})
        if "name" not in meta:
            kind = args.typ.rsplit(":", 1)[-1]
            meta["name"] = f"{args.name}-auto-{kind}"
        outputs = {**args.inputs, "metadata": meta}
        with self._lock:
            self.resources.append(ResourceRecord(
                typ=args.typ,
                name=args.name,
                inputs=outputs,
                program_inputs=program_inputs,
            ))
        return (args.name + "-id", outputs)

    def call(self, args: pulumi.runtime.MockCallArgs) -> tuple[dict, list[tuple[str, str]] | None]:
        return ({}, None)


def make_recorder() -> Recorder:
    rec = Recorder()
    pulumi.runtime.set_mocks(rec, project="dataflow-capd", stack="dev", preview=False)
    return rec


def find_resources(resources: list[ResourceRecord], token: str) -> list[ResourceRecord]:
    return [r for r in resources if r.typ == token]


def find_one(resources: list[ResourceRecord], token: str) -> ResourceRecord:
    found = find_resources(resources, token)
    assert len(found) == 1, f"expected 1 resource of type {token}, got {len(found)}"
    return found[0]


def lookup(d: Any, *path: str | int) -> Any:
    for key in path:
        if isinstance(d, dict):
            d = d[key]
        elif isinstance(d, (list, tuple)):
            d = d[key]
        else:
            raise KeyError(f"expected dict or list at {key!r}, got {type(d)}")
    return d
