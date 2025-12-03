#!/usr/bin/env python3
"""
CLI wrapper for WireGuard AllowedIPs calculator.

Examples:
  python3 wg_ips_cli.py \
    --allowed "0.0.0.0/0, ::/0" \
    --disallowed "27.27.27.27, 10.27.0.27/32, 10.27.0.1"
    --disallowed is omitted -> treated as empty.
"""

import sys
import argparse

from wg_ips_core import calculate_allowed_ips, VERSION


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="WireGuard AllowedIPs calculator (CLI) %s " % VERSION
    )
    parser.add_argument(
        "-a",
        "--allowed",
        required=True,
        help="Allowed IPs/CIDRs (comma- or whitespace-separated)",
    )
    parser.add_argument(
        "-d",
        "--disallowed",
        default="",
        help="Disallowed IPs/CIDRs (comma- or whitespace-separated)",
    )

    args = parser.parse_args(argv)

    try:
        result = calculate_allowed_ips(args.allowed, args.disallowed)
    except ValueError as e:
        print(f"Input error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
