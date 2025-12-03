#!/usr/bin/env python3
"""
Unit tests for the WireGuard AllowedIPs calculation algorithm.
Run with:
  python3 -m unittest test_wg_ips_core.py
"""
import unittest
import ipaddress
import re

import wg_ips_core as core


class TestParseIpList(unittest.TestCase):
    def test_parse_single_ip(self):
        nets = core.parse_ip_list("10.0.0.1")
        self.assertEqual(len(nets), 1)
        self.assertEqual(str(nets[0]), "10.0.0.1/32")

    def test_parse_cidr(self):
        nets = core.parse_ip_list("10.0.0.0/24")
        self.assertEqual(len(nets), 1)
        self.assertEqual(str(nets[0]), "10.0.0.0/24")

    def test_invalid_ip_raises(self):
        with self.assertRaises(ValueError):
            core.parse_ip_list("10.0.0.999")


class TestRangeSubtraction(unittest.TestCase):
    def test_simple_subtraction_single_range(self):
        # Allowed: 10.0.0.0/24 -> [10.0.0.0 - 10.0.0.255]
        # Disallowed: 10.0.0.128/25 -> [128–255]
        allowed_net = ipaddress.ip_network("10.0.0.0/24")
        disallowed_net = ipaddress.ip_network("10.0.0.128/25")

        allowed_ranges = core.nets_to_ranges([allowed_net])
        disallowed_ranges = core.nets_to_ranges([disallowed_net])

        result_ranges = core.subtract_ranges(allowed_ranges, disallowed_ranges)
        # Should leave [10.0.0.0 – 10.0.0.127] => 10.0.0.0/25
        nets = core.ranges_to_networks(result_ranges, 4)
        self.assertEqual(len(nets), 1)
        self.assertEqual(str(nets[0]), "10.0.0.0/25")


class TestCalculateAllowedIps(unittest.TestCase):
    def test_empty_allowed_raises(self):
        with self.assertRaises(ValueError):
            core.calculate_allowed_ips("", "")

    def test_omit_empty_dis(self):
         result = core.calculate_allowed_ips("0.0.0.0/0", "")
         self.assertEqual(result, "AllowedIPs = 0.0.0.0/0")

    def test_example_from_readme(self):
        allowed = "0.0.0.0/0, ::/0"
        disallowed = "37.27.12.178, 10.74.0.3/32, 10.74.0.1"

        result = core.calculate_allowed_ips(allowed, disallowed)

        # Basic sanity checks on structure
        self.assertTrue(result.startswith("AllowedIPs = 0.0.0.0/5, 8.0.0.0/7"))
        self.assertIn("10.74.0.0/32", result)
        self.assertIn("10.74.0.2/32", result)
        self.assertIn("37.27.12.176/31", result)
        self.assertIn("37.27.12.179/32", result)
        self.assertTrue(result.endswith("128.0.0.0/1, ::/0"))

        # Ensure that disallowed IP itself is not included in any remaining network
        # (quick check across networks containing that IP)
        _, _, disallowed_ip_str, *_ = disallowed.split(",")
        disallowed_ip_str = disallowed_ip_str.strip()
        dis_ip = ipaddress.ip_address("37.27.12.178")

        # Parse result networks
        nets_str = result.split("=", 1)[1].strip()
        nets = [s.strip() for s in nets_str.split(",")]
        parsed_nets = [
            ipaddress.ip_network(n)
            for n in nets
            if ":" not in n and n  # skip IPv6 here
        ]

        for n in parsed_nets:
            self.assertNotIn(dis_ip, n)

    @staticmethod
    def ip_not_in_allowed(ip: str, result_str: str) -> bool:
        ip_obj = ipaddress.ip_address(ip)
        # extract networks
        cidrs = re.findall(r"\d+\.\d+\.\d+\.\d+/\d+", result_str)
        networks = [ipaddress.ip_network(c) for c in cidrs]
        return not any(ip_obj in net for net in networks)

    def test_exclude_cloak_external_ip(self):
        allowed = "0.0.0.0/0"
        disallowed = "37.27.21.100"

        result = core.calculate_allowed_ips(allowed, disallowed)
        self.assertTrue(result.startswith("AllowedIPs = 0.0.0.0/3, 32.0.0.0/6, 36.0.0.0/8, 37.0.0.0/12"))
        self.assertIn("37.16.0.0/13", result)
        self.assertIn("37.24.0.0/15", result)
        self.assertIn("37.26.0.0/16", result)
        self.assertIn("37.27.0.0/20", result)
        self.assertIn("37.27.16.0/22", result)
        self.assertIn("37.27.20.0/24", result)
        self.assertIn("37.27.21.0/26", result)
        self.assertIn("37.27.21.64/27", result)
        self.assertIn("37.27.21.96/30", result)
        self.assertIn("37.27.21.101/32", result)
        self.assertIn("37.27.21.102/31", result)
        self.assertIn("37.27.21.104/29", result)
        self.assertIn("37.27.21.112/28", result)
        self.assertIn("37.27.21.128/25", result)
        self.assertIn("37.27.22.0/23", result)
        self.assertIn("37.27.24.0/21", result)
        self.assertIn("37.27.32.0/19", result)
        self.assertIn("37.27.64.0/18", result)
        self.assertIn("37.27.128.0/17", result)
        self.assertIn("37.28.0.0/14", result)
        self.assertIn("37.32.0.0/11", result)
        self.assertIn("37.64.0.0/10", result)
        self.assertIn("37.128.0.0/9", result)
        self.assertIn("38.0.0.0/7", result)
        self.assertIn("40.0.0.0/5", result)
        self.assertIn("48.0.0.0/4", result)
        self.assertIn("64.0.0.0/2", result)
        self.assertIn("128.0.0.0/1", result)

        self.assertTrue(self.ip_not_in_allowed(disallowed, result))


if __name__ == "__main__":
    unittest.main()
