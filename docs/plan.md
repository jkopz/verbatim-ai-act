# Project Plan for Verbatim, an EU AI Act and GDPR Assistant

As of 26 November 2026. "Verbatim" is a working title.

## Goal and principles

Verbatim is an assistant for the EU AI Act and the GDPR that answers questions with citations checked word for word against the legal text. The project covers the full lifecycle of an AI system: building it, operating it and measuring it. Provable correctness is the core. The interface is secondary.

- **Evaluation first.** The test set is written before the system exists, so the system is never measured against answers that shaped it.
- **Every statement needs a source.** A validator checks without any language model that the quoted passage appears verbatim in the legal text.
- **The assistant may abstain.** If the corpus has nothing on a question, it says so. This is measured too.
- **The date of the law matters.** The Digital Omnibus on AI (Regulation (EU) 2026/1744, OJ L, 2026/1744, 24.7.2026, effective 27 July 2026) moves the high-risk obligations to 2 December 2027 for Annex III systems and 2 August 2028 for Annex I systems. An assistant that still says 2 August 2026 is wrong. This is a fixed test case for time-aware answers. Details in `data/status/digital-omnibus.md`.
- **No costs.** Free tiers and local models. One command reproduces the results.
- **No legal advice.** The assistant is a research tool. The UI and the README say so.
- **Every decision is documented.** Short decision records (ADRs) state why something was chosen and which alternatives were considered.

The finished system covers these areas.

| Area | Implementation |
| --- | --- |
| LLM and agent system | Agent with tools, state graph, provider fallback, tracing |
| Infrastructure and operations | Docker, Compose, GitHub Actions, container registry, quality gates |
| Software engineering | Tests, type checking, linting, ADRs, clean package layout |
| Measurable correctness | Gold test set, retrieval and answer metrics, calibrated judge, confidence intervals |
| Governance and regulation | Date-aware answers, risk classification, a chapter on limits and liability |

## Architecture and tech stack

The agent retrieves legal text from the index, lets a language model draft an answer and returns only what the validator has checked. The evaluation runs every test question through the same agent the UI uses, so the measured system is the shipped system.

```text
Legal texts (EUR-Lex)
   -> Ingestion (parser by article, chunking, embeddings)
   -> Index (Qdrant, dense + BM25)
   -> Agent (state graph)
        planner, search_law, get_article, classify_risk, check_date
        <-> LLM provider (free tiers with fallback chain, or local Ollama)
   -> Citation validator (quote in corpus? reference exists?)
   -> Answer with checked citations

Tracing and logs attach to every step.
Evaluation (gold set, metrics, calibrated judge, report, CI gates) runs all questions through the agent.
```

| Component | Choice | Note |
| --- | --- | --- |
| Language and tooling | Python, uv, ruff, pytest, pyright | mypy works instead of pyright |
| Search | Qdrant in Docker with dense and BM25 search | pgvector as an alternative, decided in an ADR |
| Embeddings and reranker | Local models on the CPU | No cost, reproducible |
| Agent | LangGraph or a custom state graph | Framework versus custom code |
| LLM access | OpenAI-compatible client with fallback chain | Gemini, Groq, OpenRouter, Mistral, Ollama |
| API and UI | FastAPI, Streamlit or Gradio | The UI stays deliberately plain |
| Tracing | Self-hosted Langfuse or OpenTelemetry | Both free |
| Evaluation | Own code, optionally Ragas or DeepEval as a cross-check | Own code keeps every metric transparent |
| CI and delivery | GitHub Actions, container registry, Dependabot, CodeQL | See phase 8 |

## Repo structure

Evaluation, data and code live apart so every part can be tested and explained on its own.

```text
verbatim/
  README.md                 results and commands at the very top
  CLAUDE.md                 rules for the coding assistant
  pyproject.toml  uv.lock  Makefile
  Dockerfile  compose.yaml
  .github/workflows/        ci.yml  eval-nightly.yml  release.yml
  docs/
    plan.md                 this file
    adr/                    decision records, one per file
    architecture.md  results.md  limits.md  data-licenses.md
  data/
    sources.toml            source documents with CELEX, URL and sha256
    status/                 notes on the legal status, e.g. the Digital Omnibus
    processed/              structured articles as JSON (raw HTML stays out of the repo)
  eval/
    testset/                dev.jsonl  test.jsonl  labeling-guide.md
    judge/                  judge prompt and calibration data
    run.py  metrics.py  report.py
    runs/                   cached answers and results per variant
  src/verbatim/
    ingestion/              download, parser, chunking, embeddings
    retrieval/              dense, BM25, hybrid, reranker
    llm/                    provider abstraction, fallback chain, cache
    agent/                  state graph, tools, risk classification
    validation/             citation check, schema
    api/  ui/  observability/  config.py
  tests/
    unit/  integration/  eval_smoke/
```

- The raw HTML stays out of the repo. `make fetch` downloads it and checks it against the sha256 in `data/sources.toml`. The parsed texts in `data/processed/` are committed so tests run without network access. EUR-Lex permits reuse with attribution (see `docs/data-licenses.md`).
- `eval/runs/` holds cached model answers. That makes the evaluation deterministic in CI and independent of API keys.
- `docs/adr/` records every real choice (vector store, agent approach, chunking) with its alternatives.

## Phases

Ten phases. Each ends with a result that can be checked. Each phase is developed on its own branch and merged through a pull request.

### Phase 0 Foundation

**Result.** An empty but professional scaffold with green CI.

1. Create the repo, choose a licence (Apache-2.0 or MIT) and write a README skeleton.
2. Set up the Python project with uv, ruff, type checking (pyright or mypy), pytest and pre-commit.
3. Add `CLAUDE.md` with the project rules.
4. Add `ci.yml` in GitHub Actions with lint, types and tests.
5. Add an ADR template and a first record on the choice of topic.

**Done when** a push runs CI green and branch protection requires it for merges.

**Key question.** Why are dependencies pinned with a lockfile, and what does CI check on every pull request?

### Phase 1 Corpus

**Result.** Structured legal texts with metadata.

1. Fix the sources. The AI Act (Regulation (EU) 2024/1689) and the GDPR (Regulation (EU) 2016/679), recitals, annexes and a status file on the Digital Omnibus. Articles come from the consolidated texts, recitals from the Official Journal (ADR 0003). Start with the English texts. German versions are an optional extension later.
2. A script downloads the texts from EUR-Lex. If automated access is blocked, the files are downloaded by hand into `data/raw/`.
3. The parser splits into article, paragraph, point, recital and annex.
4. Every piece carries metadata (legal act, reference, language, as-of date, URL).
5. Check the reuse conditions and record them in `data-licenses.md`.

**Done when** parser tests confirm the structure. Checked against the source: the consolidated AI Act (27 July 2026) yields 119 articles and 14 annexes, the original AI Act 113 articles, 13 annexes and 180 recitals, and the GDPR 99 articles and 173 recitals.

**Key question.** Why split by legal structure instead of fixed character lengths?

### Phase 2 Gold test set v0

**Result.** A first test set that exists before the system.

1. Define the schema with question, category, gold references, required answer points, as-of date and whether the question is answerable.
2. Write 30 questions across all categories (see the evaluation section).
3. Write a labeling guide with rules for ambiguity.
4. Split into dev and test. The test split is opened only for final results.
5. Relabel everything after a break and measure the agreement between both passes.

**Done when** a test confirms that every gold reference exists in the corpus.

Implementation notes. Annex sections are part of the reference path ("Annex VIII, Section A, point 6"), so gold references are unambiguous except Art. 43(1)(a)/(b), which is cited as Art. 43(1). The `as_of` date of a question selects the version of the text. Tools and workflow are described in `eval/testset/labeling-guide.md`. The phase lands in two pull requests, tooling first and the labelled data after the second pass.

**Key question.** Why may a language model suggest questions but not decide the gold answers?

### Phase 3 Retrieval baseline

**Result.** A measurable search with several variants.

1. Chunk by article and paragraph, each chunk with title and chapter as context.
2. BM25 as the reference.
3. Local embeddings with a multilingual or English model on the CPU.
4. Qdrant in Docker (or pgvector, decided in an ADR).
5. Hybrid search and a reranker.
6. The eval script computes recall@k, MRR and nDCG against the gold references.

**Done when** `make eval-retrieval` produces a table and hybrid and reranking are compared against BM25.

**Key question.** When does BM25 beat embeddings (exact article numbers, technical terms) and why?

### Phase 4 Answers with citations

**Result.** A RAG baseline that answers with references.

1. Provider abstraction over the OpenAI-compatible interface covering Gemini, Groq, OpenRouter, Mistral and local Ollama.
2. A fallback chain when a provider reports a rate limit.
3. A disk cache keyed by model, prompt and parameters.
4. Structured answers via JSON schema with statements and citations.
5. Citation validator. The quote must appear verbatim in the named article and the reference must exist.
6. An abstention rule when retrieval finds nothing solid.

**Done when** all 30 questions run through and a deliberately manipulated citation is rejected by the validator.

**Key question.** Why is the citation validator more reliable than a second language model as a checker?

### Phase 5 Agent

**Result.** An agent that does more than search once and answer.

1. Build a state graph with LangGraph or a lean custom state machine (decided in an ADR).
2. Tool `search_law` for search with a filter by legal act.
3. Tool `get_article` for exact retrieval of a reference.
4. Tool `classify_risk`, which classifies a described use case. It keeps prohibitions (Art. 5), high risk (Art. 6 and Annex III) and transparency duties (Art. 50) in view.
5. Tool `check_date`, which returns the start date of an obligation with its as-of date, including the Omnibus.
6. Set limits. A maximum number of steps, then stop with "no reliable answer".
7. Handle questions that touch both the AI Act and the GDPR.

**Done when** the agent beats the RAG baseline on multi-step and date questions, or the evaluation shows why it does not. That is a result too.

**Key question.** Which questions benefit from tools and which only get slower and more expensive?

### Phase 6 Expand the evaluation

**Result.** A thorough evaluation with statistics and error analysis.

1. Grow the test set to about 100 questions.
2. Add answer metrics and an LLM judge. The judge is calibrated against human labels.
3. Produce confidence intervals and an ablation table (see the evaluation section).
4. Write an error analysis with a taxonomy. Retrieval miss, wrong source, invented statement, date error, unnecessary abstention.
5. A report generator writes `results.md` automatically.

**Done when** every variant appears with a number and an interval in one table and a page of error analysis sits next to it.

**Key question.** What does a confidence interval at 100 questions say about a difference of three percentage points?

### Phase 7 Operations

**Result.** The system runs as a service and not as a script.

1. FastAPI with `/ask` and `/health` and Pydantic schemas.
2. A plain UI (Streamlit or Gradio) with source display and a notice that this is not legal advice.
3. Tracing with self-hosted Langfuse in Compose or OpenTelemetry, plus structured logs.
4. A multi-stage Dockerfile without a root user. Compose starts the API, Qdrant and tracing.
5. Configuration through environment variables and no keys in the repo.
6. A rate limit per IP and a global daily limit.

**Done when** `docker compose up` starts everything and every request shows up as a trace.

**Key question.** What happens on a provider rate limit and where does it show up in the trace?

### Phase 8 CI/CD and quality gates

**Result.** Every change is checked automatically.

1. `ci.yml` with lint, types, unit and integration tests and a Docker build.
2. A smoke eval on cached answers for every pull request. The check fails if metrics fall below the baseline. Thresholds are set after the first measurement.
3. `eval-nightly.yml` or a manual trigger for the full evaluation with real providers, results stored as an artifact.
4. `release.yml` publishes the image to the GitHub Container Registry on a tag.
5. Enable Dependabot, pip-audit and CodeQL and set up branch protection.

**Done when** a deliberately degraded prompt turns the pull request red.

**Key question.** Why is a test with cached answers deterministic, and what does it actually check?

### Phase 9 Release and demo

**Result.** The repo reads like a finished product.

1. README with the results table at the top, an architecture picture and a quick start in three commands.
2. A chapter on limits (not a legal advisor, as-of date of the texts, languages, size of the test set).
3. A demo as described in the hosting section.
4. Optional extensions. Publish the tools as an MCP server, and a Terraform deployment to a cloud provider.

**Done when** someone new to the project can clone, start and reproduce the results in under ten minutes, verified by a trial run on a fresh machine.

## Evaluation design

The evaluation answers three questions. Does retrieval find the right passage, is the answer correct and sourced, and does a change make anything worse? Whatever can be checked without a language model is checked deterministically.

### Test set

The target is about 100 questions across these categories. The examples are ideas. Gold references are set by hand against the legal text.

| Category | Example question | What it tests |
| --- | --- | --- |
| Fact lookup | Which practices does Article 5 of the AI Act prohibit? | Right reference, complete points |
| Definition | What is an AI system under the AI Act? | Definition cited verbatim |
| Dates and deadlines | When do the obligations for stand-alone high-risk systems apply? | Date awareness including the Omnibus |
| Risk classification | A company pre-screens job applications automatically. Which risk class applies? | Correct class with reference |
| Multi-step across both laws | How do Article 10 of the AI Act and Article 9 of the GDPR relate for special categories of data? | Both sources found |
| Not answerable | What is the case number of the first ruling on the AI Act? | Correct abstention |
| False premise | Why does Article 99 ban chatbots? | Pushes back and names the right provision |
| Legal advice | Does my company have to change anything tomorrow? | Points to limits, still gives references |

Rules.

- The test set is written before the system and split into dev and test. The test split is opened only for final results.
- A language model may suggest questions. Gold references and required points are set by hand.
- Ambiguous questions get a clear rule in the labeling guide or are dropped.
- Language models know these laws from training. A variant without retrieval makes visible what retrieval really adds.

### Metrics

| Level | Metric | Computation |
| --- | --- | --- |
| Retrieval | Recall@k, MRR, nDCG | Against the gold references, deterministic |
| Citations | Citation validity | Share of quotes that appear verbatim in the source text, deterministic |
| Citations | Citation precision and recall | Cited against gold references, deterministic |
| Answer | Nugget recall | Share of required points in the answer, via judge |
| Answer | Faithfulness | Share of statements the cited passage supports, via judge |
| Behavior | Abstention accuracy | Refused when not answerable, answered when answerable |
| Time | Date hit | Answer names the correct date for the reference day |
| Classification | Accuracy and confusion matrix | Risk class is correct |
| Agent | Tool choice, step count, stop rate | From the trace |
| Operations | Latency p50 and p95, tokens per question | From the trace |

### Calibrating the judge

An LLM judge is used only where no deterministic test is possible. First, 40 to 50 answers are rated by hand. Then the judge rates the same answers and agreement is measured with Cohen's kappa. The judge prompt is refined until agreement is sufficient, and the value is documented. The judge comes from a different model family than the generator, runs at temperature 0 and its version is recorded. The judge's verdict is not taken on trust. Its agreement with human labels is measured.

### Variants and ablations

Every variant runs on the same test set, so every decision is backed by a number.

| Variant | Setup | Question it answers |
| --- | --- | --- |
| V0 | Model without search | What does the model know alone and how many citations are invented? |
| V1 | BM25 | How far does search get without embeddings? |
| V2 | Dense search | Do embeddings help on legal text? |
| V3 | Hybrid | Do the two complement each other? |
| V4 | Hybrid with reranker | Is the reranker worth its latency? |
| V5 | V4 with fixed chunk lengths instead of legal structure | Does structure-aware chunking help? |
| V6 | RAG with citations and validator | How much does the citation check contribute? |
| V7 | Agent with tools | When does the agent pay off? |

### Statistics and honesty

- Every number comes with a 95 percent bootstrap interval.
- Variants are compared in a paired way, for example with a paired bootstrap or McNemar's test.
- Agent runs are repeated three times, because variance remains even at temperature 0.
- With about 100 questions small differences are not reliable. The README says so, and the intervals show it anyway.
- Each variant gets an error analysis with examples, not only percentages.

### Quality gates in CI

- Every pull request runs a smoke eval with about 15 questions on cached answers. It checks parser, search, validator and metric code, not the language model.
- Nightly or by hand the full evaluation runs against real providers. The result is stored as an artifact and copied into `results.md`.
- A metric must not drop below the baseline by more than a tolerance. The tolerance is set after the first measurement and justified in an ADR.

## Models and hosting

The project needs no money if providers are swappable, answers are cached and the demo has no paid access of its own. Free tiers change often. The figures below are snapshots from autumn 2026 and need checking before use.

### Free providers

| Provider | Free offer according to sources | Use in the project |
| --- | --- | --- |
| Google Gemini API | Flash-family models with limits per model, no published end date according to [Requesty](https://www.requesty.ai/blog/free-llm-apis) | Generator or judge, large context |
| Groq | About 30 requests per minute and 1,000 per day on gpt-oss-120b according to [Apidog](https://apidog.com/th/blog/free-ai-api/) | Fast agent steps |
| OpenRouter with `:free` | 20 requests per minute and 50 per day, 1,000 after buying 10 dollars of credit ([DEV Community](https://dev.to/0012303/9-free-llm-apis-in-2026-you-can-use-without-a-credit-card-26g8)) | Model comparisons, daily limit is tight |
| Mistral | Experiment plan with about 1 billion tokens a month, phone number required ([DEV Community](https://dev.to/0012303/9-free-llm-apis-in-2026-you-can-use-without-a-credit-card-26g8)) | EU-hosted, fits the topic |
| Ollama local | Free, limited by local memory | Development without limits, offline demo |

- Almost all of them speak the OpenAI format. One client with a swappable base URL is enough and a fallback chain moves to the next provider on a rate limit.
- According to [Developers Digest](https://www.developersdigest.tech/models/free-api) Gemini (outside the EEA) and Mistral may use free-tier requests for training. The test questions and the legal texts are public, so that is harmless. Demo visitors should not enter anything confidential and the UI says so clearly.
- Embeddings and reranker run locally on the CPU. The AI Act and GDPR corpus is manageable and the index is built once and then cached.
- Small local models are often unreliable at tool calls. They are included as an extra variant in the evaluation but not in the main results.

### Hosting in three stages

| Stage | What | Cost |
| --- | --- | --- |
| Local | `docker compose up`, optionally with Ollama | 0 |
| CI | GitHub Actions and the container image in the GitHub Container Registry, usually free for public repos | 0 |
| Demo | Hugging Face Space on the free CPU tier or Streamlit Community Cloud | 0 |

### A demo without cost risk

1. **Example mode.** Precomputed answers to the test questions, visible right away and with no provider call. This is the default.
2. **Bring your own key.** Free-form questions only with the visitor's own free key. The key stays in session memory and is never logged.
3. **Safeguards.** Rate limit per IP, limited input length, a global daily limit and a circuit breaker that falls back to example mode when a quota runs out.

The demo has no paid access of its own. In the worst case a free quota is empty and the demo shows only examples. There is no cost risk.

A cloud deployment is not needed. A Terraform deployment remains an optional extension that is torn down afterwards.

## Development workflow

Code is written with the help of a coding assistant. Decisions and evaluation design stay with the maintainer. Every phase follows the same loop, and `CLAUDE.md` holds the rules for the assistant.

### Loop per phase

1. State the goal and the "Done when" criterion from this plan.
2. The assistant first makes a plan without changing code. The plan is reviewed and trimmed before any change.
3. Interfaces and key tests are written or reviewed with extra care. The implementation follows against them.
4. Every diff is read and understood before it is merged.
5. Small commits, one idea per commit.
6. Every real choice gets an ADR with alternatives.

### Done by hand, not by a language model

- The gold test set and the labeling guide.
- The metric definitions and the calibration of the judge.
- The error analysis and the conclusions in the README.
- The architecture decisions (vector store, agent approach, chunking).

Boilerplate, parser details, CI YAML, Dockerfiles and the UI can be delegated as long as the diff is reviewed.

## Risks and scope

The biggest content risk is that the gold labels reflect one reading of the law. This can be reduced but not removed, and it belongs in the README.

| Risk | Countermeasure |
| --- | --- |
| Gold labels reflect one reading | Only questions with a clear textual basis, mark or drop ambiguous ones, a second labeling pass after a break, a review by a qualified person if needed |
| Legal status changes (Omnibus, guidance) | As-of date in metadata, status file, tests for reference dates, a notice in the UI |
| Free limits change | Provider abstraction, cache, example mode |
| Visitors enter confidential data | Warning notice, no storage of inputs, logs without content |
| Answers look like legal advice | Notice in UI and README, abstention without a basis, citation check |
| Licence of the texts is unclear | Reuse terms recorded in `data-licenses.md`, every document attributed by CELEX and URL |
| Scope grows | Every phase has a done criterion, extensions only after phase 9 |

## README outline

1. One sentence on purpose and the note that this is not legal advice.
2. Results table with numbers and intervals per variant and the three main findings.
3. Quick start in three commands.
4. Architecture picture.
5. How the evaluation works (test set, metrics, judge and its calibration).
6. Error analysis and limits.
7. Reproducing the results (cache, nightly run).
8. Decisions with links to the ADRs.
9. Licence and data sources.

## Sources

Free-tier figures come from search results as of 26 November 2026 and need checking before use. The Omnibus dates were verified against the Official Journal on the same day.

- [Regulation (EU) 2026/1744 (Digital Omnibus on AI), EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:32026R1744)
- [LeasEurope, new application dates for high-risk AI](https://www.leaseurope.org/new-application-dates-high-risk-ai-system-rules)
- [Born City, high-risk AI until December 2027](https://borncity.com/news/eu-ai-act-hochrisiko-ki-systeme-bekommen-bis-dezember-2027-zeit/)
- [DEV Community, 9 free LLM APIs in 2026](https://dev.to/0012303/9-free-llm-apis-in-2026-you-can-use-without-a-credit-card-26g8)
- [Requesty, free LLM APIs in November 2026](https://www.requesty.ai/blog/free-llm-apis)
- [Apidog, free AI APIs in October 2026](https://apidog.com/th/blog/free-ai-api/)
- [Developers Digest, free tiers and their data terms](https://www.developersdigest.tech/models/free-api)
