---
name: translate-chinese-fiction
description: Translate long-form Chinese fiction into natural English while preserving plot facts, voice, terminology, and cross-chapter continuity through a maintained canon reference.
---

# Chinese Fiction Translation

Produce publication-quality English prose, not a sentence-by-sentence gloss. Preserve every plot fact, implication, relationship, and deliberate ambiguity, while allowing syntax, paragraph rhythm, dialogue tags, and idioms to become natural English.

## Required project files

Keep these beside each novel:

- The untouched source text.
- A `decoded/` directory containing UTF-8 source batches of 50 chapter-parts each, plus a manifest.
- `base_screen_reference.md`, the authoritative living canon and terminology ledger.
- A `translation/` directory containing ordered chapter files and `translation_progress.md`.

Read the entire reference and the end of the preceding translated chapter before translating a new section. If the source contradicts an earlier assumption, correct the reference and check affected translation files.

## Before translating

1. Detect the source encoding. Never overwrite or silently transcode the original.
2. Decode the source into UTF-8 before translating. Split it into deterministic, ordered batches of 50 chapter-parts per file under `decoded/`; include front matter in the first batch and write a manifest containing each batch's first and last headings. Treat parenthetical parts such as `（上）`, `（下）`, and `（一）` as separate chapter-parts for batching.
   Use `media/decode_novel.py` when working in this repository; specify the detected source encoding rather than relying on its default.
3. Inventory volumes, arcs, chapters, and part divisions. Record stable decoded batch names and unique headings so work can resume without omissions.
4. Build the reference from the source itself. Record confirmed information separately from provisional interpretations.
5. Lock English forms for names, titles, factions, locations, abilities, ranks, items, currencies, attributes, recurring system messages, and combat mechanics.
6. Identify licensed or borrowed settings. Use their established English names when the Chinese clearly refers to an existing work or character, unless the novel explicitly uses a conflicting name.

## Incorporating user feedback

Treat later user comments as amendments to the active project rules. Apply them to subsequent work immediately and revise already translated text when the comment requires retroactive consistency. Update the project reference with novel-specific decisions. When feedback expresses a reusable translation workflow, quality rule, or output convention, also update this skill file so later novel projects inherit it. Do not add a one-off story fact to the general skill.

## Translation files and 50-chapter merging

- Translate each chapter-part into a separate, zero-padded working file. Its sequence number must match the decoded manifest's global chapter-part number.
- Keep working files until every one of the corresponding 50-part source batch has passed the quality gates.
- Then concatenate the 50 translations in numeric source order into one UTF-8 Markdown batch file. Do not summarize, deduplicate, or alter text during merging.
- In this repository, use `media/merge_translation_batch.py` for the verified merge-and-cleanup operation; run it without `--delete` for validation first, then rerun with `--delete` only after reviewing its manifest.
- Verify the merged file contains all 50 unique chapter headings in order, has the expected first and last headings, and preserves the combined body of every working file.
- Only after that verification succeeds, delete those 50 per-chapter working files. This deletion is authorized only for files already represented in the verified merged batch.
- The final source batch may contain fewer than 50 parts; merge it after every remaining part is complete using the same checks.
- Record the merged output and removal of working files in `translation_progress.md`. Never mark a batch complete based only on file count.

## Translation standard

- Write idiomatic contemporary narrative English appropriate to the novel's genre and period.
- Translate meaning and dramatic effect, not Chinese word order. Recast long paratactic sentences when English clarity requires it.
- Preserve viewpoint, tense, pacing, foreshadowing, uncertainty, and character-specific speech.
- Keep all material content. Do not summarize, sanitize, embellish, repair plot logic, or invent connective detail.
- Exception: do not reproduce explicit sexual content involving anyone under eighteen. Preserve non-graphic plot facts and consequences in neutral language, insert a concise editorial omission marker where explicit detail was removed, and record the treatment in the project reference. Do not age a character up or silently alter canon.
- Avoid translationese: excessive “actually,” “naturally,” “after all,” repeated names, comma splices, mechanical dialogue tags, and literal four-character idioms.
- Retain purposeful repetition and abrupt fragments when they create rhythm or tension.
- Render measurements and culturally specific concepts consistently. Do not localize away facts relevant to the setting.
- Use pinyin without tone marks for Chinese personal names, family name first, unless the story establishes another form. Do not arbitrarily Westernize names.
- Use curly quotation marks for dialogue and italics sparingly for internal emphasis. Keep system messages visually consistent with the project reference.
- Translate chapter titles for impact as well as accuracy, and keep numbered multi-part titles structurally consistent.

## Canon discipline

For every new proper noun or mechanic:

1. Search the source and existing translation for earlier occurrences.
2. Check the reference for a locked form.
3. If absent, choose a concise English form that remains viable in later contexts; mark it provisional when evidence is incomplete.
4. Add the source term, locked English, category, first occurrence, aliases, and any constraints to the reference before using it repeatedly.

Names that are visually similar in Chinese must remain distinct. Track pronouns, gender, affiliations, deaths, injuries, equipment ownership, ability costs, cooldowns, ranges, ranks, and upgrades when they affect continuity.

## Chapter workflow

1. Extract exactly one chapter-part from the UTF-8 files in `decoded/`; never translate directly from a legacy-encoded source when decoded batches exist.
2. Read enough surrounding source to resolve references and transitions.
3. Update the reference with newly established canon.
4. Draft the chapter as cohesive English prose.
5. Compare the draft paragraph-by-paragraph against the Chinese for omissions, additions, reversed logic, number errors, speaker errors, and inconsistent terms.
6. Read the English alone for native rhythm, varied syntax, dialogue flow, and unintended ambiguity.
7. Update `translation_progress.md` with source boundaries, output path, status, and unresolved questions.

## Quality gates

A chapter is complete only when:

- every source paragraph is represented in order;
- names, mechanics, numbers, and movie/franchise terms match the reference;
- dialogue speakers and pronouns are unambiguous where the source makes them clear;
- the English reads as authored prose rather than a literal draft;
- no mojibake, source boilerplate, duplicated passage, or untranslated Chinese remains, except deliberately retained terms recorded in the reference.

At arc boundaries, audit the reference, search all completed chapters for deprecated terms, and record any intentional retroactive changes.
