from __future__ import annotations

from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

from .models import ModelSpec, ShellSpec, TestSpec

T = TypeVar("T", bound=BaseModel)


def _load_yaml_file(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def _load_specs(path: Path, model_type: type[T]) -> list[T]:
    specs: list[T] = []
    for file in sorted(path.glob("*.yaml")):
        specs.append(model_type.model_validate(_load_yaml_file(file)))
    return specs


def load_test_specs(root: Path) -> list[TestSpec]:
    return _load_specs(root / "specs" / "tests", TestSpec)


def load_model_specs(root: Path) -> list[ModelSpec]:
    return _load_specs(root / "specs" / "models", ModelSpec)


def load_shell_specs(root: Path) -> list[ShellSpec]:
    return _load_specs(root / "specs" / "shells", ShellSpec)
