from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.analysis import filter_dates, insights, patterns, prepare, relationship, spikes, summary
from src.analysis import daily_market, demand_bands, monthly_spikes, price_duration
from src.analysis import price_story


@pytest.fixture
def sample():
    return prepare(pd.DataFrame({"timestamp_utc": pd.date_range("2025-01-01 07:00", periods=4, freq="h", tz="UTC"),
                                 "pool_price_cad_mwh": [0., 250., 500., 750.], "ail_mw": [100., 200., 300., 400.]}))


def test_summary_and_strict_spike_boundary(sample):
    assert summary(sample) == {"mean": 375., "max": 750., "min": 0., "hours": 4, "spike_hours": 1, "spike_percent": 25.}
    assert spikes(sample).pool_price_cad_mwh.tolist() == [750.]


def test_linear_relationship_and_constant_load(sample):
    correlation, line = relationship(sample)
    assert correlation == pytest.approx(1)
    assert line.pool_price_cad_mwh.tolist() == pytest.approx([0., 750.])
    assert np.isnan(relationship(sample.assign(ail_mw=100))[0])


def test_local_dates_and_dst():
    frame = prepare(pd.DataFrame({"timestamp_utc": ["2025-11-02T07:00Z", "2025-11-02T08:00Z", "2025-11-03T06:00Z"], "pool_price_cad_mwh": [10., 30., 80.], "ail_mw": [1., 2., 3.]}))
    assert frame.hour.tolist() == [1, 1, 23]
    assert len(filter_dates(frame, date(2025, 11, 2), date(2025, 11, 2))) == 3
    assert patterns(frame)[0].loc[1] == 20


def test_patterns_missing_months_and_no_mutation(sample):
    before = sample.copy(deep=True)
    hourly, monthly, heatmap = patterns(sample)
    assert monthly.loc[1] == 375
    assert np.isnan(monthly.loc[2])
    assert heatmap.shape == (24, 12)
    assert len(insights(sample)) == 4
    pd.testing.assert_frame_equal(sample, before)


def test_empty_data(sample):
    empty = sample.iloc[:0]
    assert summary(empty)["spike_percent"] == 0
    assert insights(empty) == []
    assert np.isnan(relationship(empty)[0])


def test_price_story_threshold_and_empty_comparison(sample):
    result = price_story(sample)
    assert result['mean'] == 375
    assert result['median'] == 375
    assert result['without_spikes'] == 250  # Exactly $500 is not a spike.
    assert result['ordinary_hours'] == 3
    assert result['spike_percent'] == 25
    assert np.isnan(price_story(sample.iloc[3:])['without_spikes'])
    assert price_story(sample.iloc[:3])['spike_hours'] == 0


def test_demand_bands_preserve_ties_and_denominators(sample):
    repeated = pd.concat([sample, sample], ignore_index=True)
    bands = demand_bands(repeated)
    assert bands.hours.sum() == len(repeated)
    assert (bands.hours % 2 == 0).all()
    weighted_spikes = (bands.spike_percent * bands.hours / 100).sum()
    assert weighted_spikes == 2
    constant = demand_bands(sample.assign(ail_mw=100))
    assert len(constant) == 1
    assert constant.iloc[0].spike_percent == 25
    assert demand_bands(sample.iloc[:0]).empty


def test_monthly_spikes_use_observed_hours(sample):
    result = monthly_spikes(sample)
    assert result.iloc[0].hours == 4
    assert result.iloc[0].spikes == 1
    assert result.iloc[0].percent == 25


def test_daily_averages_and_price_duration(sample):
    daily = daily_market(sample)
    assert daily.iloc[0]['mean'] == 375
    assert daily.iloc[0]['rolling'] == 375
    assert daily.iloc[0]['low'] == 0
    assert daily.iloc[0]['high'] == 750
    duration = price_duration(sample)
    assert duration.pool_price_cad_mwh.tolist() == [750, 500, 250, 0]
    assert duration.share.tolist() == [25, 50, 75, 100]
