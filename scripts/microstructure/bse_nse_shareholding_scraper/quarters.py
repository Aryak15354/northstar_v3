#!/usr/bin/env python3
"""Quarter list for the MICRO-002 backfill, matching shareholding_quarterly.parquet's own schema.

`availability_date` uses SEBI LODR Regulation 31(1)(b)'s filing deadline -- 21 days from quarter
end -- as the point-in-time availability estimate, consistent with how the rest of this panel treats
PIT discipline (a filing is not "available" on its as-of date, but on when it was actually filed).
This is a documented assumption, not a measured one: real filing dates vary per company and should
replace this estimate once the raw filing timestamp is parsed out of a fetched response, if present.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

FILING_DEADLINE_DAYS = 21


@dataclass(frozen=True)
class Quarter:
    label: str                    # "Q1-2010" (calendar quarter, matching the canonical schema)
    quarter_end: pd.Timestamp
    availability_date: pd.Timestamp


def quarter_list(start: str = "2010-01-01", end: str = "2022-12-31") -> list[Quarter]:
    ends = pd.date_range(start=start, end=end, freq="QE")
    out = []
    for qe in ends:
        label = f"Q{qe.quarter}-{qe.year}"
        out.append(Quarter(label=label, quarter_end=qe,
                           availability_date=qe + pd.Timedelta(days=FILING_DEADLINE_DAYS)))
    return out


if __name__ == "__main__":
    qs = quarter_list()
    print(f"{len(qs)} quarters, {qs[0].label} .. {qs[-1].label}")
    for q in qs[:3] + qs[-3:]:
        print(f"  {q.label}: quarter_end={q.quarter_end.date()} availability_date={q.availability_date.date()}")
