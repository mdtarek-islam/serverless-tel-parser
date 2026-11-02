---
description: Run the handler in a local Lambda emulator and report cold-start and warm latency against the 200 ms target.
---

# /simulate-env

Agent: env-simulation-tester. Skill: ci-cd-harness.

## Steps

1. Check that Docker is running. Stop and report if it is not.
2. Build the image: `docker build -t tel-parser:sim .`. Record the image digest.
3. Start the container with the Lambda Runtime Interface Emulator on a local port.
4. Start DynamoDB Local, or select the in-process fake that matches the `StatsWriter` interface.
5. Post the API Gateway v2 events: valid Overwatch, valid Marvel Rivals, bad game, bad base64, missing body.
6. Measure the cold start over at least 10 fresh containers. Report p50 and p95 of `init_ms`.
7. Measure 100 warm invocations. Report p50, p95 and p99 of `invoke_ms`.
8. Print a table: metric, samples, p50, p95, p99, target, verdict.

## Rules

1. Use no AWS credentials. Touch no live table.
2. Keep raw timings in `.dump/` when a run fails.
3. Change no source file. Report the finding to the owner.
4. Cold start above 200 ms is a FAIL, not a warning.
