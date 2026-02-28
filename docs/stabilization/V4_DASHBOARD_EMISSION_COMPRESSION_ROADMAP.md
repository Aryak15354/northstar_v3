# V4 Dashboard Emission Compression Roadmap

- Baseline emissions: 77
- Target emissions: 90

## Wave Plan
| Wave | From | To | Estimated Reduction | Goal |
|---|---:|---:|---:|---|
| Completed | 77 | 77 | 0 | Emission target achieved (<=90) |

## Top Emission Sources (Current)
| Function | Emissions | Compression Action |
|---|---:|---|
| render_wave_analysis | 5 | Fold into section-level card family and remove duplicate derivative views. |
| render_macro_news_pressure_index | 5 | Merge into one market/news pressure surface with toggle dimensions. |
| render_sector_sentiment_vs_flows | 5 | Merge into one market/news pressure surface with toggle dimensions. |
| render_risk_survival_layer | 5 | Unify drawdown/crisis/entropy into a single multi-layer risk card. |
| render_advanced_intelligence | 4 | Convert to family tabs + small-multiples + overlays; keep deep views behind expanders. |
| render_intelligence_layer | 4 | Fold into section-level card family and remove duplicate derivative views. |
| render_research_mode_compact | 3 | Fold into section-level card family and remove duplicate derivative views. |
| render_v3_analytics | 3 | Consolidate benchmark/performance/risk stats into a compact KPI+toggle card. |
| render_alpha_os_control_tower | 3 | Merge overlapping risk diagnostics into one survival engine card set. |
| render_edge_health | 2 | Fold into section-level card family and remove duplicate derivative views. |
| render_exit_risk | 2 | Fold into section-level card family and remove duplicate derivative views. |
| render_system_health_surface | 2 | Fold into section-level card family and remove duplicate derivative views. |
| render_market_state_layer | 2 | Fold into section-level card family and remove duplicate derivative views. |
| render_portfolio_expression_layer | 2 | Fold into section-level card family and remove duplicate derivative views. |
| render_causal_flow_panel | 2 | Fold into section-level card family and remove duplicate derivative views. |
| render_regime_belief_allocation_elasticity_surface | 2 | Fold into section-level card family and remove duplicate derivative views. |
| render_capital_convexity_map | 2 | Fold into section-level card family and remove duplicate derivative views. |
| render_macro_fragility_index | 2 | Fold into section-level card family and remove duplicate derivative views. |
| render_allocation_drift_vs_information_shock | 2 | Fold into section-level card family and remove duplicate derivative views. |
| _render_chart_with_contract | 1 | Fold into section-level card family and remove duplicate derivative views. |

## Safety Migration Rule
1. Replace chart with new surface container.
2. Verify contract and freshness behavior.
3. Run strict runtime gate.
4. Remove old chart emission.
5. Recompute inventory and repeat.
