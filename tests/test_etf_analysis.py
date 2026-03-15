import unittest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

class TestETFAnalysis(unittest.TestCase):
    def setUp(self):
        """Set up test data"""
        self.mock_etf_data = pd.DataFrame({
            'name': ['ETF1', 'ETF2', 'ETF3'],
            'ter': [0.1, 0.2, 0.3],
            'dividends': ['Distributing', 'Distributing', 'Accumulating'],
            'last_year_return_per_risk': [0.5, 0.6, 0.4],
            'last_three_years_return_per_risk': [0.4, 0.5, 0.3],
            'last_five_years_return_per_risk': [0.3, 0.4, 0.2],
            'last_year_volatility': [0.15, 0.18, 0.12]
        })

    def test_calculate_weighted_scores(self):
        """Test weighted score calculation"""
        weights = {
            'last_five_years_return_per_risk': 0.2,
            'last_three_years_return_per_risk': 0.3,
            'last_year_return_per_risk': 0.5
        }
        
        expected_scores = [
            0.2 * 0.3 + 0.3 * 0.4 + 0.5 * 0.5,
            0.2 * 0.4 + 0.3 * 0.5 + 0.5 * 0.6,
            0.2 * 0.2 + 0.3 * 0.3 + 0.5 * 0.4
        ]
        total = sum(expected_scores)
        expected_scores = [score/total for score in expected_scores]
        
        # Calculate actual scores
        self.mock_etf_data['weighted_score'] = (
            weights['last_five_years_return_per_risk'] * self.mock_etf_data['last_five_years_return_per_risk'] +
            weights['last_three_years_return_per_risk'] * self.mock_etf_data['last_three_years_return_per_risk'] +
            weights['last_year_return_per_risk'] * self.mock_etf_data['last_year_return_per_risk']
        )
        self.mock_etf_data['weighted_score'] = self.mock_etf_data['weighted_score'] / self.mock_etf_data['weighted_score'].sum()
        
        np.testing.assert_array_almost_equal(
            self.mock_etf_data['weighted_score'].values,
            expected_scores,
            decimal=5
        )

    def test_filter_distributing_etfs(self):
        """Test filtering for distributing ETFs"""
        distributing_etfs = self.mock_etf_data[self.mock_etf_data['dividends'] == 'Distributing']
        self.assertEqual(len(distributing_etfs), 2)
        self.assertTrue(all(distributing_etfs['dividends'] == 'Distributing'))

    @patch('requests.get')
    def test_etf_availability_check(self, mock_get):
        """Test ETF availability checking"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{'ticker': 'ETF1', 'available': True}]
        mock_get.return_value = mock_response

        # Import the actual function
        from etf_utils.platform_check import check_etf_availability

        # Test availability check
        result = check_etf_availability('ETF1')
        self.assertTrue(result)
        mock_get.assert_called_once()
        
if __name__ == '__main__':
    unittest.main()


# ---------------------------------------------------------------------------
# New asset class tests (pytest-style, no class needed)
# ---------------------------------------------------------------------------

from etf_utils.data_io import get_asset_class_from_filename
from etf_utils.metrics import interpolate_adjustment_factor


def test_get_asset_class_preciousmetals():
    assert get_asset_class_from_filename('justetf_class-preciousMetals_global.csv') == 'preciousMetals'


def test_get_asset_class_commodities():
    assert get_asset_class_from_filename('justetf_class-commodities_global.csv') == 'commodities'


def test_get_asset_class_commodities_intermediate():
    """Broad commodity ETCs use 'commodities' as the intermediate filename suffix."""
    from etf_utils.data_io import _asset_class_from_intermediate_filename
    assert _asset_class_from_intermediate_filename('summary_commodities.csv') == 'commodities'


def test_four_class_weight_normalization():
    """Normalized weights for 4 asset classes must sum to ~100."""
    # Fixed inputs: 65 / 10 / 5 / 10
    eq_risk, bnd_risk, pm_risk, cmd_risk = 65, 10, 5, 10
    # No Sharpe adjustment (factors = 1.0)
    adjs = [w * 1.0 for w in (eq_risk, bnd_risk, pm_risk, cmd_risk)]
    total = sum(adjs)
    normalized = [round(w / total * 100, 2) for w in adjs]
    assert abs(sum(normalized) - 100.0) < 0.1


def test_pm_overlap_gold():
    """Gold → 14.29% BCOM overlap (heaviest duplication with commodity ETC)."""
    from etf_utils.config import DATA_CONFIG
    import json
    bcom = json.loads((DATA_CONFIG / 'commodity_index_weights.json').read_text())
    pm_bcom = bcom['precious_metals']

    def overlap(name):
        n = name.lower()
        if 'palladium' in n: return pm_bcom['palladium']
        if 'platinum'  in n: return pm_bcom['platinum']
        if 'silver'    in n: return pm_bcom['silver']
        if 'gold'      in n: return pm_bcom['gold']
        return pm_bcom['mixed']

    assert overlap('iShares Physical Gold ETC') == 14.29
    assert overlap('WisdomTree Physical Silver') == 4.49
    assert overlap('iShares Physical Platinum ETC') == 0.0
    assert overlap('WisdomTree Physical Palladium') == 0.0
    assert overlap('WisdomTree Physical Precious Metals') == pm_bcom['mixed']


def test_pm_overlap_sort_order():
    """Overlap-aware sort puts platinum/palladium before silver before gold."""
    import pandas as pd
    from etf_utils.config import DATA_CONFIG
    import json
    bcom = json.loads((DATA_CONFIG / 'commodity_index_weights.json').read_text())
    pm_bcom = bcom['precious_metals']

    def overlap(name):
        n = name.lower()
        if 'palladium' in n: return pm_bcom['palladium']
        if 'platinum'  in n: return pm_bcom['platinum']
        if 'silver'    in n: return pm_bcom['silver']
        if 'gold'      in n: return pm_bcom['gold']
        return pm_bcom['mixed']

    df = pd.DataFrame({
        'name': ['iShares Physical Gold', 'iShares Physical Silver',
                 'iShares Physical Platinum', 'WisdomTree Physical Palladium'],
        'ter':  [0.12, 0.20, 0.20, 0.49],
    })
    df['commodity_overlap_pct'] = df['name'].apply(overlap)
    df = df.sort_values(['commodity_overlap_pct', 'ter'], ascending=[True, True])

    # First two should be the zero-overlap metals (platinum and palladium)
    assert df.iloc[0]['commodity_overlap_pct'] == 0.0
    assert df.iloc[1]['commodity_overlap_pct'] == 0.0
    # Silver before gold
    assert df.iloc[2]['commodity_overlap_pct'] == 4.49
    assert df.iloc[3]['commodity_overlap_pct'] == 14.29


def test_pm_diversity_no_duplicate_metals():
    """Metal-diversity groupby ensures the top-2 selection spans two different metal types.

    Scenario: pool contains two platinum ETCs (TER 0.20 and 0.49) and one palladium ETC
    (TER 0.19).  Without diversity logic head(2) returns both platinum funds.
    With diversity logic the result must be one palladium + one platinum.
    """
    import pandas as pd
    from etf_utils.config import DATA_CONFIG
    import json

    bcom = json.loads((DATA_CONFIG / 'commodity_index_weights.json').read_text())
    pm_bcom = bcom['precious_metals']

    def overlap(name):
        n = name.lower()
        if 'palladium' in n: return pm_bcom['palladium']
        if 'platinum'  in n: return pm_bcom['platinum']
        if 'silver'    in n: return pm_bcom['silver']
        if 'gold'      in n: return pm_bcom['gold']
        return pm_bcom['mixed']

    def metal_type(name):
        n = name.lower()
        if 'palladium' in n: return 'palladium'
        if 'platinum'  in n: return 'platinum'
        if 'silver'    in n: return 'silver'
        if 'gold'      in n: return 'gold'
        return 'mixed'

    # Two platinum ETCs + one palladium ETC — all with 0% BCOM overlap
    df = pd.DataFrame({
        'name': ['iShares Physical Platinum', 'WisdomTree Physical Platinum',
                 'Invesco Physical Palladium'],
        'ter':  [0.20, 0.49, 0.19],
        'last_year_return_per_risk': [2.26, 2.45, 1.55],
    })
    df['commodity_overlap_pct'] = df['name'].apply(overlap)
    df['metal_type'] = df['name'].apply(metal_type)

    # Apply the same sorting used in the notebook
    df = df.sort_values(
        ['commodity_overlap_pct', 'ter', 'last_year_return_per_risk'],
        ascending=[True, True, False],
    )

    # Without diversity: head(2) would give two platinum ETCs
    assert list(df.head(2)['metal_type']) == ['palladium', 'platinum'], \
        "Sorted order is palladium (TER 0.19) then platinum (TER 0.20)"

    # With diversity: groupby metal_type → best per type → top 2 types
    best_per_metal = (
        df
        .groupby('metal_type', sort=False)
        .first()
        .reset_index()
        .sort_values(['commodity_overlap_pct', 'ter'], ascending=[True, True])
    )
    selected = best_per_metal.head(2)

    assert len(selected) == 2
    assert selected['metal_type'].nunique() == 2, "Must select two different metal types"
    assert set(selected['metal_type']) == {'palladium', 'platinum'}


def test_pm_diversity_two_platinum_pool():
    """When the pool contains ONLY two platinum ETCs (e.g. palladium not on InvestEngine),
    diversity groupby gracefully returns both — one per group is still possible even if
    there is only one group with two members (head(2) on best_per_metal returns 1 row here,
    confirming diversity is enforced and callers should check for fewer than 2 results).
    """
    import pandas as pd
    from etf_utils.config import DATA_CONFIG
    import json

    bcom = json.loads((DATA_CONFIG / 'commodity_index_weights.json').read_text())
    pm_bcom = bcom['precious_metals']

    def overlap(name):
        n = name.lower()
        if 'platinum' in n: return pm_bcom['platinum']
        return pm_bcom['gold']

    def metal_type(name):
        n = name.lower()
        if 'platinum' in n: return 'platinum'
        return 'gold'

    df = pd.DataFrame({
        'name': ['iShares Physical Platinum', 'WisdomTree Physical Platinum'],
        'ter':  [0.20, 0.49],
        'last_year_return_per_risk': [2.26, 2.45],
    })
    df['commodity_overlap_pct'] = df['name'].apply(overlap)
    df['metal_type'] = df['name'].apply(metal_type)
    df = df.sort_values(
        ['commodity_overlap_pct', 'ter', 'last_year_return_per_risk'],
        ascending=[True, True, False],
    )

    best_per_metal = (
        df
        .groupby('metal_type', sort=False)
        .first()
        .reset_index()
        .sort_values(['commodity_overlap_pct', 'ter'], ascending=[True, True])
    )
    selected = best_per_metal.head(2)

    # Only 1 metal type in the pool → 1 row returned, no duplicates
    assert len(selected) == 1
    assert selected.iloc[0]['metal_type'] == 'platinum'
    assert selected.iloc[0]['ter'] == 0.20  # cheapest platinum chosen


def test_pm_within_metal_beta_filters_laggards():
    """Within-metal beta filter (threshold 0.93 vs group median) removes commodity-style
    ETPs that underperform physically-backed peers in the same metal group.

    Gold group median ≈ 53.33%.  XGLD (47.27%) → beta 0.886 → filtered.
    Silver group median ≈ 131.29%. SLVR (119.72%) → beta 0.912 → filtered.
    Platinum: SPLT (105.93%) and PPTX (105.37%) are near-identical → both pass.
    """
    import pandas as pd

    data = {
        'name':   ['iShares Physical Gold ETC', 'Xetra-Gold', 'Xtrackers Physical Gold ETC',
                   'iShares Physical Silver ETC', 'Xtrackers IE Physical Silver ETC',
                   'WisdomTree Silver',
                   'iShares Physical Platinum ETC', 'WisdomTree Physical Platinum'],
        'ticker': ['SGLN', '4GLD', 'XGLD', 'SSLN', 'XSLR', 'SLVR', 'SPLT', 'PPTX'],
        '2025':   [53.33, 57.03, 47.27, 131.29, 144.17, 119.72, 105.93, 105.37],
    }

    def metal_type(name):
        n = name.lower()
        if 'platinum' in n: return 'platinum'
        if 'silver'   in n: return 'silver'
        if 'gold'     in n: return 'gold'
        return 'mixed'

    df = pd.DataFrame(data)
    df['metal_type'] = df['name'].apply(metal_type)

    metal_group_median = df.groupby('metal_type')['2025'].transform('median')
    df['within_metal_beta'] = df['2025'] / metal_group_median
    passing = df[df['within_metal_beta'] >= 0.93]

    # Laggards should be removed
    assert 'XGLD' not in passing['ticker'].values   # beta 0.886
    assert 'SLVR' not in passing['ticker'].values   # beta 0.912
    # Good ETCs should pass
    assert 'SGLN' in passing['ticker'].values
    assert 'SSLN' in passing['ticker'].values
    assert 'SPLT' in passing['ticker'].values
    assert 'PPTX' in passing['ticker'].values


def test_commodity_beta_filter_removes_underperformers():
    """Beta >= 1 filter keeps only ETCs that matched/beat the CMOP 2025 benchmark.

    CMOP benchmark return: 7.33%.
    - COMM (7.64%) → beta 1.04 → kept
    - BCOG (7.57%) → beta 1.03 → kept
    - ENCG (0.00%) → beta 0.00 → removed
    - UC15 (1.58%) → beta 0.22 → removed
    - AIGC (6.76%) → beta 0.92 → removed (just under threshold)
    """
    import pandas as pd

    benchmark_return = 7.33  # CMOP 2025 %

    df = pd.DataFrame({
        'name':  ['Invesco CMOP', 'iShares COMM', 'L&G BCOG', 'L&G ENCG', 'UBS UC15', 'WT AIGC'],
        'ticker': ['CMOP', 'COMM', 'BCOG', 'ENCG', 'UC15', 'AIGC'],
        '2025':  [7.33, 7.64, 7.57, 0.00, 1.58, 6.76],
    })
    df = df[df['2025'].notna()].copy()
    df['beta'] = df['2025'] / benchmark_return
    passing = df[df['beta'] >= 1]

    assert set(passing['ticker']) == {'CMOP', 'COMM', 'BCOG'}
    assert 'ENCG' not in passing['ticker'].values
    assert 'UC15' not in passing['ticker'].values
    assert 'AIGC' not in passing['ticker'].values


def test_commodity_beta_filter_skipped_when_benchmark_zero():
    """Beta filter is skipped gracefully when benchmark return is 0 or negative."""
    import pandas as pd

    df = pd.DataFrame({
        'name':  ['ETC A', 'ETC B'],
        'ticker': ['ETCA', 'ETCB'],
        '2025':  [5.0, -3.0],
    })
    df = df[df['2025'].notna()].copy()

    benchmark_return = 0  # e.g. flat year
    if benchmark_return and benchmark_return > 0:
        df['beta'] = df['2025'] / benchmark_return
        df = df[df['beta'] >= 1]
    else:
        df['beta'] = None  # filter skipped

    # All rows survive because filter was skipped
    assert len(df) == 2
    assert df['beta'].isna().all()


def test_pm_interpolation_with_015_table():
    """interpolate_adjustment_factor works correctly with the ±0.15 PM/commodities table."""
    sr_table = {
        -0.15: 0.6, -0.12: 0.66, -0.09: 0.77, -0.06: 0.85, -0.03: 0.94,
         0:    1.0,  0.03: 1.11,  0.06: 1.19,  0.09: 1.30,  0.12: 1.37, 0.15: 1.48
    }
    # Exact match at 0 → 1.0
    assert interpolate_adjustment_factor(0, sr_table) == 1.0
    # Exact match at boundary
    assert interpolate_adjustment_factor(-0.15, sr_table) == 0.6
    assert interpolate_adjustment_factor(0.15, sr_table) == 1.48
    # Clipping below minimum
    assert interpolate_adjustment_factor(-0.5, sr_table) == 0.6
    # Clipping above maximum
    assert interpolate_adjustment_factor(0.5, sr_table) == 1.48
    # Midpoint between 0 and 0.03: (1.0 + 1.11) / 2 = 1.055
    result = interpolate_adjustment_factor(0.015, sr_table)
    assert abs(result - 1.055) < 1e-6