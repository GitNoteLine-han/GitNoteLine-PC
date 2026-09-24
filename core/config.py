"""Runtime configuration — shared between web and desktop entry points."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class RuntimeConfig:
    """Holds runtime state that both web/ and desktop/ can access."""

    port: int = 0
    debug: bool = False
    db_path: str = ""          # absolute path to userdata.db
    base_url: str = field(init=False)

    def __post_init__(self) -> None:
        self.base_url = f"http://gitnoteline.localhost:{self.port}"


# Module-level singleton, populated at startup.
config: RuntimeConfig = RuntimeConfig()