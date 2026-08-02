"""Tier 3 tests: mocks/fixtures, cache, scoring (§3.1-3.3, §4.1 'Scoring/Cache' contracts)."""
from cravecare import cache as cache_module
from cravecare import scoring


def test_seeded_cache_has_items(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn)
    assert len(items) == 16


def test_cache_read_is_area_scoped(seeded_cache_conn):
    bandra_items = cache_module.read_all(seeded_cache_conn, area="Bandra West")
    assert all(i.area == "Bandra West" for i in bandra_items)
    assert len(bandra_items) < len(cache_module.read_all(seeded_cache_conn))


def test_cache_last_updated_is_recorded(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn)
    assert all(i.last_updated for i in items)
    assert cache_module.latest_updated_at(seeded_cache_conn) is not None


def test_reddit_score_within_0_5_bounds():
    comments = [
        {"text": "Amazing food, loved it!", "upvotes": 50, "posted_days_ago": 10},
        {"text": "Terrible experience, would not recommend.", "upvotes": 5, "posted_days_ago": 20},
        {"text": "It was okay, nothing special.", "upvotes": 2, "posted_days_ago": 30},
    ]
    score, mentions = scoring.reddit_score_from_comments(comments)
    assert score is not None
    assert 0.0 <= score <= 5.0
    assert mentions == 3


def test_reddit_min_sample_floor_excludes_below_three():
    comments = [
        {"text": "Great!", "upvotes": 10, "posted_days_ago": 5},
        {"text": "Pretty good.", "upvotes": 3, "posted_days_ago": 10},
    ]
    score, mentions = scoring.reddit_score_from_comments(comments)
    assert score is None
    assert mentions == 2


def test_reddit_window_excludes_old_comments():
    comments = [
        {"text": "Great!", "upvotes": 10, "posted_days_ago": 5},
        {"text": "Pretty good.", "upvotes": 3, "posted_days_ago": 10},
        {"text": "Solid.", "upvotes": 4, "posted_days_ago": 20},
        {"text": "Old comment outside window.", "upvotes": 100, "posted_days_ago": 400},
    ]
    score, mentions = scoring.reddit_score_from_comments(comments)
    assert mentions == 3  # the 400-day-old comment is excluded by the 12-month window


def test_quality_score_redistributes_weights_below_floor():
    # Only 1 relevant comment -> Reddit excluded -> weights become 0.57/0.43.
    comments = [{"text": "Fine.", "upvotes": 1, "posted_days_ago": 5}]
    breakdown = scoring.compute_quality_score(4.0, 4.0, comments)
    assert breakdown.reddit_score is None
    assert breakdown.weights_used == scoring.WEIGHTS_WITHOUT_REDDIT
    assert breakdown.quality_score == round(0.57 * 4.0 + 0.43 * 4.0, 4)


def test_quality_score_uses_full_weights_with_enough_mentions():
    comments = [
        {"text": "Great!", "upvotes": 10, "posted_days_ago": 5},
        {"text": "Pretty good.", "upvotes": 3, "posted_days_ago": 10},
        {"text": "Solid.", "upvotes": 4, "posted_days_ago": 20},
    ]
    breakdown = scoring.compute_quality_score(4.0, 4.0, comments)
    assert breakdown.reddit_score is not None
    assert breakdown.weights_used == scoring.WEIGHTS_WITH_REDDIT
    expected = 0.4 * 4.0 + 0.3 * 4.0 + 0.3 * breakdown.reddit_score
    assert breakdown.quality_score == round(expected, 4)


def test_quality_score_known_mock_inputs_exact():
    """§4.1: 'Quality Score sums match expected values for known mock inputs.'

    Uses identical zero-upvote comments so the weighted average degrades to a
    plain average (equal weights), and derives the expected reddit_score
    directly from VADER's own polarity output rather than assuming a
    hand-picked "neutral" string scores exactly 0 (VADER's lexicon can score
    plain sentences non-zero - see the flagged VADER-fit note in scoring.py).
    """
    text = "It was an average meal, nothing special either way."
    comments = [{"text": text, "upvotes": 0, "posted_days_ago": 5} for _ in range(3)]
    expected_polarity = scoring.polarity_of(text)
    expected_reddit_score = round((expected_polarity + 1) * 2.5, 10)

    breakdown = scoring.compute_quality_score(5.0, 5.0, comments)

    assert round(breakdown.reddit_score, 10) == expected_reddit_score
    expected_quality = round(0.4 * 5.0 + 0.3 * 5.0 + 0.3 * breakdown.reddit_score, 4)
    assert breakdown.quality_score == expected_quality
