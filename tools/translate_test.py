# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest

import translate


class TestTranslateLogic(unittest.TestCase):
    def test_fix_translation(self) -> None:
        lang = translate.Language("eo")
        source = "Hello %1"
        # Fix missing space after %
        self.assertEqual(
            translate._fix_translation(lang, source, "Saluton % 1"), "Saluton %1"
        )
        # Ensure it raises ValueError if %1 is missing
        with self.assertRaises(ValueError):
            translate._fix_translation(lang, source, "Saluton")

    def test_reflow(self) -> None:
        source = "This is a long line\nand another one."
        # max_length of source is 19
        translation = "This is an even longer translation that should be wrapped."
        reflowed = translate._reflow(source, translation)
        # Check that it wrapped
        self.assertIn("\n", reflowed)
        for line in reflowed.split("\n"):
            self.assertLessEqual(len(line), 19)

    def test_blyatyfy(self) -> None:
        text = "Process %1 and %2 with %n"
        blyatyfied = translate._blyatyfy(text)
        self.assertIn("#TEEHEE#", blyatyfied)
        self.assertIn("#BLYAT#", blyatyfied)
        self.assertIn("12345", blyatyfied)
        self.assertEqual(translate._unblyatyfy(blyatyfied), text)

    def test_need_translation(self) -> None:
        from xml.dom import minidom  # nosec

        lang = translate.Language("de")

        def create_message(
            source_text: str,
            translation_text: str = "",
            translation_type: str | None = "unfinished",
            comment: str = "",
        ) -> minidom.Element:
            doc = minidom.Document()
            message = doc.createElement("message")
            source = doc.createElement("source")
            source.appendChild(doc.createTextNode(source_text))
            message.appendChild(source)

            translation = doc.createElement("translation")
            if translation_type:
                translation.setAttribute("type", translation_type)
            if translation_text:
                translation.appendChild(doc.createTextNode(translation_text))
            message.appendChild(translation)

            if comment:
                trans_comment = doc.createElement("translatorcomment")
                trans_comment.appendChild(doc.createTextNode(comment))
                message.appendChild(trans_comment)
            return message

        # Needs translation: unfinished and empty
        msg = create_message("Hello", "")
        self.assertTrue(translate._need_translation(lang, "Hello", msg))

        # Does not need: finished
        msg = create_message("Hello", "", translation_type=None)
        self.assertFalse(translate._need_translation(lang, "Hello", msg))

        # Does not need: has human comment
        msg = create_message("Hello", "", comment="Human comment")
        self.assertFalse(translate._need_translation(lang, "Hello", msg))

        # Does not need: skip LTR
        msg = create_message("LTR", "")
        self.assertFalse(translate._need_translation(lang, "LTR", msg))


if __name__ == "__main__":
    unittest.main()
