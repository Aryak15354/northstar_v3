"""Mapping utilities across stock sectors and macro categories."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


GST_TO_SECTOR_MAP = {
    "Automobile": ["Automobiles", "Auto Components", "Automobile and Auto Components"],
    "Iron and Steel": ["Steel", "Metals & Mining"],
    "Cement": ["Cement", "Construction Materials"],
    "Pharmaceuticals": ["Pharmaceuticals", "Healthcare"],
    "FMCG": ["FMCG", "Consumer Goods", "Fast Moving Consumer Goods"],
    "Textiles": ["Textiles"],
    "Chemicals": ["Chemicals", "Specialty Chemicals"],
    "Electronics": ["Technology Hardware", "Consumer Electronics", "Information Technology"],
    "Construction": ["Construction", "Real Estate", "Infrastructure", "Realty"],
    "Agriculture": ["Agro Chemicals", "Food Processing"],
}


CEA_REGION_TO_STATES = {
    "Northern": ["Delhi", "Haryana", "Punjab", "Rajasthan", "UP", "Uttarakhand"],
    "Western": ["Maharashtra", "Gujarat", "MP", "Goa", "Chhattisgarh"],
    "Southern": ["Tamil Nadu", "Karnataka", "Andhra Pradesh", "Telangana", "Kerala"],
    "Eastern": ["West Bengal", "Odisha", "Bihar", "Jharkhand"],
    "North-Eastern": ["Assam", "Meghalaya", "Tripura", "Manipur", "Nagaland", "Mizoram", "Arunachal Pradesh", "Sikkim"],
}


class SectorMapper:
    """Resolve macro categories relevant for each stock."""

    def __init__(self) -> None:
        self._sector_map_df = self._load_sector_map()

    @staticmethod
    def _normalize_ticker(value: object) -> str:
        s = str(value or "").strip().upper()
        if not s:
            return ""
        if s.endswith(".NS"):
            return s
        if "." in s:
            s = s.split(".", 1)[0]
        return f"{s}.NS"

    def _load_sector_map(self) -> pd.DataFrame:
        rows: list[dict] = []

        sector_map_path = Path("data/processed/sector_mapping.csv")
        if sector_map_path.exists():
            try:
                sm = pd.read_csv(sector_map_path)
                for r in sm.to_dict("records"):
                    rows.append(
                        {
                            "ticker": self._normalize_ticker(r.get("ticker")),
                            "industry": str(r.get("industry", "") or "").strip(),
                            "sector": str(r.get("sector", "") or "").strip(),
                            "state": str(r.get("state", "") or "").strip(),
                        }
                    )
            except Exception:
                pass

        nifty500_path = Path("universe/nifty500.csv")
        if nifty500_path.exists():
            try:
                nf = pd.read_csv(nifty500_path)
                for r in nf.to_dict("records"):
                    rows.append(
                        {
                            "ticker": self._normalize_ticker(r.get("Symbol")),
                            "industry": str(r.get("Industry", "") or "").strip(),
                            "sector": str(r.get("Industry", "") or "").strip(),
                            "state": "",
                        }
                    )
            except Exception:
                pass

        if not rows:
            return pd.DataFrame(columns=["ticker", "industry", "sector", "state"])

        out = pd.DataFrame(rows)
        out = out[out["ticker"] != ""].drop_duplicates(subset=["ticker"], keep="first").reset_index(drop=True)
        return out

    def _lookup_sector(self, nse_ticker: str, metadata_df: pd.DataFrame | None = None) -> str:
        tk = self._normalize_ticker(nse_ticker)
        if metadata_df is not None and not metadata_df.empty and "ticker" in metadata_df.columns:
            m = metadata_df.copy()
            m["ticker"] = m["ticker"].map(self._normalize_ticker)
            row = m[m["ticker"] == tk]
            if not row.empty:
                for c in ["sector", "industry", "Industry", "Sector"]:
                    if c in row.columns:
                        val = str(row.iloc[0].get(c, "") or "").strip()
                        if val:
                            return val
        row = self._sector_map_df[self._sector_map_df["ticker"] == tk]
        if not row.empty:
            sector = str(row.iloc[0].get("sector", "") or "").strip()
            if sector:
                return sector
            industry = str(row.iloc[0].get("industry", "") or "").strip()
            if industry:
                return industry
        return ""

    def _lookup_state(self, nse_ticker: str, metadata_df: pd.DataFrame | None = None) -> str:
        tk = self._normalize_ticker(nse_ticker)
        if metadata_df is not None and not metadata_df.empty and "ticker" in metadata_df.columns:
            m = metadata_df.copy()
            m["ticker"] = m["ticker"].map(self._normalize_ticker)
            row = m[m["ticker"] == tk]
            if not row.empty:
                for c in ["state", "hq_state", "headquarter_state"]:
                    if c in row.columns:
                        val = str(row.iloc[0].get(c, "") or "").strip()
                        if val:
                            return val
        row = self._sector_map_df[self._sector_map_df["ticker"] == tk]
        if not row.empty:
            return str(row.iloc[0].get("state", "") or "").strip()
        return ""

    def get_relevant_gst_categories(self, nse_ticker: str, metadata_df: pd.DataFrame | None = None) -> list[str]:
        """Return GST categories relevant to the ticker sector/industry."""
        sector = self._lookup_sector(nse_ticker, metadata_df=metadata_df).lower()
        if not sector:
            return []
        out: list[str] = []
        for gst_cat, sectors in GST_TO_SECTOR_MAP.items():
            if any(str(s).lower() in sector or sector in str(s).lower() for s in sectors):
                out.append(gst_cat)
        return out

    def get_relevant_cea_regions(self, nse_ticker: str, metadata_df: pd.DataFrame | None = None) -> list[str]:
        """Return CEA regions relevant to ticker geography."""
        state = self._lookup_state(nse_ticker, metadata_df=metadata_df).lower()
        if not state:
            return []
        out: list[str] = []
        for region, states in CEA_REGION_TO_STATES.items():
            if any(state == s.lower() or state in s.lower() for s in states):
                out.append(region)
        return out
