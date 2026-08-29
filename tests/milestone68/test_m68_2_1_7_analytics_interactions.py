from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_inflection_inline_detail_uses_readable_compact_typography():
    source = (
        ROOT / "ui/workstation/src/InflectionAnalyticsPage.tsx"
    ).read_text()

    assert "InlineCandidateDetail" in source
    assert "fontSize: 13" in source
    assert "fontSize: 12" in source
    assert "lineHeight: 1.35" in source
    assert "repeat(3, minmax(250px, 1fr))" in source


def test_mispricing_candidate_table_has_header_filters_and_inline_detail():
    source = (
        ROOT / "ui/workstation/src/OptionsMispricingAnalyticsPage.tsx"
    ).read_text()

    assert "HEADER_FILTER_FIELDS" in source
    assert "CandidateHeaderFilter" in source
    assert "minimumProbability" in source
    assert "expectedValueBand" in source
    assert "expandedSnapshotId" in source
    assert "event.key === 'Enter' || event.key === ' '" in source
    assert "InlineValuationDetail" in source
    assert "Exact market lineage" in source
    assert "Option legs" in source
    assert "DetailDrawer" not in source
    assert "AnalyticsTable" not in source
