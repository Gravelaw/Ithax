# Assistant access: each Phase 1 template built and run through MCP, 2026-11-09

Spec 0 "Success measures", assistant access (M10, AKS-125): "An assistant connected through MCP builds and runs each Phase 1 template from a text description", transcripts under `docs/research/mcp/`.

## Question

Can a real assistant, connected to `python -m lcsim.mcp` and given only a plain description of each template's problem (never the template's id), build the model, run it and report the answer, for all ten Phase 1 templates? And what does it get wrong, so the tool names, inputs and descriptions can be revised (guide known gaps, M7)?

## Finding

**Ten of ten passed** on the measure's reading below: every model loads with no error and no warning, every run the assistant reported ended `done`, and every reported answer agrees with the template's theory or benchmark value (within 3 standard errors for a simulation, exactly for an optimization). Nine passed on the first attempt as the assistant's own model. "How many machines?" passed on its answer in attempt 1 but not as the problem was meant to be built: the assistant could not find how a setting uses a parameter and ran five models by hand; after the descriptions named `{"$param": "<id>"}`, attempt 2 built one model with a parameter and five scenarios and passed. Neither attempt used an experiment's `search`, the way the template itself is built (spec 2 "Simulation-based optimization"); comparing the five values in scenarios is a correct model of the problem, so the row is counted as passed, with that difference noted.

**The assistant.** Claude Code CLI 2.1.319 (`/opt/node22/bin/claude`), run headless with `claude -p`, model `claude-opus-5-5` (Claude Opus 5.5), the only model each `result` event lists. It is the same model as the build session, so the trial is not independent of the builder (as at M7). A trial with another assistant stays an owner item.

**What it could see and do.** As in the M7 trial (`docs/research/spec-4-mcp-trial-2026-11-08.md`): only the eleven lcsim tools (`--tools ""`, `--strict-mcp-config`, `--allowedTools "mcp__lcsim"`, `--permission-mode dontAsk`), a working folder outside the repository, and the variables that would add the repository's `CLAUDE.md` removed. One change from M7: each trial's engine service was started first with `--templates-dir` an empty folder, so `list_templates` answered `[]` and the assistant had to build each model, not copy a template (the MCP server finds a running service through `service.json` in the same configuration folder). Each trial had its own configuration and data folders; its service was stopped after it.

**The descriptions** (`tests/mcp/coffee_shop_description.txt` for the coffee shop; the others written for this check, each giving the problem's numbers and the run settings in plain words and asking for the numbers the template's lesson is about, never naming a block type, a template or an answer) are at the top of each transcript.

| Template | Transcript | Tool calls (refused) | What it built | Key values, theory or benchmark, deviation in standard errors | Pass |
| --- | --- | --- | --- | --- | --- |
| Coffee shop | `coffee_shop.md` | 6 (0) | source, server, sink; `length` 210 h, `warmup` 10 h | wait 269.1 s ± 11.9 (270, −0.15); till 0.7480 (0.75, −0.78) | yes |
| Three-machine line | `three_machine_line.md` | 12 (0) | the buffer as weld's `queue_capacity` 10 rather than a `queue` block; transfer as a `delay` | weld 0.8999 (0.9, −0.03); paint 0.5017 (0.5, +0.66); throughput 30.0 an hour (−0.09); named weld the bottleneck | yes |
| Machine breakdowns | `machine_breakdowns.md` | 8 (0) | source, server, `failure`, sink | availability 0.8976 (0.9, −1.21); utilization 0.5566 (5/9, +0.44) | yes |
| Clinic patient flow | `clinic_patient_flow.md` | 11 (0) | `resource_pool` of 2 nurses, `branch` 0.6/0.4, two servers of 3 rooms | nurses 0.8006 (0.8, +0.17); time in clinic 1,321 s (4,000/3, −0.38); rooms 0.3198 and 0.2139 (0.32, −0.11; 0.2133, +0.42) | yes |
| Warehouse pick and pack | `warehouse_pick_pack.md` | 15 (0) | `batch` of 5, server with a daily `schedule` (1, 3, 1 pickers), `delay` 3 min, `unbatch`, packer | cart wait 119.98 s (120, −0.06); packer 0.5007 (0.5, +0.54); 60.0 an hour (−0.02) | yes |
| Inventory reorder point | `inventory_reorder_point.md` | 9 (0) | source, `store` (70, reorder at 20, order 50, lead 5 d), sink | stock 25.65 (25.588, +0.83); stock-outs 130.8 (135.03, −0.95), 3.4% of customers | yes |
| Transport plan | `transport_plan.md` | 7 (0) | twelve flat variables (not the indexed layout), supply and demand limits | cost 2,690 and the benchmark's plan | yes |
| Product mix | `product_mix.md` | 6 (0) | two integer variables, two limits | 24 chairs, 14 tables, 2,200; both limits tight | yes |
| Staff rota | `staff_rota.md` | 6 (0) | seven integer variables by start day, seven cover limits | 9 people (theory 9); another rota of 9 than the template's | yes |
| How many machines? | `how_many_machines-attempt-1.md` | 30 (2) | after five refused spellings of a parameter, one till count changed by hand and five runs | 2 tills: wait 14.77 s (162/11 s, +0.16), 0.3750 (0.375, +0.03); answer right | answer only |
| How many machines? | `how_many_machines-attempt-2.md` | 8 (0) | `tills` as a parameter, `{"$param": "tills"}`, five scenarios in one experiment | 2 tills: wait 15.19 s (+2.32), 0.3780 (+2.88); answer right | yes |

Standard error = half-width / t(0.975, 29), t = 2.0452 (as the M7 and M9 acceptance cases read it). Each run used its own seed or none, so deviations differ from the templates' at seed 12345. In attempt 2 the five scenarios share common random numbers (spec 1), so one run's draw moves them together: the one-till scenario is +2.85 as well. Every project validated with no issue (each project's `model.json` loaded with 0 errors and 0 warnings after the trial).

**What it got wrong, or what cost it a step:**

1. **The parameter reference.** For "How many machines?" it wrote the till's `capacity` as `"$tills"`, `{"param": "tills"}`, `"${tills}"`, `"@tills"` and `{"parameter": "tills"}`; each was saved with an E123 issue ("a plain number with no unit is expected"), and a scenario setting `till.capacity` was refused with E180. It then removed the parameter and ran five models by hand. Spec 1's `{"$param": "<id>"}` was in no tool description and in no hint. Fixed in the descriptions (Decision); attempt 2 wrote it right the first time.
2. **No search.** In neither attempt did it use an experiment's `search`, which `edit_model`'s description lists among the experiment fields without its layout. Scenarios answer the question; a search would also confirm the best (spec 2). Not changed: the description is at 3,982 of the 4,096 characters the CLI takes whole, and the answer was right. Listed under Left (Phase 1a: a search example in `get_schema` or a `get_schema` topic for experiments).
3. **`get_results` while running** (attempt 1): one call answered E188 because the run had not finished; it waited and asked again, as the description says.
4. **`get_schema` many times.** Several trials read five to seven block types one by one before building, as the description asks ("one type at a time"); no harm.
5. Two models were built differently from their template but correctly: the line's buffer as weld's own queue of 10 (the same behaviour as a 10-place `queue` before a server with no queue), and the transport plan and staff rota as flat variables rather than the indexed layout (both solve the same problem).

## Sources

- The eleven transcripts in this folder, rendered from the CLI's `stream-json` output: the prompt, the `init` event, every tool call with its input and its full result, the assistant's text and the `result` event. The CLI's thinking blocks arrived empty. Nothing was trimmed.
- Each template's `expected.json` (the theory and benchmark values); spec 2 "Benchmarks" (the 3 × standard error rule); spec 1 "Parameters" (`{"$param": "id"}`).
- `docs/research/spec-4-mcp-trial-2026-11-08.md` (how the M7 trial was run).

## Decision

- **Assistant access is met by the agent** for all ten templates, with Claude Code CLI 2.1.319 and `claude-opus-5-5`; "How many machines?" on the second attempt, after a description change, and as scenarios rather than a search (owner to confirm that reading; AKS-125 DECISIONS entry).
- **Two descriptions revised** (spec 4 "How the server runs and answers", "What the M10 trials changed"): `edit_model` says a setting uses a parameter as `{"$param": "<id>"}`; `get_schema` says any number or time setting, a distribution's fields included, may be a parameter, which scenarios and a search change. No tool name or input changed; `tests/mcp/test_mcp_write_tools.py` checks both.
- **Left for the owner:** a trial with another assistant, and whether the measure wants a `search` for "How many machines?".

## Tested

Trials 1 to 10 ran on 2026-11-09 with the tools as at f1388b6 (the AKS-124 head; the AKS-125 changes had not started); attempt 2 of "How many machines?" with the tools as at b840ff4 (the description change). For each, in `/tmp/claude-0/m10-mcp/<template>/`:

```bash
python -m lcsim.service --config-dir config --data-dir data --templates-dir no-templates --idle-minutes 60 &
# mcp.json: {"mcpServers": {"lcsim": {"type": "stdio", "command": "/home/user/Ithax/.venv/bin/python",
#   "args": ["-m", "lcsim.mcp", "--config-dir", "<folder>/config", "--data-dir", "<folder>/data"]}}}
cd work
env -u CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD -u CLAUDE_ADDITIONAL_DIRECTORIES \
  claude -p "$(cat <description>.txt)" \
  --mcp-config mcp.json --strict-mcp-config --tools "" --allowedTools "mcp__lcsim" \
  --permission-mode dontAsk --no-session-persistence --max-budget-usd 10 \
  --output-format stream-json --verbose < /dev/null > transcript.jsonl
```

Every `claude` exited 0 with nothing on standard error (19 to 69 s each; USD 0.08 to 0.42). The values above were read afterwards by this session from each trial's run folders (`summary.json` and `manifest.json` under `data/projects/<id>/runs/`), and each project's `model.json` was loaded with `lcsim.model.loading.load_document`.
