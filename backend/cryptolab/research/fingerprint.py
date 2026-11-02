"""Versioned replay fingerprint; no network, database or exchange access."""
import ast
import hashlib
import json
import platform
import sys
from decimal import __libmpdec_version__
from importlib.metadata import version
from pathlib import Path

SCHEME = "cryptolab-replay-fingerprint/1"
BACKEND = Path(__file__).resolve().parents[2]
PACKAGE = BACKEND / "cryptolab"

# These modules determine simulation, validated inputs or their canonical output.
REPLAY_FILES = (
    "cryptolab/engine/backtest.py", "cryptolab/engine/contracts.py",
    "cryptolab/engine/strategies.py", "cryptolab/history/reader.py",
    "cryptolab/research/fingerprint.py",
)
PACKAGES = ("pydantic", "pydantic_core", "annotated-types", "typing-inspection", "typing_extensions")


def _selected_ast(path: Path, symbols: tuple[str, ...], methods: dict[str, tuple[str, ...]]) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    selected = []
    found = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            selected.append(node)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in symbols:
            selected.append(node)
            found.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {target.id for target in targets if isinstance(target, ast.Name)} & set(symbols)
            if names:
                selected.append(node)
                found.update(names)
        elif isinstance(node, ast.ClassDef) and node.name in methods:
            selected_methods = []
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name in methods[node.name]:
                    selected_methods.append(child)
                    found.add(f"{node.name}.{child.name}")
            selected.append(ast.ClassDef(name=node.name, bases=node.bases, keywords=node.keywords,
                                         body=selected_methods or [ast.Pass()], decorator_list=node.decorator_list))
    expected = set(symbols) | {f"{cls}.{name}" for cls, names in methods.items() for name in names}
    if found != expected:
        raise RuntimeError("Dependências de replay incompletas; revisão do fingerprint necessária")
    return ast.dump(ast.Module(body=selected, type_ignores=[]), include_attributes=False)


def _history_store_ast(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "HistoryStore"]
    if len(classes) != 1:
        raise RuntimeError("HistoryStore ausente ou ambíguo")
    cls = classes[0]
    methods = {"__init__", "__new__", "__getattribute__", "__getattr__", "connect"}
    selected = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in methods]
    shell = ast.ClassDef(name=cls.name, bases=cls.bases, keywords=cls.keywords,
                         body=selected or [ast.Pass()], decorator_list=cls.decorator_list)
    return ast.dump(shell, include_attributes=False)


def replay_fingerprint(backend: Path = BACKEND) -> dict:
    components = {}
    for name in REPLAY_FILES:
        # Normalize platform line endings; preserve all other source content.
        source = (backend / name).read_text(encoding="utf-8")
        components[name] = hashlib.sha256(source.encode("utf-8")).hexdigest()
    for name, symbols, methods in (
        ("cryptolab/config.py", ("INTERVALS",), {}),
        ("cryptolab/models.py", ("Symbol", "Interval", "Candle"), {}),
        ("cryptolab/engine/indicators.py", ("D", "sma", "rsi", "atr"), {}),
        ("cryptolab/history/models.py", ("MAX_CANDLES", "utc_iso", "parse_utc", "HistoryRequest",
         "decimal_text", "candle_record", "canonical_json", "candle_payload", "canonical_history"), {}),
        ("cryptolab/research/service.py", ("digest", "code_reference", "ProtocolRequest", "RunRequest", "ResearchError"),
         {"ResearchService": ("__init__", "protocol", "run", "result", "verify")}),
        ("cryptolab/storage.py", (), {"Store": ("__init__", "connect")}),
    ):
        selected = _selected_ast(backend / name, symbols, methods)
        components[name + "#replay"] = hashlib.sha256(selected.encode("utf-8")).hexdigest()
    store_ast = _history_store_ast(backend / "cryptolab/history/storage.py")
    components["cryptolab/history/storage.py#connection"] = hashlib.sha256(store_ast.encode("utf-8")).hexdigest()
    runtime = {"python": platform.python_version(), "implementation": platform.python_implementation(),
               "python_cache_tag": sys.implementation.cache_tag, "libmpdec": __libmpdec_version__,
               "packages": {name: version(name) for name in PACKAGES}}
    contents = {"scheme": SCHEME, "components": components, "runtime": runtime}
    payload = json.dumps(contents, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {"fingerprint_scheme": SCHEME, "code_hash": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            "replay_dependencies": contents}


def legacy_fingerprint(backend: Path = BACKEND) -> str:
    """Fase 2.2 algorithm, retained verbatim for historical protocols."""
    package = backend / "cryptolab"
    files = sorted([*package.rglob("*.py"), *package.joinpath("migrations").glob("*.sql"),
                    backend / "requirements.lock.txt"])
    content = {str(p.relative_to(backend)).replace("\\", "/"): p.read_text(encoding="utf-8") for p in files}
    payload = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
