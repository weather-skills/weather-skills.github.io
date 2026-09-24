# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Build the deployable GitHub Pages site from the template in site/.

Clones `skills/` from https://github.com/weather-skills/weather-skills-catalog
at `main` (layout `skills/<collection>/<skill>/SKILL.md`), reads each
SKILL.md frontmatter (`name`, `description`, the nested
`metadata.catalog-group` key, and `metadata.openclaw.requires.env`),
renders the skill catalog as four short capability boxes and the skill
count into `site/index.html` via marker comments, and writes the complete
deployable site (index.html, 404.html, style.css, CNAME) to the output
directory. Catalog labels are short names (a dataset or an operation), not
the skill directory name. Each label opens a one-line description: where a
datasource comes from, or what any other skill does. The boxes and count
track the catalog: adding, removing, or regrouping a skill changes the
page on the next build with no template edit. The CNAME publishes the site
at weather-skills.org.

The output directory is created fresh on every build. An existing output
directory is cleaned only if it is empty or carries the marker file this
build writes; anything else is refused, as is an output path that is (or
contains) the `site/` template directory.

Marker comments in the template (each must appear exactly once):

    <!-- gen:skill-count -->     the number of skills
    <!-- gen:catalog -->         the grouped catalog sections

Usage:
    uv run tools/build_site.py                  # writes _site/
    uv run tools/build_site.py --output /tmp/site-build
"""

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

# Public catalog the page is generated from. Skills live at skills/ on main,
# grouped as skills/<collection>/<skill>/SKILL.md.
CATALOG_REPO = "https://github.com/weather-skills/weather-skills-catalog.git"
CATALOG_REF = "main"
CATALOG_SKILLS_PATH = "skills"

# Catalog boxes in page order. Every SKILL.md must carry one of these keys
# in `metadata.catalog-group`.
GROUPS: list[tuple[str, str, str | None]] = [
    ("fetchers", "Datasources", None),
    ("transforms", "Transformations", None),
    ("figure", "Visualizations", None),
    ("agent-tooling", "Utilities", None),
]

# Short names shown in the catalog boxes. A skill that covers several
# products lists each product. Skills absent from this map fall back to a
# shortened form of their directory name.
_CATALOG_LABELS: dict[str, tuple[str, ...]] = {
    "arco-era5-fetch": ("ERA5",),
    "chirps-fetch": ("CHIRPS",),
    "cmip6-fetch": ("CMIP6",),
    "dynamical-fetch": ("GFS", "GEFS", "IFS-ENS", "AIFS", "ICON-EU", "MRMS"),
    "ecmwf-fetch": ("ECMWF S2S",),
    "ghcn-daily-fetch": ("GHCN",),
    "imerg-fetch": ("IMERG",),
    "kenya-forecast-fetch": (),
    "oisst-fetch": ("OISST",),
    "openaq-fetch": ("OpenAQ",),
    "smap-fetch": ("SMAP",),
    "tahmo-fetch": ("TAHMO",),
    "aggregate-temporal": ("aggregate",),
    "clip-region": ("clip",),
    "convert-calendar": ("calendar",),
    "convert-to-totals": ("totals",),
    "step-to-time": ("step to time",),
    "summarize-dim": ("summarize",),
    "unit-convert": ("units",),
    "plot": ("heatmap",),
    "plot-compare": ("heatmap-compare",),
    "plot-compare-forecasts": ("heatmap-compare",),
    "plot-mediogram": ("mediogram",),
    "plot-timeseries": ("timeseries",),
    "kenya-forecast-png": (),
    "inspect-zarr": ("inspect data",),
    "resolve-region": ("resolve-region",),
    "resolve-time": ("resolve-time",),
    "submit-feedback": ("feedback",),
    "africa-itf": ("ITF",),
    "iod-mode-index": ("IOD",),
    "mjo-forecast-fetch": ("MJO",),
    "subc-mme-fetch": ("SubC MME",),
}

# One line shown when a catalog label is opened. Datasource lines say where
# the data comes from; every other line says what the skill does. Keyed by
# the short label, because one skill can cover several products and one
# label can cover more than one skill. Every rendered label must appear here.
_CATALOG_BLURBS: dict[str, str] = {
    "AIFS": "ECMWF Artificial Intelligence Forecasting System, via the dynamical.org catalog.",
    "CHIRPS": "UC Santa Barbara Climate Hazards Center precipitation.",
    "CMIP6": "CMIP6 climate-model output from the Pangeo catalog on Google Cloud.",
    "ECMWF S2S": "ECMWF subseasonal-to-seasonal ensemble, from the ECMWF Data Stores.",
    "ERA5": "ECMWF ERA5 reanalysis, from the ARCO store on Google Cloud.",
    "GEFS": "NOAA Global Ensemble Forecast System, via the dynamical.org catalog.",
    "GFS": "NOAA Global Forecast System, via the dynamical.org catalog.",
    "GHCN": "NOAA Global Historical Climatology Network daily station observations.",
    "ICON-EU": "DWD ICON-EU regional forecast, via the dynamical.org catalog.",
    "IFS-ENS": "ECMWF Integrated Forecasting System ensemble, via the dynamical.org catalog.",
    "IMERG": "NASA IMERG satellite precipitation, from NASA Earthdata.",
    "MRMS": "NOAA Multi-Radar Multi-Sensor precipitation analysis, via the dynamical.org catalog.",
    "OISST": "NOAA Optimum Interpolation sea-surface temperature, from NOAA Physical Sciences Laboratory.",
    "OpenAQ": "Air-quality station observations from the OpenAQ network.",
    "SMAP": "NASA SMAP soil moisture, from NASA Earthdata.",
    "SubC MME": "Climate Hazards Center SubC multi-model ensemble.",
    "TAHMO": "TAHMO weather stations across Africa.",
    "aggregate": "Roll a time series up into daily, weekly, dekadal, or monthly windows.",
    "calendar": "Convert a dataset's time axis onto another calendar.",
    "clip": "Cut a dataset down to a bounding box or polygon.",
    "coarsen": "Regrid a dataset onto a coarser or realigned grid.",
    "concat": "Join datasets along one dimension.",
    "deaccumulate": "Turn a cumulative forecast into a per-step rate.",
    "difference": "Subtract one dataset from another, cell by cell.",
    "downscale": "Map a dataset onto a finer grid.",
    "IOD": "Compute the Indian Ocean Dipole index from a temperature anomaly.",
    "rename": "Rename one variable in a dataset.",
    "select": "Keep chosen entries along one dimension.",
    "step to time": "Turn forecast lead times into calendar valid times.",
    "summarize": "Collapse a dimension with a statistic such as the mean or the spread.",
    "totals": "Convert a rate into a total over its aggregation period.",
    "units": "Convert variables into different units.",
    "heatmap": "Draw a map or a single time series from one dataset.",
    "heatmap-compare": "Compare datasets as heatmaps, side by side or across times.",
    "ITF": "Show the latest NOAA CPC map of the African Intertropical Front.",
    "mediogram": "Compare a forecast ensemble with its historical climate at one place.",
    "MJO": "Show the latest NOAA CPC Madden–Julian Oscillation phase diagram.",
    "timeseries": "Overlay several datasets as lines on one time axis.",
    "feedback": "Build a link that files a GitHub issue about the skills.",
    "inspect data": "List a dataset's dimensions, coordinates, and variables.",
    "provenance": "Show how an output was produced and how to regenerate it.",
    "resolve-region": "Turn a place name into a bounding box or a boundary.",
    "resolve-time": "Turn a relative date into absolute start and end times.",
}

# Files copied verbatim from site/ into the output directory.
STATIC_FILES = (
    "style.css",
    "CNAME",
    "404.html",
    "demo.js",
    "demo_sen_weekly.png",
    "demo_sen_gmb_weekly.png",
    "weather-skills-chat-orig.gif",
)

# Written into the output directory so a later build can recognize the
# directory as its own prior output and clean it safely.
MARKER_FILE = ".weather-skills-build"

def _parse_frontmatter(skill_md: Path) -> dict:
    """Return the YAML frontmatter mapping of a SKILL.md, or raise ValueError."""
    text = skill_md.read_text(encoding="utf-8")
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        raise ValueError(f"{skill_md}: no YAML frontmatter")
    for index, line in enumerate(lines[1:], start=1):
        if line == "---":
            block = "\n".join(lines[1:index])
            break
    else:
        raise ValueError(f"{skill_md}: frontmatter has no closing `---` line")
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        raise ValueError(f"{skill_md}: invalid YAML frontmatter: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{skill_md}: frontmatter is not a mapping")  # noqa: TRY004 -- ValueError is the documented malformed-frontmatter contract; not a type bug
    return data


def _catalog_labels(name: str) -> tuple[str, ...]:
    """Return the short catalog labels for a skill directory name."""
    labels = _CATALOG_LABELS.get(name)
    if labels is not None:
        return labels
    short = name.removesuffix("-fetch").removeprefix("plot-").replace("-", " ")
    return (short,)


def _requires_credentials(skill_md: Path, metadata: dict) -> bool:
    """True when frontmatter `metadata.openclaw.requires.env` is a non-empty list.

    An absent `openclaw`, `requires`, or `env` key means no credentials. A key
    that is present with the wrong shape (`openclaw`/`requires` not a mapping,
    `env` not a list) raises ValueError naming the skill.
    """
    if "openclaw" not in metadata:
        return False
    openclaw = metadata["openclaw"]
    if not isinstance(openclaw, dict):
        raise ValueError(f"{skill_md}: `metadata.openclaw` is not a mapping: {openclaw!r}")  # noqa: TRY004 -- ValueError is the documented malformed-frontmatter contract; not a type bug
    if "requires" not in openclaw:
        return False
    requires = openclaw["requires"]
    if not isinstance(requires, dict):
        raise ValueError(f"{skill_md}: `metadata.openclaw.requires` is not a mapping: {requires!r}")  # noqa: TRY004 -- ValueError is the documented malformed-frontmatter contract; not a type bug
    if "env" not in requires:
        return False
    env = requires["env"]
    if not isinstance(env, list):
        raise ValueError(f"{skill_md}: `metadata.openclaw.requires.env` is not a list: {env!r}")  # noqa: TRY004 -- ValueError is the documented malformed-frontmatter contract; not a type bug
    return len(env) > 0


def _visible_dirs(path: Path) -> list[Path]:
    """Return non-hidden child directories, in name order."""
    return [
        entry
        for entry in sorted(path.iterdir())
        if entry.is_dir() and not entry.name.startswith(".") and entry.name != "__pycache__"
    ]


def _skill_dirs(skills_dir: Path) -> list[Path]:
    """Return skill directories under the catalog `skills/` tree.

    The catalog layout is `skills/<collection>/<skill>/SKILL.md`. A flat
    `skills/<skill>/SKILL.md` tree is also accepted.
    """
    children = _visible_dirs(skills_dir)
    if not children:
        raise ValueError(f"no skill directories under {skills_dir}")
    if any((child / "SKILL.md").is_file() for child in children):
        return children
    skill_dirs: list[Path] = []
    for collection in children:
        nested = _visible_dirs(collection)
        if not nested:
            raise ValueError(f"{collection}: collection directory has no skills")
        skill_dirs.extend(nested)
    return skill_dirs


def _fetch_skills_dir(dest: Path) -> Path:
    """Clone the catalog at main and return its skills directory."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    clone = subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            CATALOG_REF,
            CATALOG_REPO,
            str(dest),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    if clone.returncode != 0:
        detail = (clone.stderr or clone.stdout).strip()
        raise ValueError(f"failed to clone {CATALOG_REPO}@{CATALOG_REF}: {detail}")
    skills_dir = dest / CATALOG_SKILLS_PATH
    if not skills_dir.is_dir():
        raise ValueError(f"clone of {CATALOG_REPO}@{CATALOG_REF} has no {CATALOG_SKILLS_PATH}/ directory")
    return skills_dir


def _collect_skills(skills_dir: Path) -> dict[str, list[tuple[str, str, bool]]]:
    """Read all SKILL.md files; return {group_key: [(name, description, creds), ...]}.

    `creds` is True when the skill's frontmatter declares a non-empty
    `metadata.openclaw.requires.env` list. Entries are sorted by skill name
    within each group. Raises ValueError on a skill directory without a
    SKILL.md, a missing/unknown group key, a name that doesn't match its
    directory, a missing description, a duplicate skill name, or a malformed
    `metadata.openclaw.requires.env` shape.
    """
    known = {key for key, _, _ in GROUPS}
    grouped: dict[str, list[tuple[str, str, bool]]] = {key: [] for key, _, _ in GROUPS}
    skill_dirs = _skill_dirs(skills_dir)
    for entry in skill_dirs:
        if not (entry / "SKILL.md").is_file():
            raise ValueError(f"{entry}: skill directory has no SKILL.md")
    skill_mds = sorted((entry / "SKILL.md" for entry in skill_dirs), key=lambda p: p.parent.name)
    if not skill_mds:
        raise ValueError(f"no skills/*/SKILL.md found under {skills_dir}")
    for skill_md in skill_mds:
        front = _parse_frontmatter(skill_md)
        name = front.get("name")
        if name != skill_md.parent.name:
            raise ValueError(
                f"{skill_md}: frontmatter name {name!r} != directory name {skill_md.parent.name!r}"
            )
        if any(existing == name for members in grouped.values() for existing, _, _ in members):
            raise ValueError(f"{skill_md}: duplicate skill name {name!r}")
        description = front.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"{skill_md}: frontmatter has no description")
        if description.count("`") % 2:
            raise ValueError(f"{skill_md}: description has an unpaired backtick")
        metadata = front.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError(f"{skill_md}: frontmatter has no `metadata:` map")  # noqa: TRY004 -- ValueError is the documented malformed-frontmatter contract; not a type bug
        group = metadata.get("catalog-group")
        if group not in known:
            raise ValueError(
                f"{skill_md}: `metadata.catalog-group` is {group!r}; "
                f"expected one of {sorted(known)}"
            )
        grouped[group].append((name, description, _requires_credentials(skill_md, metadata)))
    for key, _, _ in GROUPS:
        if not grouped[key]:
            raise ValueError(f"catalog group {key!r} has no member skills")
    return grouped


def _render_catalog(grouped: dict[str, list[tuple[str, str, bool]]]) -> str:
    """Render the catalog as four boxes of labels that open a one-line description.

    The same `name` on every disclosure in a box keeps a single description
    open at a time. A label with no entry in `_CATALOG_BLURBS` is an error,
    as is a blurb that no rendered label uses.
    """
    parts: list[str] = ['<div class="cap-grid">']
    used: set[str] = set()
    for key, label, _note in GROUPS:
        labels: list[str] = []
        seen: set[str] = set()
        for name, _description, _requires_credentials in grouped[key]:
            for short in _catalog_labels(name):
                if short not in seen:
                    seen.add(short)
                    labels.append(short)
        labels.sort(key=str.casefold)
        items: list[str] = []
        for short in labels:
            blurb = _CATALOG_BLURBS.get(short)
            if blurb is None:
                raise ValueError(f"catalog label {short!r} has no short description")
            used.add(short)
            items.append(
                "        <li>\n"
                f'          <details class="cap-skill" name="cap-{html.escape(key)}">\n'
                f"            <summary>{html.escape(short)}</summary>\n"
                f"            <p>{html.escape(blurb)}</p>\n"
                f"          </details>\n"
                f"        </li>"
            )
        parts.append(
            f'  <section class="cap-box" aria-label="{html.escape(label)}">\n'
            f'    <h3>{html.escape(label)}</h3>\n'
            f"    <ul>\n" + "\n".join(items) + "\n    </ul>\n"
            f"  </section>"
        )
    unused = sorted(set(_CATALOG_BLURBS) - used)
    if unused:
        raise ValueError(f"catalog descriptions are unused: {unused}")
    parts.append("</div>")
    return "\n".join(parts)


def _prepare_output_dir(out_dir: Path, site_dir: Path) -> None:
    """Create out_dir fresh; refuse unsafe targets.

    Refuses an out_dir that is, or contains, the site/ template directory,
    and refuses to clean an existing non-empty out_dir unless it carries the
    marker file a previous build wrote.
    """
    if out_dir == site_dir or site_dir.is_relative_to(out_dir):
        raise ValueError(f"output directory {out_dir} is or contains the site/ template directory")
    if out_dir.exists():
        if not out_dir.is_dir():
            raise ValueError(f"output path {out_dir} exists and is not a directory")
        if any(out_dir.iterdir()) and not (out_dir / MARKER_FILE).is_file():
            raise ValueError(
                f"output directory {out_dir} is not empty and has no "
                f"{MARKER_FILE} marker; refusing to clean it"
            )
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)


def _substitute(template: str, replacements: dict[str, str]) -> str:
    """Replace each marker exactly once; fail on missing or leftover markers."""
    out = template
    for marker, value in replacements.items():
        occurrences = out.count(marker)
        if occurrences != 1:
            raise ValueError(f"template marker {marker!r} appears {occurrences} times; expected 1")
        out = out.replace(marker, value)
    leftovers = re.findall(r"<!--\s*gen:[^>]*-->", out)
    if leftovers:
        raise ValueError(f"unsubstituted generator markers remain: {leftovers}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory for the deployable site (default: <repo>/_site)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    site_dir = repo_root / "site"
    out_dir = Path(args.output).resolve() if args.output else repo_root / "_site"

    try:
        with tempfile.TemporaryDirectory(prefix="weather-skills-catalog-") as tmp_name:
            skills_dir = _fetch_skills_dir(Path(tmp_name) / "catalog")
            grouped = _collect_skills(skills_dir)
        count = sum(len(members) for members in grouped.values())
        template = (site_dir / "index.html").read_text(encoding="utf-8")
        page = _substitute(
            template,
            {
                "<!-- gen:skill-count -->": str(count),
                "<!-- gen:catalog -->": _render_catalog(grouped),
            },
        )
        _prepare_output_dir(out_dir, site_dir)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    (out_dir / "index.html").write_text(page, encoding="utf-8")
    for filename in STATIC_FILES:
        shutil.copy2(site_dir / filename, out_dir / filename)
    (out_dir / MARKER_FILE).write_text("weather-skills.org site build output\n", encoding="utf-8")
    print(f"Built site with {count} skills from {CATALOG_REPO}@{CATALOG_REF} -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
