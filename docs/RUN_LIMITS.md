# Run limits and allowance rules

All limits live in `Settings` (env names below) and are read through `workspace/limits.py`.
When a limit is reached, dispatch stops, completed work is kept, the run becomes `blocked` with
a reason and a human action is offered: a new run, fixture replay as a separate run, or staff
handling. Nothing is ever reported as a success.

| Env | Default | Applies to |
| --- | --- | --- |
| RUN_MAX_AGENT_TURNS | 14 | specialist turns per collaboration run |
| RUN_MAX_TOOL_CALLS | 16 | deterministic service calls per collaboration run |
| RUN_MAX_OUTPUT_TOKENS_PER_TURN | 600 | hard provider cap per live call |
| RUN_MAX_OUTPUT_TOKENS | 6000 | live output tokens per run |
| RUN_MAX_USD | 0.05 | per-run share of the confirmed allowance (worst case reserved before each call) |
| RUN_MAX_WALL_SECONDS | 180 | active time per run (paused time excluded) |
| RUN_MAX_RETRIES | 1 | provider retries per turn |
| RUN_MAX_CONCURRENT_PER_SCOPE | 3 | active runs per workspace (429 beyond) |
| RUN_MAX_MESSAGE_BYTES | 4096 | exchange payload / command payload size |
| RUN_MAX_INSTRUCTION_CHARS | 500 | user instruction length |
| MAX_UPLOAD_BYTES / MAX_IMAGE_PIXELS | 10 MB / 20 MP | nameplate photos |
| FIXTURE_STEP_DELAY_MS | 600 | pacing between fixture steps so a viewer can watch and pause (0 in tests) |
| DEMO_MAX_WORKSPACES | 400 | demo sandboxes held in memory (oldest evicted) |

The controller also enforces: at most 3 actions per turn, summaries ≤ 600 characters, dropping
repeated identical exchanges, and blocking after 2 consecutive fully rejected turns
(`loop_detected`).

Live AI: a run is `live` only if AI_MODE=live, OPENAI_API_KEY and OPENAI_TEXT_MODEL are set,
AI_CONFIRMED_ALLOWANCE_USD > 0 and AI_ALLOWANCE_EXPIRES_AT is in the future. The model must
have a price in `apps/api/partsiq/ai/prices.json`, or calls are refused (an unknown price is
never guessed; `gpt-4o-mini` is **not** listed yet). An exhausted or expired allowance blocks
the run (`allowance_exhausted`). There is no paid fallback, and a live run never silently
switches to fixture output.
