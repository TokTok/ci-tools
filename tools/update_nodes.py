#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2025-2026 The TokTok team
import argparse
import json
import re
import socket
import subprocess  # nosec
from dataclasses import asdict, dataclass
from functools import cache as memoize
from typing import Any, Optional

import requests
from lib import git

_IPV4_REGEX = re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
# https://stackoverflow.com/a/17871737
_IPV6_REGEX = re.compile(
    r"(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}"
    r"|([0-9a-fA-F]{1,4}:){1,7}:"
    r"|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}"
    r"|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}"
    r"|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}"
    r"|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}"
    r"|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}"
    r"|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})"
    r"|:((:[0-9a-fA-F]{1,4}){1,7}|:)"
    r"|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}"
    r"|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]"
    r"|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])"
    r"|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))"
)


@dataclass
class Config:
    url: str
    output: str


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="""
    Downloads the list of nodes from the given URL, resolves the domains to IP
    addresses and saves the result to a JSON file.
    """)
    parser.add_argument(
        "--url",
        help="URL to download the nodes from",
        required=False,
        default="https://nodes.tox.chat/json",
    )
    parser.add_argument(
        "--output",
        help="Output JSON file",
        required=False,
        default=git.root_dir() / "res" / "nodes.json",
    )
    return Config(**vars(parser.parse_args()))


@dataclass
class Node:
    ipv4: Optional[str]
    ipv6: Optional[str]
    port: int
    tcp_ports: list[int]
    public_key: str
    maintainer: str
    location: str
    status_udp: bool
    status_tcp: bool
    version: str
    motd: str

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Node":
        return Node(
            ipv4=data.get("ipv4"),
            ipv6=data.get("ipv6"),
            port=data["port"],
            tcp_ports=sorted(data["tcp_ports"]),
            public_key=data["public_key"],
            maintainer=data["maintainer"],
            location=data["location"],
            status_udp=data["status_udp"],
            status_tcp=data["status_tcp"],
            version=data["version"],
            motd=data["motd"],
        )


def _get_nodes(config: Config) -> list[Node]:
    response = requests.get(config.url)
    response.raise_for_status()
    return [Node.from_dict(node) for node in response.json()["nodes"]]


@memoize
def _resolve(host: str, port: int, family: socket.AddressFamily) -> Optional[str]:
    """Resolve a hostname to an IP address."""
    if _IPV4_REGEX.match(host) or _IPV6_REGEX.match(host):
        return host
    try:
        result = socket.getaddrinfo(host, port, family, socket.SOCK_DGRAM)
        if not result:
            return None
        address = result[0][4][0]
        if not isinstance(address, str):
            return None
        print(f"Resolved {host}:{port} ({family.name}) to {address}")
        return address
    except socket.error:
        return None


def _resolve_nodes(nodes: list[Node]) -> None:
    for node in nodes:
        if node.ipv4:
            node.ipv4 = _resolve(node.ipv4, node.port, socket.AF_INET)
        if node.ipv6:
            node.ipv6 = _resolve(node.ipv6, node.port, socket.AF_INET6)


def main(config: Config) -> None:
    nodes = _get_nodes(config)
    _resolve_nodes(nodes)
    with open(config.output, "w") as f:
        json.dump(
            {"nodes": [asdict(node) for node in nodes if node.ipv4 or node.ipv6]},
            f,
            indent=2,
        )
    try:
        # If prettier exists in $PATH, use it to format the output. Ignore
        # not found, but check for any other errors.
        subprocess.check_call(["prettier", "--write", config.output])  # nosec
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    main(parse_args())
