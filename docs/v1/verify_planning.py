"""Standard-library structural checks; semantic/release review remains mandatory."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/v1"
files = [ROOT / "AGENTS.md", ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


for path in files:
    content = path.read_text()
    require(len(re.findall(r"^```", content, re.M)) % 2 == 0,
            f"Unclosed fenced block: {path.relative_to(ROOT)}")
    for link in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", content):
        if re.match(r"(?:https?://|mailto:|#)", link):
            continue
        target = link.split("#", 1)[0].strip("<>")
        require((path.parent / target).exists(), f"Missing local link: {path.name}: {link}")

index = (DOCS / "README.md").read_text()
for guide in ("HOW_IT_WORKS.md", "EXTENDING_MLFORGE.md"):
    require((ROOT / "docs" / guide).exists(), f"Missing practical guide: {guide}")
    require(f"](../{guide})" in index, f"Missing guide index link: {guide}")
    require(f"](docs/{guide})" in (ROOT / "AGENTS.md").read_text(), f"Missing agent guide link: {guide}")

required = "PRODUCT_SPEC UX_FLOW DESIGN_SYSTEM ARCHITECTURE DATASET_SPEC ML_PIPELINE EXPORT_SPEC TEST_PLAN IMPLEMENTATION_PLAN ACCEPTANCE_CRITERIA CODEX_EXECUTION RESUME_PROTOCOL BUILD_STATE BUILD_LOG CODEX_PROMPT PLANNING_REVIEW REPOSITORY_AUDIT".split()
for name in required:
    require((DOCS / f"{name}.md").exists(), f"Missing canonical document: {name}")
    require(f"]({name}.md)" in index, f"Missing canonical index entry: {name}")
plan = (DOCS / "IMPLEMENTATION_PLAN.md").read_text()
phases = re.findall(r"^## (P\d\d) — (.*?)(?=^## |\Z)", plan, re.M | re.S)
require([p for p, _ in phases] == [f"P{n:02}" for n in range(1, 11)], "Expected phases P01–P10")
for phase, body in phases:
    for field in ("Depends", "Objective", "Work", "Tests", "Docs", "Complete when", "Commit boundar"):
        require(f"**{field}" in body, f"Missing phase contract: {phase}/{field}")
units = set(re.findall(r"\bP\d\d\.[123]\b", plan))
require(units == {f"P{p:02}.{u}" for p in range(1, 11) for u in range(1, 4)}, "Expected 30 work units")
acceptance = (DOCS / "ACCEPTANCE_CRITERIA.md").read_text()
ids = re.findall(r"^\| (A\d\d) \|", acceptance, re.M)
require(ids == [f"A{n:02}" for n in range(1, 29)], "Expected unique A01–A28")
review = (DOCS / "PLANNING_REVIEW.md").read_text().split("## Acceptance → implementation → verification traceability")[-1]
require(re.findall(r"^\| (A\d\d) \|", review, re.M) == ids, "Incomplete acceptance traceability")
for name in ("AGENTS.md", "docs/v1/CODEX_EXECUTION.md", "docs/v1/RESUME_PROTOCOL.md"):
    content = (ROOT / name).read_text()
    require("BUILD_STATE" in content, f"Missing current-state pointer: {name}")
    require("top of BUILD_LOG" not in content, f"Stale current-state ownership: {name}")
require("## Current checkpoint" not in (DOCS / "BUILD_LOG.md").read_text(), "Duplicate current pointer in history")

# Check default normal-text token pairings independently of Textual.
colors = dict(re.findall(r"^\| ([a-z-]+) \| (#[0-9A-Fa-f]{6}) \|", (DOCS / "DESIGN_SYSTEM.md").read_text(), re.M))
def luminance(hex_color):
    values = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
    return sum(c * w for c, w in zip(linear, (0.2126, 0.7152, 0.0722)))

pairs = [(fg, bg) for fg in ("text", "muted", "accent", "warning", "error")
         for bg in ("background", "surface", "elevated", "selected")]
pairs.append(("on-accent", "accent"))
for fg, bg in pairs:
    require(fg in colors and bg in colors, f"Missing palette tokens: {fg}/{bg}")
    if fg in colors and bg in colors:
        a, b = sorted((luminance(colors[fg]), luminance(colors[bg])))
        require((b + 0.05) / (a + 0.05) >= 4.5, f"Low default contrast: {fg}/{bg}")
if errors:
    raise SystemExit("\n".join(errors))
print(f"PASS: {len(files)} Markdown files, local links/fences, owner index, 10 phases, 30 units, 28 mapped acceptance IDs, state ownership, {len(pairs)} palette pairs")
print("Manual semantic review, actual rendered TUI checks and implementation acceptance remain separate.")
