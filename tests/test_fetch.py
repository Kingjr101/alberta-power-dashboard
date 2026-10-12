import pandas as pd
import pytest

from src.fetch import clean_data


@pytest.fixture
def reports():
    hours = pd.date_range("2025-01-01 07:00", "2026-01-01 07:00", freq="h", inclusive="left")
    prices = [{"begin_datetime_utc": str(t), "pool_price": "25.50"} for t in hours]
    loads = [{"begin_datetime_utc": str(t), "alberta_internal_load": "10000"} for t in hours]
    return prices, loads


def test_complete_year_and_identical_duplicate(reports):
    prices, loads = reports
    result = clean_data(prices + prices[:1], loads, 2025, 2025)
    assert len(result) == 8760
    assert result.timestamp_utc.is_unique
    repeated = result.timestamp_alberta.str.startswith("2025-11-02T01:00")
    assert repeated.sum() == 2


def test_missing_load_rejected(reports):
    prices, loads = reports
    with pytest.raises(ValueError, match="Missing/nonfinite"):
        clean_data(prices, loads[:-1], 2025, 2025)


def test_missing_hour_rejected(reports):
    prices, loads = reports
    with pytest.raises(ValueError, match="Missing or unexpected"):
        clean_data(prices[:-1], loads[:-1], 2025, 2025)


def test_conflicting_duplicate_rejected(reports):
    prices, loads = reports
    with pytest.raises(ValueError, match="Conflicting"):
        clean_data(prices + [{**prices[0], "pool_price": "30"}], loads, 2025, 2025)
