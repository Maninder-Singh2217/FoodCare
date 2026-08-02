"""Quality Score computation per spec §3.1-3.2.

Reddit sentiment normalization pipeline:
  raw comments -> VADER polarity [-1,1] -> log(1+upvotes) weighted avg
  -> rescale to [0,5] -> combine with Swiggy/Google via weighted formula.

NOTE (flagged assumption, spec ambiguity beyond §6): §3.2 step 1 mentions a
"rolling 12-month window (older = decayed relevance)" but defines no decay
function - only an upvote-based weighting formula is given (step 3). We
implement the 12-month window as a hard cutoff (comments older than 365
days are excluded entirely) rather than inventing a gradual age-decay
curve, since the spec supplies no such formula.

FLAGGED LIMITATION (VADER fit, spec §6 gap #4): spot-checking VADER against
the seeded Reddit-style fixture text showed it misreads some idiomatic
phrasing - e.g. "never misses" scored negative (polarity -0.325) despite
being clearly positive slang, and some enthusiastic-but-plainly-worded
praise scored near 0. Per the spec's default-to-VADER guidance, we keep it
since (a) it's free/instant/local, matching the manual-cache-refresh
design, and (b) the multi-source weighted formula limits the blast radius
of any single misread comment (Swiggy+Google make up 57-70% of the final
Quality Score). Revisit only if this shows up as a user-visible quality
problem post-launch, per the spec's own "reasonable defaults acceptable"
framing for this gap.
"""
import math
from dataclasses import dataclass

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()

REDDIT_WINDOW_DAYS = 365
MIN_REDDIT_MENTIONS = 3

WEIGHTS_WITH_REDDIT = {"swiggy": 0.4, "google": 0.3, "reddit": 0.3}
WEIGHTS_WITHOUT_REDDIT = {"swiggy": 0.57, "google": 0.43}


@dataclass
class ScoreBreakdown:
    quality_score: float
    reddit_score: float | None
    reddit_mentions_used: int
    weights_used: dict


def polarity_of(text: str) -> float:
    """Return VADER compound polarity in [-1, 1] for a single comment."""
    return _analyzer.polarity_scores(text)["compound"]


def filter_recent_comments(comments: list[dict], window_days: int = REDDIT_WINDOW_DAYS) -> list[dict]:
    return [c for c in comments if c.get("posted_days_ago", 0) <= window_days]


def weighted_average_polarity(comments: list[dict]) -> float:
    """§3.2 steps 2-4: polarity per comment, weighted by log(1+upvotes)."""
    total_weight = 0.0
    weighted_sum = 0.0
    for c in comments:
        polarity = polarity_of(c["text"])
        weight = math.log(1 + max(c.get("upvotes", 0), 0))
        weighted_sum += polarity * weight
        total_weight += weight
    if total_weight == 0:
        # All-zero-upvote comments still count equally, avoid div/0.
        polarities = [polarity_of(c["text"]) for c in comments]
        return sum(polarities) / len(polarities) if polarities else 0.0
    return weighted_sum / total_weight


def reddit_score_from_comments(comments: list[dict]) -> tuple[float | None, int]:
    """§3.2 steps 1,5,6: window filter, rescale to 0-5, minimum sample floor.

    Returns (reddit_score_or_None, mentions_used). None means below the
    minimum-sample floor (fewer than 3 relevant mentions) - caller must
    redistribute weights per §3.2 step 6.
    """
    recent = filter_recent_comments(comments)
    if len(recent) < MIN_REDDIT_MENTIONS:
        return None, len(recent)
    avg_polarity = weighted_average_polarity(recent)
    reddit_score = (avg_polarity + 1) * 2.5
    reddit_score = max(0.0, min(5.0, reddit_score))
    return reddit_score, len(recent)


def compute_quality_score(swiggy_rating: float, google_rating: float, reddit_comments: list[dict]) -> ScoreBreakdown:
    """§3.1: weighted sum of normalized Swiggy/Google/Reddit scores.

    Swiggy/Google are already 0-5 and used as-is. Reddit is derived via
    reddit_score_from_comments. If Reddit is excluded (min-sample floor),
    weights redistribute per §3.2 step 6: Swiggy -> 0.57, Google -> 0.43.
    """
    reddit_score, mentions_used = reddit_score_from_comments(reddit_comments)

    if reddit_score is None:
        weights = WEIGHTS_WITHOUT_REDDIT
        quality_score = (
            weights["swiggy"] * swiggy_rating + weights["google"] * google_rating
        )
    else:
        weights = WEIGHTS_WITH_REDDIT
        quality_score = (
            weights["swiggy"] * swiggy_rating
            + weights["google"] * google_rating
            + weights["reddit"] * reddit_score
        )

    return ScoreBreakdown(
        quality_score=round(quality_score, 4),
        reddit_score=reddit_score,
        reddit_mentions_used=mentions_used,
        weights_used=weights,
    )
