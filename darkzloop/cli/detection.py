"""
Darkzloop Auto-Detection

Zero-config project detection. Finds project type and appropriate quality gates.
"""

import json
from pathlib import Path
from dataclasses import dataclass
from typing import List


@dataclass
class ProjectConfig:
    """Auto-detected project configuration."""
    type: str
    tier1_gates: List[str]  # Fast (lint/compile)
    tier2_gates: List[str]  # Slow (tests)


def detect_configuration(path: str = ".") -> ProjectConfig:
    """
    Auto-detect project type and quality gates.
    
    Prioritizes safer/faster checks (Tier 1) over slow test suites (Tier 2).
    """
    root = Path(path)

    # 1. RUST
    if (root / "Cargo.toml").exists():
        return ProjectConfig(
            type="rust",
            tier1_gates=["cargo check"],
            tier2_gates=["cargo test"]
        )

    # 2. NODE / JAVASCRIPT
    if (root / "package.json").exists():
        try:
            pkg = json.loads((root / "package.json").read_text())
            scripts = pkg.get("scripts", {})
            
            t1 = ["npm run lint"] if "lint" in scripts else []
            t2 = ["npm test"] if "test" in scripts else []
            
            return ProjectConfig(type="node", tier1_gates=t1, tier2_gates=t2)
        except Exception:
            return ProjectConfig(type="node", tier1_gates=[], tier2_gates=["npm test"])

    # 3. PYTHON
    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
        t1 = ["ruff check ."] if (root / "pyproject.toml").exists() else []
        t2 = ["pytest -x"]
        return ProjectConfig(type="python", tier1_gates=t1, tier2_gates=t2)

    # 4. GO
    if (root / "go.mod").exists():
        return ProjectConfig(
            type="go",
            tier1_gates=["go build ./..."],
            tier2_gates=["go test ./..."]
        )

    # 5. UNKNOWN
    return ProjectConfig(type="unknown", tier1_gates=[], tier2_gates=[])
