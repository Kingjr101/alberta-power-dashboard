"""Download complete calendar years from AESO; fail rather than hide missing hours."""
import argparse
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://apimgw.aeso.ca/public/"
REPORTS = {
    "price": ("poolprice-api/v1.1/price/poolPrice", "Pool Price Report"),
    "load": ("actualforecast-api/v1/load/albertaInternalLoad", "Actual Forecast Report"),
}


def clean_data(prices, loads, start_year, end_year):
    """One-to-one UTC join, preserving the repeated fall DST hour."""
    frames = []
    for rows, source, target in [(prices, "pool_price", "pool_price_cad_mwh"),
                                  (loads, "alberta_internal_load", "ail_mw")]:
        frame = pd.DataFrame(rows)[["begin_datetime_utc", source]].copy()
        frame.columns = ["timestamp_utc", target]
        frame["timestamp_utc"] = pd.to_datetime(frame.timestamp_utc, utc=True)
        frame[target] = pd.to_numeric(frame[target], errors="raise")
        frame = frame.drop_duplicates()
        if frame.timestamp_utc.duplicated().any():
            raise ValueError("Conflicting values for a UTC hour")
        frames.append(frame)
    data = frames[0].merge(frames[1], on="timestamp_utc", how="outer", validate="one_to_one")
    start = pd.Timestamp(f"{start_year}-01-01", tz="America/Edmonton").tz_convert("UTC")
    stop = pd.Timestamp(f"{end_year + 1}-01-01", tz="America/Edmonton").tz_convert("UTC")
    data = data.loc[(data.timestamp_utc >= start) & (data.timestamp_utc < stop)].sort_values("timestamp_utc").reset_index(drop=True)
    expected = pd.date_range(start, stop, freq="h", inclusive="left")
    if not pd.DatetimeIndex(data.timestamp_utc).equals(expected):
        raise ValueError("Missing or unexpected hourly timestamps; existing snapshot not replaced")
    if not np.isfinite(data[["pool_price_cad_mwh", "ail_mw"]]).all().all() or (data.ail_mw <= 0).any():
        raise ValueError("Missing/nonfinite values or nonpositive actual load")
    data.insert(1, "timestamp_alberta", data.timestamp_utc.dt.tz_convert("America/Edmonton").map(lambda t: t.isoformat()))
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=date.today().year - 2)
    parser.add_argument("--end-year", type=int, default=date.today().year - 1)
    args = parser.parse_args()
    if not 2000 <= args.start_year <= args.end_year < date.today().year:
        parser.error("Choose complete calendar years from 2000 onward")
    load_dotenv(ROOT / ".env")
    key = os.environ.get("AESO_API_KEY")
    if not key:
        parser.error("Set AESO_API_KEY in .env or your environment")
    session = requests.Session()
    session.headers["API-KEY"] = key
    session.mount("https://", HTTPAdapter(max_retries=Retry(total=4, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
    records = {"price": [], "load": []}
    for month in pd.date_range(f"{args.start_year}-01-01", f"{args.end_year}-12-01", freq="MS"):
        end = month + pd.offsets.MonthEnd(0)
        for name, (endpoint, report) in REPORTS.items():
            response = session.get(BASE + endpoint, params={"startDate": month.strftime("%Y-%m-%d"), "endDate": end.strftime("%Y-%m-%d")}, timeout=90)
            response.raise_for_status()
            payload = response.json()
            if str(payload.get("responseCode")) != "200":
                raise ValueError("AESO returned an unsuccessful report")
            records[name].extend(payload["return"][report])
        print(f"Downloaded {month:%Y-%m}", flush=True)
    data = clean_data(records["price"], records["load"], args.start_year, args.end_year)
    directory = ROOT / "data"
    directory.mkdir(exist_ok=True)
    output = directory / "hourly.csv"
    temporary = output.with_suffix(".tmp")
    data.to_csv(temporary, index=False, float_format="%.2f")
    temporary.replace(output)
    metadata = {"source": "AESO Pool Price Report and Actual Forecast Report (actual AIL)",
                "endpoints": [BASE + item[0] for item in REPORTS.values()],
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "start_date": f"{args.start_year}-01-01", "end_date": f"{args.end_year}-12-31",
                "rows": len(data), "missing_hours": 0,
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
    (directory / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(data):,} validated hours to {output}")


if __name__ == "__main__":
    main()
