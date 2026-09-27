"""P09 recovery rehearsal on a disposable clone (RESUME_PROTOCOL, A27).

Run from a committed checkout: python scripts/rehearse_recovery.py

Builds the three synthetic interruption scenarios in a throwaway clone, applies
the documented read-only reconciliation, and records whether partial work was
preserved, whether unknown checks stay unverified, and which unit is next.
"""

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
WORK = Path(tempfile.mkdtemp(prefix="mlforge-recovery-"))
FIXTURE = WORK / "fixture"


def git(*args, cwd=FIXTURE):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def digest(path):
    return hashlib.sha256((FIXTURE / path).read_bytes()).hexdigest()


def check_status(log):
    """RESUME_PROTOCOL: only a recorded exit status is definitive."""
    text = (FIXTURE / log).read_text()
    match = re.search(r"^EXIT (\d+)$", text, re.M)
    if match is None:
        return "UNKNOWN"
    return "PASS" if match[1] == "0" else "FAIL"


def unit_order():
    plan = (FIXTURE / "docs/v1/IMPLEMENTATION_PLAN.md").read_text()
    return re.findall(r"\b(P\d\d\.\d)\b", plan.split("## P01")[0])


git("clone", "--quiet", "--no-hardlinks", str(SOURCE), str(FIXTURE), cwd=WORK)
planning_base = "0798b5b7d7ae07b0bd9fe454b3ddf90eba5434d5"
head = git("rev-parse", "HEAD")
evidence = {"fixture": "disposable local clone", "source_head": head}

# Scenario 3 first: Git ahead of the log (a verified commit the pointer omits).
recorded = git("rev-parse", "HEAD")
(FIXTURE / "docs/v1/REHEARSAL_NOTE.md").write_text("Rehearsal-only commit.\n")
git("add", "docs/v1/REHEARSAL_NOTE.md")
git(
    "-c",
    "user.name=rehearsal",
    "-c",
    "user.email=rehearsal@invalid",
    "commit",
    "-q",
    "-m",
    "test: rehearsal commit ahead of BUILD_STATE",
)
ahead = git("log", "--format=%H %s", f"{recorded}..HEAD").splitlines()

# Scenario 1: stale pointer plus staged, unstaged and untracked partial work.
state = FIXTURE / "docs/v1/BUILD_STATE.md"
state.write_text(
    state.read_text()
    + "- STALE REHEARSAL POINTER: Active unit P08.2 EDITING; next action: "
    "implement export screen.\n"
)
trial = "src/mlforge/tui/screens/trial.py"
(FIXTURE / trial).write_text((FIXTURE / trial).read_text() + "# staged partial\n")
git("add", trial)
log_path = "docs/v1/BUILD_LOG.md"
(FIXTURE / log_path).write_text(
    (FIXTURE / log_path).read_text() + "\nUnstaged partial history line.\n"
)
untracked = "tests/mlforge/tui/test_partial_rehearsal.py"
(FIXTURE / untracked).write_text("def test_partial():\n    assert True\n")

# Scenario 2: a check whose log has no definitive exit status.
(FIXTURE / ".mlforge-build").mkdir(exist_ok=True)
(FIXTURE / ".mlforge-build/rehearsal-unknown.log").write_text("....... [ 40%]\n")
(FIXTURE / ".mlforge-build/rehearsal-pass.log").write_text("3 passed\nEXIT 0\n")

protected = ["docs/v1/BUILD_STATE.md", trial, log_path, untracked]
before = {path: digest(path) for path in protected}
index_before = git("diff", "--cached", "--name-only")

# Read-only reconciliation exactly as documented (no reset/stash/checkout).
observed = {
    "branch": git("branch", "--show-current"),
    "status": git("status", "--short").splitlines(),
    "staged": git("diff", "--cached", "--name-only").splitlines(),
    "unstaged": git("diff", "--name-only").splitlines(),
    "untracked": git("ls-files", "--others", "--exclude-standard").splitlines(),
    "planning_ancestry": subprocess.run(
        ["git", "merge-base", "--is-ancestor", planning_base, "HEAD"], cwd=FIXTURE
    ).returncode
    == 0,
}
last_code_subject = git("log", "-1", "--format=%s", "--", "src", "scripts", "tests")
pointer = state.read_text()
stale = "P08.2 EDITING" in pointer and "verify installed Try" in git(
    "log", "--format=%s", "-5"
)
units = unit_order()
next_unit = units[units.index("P08.3") + 1] if "P08.3" in units else None
after = {path: digest(path) for path in protected}

evidence.update(
    {
        "scenario_git_ahead": {
            "recorded_pointer_sha": recorded,
            "commits_ahead": ahead,
            "decision": "reconstruct evidence for the commit and repair the "
            "pointer; do not rebuild completed phases",
        },
        "scenario_stale_pointer_partial_edits": {
            "observed": observed,
            "pointer_detected_stale": stale,
            "last_code_commit_subject": last_code_subject,
            "partial_work_preserved": before == after
            and index_before == git("diff", "--cached", "--name-only"),
            "hashes": after,
        },
        "scenario_unknown_check": {
            "rehearsal-unknown.log": check_status(
                ".mlforge-build/rehearsal-unknown.log"
            ),
            "rehearsal-pass.log": check_status(".mlforge-build/rehearsal-pass.log"),
            "decision": "UNKNOWN is never PASS; rerun that check",
        },
        "plan_units": units,
        "next_unit_after_P08_3": next_unit,
    }
)
assert evidence["scenario_stale_pointer_partial_edits"]["partial_work_preserved"]
assert observed["planning_ancestry"] and observed["branch"] == "v1/mlforge"
assert observed["staged"] == [trial] and log_path in observed["unstaged"]
assert untracked in observed["untracked"]
assert evidence["scenario_unknown_check"]["rehearsal-unknown.log"] == "UNKNOWN"
assert len(ahead) == 1 and stale and next_unit == "P09.1"
report = SOURCE / ".mlforge-build/recovery-p09.json"
report.write_text(json.dumps(evidence, indent=2) + "\n")
print(f"Recovery rehearsal passed: {report} (fixture {FIXTURE})")
