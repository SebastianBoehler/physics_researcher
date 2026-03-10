# Example Prompts and Problems

This file is the short list of prompts to try against the current repository. It is split into:

- prompts that are runnable against the current fake-simulator workflow
- prompts that should drive the next round of iteration

## Runnable now

### 1. Baseline closed-loop search

Use with [baseline_conductivity.json](../campaigns/baseline_conductivity.json).

```text
Run a materials discovery campaign to maximize conductivity while keeping cost below 55 and stability above 0.7. Use a budget of 12 runs and batch size 2. After each step, explain why the next batch was chosen.
```

What this stresses:

- full campaign stepping loop
- planner and critic summaries
- optimizer state updates
- persistence of runs and artifacts

### 2. Feasibility-first search

Use with [cautious_feasible_search.json](../campaigns/cautious_feasible_search.json).

```text
Run a cautious search that prefers feasible improvement over aggressive exploration. Keep the batch size at 1 and call out when a candidate is close to violating cost or stability constraints.
```

What this stresses:

- constraint handling
- smaller batch behavior
- run-by-run decision reporting

### 3. Process window tuning

Use with [process_window_tuning.json](../campaigns/process_window_tuning.json).

```text
Treat this as a process optimization campaign. Optimize anneal temperature, pressure, and synthesis time, then summarize the best operating window instead of just the single best point.
```

What this stresses:

- `process_optimization` mode
- analysis summaries for process settings
- critic language around regimes instead of single winners

### 4. Tight-budget benchmark

Use with [tight_budget_screen.json](../campaigns/tight_budget_screen.json).

```text
Run a very small-budget screening campaign and report whether the first two batches are strong enough to justify a larger search. Focus on sample efficiency.
```

What this stresses:

- early-step optimizer quality
- benchmark-style reporting
- small-budget decision quality

### 5. Longer-horizon observation

Use with [longer_horizon_exploration.json](../campaigns/longer_horizon_exploration.json).

```text
Run a longer fake-simulator campaign and summarize how the search direction changes across batches. Call out whether the planner appears to be exploiting a promising region or still exploring broadly.
```

What this stresses:

- optimizer behavior over multiple updates
- batch size 4 path
- critic summaries over history

## Prompt templates for operator testing

These are useful when you want to watch the agents and orchestration layer rather than just submit a static campaign JSON.

### Candidate rationale prompt

```text
Explain why the proposed batch is reasonable using only campaign objectives, constraints, and prior run history. Do not speculate about simulator internals.
```

### Critic summary prompt

```text
Compare the last five runs, identify the most likely promising region in parameter space, and state whether the next batch should explore or exploit.
```

### Report-writing prompt

```text
Write a short run report for each completed simulation and a campaign summary after every batch. Highlight feasible best-so-far candidates.
```

## Next iteration prompts

These are not fully implemented today, but they are the right problems to use when extending the repository.

### 6. Failure recovery campaign

```text
Inject transient failures into 20 percent of runs, retry only transient failures, and summarize failure classes at the end of the campaign.
```

Why it matters:

- needs campaign-level failure injection hooks
- exercises retry and classification more directly

### 7. Early stopping by diminishing returns

```text
Stop the campaign early if the last three completed runs improve conductivity by less than 2 percent, and explain why the stop condition was triggered.
```

Why it matters:

- needs explicit stop-rule configuration
- pushes critic-driven workflow control

### 8. Robustness over peak performance

```text
Search for robust candidates, not just high-performing ones. Prefer regions where small parameter changes do not sharply reduce stability.
```

Why it matters:

- needs derived robustness metrics
- suggests new evaluation logic beyond single-point objective values

### 9. Seeded versus unseeded comparison

```text
Warm-start the optimizer with four hand-picked candidates, then compare the seeded campaign against an unseeded baseline after the same budget.
```

Why it matters:

- needs candidate seeding support at campaign start
- good benchmark for optimizer initialization

### 10. Multi-objective tradeoff analysis

```text
Maximize conductivity while minimizing cost and explain the tradeoff frontier after each batch.
```

Why it matters:

- current transport models allow multiple objectives
- the working optimizer still behaves as single-objective-first and should be extended before treating this as production-ready

## Suggested order

If you want a disciplined progression, run them in this order:

1. baseline closed-loop search
2. cautious feasibility-first search
3. process window tuning
4. tight-budget benchmark
5. longer-horizon observation
6. failure recovery campaign
7. early stopping by diminishing returns

## CLI examples

```bash
uv run autolab create-campaign examples/campaigns/baseline_conductivity.json
uv run autolab create-campaign examples/campaigns/process_window_tuning.json
uv run autolab create-campaign examples/campaigns/tight_budget_screen.json
```
