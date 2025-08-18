from scalp.signals import confluence_quality


def test_confluence_quality_varies_with_score():
    assert confluence_quality(0.9) == "A"
    assert confluence_quality(0.6) == "B"
    assert confluence_quality(0.2) == "C"
