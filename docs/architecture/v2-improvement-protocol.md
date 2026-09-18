# DeepSeek improvement experiment — 2026-09-18

User authorized an additional CNY 10–15 for evaluation and failure-driven improvement.
Starting project ledger: CNY 0.490326, 109 completed calls, no unknown usage.
Local admission ceiling is temporarily lowered to CNY 15.49 including reservations,
so this experiment can add at most CNY 14.999674. The global CNY 25/30 limits remain.
All runs use the existing persistent ledger; never reset it or use an unmetered client.
Pricing verified at https://api-docs.deepseek.com/zh-cn/quick_start/pricing/:
Flash peak uncached input CNY 2/M, output CNY 8/M. Estimates use these upper prices.

## Frozen experiment

1. Unmodified main `1e2e189`: DeepSeek on the original 150 scenarios, three repeats,
   four concurrent cases, non-thinking, temperature 0.7, top_p 0.8, output cap 1024.
2. Inspect tool traces and run the original 50-case development set. Improve only
   investigation instructions and tool feedback where needed. Business policies,
   authorizations, execution semantics and original golden labels stay unchanged.
3. Run development validation; freeze the candidate before final regression runs.
4. Re-run the original test set (target three repeats, subject to the budget gate).
   This is regression evidence after seeing failures, NOT a new unseen test result.
5. Add a separately frozen multi-turn acceptance set covering clarification, target
   changes and refusal/authorization boundaries. It is supplementary synthetic
   acceptance evidence, not a statistically independent production benchmark.
6. Run backend safety/recovery checks, review raw results and failures, update the
   demo and interview evidence, then publish via the existing project branch/main.

Do not silently restart failed samples, select the best repeat, change labels to
increase scores, raise budgets, switch providers, or claim to have fine-tuned model
weights. Any incomplete run, infrastructure incident, or validation-driven second
candidate must be reported. Qwen remains stopped; this experiment makes no claim
about improved Qwen accuracy. GPU resources are not required for DeepSeek calls.

## Intervention contract

The model still selects and calls tools. Clear user omissions require clarification;
deterministic policy rejection must be explained rather than repeatedly checked or
treated as missing user information. Missing business evidence/conflicting policy
requires manual handling, not invented facts. A bypass-approval instruction cannot
invalidate an otherwise legitimate request or grant execution authority. All plans
still need the existing immutable evidence and independent authorization checks.

Paid runs keep their original artifacts and identify the code/data version, actual
returned model name, call count, usage, conservative cost, latency, denominators,
failure categories and repeat-level results. Do not compare latency to old runs as
an isolated speed benchmark: concurrency and shared infrastructure differ.
