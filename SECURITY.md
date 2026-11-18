# Security Policy

## Reporting a vulnerability

Email security@forumtrust.ai. Please include reproduction steps and, where
possible, the exact command output of the affected verification tool.

## What matters most here

This repo holds the verification tooling for FORUM's signed releases. A bug
that lets a tampered release pass verification is the highest-severity class
of issue. If you find one, we want to hear about it immediately — the
integrity of the anchored history is the product.

## Scope

- verify_public_release.py, verify_anchor_recipe.py, verify_sampler.py, keccak.py
- the documented recipes in docs/

## Out of scope

- the scoring method's choices themselves (those are debated publicly, not
  reported privately — the method is the product)
- availability attacks on the public API
