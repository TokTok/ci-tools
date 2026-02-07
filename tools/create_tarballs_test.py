#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest
from unittest.mock import MagicMock, patch

from create_tarballs import Config, main


class TestCreateTarballs(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config(upload=False, tag="v1.0.0", project_name="ci-tools")

    @patch("create_tarballs.create_tarballs")
    def test_local_create(self, mock_create: MagicMock) -> None:
        main(self.config)
        mock_create.assert_called_once_with("ci-tools", "v1.0.0", ".")

    @patch("create_tarballs.create_tarballs")
    @patch("create_tarballs.upload_tarballs")
    @patch("tempfile.TemporaryDirectory")
    def test_upload_create(
        self, mock_tmp: MagicMock, mock_upload: MagicMock, mock_create: MagicMock
    ) -> None:
        self.config.upload = True
        mock_tmp.return_value.__enter__.return_value = "/tmp/dir"  # nosec
        main(self.config)
        mock_create.assert_called_once_with("ci-tools", "v1.0.0", "/tmp/dir")  # nosec
        mock_upload.assert_called_once_with("v1.0.0", "/tmp/dir")  # nosec

    @patch("subprocess.run")
    @patch("create_tarballs.os.path.join")
    def test_create_tarballs_logic(
        self, mock_join: MagicMock, mock_run: MagicMock
    ) -> None:
        from create_tarballs import create_tarballs

        with patch("tempfile.TemporaryDirectory") as mock_tmp:
            mock_tmp.return_value.__enter__.return_value = "/tmp/dir"  # nosec
            mock_join.side_effect = lambda *args: "/".join(args)
            create_tarballs("ci-tools", "v1.0.0", "/tmp/dir")  # nosec

            # Should call git archive, then gzip, then git archive, then xz
            self.assertEqual(mock_run.call_count, 4)

            # Verify first call (gzip)
            mock_run.assert_any_call(
                [
                    "git",
                    "archive",
                    "--format=tar",
                    "--prefix=ci-tools-v1.0.0/",
                    "v1.0.0",
                    "--output=/tmp/dir/v1.0.0.tar",  # nosec
                ],
                check=True,
            )
            mock_run.assert_any_call(
                ["gzip", "-nf", "/tmp/dir/v1.0.0.tar"], check=True  # nosec
            )


if __name__ == "__main__":
    unittest.main()
