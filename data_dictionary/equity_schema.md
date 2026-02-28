# Equity Schema (Public)

Fields (sample subset):
- symbol: string
- date: date
- open, high, low, close: float
- volume: int
- adjusted_close: float
- corporate_actions: struct (splits, dividends)

Notes: Primary key is (symbol, date). Times are UTC end-of-day. Corporate actions normalized.
