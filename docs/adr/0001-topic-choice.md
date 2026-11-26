# 0001 Topic: an assistant for the EU AI Act and GDPR

- Status: accepted
- Date: 2026-11-26

## Context

The project is an AI system whose correctness can be measured end to end, from retrieval to
the final answer. That requires a domain with a public, stable source text, questions with
checkable answers, and stakes high enough that a wrong answer matters.

## Decision

Build a research assistant for the EU AI Act (Regulation (EU) 2024/1689) and the GDPR
(Regulation (EU) 2016/679) whose citations are checked word for word against the legal text.

## Alternatives considered

| Option | Pros | Cons |
| --- | --- | --- |
| EU AI Act and GDPR | Public text with clear structure (articles, paragraphs), correctness is verifiable, a time-dependent case (Digital Omnibus), high practical relevance for organisations | Risk of answers being read as legal advice, gold labels reflect one reading of the law |
| Generic document chat | Easy to start | No ground truth, hard to measure, not distinctive |
| Technical documentation of a framework | Clear answers | Text changes often, no regulatory dimension |

## Consequences

- Every answer carries sources and a disclaimer that it is not legal advice.
- Raw legal texts stay out of the repo and are downloaded by a script.
- The as-of date of the law becomes part of the data model and of the test set.
