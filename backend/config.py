import os

# ── Analysis limits ─────────────────────────────────────────────────────────
MAX_COMMITS: int = 1000

# ── Trust layer: uncertainty-aware attribution ──────────────────────────────
# Cluster bootstrap over files for ownership confidence intervals. The interval
# captures sensitivity to file composition (the dominant honest variance source),
# NOT blame-method error — that is handled by the reliability layer.
TRUST_BOOTSTRAP_SAMPLES: int = 1000
TRUST_CI: float = 0.90              # 90% interval (5th–95th percentile)
TRUST_MIN_FILES_FOR_CI: int = 2     # below this, ownership cannot be bounded
TRUST_BOOTSTRAP_SEED: int = 12345   # fixed for reproducibility

# ── Trust layer: history reliability ─────────────────────────────────────────
# Reliability estimates whether a repo's history can support trustworthy
# attribution. Detection is itself heuristic — it flags risk, never certainty.
# Each detector yields a penalty in [0, cap]; reliability = ∏ (1 − penalty).
TRUST_SQUASH_RATIO_FULL: float = 0.5    # squash-like commit ratio that maxes the penalty
TRUST_SQUASH_PENALTY_CAP: float = 0.9
TRUST_REBASE_GAP_SECONDS: int = 3600    # committer−author gap suggesting a rebase
TRUST_REBASE_RATIO_FULL: float = 0.5
TRUST_REBASE_PENALTY_CAP: float = 0.7
TRUST_FORMAT_FILES: int = 20            # files touched in one commit → format-bomb candidate
TRUST_FORMAT_CHURN: int = 500
TRUST_FORMAT_PENALTY_PER: float = 0.2   # per format-bomb commit
TRUST_FORMAT_PENALTY_CAP: float = 0.6
TRUST_LOW_COMMITS: int = 10             # below this total, granularity is poor
TRUST_MIN_COMMITS_PER_AUTHOR: int = 3
TRUST_GRANULARITY_PENALTY_CAP: float = 0.6
TRUST_TIMESTAMP_PENALTY_CAP: float = 0.5

# Reliability score → band cutoffs.
TRUST_BAND_HIGH: float = 0.80
TRUST_BAND_MODERATE: float = 0.55
TRUST_BAND_LOW: float = 0.30

# ── Trust layer: confidence & ethical gating ─────────────────────────────────
# A role verdict is a "boundary case" when its impact score sits within this
# fraction of the expected per-author average of a role threshold.
TRUST_BOUNDARY_MARGIN: float = 0.25
# Reliability below this floor caps confidence and raises the unreliable banner.
TRUST_RELIABILITY_FLOOR: float = 0.50
# Cold-start confidence ladder cutoffs (deliberately under-confident; never "high").
TRUST_CONFIDENCE_FLOOR: float = 0.20   # below → "insufficient — manual review"
TRUST_CONF_MODERATE: float = 0.40      # at/above → "moderate" (cold-start ceiling)
TRUST_CALIB_MIN_LABELS: int = 40       # reviews needed before leaving cold-start
TRUST_ISO_MIN_LABELS: int = 150        # reviews needed before isotonic (else Platt)
# Calibrated-regime confidence band cutoffs (on the calibrated probability).
TRUST_CALIB_BAND_HIGH: float = 0.80
TRUST_CALIB_BAND_MODERATE: float = 0.60
TRUST_CALIB_BAND_LOW: float = 0.40

# ── Code-quality metric weights (must sum to 1.0) ───────────────────────────
QUALITY_WEIGHT_CC: float = 0.35
QUALITY_WEIGHT_MI: float = 0.25
QUALITY_WEIGHT_CD: float = 0.15
QUALITY_WEIGHT_LINTER: float = 0.15
QUALITY_WEIGHT_READABILITY: float = 0.10

# Ideal comment-density ratio (15 % of lines should be comments)
QUALITY_CD_TARGET_RATIO: float = 0.15

# Lines longer than this are penalised by the linter heuristic
QUALITY_MAX_LINE_LENGTH: int = 100

# Lines longer than this reduce the readability score
QUALITY_IDEAL_LINE_LENGTH: int = 60

# ── Impact-score weights (must sum to 1.0) ──────────────────────────────────
IMPACT_WEIGHT_COMMITS: float = 0.30
IMPACT_WEIGHT_LINES: float = 0.50
IMPACT_WEIGHT_FILES: float = 0.20

# ── Integrity forensics ──────────────────────────────────────────────────────
# Deadline-spike: the final fraction of the project timeline treated as "near the
# deadline", and how concentrated an author's additions must be there to flag.
INTEGRITY_DEADLINE_WINDOW: float = 0.10   # last 10% of the timeline
INTEGRITY_DEADLINE_RATIO: float = 0.60    # ≥60% of an author's additions land late
INTEGRITY_DEADLINE_MIN_LINES: int = 50    # ignore trivially small contributions

# Bulk-paste: a commit is anomalous if its additions dwarf the author's own
# median commit size AND exceed an absolute floor. A median-based test is used
# (not mean/stdev) because a single huge paste inflates the stdev enough to hide
# itself — the robust statistic catches what the z-score misses.
INTEGRITY_PASTE_MIN_COMMITS: int = 5      # need enough commits for a baseline
INTEGRITY_PASTE_MEDIAN_MULT: float = 5.0  # additions must exceed median × this
INTEGRITY_PASTE_FLOOR: int = 300          # absolute additions floor for a flag

# Authorship laundering: minimum count of a person committing *another* person's
# authored work before flagging (advisory — committer≠author is often legitimate).
INTEGRITY_LAUNDERING_MIN: int = 3
# Committer identities to ignore (bots / platform merge committers).
INTEGRITY_BOT_EMAIL_FRAGMENTS: tuple[str, ...] = (
    "noreply@github.com", "web-flow", "actions@github.com", "[bot]",
)

# ── Explainability ───────────────────────────────────────────────────────────
# Divergence (effort − ownership) beyond this magnitude earns a narrative note.
EXPLAIN_DIVERGENCE_NOTE: float = 20.0
# Attributed quality below this is called out as a negative factor.
EXPLAIN_QUALITY_LOW: float = 50.0
# Optional LLM prose-polish (constrained to the evidence dict). Off by default;
# the deterministic template is always the source of truth.
EXPLAIN_USE_LLM: bool = os.getenv("GITSIGHT_EXPLAIN_LLM", "0") == "1"

# ── Role-assignment thresholds (relative to expected average per author) ─────
ROLE_MAJOR_THRESHOLD: float = 1.5   # score ≥ 1.5× average → Major Contributor
ROLE_FREE_RIDER_THRESHOLD: float = 0.3  # score ≤ 0.3× average → Free Rider

# ── Source files eligible for quality analysis ───────────────────────────────
ANALYSABLE_EXTENSIONS: tuple[str, ...] = (
    ".py", ".js", ".ts", ".html", ".css",
    ".java", ".cpp", ".c", ".go",
)

# ── Attribution (line-ownership) ─────────────────────────────────────────────
# Extensions whose surviving lines count toward authorship ownership.
OWNERSHIP_EXTENSIONS: tuple[str, ...] = ANALYSABLE_EXTENSIONS

# Path fragments marking vendored / generated / build output. Files whose path
# contains any of these are excluded from ownership and effort so that committing
# dependencies or build artifacts cannot inflate a contributor's score.
VENDORED_PATH_FRAGMENTS: tuple[str, ...] = (
    "node_modules/", "vendor/", "dist/", "build/", "out/",
    ".min.", "site-packages/", "third_party/", "thirdparty/",
    "__pycache__/", ".cache/", "venv/",
)

# Exact basenames that are generated/lock files (never hand-authored line-by-line).
GENERATED_BASENAMES: frozenset[str] = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "pipfile.lock", "composer.lock", "cargo.lock", "go.sum",
})

# ── Quality attribution (function-granularity) ───────────────────────────────
# Functions whose cyclomatic complexity exceeds this are flagged "complex".
QUALITY_CC_HIGH_THRESHOLD: float = 10.0
# How the per-author quality score blends complexity vs. maintainability.
QUALITY_ATTR_WEIGHT_CC: float = 0.6
QUALITY_ATTR_WEIGHT_MI: float = 0.4
# Maintainability Index (radon) is Python-only; other languages use CC alone.
MAINTAINABILITY_EXTENSIONS: tuple[str, ...] = (".py",)

# ── Impact-profile weights — how the dimensions combine into the impact score ─
# (must sum to 1.0) Ownership of surviving code is weighted highest because it
# is the least gameable signal; raw churn (effort) is weighted lowest.
IMPACT_WEIGHT_OWNERSHIP: float = 0.55
IMPACT_WEIGHT_BREADTH: float = 0.20
IMPACT_WEIGHT_EFFORT: float = 0.25

# ── Persistence & caching ────────────────────────────────────────────────────
# Results are cached keyed on (repo_url, HEAD sha): an unchanged repo is never
# re-analysed. Set GITSIGHT_CACHE=0 to disable.
CACHE_ENABLED: bool = os.getenv("GITSIGHT_CACHE", "1") == "1"


def get_db_path() -> str:
    env_path = os.getenv("GITSIGHT_DB_PATH")
    if env_path:
        os.makedirs(os.path.dirname(env_path) or ".", exist_ok=True)
        return env_path
    cache_dir = os.path.join(os.path.dirname(__file__), ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "gitsight.db")


# ── Clone directory ──────────────────────────────────────────────────────────
def get_clone_root() -> str:
    env_dir = os.getenv("GITSIGHT_CLONE_DIR")
    if env_dir:
        os.makedirs(env_dir, exist_ok=True)
        return env_dir
    clone_root = os.path.join(os.path.dirname(__file__), ".cache", "repo_clones")
    os.makedirs(clone_root, exist_ok=True)
    return clone_root

# ── Server ───────────────────────────────────────────────────────────────────
HOST: str = os.getenv("GITSIGHT_HOST", "127.0.0.1")
PORT: int = int(os.getenv("GITSIGHT_PORT", "8000"))
ALLOWED_ORIGINS: list[str] = os.getenv("GITSIGHT_ALLOWED_ORIGINS", "*").split(",")
