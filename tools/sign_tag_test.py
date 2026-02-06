#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest
from unittest.mock import MagicMock, patch

from sign_tag import Config, main


class TestSignTag(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config(
            tag="v1.0.0", upstream="origin", verify_only=False, local_only=False
        )

    @patch("lib.git.fetch")
    @patch("lib.git.tag_has_signature")
    @patch("lib.git.sign_tag")
    @patch("lib.git.push_tag")
    def test_sign_and_push(
        self,
        mock_push: MagicMock,
        mock_sign: MagicMock,
        mock_has_sig: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        mock_has_sig.return_value = False
        main(self.config)
        mock_fetch.assert_called_once_with("origin")
        mock_sign.assert_called_once_with("v1.0.0")
        mock_push.assert_called_once_with("v1.0.0", "origin")

    @patch("lib.git.fetch")
    @patch("lib.git.tag_has_signature")
    @patch("lib.git.sign_tag")
    def test_already_signed(
        self, mock_sign: MagicMock, mock_has_sig: MagicMock, mock_fetch: MagicMock
    ) -> None:
        mock_has_sig.return_value = True
        main(self.config)
        mock_sign.assert_not_called()

    @patch("lib.git.fetch")
    @patch("lib.git.tag_has_signature")
    @patch("lib.git.verify_tag")
    def test_verify_only_success(
        self, mock_verify: MagicMock, mock_has_sig: MagicMock, mock_fetch: MagicMock
    ) -> None:
        self.config.verify_only = True
        mock_has_sig.return_value = True
        mock_verify.return_value = True
        main(self.config)
        mock_verify.assert_called_once_with("v1.0.0")

    @patch("lib.git.fetch")
    @patch("lib.git.tag_has_signature")
    @patch("lib.git.verify_tag")
    def test_verify_only_failure(
        self, mock_verify: MagicMock, mock_has_sig: MagicMock, mock_fetch: MagicMock
    ) -> None:
        self.config.verify_only = True
        mock_has_sig.return_value = True
        mock_verify.return_value = False
        with self.assertRaises(SystemExit):
            main(self.config)


if __name__ == "__main__":
    unittest.main()
