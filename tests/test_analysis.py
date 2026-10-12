from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.analysis import filter_dates, insights, patterns, prepare, relationship, spikes, summary


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
