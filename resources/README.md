# Resources

Data used to help Chinese speakers expand their English vocabulary.

## `dict/` — English → Chinese dictionary

### `ecdict.csv`
Free English→Chinese dictionary (ECDICT). ~770,000 entries. UTF-8, comma-separated.

- Source: https://github.com/skywind3000/ECDICT (MIT License)
- Columns:
  | column | meaning |
  | --- | --- |
  | `word` | the word |
  | `phonetic` | IPA phonetic (British-based) |
  | `definition` | English definition (one per line) |
  | `translation` | Chinese translation (one per line) |
  | `pos` | part-of-speech ratio, e.g. `n:46/v:54` |
  | `collins` | Collins star rating (1–5) |
  | `oxford` | 1 if in the Oxford 3000 core list |
  | `tag` | exam tags: `zk`(中考) `gk`(高考) `cet4` `cet6` `ky`(考研) `toefl` `ielts` `gre` |
  | `bnc` | frequency rank in the BNC corpus |
  | `frq` | frequency rank in the COCA corpus |
  | `exchange` | inflected forms (tenses, plural, comparative, lemma, …) |
  | `detail` | JSON extra info |
  | `audio` | audio URL |

This single file is the primary dictionary: it contains Chinese translations **plus** COCA (`frq`) and BNC (`bnc`) frequency ranks and exam-syllabus tags, so most lookups and filtering can be done from it alone.


### `morphemes_colingoldberg.json`

Supplementary English morpheme data from
[colingoldberg/morphemes](https://github.com/colingoldberg/morphemes),
licensed under MIT; the original notice is in
`dict/morphemes_colingoldberg_LICENSE`. The source contains 2,435 entries
with forms, meanings, positions, and example words. The reading popup uses
these examples only when the indicated form matches the word in its stated
position. This yields about 13,000 distinct word lookups. Its meanings are in
English and appear only when no curated Chinese explanation or confirmed
Chinese affix analysis is available.

## `wordlists/` — English word lists

Source for all lists below: https://github.com/mahavivo/english-wordlists

| file | description | approx. size |
| --- | --- | --- |
| `COCA_20000.txt` | COCA 20,000 most frequent words, one per line, in frequency order | 20,000 words |
| `COCA_with_translation.txt` | COCA list with inline Chinese translations | ~20,000 words |
| `primary_school.txt` | 小学 (primary school) syllabus words | ~450 words |
| `middle_school_zhongkao.txt` | 中考 (middle-school exam) word list, with phonetics + Chinese | ~1,600 words |
| `high_school_gaokao.txt` | 高考 (high-school exam) word list | ~3,500 words |
| `CET4.txt` | 大学英语四级 (CET-4) syllabus | ~4,600 words |
| `CET6.txt` | 大学英语六级 (CET-6) syllabus, with phonetics + Chinese | ~2,300 words |
| `TOEFL.txt` | TOEFL vocabulary, with phonetics + Chinese | ~4,500 words |
| `GRE_8000.txt` | GRE ~8,000 words, with phonetics + Chinese | ~7,700 words |

### Format notes
Formats differ per file:
- Plain lists (`COCA_20000.txt`, `primary_school.txt`, `high_school_gaokao.txt`): one word per line.
- Annotated lists (`CET6.txt`, `TOEFL.txt`, `GRE_8000.txt`, `middle_school_zhongkao.txt`, `COCA_with_translation.txt`): `word [phonetic] pos. 中文释义`.
- Some files contain section headers (e.g. `A`, `B`) and title lines that should be skipped when parsing.

The plain word lists are graded by difficulty (primary → 中考 → 高考 → CET4 → CET6 → TOEFL → GRE), which pairs well with the COCA/BNC frequency ranks in `ecdict.csv` for building a learning curriculum.
