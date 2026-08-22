# MCP Client Guardrails Integration (NeMo Guardrails)

Integration guide for adding domain-scope guardrails to the MCP client. The
same client image deploys across projects with different domains by passing
a project-specific `guardrails_config` dict through the existing `mcp init`
API — no code changes per deployment.

---

## What this gives you

- **Input rail** — rejects out-of-scope queries before tool selection runs.
  Saves tokens, latency, and prevents the agent from confidently picking the
  wrong tool for a question it shouldn't answer.
- **Output rail** — catches cases where a tool returned off-topic content or
  the LLM drifted, before the response reaches the user.
- **Local LLM friendly** — works with Ollama and vLLM. The rail uses your
  existing local serving stack, no external API calls.
- **Per-project scope** — each deployment passes its own domain examples and
  refusal message via the init dict. Same code, different scope.

---

## Files in this integration

| File                    | Purpose                                            |
| ----------------------- | -------------------------------------------------- |
| `mcpGuardrails.py`      | New module under `MCPClient/src/`. Owns rail state, builds Colang config from dict, exposes init + check functions. |
| `mcpInit_patch.py`      | Appended block for `MCPClient/src/mcpInit.py`. Adds `mcp_guardrails_init`. |
| `mcp_api_patch.py`      | Patch for `MCPClient/mcp_api.py`. Adds `mcp_api_guardrails_init` and wires it into `mcp_api_init_all`. |
| `mcpClient_patch.py`    | Patch for `MCPClient/src/mcpClient.py`. Adds input rail at workflow entry and output rail before chat persistence. |

---

## Installation

```bash
pip install nemoguardrails
```

The module imports `nemoguardrails` lazily inside `mcp_guardrails_init`, so
projects that don't pass `guardrails_config` are unaffected if the package
isn't installed.

---

## File placement

```
MCPClient/
├── mcp_api.py              ← apply mcp_api_patch.py
├── src/
│   ├── mcpClient.py        ← apply mcpClient_patch.py
│   ├── mcpInit.py          ← apply mcpInit_patch.py
│   ├── mcpGuardrails.py    ← NEW FILE (copy mcpGuardrails.py here)
│   ├── mcpChat.py
│   ├── mcpPrompt.py
│   └── mcpResponse.py
└── mcpSetting.py
```

---

## Applying the patches

Each `*_patch.py` file is **not** a standalone Python file — it's a set of
annotated instructions showing the exact lines to insert or replace.
Open the patch alongside the target file and apply the changes manually,
or use it as a reference for a code review.

Order of application:

1. Drop `mcpGuardrails.py` into `MCPClient/src/`.
2. Append the block from `mcpInit_patch.py` to `MCPClient/src/mcpInit.py`.
3. Apply the three changes from `mcp_api_patch.py` to `MCPClient/mcp_api.py`.
4. Apply the three changes from `mcpClient_patch.py` to `MCPClient/src/mcpClient.py`.

---

## Configuration shape

The init dict accepted by `mcp_api_guardrails_init` (or via the
`guardrails_config` key of `mcp_api_init_all`):

```python
{
    "enabled":   True,
    "fail_mode": "open",        # "open" allows on internal error; "closed" blocks

    "llm": {
        "provider":    "ollama",                  # "ollama" | "vllm" | "openai_compatible"
        "model":       "llama3.1:8b",
        "base_url":    "http://localhost:11434",
        "temperature": 0.0,
    },

    "domain": {
        "name":               "finance",
        "on_topic_examples":  [
            "what's our Q3 revenue",
            "show me invoice INV-4421",
            "list outstanding payments for vendor X",
            "generate the AR aging report",
            "what's the budget variance for cost center 42",
        ],
        "off_topic_examples": [
            "what's the weather",
            "tell me a joke",
            "write me a poem",
            "recipe for pasta",
            "help me with my homework",
        ],
        "refusal_message": (
            "I can only help with finance-related questions like invoices, "
            "payments, budgets, and financial reports. Could you rephrase?"
        ),
    },

    "rails": {
        "input":  True,
        "output": True,
    },
}
```

### Validation rules

- `llm.provider` must be one of `ollama`, `vllm`, `openai_compatible`.
- `domain.on_topic_examples` and `domain.off_topic_examples` must each have
  at least 2 entries.
- `fail_mode` must be `open` or `closed`. Default is `open`.
- `rails.input` and `rails.output` default to `True` if `rails` is omitted.

Invalid configs return `(False, "Invalid guardrails config: <reason>")` from
the init call. The same client image then continues to run with guardrails
disabled.

---

## Usage from your application

### Option A — pass it through `mcp_api_init_all`

```python
from MCPClient.mcp_api import mcp_api_init_all

ok, msg = mcp_api_init_all({
    "log_path":         "/var/log/mcp",
    "llm_model_name":   "llama3.1:8b",
    "llm_model_host":   "localhost",
    "llm_model_port":   "11434",
    "mcp_url":          "http://mcp-gateway:9000",
    "redis_server_ip":  "localhost",
    "redis_server_port": 6379,
    "intent_list":      [...],

    # NEW — opt in per project
    "guardrails_config": {
        "enabled": True,
        "fail_mode": "open",
        "llm": {
            "provider": "ollama",
            "model":    "llama3.1:8b",
            "base_url": "http://localhost:11434",
            "temperature": 0.0,
        },
        "domain": {
            "name": "finance",
            "on_topic_examples":  [...],
            "off_topic_examples": [...],
            "refusal_message":    "...",
        },
        "rails": {"input": True, "output": True},
    },
})
```

### Option B — init guardrails separately

```python
from MCPClient.mcp_api import mcp_api_guardrails_init

ok, msg = mcp_api_guardrails_init(guardrails_config)
```

Calling `mcp_api_guardrails_init` more than once is safe — it tears down any
previous rail and rebuilds from the new config. Useful for tests or live
scope updates.

---

## Behaviour at runtime

| Scenario                              | What happens                                                              |
| ------------------------------------- | ------------------------------------------------------------------------- |
| Config not passed / `enabled=False`   | Guardrails are off. Workflow unchanged. Zero overhead.                    |
| Init succeeds, query is in scope      | Input rail returns fast, workflow proceeds normally.                      |
| Init succeeds, query out of scope     | Refusal message is yielded to caller, persisted to chat history with `intent="out_of_scope"`, `tool="guardrails:input_rail"`. Tool selection is skipped entirely. |
| Output rail blocks                    | Response is replaced with refusal text, persisted with `tool="guardrails:output_rail"`. |
| Internal error in rail (`fail_mode=open`) | Workflow proceeds as if guardrails were off. Error is logged.         |
| Internal error in rail (`fail_mode=closed`) | Query is treated as out-of-scope. Refusal is returned.              |

Because blocked queries are persisted with `intent="out_of_scope"`, you can
mine your Redis chat history to discover what users *try* to ask that falls
outside scope. Add a quick filter on the existing `mcp_chat_get_history`
result for `entry["intent"] == "out_of_scope"`. This is gold for tuning the
`off_topic_examples` list over time.

---

## Per-project scope strategy

Keep project-specific configs in the same repo that owns the deployment
manifest, not in the MCP client repo. A pattern that works well:

```
my-finance-project/
├── deploy/
│   ├── mcp_init_config.py     # builds the dict passed to mcp_api_init_all
│   └── guardrails_examples.yaml
└── ...
```

Then `mcp_init_config.py` loads `guardrails_examples.yaml`, builds the dict,
and passes it through the init API. The MCP client image stays generic.

Suggested layout for the examples YAML:

```yaml
domain_name: finance
refusal_message: |
  I can only help with finance-related questions like invoices, payments,
  budgets, and financial reports. Could you rephrase?

on_topic:
  - "what's our Q3 revenue"
  - "show me invoice INV-4421"
  # ...

off_topic:
  - "what's the weather"
  - "tell me a joke"
  # ...
```

---

## LLM provider notes

### Ollama

The wrapper writes:

```yaml
- type: main
  engine: ollama
  model: llama3.1:8b
  parameters:
    base_url: http://localhost:11434
    temperature: 0.0
```

Cold-start gotcha: if Ollama hasn't loaded the model yet, the first rail
call blocks on model load (5–15s for an 8B model). Fix: send a warmup
`generate("hello")` call at the end of your application's startup, or
keep the model resident with Ollama's `OLLAMA_KEEP_ALIVE=-1`.

### vLLM

The wrapper writes:

```yaml
- type: main
  engine: openai
  model: meta-llama/Llama-3.1-8B-Instruct
  parameters:
    openai_api_base: http://vllm-host:8000/v1
    openai_api_key: dummy
    temperature: 0.0
```

vLLM exposes an OpenAI-compatible endpoint, so we use the `openai` engine
pointed at it. The dummy key is required by the OpenAI client library even
though vLLM doesn't check it.

### Using a different model for the rail than the main agent

You probably don't need your full reasoning model for scope classification.
A 3B instruction-tuned model is usually 3–5x faster and just as accurate
for this task. Easiest way: run a second Ollama model and point the
guardrails config at it while the rest of your app keeps using the big one.

```python
"llm": {
    "provider": "ollama",
    "model":    "llama3.2:3b",          # smaller than the main agent
    "base_url": "http://localhost:11434",
    "temperature": 0.0,
},
```

---

## Latency budget

Typical overhead, measured per request:

| Stage             | Latency (Ollama, llama3.2:3b on consumer GPU) |
| ----------------- | ---------------------------------------------- |
| Input rail        | ~80–150ms                                      |
| Output rail       | ~80–150ms                                      |
| Both rails on     | ~160–300ms total added                         |

If the input rail alone is what you care about (catching off-domain traffic
early), set `rails.output = False` to halve the overhead.

---

## Testing your scope

Add a small harness per project that runs known in-scope and out-of-scope
queries against the initialized rail and asserts the verdicts. Run it in CI
when the examples list changes. Otherwise scope regressions only surface in
production.

```python
from MCPClient.src.mcpGuardrails import (
    mcp_guardrails_init,
    mcp_guardrails_check_input,
)

mcp_guardrails_init(your_config)

cases = [
    ("show me invoice INV-1234", True),
    ("what's the weather",       False),
    ("recipe for tiramisu",      False),
    ("vendor X outstanding payments", True),
]

for query, expected_in_scope in cases:
    in_scope, _ = mcp_guardrails_check_input(query)
    assert in_scope == expected_in_scope, f"{query!r}: expected {expected_in_scope}, got {in_scope}"
```

---

## Operational checklist

Before deploying to a new project:

- [ ] `nemoguardrails` installed in the image
- [ ] Local LLM (Ollama or vLLM) is reachable from the MCP client at the
      `base_url` in the guardrails config
- [ ] Guardrails config has at least 5 examples each for on-topic and
      off-topic — more is better; ten of each is a good baseline
- [ ] Refusal message is written in your application's tone of voice and
      hints at what the user *can* ask about
- [ ] `fail_mode` set appropriately (`open` for most apps, `closed` for
      compliance-sensitive deployments)
- [ ] Warmup call sent at startup so first user doesn't pay cold-start cost
- [ ] Test harness asserts at least 5 in-scope and 5 out-of-scope queries
      get the right verdict
- [ ] `flag_meta_data` enabled if you want the `guardrails:input_rail` /
      `guardrails:output_rail` tags surfaced in API responses for debugging

---

## Disabling without code changes

To turn guardrails off in any deployment without redeploying, pass either:

```python
"guardrails_config": None
# or
"guardrails_config": {"enabled": False}
```

The init call returns success and the workflow runs as if the integration
weren't there. Useful for incident response or for development environments
where you want to bypass scope checks while iterating on tool definitions.
