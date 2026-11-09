import sys
from pathlib import Path
import time
from .control import BASE, atomic_json, command

try:
    command()
except Exception as exc:
    base = BASE
    if "--base" in sys.argv:
        base = Path(sys.argv[sys.argv.index("--base") + 1])
    atomic_json(base / "mascote_runtime.json", {"phase": "error", "heartbeat": time.time(), "message": "Falha ao iniciar o mascote: " + type(exc).__name__})
    raise
