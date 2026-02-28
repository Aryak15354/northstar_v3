import pandas as pd
import os

RAW_PRICE_DIR = "data/raw/prices_daily"
OUTPUT_FILE = "data/processed/prices.parquet"


def main():
    all_data = []

    files = [f for f in os.listdir(RAW_PRICE_DIR) if f.endswith(".csv")]

    print(f"📦 Processing {len(files)} price files")

    for file in files:
        try:
            ticker = file.replace(".csv", "")
            path = os.path.join(RAW_PRICE_DIR, file)

            df = pd.read_csv(path)
            if df.empty:
                continue

            df["Date"] = pd.to_datetime(df["Date"])
            df["ticker"] = ticker

            all_data.append(df)

        except Exception as e:
            print(f"❌ {file}: {e}")

    prices = pd.concat(all_data)
    prices = prices.sort_values(["ticker", "Date"])

    prices.to_parquet(OUTPUT_FILE, index=False)

    print(f"✅ Prices saved: {len(prices)} rows")


if __name__ == "__main__":
    main()
