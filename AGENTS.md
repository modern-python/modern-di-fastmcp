# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`modern-di-fastmcp` is a FastMCP adapter over
[`modern-di`](https://github.com/modern-python/modern-di); [`CONTEXT.md`](CONTEXT.md) opens with
what it does and owns the vocabulary. Read it before naming a concept in code, a test name, or an
issue title. It is one of that project's integrations, each of which lives in a separate repository
and ships as a separate PyPI package.

## Commands

`just` (task runner) and `uv` (package manager). The [`justfile`](justfile) is the source of truth:
`just --list`, or read it.

## Architecture

All implementation is `modern_di_fastmcp/main.py`, short enough to read whole. Read it.
[ADR 0001](docs/adr/0001-from-di-is-a-default-value.md) explains why `FromDI` is a parameter default
and not `Annotated` metadata.

### Testing patterns

The suite runs against a real in-memory client, not mocks: `fastmcp.Client(server)`, with
`tests/dependencies.py` as the `Group` every test resolves from. A test that needs DI wired takes the
`mcp` fixture from `tests/conftest.py`.

## Workflow

Every link in `README.md` must be absolute: `https://github.com/modern-python/<repo>/blob/main/<path>`,
or `.../tree/main/<path>` for a directory. Never a relative path: `README.md` is also the PyPI long
description, and PyPI does not rewrite relative links, so a relative one 404s on the package page.

## Agent skills

### Issue tracker

GitHub issues on `modern-python/modern-di-fastmcp`, via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical roles, each label string equal to its name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
