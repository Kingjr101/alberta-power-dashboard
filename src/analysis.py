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
