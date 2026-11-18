---
title: SSO Login Troubleshooting
category: login_issue
tags: [sso, login, identity-provider]
summary: Diagnose whether SSO failures affect one user or the entire workspace.
---

# Scope

Confirm whether the issue affects one user or multiple users. Ask for the
workspace name and record the time the failure began. A single-user issue often
points to a local account or session problem, while a team-wide failure may
indicate an identity-provider or CloudDesk outage.

# Checks

Check the identity-provider status and any recent configuration changes. Confirm
the CloudDesk workspace SSO connection is enabled and that required attributes,
domains, and certificates are current. Review recent sign-in attempts without
exposing credentials or secrets.

# Resolution

Restore the affected session by signing out and signing back in when the issue
is limited to one user. For a confirmed team-wide outage, escalate to the
identity team with scope, start time, and identity-provider details.
