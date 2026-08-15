"""FastAPI application: JSON API + static web UI for the vocabulary trainer."""

from __future__ import annotations

import random
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .ignore import IgnoreStore
from .loader import load_dataset
from .mastered import MasteredStore
from .models import (
    FAMILIARITY_LABELS,
    GRADED_LEVEL_LABELS,
    GRADED_LEVELS,
    Familiarity,
    WordEntry,
)
from .progress import ProgressStore
from .reading import build_index, clean, glossary_entries, render_reading_body
from .reading_progress import ReadingProgressStore
from .textscan import SUPPORTED_SUFFIXES, LemmaResolver, extract_text, lookup_ecdict
from .webpage import WebpageFetchError, fetch_webpage_text
from .word_shooter import mastery_response

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "static"
UPLOAD_DIR = PROJECT_ROOT / "media" / "uploads"


class VocabService:
    """Holds the immutable dataset plus the learner progress store."""

    def __init__(self) -> None:
        self.dataset: dict[str, WordEntry] = load_dataset()
        self.progress = ProgressStore()
        self.ignore = IgnoreStore()
        self.mastered = MasteredStore()
        self.reading_progress = ReadingProgressStore()
        self.resolver = LemmaResolver(self.dataset)
        # Pre-sort each difficulty level by frequency (most common first).
        self.by_level: dict[str, list[str]] = {}
        for level in GRADED_LEVELS:
            words = [
                key
                for key, entry in self.dataset.items()
                if level in entry.levels
            ]
            words.sort(key=self._freq_key)
            self.by_level[level] = words
        self.all_words: list[str] = sorted(self.dataset, key=self._freq_key)

    def _freq_key(self, key: str) -> tuple[int, str]:
        rank = self.dataset[key].frequency_rank
        return (rank if rank is not None else 10**9, key)

    def pool(self, level: str | None) -> list[str]:
        if level and level in self.by_level:
            return self.by_level[level]
        return self.all_words

    def study_queue(
        self,
        level: str | None,
        max_familiarity: int,
        limit: int,
        min_familiarity: int = 1,
    ) -> list[dict]:
        lo = max(1, min(5, min_familiarity))
        hi = max(1, min(5, max_familiarity))
        if lo > hi:
            lo, hi = hi, lo
        out: list[dict] = []
        for key in self.pool(level):
            # Words parked in the ignore / mastered pools are outside the
            # 5-level process and must never surface in the flashcard queue.
            if self.ignore.contains(key) or self.mastered.contains(key):
                continue
            fam = int(self.progress.familiarity(key))
            if lo <= fam <= hi:
                out.append(self._entry_payload(key))
                if len(out) >= limit:
                    break
        return out

    def _entry_payload(self, key: str) -> dict:
        entry = self.dataset[key]
        fam = self.progress.familiarity(key)
        data = entry.to_dict()
        data["familiarity"] = int(fam)
        data["familiarity_label"] = fam.label
        return data

    def stats(self, level: str | None) -> dict:
        pool = self.pool(level)
        counts = self.progress.counts(pool)
        return {
            "total": len(pool),
            "counts": {str(k): v for k, v in counts.items()},
        }

    # ---------------------------------------------------------- uploads
    def save_upload(self, filename: str, content: bytes) -> Path:
        """Persist an uploaded file safely under the uploads folder."""

        safe = Path(filename or "upload.txt").name or "upload.txt"
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        path = UPLOAD_DIR / safe
        path.write_bytes(content)
        return path

    def list_uploads(self) -> list[dict]:
        """Return previously uploaded, readable files, newest first."""

        if not UPLOAD_DIR.exists():
            return []
        items = []
        for p in UPLOAD_DIR.iterdir():
            if not p.is_file():
                continue
            if p.suffix and p.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            stat = p.stat()
            bp = self.reading_progress.get(p.name)
            items.append(
                {
                    "name": p.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "percent": bp.percent if bp is not None else None,
                    "scroll": bp.scroll if bp is not None else 0,
                }
            )
        items.sort(key=lambda x: x["modified"], reverse=True)
        return items

    def resolve_upload(self, name: str) -> Path:
        """Safely resolve an existing upload by name."""

        safe = Path(name or "").name
        path = UPLOAD_DIR / safe
        if not safe or not path.is_file():
            raise HTTPException(status_code=404, detail="file not found")
        return path

    def delete_upload(self, name: str) -> dict:
        """Delete a book, its unread tracked words, and reading position."""

        path = self.resolve_upload(name)
        stored_name = path.name
        book_words = self.book_wordlist(path)["words"]
        unread = {
            item["headword"]
            for item in book_words
            if item.get("familiarity") == int(Familiarity.UNFAMILIAR)
            and self.progress.get(item["headword"]) is not None
        }
        removed_words = self.progress.remove_many(unread)
        path.unlink()
        self.reading_progress.remove(stored_name)
        return {"name": stored_name, "removed_words": removed_words}

    def read_book(
        self, path: Path, max_familiarity: int, min_familiarity: int = 1
    ) -> dict:
        """Extract, analyze, register words, and render a reading payload."""

        if path.suffix and path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise HTTPException(status_code=400, detail=f"unsupported file type: {path.suffix}")
        try:
            text = extract_text(path)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"could not read file: {exc}")
        return self._reading_payload(
            text, path.name, max_familiarity, min_familiarity=min_familiarity
        )

    def read_webpage(
        self, url: str, max_familiarity: int, min_familiarity: int = 1
    ) -> dict:
        """Download a public webpage and render its readable text."""

        try:
            page = fetch_webpage_text(url)
        except WebpageFetchError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload = self._reading_payload(
            page.text,
            page.title,
            max_familiarity,
            min_familiarity=min_familiarity,
            register_words=False,
        )
        payload["source_url"] = page.url
        payload["track_progress"] = False
        return payload

    def _reading_payload(
        self,
        text: str,
        name: str,
        max_familiarity: int,
        *,
        min_familiarity: int = 1,
        register_words: bool = True,
    ) -> dict:
        """Analyze text, register its words, and build a reader response."""

        if not text.strip():
            raise HTTPException(status_code=400, detail="no readable text found")
        max_familiarity = max(1, min(5, max_familiarity))
        min_familiarity = max(1, min(5, min_familiarity))
        if min_familiarity > max_familiarity:
            min_familiarity, max_familiarity = max_familiarity, min_familiarity
        index = self.analyze(text)
        added = 0
        if register_words:
            added = self.progress.register_words(
                {i.headword for i in index.values() if not i.excluded}
            )
        body = render_reading_body(text, index, max_familiarity, min_familiarity)
        highlighted = sum(
            1
            for i in index.values()
            if not i.excluded and min_familiarity <= i.familiarity <= max_familiarity
        )
        return {
            "name": name,
            "body": body,
            "unique_words": len({i.headword.lower() for i in index.values()}),
            "highlighted": highlighted,
            "added": added,
        }

    def book_wordlist(self, path: Path) -> dict:
        """Analyze an existing book and return its words for a glossary view.

        Unlike :meth:`read_book`, no HTML body is rendered and progress is left
        untouched: this is a read-only view of the book's vocabulary, grouped by
        familiarity level on the client.
        """

        if path.suffix and path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise HTTPException(status_code=400, detail=f"unsupported file type: {path.suffix}")
        try:
            text = extract_text(path)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"could not read file: {exc}")
        if not text.strip():
            raise HTTPException(status_code=400, detail="no readable text found")
        index = self.analyze(text)
        words = [
            w.to_dict()
            for w in glossary_entries(index, None, sort_by_frequency=False)
        ]
        return {"name": path.name, "count": len(words), "words": words}

    def analyze(self, text: str):
        index = build_index(text, self.dataset, self.resolver, self.progress)
        # Words in the ignore pool (names, proper nouns, ...) or the mastered
        # pool live outside the 5-level process.  They stay in the index so the
        # reader can still tap them (and pull them back into learning), but are
        # flagged so they are never highlighted, registered, or listed in the
        # glossary.
        for info in index.values():
            if self.ignore.contains(info.headword) or self.mastered.contains(
                info.headword
            ):
                info.excluded = True
        return index


class ReviewRequest(BaseModel):
    word: str
    response: str = Field(pattern="^(again|hard|good|easy)$")


class FamiliarityRequest(BaseModel):
    word: str
    level: int = Field(ge=1, le=5)


class AdjustRequest(BaseModel):
    word: str
    delta: int = Field(ge=-4, le=4)


class WordRequest(BaseModel):
    word: str


class OpenBookRequest(BaseModel):
    name: str
    max_familiarity: int = Field(default=2, ge=1, le=5)
    min_familiarity: int = Field(default=1, ge=1, le=5)


class OnlineReadingRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    max_familiarity: int = Field(default=2, ge=1, le=5)
    min_familiarity: int = Field(default=1, ge=1, le=5)


class ReadingProgressRequest(BaseModel):
    name: str
    percent: int = Field(ge=0, le=100)
    scroll: int = Field(default=0, ge=0)


class ShooterWordResult(BaseModel):
    word: str
    correct_count: int = Field(ge=0)
    wrong_count: int = Field(ge=0)


class ShooterResultsRequest(BaseModel):
    words: list[ShooterWordResult] = Field(max_length=100)


def create_app() -> FastAPI:
    app = FastAPI(title="English Vocabulary Trainer")
    service = VocabService()

    @app.get("/api/meta")
    def meta() -> dict:
        return {
            "familiarity": [
                {"level": int(level), "label": label}
                for level, label in FAMILIARITY_LABELS.items()
            ],
            "difficulty_levels": [
                {"id": lid, "label": GRADED_LEVEL_LABELS[lid]} for lid in GRADED_LEVELS
            ],
        }

    @app.get("/api/stats")
    def stats(level: str | None = None) -> dict:
        return service.stats(level)

    @app.get("/api/study")
    def study(
        level: str | None = None,
        max_familiarity: int = 3,
        min_familiarity: int = 1,
        limit: int = 20,
    ) -> dict:
        max_familiarity = max(1, min(5, max_familiarity))
        min_familiarity = max(1, min(5, min_familiarity))
        limit = max(1, min(100, limit))
        return {
            "words": service.study_queue(
                level, max_familiarity, limit, min_familiarity=min_familiarity
            )
        }

    @app.get("/api/word/{word}")
    def word(word: str) -> dict:
        key = word.lower()
        if key not in service.dataset:
            raise HTTPException(status_code=404, detail="word not found")
        return service._entry_payload(key)

    @app.get("/api/search")
    def search(q: str, limit: int = 20) -> dict:
        q = q.strip().lower()
        if not q:
            return {"words": []}
        matches = [k for k in service.all_words if k.startswith(q)][:limit]
        return {"words": [service._entry_payload(k) for k in matches]}

    @app.post("/api/review")
    def review(req: ReviewRequest) -> dict:
        key = req.word.lower()
        if key not in service.dataset:
            raise HTTPException(status_code=404, detail="word not found")
        fam = service.progress.record(key, req.response)
        return {"word": key, "familiarity": int(fam), "familiarity_label": fam.label}

    @app.get("/api/word-shooter/session")
    def shooter_session(
        min_familiarity: int = 1,
        max_familiarity: int = 3,
        limit: int = 8,
    ) -> dict:
        """Return words in a familiarity range with Chinese translations."""

        limit = max(10, min(100, limit))
        min_familiarity = max(1, min(5, min_familiarity))
        max_familiarity = max(1, min(5, max_familiarity))
        candidates = service.study_queue(
            None, max_familiarity, 5000,
            min_familiarity=min_familiarity,
        )
        words = [item for item in candidates if clean(item.get("translation", ""))]
        random.Random(time.time_ns()).shuffle(words)
        return {"words": words[:limit]}

    @app.post("/api/word-shooter/results")
    def shooter_results(req: ShooterResultsRequest) -> dict:
        updated = []
        for item in req.words:
            key = item.word.lower()
            if key not in service.dataset:
                raise HTTPException(status_code=404, detail=f"word not found: {key}")
            response = mastery_response(item.correct_count, item.wrong_count)
            if response is None:
                continue
            fam = service.progress.record(key, response)
            updated.append({"word": key, "response": response, "familiarity": int(fam)})
        return {"updated": updated}

    @app.post("/api/familiarity")
    def set_familiarity(req: FamiliarityRequest) -> dict:
        """Set a word to an exact familiarity level.

        Explicitly grading a word means it is being actively tracked, so it is
        also pulled back out of the ignore / mastered pools (a no-op for the
        flashcard and *my words* callers, which only grade tracked words).
        """

        key = req.word.lower()
        service.ignore.remove(key)
        service.mastered.remove(key)
        fam = service.progress.set_familiarity(key, req.level)
        return {"word": key, "familiarity": int(fam), "familiarity_label": fam.label}

    @app.post("/api/familiarity/adjust")
    def adjust_familiarity(req: AdjustRequest) -> dict:
        """Nudge a word's familiarity up or down by ``delta`` (clamped 1..5).

        Used by *read & mark* to rank a word higher / lower with one tap; it
        also pulls the word back into the learning pool if it was ignored or
        mastered.
        """

        key = req.word.lower()
        service.ignore.remove(key)
        service.mastered.remove(key)
        current = int(service.progress.familiarity(key))
        new_level = max(1, min(5, current + req.delta))
        fam = service.progress.set_familiarity(key, new_level)
        return {"word": key, "familiarity": int(fam), "familiarity_label": fam.label}

    @app.post("/api/familiarity/reduce")
    def reduce_familiarity(req: WordRequest) -> dict:
        """Mark a word as not known while reading -> drop to Unfamiliar.

        Tapping a word in *read & mark* also pulls it back into the normal
        learning pool: if it was parked in the ignore or mastered list, it is
        removed from there so it behaves like every other tracked word again.
        """

        key = req.word.lower()
        service.ignore.remove(key)
        service.mastered.remove(key)
        fam = service.progress.set_familiarity(key, int(Familiarity.UNFAMILIAR))
        return {"word": key, "familiarity": int(fam), "familiarity_label": fam.label}

    # ------------------------------------------------------------ uploads
    @app.get("/api/uploads")
    def list_uploads() -> dict:
        return {"files": service.list_uploads()}

    @app.delete("/api/uploads")
    def delete_upload(name: str) -> dict:
        result = service.delete_upload(name)
        return {**result, "deleted": True}

    @app.post("/api/reading/prepare")
    async def prepare_reading(
        file: UploadFile = File(...),
        max_familiarity: int = Form(2),
        min_familiarity: int = Form(1),
    ) -> dict:
        content = await file.read()
        path = service.save_upload(file.filename or "upload.txt", content)
        return service.read_book(path, max_familiarity, min_familiarity)

    @app.post("/api/reading/open")
    def open_reading(req: OpenBookRequest) -> dict:
        path = service.resolve_upload(req.name)
        return service.read_book(path, req.max_familiarity, req.min_familiarity)

    @app.post("/api/reading/webpage")
    def open_webpage(req: OnlineReadingRequest) -> dict:
        return service.read_webpage(req.url, req.max_familiarity, req.min_familiarity)

    @app.post("/api/reading/wordlist")
    def reading_wordlist(req: OpenBookRequest) -> dict:
        path = service.resolve_upload(req.name)
        return service.book_wordlist(path)

    @app.get("/api/reading/progress")
    def get_reading_progress(name: str) -> dict:
        bp = service.reading_progress.get(name)
        if bp is None:
            return {"name": name, "percent": None, "scroll": 0}
        return {"name": name, "percent": bp.percent, "scroll": bp.scroll}

    @app.post("/api/reading/progress")
    def set_reading_progress(req: ReadingProgressRequest) -> dict:
        # Only track progress for files that still exist as uploads.
        service.resolve_upload(req.name)
        bp = service.reading_progress.set(req.name, req.percent, req.scroll)
        return {"name": req.name, "percent": bp.percent, "scroll": bp.scroll}

    @app.post("/api/dictionary/prepare")
    async def prepare_dictionary(
        file: UploadFile = File(...),
        max_familiarity: int | None = Form(None),
    ) -> dict:
        content = await file.read()
        path = service.save_upload(file.filename or "upload.txt", content)
        if path.suffix and path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise HTTPException(status_code=400, detail=f"unsupported file type: {path.suffix}")
        try:
            text = extract_text(path)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"could not read file: {exc}")
        if not text.strip():
            raise HTTPException(status_code=400, detail="no readable text found")
        index = service.analyze(text)
        added = service.progress.register_words(
            {i.headword for i in index.values() if not i.excluded}
        )
        cap = None if max_familiarity in (None, 0) else max(1, min(5, max_familiarity))
        words = [w.to_dict() for w in glossary_entries(index, cap)]
        return {"name": path.name, "count": len(words), "words": words, "added": added}

    # ------------------------------------------------------- my words
    @app.get("/api/mywords/summary")
    def mywords_summary() -> dict:
        counts = service.progress.counts()
        return {
            "levels": [
                {
                    "level": int(level),
                    "label": FAMILIARITY_LABELS[level],
                    "count": counts[int(level)],
                }
                for level in Familiarity
            ]
        }

    @app.get("/api/mywords")
    def mywords(level: int, limit: int = 1000) -> dict:
        level = max(1, min(5, level))
        keys = [
            k
            for k in service.progress.words_at(level)
            if not service.ignore.contains(k) and not service.mastered.contains(k)
        ]
        out: list[dict] = []
        missing: list[str] = []
        for key in keys:
            entry = service.dataset.get(key)
            if entry is not None:
                out.append(
                    {
                        "word": entry.word,
                        "phonetic": entry.phonetic,
                        "translation": clean(entry.translation),
                        "familiarity": level,
                    }
                )
            else:
                missing.append(key)
                out.append(
                    {"word": key, "phonetic": "", "translation": "", "familiarity": level}
                )

        if missing:
            found = lookup_ecdict(set(missing))
            for item in out:
                data = found.get(item["word"].lower())
                if data and not item["translation"]:
                    item["phonetic"] = data.get("phonetic", "")
                    item["translation"] = clean(data.get("translation", ""))

        out.sort(key=lambda x: x["word"].lower())
        return {
            "level": level,
            "label": FAMILIARITY_LABELS[Familiarity(level)],
            "total": len(out),
            "words": out[: max(1, min(5000, limit))],
        }

    # ---------------------------------------------------------- ignore list
    @app.post("/api/mywords/ignore")
    def ignore_word(req: WordRequest) -> dict:
        """Mark a word as ignored (a name / proper noun not worth learning).

        The word is added to ``data/ignore.json`` and dropped from progress so
        it disappears from the familiarity buckets and is filtered out of every
        future upload.
        """

        key = req.word.strip().lower()
        if not key:
            raise HTTPException(status_code=400, detail="empty word")
        service.ignore.add(key)
        service.progress.remove(key)
        return {"word": key, "ignored": True}

    @app.post("/api/mywords/unignore")
    def unignore_word(req: WordRequest) -> dict:
        """Remove a word from the ignore list so it is tracked again."""

        key = req.word.strip().lower()
        removed = service.ignore.remove(key)
        return {"word": key, "ignored": False, "removed": removed}

    @app.get("/api/mywords/ignored")
    def ignored_words() -> dict:
        keys = service.ignore.all()
        out: list[dict] = []
        missing: list[str] = []
        for key in keys:
            entry = service.dataset.get(key)
            if entry is not None:
                out.append(
                    {
                        "word": entry.word,
                        "phonetic": entry.phonetic,
                        "translation": clean(entry.translation),
                    }
                )
            else:
                missing.append(key)
                out.append({"word": key, "phonetic": "", "translation": ""})

        if missing:
            found = lookup_ecdict(set(missing))
            for item in out:
                data = found.get(item["word"].lower())
                if data and not item["translation"]:
                    item["phonetic"] = data.get("phonetic", "")
                    item["translation"] = clean(data.get("translation", ""))

        out.sort(key=lambda x: x["word"].lower())
        return {"total": len(out), "words": out}

    # -------------------------------------------------------- mastered list
    @app.post("/api/mywords/master")
    def master_word(req: WordRequest) -> dict:
        """Mark a word as mastered (known well enough to leave the process).

        The word is added to its shard under ``data/mastered/`` and dropped from progress so
        it disappears from the familiarity buckets and is filtered out of every
        future upload, the glossary and the flashcards.
        """

        key = req.word.strip().lower()
        if not key:
            raise HTTPException(status_code=400, detail="empty word")
        service.mastered.add(key)
        service.progress.remove(key)
        return {"word": key, "mastered": True}

    @app.post("/api/mywords/unmaster")
    def unmaster_word(req: WordRequest) -> dict:
        """Remove a word from the mastered list so it is tracked again."""

        key = req.word.strip().lower()
        removed = service.mastered.remove(key)
        return {"word": key, "mastered": False, "removed": removed}

    @app.get("/api/mywords/mastered")
    def mastered_words() -> dict:
        keys = service.mastered.all()
        out: list[dict] = []
        missing: list[str] = []
        for key in keys:
            entry = service.dataset.get(key)
            if entry is not None:
                out.append(
                    {
                        "word": entry.word,
                        "phonetic": entry.phonetic,
                        "translation": clean(entry.translation),
                    }
                )
            else:
                missing.append(key)
                out.append({"word": key, "phonetic": "", "translation": ""})

        if missing:
            found = lookup_ecdict(set(missing))
            for item in out:
                data = found.get(item["word"].lower())
                if data and not item["translation"]:
                    item["phonetic"] = data.get("phonetic", "")
                    item["translation"] = clean(data.get("translation", ""))

        out.sort(key=lambda x: x["word"].lower())
        return {"total": len(out), "words": out}

    @app.get("/favicon.ico")
    def favicon() -> Response:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            '<text y="50%" x="50%" dominant-baseline="central" '
            'text-anchor="middle" font-size="80">📖</text></svg>'
        )
        return Response(content=svg, media_type="image/svg+xml")

    @app.get("/")
    def home() -> FileResponse:
        return FileResponse(STATIC_DIR / "home.html")

    @app.get("/cards")
    def cards() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/word-shooter")
    def word_shooter() -> FileResponse:
        return FileResponse(STATIC_DIR / "word-shooter.html")

    @app.get("/read")
    def read_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "read.html")

    @app.get("/dictionary")
    def dictionary_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "dictionary.html")

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app


app = create_app()
