"""Prepare a paper / book you are about to read.

For a given text it produces two HTML files in ``media/output/``:

* ``<name>.reading.html``  – the full text with unfamiliar words highlighted;
  tap / hover a highlighted word to see its Chinese meaning.
* ``<name>.glossary.html`` – a pre-generated dictionary of those words
  (phonetic + translation + difficulty + frequency), sorted by frequency.

"Unfamiliar" means: words you have not yet rated as Familiar (familiarity <=
threshold), plus any word that is outside the graded vocabulary but found in the
full ECDICT dictionary.

Usage:
    uv run python -m scripts.prepare_reading media/to_read/paper.pdf
    uv run python -m scripts.prepare_reading media/to_read           # all files
    uv run python -m scripts.prepare_reading paper.txt --max-familiarity 2
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path

from vocab.loader import PROJECT_ROOT, load_dataset
from vocab.models import GRADED_LEVEL_LABELS, Familiarity, WordEntry
from vocab.progress import ProgressStore
from vocab.textscan import (
    LemmaResolver,
    extract_text,
    iter_text_files,
    iter_word_spans,
    lookup_ecdict,
    tokenize,
)

DEFAULT_TARGET = PROJECT_ROOT / "media" / "to_read"
OUTPUT_DIR = PROJECT_ROOT / "media" / "output"

# Familiarity color scheme, matching the web UI.
_FAM_COLOR = {
    1: "#ef4444",
    2: "#f59e0b",
    3: "#84cc16",
    4: "#16c0cc",
    5: "#58585b",
}
_UNKNOWN_COLOR = "#e9d5ff"  # word outside the graded vocabulary


def _clean(text: str) -> str:
    """Normalise ECDICT translation whitespace (drop stray carriage returns)."""

    return text.replace("\\r", "").replace("\r", "").replace("\\n", "\n").strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        nargs="?",
        default=str(DEFAULT_TARGET),
        help="File or directory to prepare (default: media/to_read/).",
    )
    parser.add_argument(
        "--max-familiarity",
        type=int,
        default=int(Familiarity.LEARNING),
        choices=[int(f) for f in Familiarity],
        help="Highlight words at or below this familiarity (default: 2 = "
        "Learning; i.e. not yet Familiar).",
    )
    parser.add_argument(
        "--include-unknown",
        dest="include_unknown",
        action="store_true",
        default=True,
        help="Also highlight words outside the graded vocabulary that are "
        "found in the full ECDICT (default: on).",
    )
    parser.add_argument(
        "--no-unknown",
        dest="include_unknown",
        action="store_false",
        help="Do not consult the full ECDICT for out-of-vocabulary words.",
    )
    return parser.parse_args()


class WordInfo:
    __slots__ = ("headword", "phonetic", "translation", "difficulty", "coca", "familiarity", "in_vocab")

    def __init__(self, headword: str, phonetic: str, translation: str,
                 difficulty: str | None, coca: int | None,
                 familiarity: int | None, in_vocab: bool) -> None:
        self.headword = headword
        self.phonetic = phonetic
        self.translation = translation
        self.difficulty = difficulty
        self.coca = coca
        self.familiarity = familiarity
        self.in_vocab = in_vocab

    def color(self) -> str:
        if not self.in_vocab:
            return _UNKNOWN_COLOR
        return _FAM_COLOR.get(self.familiarity or 1, _FAM_COLOR[1])


def build_target_map(
    text: str,
    dataset: dict[str, WordEntry],
    resolver: LemmaResolver,
    store: ProgressStore,
    max_familiarity: int,
    include_unknown: bool,
) -> dict[str, WordInfo]:
    """Return ``token/headword -> WordInfo`` for words to highlight."""

    targets: dict[str, WordInfo] = {}
    unknown_tokens: set[str] = set()

    for token in set(tokenize(text)):
        base = resolver.resolve(token)
        if base is not None:
            fam = int(store.familiarity(base))
            if fam <= max_familiarity:
                entry = dataset[base]
                info = WordInfo(
                    headword=entry.word,
                    phonetic=entry.phonetic,
                    translation=_clean(entry.translation),
                    difficulty=entry.difficulty,
                    coca=entry.coca,
                    familiarity=fam,
                    in_vocab=True,
                )
                targets[token] = info
                targets.setdefault(base, info)
        elif include_unknown:
            unknown_tokens.add(token)

    if include_unknown and unknown_tokens:
        looked_up = lookup_ecdict(unknown_tokens)
        for token, data in looked_up.items():
            if not data.get("translation"):
                continue
            targets[token] = WordInfo(
                headword=token,
                phonetic=data.get("phonetic", ""),
                translation=_clean(data["translation"]),
                difficulty=None,
                coca=None,
                familiarity=None,
                in_vocab=False,
            )

    return targets


def render_reading_html(title: str, text: str, targets: dict[str, WordInfo]) -> str:
    pieces: list[str] = []
    pos = 0
    for start, end, word in iter_word_spans(text):
        pieces.append(html.escape(text[pos:start]))
        raw = text[start:end]
        info = targets.get(word)
        if info is not None:
            tip = info.translation.split("\n")[0] if info.translation else ""
            pieces.append(
                f'<mark class="hl" style="background:{info.color()}" '
                f'data-tr="{html.escape(info.translation)}" '
                f'data-ph="{html.escape(info.phonetic)}" '
                f'data-hw="{html.escape(info.headword)}" '
                f'title="{html.escape(tip)}">{html.escape(raw)}</mark>'
            )
        else:
            pieces.append(html.escape(raw))
        pos = end
    pieces.append(html.escape(text[pos:]))
    body = "".join(pieces)

    return _READING_TEMPLATE.format(title=html.escape(title), body=body,
                                    count=len(set(t for t in targets.values())))


def render_glossary_html(title: str, targets: dict[str, WordInfo]) -> str:
    # Deduplicate by headword.
    unique: dict[str, WordInfo] = {}
    for info in targets.values():
        unique.setdefault(info.headword.lower(), info)

    def sort_key(info: WordInfo) -> tuple[int, str]:
        return (info.coca if info.coca is not None else 10**9, info.headword.lower())

    rows = []
    for info in sorted(unique.values(), key=sort_key):
        diff = GRADED_LEVEL_LABELS.get(info.difficulty, "—") if info.difficulty else (
            "生词 New" if not info.in_vocab else "—")
        freq = f"#{info.coca}" if info.coca else "—"
        tr = html.escape(info.translation).replace("\n", "<br>")
        rows.append(
            f"<tr><td class='w'>{html.escape(info.headword)}</td>"
            f"<td class='p'>{html.escape(info.phonetic)}</td>"
            f"<td class='t'>{tr}</td>"
            f"<td class='d'>{html.escape(diff)}</td>"
            f"<td class='f'>{freq}</td></tr>"
        )

    return _GLOSSARY_TEMPLATE.format(
        title=html.escape(title), count=len(unique), rows="\n".join(rows)
    )


def prepare_file(
    path: Path,
    dataset: dict[str, WordEntry],
    resolver: LemmaResolver,
    store: ProgressStore,
    args: argparse.Namespace,
) -> None:
    text = extract_text(path)
    targets = build_target_map(
        text, dataset, resolver, store, args.max_familiarity, args.include_unknown
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = path.stem

    reading_path = OUTPUT_DIR / f"{stem}.reading.html"
    glossary_path = OUTPUT_DIR / f"{stem}.glossary.html"
    reading_path.write_text(
        render_reading_html(path.name, text, targets), encoding="utf-8"
    )
    glossary_path.write_text(
        render_glossary_html(path.name, targets), encoding="utf-8"
    )

    unique = len({info.headword.lower() for info in targets.values()})
    print(f"  {path.name}: {unique:,} words to learn")
    print(f"    highlighted : {reading_path.relative_to(PROJECT_ROOT)}")
    print(f"    glossary    : {glossary_path.relative_to(PROJECT_ROOT)}")


def main() -> None:
    args = parse_args()
    target = Path(args.target)
    if not target.exists():
        raise SystemExit(f"error: path not found: {target}")

    files = list(iter_text_files(target))
    if not files:
        raise SystemExit(f"error: no supported files found under {target}")

    dataset = load_dataset()
    resolver = LemmaResolver(dataset)
    store = ProgressStore()

    for path in files:
        try:
            prepare_file(path, dataset, resolver, store, args)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! skipped {path.name}: {exc}")


_READING_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{title} · Reading</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ font-family: Georgia, "Songti SC", serif; max-width: 760px; margin: 0 auto;
    padding: 24px 20px 120px; line-height: 1.9; font-size: 19px; color: #1e293b; }}
  h1 {{ font-size: 20px; font-family: system-ui, sans-serif; color: #475569; }}
  .content {{ white-space: pre-wrap; }}
  mark.hl {{ border-radius: 4px; padding: 0 2px; cursor: pointer; }}
  #panel {{ position: fixed; left: 0; right: 0; bottom: 0; background: #0f172a;
    color: #e2e8f0; padding: 14px 18px; font-family: system-ui, sans-serif;
    font-size: 17px; box-shadow: 0 -4px 20px rgba(0,0,0,.3);
    transform: translateY(110%); transition: transform .2s; }}
  #panel.show {{ transform: translateY(0); }}
  #panel .hw {{ font-size: 20px; font-weight: 700; }}
  #panel .ph {{ color: #38bdf8; margin-left: 8px; }}
  #panel .tr {{ margin-top: 6px; white-space: pre-line; }}
</style></head>
<body>
  <h1>{title} — {count} words highlighted</h1>
  <div class="content">{body}</div>
  <div id="panel"><span class="hw"></span><span class="ph"></span><div class="tr"></div></div>
<script>
  const panel = document.getElementById('panel');
  document.querySelectorAll('mark.hl').forEach(m => {{
    m.addEventListener('click', () => {{
      panel.querySelector('.hw').textContent = m.dataset.hw;
      panel.querySelector('.ph').textContent = m.dataset.ph ? '[' + m.dataset.ph + ']' : '';
      panel.querySelector('.tr').textContent = m.dataset.tr;
      panel.classList.add('show');
    }});
  }});
  document.addEventListener('click', (e) => {{
    if (!e.target.closest('mark.hl') && !e.target.closest('#panel')) panel.classList.remove('show');
  }});
</script>
</body></html>
"""

_GLOSSARY_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{title} · Glossary</title>
<style>
  body {{ font-family: system-ui, "PingFang SC", "Microsoft YaHei", sans-serif;
    max-width: 820px; margin: 0 auto; padding: 24px 18px 80px; color: #1e293b; }}
  h1 {{ font-size: 20px; color: #475569; }}
  input {{ width: 100%; padding: 12px 14px; font-size: 16px; margin: 10px 0 16px;
    border: 1px solid #cbd5e1; border-radius: 10px; box-sizing: border-box; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: 9px 10px; border-bottom: 1px solid #e2e8f0;
    vertical-align: top; }}
  th {{ position: sticky; top: 0; background: #f8fafc; font-size: 13px; color: #64748b; }}
  td.w {{ font-weight: 700; font-size: 17px; white-space: nowrap; }}
  td.p {{ color: #0ea5e9; white-space: nowrap; }}
  td.t {{ font-size: 15px; }}
  td.d, td.f {{ color: #64748b; white-space: nowrap; font-size: 13px; }}
</style></head>
<body>
  <h1>{title} — {count} words</h1>
  <input id="q" placeholder="筛选 / filter words..." oninput="filter()"/>
  <table><thead><tr><th>Word</th><th>音标</th><th>释义 Translation</th>
    <th>Level</th><th>COCA</th></tr></thead>
  <tbody id="rows">
{rows}
  </tbody></table>
<script>
  function filter() {{
    const q = document.getElementById('q').value.toLowerCase();
    document.querySelectorAll('#rows tr').forEach(tr => {{
      tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
    }});
  }}
</script>
</body></html>
"""


if __name__ == "__main__":
    main()
