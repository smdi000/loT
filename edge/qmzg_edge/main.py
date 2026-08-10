from __future__ import annotations

import argparse

from .config import EdgeConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QMZG Intel edge bootstrap")
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="validate environment configuration without opening a serial port",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = EdgeConfig.from_env()
    if args.validate_config:
        print(f"edge configuration valid: {config.safe_description()}")
        return 0
    print("Linux L610 wire backend is intentionally not activated in Phase 5-A.")
    print("Use --validate-config, then follow docs/handoff/INTEL_MIGRATION_CHECKLIST.md.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
