from __future__ import annotations

import argparse
import logging
import sys

from app.db.session import get_session_factory
from app.services.device_ownership import (
    DeviceOwnershipError,
    mask_device_id,
    preview_device_transfer,
    transfer_device,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    transfer = commands.add_parser("transfer-device", help="transfer one exact device to one exact user")
    transfer.add_argument("--device-id", required=True)
    transfer.add_argument("--to-user-id", required=True)
    transfer.add_argument("--yes", action="store_true", help="commit without an interactive prompt")
    return parser


def _run_transfer(args: argparse.Namespace) -> int:
    session = get_session_factory()()
    try:
        preview = preview_device_transfer(
            session,
            device_id=args.device_id,
            to_user_id=args.to_user_id,
        )
        print("Device ownership transfer")
        print(f"  device:   {mask_device_id(preview.device_id)}")
        print(f"  old user: {preview.old_user_id or '<unassigned>'}")
        print(f"  new user: {preview.new_user_id}")
        if not args.yes:
            answer = input("Type TRANSFER to commit: ").strip()
            if answer != "TRANSFER":
                print("Transfer cancelled.")
                return 2
        result = transfer_device(
            session,
            device_id=preview.device_id,
            to_user_id=preview.new_user_id,
        )
        print("Transfer complete." if result.changed else "Device already belongs to the target user.")
        return 0
    except DeviceOwnershipError as exc:
        print(f"Transfer rejected: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = build_parser().parse_args(argv)
    if args.command == "transfer-device":
        return _run_transfer(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
