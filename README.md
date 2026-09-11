<p align="center">
  <img src="assets/logo.svg" alt="ML6 logo" height="112">
</p>

# Multimodal Agent Workshop — Team Case Study

This repository preserves a team solution built during the **ML6 × AISO Agent
Workshop (March 2026)**. It combines a Gemini-based agent with tools for
arithmetic, PDF extraction, web research, webpage retrieval, and image analysis.

> [!IMPORTANT]
> This is an attributed workshop case study, not an original solo project.
> The workshop scaffold, benchmark, attachments, evaluation harness, and guide
> came from [ML6's AISO workshop](https://github.com/ml6team/AISO-workshop).

## Recorded result

The inherited team solution's public commit message records **13/16 benchmark
questions (81.25%)**:

- The result is retained as historical provenance in Git rather than linked here,
  because that older tree also contains the credential discussed below.
- Coverage: instruction following, arithmetic, PDF/image interpretation, and web research
- Model and external-web behaviour can change, so this is historical evidence—not a guarantee
- No evaluation result is committed; a fresh paid benchmark was intentionally not run for this cleanup

## Public provenance

| Contributor | Publicly attributable work |
| --- | --- |
| ML6 workshop authors | Workshop design, guide, benchmark, attachments, evaluator, server utility, and starter code |
| Antonio Pascarella | API and environment setup in the inherited public history |
| El Yassae | Implemented the recorded tool-using solution in the inherited public history |
| Filippo Donghi | Repository owner; the inherited public solution history contains no commit authored by Filippo, so this case study makes no contrary claim |

The original workshop instructions remain available in
[`docs/WORKSHOP_GUIDE.md`](docs/WORKSHOP_GUIDE.md).

## How it works

```text
Question + optional benchmark attachment
                  │
                  ▼
        Google ADK root agent
          ├── calculator
          ├── PDF text extraction
          ├── DuckDuckGo search
          ├── bounded public-web fetch
          └── Gemini image analysis
                  │
                  ▼
       exact match or LLM-assisted judge
```

The portfolio refresh adds defensive boundaries around the workshop tools:

- Web retrieval accepts only public HTTP(S) destinations, revalidates redirects,
  blocks non-public resolved IP addresses, and limits response size.
- PDF and image readers accept only regular files inside
  `benchmark/attachments/`, with extension and size limits.
- Image bytes are sent to Gemini only after those local-file checks pass.
- Unit tests cover calculator behaviour and the security boundaries without
  making paid model calls.

These controls are defence in depth, not a complete network sandbox. Do not
expose this workshop agent as an untrusted public service.

## Setup

Prerequisites:

- Python 3.12
- [`uv`](https://docs.astral.sh/uv/)
- A personal Gemini API key for interactive or benchmark runs

```bash
git clone https://github.com/FilippoDonghi/AISO-workshop.git
cd AISO-workshop
uv sync --frozen --group dev
cp my_agent/.env.example my_agent/.env
```

Replace the placeholder in `my_agent/.env` with your own key. Never commit that
file.

Launch the local ADK interface:

```bash
uv run adk web
```

Then open <http://127.0.0.1:8000> and select `my_agent`.

## Verification

The unit and static checks are offline:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check my_agent tests evaluate.py utils
```

Evaluation calls Gemini and can incur usage charges:

```bash
# One question
uv run python evaluate.py --question 1

# Full 16-question benchmark
uv run python evaluate.py
```

Generated `evaluation_results_*.json` files are ignored by Git.

## Security history notice

A previous public commit contained a Google API credential. The tracked file has
been replaced by a placeholder-only `.env.example`, but deleting a value from the
current tree does **not** remove it from Git history or revoke it.

Repository and parent-fork owners must:

1. Treat the old credential as compromised and rotate/revoke it in Google Cloud.
2. Remove it from all reachable Git history and coordinate across the fork network.
3. Review forks, caches, CI logs, and local clones before considering cleanup complete.

Do not reuse or test the exposed credential.

## Limitations

- A valid Gemini key and network access are required for agent and image-model runs.
- Search results and model outputs are nondeterministic; scores may drift.
- HTML extraction is intentionally simple and does not neutralize every form of
  prompt injection in third-party content.
- The locked Google ADK stack currently resolves `starlette==0.52.1`, for which
  the dependency audit reports known 2026 advisories. Published fixes require
  Starlette 1.x, while `google-adk==1.35.2` requires Starlette `<1`; do not expose
  the local ADK interface publicly, and update once the upstream constraint permits it.
- Local tools intentionally reject files outside the benchmark attachment folder.
- The benchmark is small and should not be interpreted as a production-quality evaluation.
- No licence file is included; review upstream permissions before reuse or redistribution.

## Repository map

```text
my_agent/                  Agent configuration and bounded tools
benchmark/                 ML6 benchmark dataset and attachments
tests/                     Offline unit and security-boundary tests
utils/server.py            Local ADK evaluation runner
evaluate.py                Single-question and full benchmark CLI
docs/WORKSHOP_GUIDE.md     Preserved upstream workshop instructions
```
