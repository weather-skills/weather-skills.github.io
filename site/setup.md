# weather skills: setup for coding agents

A person has asked you to set up weather skills in their project. Weather skills are reviewed command-line tools for weather and climate data: fetchers, transforms, and plots that you chain together, each recording how its output was made.

This page covers installing the skills and checking the install. How to work with them comes from the weather-skills sources themselves, linked in step 3; read those rather than relying on a summary here. Keep changes inside this project, and ask the person before you touch anything outside it. Two writes outside the project are expected and need no extra permission: uv caches environments under its cache directory (`~/.cache/uv`), and skillkit records installs in `~/.skillkit/lock.json`.

## 1. Get the skills

All skills run through [uv](https://docs.astral.sh/uv/). Check that `uv` is installed. If it is missing, point the person to the uv install page rather than installing it system-wide yourself.

Then choose one of these:

**Your agent loads `SKILL.md` files from the project** (Claude Code, Cursor, Codex, and similar). Add the skills to this project with skillkit, which needs Node.js (`npx`); if `npx` is missing, use the command-line route below instead:

```
npx skillkit install weather-skills/weather-skills-catalog --all --yes
```

skillkit detects your agent and prints where it put the skills, for example `.claude/skills/<skill>/` for Claude Code. Note that path for your report. Add `--list` to see what is available first, or `--skill=<name>` to add only some.

**Your agent cannot load skills.** Call them through the command-line runner, which needs no install:

```
uvx --from git+https://github.com/weather-skills/weather-skills-catalog weather-skills
```

With no arguments it lists every skill. `weather-skills <skill> --help` shows a skill's arguments.

## 2. Check that it works

These need no credentials. The first runs a skill end to end; the others check that a transform and the plotter load:

```
uvx --from git+https://github.com/weather-skills/weather-skills-catalog weather-skills resolve-region KEN
uvx --from git+https://github.com/weather-skills/weather-skills-catalog weather-skills aggregate-temporal --help
uvx --from git+https://github.com/weather-skills/weather-skills-catalog weather-skills plot --help
```

The first must print one `N/W/S/E` bounding box for Kenya, about `5.43/33.91/-4.70/41.91`. The other two must print usage text. If any of them fails, setup has failed: show the person the command and the error exactly, do not speculate about why, and do not work around it.

## 3. Learn how to use them

Fetch and read these now. They are maintained alongside the skills, so they are current.

- **Operating instructions:** https://raw.githubusercontent.com/rhiza-research/weather-skills/main/agents/forecaster.md
  This is the system prompt of the weather-skills forecaster agent. Follow it for every weather or climate data task in this project: which fetcher to prefer, how to resolve dates and regions, how to chain skills, rates versus totals, managing output files, provenance, and credentials. Two adjustments for a local coding agent: you discover the skills you installed in step 1 rather than "bundled" ones, and credentials come from environment variables the person sets in their own shell.
- **Each skill's `SKILL.md`:** when to use it, its arguments, and the environment variables it needs. Read a skill's `SKILL.md` before you first call it.
- **Data contract** (read when you inspect, combine, or explain outputs):
  - https://raw.githubusercontent.com/weather-skills/weather-skills-core/main/docs/weather-skill-authoring/references/STANDARD_DATASET.md — the standard dataset every data skill reads and writes: dimension names, dataset types, and the provenance attribute.
  - https://raw.githubusercontent.com/weather-skills/weather-skills-core/main/docs/weather-skill-authoring/references/UNITS.md — the units contract: standard units, rates, and totals.

Ask the person whether to add a line to this project's agent instructions file (`CLAUDE.md`, `AGENTS.md`, or your tool's equivalent) pointing at the operating instructions above, so later sessions pick them up.

## If a skill fails later

Report the command and its error to the person, and suggest filing it at the issues link below. Do not replace a failing skill with your own code; its outputs would carry no review and no provenance.

## 4. Tell the person

Report which install route you took, where the skills now live, and the bounding box the check printed. Then ask what weather or climate question they want to look at. Bugs and suggestions go to https://github.com/weather-skills/weather-skills-catalog/issues or help@weather-skills.org.
