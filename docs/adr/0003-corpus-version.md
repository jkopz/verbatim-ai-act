# 0003 Corpus version: consolidated text for provisions, Official Journal for recitals

- Status: accepted
- Date: 2026-11-26

## Context

Both regulations exist in several versions on EUR-Lex.

- The AI Act (Regulation (EU) 2024/1689, OJ L, 2024/1689, 12.7.2024) was amended by the
  Digital Omnibus on AI (Regulation (EU) 2026/1744, OJ L, 2026/1744, 24.7.2026), effective
  27 July 2026. The consolidated version `02024R1689-20260727` has 119 articles and 14 annexes,
  the original has 113 articles and 13 annexes. Among other changes, the Omnibus moves the
  application date of the Annex III high-risk obligations to 2 December 2027.
- The GDPR (Regulation (EU) 2016/679, OJ L 119, 4.5.2016) has not been amended, but it has
  three corrigenda. The consolidated version `02016R0679-20160504` incorporates the corrigendum
  of OJ L 127, 23.5.2018.
- Consolidated texts contain no recitals.
- EUR-Lex states that consolidated texts are "meant purely as a documentation tool and have no
  legal effect". Only the texts published in the Official Journal are authentic.

An assistant that still answers with the pre-Omnibus dates gives wrong answers, so the current
text is needed. At the same time, the tool claims verbatim citations and must be clear about
which text it cites.

## Decision

The corpus contains four source documents, each stored and parsed separately:

| Source | CELEX | Used for |
| --- | --- | --- |
| AI Act, consolidated 2026-07-27 | `02024R1689-20260727` | Articles and annexes (current law) |
| AI Act, Official Journal | `32024R1689` | Recitals, and the text as it stood before the Omnibus |
| GDPR, consolidated 2016-05-04 | `02016R0679-20160504` | Articles (with the 2018 corrigendum) |
| GDPR, Official Journal | `32016R0679` | Recitals |

Every parsed piece carries its source CELEX, version date and URL, so every citation names
exactly the text it was checked against.

## Alternatives considered

| Option | Pros | Cons |
| --- | --- | --- |
| Consolidated for provisions, Official Journal for recitals | Current law, recitals available, older version still queryable | Two versions per act, consolidated text is not authentic |
| Consolidated only | One version per act | No recitals, no history |
| Official Journal only | Authentic text | AI Act answers miss the Omnibus, GDPR misses corrigenda |
| Additionally the Omnibus act 32026R1744 | Its recitals explain the amendments | More scope, deferred until needed |

## Consequences

- The UI and the README state that citations refer to the consolidated text published on
  EUR-Lex, which is not legally binding, and link to the Official Journal.
- Recitals of the original GDPR do not reflect the corrigenda. This is recorded as a known
  limitation.
- Known parser limitations, pinned in `tests/unit/test_corpus.py`:
  - Section headings in annexes ("Section A", "1. Introduction") are a level of the
    structural path, because Annexes VII, VIII and X restart their point numbering per
    section. References read "Annex VIII, Section A, point 6".
  - Annexes I, VII and XI list some points as numbered plain text ("3.1.", "2. Directive
    ..."). References to them stop at the enclosing section.
  - Article 43(1) of the AI Act has points (a) and (b) in two subparagraphs. The path does not
    record subparagraphs, so "Art. 43(1)(a)" is ambiguous and is cited as "Art. 43(1)".
  - Articles 102 to 110 of the AI Act amend other regulations and quote their text. The
    quoted parts are kept as plain text, which leaves a few fragment blocks such as `;`.
- New consolidated versions appear when an act is amended again. The source manifest pins
  the version, so an update is a deliberate change with new tests.
