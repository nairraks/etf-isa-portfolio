"""Tests for etf_utils.data_io — CSV/JSON file helpers."""

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from etf_utils.data_io import (
    get_asset_class_from_filename,
    get_region_category_from_filename,
    load_config,
    load_intermediate,
    load_output,
    load_raw_etf_data,
    save_intermediate,
    save_output,
)


# --- Filename parsing ---


class TestFilenameParsing:
    def test_get_region_category_equity(self):
        assert get_region_category_from_filename("justetf_class-equity_developed_emea.csv") == "developed_emea"

    def test_get_region_category_bonds(self):
        assert get_region_category_from_filename("justetf_class-bonds_emerging_apacandemea.csv") == "emerging_apacandemea"

    def test_get_asset_class_equity(self):
        assert get_asset_class_from_filename("justetf_class-equity_developed_emea.csv") == "equity"

    def test_get_asset_class_bonds(self):
        assert get_asset_class_from_filename("justetf_class-bonds_developed_americasanduk.csv") == "bonds"

    def test_get_region_category_short_name(self):
        """Filenames without enough parts return the stem."""
        result = get_region_category_from_filename("justetf_unknown.csv")
        assert result == "justetf_unknown"


# --- Round-trip save/load ---


class TestSaveLoad:
    @pytest.fixture(autouse=True)
    def isolate_db(self, tmp_path, monkeypatch):
        """Redirect DB_PATH to a throw-away file so tests never touch the real DB."""
        import etf_utils.database as db_mod

        monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / "test_data_io.db")
        monkeypatch.setattr(db_mod, "_db_initialized", False)

    def test_save_and_load_intermediate(self, tmp_data_dir):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        with patch("etf_utils.data_io.DATA_INTERMEDIATE", tmp_data_dir / "intermediate"):
            path = save_intermediate(df, "test.csv")
            assert path.exists()
            loaded = load_intermediate("test.csv")
            pd.testing.assert_frame_equal(df, loaded)

    def test_save_and_load_output(self, tmp_data_dir):
        df = pd.DataFrame({"ticker": ["VEVE"], "weight": [50.0]})
        with patch("etf_utils.data_io.DATA_OUTPUT", tmp_data_dir / "output"):
            path = save_output(df, "portfolio.csv")
            assert path.exists()
            loaded = load_output("portfolio.csv")
            pd.testing.assert_frame_equal(df, loaded)

    def test_load_intermediate_missing_file(self, tmp_data_dir):
        with patch("etf_utils.data_io.DATA_INTERMEDIATE", tmp_data_dir / "intermediate"):
            with pytest.raises(FileNotFoundError):
                load_intermediate("nonexistent.csv")

    def test_load_output_missing_file(self, tmp_data_dir):
        with patch("etf_utils.data_io.DATA_OUTPUT", tmp_data_dir / "output"):
            with pytest.raises(FileNotFoundError):
                load_output("nonexistent.csv")


# --- load_raw_etf_data ---


class TestLoadRawData:
    def test_load_raw_etf_data(self, tmp_data_dir):
        raw_dir = tmp_data_dir / "raw"
        df = pd.DataFrame({"ticker": ["VEVE", "IGLT"], "ter": [0.12, 0.07]})
        df.to_csv(raw_dir / "justetf_class-equity_developed_emea.csv", index=False)

        with patch("etf_utils.data_io.DATA_RAW", raw_dir):
            result = load_raw_etf_data()
            assert "justetf_class-equity_developed_emea" in result
            assert len(result["justetf_class-equity_developed_emea"]) == 2

    def test_load_raw_no_files(self, tmp_data_dir):
        with patch("etf_utils.data_io.DATA_RAW", tmp_data_dir / "raw"):
            with pytest.raises(FileNotFoundError):
                load_raw_etf_data()


# --- load_config ---


class TestLoadConfig:
    def test_load_config_json(self, tmp_data_dir):
        config_dir = tmp_data_dir / "config"
        config_data = {"tickers": ["VEVE", "IGLT"]}
        (config_dir / "test_config.json").write_text(json.dumps(config_data))

        with patch("etf_utils.data_io.DATA_CONFIG", config_dir):
            result = load_config("test_config.json")
            assert result == config_data

    def test_load_config_missing(self, tmp_data_dir):
        with patch("etf_utils.data_io.DATA_CONFIG", tmp_data_dir / "config"):
            with pytest.raises(FileNotFoundError):
                load_config("missing.json")
