---
title: API Rate Limits
category: api_failure
tags: [api, 429, backoff]
summary: Troubleshoot HTTP 429 responses and apply documented retry behavior.
---

# Diagnose

Review request frequency, API plan limits, response headers, and the time range
of 429 responses. A single burst is different from repeated limits across a
nightly sync.

# Retry Behavior

Respect the documented retry interval and use bounded exponential backoff. Add
jitter when many clients retry together. Do not loop immediately or disable
retry limits.

# Escalation

If persistent 429 responses continue after the retry policy is applied, escalate
with request volume, account plan, endpoint, and response headers.