#!/usr/bin/env python3
"""
Unit tests for the WireGuard AllowedIPs calculation algorithm.
Run with:
  python3 -m unittest test_wg_ips_core.py
"""
import unittest
import ipaddress

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


if __name__ == "__main__":
    unittest.main()
