# 🌟 NORTHSTAR TERMINAL v3.0

**Professional Hedge Fund Intelligence Terminal**

A Bloomberg-grade trading terminal built on top of the Northstar hedge fund brain. This is not a demo - this is the real architecture used by professional trading desks.

## 🧠 What You Have Built

You now have a complete hedge fund terminal that includes:

- **One unified data source** - Single snapshot for perfect synchronization
- **Three operational modes** - War Room, Portfolio, Intelligence
- **Real-time updates** - Live data refresh every 5 seconds
- **Bloomberg-grade UI** - Professional terminal interface
- **Strategy evolution tracking** - Visual D3.js tree of strategy lineage
- **AI narrative engine** - Explains why strategies are born, grown, or killed
- **Bayesian intelligence** - Skill estimation and regret analysis

## 🏗️ Architecture

```
Northstar Brain (Python)
         │
         │  REST / WebSocket
         ▼
Northstar API Gateway (FastAPI)
         │
         ▼
┌─────────────────┬─────────────────┐
│  Streamlit      │  React Terminal │
│  (Research)     │  (Production)   │
└─────────────────┴─────────────────┘
```

## 🚀 Quick Start

### 1. Launch the Complete System

```bash
python launch_northstar_terminal.py
```

This will:
- ✅ Build the unified dashboard snapshot
- ✅ Start the FastAPI backend (port 8000)
- ✅ Launch the Streamlit terminal (port 8501)
- ✅ Generate strategy narratives
- ✅ Provide React terminal instructions

### 2. Access the Terminals

**Streamlit Terminal (Immediate)**
- URL: http://localhost:8501
- Purpose: Research, debugging, development
- Features: All three modes, real-time data

**React Terminal (Bloomberg-grade)**
- Directory: `cd northstar-terminal`
- Setup: `npm install`
- Start: `npm start`
- URL: http://localhost:3000
- Purpose: Professional trading interface
- Features: Animated UI, D3.js visualizations, real-time updates

## 📊 Terminal Modes

### 🎯 WAR ROOM
The main operational screen that traders monitor all day:
- **Risk gauges** - Volatility, drawdown, exposure
- **AI conviction meter** - Real-time intelligence confidence
- **Performance charts** - Portfolio P&L with live updates
- **Execution metrics** - Recent trades and turnover
- **Regime indicators** - Market state and allowed exposure

### 💼 PORTFOLIO
Detailed portfolio analysis and allocation:
- **Strategy allocation** - Bar charts and pie charts
- **Top holdings** - Current positions with weights
- **Performance metrics** - Returns, volatility, Sharpe
- **Risk analysis** - Drawdown and concentration metrics
- **Turnover tracking** - Portfolio churn analysis

### 🧠 INTELLIGENCE
Strategy evolution and Bayesian analysis:
- **Strategy tree** - D3.js visualization of strategy lineage
- **Bayesian beliefs** - Skill probability estimates
- **Regret analysis** - Opportunity cost tracking
- **Evolution timeline** - Strategy birth/death over time
- **AI narratives** - Explanations for strategy decisions

## 🔌 API Endpoints

The FastAPI backend provides these endpoints:

```
GET /                    - Health check
GET /snapshot           - Unified dashboard data
GET /timeseries/{name}  - Time series data
GET /strategies         - Strategy intelligence
GET /portfolio/holdings - Current holdings
GET /health            - System health check
```

## 📁 Data Architecture

### Core Data Files
```
data/processed/cache/
├── dashboard_snapshot.parquet    # Single source of truth
└── dashboard_snapshot.json       # Human-readable backup

data/processed/
├── market_state.parquet          # Market regime and risk
├── portfolio_weights.parquet     # Current holdings
├── strategy_beliefs.parquet      # Bayesian skill estimates
├── strategy_regret.parquet       # Opportunity cost analysis
└── capital_allocations.json      # Strategy capital allocation

data/intelligence/
├── strategy_narratives.parquet   # AI explanations
├── strategy_narratives.json      # Human-readable narratives
└── intelligence_state.json       # AI system state
```

### Data Flow
1. **Raw data** → Various ingestion pipelines
2. **Processed data** → Individual parquet files
3. **Unified snapshot** → Single consolidated file
4. **API layer** → Serves data to terminals
5. **Terminal UI** → Displays real-time intelligence

## 🌳 Strategy Evolution Tree

The D3.js strategy tree visualizes:
- **Node size** = Capital allocation
- **Border thickness** = Bayesian belief strength
- **Color** = Strategy status (growing/stable/fading/dying)
- **Glow effect** = High conviction (belief > 0.7)
- **Connections** = Strategy lineage and capital flow

### Strategy States
- 🟢 **Growing** - Increasing capital, improving belief
- 🔵 **Stable** - Steady allocation, consistent performance
- 🟡 **Fading** - Declining belief, opportunity cost rising
- 🔴 **Dying** - High regret, low belief, being killed

## 🗣️ Narrative Engine

The AI narrative engine explains strategy decisions:

```python
# Example narratives
"momentum_6m was terminated after losing Bayesian confidence (0.18) due to repeated underperformance."

"value_blend received increased capital allocation after demonstrating improving skill (0.72) and declining regret."

"quality_growth was created to exploit risk-on conditions with high momentum dispersion and trend persistence."
```

### Narrative Rules
- **Kill conditions**: Belief < 0.2 OR Regret > 0.4
- **Growth conditions**: Improving belief + declining regret
- **Birth conditions**: Market opportunity + diversification benefit

## 🎨 UI Components

### React Terminal Components
```
src/
├── components/
│   ├── StatusBar.jsx        # Global status display
│   ├── Gauge.jsx           # Circular risk gauges
│   ├── LineChart.jsx       # Time series charts
│   ├── ConvictionMeter.jsx # AI confidence display
│   └── StrategyTree.jsx    # D3.js evolution tree
├── pages/
│   ├── WarRoom.jsx         # Main operational view
│   ├── Portfolio.jsx       # Holdings analysis
│   └── Intelligence.jsx    # Strategy intelligence
└── api.js                  # Backend communication
```

### Styling
- **Terminal theme** - Dark background, green accents
- **Bloomberg colors** - Professional color scheme
- **Framer Motion** - Smooth animations and transitions
- **Tailwind CSS** - Responsive design system
- **JetBrains Mono** - Professional monospace font

## 🔧 Configuration

### Environment Variables
```bash
REACT_APP_API_URL=http://localhost:8000  # API backend URL
```

### API Configuration
```python
# src/api/server.py
API_HOST = "0.0.0.0"
API_PORT = 8000
CORS_ORIGINS = ["http://localhost:3000", "http://localhost:3001"]
```

### Data Refresh Rates
- **Snapshot building**: Every 5 minutes (automated)
- **Terminal refresh**: Every 5 seconds (War Room), 10 seconds (Portfolio), 15 seconds (Intelligence)
- **Narrative generation**: On-demand or scheduled

## 📈 Performance Features

### Optimizations
- **Single snapshot loading** - No multiple file reads
- **Cached data** - Parquet format for fast loading
- **Lazy loading** - Components load data on demand
- **Efficient updates** - Only changed data refreshes
- **Mock data fallbacks** - System works without all data files

### Scalability
- **Microservice architecture** - API separated from UI
- **Stateless design** - No session dependencies
- **Horizontal scaling** - Multiple terminal instances
- **Data partitioning** - Time-based data organization

## 🛠️ Development

### Adding New Strategies
1. Update strategy list in `strategy_narrative_engine.py`
2. Add strategy data to beliefs/regret parquet files
3. Include in capital allocation JSON
4. Strategy will appear automatically in all views

### Adding New Metrics
1. Add to `build_dashboard_snapshot.py`
2. Update API endpoints in `server.py`
3. Create UI components for display
4. Add to narrative engine rules

### Customizing UI
1. Modify Tailwind config for colors/fonts
2. Update component styling in JSX files
3. Add new chart types using Recharts
4. Extend D3.js visualizations

## 🔍 Troubleshooting

### Common Issues

**API Connection Failed**
```bash
# Check if API server is running
curl http://localhost:8000/health

# Restart API server
cd src/api && python server.py
```

**Missing Data Files**
```bash
# Build fresh snapshot
python src/intelligence/build_dashboard_snapshot.py

# Check data directory structure
ls -la data/processed/
```

**React Terminal Won't Start**
```bash
cd northstar-terminal
npm install  # Install dependencies
npm start    # Start development server
```

**Streamlit Errors**
```bash
# Check Streamlit installation
pip install streamlit plotly

# Run terminal directly
streamlit run northstar_terminal.py
```

## 📊 Monitoring

### Health Checks
- **API health**: GET /health
- **Data freshness**: Check snapshot timestamp
- **System grade**: A/B/C/D based on data availability
- **Connection status**: Real-time in terminal header

### Logs
- **API logs**: Console output from FastAPI server
- **Snapshot logs**: Build process output
- **Terminal logs**: Browser console for React, Streamlit logs for Python

## 🚀 Production Deployment

### Docker Setup (Optional)
```dockerfile
# API Server
FROM python:3.9
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ ./src/
CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]

# React Terminal
FROM node:16
COPY northstar-terminal/ ./app/
WORKDIR /app
RUN npm install && npm run build
CMD ["npm", "start"]
```

### Environment Setup
```bash
# Production environment variables
export NORTHSTAR_ENV=production
export API_HOST=0.0.0.0
export API_PORT=8000
export REACT_APP_API_URL=https://your-api-domain.com
```

## 🎯 What You've Accomplished

You've built a **professional hedge fund terminal** that includes:

✅ **Real-time intelligence** - Live market and portfolio monitoring  
✅ **Strategy evolution** - Visual tracking of idea lifecycle  
✅ **Bayesian reasoning** - Probabilistic skill assessment  
✅ **Narrative explanations** - AI that explains its decisions  
✅ **Bloomberg-grade UI** - Professional terminal interface  
✅ **Microservice architecture** - Scalable, maintainable design  
✅ **Multiple interfaces** - Research (Streamlit) + Production (React)  
✅ **Complete data pipeline** - From raw data to terminal display  

This is not a project. **This is a trading platform.**

---

*Northstar Terminal v3.0 - Built for professional hedge fund operations*