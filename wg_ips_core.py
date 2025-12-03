#!/usr/bin/env python3
"""
Core calculation logic for WireGuard AllowedIPs calculator.
"""

import re
import ipaddress
from typing import List, Tuple

VERSION = 0.1


def parse_ip_list(text: str):
    """
    Parse a comma / whitespace-separated list of IPs and CIDRs.

    Returns a list of ipaddress.IPv4Network / IPv6Network objects.
    Single IPs are converted to /32 (IPv4) or /128 (IPv6).
    """
    tokens = []
    for part in re.split(r"[,\s]+", text.strip()):
        if not part:
            continue
        tokens.append(part)

    nets = []
    for token in tokens:
        try:
            if "/" in token:
                n = ipaddress.ip_network(token, strict=False)
            else:
                addr = ipaddress.ip_address(token)
                prefix = 32 if addr.version == 4 else 128
                n = ipaddress.ip_network(f"{addr}/{prefix}", strict=False)
            nets.append(n)
        except Exception as e:
            raise ValueError(f"Invalid IP/CIDR '{token}': {e}")
    return nets


def split_networks_by_ip_version(nets):
    v4, v6 = [], []
    for n in nets:
        if n.version == 4:
            v4.append(n)
        else:
            v6.append(n)
    return v4, v6


def nets_to_ranges(nets) -> List[Tuple[int, int]]:
    """
    Convert networks to inclusive numeric ranges [start, end].
    """
    ranges = []
    for n in nets:
        start = int(n.network_address)
        end = int(n.broadcast_address)
        ranges.append([start, end])
    return ranges


def subtract_one_range_list(ranges: List[List[int]], remove_range: List[int]):
    """
    Subtract one inclusive [c, d] range from a list of inclusive [a, b] ranges.
    Returns a new list of ranges.
    """
    c, d = remove_range
    result = []

    for a, b in ranges:
        # No overlap
        if d < a or c > b:
            result.append([a, b])
            continue

        # Full cover: [c, d] completely covers [a, b] -> drop [a, b]
        if c <= a and d >= b:
            continue

        # Partial overlaps
        # Case: c <= a <= d < b -> keep right part
        if c <= a <= d < b:
            result.append([d + 1, b])
            continue

        # Case: a < c <= b <= d -> keep left part
        if a < c <= b <= d:
            result.append([a, c - 1])
            continue

        # Case: a < c and d < b -> [a, c-1] and [d+1, b]
        if a < c and d < b:
            result.append([a, c - 1])
            result.append([d + 1, b])
            continue
    return result


def subtract_ranges(allowed_ranges: List[List[int]], disallowed_ranges: List[List[int]]):
    """
    Subtract all disallowed ranges from allowed ranges.
    Both arguments are lists of inclusive [start, end] integer ranges.
    """
    result = allowed_ranges
    for dr in disallowed_ranges:
        result = subtract_one_range_list(result, dr)
    return result


def ranges_to_networks(ranges: List[List[int]], version: int):
    """
    Convert inclusive [start, end] ranges back to a minimal set of CIDRs.
    Uses ipaddress.summarize_address_range + collapse_addresses.
    """
    if not ranges:
        return []

    addr_cls = ipaddress.IPv4Address if version == 4 else ipaddress.IPv6Address

    nets = []
    for start, end in ranges:
        nets.extend(ipaddress.summarize_address_range(addr_cls(start), addr_cls(end)))

    # Collapse overlapping/adjacent networks to minimal representation
    nets = list(ipaddress.collapse_addresses(nets))

    # Sort by starting address
    nets.sort(key=lambda n: int(n.network_address))
    return nets


def calculate_allowed_ips(allowed_text: str, disallowed_text: str) -> str:
    """
    High-level API: compute the final AllowedIPs string.

    Takes raw user text, returns a single string:
      "AllowedIPs = 0.0.0.0/5, 8.0.0.0/7, ..., ::/0"
    or "AllowedIPs =" if nothing remains.
    """
    if not allowed_text.strip():
        raise ValueError("Allowed IPs field is empty.")

    allowed_nets = parse_ip_list(allowed_text)
    disallowed_nets = parse_ip_list(disallowed_text) if disallowed_text.strip() else []

    allowed_v4, allowed_v6 = split_networks_by_ip_version(allowed_nets)
    disallowed_v4, disallowed_v6 = split_networks_by_ip_version(disallowed_nets)

    allowed_v4_ranges = nets_to_ranges(allowed_v4)
    allowed_v6_ranges = nets_to_ranges(allowed_v6)

    disallowed_v4_ranges = nets_to_ranges(disallowed_v4)
    disallowed_v6_ranges = nets_to_ranges(disallowed_v6)

    final_v4_ranges = subtract_ranges(allowed_v4_ranges, disallowed_v4_ranges)
    final_v6_ranges = subtract_ranges(allowed_v6_ranges, disallowed_v6_ranges)

    final_v4_nets = ranges_to_networks(final_v4_ranges, 4)
    final_v6_nets = ranges_to_networks(final_v6_ranges, 6)

    all_nets = final_v4_nets + final_v6_nets
    joined = ", ".join(str(n) for n in all_nets)
    return f"AllowedIPs = {joined}"
