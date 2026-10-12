"""Pure analysis functions; prices are CAD/MWh and actual load is MW."""
import numpy as np
import pandas as pd


def prepare(data):
    result = data.copy()
    result["timestamp_utc"] = pd.to_datetime(result.timestamp_utc, utc=True)
    local = result.timestamp_utc.dt.tz_convert("America/Edmonton")
    result["date"] = local.dt.date
    result["hour"] = local.dt.hour
    result["month"] = local.dt.month
    return result


def filter_dates(data, start, end):
    return data.loc[data.date.between(start, end)].copy()


def summary(data, threshold=500):
    prices = data.pool_price_cad_mwh
    count = int((prices > threshold).sum())
    return {"mean": prices.mean(), "max": prices.max(), "min": prices.min(),
            "hours": len(data), "spike_hours": count,
            "spike_percent": 100 * count / len(data) if len(data) else 0.0}


def relationship(data):
    if len(data) < 2 or data.ail_mw.nunique() < 2 or data.pool_price_cad_mwh.nunique() < 2:
        return float("nan"), pd.DataFrame(columns=["ail_mw", "pool_price_cad_mwh"])
    correlation = data.ail_mw.corr(data.pool_price_cad_mwh)
    slope, intercept = np.polyfit(data.ail_mw, data.pool_price_cad_mwh, 1)
    x = np.array([data.ail_mw.min(), data.ail_mw.max()])
    return float(correlation), pd.DataFrame({"ail_mw": x, "pool_price_cad_mwh": slope * x + intercept})


def patterns(data):
    hourly = data.groupby("hour").pool_price_cad_mwh.mean().reindex(range(24))
    monthly = data.groupby("month").pool_price_cad_mwh.mean().reindex(range(1, 13))
    heatmap = data.pivot_table(index="hour", columns="month", values="pool_price_cad_mwh", aggfunc="mean").reindex(index=range(24), columns=range(1, 13))
    return hourly, monthly, heatmap


def spikes(data, threshold=500):
    return data.loc[data.pool_price_cad_mwh > threshold].sort_values("pool_price_cad_mwh", ascending=False).copy()


def daily_market(data):
    """Daily means and observed hourly range; rolling mean uses up to seven days."""
    daily = data.groupby("date", as_index=False).agg(
        mean=("pool_price_cad_mwh", "mean"), low=("pool_price_cad_mwh", "min"),
        high=("pool_price_cad_mwh", "max"), load=("ail_mw", "mean"))
    daily["rolling"] = daily["mean"].rolling(7, min_periods=1).mean()
    return daily


def demand_bands(data):
    """Up to five quantile bands; ties stay together, so counts can differ."""
    columns = ["band", "load_min", "load_max", "hours", "mean", "median", "spike_percent"]
    if data.empty:
        return pd.DataFrame(columns=columns)
    frame = data.copy()
    frame["band"] = (0 if frame.ail_mw.nunique() == 1 else
                     pd.qcut(frame.ail_mw, 5, labels=False, duplicates="drop"))
    frame["spike"] = frame.pool_price_cad_mwh > 500
    result = frame.groupby("band", as_index=False).agg(
        load_min=("ail_mw", "min"), load_max=("ail_mw", "max"),
        hours=("ail_mw", "size"), mean=("pool_price_cad_mwh", "mean"),
        median=("pool_price_cad_mwh", "median"), spike_percent=("spike", "mean"))
    result["spike_percent"] *= 100
    result["band"] = [f"Band {i + 1}" for i in range(len(result))]
    return result[columns]


def monthly_spikes(data):
    frame = data.assign(period=pd.to_datetime(data.date).dt.to_period("M").astype(str),
                        spike=data.pool_price_cad_mwh > 500)
    result = frame.groupby("period", as_index=False).agg(hours=("spike", "size"), spikes=("spike", "sum"))
    result["percent"] = result.spikes / result.hours * 100
    return result


def price_duration(data):
    """Descending hourly prices with cumulative share of observed hours."""
    result = data[["pool_price_cad_mwh"]].sort_values("pool_price_cad_mwh", ascending=False).reset_index(drop=True)
    result["share"] = np.arange(1, len(result) + 1) / max(len(result), 1) * 100
    return result


def insights(data):
    if data.empty:
        return []
    stats = summary(data)
    hourly, monthly, _ = patterns(data)
    correlation, _ = relationship(data)
    hour = int(hourly.idxmax())
    month = int(monthly.idxmax())
    import calendar
    return [f"The average pool price was ${stats['mean']:,.2f}/MWh, ranging from ${stats['min']:,.2f} to ${stats['max']:,.2f}/MWh.",
            f"The most expensive hour began at {hour:02d}:00 Alberta time, averaging ${hourly.loc[hour]:,.2f}/MWh. {calendar.month_name[month]} had the highest monthly average (${monthly.loc[month]:,.2f}/MWh).",
            f"Prices exceeded $500/MWh in {stats['spike_hours']:,} of {stats['hours']:,} hours ({stats['spike_percent']:.2f}%).",
            (f"Hourly price and load had a Pearson correlation of {correlation:.3f}. This describes association, not causation." if np.isfinite(correlation) else "Correlation needs at least two varying price and load observations.")]
