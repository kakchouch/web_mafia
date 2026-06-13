"""
Store de configuration mutable.
Source unique de vérité : config.env.
Les clés, valeurs par défaut et types sont déduits de ce fichier au démarrage.
"""
from __future__ import annotations
import os

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.env")


def _parse_env_file(path: str) -> dict[str, str]:
    """Lit config.env et retourne les paires clé→valeur brute (ignore commentaires)."""
    result: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith("#") and "=" in s:
                    key, _, val = s.partition("=")
                    result[key.strip()] = val.strip()
    except FileNotFoundError:
        pass
    return result


def _infer_type(raw: str) -> type:
    """Infère le type Python d'une valeur brute (bool > int > float > str)."""
    if raw.lower() in ("true", "false"):
        return bool
    try:
        int(raw)
        return int
    except ValueError:
        pass
    try:
        float(raw)
        return float
    except ValueError:
        pass
    return str


# Valeurs brutes lues depuis config.env — source unique de vérité
_RAW_DEFAULTS: dict[str, str] = _parse_env_file(_CONFIG_PATH)
# Types inférés automatiquement
_TYPES: dict[str, type] = {k: _infer_type(v) for k, v in _RAW_DEFAULTS.items()}
# Store mutable en mémoire
_CONFIG: dict[str, str | int | float | bool] = {}


def _coerce(raw: str, key: str) -> str | int | float | bool:
    t = _TYPES.get(key, str)
    if t is bool:
        return raw.lower() in ("1", "true", "yes")
    if t is int:
        try:
            return int(raw)
        except ValueError:
            try:
                return int(_RAW_DEFAULTS.get(key, "0"))
            except ValueError:
                return 0
    if t is float:
        try:
            return float(raw)
        except ValueError:
            try:
                return float(_RAW_DEFAULTS.get(key, "0"))
            except ValueError:
                return 0.0
    return raw


def _init() -> None:
    for key, raw_default in _RAW_DEFAULTS.items():
        raw = os.environ.get(key, raw_default)
        _CONFIG[key] = _coerce(raw, key)


_init()


def get(key: str) -> str | int | float | bool:
    return _CONFIG[key]


def all_values() -> dict:
    return dict(_CONFIG)


def update(values: dict) -> None:
    """Met à jour les valeurs en mémoire (sans écrire le fichier)."""
    for k, v in values.items():
        if k not in _TYPES:
            continue
        if isinstance(v, str):
            _CONFIG[k] = _coerce(v, k)
        else:
            t = _TYPES[k]
            if t is bool:
                _CONFIG[k] = bool(v)
            elif t is int:
                _CONFIG[k] = int(v)
            elif t is float:
                _CONFIG[k] = float(v)
            else:
                _CONFIG[k] = str(v)


def save() -> None:
    """Persiste la configuration courante dans config.env en préservant les commentaires."""
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    written: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            key = s.split("=", 1)[0].strip()
            if key in _CONFIG:
                new_lines.append(f"{key}={_CONFIG[key]}\n")
                written.add(key)
                continue
        new_lines.append(line)

    for key, val in _CONFIG.items():
        if key not in written:
            new_lines.append(f"{key}={val}\n")

    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
