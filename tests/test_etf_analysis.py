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
        mock_response.json.return_value = [{'symbol': 'ETF1', 'available': True}]
        mock_get.return_value = mock_response

        # Import the actual function
        from curation import check_etf_availability

        # Test availability check
        result = check_etf_availability('ETF1')
        self.assertTrue(result)
        mock_get.assert_called_once()
        
if __name__ == '__main__':
    unittest.main()