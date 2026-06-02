"""
ShockKnowledgeBase — static mappings from shock types to the exact 21
Nifty 500 sectors used by Northstar V3.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.intelligence.news_brain.news_signal_state import NIFTY500_SECTORS


def _sector(
    score: float,
    estimated_move_pct: float,
    time_horizon_days: int,
    at_risk: list[str] | None = None,
    beneficiaries: list[str] | None = None,
    rationale: str = "",
) -> dict[str, Any]:
    return {
        "score": float(score),
        "estimated_move_pct": float(estimated_move_pct),
        "time_horizon_days": int(time_horizon_days),
        "at_risk": list(at_risk or []),
        "beneficiaries": list(beneficiaries or []),
        "rationale": str(rationale or "Neutral blended sector impact"),
    }


def _neutral_sector_template() -> dict[str, Any]:
    return {
        sector: _sector(
            0.0,
            0.0,
            5,
            rationale="Neutral baseline because the shock has limited first-order transmission to this sector",
        )
        for sector in NIFTY500_SECTORS
    }


def _complete_shock(
    market_level_impact: float,
    inr_change_pct: float,
    time_horizon_days: int,
    sector_overrides: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    base = _neutral_sector_template()
    for sector, override in sector_overrides.items():
        payload = dict(base.get(sector, {}))
        payload.update(override)
        payload["time_horizon_days"] = int(payload.get("time_horizon_days", time_horizon_days) or time_horizon_days)
        payload["at_risk"] = list(payload.get("at_risk", []) or [])
        payload["beneficiaries"] = list(payload.get("beneficiaries", []) or [])
        payload["rationale"] = str(payload.get("rationale", "") or "Neutral blended sector impact")
        base[sector] = payload

    missing = [sector for sector in NIFTY500_SECTORS if sector not in base]
    if missing:
        raise ValueError(f"Shock definition missing sectors: {missing}")

    return {
        "market_level_impact": float(market_level_impact),
        "inr_change_pct": float(inr_change_pct),
        "time_horizon_days": int(time_horizon_days),
        "sector_impacts": base,
    }


def _scale_shock(
    shock: dict[str, Any],
    score_factor: float,
    move_factor: float,
    market_level_impact: float | None = None,
    inr_change_pct: float | None = None,
    time_horizon_days: int | None = None,
    sector_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    derived = deepcopy(shock)
    derived["market_level_impact"] = float(
        market_level_impact if market_level_impact is not None else shock["market_level_impact"] * score_factor
    )
    derived["inr_change_pct"] = float(
        inr_change_pct if inr_change_pct is not None else shock.get("inr_change_pct", 0.0)
    )
    derived["time_horizon_days"] = int(
        time_horizon_days if time_horizon_days is not None else shock.get("time_horizon_days", 5)
    )
    for sector, payload in derived["sector_impacts"].items():
        payload["score"] = float(max(-1.0, min(1.0, payload.get("score", 0.0) * score_factor)))
        payload["estimated_move_pct"] = float(payload.get("estimated_move_pct", 0.0) * move_factor)
        payload["time_horizon_days"] = int(payload.get("time_horizon_days", derived["time_horizon_days"]) or derived["time_horizon_days"])
    for sector, override in dict(sector_overrides or {}).items():
        derived["sector_impacts"][sector].update(override)
        derived["sector_impacts"][sector]["at_risk"] = list(derived["sector_impacts"][sector].get("at_risk", []) or [])
        derived["sector_impacts"][sector]["beneficiaries"] = list(derived["sector_impacts"][sector].get("beneficiaries", []) or [])
    return derived


SHOCK_KNOWLEDGE_BASE: dict[str, dict[str, Any]] = {
    "oil_price_spike": _complete_shock(
        market_level_impact=-0.025,
        inr_change_pct=-1.5,
        time_horizon_days=5,
        sector_overrides={
            "Oil Gas & Consumable Fuels": _sector(-0.40, -3.5, 3, ["BPCL", "HPCL", "IOC", "MRPL", "CHENNPETRO"], ["ONGC", "OIL"], "OMC under-recovery exceeds upstream gain at index level"),
            "Services": _sector(-0.85, -6.0, 2, ["INDIGO", "BLUEDART", "DELHIVERY", "CONCOR"], [], "Aviation ATF and logistics diesel costs rise immediately"),
            "Chemicals": _sector(-0.70, -5.0, 5, ["DEEPAKNTR", "AARTIIND", "PIDILITIND", "CHAMBLFERT", "DEEPAKFERT"], [], "Naphtha and solvent feedstock costs rise faster than pricing"),
            "Automobile and Auto Components": _sector(-0.45, -3.5, 7, ["APOLLOTYRE", "CEATLTD", "MRF", "BALKRISIND", "HEROMOTOCO"], ["ATHERENERG"], "Tyre feedstock and fuel anxiety pressure volume and margins"),
            "Construction Materials": _sector(-0.35, -2.5, 7, ["ULTRACEMCO", "SHREECEM", "ACC", "AMBUJACEM"], [], "Energy-intensive cement costs rise with crude-linked fuels"),
            "Power": _sector(-0.30, -2.0, 5, ["CESC", "TORNTPOWER", "RPOWER"], ["ADANIGREEN", "ADANIENSOL", "ACMESOLAR", "NTPCGREEN"], "Gas-linked plants see cost pressure while renewables gain narrative support"),
            "Textiles": _sector(-0.50, -3.5, 5, ["ALOKINDS", "TRIDENT", "WELSPUNLIV"], ["KPRMILL"], "Polyester and synthetic input costs rise with crude"),
            "Consumer Durables": _sector(-0.25, -1.5, 7, ["ASIANPAINT", "BERGEPAINT", "AKZOINDIA", "DIXON", "AMBER"], [], "Paints and plastics carry crude-linked input exposure"),
            "Capital Goods": _sector(-0.20, -1.5, 7, ["BHEL", "CGPOWER", "CUMMINSIND"], ["BEL", "BDL", "DATAPATTNS"], "Manufacturing costs rise but defence names cushion the sector"),
            "Construction": _sector(-0.30, -2.0, 7, ["LT", "KPIL", "KEC", "NCC", "RVNL"], [], "Bitumen, diesel, and polymer inputs all reprice"),
            "Fast Moving Consumer Goods": _sector(-0.15, -1.0, 10, ["HINDUNILVR", "ITC", "BRITANNIA"], [], "Packaging and logistics costs rise but demand is defensive"),
            "Financial Services": _sector(-0.20, -1.5, 3, ["BAJFINANCE", "SHRIRAMFIN", "LICHSGFIN", "PNBHOUSING"], [], "Oil shock feeds bond yields and rate-hike expectations"),
            "Information Technology": _sector(+0.20, +1.5, 2, [], ["INFY", "TCS", "HCLTECH", "WIPRO", "LTIM", "PERSISTENT"], "USD revenue benefits from INR weakness"),
            "Healthcare": _sector(+0.05, +0.3, 3, ["SUNPHARMA", "CIPLA"], ["DIVISLAB", "DRREDDY"], "Defensive demand offsets modest API import pressure"),
            "Metals & Mining": _sector(-0.25, -1.5, 5, ["HINDALCO", "TATASTEEL", "JSWSTEEL", "SAIL"], ["NMDC", "COALINDIA"], "Smelting energy costs dominate export currency tailwind"),
            "Realty": _sector(-0.20, -1.5, 7, ["DLF", "GODREJPROP", "LODHA"], [], "Construction costs rise while demand sentiment softens"),
            "Telecommunication": _sector(-0.10, -0.5, 5, ["IDEA"], [], "Tower backup diesel costs rise but revenue linkage is limited"),
            "Consumer Services": _sector(-0.30, -2.0, 5, ["JUBLFOOD", "DEVYANI", "SWIGGY", "ZOMATO"], [], "Delivery costs and discretionary spending both weaken"),
            "Media Entertainment & Publication": _sector(-0.15, -1.0, 7, ["PVRINOX", "ZEEL"], [], "Ad demand and multiplex traffic soften in inflationary conditions"),
            "Diversified": _sector(-0.20, -1.5, 5, ["GODREJIND"], ["3MINDIA"], "Blended exposure skews mildly negative in an oil shock"),
            "Forest Materials": _sector(-0.15, -1.0, 7, ["ABREL"], [], "Pulp processing energy costs rise"),
        },
    ),
    "oil_supply_disruption": _complete_shock(
        market_level_impact=-0.040,
        inr_change_pct=-2.0,
        time_horizon_days=7,
        sector_overrides={
            "Oil Gas & Consumable Fuels": _sector(-0.55, -4.5, 3, ["BPCL", "HPCL", "IOC", "MRPL", "CHENNPETRO"], ["ONGC", "OIL"], "A supply route shock magnifies OMC under-recovery and INR pain"),
            "Services": _sector(-0.85, -6.5, 2, ["INDIGO", "BLUEDART", "DELHIVERY", "CONCOR"], [], "Aviation and logistics bear the most direct fuel shock"),
            "Chemicals": _sector(-0.80, -5.5, 5, ["DEEPAKNTR", "AARTIIND", "PIDILITIND", "CHAMBLFERT"], [], "Feedstock disruptions hit margin pass-through and working capital"),
            "Automobile and Auto Components": _sector(-0.55, -4.0, 6, ["HEROMOTOCO", "BAJAJ-AUTO", "APOLLOTYRE", "MRF"], ["ATHERENERG"], "Fuel-sensitive demand and tyre inputs both worsen"),
            "Construction Materials": _sector(-0.45, -3.0, 7, ["ULTRACEMCO", "SHREECEM", "ACC", "AMBUJACEM"], [], "Energy-intensive materials face severe fuel inflation"),
            "Power": _sector(-0.40, -2.5, 5, ["CESC", "TORNTPOWER", "RPOWER"], ["ADANIGREEN", "NTPCGREEN"], "Gas import dependence hurts while renewables gain substitution premium"),
            "Textiles": _sector(-0.55, -4.0, 5, ["ALOKINDS", "TRIDENT", "WELSPUNLIV"], ["KPRMILL"], "Synthetic fibre chains feel both crude and freight disruption"),
            "Consumer Durables": _sector(-0.35, -2.0, 6, ["ASIANPAINT", "BERGEPAINT", "DIXON", "AMBER"], [], "Paint and polymer costs jump faster than channel repricing"),
            "Capital Goods": _sector(-0.25, -1.5, 7, ["BHEL", "CGPOWER", "CUMMINSIND"], ["BEL", "BDL", "DATAPATTNS"], "Manufacturing cost pressure partly offset by defence spending"),
            "Construction": _sector(-0.40, -2.5, 7, ["LT", "KPIL", "KEC", "NCC", "RVNL"], [], "Bitumen and diesel shocks squeeze project economics"),
            "Fast Moving Consumer Goods": _sector(-0.20, -1.2, 9, ["HINDUNILVR", "ITC", "BRITANNIA"], [], "Packaging and freight headwinds matter more in a persistent disruption"),
            "Financial Services": _sector(-0.30, -2.0, 3, ["BAJFINANCE", "SHRIRAMFIN", "LICHSGFIN"], [], "Rate and risk-off repricing hit lenders and NBFCs"),
            "Information Technology": _sector(+0.25, +1.8, 2, [], ["INFY", "TCS", "HCLTECH", "WIPRO"], "INR weakness and defensive offshore revenue help"),
            "Healthcare": _sector(+0.10, +0.8, 3, ["SUNPHARMA"], ["DIVISLAB", "DRREDDY", "CIPLA"], "Defensive rotation outweighs moderate API import pressure"),
            "Metals & Mining": _sector(-0.30, -2.0, 5, ["HINDALCO", "TATASTEEL", "JSWSTEEL"], ["COALINDIA"], "Energy cost pressure offsets export tailwinds"),
            "Realty": _sector(-0.30, -2.0, 7, ["DLF", "GODREJPROP", "LODHA"], [], "Inflation fear and build-cost pressure hurt bookings"),
            "Telecommunication": _sector(-0.15, -1.0, 5, ["IDEA"], [], "Energy and import costs rise but impact is secondary"),
            "Consumer Services": _sector(-0.40, -2.5, 5, ["JUBLFOOD", "DEVYANI", "SWIGGY", "ZOMATO"], [], "Fuel and discretionary stress combine"),
            "Media Entertainment & Publication": _sector(-0.20, -1.2, 6, ["PVRINOX"], [], "Ad budgets and discretionary outings retrench"),
            "Diversified": _sector(-0.25, -1.5, 5, ["GODREJIND"], ["3MINDIA"], "Mixed businesses average out to a moderate negative shock"),
            "Forest Materials": _sector(-0.20, -1.2, 7, ["ABREL"], [], "Energy-intensive processing costs rise"),
        },
    ),
    "rate_hike_rbi": _complete_shock(
        market_level_impact=-0.015,
        inr_change_pct=+0.8,
        time_horizon_days=3,
        sector_overrides={
            "Realty": _sector(-0.85, -5.5, 3, ["DLF", "GODREJPROP", "LODHA", "BRIGADE", "OBEROIRLTY", "PRESTIGE", "SIGNATURE", "SOBHA"], [], "Mortgage affordability is hit immediately by repo hikes"),
            "Financial Services": _sector(-0.40, -3.0, 3, ["BAJFINANCE", "SHRIRAMFIN", "AAVAS", "APTUS", "LICHSGFIN", "PNBHOUSING", "BAJAJHFL"], ["BANKBARODA", "BANKINDIA", "SBI", "AXISBANK"], "NBFC funding costs rise faster than asset repricing"),
            "Consumer Durables": _sector(-0.55, -3.5, 5, ["TITAN", "HAVELLS", "VOLTAS", "CROMPTON", "BLUESTARCO", "DIXON"], [], "EMI-heavy purchases reprice lower on higher interest rates"),
            "Automobile and Auto Components": _sector(-0.50, -3.5, 5, ["TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO", "HYUNDAI"], [], "Auto finance costs rise and demand defers"),
            "Construction": _sector(-0.55, -3.5, 5, ["LT", "KPIL", "NCC", "RVNL", "NBCC", "IRB"], [], "Project IRR falls as funding costs rise"),
            "Capital Goods": _sector(-0.40, -2.5, 7, ["BHEL", "CGPOWER", "ABB", "SIEMENS"], [], "Capex decision hurdle rates move higher"),
            "Power": _sector(-0.35, -2.0, 5, ["ADANIPOWER", "TATAPOWER", "JPPOWER", "RELINFRA"], [], "High leverage and regulated returns become less attractive"),
            "Telecommunication": _sector(-0.30, -2.0, 3, ["IDEA", "BHARTIARTL"], [], "Debt-heavy telecom balance sheets feel higher rates quickly"),
            "Information Technology": _sector(0.0, 0.0, 3, [], [], "USD revenue base limits direct sensitivity to domestic rates"),
            "Healthcare": _sector(+0.10, +0.5, 3, [], ["DIVISLAB", "SUNPHARMA", "CIPLA"], "Defensive rotation modestly benefits pharma"),
            "Fast Moving Consumer Goods": _sector(+0.05, +0.3, 4, [], ["HINDUNILVR", "ITC"], "Defensive consumption attracts relative flows"),
            "Metals & Mining": _sector(-0.30, -2.0, 5, ["TATASTEEL", "JSWSTEEL", "SAIL", "HINDALCO"], [], "Construction-linked demand slows with tighter rates"),
            "Chemicals": _sector(-0.25, -1.5, 5, ["DEEPAKNTR", "AARTIIND"], [], "Working-capital-heavy businesses get squeezed"),
            "Consumer Services": _sector(-0.35, -2.0, 4, ["INDHOTEL", "EIHOTEL", "DMART"], [], "Discretionary spending cools under tighter policy"),
            "Services": _sector(-0.25, -1.5, 4, ["ADANIPORTS", "IRCTC"], [], "Infrastructure and logistics funding costs rise"),
            "Textiles": _sector(-0.30, -2.0, 5, ["ALOKINDS", "WELSPUNLIV"], [], "Export finance and working capital become costlier"),
            "Construction Materials": _sector(-0.40, -2.5, 5, ["ULTRACEMCO", "SHREECEM", "ACC", "AMBUJACEM"], [], "Real estate and infra demand soften"),
            "Media Entertainment & Publication": _sector(-0.20, -1.0, 4, ["PVRINOX"], [], "Discretionary leisure demand slows"),
            "Diversified": _sector(-0.25, -1.5, 5, [], [], "Blended exposure skews negative in a domestic rate shock"),
            "Forest Materials": _sector(-0.15, -1.0, 5, ["ABREL"], [], "Debt carrying costs rise for paper and forestry businesses"),
        },
    ),
    "inr_depreciation": _complete_shock(
        market_level_impact=-0.010,
        inr_change_pct=-1.0,
        time_horizon_days=3,
        sector_overrides={
            "Information Technology": _sector(+0.80, +5.0, 1, [], ["INFY", "TCS", "HCLTECH", "WIPRO", "LTIM", "MPHASIS", "PERSISTENT", "COFORGE", "KPITTECH"], "USD revenue gets an immediate translation tailwind"),
            "Healthcare": _sector(+0.45, +3.0, 3, ["SUNPHARMA", "CIPLA"], ["DRREDDY", "DIVISLAB", "AUROPHARMA", "LUPIN"], "Export-heavy pharma benefits despite some API imports"),
            "Textiles": _sector(+0.50, +3.5, 4, [], ["KPRMILL", "PAGEIND", "TRIDENT", "WELSPUNLIV"], "Export competitiveness improves directly"),
            "Services": _sector(-0.60, -4.0, 2, ["INDIGO"], ["GESHIP"], "Aviation leases and fuel are USD-linked while shipping earns in dollars"),
            "Oil Gas & Consumable Fuels": _sector(-0.55, -3.5, 3, ["BPCL", "HPCL", "IOC"], ["ONGC", "OIL"], "Imported crude costs more in rupee terms"),
            "Metals & Mining": _sector(+0.25, +1.5, 4, [], ["TATASTEEL", "HINDALCO", "JSWSTEEL"], "Exporters get a partial FX hedge"),
            "Chemicals": _sector(-0.35, -2.0, 5, ["DEEPAKNTR", "AARTIIND", "PIDILITIND"], [], "Imported feedstock costs rise"),
            "Capital Goods": _sector(-0.30, -2.0, 5, ["ABB", "CUMMINSIND", "BOSCHLTD"], [], "Imported equipment and components reprice higher"),
            "Financial Services": _sector(-0.25, -1.5, 4, [], [], "FX weakness often arrives with FII outflow and valuation pressure"),
            "Consumer Durables": _sector(-0.30, -2.0, 4, ["DIXON", "AMBER"], [], "Electronics import content increases landed cost"),
            "Fast Moving Consumer Goods": _sector(-0.10, -0.5, 5, [], [], "Packaging and ingredient imports rise modestly"),
            "Realty": _sector(-0.10, -0.5, 5, [], [], "Mostly domestic revenues limit direct sensitivity"),
            "Construction Materials": _sector(-0.15, -1.0, 5, [], [], "Imported coal and coke costs rise"),
            "Power": _sector(-0.20, -1.5, 5, [], [], "Imported thermal fuel becomes costlier"),
            "Automobile and Auto Components": _sector(-0.25, -1.5, 4, ["BOSCHLTD"], [], "Imported components and kits reprice"),
            "Telecommunication": _sector(-0.15, -1.0, 4, [], [], "Network equipment imports get costlier"),
            "Construction": _sector(-0.15, -1.0, 5, [], [], "Imported machinery and project inputs rise"),
            "Consumer Services": _sector(-0.10, -0.5, 5, [], [], "Some imported food and fuel costs rise"),
            "Media Entertainment & Publication": _sector(0.0, 0.0, 5, [], [], "Domestic revenue base offsets limited FX exposure"),
            "Diversified": _sector(-0.10, -0.5, 5, [], [], "Mixed exposures average mildly negative"),
            "Forest Materials": _sector(0.0, 0.0, 5, [], [], "Domestic forest product demand dominates"),
        },
    ),
    "fii_outflow": _complete_shock(
        market_level_impact=-0.020,
        inr_change_pct=-1.0,
        time_horizon_days=5,
        sector_overrides={
            "Financial Services": _sector(-0.70, -5.0, 3, ["HDFC", "ICICIBANK", "KOTAKBANK", "AXISBANK", "BAJFINANCE", "SBILIFE"], [], "FIIs are structurally overweight financials"),
            "Information Technology": _sector(-0.65, -4.5, 3, ["TCS", "INFY", "HCLTECH", "WIPRO"], [], "High-ownership large-cap IT is sold aggressively during risk-off"),
            "Metals & Mining": _sector(-0.55, -4.0, 4, ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL"], [], "Cyclicals unwind in global risk aversion"),
            "Automobile and Auto Components": _sector(-0.50, -3.5, 4, ["TATAMOTORS", "M&M", "BAJAJ-AUTO"], [], "Cyclical FII favorites are sold in macro derisking"),
            "Consumer Durables": _sector(-0.45, -3.0, 4, ["TITAN", "HAVELLS"], [], "Premium consumer names de-rate quickly"),
            "Realty": _sector(-0.40, -3.0, 4, ["DLF", "GODREJPROP", "LODHA"], [], "Rate-sensitive growth valuations compress"),
            "Power": _sector(-0.35, -2.5, 5, ["ADANIPOWER", "TATAPOWER"], [], "Capital-intensive utilities de-rate in risk-off"),
            "Capital Goods": _sector(-0.40, -3.0, 5, ["LT", "ABB", "SIEMENS"], [], "Capex cycle exposures get sold with foreign flows"),
            "Healthcare": _sector(-0.15, -1.0, 4, [], ["DIVISLAB", "SUNPHARMA"], "Defensives hold up better than the market"),
            "Fast Moving Consumer Goods": _sector(-0.10, -0.5, 4, [], ["HINDUNILVR", "ITC"], "The sector is comparatively defensive in FII-driven selloffs"),
            "Oil Gas & Consumable Fuels": _sector(-0.30, -2.0, 4, ["RELIANCE"], [], "Large benchmark energy exposures still see foreign selling"),
            "Chemicals": _sector(-0.35, -2.5, 4, [], [], "Mid-cap chemical ownership amplifies derating"),
            "Construction": _sector(-0.30, -2.0, 5, [], [], "Infrastructure cyclicals get sold when foreign flows reverse"),
            "Construction Materials": _sector(-0.35, -2.5, 5, [], [], "Real estate-linked materials de-rate with foreign risk appetite"),
            "Telecommunication": _sector(-0.25, -1.5, 4, ["BHARTIARTL"], [], "Large foreign ownership and debt both matter"),
            "Services": _sector(-0.40, -3.0, 4, ["INDIGO", "ADANIPORTS"], [], "Cyclical transport and logistics are sold"),
            "Consumer Services": _sector(-0.35, -2.5, 4, ["DMART", "IRCTC"], [], "High-PE domestic growth names de-rate"),
            "Textiles": _sector(-0.25, -1.5, 4, [], [], "Smaller foreign ownership keeps the move milder"),
            "Media Entertainment & Publication": _sector(-0.20, -1.5, 4, [], [], "Small-cap media sells off on liquidity withdrawal"),
            "Diversified": _sector(-0.25, -1.5, 4, [], [], "Blended ownership still skews negative"),
            "Forest Materials": _sector(-0.15, -1.0, 4, ["ABREL"], [], "Liquidity-driven small-cap derating"),
        },
    ),
    "geopolitical_conflict": _complete_shock(
        market_level_impact=-0.035,
        inr_change_pct=-2.0,
        time_horizon_days=7,
        sector_overrides={
            "Services": _sector(-0.90, -7.0, 2, ["INDIGO", "GESHIP", "BLUEDART"], [], "Flight routes and shipping lanes face direct disruption"),
            "Oil Gas & Consumable Fuels": _sector(-0.50, -4.0, 3, ["BPCL", "HPCL", "IOC"], ["ONGC", "OIL"], "Conflict usually embeds crude supply risk"),
            "Chemicals": _sector(-0.65, -4.5, 4, ["DEEPAKNTR", "AARTIIND"], [], "Feedstock supply chains become unstable"),
            "Capital Goods": _sector(+0.40, +3.0, 5, [], ["BEL", "BDL", "DATAPATTNS", "HAL", "MIDHANI"], "Defence procurement and valuation premiums expand"),
            "Information Technology": _sector(+0.15, +1.0, 3, [], ["INFY", "TCS", "HCLTECH"], "INR weakness offsets some global risk aversion"),
            "Healthcare": _sector(+0.20, +1.5, 3, [], [], "Defensive rotation favors pharma and healthcare"),
            "Fast Moving Consumer Goods": _sector(+0.10, +0.5, 4, [], [], "Staples attract relative inflows"),
            "Financial Services": _sector(-0.55, -4.0, 3, [], [], "Risk-off selling and credit worries dominate"),
            "Metals & Mining": _sector(-0.30, -2.0, 4, [], [], "Supply uncertainty and cyclical risk hurt"),
            "Consumer Durables": _sector(-0.40, -3.0, 4, [], [], "Discretionary demand weakens sharply"),
            "Realty": _sector(-0.45, -3.5, 4, [], [], "Risk aversion hits rate-sensitive sectors"),
            "Automobile and Auto Components": _sector(-0.45, -3.5, 4, [], [], "Supply chains and sentiment both deteriorate"),
            "Construction": _sector(-0.35, -2.5, 5, [], [], "Commodity costs rise while project appetite falls"),
            "Construction Materials": _sector(-0.30, -2.0, 5, [], [], "Demand uncertainty outweighs cost support"),
            "Power": _sector(-0.25, -2.0, 5, [], ["ADANIGREEN", "ACMESOLAR"], "Fuel-security narratives aid renewables"),
            "Telecommunication": _sector(-0.20, -1.5, 4, [], [], "General risk-off with modest direct exposure"),
            "Consumer Services": _sector(-0.50, -4.0, 4, ["INDHOTEL", "EIHOTEL"], [], "Tourism and discretionary spend fall"),
            "Textiles": _sector(-0.35, -2.5, 4, [], [], "Export and supply disruptions hurt"),
            "Media Entertainment & Publication": _sector(-0.25, -2.0, 4, [], [], "Ad demand weakens in risk-off environments"),
            "Diversified": _sector(-0.25, -2.0, 4, [], [], "Blended exposures still skew negative"),
            "Forest Materials": _sector(-0.10, -0.5, 5, [], [], "Second-order demand impact is limited"),
        },
    ),
    "china_slowdown": _complete_shock(
        market_level_impact=-0.020,
        inr_change_pct=-0.5,
        time_horizon_days=7,
        sector_overrides={
            "Metals & Mining": _sector(-0.85, -6.0, 4, ["TATASTEEL", "JSWSTEEL", "HINDALCO", "SAIL", "NMDC", "VEDL", "NATIONALUM", "HINDCOPPER"], [], "China demand dominates global industrial metal pricing"),
            "Chemicals": _sector(-0.60, -4.0, 5, ["DEEPAKNTR", "AARTIIND", "PIIND"], [], "Chinese oversupply and dumping pressure Indian spreads"),
            "Capital Goods": _sector(-0.40, -3.0, 5, [], [], "Global capex narratives cool quickly"),
            "Oil Gas & Consumable Fuels": _sector(-0.35, -2.5, 4, [], [], "China demand destruction weakens crude and refining expectations"),
            "Information Technology": _sector(-0.20, -1.5, 4, [], [], "Global enterprise spending expectations soften"),
            "Healthcare": _sector(+0.15, +1.0, 4, [], [], "India can take share in APIs and generic manufacturing"),
            "Financial Services": _sector(-0.35, -2.5, 4, [], [], "Global risk-off weakens financial valuations"),
            "Consumer Services": _sector(-0.20, -1.5, 4, [], [], "Travel and discretionary channels slow"),
            "Textiles": _sector(-0.30, -2.0, 4, [], [], "Chinese textile oversupply raises pricing pressure"),
            "Construction Materials": _sector(-0.30, -2.0, 5, [], [], "Weak commodity demand outweighs lower input costs"),
            "Automobile and Auto Components": _sector(-0.35, -2.5, 4, [], [], "Global cyclical sentiment weakens auto suppliers"),
            "Power": _sector(-0.15, -1.0, 4, [], [], "Coal softness helps but macro demand fears remain"),
            "Fast Moving Consumer Goods": _sector(-0.05, -0.3, 5, [], [], "Domestic defensiveness limits spillover"),
            "Services": _sector(-0.20, -1.5, 4, [], [], "Trade and shipping volumes slow"),
            "Realty": _sector(-0.15, -1.0, 5, [], [], "Risk-off spillover is mild but negative"),
            "Construction": _sector(-0.20, -1.5, 5, [], [], "Weaker growth expectations offset any material-cost relief"),
            "Consumer Durables": _sector(-0.25, -1.5, 4, [], [], "Electronics and global cyclical demand weaken"),
            "Telecommunication": _sector(-0.15, -1.0, 4, [], [], "Capex-heavy telecom de-rates mildly"),
            "Media Entertainment & Publication": _sector(-0.10, -0.5, 5, [], [], "Mostly domestic revenue limits the impact"),
            "Diversified": _sector(-0.20, -1.5, 5, [], [], "Blended cyclical exposures skew negative"),
            "Forest Materials": _sector(-0.10, -0.5, 5, [], [], "Pulp and commodity exports soften"),
        },
    ),
    "capex_cycle_acceleration": _complete_shock(
        market_level_impact=+0.020,
        inr_change_pct=0.0,
        time_horizon_days=10,
        sector_overrides={
            "Capital Goods": _sector(+0.85, +6.0, 7, [], ["LT", "ABB", "SIEMENS", "BHEL", "CGPOWER", "BEL", "BEML", "CUMMINSIND", "THERMAX", "GRINDWELL"], "Order books expand directly in a capex upcycle"),
            "Construction": _sector(+0.80, +5.5, 7, [], ["LT", "KPIL", "KEC", "NCC", "RVNL", "IRCON", "AFCONS"], "Infra contract awards accelerate"),
            "Construction Materials": _sector(+0.65, +4.5, 8, [], ["ULTRACEMCO", "SHREECEM", "ACC", "AMBUJACEM", "DALBHARAT"], "Cement and materials demand rise with project starts"),
            "Metals & Mining": _sector(+0.60, +4.0, 6, [], ["TATASTEEL", "JSWSTEEL", "NMDC", "SAIL"], "Steel demand and industrial confidence both rise"),
            "Power": _sector(+0.55, +4.0, 7, [], ["NTPC", "POWERGRID", "TATAPOWER", "ADANIPOWER"], "Grid and generation investments rise alongside capex"),
            "Financial Services": _sector(+0.35, +2.5, 6, [], ["SBIN", "BANKBARODA", "CANFINHOME"], "Project finance and working capital demand improve"),
            "Services": _sector(+0.40, +3.0, 6, [], ["ADANIPORTS", "GMRAIRPORT", "JSWINFRA"], "Logistics and infra services are direct beneficiaries"),
            "Telecommunication": _sector(+0.30, +2.0, 6, [], ["BHARTIARTL", "RAILTEL", "HFCL"], "Digital infrastructure capex lifts network suppliers"),
            "Information Technology": _sector(+0.25, +1.5, 6, [], ["LTTS", "KPITTECH", "PERSISTENT"], "Industrial software and digital capex improve"),
            "Automobile and Auto Components": _sector(+0.25, +1.5, 6, [], ["ASHOKLEY", "TATAMOTORS"], "Commercial vehicles benefit from construction activity"),
            "Chemicals": _sector(+0.20, +1.5, 6, [], [], "Industrial and specialty chemical demand improves"),
            "Consumer Durables": _sector(+0.15, +1.0, 8, [], [], "Income effects help over time"),
            "Realty": _sector(+0.35, +2.5, 8, [], ["DLF", "GODREJPROP", "ANANTRAJ"], "Infra-linked land and demand sentiment improve"),
            "Consumer Services": _sector(+0.20, +1.5, 8, [], [], "Employment growth improves discretionary demand"),
            "Textiles": _sector(+0.15, +1.0, 8, [], [], "Manufacturing and PLI pipelines help"),
            "Media Entertainment & Publication": _sector(+0.10, +0.5, 8, [], [], "Ad budgets expand with business confidence"),
            "Oil Gas & Consumable Fuels": _sector(+0.20, +1.5, 7, [], ["GAIL", "ATGL"], "Gas and pipeline investments rise alongside industrial capex"),
            "Diversified": _sector(+0.25, +1.5, 7, [], [], "Industrial mix skews positive"),
            "Forest Materials": _sector(+0.10, +0.5, 8, [], [], "Packaging and industrial paper demand improve"),
        },
    ),
    "monsoon_deficit": _complete_shock(
        market_level_impact=-0.015,
        inr_change_pct=-0.5,
        time_horizon_days=14,
        sector_overrides={
            "Fast Moving Consumer Goods": _sector(-0.50, -3.5, 10, ["HINDUNILVR", "DABUR", "MARICO", "GODREJCP", "COLPAL"], [], "Rural consumption slows materially with weak farm income"),
            "Automobile and Auto Components": _sector(-0.55, -4.0, 10, ["HEROMOTOCO", "BAJAJ-AUTO", "M&M"], [], "Two-wheelers and tractors are highly rural-linked"),
            "Consumer Services": _sector(-0.35, -2.5, 10, ["DMART", "DEVYANI", "JUBLFOOD"], [], "Semi-urban consumption softens in poor monsoons"),
            "Chemicals": _sector(-0.40, -3.0, 9, ["CHAMBLFERT", "COROMANDEL", "DEEPAKFERT", "PIIND", "BAYERCROP"], [], "Agri-input demand falls with weak sowing"),
            "Financial Services": _sector(-0.35, -2.5, 9, ["AUBANK", "UJJIVANSFB"], [], "Rural credit stress and microfinance NPAs rise"),
            "Construction": _sector(-0.20, -1.5, 8, [], [], "Rural and migrant labor supply disruptions slow activity"),
            "Consumer Durables": _sector(-0.30, -2.0, 8, ["VOLTAS", "HAVELLS", "CROMPTON"], [], "Rural pumps, fans, and AC demand weaken"),
            "Textiles": _sector(-0.35, -2.5, 9, ["KPRMILL", "TRIDENT"], [], "Cotton supply risk and rural demand both deteriorate"),
            "Power": _sector(-0.25, -1.5, 8, ["NHPC", "SJVN", "NTPCGREEN"], [], "Hydro generation weakens under low rainfall"),
            "Healthcare": _sector(+0.10, +0.5, 8, [], [], "Disease incidence and defensive rotation provide mild support"),
            "Capital Goods": _sector(-0.15, -1.0, 8, [], [], "Agri equipment demand softens"),
            "Metals & Mining": _sector(-0.10, -0.5, 8, [], [], "Only indirect demand linkage via equipment and rural spending"),
            "Oil Gas & Consumable Fuels": _sector(-0.10, -0.5, 8, [], [], "Farm fuel demand softens"),
            "Construction Materials": _sector(-0.20, -1.5, 9, [], [], "Construction activity slows in rural catchments"),
            "Services": _sector(-0.10, -0.5, 8, [], [], "Second-order growth effect is mild"),
            "Realty": _sector(-0.10, -0.5, 9, [], [], "Rural land and sentiment soften"),
            "Telecommunication": _sector(-0.10, -0.5, 8, [], [], "Rural recharge growth slows"),
            "Media Entertainment & Publication": _sector(-0.15, -1.0, 8, [], [], "Rural ad budgets contract"),
            "Diversified": _sector(-0.15, -1.0, 8, [], [], "Mixed rural-facing businesses weaken"),
            "Forest Materials": _sector(-0.20, -1.5, 9, ["ABREL"], [], "Broad economic softness hurts paper demand"),
        },
    ),
    "rate_cut_rbi": _complete_shock(
        market_level_impact=+0.015,
        inr_change_pct=-0.5,
        time_horizon_days=3,
        sector_overrides={
            "Realty": _sector(+0.85, +5.5, 3, [], ["DLF", "GODREJPROP", "LODHA", "BRIGADE", "PRESTIGE", "OBEROIRLTY", "SIGNATURE", "SOBHA"], "Mortgage affordability improves immediately"),
            "Financial Services": _sector(+0.40, +3.0, 3, [], ["BAJFINANCE", "SHRIRAMFIN", "LICHSGFIN", "AAVAS", "BAJAJHFL"], "Funding costs fall for NBFCs and HFCs"),
            "Automobile and Auto Components": _sector(+0.50, +3.5, 4, [], ["TATAMOTORS", "M&M", "HYUNDAI", "HEROMOTOCO"], "Auto loans get cheaper and demand revives"),
            "Consumer Durables": _sector(+0.55, +3.5, 4, [], ["TITAN", "HAVELLS", "CROMPTON", "VOLTAS", "DIXON"], "EMI-linked categories improve quickly"),
            "Construction": _sector(+0.55, +4.0, 5, [], ["LT", "KPIL", "NCC"], "Lower discount rates unlock capex and projects"),
            "Capital Goods": _sector(+0.40, +3.0, 5, [], ["ABB", "SIEMENS", "BHEL"], "Capex hurdle rates fall"),
            "Consumer Services": _sector(+0.35, +2.5, 4, [], ["DMART", "INDHOTEL", "DEVYANI"], "Lower financing and better sentiment help discretionary demand"),
            "Power": _sector(+0.35, +2.5, 5, [], ["ADANIPOWER", "NTPC", "TATAPOWER"], "Capital-intensive utilities benefit from lower WACC"),
            "Metals & Mining": _sector(+0.30, +2.0, 5, [], [], "Construction-led demand gets a cyclical boost"),
            "Fast Moving Consumer Goods": _sector(+0.15, +1.0, 5, [], [], "Lower debt burden supports rural and urban consumption"),
            "Chemicals": _sector(+0.20, +1.5, 5, [], [], "Working capital becomes cheaper"),
            "Telecommunication": _sector(+0.30, +2.0, 4, [], ["BHARTIARTL", "IDEA"], "High leverage benefits from lower interest costs"),
            "Construction Materials": _sector(+0.40, +3.0, 5, [], [], "Real estate and project demand improve"),
            "Services": _sector(+0.25, +1.5, 5, [], [], "Logistics and infra services gain"),
            "Textiles": _sector(+0.30, +2.0, 5, [], [], "Export finance and working capital improve"),
            "Media Entertainment & Publication": _sector(+0.20, +1.5, 4, [], [], "Discretionary media consumption improves"),
            "Oil Gas & Consumable Fuels": _sector(+0.10, +0.5, 4, [], [], "Only modestly rate-sensitive"),
            "Diversified": _sector(+0.25, +1.5, 5, [], [], "Blended businesses benefit from lower rates"),
            "Forest Materials": _sector(+0.15, +1.0, 5, [], [], "Paper and packaging demand improve"),
        },
    ),
}


SHOCK_KNOWLEDGE_BASE["rate_hike_fed"] = _complete_shock(
    market_level_impact=-0.022,
    inr_change_pct=-1.2,
    time_horizon_days=4,
    sector_overrides={
        "Financial Services": _sector(-0.60, -4.5, 3, ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "BAJFINANCE"], [], "Global rates trigger FII outflow and valuation compression in financials"),
        "Information Technology": _sector(-0.45, -3.0, 3, ["TCS", "INFY", "HCLTECH", "WIPRO"], [], "US growth fears dominate the FX tailwind in a hawkish Fed shock"),
        "Realty": _sector(-0.50, -3.5, 4, ["DLF", "GODREJPROP", "LODHA"], [], "Higher global yields tighten domestic financial conditions"),
        "Capital Goods": _sector(-0.40, -3.0, 5, ["LT", "ABB", "SIEMENS"], [], "Global cost of capital rises"),
        "Metals & Mining": _sector(-0.50, -3.5, 4, ["TATASTEEL", "JSWSTEEL", "HINDALCO"], [], "Global growth and commodity expectations weaken"),
        "Automobile and Auto Components": _sector(-0.35, -2.5, 4, ["TATAMOTORS", "M&M"], [], "Global risk-off hurts cyclicals"),
        "Consumer Durables": _sector(-0.30, -2.0, 4, ["TITAN", "HAVELLS"], [], "Premium valuation compression under higher global discount rates"),
        "Healthcare": _sector(+0.10, +0.5, 4, [], ["SUNPHARMA", "DIVISLAB"], "Defensive and export characteristics help"),
        "Fast Moving Consumer Goods": _sector(+0.05, +0.3, 4, [], ["HINDUNILVR", "ITC"], "Defensive rotation provides mild support"),
        "Services": _sector(-0.30, -2.0, 4, ["ADANIPORTS", "INDIGO"], [], "Risk-off and dollar strength hurt transport-sensitive names"),
    },
)

SHOCK_KNOWLEDGE_BASE["inr_appreciation"] = _complete_shock(
    market_level_impact=+0.008,
    inr_change_pct=+1.0,
    time_horizon_days=3,
    sector_overrides={
        "Information Technology": _sector(-0.80, -5.0, 1, ["INFY", "TCS", "HCLTECH", "WIPRO", "LTIM"], [], "Export translation headwind is immediate in IT"),
        "Healthcare": _sector(-0.25, -1.5, 3, ["DRREDDY", "DIVISLAB", "LUPIN"], [], "Export realizations fall, partly offset by cheaper APIs"),
        "Textiles": _sector(-0.35, -2.5, 4, ["KPRMILL", "TRIDENT", "WELSPUNLIV"], [], "Export competitiveness softens"),
        "Services": _sector(+0.35, +2.5, 2, ["GESHIP"], ["INDIGO"], "Aviation and imported fuel benefit from a stronger INR"),
        "Oil Gas & Consumable Fuels": _sector(+0.30, +2.0, 3, ["ONGC", "OIL"], ["BPCL", "HPCL", "IOC"], "Refiners gain from lower landed crude cost"),
        "Chemicals": _sector(+0.20, +1.5, 4, [], ["PIDILITIND", "AARTIIND"], "Imported feedstock gets cheaper"),
        "Capital Goods": _sector(+0.20, +1.5, 4, [], ["ABB", "BOSCHLTD"], "Imported equipment and kits are cheaper"),
        "Consumer Durables": _sector(+0.30, +2.0, 4, [], ["DIXON", "AMBER"], "Import content in electronics becomes a margin tailwind"),
        "Automobile and Auto Components": _sector(+0.15, +1.0, 4, [], ["BOSCHLTD"], "Imported components benefit modestly"),
        "Telecommunication": _sector(+0.10, +0.8, 4, [], [], "Imported network equipment gets cheaper"),
        "Power": _sector(+0.10, +0.5, 4, [], [], "Imported fuel and equipment costs ease"),
        "Metals & Mining": _sector(-0.15, -1.0, 4, ["TATASTEEL", "HINDALCO"], [], "Export competitiveness weakens"),
    },
)

SHOCK_KNOWLEDGE_BASE["global_recession"] = _complete_shock(
    market_level_impact=-0.045,
    inr_change_pct=-1.5,
    time_horizon_days=10,
    sector_overrides={
        "Metals & Mining": _sector(-0.85, -6.0, 4, ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "NMDC"], [], "Global cyclical demand destruction is most severe in metals"),
        "Information Technology": _sector(-0.70, -5.0, 4, ["TCS", "INFY", "HCLTECH", "WIPRO"], [], "US and Europe spending cuts dominate FX benefits"),
        "Chemicals": _sector(-0.70, -5.0, 5, ["DEEPAKNTR", "AARTIIND", "PIIND"], [], "Industrial demand and pricing both weaken"),
        "Services": _sector(-0.65, -5.0, 3, ["INDIGO", "ADANIPORTS", "GESHIP"], [], "Transport demand contracts sharply"),
        "Consumer Services": _sector(-0.60, -4.5, 4, ["INDHOTEL", "JUBLFOOD", "DMART"], [], "Discretionary spending slows heavily"),
        "Financial Services": _sector(-0.65, -5.0, 3, ["HDFCBANK", "ICICIBANK", "BAJFINANCE"], [], "Credit risk, flows, and growth all turn negative"),
        "Realty": _sector(-0.55, -4.0, 4, ["DLF", "GODREJPROP", "LODHA"], [], "Risk-off and weak demand are both headwinds"),
        "Construction": _sector(-0.50, -3.5, 5, ["LT", "KPIL", "NCC"], [], "Projects defer under weak growth"),
        "Capital Goods": _sector(-0.55, -4.0, 5, ["ABB", "SIEMENS", "BHEL"], [], "Capex pipelines are repriced down"),
        "Automobile and Auto Components": _sector(-0.50, -3.5, 4, ["TATAMOTORS", "M&M", "HEROMOTOCO"], [], "Vehicle demand cools in a broad recession"),
        "Consumer Durables": _sector(-0.45, -3.0, 4, ["TITAN", "HAVELLS", "DIXON"], [], "Premium discretionary categories de-rate"),
        "Oil Gas & Consumable Fuels": _sector(-0.30, -2.0, 4, ["RELIANCE", "BPCL"], [], "Demand destruction lowers earnings power"),
        "Healthcare": _sector(+0.25, +1.5, 4, [], ["SUNPHARMA", "DIVISLAB", "CIPLA"], "Defensive and export qualities help"),
        "Fast Moving Consumer Goods": _sector(+0.15, +1.0, 5, [], ["HINDUNILVR", "ITC"], "Staples hold up relatively better in recessions"),
        "Power": _sector(-0.25, -2.0, 5, ["ADANIPOWER", "TATAPOWER"], [], "Industrial demand slows and leverage hurts"),
        "Telecommunication": _sector(-0.15, -1.0, 4, [], [], "Defensive demand limits downside"),
        "Construction Materials": _sector(-0.45, -3.0, 5, [], [], "Materials demand follows construction and capex lower"),
        "Textiles": _sector(-0.40, -3.0, 4, [], [], "Export demand contracts"),
        "Media Entertainment & Publication": _sector(-0.30, -2.0, 4, [], [], "Ad budgets and discretionary leisure weaken"),
        "Diversified": _sector(-0.30, -2.0, 5, [], [], "Mixed cyclicality still points lower"),
        "Forest Materials": _sector(-0.20, -1.5, 5, ["ABREL"], [], "Paper and packaging demand soften"),
    },
)

SHOCK_KNOWLEDGE_BASE["commodity_crash"] = _complete_shock(
    market_level_impact=-0.005,
    inr_change_pct=+0.3,
    time_horizon_days=6,
    sector_overrides={
        "Metals & Mining": _sector(-0.90, -6.5, 3, ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "NMDC"], [], "Commodity price collapse directly compresses producer earnings"),
        "Oil Gas & Consumable Fuels": _sector(-0.45, -3.0, 3, ["ONGC", "OIL", "RELIANCE"], ["BPCL", "HPCL", "IOC"], "Upstream realization falls while refiners gain from cheaper input"),
        "Chemicals": _sector(+0.30, +2.0, 4, [], ["PIDILITIND", "DEEPAKNTR"], "Cheaper feedstock helps specialty and downstream chemicals"),
        "Automobile and Auto Components": _sector(+0.25, +1.5, 5, [], ["MRF", "APOLLOTYRE", "TATAMOTORS"], "Rubber, steel, and fuel costs soften"),
        "Construction Materials": _sector(+0.20, +1.5, 5, [], ["ULTRACEMCO", "ACC"], "Energy and freight costs ease"),
        "Consumer Durables": _sector(+0.15, +1.0, 5, [], ["ASIANPAINT", "DIXON"], "Input inflation relief supports margins"),
        "Fast Moving Consumer Goods": _sector(+0.10, +0.8, 5, [], ["HINDUNILVR", "ITC"], "Packaging and transport costs ease"),
        "Services": _sector(+0.10, +0.5, 4, [], ["INDIGO"], "Fuel cost relief benefits airlines and logistics"),
        "Realty": _sector(+0.10, +0.5, 5, [], [], "Construction input costs soften modestly"),
    },
)

SHOCK_KNOWLEDGE_BASE["inflation_surprise_high"] = _complete_shock(
    market_level_impact=-0.018,
    inr_change_pct=-0.8,
    time_horizon_days=5,
    sector_overrides={
        "Realty": _sector(-0.40, -2.5, 4, ["DLF", "GODREJPROP"], [], "Higher inflation revives rate fears for property"),
        "Financial Services": _sector(-0.20, -1.5, 3, ["BAJFINANCE", "LICHSGFIN"], [], "Inflation raises yield expectations and funding costs"),
        "Consumer Durables": _sector(-0.35, -2.0, 4, ["TITAN", "HAVELLS"], [], "Discretionary and financing-heavy categories weaken"),
        "Automobile and Auto Components": _sector(-0.30, -2.0, 4, ["TATAMOTORS", "M&M"], [], "Fuel and financing fears hurt demand"),
        "Fast Moving Consumer Goods": _sector(-0.25, -1.5, 4, ["HINDUNILVR", "BRITANNIA"], [], "Margin pressure rises before pricing catches up"),
        "Consumer Services": _sector(-0.30, -2.0, 4, ["JUBLFOOD", "DMART"], [], "Discretionary wallets tighten"),
        "Information Technology": _sector(+0.10, +0.5, 3, [], ["TCS", "INFY"], "FX hedge offsets domestic inflation risk"),
        "Healthcare": _sector(+0.15, +0.8, 3, [], ["SUNPHARMA", "CIPLA"], "Defensive rotation helps"),
        "Metals & Mining": _sector(-0.20, -1.0, 4, [], [], "Rate fears offset commodity pricing"),
        "Construction Materials": _sector(-0.20, -1.0, 5, [], [], "Demand fears and higher energy costs hurt"),
    },
)

SHOCK_KNOWLEDGE_BASE["inflation_surprise_low"] = _complete_shock(
    market_level_impact=+0.012,
    inr_change_pct=0.0,
    time_horizon_days=4,
    sector_overrides={
        "Realty": _sector(+0.35, +2.0, 4, [], ["DLF", "GODREJPROP"], "Lower inflation eases future rate pressure"),
        "Financial Services": _sector(+0.20, +1.5, 3, [], ["BAJFINANCE", "LICHSGFIN"], "Funding expectations improve"),
        "Consumer Durables": _sector(+0.30, +2.0, 4, [], ["TITAN", "HAVELLS"], "Lower inflation supports discretionary demand"),
        "Automobile and Auto Components": _sector(+0.25, +1.5, 4, [], ["TATAMOTORS", "M&M"], "Rates and input worries both ease"),
        "Fast Moving Consumer Goods": _sector(+0.20, +1.0, 4, [], ["HINDUNILVR", "BRITANNIA"], "Margins improve with benign input inflation"),
        "Consumer Services": _sector(+0.20, +1.0, 4, [], ["DMART", "JUBLFOOD"], "Household real income improves"),
        "Healthcare": _sector(+0.05, +0.3, 3, [], [], "Defensive sector stays steady in a benign inflation print"),
        "Capital Goods": _sector(+0.10, +0.8, 5, [], [], "Lower discount rates support capex"),
    },
)

SHOCK_KNOWLEDGE_BASE["banking_stress"] = _complete_shock(
    market_level_impact=-0.030,
    inr_change_pct=-0.8,
    time_horizon_days=6,
    sector_overrides={
        "Financial Services": _sector(-1.00, -7.0, 2, ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "INDUSINDBK", "BAJFINANCE"], [], "Banking stress is directly transmitted through the financial sector"),
        "Realty": _sector(-0.60, -4.0, 3, ["DLF", "GODREJPROP", "LODHA"], [], "Credit availability and sentiment weaken sharply"),
        "Consumer Durables": _sector(-0.45, -3.0, 4, ["TITAN", "HAVELLS"], [], "Financing channels tighten for discretionary purchases"),
        "Automobile and Auto Components": _sector(-0.40, -2.5, 4, ["TATAMOTORS", "M&M"], [], "Vehicle lending channels tighten"),
        "Construction": _sector(-0.35, -2.5, 4, ["LT", "KPIL", "NCC"], [], "Project finance costs rise and execution slows"),
        "Capital Goods": _sector(-0.35, -2.5, 5, ["ABB", "SIEMENS", "BHEL"], [], "Capex funding dries up"),
        "Power": _sector(-0.30, -2.0, 5, ["ADANIPOWER", "TATAPOWER"], [], "Leverage concerns matter more in stressed banking environments"),
        "Telecommunication": _sector(-0.25, -1.5, 4, ["IDEA"], [], "Debt-heavy telcos see financing pressure"),
        "Healthcare": _sector(+0.20, +1.2, 3, [], ["SUNPHARMA", "CIPLA"], "Defensive quality rotation benefits healthcare"),
        "Fast Moving Consumer Goods": _sector(+0.15, +0.8, 4, [], ["HINDUNILVR", "ITC"], "Staples outperform during financial stress"),
        "Information Technology": _sector(+0.10, +0.5, 4, [], ["TCS", "INFY"], "Net-cash exporters become relative safe havens"),
        "Consumer Services": _sector(-0.30, -2.0, 4, ["DMART", "INDHOTEL"], [], "Consumer confidence weakens"),
        "Services": _sector(-0.25, -1.5, 4, ["ADANIPORTS"], [], "General risk-off hits cyclical service names"),
        "Metals & Mining": _sector(-0.25, -1.5, 4, [], [], "Credit-sensitive cyclicals de-rate"),
        "Construction Materials": _sector(-0.30, -2.0, 5, [], [], "Property and construction finance tighten"),
        "Media Entertainment & Publication": _sector(-0.20, -1.0, 4, [], [], "Discretionary ad spend weakens"),
    },
)

SHOCK_KNOWLEDGE_BASE["earnings_miss_sector"] = _complete_shock(
    market_level_impact=-0.010,
    inr_change_pct=0.0,
    time_horizon_days=4,
    sector_overrides={
        "Financial Services": _sector(-0.20, -1.5, 3, [], [], "Sector-wide earnings misses compress valuations"),
        "Information Technology": _sector(-0.25, -1.8, 3, [], [], "Large-cap earnings misses hit index-heavy IT"),
        "Consumer Durables": _sector(-0.20, -1.5, 4, [], [], "High-PE sectors de-rate on earnings disappointment"),
        "Consumer Services": _sector(-0.20, -1.5, 4, [], [], "Discretionary sectors react sharply to earnings misses"),
        "Healthcare": _sector(-0.10, -0.5, 4, [], [], "Defensive sectors still correct on earnings misses"),
    },
)

SHOCK_KNOWLEDGE_BASE["earnings_beat_sector"] = _scale_shock(
    SHOCK_KNOWLEDGE_BASE["earnings_miss_sector"],
    score_factor=-1.0,
    move_factor=-1.0,
    market_level_impact=+0.010,
)

SHOCK_KNOWLEDGE_BASE["regulatory_negative"] = _complete_shock(
    market_level_impact=-0.012,
    inr_change_pct=0.0,
    time_horizon_days=6,
    sector_overrides={
        "Financial Services": _sector(-0.30, -2.0, 4, [], [], "Regulatory tightening usually hits financials first"),
        "Telecommunication": _sector(-0.30, -2.0, 4, ["IDEA", "BHARTIARTL"], [], "Tariff and compliance changes can hurt telecom cash flow"),
        "Healthcare": _sector(-0.25, -1.8, 4, ["SUNPHARMA", "DRREDDY"], [], "Pricing or compliance action can be material in pharma"),
        "Chemicals": _sector(-0.20, -1.5, 5, [], [], "Environmental or compliance action can disrupt output"),
        "Capital Goods": _sector(-0.15, -1.0, 5, [], [], "Tender or policy friction slows project flows"),
    },
)

SHOCK_KNOWLEDGE_BASE["regulatory_positive"] = _scale_shock(
    SHOCK_KNOWLEDGE_BASE["regulatory_negative"],
    score_factor=-1.0,
    move_factor=-1.0,
    market_level_impact=+0.012,
)

SHOCK_KNOWLEDGE_BASE["budget_positive"] = _complete_shock(
    market_level_impact=+0.018,
    inr_change_pct=0.0,
    time_horizon_days=6,
    sector_overrides={
        "Capital Goods": _sector(+0.75, +5.0, 6, [], ["LT", "ABB", "SIEMENS", "BHEL"], "A pro-growth budget boosts infra and industrial capex"),
        "Construction": _sector(+0.70, +4.5, 6, [], ["LT", "KPIL", "NCC", "RVNL"], "Budget outlays lift project visibility"),
        "Construction Materials": _sector(+0.55, +3.5, 7, [], ["ULTRACEMCO", "ACC", "AMBUJACEM"], "Materials demand rises with infra allocation"),
        "Financial Services": _sector(+0.40, +2.5, 5, [], ["SBIN", "BANKBARODA"], "Credit growth expectations improve"),
        "Metals & Mining": _sector(+0.40, +2.5, 5, [], ["TATASTEEL", "JSWSTEEL"], "Infra demand expectations rise"),
        "Realty": _sector(+0.25, +1.5, 6, [], ["DLF", "GODREJPROP"], "Tax and infra support help sentiment"),
        "Automobile and Auto Components": _sector(+0.20, +1.0, 5, [], [], "Demand support and infrastructure spending help auto"),
        "Consumer Durables": _sector(+0.15, +1.0, 5, [], [], "Income and tax support improve discretionary demand"),
        "Fast Moving Consumer Goods": _sector(+0.10, +0.5, 5, [], [], "Consumption support is positive but mild"),
    },
)

SHOCK_KNOWLEDGE_BASE["budget_negative"] = _complete_shock(
    market_level_impact=-0.018,
    inr_change_pct=0.0,
    time_horizon_days=6,
    sector_overrides={
        "Capital Goods": _sector(-0.70, -4.5, 6, ["LT", "ABB", "SIEMENS", "BHEL"], [], "Weak budget outlays hurt infra and industrial capex expectations"),
        "Construction": _sector(-0.65, -4.0, 6, ["LT", "KPIL", "NCC", "RVNL"], [], "Project pipelines look weaker"),
        "Construction Materials": _sector(-0.55, -3.5, 7, ["ULTRACEMCO", "ACC", "AMBUJACEM"], [], "Materials demand expectations soften"),
        "Financial Services": _sector(-0.35, -2.0, 5, [], [], "Credit growth and public spending expectations weaken"),
        "Metals & Mining": _sector(-0.35, -2.0, 5, [], [], "Infra-linked demand expectations fall"),
        "Realty": _sector(-0.25, -1.5, 6, [], [], "Sentiment worsens on weak growth support"),
        "Fast Moving Consumer Goods": _sector(-0.10, -0.5, 5, [], [], "Consumption disappointment is mild but negative"),
        "Healthcare": _sector(+0.05, +0.3, 5, [], [], "Defensive sectors relatively outperform"),
    },
)

SHOCK_KNOWLEDGE_BASE["us_tech_correction"] = _complete_shock(
    market_level_impact=-0.015,
    inr_change_pct=-0.3,
    time_horizon_days=4,
    sector_overrides={
        "Information Technology": _sector(-0.90, -6.0, 2, ["TCS", "INFY", "HCLTECH", "WIPRO", "LTIM"], [], "US tech de-rating transmits directly to Indian IT multiples"),
        "Financial Services": _sector(-0.25, -1.5, 3, [], [], "Global growth sentiment and flows soften"),
        "Consumer Durables": _sector(-0.20, -1.0, 4, [], [], "Global growth-linked premium valuations compress"),
        "Services": _sector(-0.15, -1.0, 4, [], [], "Risk sentiment weakens in global growth sectors"),
        "Healthcare": _sector(+0.10, +0.5, 4, [], [], "Defensive sectors benefit from rotation"),
        "Fast Moving Consumer Goods": _sector(+0.10, +0.5, 4, [], [], "Staples outperform in a tech-led correction"),
    },
)

SHOCK_KNOWLEDGE_BASE["fii_inflow"] = _scale_shock(
    SHOCK_KNOWLEDGE_BASE["fii_outflow"],
    score_factor=-1.0,
    move_factor=-1.0,
    market_level_impact=+0.020,
    inr_change_pct=+0.8,
    sector_overrides={
        "Healthcare": _sector(+0.10, +0.8, 4, [], [], "Defensives participate but less than cyclicals in inflow regimes"),
        "Fast Moving Consumer Goods": _sector(+0.08, +0.5, 4, [], [], "Staples lag high-beta sectors but still benefit"),
    },
)

SHOCK_KNOWLEDGE_BASE["monsoon_normal"] = _scale_shock(
    SHOCK_KNOWLEDGE_BASE["monsoon_deficit"],
    score_factor=-0.85,
    move_factor=-0.85,
    market_level_impact=+0.015,
    inr_change_pct=+0.2,
    sector_overrides={
        "Fast Moving Consumer Goods": _sector(+0.45, +3.0, 10, [], ["HINDUNILVR", "DABUR", "MARICO"], "Healthy monsoons improve rural income and staples demand"),
        "Automobile and Auto Components": _sector(+0.50, +3.5, 10, [], ["HEROMOTOCO", "BAJAJ-AUTO", "M&M"], "Rural two-wheelers and tractors benefit strongly"),
        "Chemicals": _sector(+0.35, +2.5, 9, [], ["COROMANDEL", "PIIND", "BAYERCROP"], "Sowing and agri-input demand improve"),
        "Financial Services": _sector(+0.25, +1.5, 9, [], ["AUBANK", "UJJIVANSFB"], "Rural credit quality improves"),
        "Power": _sector(+0.20, +1.0, 8, [], ["NHPC", "SJVN"], "Hydro output improves with better rainfall"),
    },
)

SHOCK_KNOWLEDGE_BASE["rate_cut_fed"] = _complete_shock(
    market_level_impact=+0.018,
    inr_change_pct=+0.3,
    time_horizon_days=4,
    sector_overrides={
        "Financial Services": _sector(+0.35, +2.5, 3, [], ["HDFCBANK", "ICICIBANK", "KOTAKBANK"], "Global liquidity and risk appetite improve with Fed easing"),
        "Capital Goods": _sector(+0.30, +2.0, 5, [], ["LT", "ABB", "SIEMENS"], "Lower global rates support capex valuations"),
        "Metals & Mining": _sector(+0.30, +2.0, 4, [], ["TATASTEEL", "JSWSTEEL"], "Global growth-risk premium improves"),
        "Realty": _sector(+0.25, +1.5, 4, [], ["DLF", "GODREJPROP"], "Easier global financial conditions support rate-sensitive assets"),
        "Information Technology": _sector(+0.10, +0.8, 3, [], ["TCS", "INFY"], "Client spending expectations improve modestly"),
        "Consumer Durables": _sector(+0.15, +1.0, 4, [], [], "Risk-on improves premium discretionary demand"),
        "Healthcare": _sector(0.0, 0.0, 4, [], [], "Defensives participate less in a risk-on Fed cut"),
    },
)

SHOCK_KNOWLEDGE_BASE["credit_rating_downgrade"] = _complete_shock(
    market_level_impact=-0.015,
    inr_change_pct=-0.3,
    time_horizon_days=5,
    sector_overrides={
        "Financial Services": _sector(-0.35, -2.5, 3, [], [], "Downgrades tighten funding and spread risk in financials"),
        "Realty": _sector(-0.30, -2.0, 4, [], [], "Financing-sensitive sectors suffer on downgrade stress"),
        "Power": _sector(-0.25, -1.8, 4, [], [], "High leverage magnifies downgrade pain"),
        "Telecommunication": _sector(-0.25, -1.8, 4, [], ["IDEA"], "Debt-heavy telecom is highly sensitive to funding spreads"),
        "Capital Goods": _sector(-0.20, -1.5, 5, [], [], "Project finance becomes more expensive"),
        "Healthcare": _sector(+0.05, +0.3, 4, [], [], "Defensives relatively outperform"),
        "Fast Moving Consumer Goods": _sector(+0.05, +0.3, 4, [], [], "Staples hold up better during funding stress"),
    },
)

SHOCK_KNOWLEDGE_BASE["unknown_high_magnitude"] = _complete_shock(
    market_level_impact=-0.050,
    inr_change_pct=-1.5,
    time_horizon_days=7,
    sector_overrides={
        "Financial Services": _sector(-0.85, -6.0, 2, [], [], "Unknown high-magnitude shocks usually force indiscriminate risk reduction"),
        "Information Technology": _sector(-0.55, -4.0, 2, [], [], "Index-heavy liquid sectors are sold first"),
        "Metals & Mining": _sector(-0.60, -4.5, 2, [], [], "High-beta cyclicals de-rate fast"),
        "Consumer Durables": _sector(-0.55, -4.0, 2, [], [], "Discretionary sectors face abrupt de-risking"),
        "Realty": _sector(-0.65, -4.5, 2, [], [], "Rate-sensitive assets get hit in panic"),
        "Services": _sector(-0.65, -4.5, 2, [], [], "Transport and travel de-rate quickly"),
        "Healthcare": _sector(+0.10, +0.8, 3, [], [], "Defensive rotation helps pharma"),
        "Fast Moving Consumer Goods": _sector(+0.05, +0.5, 3, [], [], "Staples outperform in unknown shocks"),
    },
)


NEUTRAL_SHOCK_PROFILE = _complete_shock(
    market_level_impact=0.0,
    inr_change_pct=0.0,
    time_horizon_days=5,
    sector_overrides={},
)


def get_shock_profile(shock_type: str) -> dict[str, Any]:
    token = str(shock_type or "").strip()
    if token in {"", "none"}:
        return deepcopy(NEUTRAL_SHOCK_PROFILE)
    if token not in SHOCK_KNOWLEDGE_BASE:
        return deepcopy(SHOCK_KNOWLEDGE_BASE["unknown_high_magnitude"])
    profile = deepcopy(SHOCK_KNOWLEDGE_BASE[token])
    learned = _learned_sector_overrides(token)
    if learned:
        for sector, learned_score in learned.items():
            if sector not in profile["sector_impacts"]:
                continue
            payload = profile["sector_impacts"][sector]
            static_score = float(payload.get("score", 0.0) or 0.0)
            payload["score"] = float(learned_score)
            if abs(static_score) > 1e-6:
                factor = max(-3.0, min(3.0, float(learned_score) / static_score))
                payload["estimated_move_pct"] = float(payload.get("estimated_move_pct", 0.0) or 0.0) * factor
            else:
                payload["estimated_move_pct"] = float(learned_score) * 4.0
            rationale = str(payload.get("rationale", "") or "")
            payload["rationale"] = f"{rationale}; learned overlay updated from realized sector reactions".strip("; ")
    return profile


_LEARNED_WEIGHTS_PATH = Path(__file__).resolve().parents[3] / "data" / "nlp" / "shock_impact_weights.json"
_LEARNED_WEIGHTS_CACHE: dict[str, Any] | None = None
_LEARNED_WEIGHTS_MTIME: float | None = None
_MIN_LEARNED_EVENTS = 5


def _learned_sector_overrides(shock_type: str) -> dict[str, float]:
    global _LEARNED_WEIGHTS_CACHE, _LEARNED_WEIGHTS_MTIME
    if not _LEARNED_WEIGHTS_PATH.exists():
        return {}
    mtime = _LEARNED_WEIGHTS_PATH.stat().st_mtime
    if _LEARNED_WEIGHTS_CACHE is None or _LEARNED_WEIGHTS_MTIME != mtime:
        _LEARNED_WEIGHTS_CACHE = json.loads(_LEARNED_WEIGHTS_PATH.read_text(encoding="utf-8"))
        _LEARNED_WEIGHTS_MTIME = mtime
    entry = dict((_LEARNED_WEIGHTS_CACHE or {}).get(shock_type, {}) or {})
    if int(entry.get("event_count", 0)) < _MIN_LEARNED_EVENTS:
        return {}
    return {
        sector: float(payload.get("score", 0.0))
        for sector, payload in dict(entry.get("sector_impacts", {}) or {}).items()
        if int(payload.get("observation_count", 0)) >= _MIN_LEARNED_EVENTS
    }


for _shock_name, _payload in SHOCK_KNOWLEDGE_BASE.items():
    sector_impacts = _payload.get("sector_impacts", {})
    missing = [sector for sector in NIFTY500_SECTORS if sector not in sector_impacts]
    if missing:
        raise ValueError(f"{_shock_name} missing sectors: {missing}")
