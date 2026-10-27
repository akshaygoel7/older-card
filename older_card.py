#!/usr/bin/env python3
"""Older Card: one remembrance line, taken only from the older note.

A later retelling may be vivid and still unusable. A local model may write
the line. The line is kept only when every content word already appears on
the older card. A word that shows up only in the later retelling is borrowed,
and the line is thrown away. The card's own first sentence stays.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_MODEL = "gemma3:1b"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

FUNCTION = {
    "a", "an", "the", "to", "of", "and", "or", "for", "in", "on", "at",
    "into", "with", "from", "before", "after", "about", "where", "when",
    "she", "he", "her", "his", "it", "was", "were",
}

NUMBERS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "1": "1", "2": "2", "3": "3", "4": "4", "5": "5",
    "6": "6", "7": "7", "8": "8", "9": "9", "10": "10",
}

STOP = FUNCTION | {
    "also", "that", "this", "them", "then", "there", "kept", "read",
}


def tokens(text: str) -> list[str]:
    found = []
    for raw in re.findall(r"[A-Za-z0-9']+", text):
        word = raw.lower().strip("'")
        if word:
            found.append(word)
    return found


def content_words(text: str) -> set[str]:
    return {word for word in tokens(text) if word not in FUNCTION and word not in NUMBERS}


def first_sentence(text: str) -> str:
    cleaned = " ".join(text.split())
    match = re.search(r"[.!?]", cleaned)
    if match is None:
        return cleaned
    return cleaned[: match.end()].strip()


def number_pairs(text: str) -> list[tuple[str, str]]:
    words = tokens(text)
    pairs = []
    for index, word in enumerate(words):
        number = NUMBERS.get(word)
        if number is None:
            continue
        for nxt in words[index + 1 : index + 4]:
            if nxt in NUMBERS or nxt in STOP or len(nxt) <= 3:
                continue
            pairs.append((number, nxt))
            break
    return pairs


def digits(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def accept(card: str, later: str, line: str) -> bool:
    """Keep a model line only when it could have been copied from the card."""
    line_words = tokens(line)
    if not line_words:
        return False
    card_words = set(tokens(card))
    later_only = set(tokens(later)) - card_words
    if any(word in later_only and word not in FUNCTION for word in line_words):
        return False
    if any(word not in card_words and word not in FUNCTION for word in line_words):
        return False
    if not digits(line) <= digits(card):
        return False
    allowed = set(number_pairs(card))
    if any(pair not in allowed for pair in number_pairs(line)):
        return False
    named = content_words(card)
    if named and not (named & content_words(line)):
        return False
    return True


def rejection_reason(card: str, later: str, model_line: str) -> str:
    line_words = tokens(model_line)
    if not line_words:
        return "the model did not return a line, so the card's first sentence stayed"
    card_words = set(tokens(card))
    later_only = set(tokens(later)) - card_words
    borrowed = [word for word in line_words if word in later_only and word not in FUNCTION]
    if borrowed:
        return "the model borrowed a word from the later retelling, so the line was thrown away"
    unknown = [word for word in line_words if word not in card_words and word not in FUNCTION]
    if unknown:
        return "the model added a word the card never used, so the line was thrown away"
    if not digits(model_line) <= digits(card):
        return "the model added a year or a count the card never wrote, so the line was thrown away"
    allowed = set(number_pairs(card))
    if any(pair not in allowed for pair in number_pairs(model_line)):
        return "the model moved a number onto a different word, so the line was thrown away"
    if content_words(card) and not (content_words(card) & content_words(model_line)):
        return "the model dropped the thing the card named, so the line was thrown away"
    return "the model line was not kept, so the card's first sentence stayed"


def parse_model_line(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            return ""
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return ""
    if not isinstance(payload, dict):
        return ""
    line = payload.get("line", "")
    return line.strip() if isinstance(line, str) else ""


def parse_pile(text: str) -> list[dict[str, str]]:
    records = []
    for block in re.split(r"\n---\n", text.strip()):
        card_lines: list[str] = []
        later_lines: list[str] = []
        mode = None
        for line in block.splitlines():
            heading = line.strip().upper()
            if heading == "CARD":
                mode = "card"
                continue
            if heading == "LATER":
                mode = "later"
                continue
            if mode == "card":
                card_lines.append(line)
            elif mode == "later":
                later_lines.append(line)
        card = " ".join(" ".join(card_lines).split())
        later = " ".join(" ".join(later_lines).split())
        if card:
            records.append({"card": card, "later": later})
    return records


def ask_ollama(card: str, later: str, model: str, url: str, timeout: float) -> str:
    prompt = (
        "Write one remembrance line for an ofrenda. "
        "Use only words that already appear on the older card. "
        "Do not use the later retelling. "
        "Do not add a year, a place, a dish, a person, or a feeling the card does not contain. "
        "Do not say anyone died, married, or was famous. "
        'Reply as JSON: {"line":"..."}\n\n'
        f"Older card:\n{card}\n\n"
        f"Later retelling, which you must not use:\n{later}"
    )
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_predict": 80},
        }
    ).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode())
    return parse_model_line(str(payload.get("response", "")))


def remember_one(record: dict[str, str], ask) -> dict:
    card = record["card"]
    later = record["later"]
    kept_card = first_sentence(card)
    started = time.perf_counter()
    try:
        model_line = ask(card, later)
        error = ""
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        model_line = ""
        error = str(exc)
    elapsed = round(time.perf_counter() - started, 2)
    if model_line and accept(card, later, model_line):
        kept = model_line
        path = "model"
        reason = "every content word is already on the older card"
    else:
        kept = kept_card
        path = "fallback"
        if error:
            reason = "the model was unreachable, so the card's first sentence stayed"
        else:
            reason = rejection_reason(card, later, model_line)
    return {
        "card": card,
        "later": later,
        "line": kept,
        "path": path,
        "model_line": model_line,
        "reason": reason,
        "seconds": elapsed,
    }


def remember_pile(records: list[dict[str, str]], ask) -> dict:
    rows = [remember_one(record, ask) for record in records]
    return {
        "items": rows,
        "count": len(rows),
        "model_kept": sum(1 for row in rows if row["path"] == "model"),
        "thrown_away": sum(1 for row in rows if row["path"] == "fallback"),
    }


def render_text(report: dict) -> str:
    lines = [
        f"{report['count']} cards",
        f"model kept {report['model_kept']}",
        f"thrown away {report['thrown_away']}",
        "",
    ]
    for index, row in enumerate(report["items"], start=1):
        lines.append(f"{index}. {row['line']}")
        lines.append(f"   {row['reason']}")
        if row["model_line"] and row["path"] != "model":
            lines.append(f"   model said: {row['model_line']}")
        lines.append(f"   later retelling: {row['later']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_html(report: dict) -> str:
    cards = []
    for row in report["items"]:
        rejected = ""
        if row["model_line"] and row["path"] != "model":
            rejected = f"<p class='rejected'>Thrown away: {escape(row['model_line'])}</p>"
        cards.append(
            "<article>"
            f"<h2>{escape(row['line'])}</h2>"
            f"<p class='meta'>{escape(row['reason'])}</p>"
            f"<p class='source'>Older card: {escape(row['card'])}</p>"
            f"<p class='later'>Later retelling: {escape(row['later'])}</p>"
            f"{rejected}"
            "</article>"
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Older Card</title>
<style>
  body {{ margin: 0; background: #f6f1e8; color: #231f20; font: 18px/1.45 Georgia, serif; }}
  main {{ max-width: 760px; margin: 0 auto; padding: 48px 24px 80px; }}
  h1 {{ font-weight: 500; font-size: 42px; margin: 0 0 8px; }}
  .tally {{ color: #671912; margin: 0 0 32px; }}
  article {{ background: white; border: 1px solid #e4d3c4; padding: 20px 22px; margin: 0 0 16px; }}
  h2 {{ font-size: 22px; font-weight: 500; margin: 0 0 8px; }}
  .meta {{ margin: 0 0 10px; color: #3d5f58; font: 14px/1.4 ui-monospace, monospace; }}
  .source {{ margin: 0 0 6px; color: #5c564e; }}
  .later {{ margin: 0; color: #8a6a4a; }}
  .rejected {{ margin: 12px 0 0; color: #8a3b32; font: 14px/1.4 ui-monospace, monospace; }}
</style>
</head>
<body>
<main>
  <h1>Older Card</h1>
  <p class="tally">{report['count']} cards · model kept {report['model_kept']} · thrown away {report['thrown_away']}</p>
  {''.join(cards)}
</main>
</body>
</html>
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Keep a remembrance line that the older card can support.")
    parser.add_argument("pile", type=Path, help="Text file of CARD / LATER pairs, separated by ---")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--url", default=OLLAMA_URL)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--rules-only", action="store_true", help="Do not call the model")
    parser.add_argument("--json", type=Path, help="Write the report JSON here")
    parser.add_argument("--html", type=Path, help="Write a page of the same report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = parse_pile(args.pile.read_text())
    if not records:
        print("The pile is empty.", file=sys.stderr)
        return 1

    def ask(card: str, later: str) -> str:
        if args.rules_only:
            return ""
        return ask_ollama(card, later, args.model, args.url, args.timeout)

    report = remember_pile(records, ask)
    report["model"] = None if args.rules_only else args.model
    sys.stdout.write(render_text(report))
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n")
    if args.html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(render_html(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
