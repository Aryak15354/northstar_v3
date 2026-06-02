.DEFAULT_GOAL := help

PYTHON ?= python3

.PHONY: help surface catalog catalog-refresh doctor gaps find gap-all gap1 gap2 gap3 gap4 gap5 gap6 gap7 preopen morning dashboard eod promote-help tools-check complete complete-quick

help:
	@echo "Northstar command surface"
	@echo ""
	@echo "Navigation:"
	@echo "  make surface          Show the curated repo surface"
	@echo "  make catalog          Show the script catalog"
	@echo "  make catalog-refresh  Regenerate docs/operations/SCRIPT_CATALOG.md"
	@echo "  make doctor           Show repo hygiene and git-noise hotspots"
	@echo "  make find q=term      Search script names by keyword"
	@echo ""
	@echo "Operations:"
	@echo "  make complete         Run the full daily Gap 1-7 system"
	@echo "  make complete-quick   Run the lighter daily system refresh"
	@echo "  make preopen          Run pre-market readiness checks"
	@echo "  make morning          Run the morning pipeline"
	@echo "  make dashboard        Launch the dashboard"
	@echo "  make eod              Run EOD processing with unified P&L"
	@echo "  make promote-help     Show governed promotion CLI help"
	@echo ""
	@echo "Gap validation:"
	@echo "  make gap1 ... make gap7"
	@echo "  make gap-all"
	@echo ""
	@echo "Maintenance:"
	@echo "  make tools-check      Syntax-check the repo navigation tools"

surface:
	@$(PYTHON) scripts/ns.py

catalog:
	@$(PYTHON) scripts/ns.py catalog

catalog-refresh:
	@$(PYTHON) scripts/ns.py catalog --refresh

doctor:
	@$(PYTHON) scripts/ns.py doctor

gaps:
	@$(PYTHON) scripts/ns.py gaps

find:
	@if [ -z "$(q)" ]; then echo "Usage: make find q=sentiment"; exit 1; fi
	@$(PYTHON) scripts/ns.py find "$(q)"

gap-all: gap1 gap2 gap3 gap4 gap5 gap6 gap7

gap1:
	@$(PYTHON) scripts/verify_gap1_fixes.py

gap2:
	@$(PYTHON) scripts/validate_gap2_complete.py

gap3:
	@$(PYTHON) scripts/validate_gap3_robust_complete.py

gap4:
	@$(PYTHON) scripts/test_gap4_robust.py

gap5:
	@$(PYTHON) scripts/validate_gap5_complete.py

gap6:
	@$(PYTHON) scripts/validate_gap6_complete.py

gap7:
	@$(PYTHON) scripts/validate_gap7_complete.py

complete:
	@$(PYTHON) scripts/run_complete_v3_system.py

complete-quick:
	@$(PYTHON) scripts/run_complete_v3_system.py --quick

preopen:
	@$(PYTHON) scripts/preopen_checks.py

morning:
	@$(PYTHON) scripts/run_morning_pipeline.py

dashboard:
	@bash scripts/launch_dashboard.sh

eod:
	@$(PYTHON) scripts/eod_rebalance_with_pnl.py

promote-help:
	@$(PYTHON) scripts/promote_research_model.py --help

tools-check:
	@$(PYTHON) -m py_compile scripts/ns.py scripts/catalog_scripts.py
