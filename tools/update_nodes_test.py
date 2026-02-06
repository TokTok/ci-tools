# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import socket
import unittest
from unittest.mock import MagicMock, patch

from update_nodes import (_IPV4_REGEX, _IPV6_REGEX, Node, _resolve,
                          _resolve_nodes)


class TestUpdateNodes(unittest.TestCase):
    def test_ipv4_regex(self) -> None:
        self.assertTrue(_IPV4_REGEX.match("1.2.3.4"))
        self.assertTrue(_IPV4_REGEX.match("127.0.0.1"))
        self.assertFalse(_IPV4_REGEX.match("1.2.3"))
        self.assertFalse(_IPV4_REGEX.match("a.b.c.d"))

    def test_ipv6_regex(self) -> None:
        self.assertTrue(_IPV6_REGEX.match("2001:0db8:85a3:0000:0000:8a2e:0370:7334"))
        self.assertTrue(_IPV6_REGEX.match("::1"))
        self.assertFalse(_IPV6_REGEX.match("1.2.3.4"))

    def test_node_from_dict(self) -> None:
        data = {
            "ipv4": "1.2.3.4",
            "ipv6": "::1",
            "port": 33445,
            "tcp_ports": [443, 80],
            "public_key": "KEY",
            "maintainer": "Maintainer",
            "location": "Location",
            "status_udp": True,
            "status_tcp": True,
            "version": "1.2.3",
            "motd": "MOTD",
        }
        node = Node.from_dict(data)
        self.assertEqual(node.ipv4, "1.2.3.4")
        self.assertEqual(node.tcp_ports, [80, 443])  # Sorted

    @patch("socket.getaddrinfo")
    def test_resolve_ipv4(self, mock_getaddrinfo: MagicMock) -> None:
        # If it's already an IP, it should return it immediately
        self.assertEqual(_resolve("1.2.3.4", 33445, socket.AF_INET), "1.2.3.4")
        mock_getaddrinfo.assert_not_called()

        # If it's a hostname, it should resolve it
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_DGRAM, 17, "", ("5.6.7.8", 33445))
        ]
        self.assertEqual(_resolve("tox.chat", 33445, socket.AF_INET), "5.6.7.8")

    @patch("socket.getaddrinfo")
    def test_resolve_failure(self, mock_getaddrinfo: MagicMock) -> None:
        mock_getaddrinfo.side_effect = socket.error
        self.assertIsNone(_resolve("invalid.host", 33445, socket.AF_INET))

    @patch("update_nodes._resolve")
    def test_resolve_nodes(self, mock_resolve: MagicMock) -> None:
        node = Node(
            ipv4="tox.chat",
            ipv6=None,
            port=33445,
            tcp_ports=[],
            public_key="K",
            maintainer="M",
            location="L",
            status_udp=True,
            status_tcp=True,
            version="V",
            motd="M",
        )
        mock_resolve.return_value = "1.2.3.4"
        _resolve_nodes([node])
        self.assertEqual(node.ipv4, "1.2.3.4")


if __name__ == "__main__":
    unittest.main()
