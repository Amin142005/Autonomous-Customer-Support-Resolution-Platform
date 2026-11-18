---
title: API Authentication Errors
category: api_failure
tags: [api, authentication, token]
summary: Diagnose API authentication failures without collecting secret values.
---

# Scope

Determine whether failures are 401, 403, or token-expiry responses. Confirm
whether the problem affects all API calls or only an endpoint or workspace.

# Checks

Verify that the integration uses the current account and approved API route.
Check expiration and permission configuration. Never request a customer's API
key or secret in plain text.

# Resolution

Direct the customer through the documented credential rotation or permission
flow. Escalate if a workspace appears to have unexpected access changes.