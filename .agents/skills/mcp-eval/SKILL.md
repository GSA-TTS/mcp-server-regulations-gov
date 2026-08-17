---
name: mcp-eval
description: Guide for building a Phoenix-based evaluation harness for an MCP server. Use when you need to create or extend LLM-as-judge evaluations that measure how well an agent can accomplish realistic tasks using only the MCP server's tools. Covers the eval/phoenix module layout, dataset creation, the LangChain agent, judges, system prompts, and running experiments.
---

# MCP Server Evaluation Guide (Phoenix)

## Overview

The measure of an MCP server's quality is NOT how comprehensively it implements
tools, but how well those tools (schemas, docstrings, return shapes) let an LLM with
NO other context answer realistic, difficult questions. This skill describes a
reusable [Arize Phoenix](https://docs.arize.com/phoenix) evaluation harness that:

1. Spins up a LangChain agent connected to the MCP server (over stdio).
2. Feeds it a dataset of natural-language questions with known answers.
3. Scores each answer with LLM-as-judge evaluators and logs traces to Phoenix.

Use this after the server is built (it complements the `mcp-builder` skill, which
produces the `evaluation.xml` question set this harness consumes).

---

# Module Layout

The harness lives in `eval/phoenix/` at the repo root:

```
eval/phoenix/
├── agent.py                   # The <Server>Agent class (launches the MCP server over stdio)
├── create_dataset.py          # CLI: upload a CSV dataset to Phoenix
├── run_experiment.py          # CLI: run an experiment (agent + judges) against a dataset
├── datasets.yaml              # Dataset registry (name -> csv_path, input/output keys, description)
├── README.md                  # Usage docs for this specific server
├── judges/                    # LLM-as-judge evaluators
│   ├── __init__.py            # Re-exports each judge for `from judges import ...`
│   ├── correctness_judge.py   # match_expected_response (compares to ground truth)
│   └── relevance_judge.py     # check_answer_scope (in-scope vs. out-of-scope)
├── prompts/                   # Agent system prompts, one per version
│   ├── system_prompt_v1.txt   # Basic domain analyst
│   └── system_prompt_v2.txt   # + scope boundaries
└── datasets/                  # Test datasets (CSV files)
    └── <name>/examples/<name>.csv
```

**Naming:** Name the agent class after the server (e.g. `HydroAgent`, `NIHReporterAgent`)
and name datasets `<domain>-eval-<n>` (e.g. `hydro-eval-0`).

---

# Environment & Configuration

All credentials come from a **root-level `.env`** (gitignored). Provide a
`.env.example` at the repo root documenting the keys. Every module calls
`load_dotenv()` (bare, so it walks up from CWD to the repo root).

Required variables:

| Variable | Used by | Purpose |
|---|---|---|
| `USAI_API_KEY` | agent + judges | Model gateway API key |
| `USAI_BASE_URL` | agent + judges | Gateway base URL (code appends `/api/v1`) |
| `AGENT_MODEL` | `agent.py` | Model the agent-under-test drives |
| `JUDGE_MODEL` | `judges/*.py` | Model the LLM-as-judge uses (separate from the agent, so you can judge with a stronger/different model) |

**Keep `AGENT_MODEL` and `JUDGE_MODEL` distinct env vars.** Judging with a different
(often stronger) model than the agent-under-test reduces self-preference bias and lets
you hold the judge fixed while iterating on the agent. Read `JUDGE_MODEL` with a
sensible default: `os.getenv("JUDGE_MODEL", "claude_4_6_sonnet")`.

The MCP server itself may need no credentials (e.g. a public API); note that in
`.env.example` so users don't think the eval vars are for the server.

## Dependency group

Add eval-only dependencies to a `dev` dependency group in `pyproject.toml` so they
don't ship with the server:

```toml
[dependency-groups]
dev = [
    "arize-phoenix>=18.0.0",
    "arize-phoenix-client>=2.13.0",
    "arize-phoenix-evals>=3.1.1",
    "langchain>=1.3.14",
    "langchain-mcp-adapters>=0.3.0",
    "langchain-openai>=1.3.5",
    "openinference-instrumentation-langchain>=0.1.67",
    "opentelemetry-exporter-otlp>=1.43.0",
    "opentelemetry-sdk>=1.43.0",
    "pandas>=2.0.0",
    "pyyaml>=6.0.0",
]
```

Install with `uv sync --group dev`.

---

# Components

## The Agent (`agent.py`)

A single `<Server>Agent` class that owns Phoenix instrumentation, the MCP client, and
the LangChain agent. Key responsibilities:

- **Instrument once:** call `phoenix.otel.register(project_name, endpoint)` then
  `LangChainInstrumentor().instrument(tracer_provider=...)` in `initialize()`.
- **Launch the server over stdio** via `MultiServerMCPClient`. Set `cwd` to the repo
  root so the launch command works regardless of the current directory:

  ```python
  REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
  ...
  self.client = MultiServerMCPClient({
      "<server>_server": {
          "transport": "stdio",
          "command": "uv",
          "args": ["run", "src/<servername>/app.py"],
          "cwd": REPO_ROOT,
      },
      # Alternative: {"transport": "http", "url": "http://localhost:8000/mcp"}
  })
  tools = await self.client.get_tools()
  ```

- **Build the agent** with `create_agent(model=ChatOpenAI(...), tools=tools,
  system_prompt=self._load_system_prompt())`, using `temperature=0` for reproducibility.
- **Load prompts by version** from `prompts/system_prompt_{version}.txt` so experiments
  can compare prompt variants.
- **Expose a sync task factory** `create_experiment_task()` that returns a
  `task(example)` closure calling `asyncio.run(self.run(example.input["query"]))` —
  Phoenix experiments expect synchronous task functions.
- Provide a `main()` for standalone smoke testing (`python agent.py`).

## Judges (`judges/`)

Each judge is a plain function using `phoenix.evals.ClassificationEvaluator` with an
`LLM` wrapper pointed at the `JUDGE_MODEL`. Judges take Phoenix's `input`, `output`,
and (for correctness) `expected` dicts and return a single classification label.

**`match_expected_response(input, output, expected)` — correctness.** Compares the
agent's answer to ground truth (`expected["responses"]`). The prompt template MUST
tolerate reasonable formatting differences (units, surrounding prose, extra context)
so a correct answer isn't marked wrong for cosmetic reasons. Returns
`correct` / `incorrect` (`choices={"correct": 1, "incorrect": 0}`).

**`check_answer_scope(input, output)` — relevance/scope.** No reference needed. Judges
whether the agent answered an in-scope question or appropriately refused an
out-of-scope one. Returns `within_scope` / `out_of_scope`.

Judge template guidelines:
- State the agent's exact domain/scope so the judge knows what "in scope" means.
- Use `{input}`, `{output}`, and (correctness only) `{reference}` placeholders.
- Set `temperature=0.0`.
- Return `result[0]` (Phoenix ClassificationEvaluator returns a list).

`judges/__init__.py` re-exports each judge so `run_experiment.py` can do
`from judges import match_expected_response, check_answer_scope`.

## System Prompts (`prompts/`)

One `system_prompt_v{n}.txt` per version. Version them so you can A/B prompt strategies
in separate experiments:
- **v1 — basic analyst:** the domain role plus critical conventions (coordinate systems,
  ID formats, unit caveats) the agent needs to call tools correctly.
- **v2 — scope boundaries:** adds explicit in-scope vs. out-of-scope guidance ("answer
  factual X; refuse Y/predictions/recommendations") while still being helpful first.

Keep `run_experiment.py`'s `--system-prompt-version choices=[...]` in sync with the
prompt files that actually exist.

## Dataset (`datasets/` + `datasets.yaml`)

Datasets are CSVs with an input column (`query`) and an output/reference column
(`responses`). Convert the `evaluation.xml` produced by `mcp-builder` into a CSV:
each `<question>` -> `query`, each `<answer>` -> `responses`.

Keep the source `evaluation.xml` inside the dataset directory it produces (e.g.
`datasets/<name>/evaluation.xml`) rather than at the repo root, so the questions and
the generated CSV travel together:

```
datasets/<name>/
├── evaluation.xml            # source question set (from mcp-builder Phase 4)
└── examples/<name>.csv       # generated dataset (query,responses)
```

Register each dataset in `datasets.yaml`:

```yaml
datasets:
  <name>:
    csv_path: datasets/<name>/examples/<name>.csv
    input_keys:
      - query
    output_keys:
      - responses
    description: "One-line description and question count"
```

Question quality bar (from the evaluation methodology): independent, read-only,
verifiable single answer, stable over time, and complex enough to require multiple tool
calls. Prefer paraphrased questions that can't be answered by keyword-matching the
tool output.

## CLIs

**`create_dataset.py`** — loads a CSV per `datasets.yaml`, validates the required
columns exist, and uploads via `phoenix.client.Client().datasets.create_dataset(...)`.
Supports `--list`, `--dataset-name`, `--phoenix-name`, `--csv-path`, and `--dry-run`
(validate without uploading — use this in CI/pre-flight).

**`run_experiment.py`** — loads the Phoenix dataset, initializes the agent with a
chosen prompt version, and runs `client.experiments.run_experiment(dataset, task,
evaluators=[check_answer_scope, match_expected_response], ...)`. Supports
`--dataset-name`, `--system-prompt-version`, `--project-name`, `--phoenix-endpoint`,
`--experiment-description`, `--dataset-version-id`, and `--no-validate`.

---

# Workflow

Run all commands from `eval/phoenix/` (after `uv sync --group dev` and populating `.env`).

1. **Start Phoenix** (standalone server, UI at :6006, OTLP at :4317):
   ```bash
   uv run arize-phoenix serve
   ```

2. **Create the dataset in Phoenix** (one-time per dataset):
   ```bash
   uv run create_dataset.py --dataset-name <name>
   # validate only, no upload:
   uv run create_dataset.py --dataset-name <name> --dry-run
   ```

3. **Run an experiment**:
   ```bash
   uv run run_experiment.py --dataset-name <name>
   uv run run_experiment.py --dataset-name <name> --system-prompt-version v2
   ```

4. **Review** results and per-question traces in the Phoenix UI (http://localhost:6006).
   Inspect failing cases to decide whether the fix belongs in the tool schema/docstring,
   the system prompt, or the question itself.

---

# Building a New Eval Harness (checklist)

When adding this harness to a fresh MCP server repo:

- [ ] Copy `eval/phoenix/` and rename the agent class + MCP server key after the server.
- [ ] Point the stdio launch command at the server's `app.py`; set `cwd=REPO_ROOT`.
- [ ] Rewrite both judge prompt templates for the new domain/scope.
- [ ] Wire `AGENT_MODEL` and `JUDGE_MODEL` (distinct) and update `.env.example`.
- [ ] Write system prompts (v1 basic, v2 scoped) for the new domain.
- [ ] Convert `evaluation.xml` -> `datasets/<name>/examples/<name>.csv` and register it in `datasets.yaml`.
- [ ] Add the `dev` dependency group; run `uv sync --group dev`.
- [ ] Verify: `create_dataset.py --dry-run` loads the CSV, and `agent.py` / `judges` / `run_experiment.py` import cleanly and the MCP server launches with the agent's exact config.
- [ ] Update `eval/phoenix/README.md` for the new server.

---

# Common Pitfalls

- **Judge marks correct answers wrong** — the correctness template is too strict. Allow
  unit/formatting/context differences explicitly.
- **Agent can't find tools** — the stdio `command`/`args`/`cwd` don't resolve to a
  runnable server. Test the exact `MultiServerMCPClient` config in isolation.
- **Env vars missing at judge time** — judges also call `load_dotenv()` and read
  `JUDGE_MODEL`/`USAI_*`; they run in the same process so the root `.env` covers them.
- **Prompt version mismatch** — `--system-prompt-version` choices must match the files
  in `prompts/`.
- **Non-reproducible runs** — set `temperature=0` for both the agent and the judges.
