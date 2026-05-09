"""
main.py

Entry point for the Finance Credit Follow-Up Email Agent.

Usage:
    python main.py            # respects DRY_RUN value from .env
    python main.py --dry-run  # forces safe mode (no real emails sent)
    python main.py --send     # forces live mode (real SMTP emails)
"""

import argparse
import sys

from src import config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finance Credit Follow-Up Email Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py --dry-run          # simulate without sending\n"
            "  python main.py --send             # send real emails via SMTP\n"
            "  python main.py --dry-run --limit 5  # test just 5 invoices\n"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of invoices to process in this run",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Override .env — force dry-run mode (no emails sent)",
    )
    mode.add_argument(
        "--send",
        action="store_true",
        help="Override .env — force live mode (real emails via SMTP)",
    )
    return parser.parse_args()


def _print_banner(dry_run: bool) -> None:
    mode_label = "DRY-RUN (safe)" if dry_run else "LIVE (emails will be sent)"
    print("=" * 60)
    print("  Finance Credit Follow-Up Email Agent")
    print(f"  Mode    : {mode_label}")
    print(f"  Dataset : {config.DATA_PATH}")
    print(f"  Output  : {config.OUTPUT_DIR}")
    print("=" * 60)
    print()


def _print_summary(summary: dict) -> None:
    print()
    print("=" * 60)
    print("  RUN COMPLETE")
    print(f"  Processed : {summary.get('total_processed', 0)}")
    print(f"  Sent      : {summary.get('total_sent', 0)}")
    print(f"  Skipped   : {summary.get('total_skipped', 0)}")
    print(f"  Errors    : {summary.get('total_errors', 0)}")
    print(f"  Report    : {summary.get('report_file', 'N/A')}")
    print("=" * 60)


def main() -> int:
    """
    Orchestrate the full agent run.

    Returns:
        0 on success, 1 on unhandled error.
    """
    args = _parse_args()

    # 1. Apply CLI mode overrides before importing the agent
    if args.dry_run:
        config.DRY_RUN = True
    elif args.send:
        config.DRY_RUN = False

    # 2. Print run mode banner so the user always knows what mode they're in
    _print_banner(config.DRY_RUN)

    # 3. Run the agent
    try:
        from src.agent import run_agent   # deferred import — respects patched config.DRY_RUN
        summary = run_agent(limit=args.limit, verbose=True)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Run cancelled by user.")
        return 1
    except Exception as exc:
        print(f"\n[ERROR] Unhandled exception: {exc}")
        return 1

    # 4. Print the final summary
    _print_summary(summary)

    # 5. Exit 0 on success
    return 0


if __name__ == "__main__":
    sys.exit(main())
