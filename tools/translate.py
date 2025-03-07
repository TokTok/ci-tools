#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2025 The TokTok team
import glob
import json
import multiprocessing
import subprocess  # nosec
import textwrap
import xml.dom.minidom as minidom  # nosec
from dataclasses import dataclass
from functools import cache as memoize
from typing import Any
from typing import Optional

import requests
from lib import stage

_AUTOMATED_TRANSLATION = "Automated translation."


@dataclass
class Language:
    # This is the main code. We call the file this code and put it into the
    # language tag in the TS file.
    weblate_code: str
    # If baidu needs a different code, we put it here.
    baidu_code: str
    # If google needs a different code, we put it here.
    google_code: str
    # This code will temporarily be used in the language tag in the TS file,
    # only when running lupdate. Afterwards, we will replace it with the
    # weblate_code.
    lupdate_code: str

    def __init__(
        self,
        weblate_code: str,
        baidu_code: Optional[str] = None,
        google_code: Optional[str] = None,
        lupdate_code: Optional[str] = None,
    ):
        self.weblate_code = weblate_code
        self.baidu_code = baidu_code or weblate_code
        self.google_code = google_code or weblate_code
        self.lupdate_code = lupdate_code or weblate_code


_LANGUAGES: tuple[Language, ...] = (
    Language("ar"),
    Language("be"),
    # Just because German has the same numerusform count.
    Language("ber", lupdate_code="de"),
    Language("bg"),
    Language("bn"),
    Language("cs"),
    Language("da"),
    Language("de"),
    Language("el"),
    Language("eo"),
    Language("es"),
    Language("et"),
    Language("ja"),
    Language("jbo", baidu_code="loj", lupdate_code="zh_CN"),  # 1 numerusform
    Language("fa"),
    Language("fi"),
    Language("fr"),
    Language("gl"),
    Language("hr"),
    Language("he"),
    Language("hu"),
    Language("is"),
    Language("it"),
    Language("lt"),
    Language("lv"),
    Language("ko"),
    Language("kn"),
    Language("mk"),
    Language("nl"),
    Language("nl_BE"),
    Language("li", lupdate_code="nl_LI"),
    Language("nb_NO"),
    Language("pl"),
    Language("pr"),
    Language("pt"),
    Language("pt_BR"),
    Language("ro"),
    Language("ru"),
    Language("si"),
    Language("sk"),
    Language("sl"),
    Language("sq"),
    Language("sr"),
    Language("sr_Latn"),
    Language("sv"),
    Language("sw"),
    Language("ta"),
    Language("tr"),
    Language("ug"),
    Language("uk"),
    Language("ur"),
    Language("vi"),
    Language("zh_CN"),
    Language("zh_TW"),
)

_BAIDU_LANGUAGES = ("jbo", )
_IGNORE_LANGUAGES = ("pr", "nl_BE", "sr_Latn")

_LOCK = multiprocessing.Lock()


@memoize
def lupdate() -> str:
    """Return the path to the lupdate executable."""
    # If "lupdate" is in PATH, it will be used.
    if (subprocess.run(  # nosec
        ["which", "lupdate"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
    ).returncode == 0):
        return "lupdate"
    # Check if we can find it in the Nix store.
    for path in glob.glob("/nix/store/*-qttools-*/bin/lupdate"):
        return path
    raise FileNotFoundError("lupdate not found")


def _normalize(text: str) -> str:
    """Normalize text for printing.

    Replace newlines with spaces and remove leading and trailing whitespace.
    """
    return text.replace("\n", " ").strip()


def _progress_ts(lang: str, current: int, total: int, text: str) -> None:
    """Print the progress of the translation.

    The progress is printed in a colorful message of the form

        "[ current/total ] (lang) text".

    The text is truncated to 80 characters.
    """
    progress = f"{current}/{total}"
    output = f"\r\033[1;34m[ {progress:4} ] ({lang})\033[0m {_normalize(text[:80])}"
    with _LOCK:
        stage.clear()
        print(output, end="", flush=True)


def _progress_done(message: str) -> None:
    """Print a progress message indicating that the process is done."""
    output = f"\r\033[1;34m[  \033[1;32mOK  \033[1;34m]\033[0m {_normalize(message)}"
    with _LOCK:
        stage.clear()
        print(output, flush=True)


def _fix_translation(lang: Language, source: str, text: str) -> str:
    """Fix common translation errors."""
    if not text:
        return text
    # These are %1, %2, etc. which are used for string formatting in Qt.
    # They only go up to 3 at the moment, but we'll be safe and go up to 6.
    for i in tuple(range(1, 6)) + ("n", ):
        if f"%{i}" in source:
            text = text.replace(f"% {i}", f"%{i}")
            if f"%{i}" not in text:
                raise ValueError(
                    f"Missing %{i} in {lang.weblate_code} translation of "
                    f"'{source}': '{text}'")
    if "%" in source:
        text = text.replace("%%", "%")
    if source.startswith(" ") and not text.startswith(" "):
        text = " " + text
    return text


def _baidu_call_translate(lang: Language, text: str) -> str:
    """Uses the Baidu Translate API to translate text to a given language.

    The source language is English. Baidu is decently good at translating
    Lojban. Google Translate doesn't support Lojban. OpenL is hilariously bad.
    E.g. it says that "vimcu lo citri" means "I will eat the lemon" when it
    actually means "remove the history".
    """
    response = requests.post(
        "https://fanyi.baidu.com/ait/text/translate",
        json={
            "domain": "common",
            "from": "en",
            "to": lang.baidu_code,
            "source": "web",
            "query": text,
        },
    )
    response.raise_for_status()
    events = (json.loads(line.removeprefix("data: "))
              for line in response.text.split("\n")
              if line.startswith("data: "))
    translations = (
        para["dst"] for event in events
        if event["data"]["event"] == "Translating" and event["data"]["list"]
        for para in event["data"]["list"])
    return "\n".join(translations)


def _validate_translation(source: str, translation: str) -> bool:
    for i in tuple(range(1, 6)) + ("n", ):
        if (f"%{i}" in source and f"% {i}" not in translation
                and f"%{i}" not in translation):
            return False
    return True


_BLYAT = (
    ("%1", "#TEEHEE#"),
    ("%2", "#BLYAT#"),
    ("%3", "#BLARGH#"),
    ("%n", "12345"),
)


def _blyatyfy(text: str) -> str:
    for key, value in _BLYAT:
        text = text.replace(key, value)
    return text


def _unblyatyfy(text: str) -> str:
    for key, value in _BLYAT:
        text = text.replace(value, key)
    return text


def _baidu_translate(lang: Language, text: str) -> str:
    """Translate text to a given language using Baidu Translate.

    All kinds of hacks here to try and make Baidu Translate work with "%1".
    """
    attempt = _baidu_call_translate(lang, text)
    if not _validate_translation(text, attempt):
        attempt = _baidu_call_translate(lang, text.replace("%", "%%"))
    if not _validate_translation(text, attempt):
        attempt = _unblyatyfy(_baidu_call_translate(lang, _blyatyfy(text)))
    if not _validate_translation(text, attempt):
        raise ValueError(
            f"Failed to translate '{text}' to '{lang.weblate_code}': '{attempt}'"
        )
    return attempt


def _reflow(source: str, translation: str) -> str:
    """Wrap translation text (single line) to the maximum source line length."""
    if "\n" not in source:
        return translation
    # Find the maximum line length in the source text.
    max_length = max(len(line) for line in source.split("\n"))
    # Wrap the translation text to the maximum line length.
    return textwrap.fill(translation, width=max_length, break_long_words=False)


def _translate(lang: Language, current: int, total: int, text: str) -> str:
    """Uses the Google Translate API to translate text to a given language.

    The source language is English.
    """
    _progress_ts(lang.weblate_code, current, total, text)
    if lang.weblate_code in _IGNORE_LANGUAGES:
        return ""
    if lang.weblate_code in _BAIDU_LANGUAGES:
        return _fix_translation(lang, text, _baidu_translate(lang, text))
    response = requests.get(
        "https://translate.googleapis.com/translate_a/single",
        params={
            "client": "gtx",
            "sl": "en",
            "tl": lang.google_code,
            "dt": "t",
            "q": text.replace("\n", " "),
        },
    )
    response.raise_for_status()
    return _fix_translation(
        lang, text, _reflow(text, "".join([x[0] for x in response.json()[0]])))


def _need_translation(lang: Language, source: str,
                      message: minidom.Element) -> list[Any]:
    translation = message.getElementsByTagName("translation")
    if not translation:
        return []
    translated = translation[0].firstChild
    if isinstance(translated, minidom.Text) and translated.data.strip() != "":
        translated.data = _fix_translation(lang, source, translated.data)
    if source == "LTR":
        # Skip the LTR/RTL context. We use it to control the UI. It
        # doesn't need to be translated.
        if isinstance(translated, minidom.Text):
            # Fix up any LTR/RTL values that are not "LTR" or "RTL".
            # We'll default to LTR if we don't know.
            if translated.data and translated.data not in ("LTR", "RTL"):
                translated.data = "LTR"
        return []
    translatorcomment = message.getElementsByTagName("translatorcomment")
    if (translatorcomment
            and isinstance(translatorcomment[0].firstChild, minidom.Text) and
            translatorcomment[0].firstChild.data != _AUTOMATED_TRANSLATION):
        # Skip messages with translator comments. These are probably
        # not meant to be translated.
        return []
    if translation[0].getAttribute("type") != "unfinished":
        return []
    # If the translation node has 1 <numerusform> child, and it's empty,
    # return it.
    numerusform = translation[0].getElementsByTagName("numerusform")
    if len(numerusform) == 1 and not numerusform[0].firstChild:
        return numerusform
    # If the translation node text is empty, fill it in using the
    # translation of source. This is done for all translations that
    # are marked as "unfinished". If they are not marked as
    # "unfinished", empty is assumed to be intentional.
    if translated:
        return []
    return translation


class _TemporaryLanguageCode:

    def __init__(self, lang: Language, file: str):
        self.lang = lang
        self.file = file

    def __enter__(self) -> None:
        """Replace the language code needed by weblate with the lupdate one."""
        if self.lang.lupdate_code == self.lang.weblate_code:
            return
        with open(self.file, "r") as f:
            data = f.read()
        data = data.replace(
            f' language="{self.lang.weblate_code}"',
            f' language="{self.lang.lupdate_code}"',
        )
        with open(self.file, "w") as f:
            f.write(data)

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        """Revert the language code back to the weblate one."""
        if self.lang.lupdate_code == self.lang.weblate_code:
            return
        with open(self.file, "r") as f:
            data = f.read()
        data = data.replace(
            f' language="{self.lang.lupdate_code}"',
            f' language="{self.lang.weblate_code}"',
        )
        with open(self.file, "w") as f:
            f.write(data)


def _translate_todo_list(
    lang: Language,
    todo: list[tuple[str, minidom.Node, minidom.Element]],
    file: str,
    dom: minidom.Document,
) -> None:
    try:
        # Write out changes we may have made in the loop above.
        with open(file, "w") as f:
            dom.writexml(f)
        for i, (source, translation, message) in enumerate(todo):
            translated = _translate(lang, i, len(todo), source)
            if not translated:
                continue
            # Clear the translation node of any existing text.
            translation.childNodes.clear()
            # Add the translation to the translation node.
            translation.appendChild(dom.createTextNode(translated))
            # Add a <translatorcomment> node to the message to indicate
            # that the translation was automated.
            if not message.getElementsByTagName("translatorcomment"):
                # Skip messages with translator comments. These are
                # probably not meant to be translated.
                # continue
                comment = dom.createElement("translatorcomment")
                comment.appendChild(dom.createTextNode(_AUTOMATED_TRANSLATION))
                message.appendChild(comment)
            # Commit to disk every time a translation is done so that we don't
            # lose progress if the script is interrupted.
            with open(file, "w") as f:
                dom.writexml(f)
    finally:
        with _TemporaryLanguageCode(lang, file):
            # Run lupdate for formatting, even if the process is interrupted.
            _progress_ts(
                lang.weblate_code,
                len(todo),
                len(todo),
                subprocess.check_output(  # nosec
                    [
                        lupdate(),
                        "src",
                        "-silent",
                        "-no-obsolete",
                        "-locations",
                        "none",
                        "-ts",
                        file,
                    ],
                    stderr=subprocess.STDOUT,
                ).decode("utf-8"),
            )


def _translate_ts_file(lang: Language, file: str) -> None:
    """Fill in the untranslated translations in a .ts file.

    Doesn't touch anything other than completely empty translations. Empty
    translations are marked with <translation type="unfinished"></translation>.
    """
    with open(file, "r") as f:
        dom = minidom.parse(f)  # nosec
    todo: list[tuple[str, minidom.Node, minidom.Element]] = []
    for context in dom.getElementsByTagName("context"):
        for message in context.getElementsByTagName("message"):
            source = message.getElementsByTagName("source")[0].firstChild
            if not isinstance(source, minidom.Text):
                continue
            translation = _need_translation(lang, source.data, message)
            if not translation:
                continue
            todo.append((source.data, translation[0], message))
    _translate_todo_list(lang, todo, file, dom)


def _translate_language(lang: Language) -> None:
    """Translate the strings in the .ts files for a given language."""
    _translate_ts_file(lang, f"translations/{lang.weblate_code}.ts")


def main() -> None:
    with multiprocessing.Pool() as pool:
        pool.map(_translate_language, _LANGUAGES)
    _progress_done("Translation done.")


if __name__ == "__main__":
    main()
