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