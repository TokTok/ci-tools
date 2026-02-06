# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest

from update_flathub_descriptor_dependencies import (_normalize,
                                                    extract_version_and_hash,
                                                    map_module_name)


class TestUpdateFlathubDependencies(unittest.TestCase):
    def test_extract_version_and_hash(self) -> None:
        output = """URL: https://example.com/v1.2.3.tar.gz
HASH: deadbeef
"""
        url, hash_val = extract_version_and_hash(output)
        self.assertEqual(url, "https://example.com/v1.2.3.tar.gz")
        self.assertEqual(hash_val, "deadbeef")

    def test_extract_version_and_hash_invalid(self) -> None:
        with self.assertRaises(ValueError):
            extract_version_and_hash("invalid output")

    def test_map_module_name(self) -> None:
        self.assertEqual(map_module_name("libsodium"), "sodium")
        self.assertEqual(map_module_name("c-toxcore"), "toxcore")
        self.assertEqual(map_module_name("other"), "other")

    def test_normalize(self) -> None:
        self.assertEqual(_normalize("My-Repo_Name"), "myreponame")


if __name__ == "__main__":
    unittest.main()
