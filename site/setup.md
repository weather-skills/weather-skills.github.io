# weather skills: setup for coding agents

A person has asked you to set up weather skills in their project. Weather skills are reviewed command-line tools for weather and climate data. Each one does one job, such as fetching a forecast, clipping it to a region, aggregating it to weekly totals, or drawing a map. Every file they write records how it was made. Your job is to pick the skills and run them in order; the skills do the data work.

Work through the sections below. Keep changes inside this project, and ask the person before you touch anything outside it.

## Get the skills

All skills run through [uv](https://docs.astral.sh/uv/). Check that `uv` is installed. If it is missing, point the person to the uv install page rather than installing it system-wide yourself.

Then choose one of these:

**Your agent loads `SKILL.md` files from the project** (Claude Code, Cursor, Codex, and similar). Add the skills to this project with skillkit:

```
npx skillkit install weather-skills/weather-skills-catalog --all --yes
```

Add `--list` to see what is available first, or `--skill=<name>` to add only some.

**Your agent cannot load skills.** Call them through the command-line runner, which needs no install:

```
uvx --from git+https://github.com/weather-skills/weather-skills-catalog weather-skills
```

With no arguments it lists every skill. `weather-skills <skill> --help` shows a skill's arguments.

Each skill's `SKILL.md` says when to use it and which environment variables it needs. The full catalog is at https://github.com/weather-skills/weather-skills-catalog, and https://weather-skills.org/#skills shows it grouped as datasources, transformations, visualizations, and utilities.

## Check that it works

This needs no credentials:

```
uvx --from git+https://github.com/weather-skills/weather-skills-catalog weather-skills resolve-region KEN
```

Expect one `N/W/S/E` bounding box for Kenya, about `5.43/33.91/-4.70/41.91`. If anything else happens, show the person the command and the error exactly; do not speculate about why.

## Working with weather skills

1. **Narrow the request first.** Turn place names into a bounding box with `resolve-region`, and phrases like "last month" into dates with `resolve-time`. Fetch only that box and that window.
2. **Start with credential-free sources.** `dynamical-fetch` covers GFS, GEFS, ECMWF IFS-ENS, AIFS, IMERG, CHIRPS, and more without any account. Reach for other fetchers when it does not carry what you need.
3. **Pass files between skills.** Data skills write a standard dataset (a CF-compliant Zarr store). Give that path to the next skill's `--input`.
4. **Let the skills do the data work.** Do not write your own fetching, regridding, aggregation, or plotting code when a skill covers it. Skill outputs are reviewed and carry provenance; one-off scripts do not.
5. **Leave the data as it is.** Never fill gaps, extrapolate, or adjust values. If data is missing, say so.
6. **Keep secrets out of the chat.** When a skill needs credentials, ask the person to set the environment variables its `SKILL.md` names. Do not ask them to paste keys into the conversation, and never echo one.
7. **Show your work.** To explain where a file came from, run the `provenance` skill on it.

## When you are done

Tell the person which install route you took, where the skills now live, and the bounding box the check printed. Then ask what weather or climate question they want to look at. Bugs and suggestions go to https://github.com/weather-skills/weather-skills-catalog/issues or help@weather-skills.org.
