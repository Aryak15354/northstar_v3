#!/usr/bin/env python3
"""
RBI Data Processor - Clean and Convert XLSX to CSV
Handles the data processing part of RBI data collection using unified RBI handler
"""
import os
import pandas as pd
import shutil
from datetime import datetime
import hashlib
import json
import re

# Import the unified RBI data handler
import sys

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.rbi_data_handler import rbi_handler

class RBIProcessor:
    """RBI data processor for XLSX to CSV conversion"""
    
    def __init__(self, raw_dir="data/macro/raw", archive_dir="data/macro/archive", metadata_dir="data/macro/metadata"):
        self.raw_dir = raw_dir
        self.archive_dir = archive_dir
        self.metadata_dir = metadata_dir
        self.date_keywords = [
            "period",
            "date",
            "reporting",
            "week",
            "month",
            "quarter",
            "year",
            "as on",
        ]
        
        # Create directories
        for dir_path in [self.raw_dir, self.archive_dir, self.metadata_dir]:
            os.makedirs(dir_path, exist_ok=True)
        
        self.metadata_file = os.path.join(self.metadata_dir, "rbi_data_metadata.json")
        self.metadata = self.load_metadata()

    @staticmethod
    def _series_key(filename):
        """Normalize versioned CSV names to a canonical series key."""
        stem = os.path.splitext(os.path.basename(filename))[0]
        return re.sub(r"_v\d+$", "", stem)

    def _find_previous_series_file(self, current_csv_path):
        """
        Locate previous CSV for the same logical series (ignores _vN suffix).
        Returns absolute path or None.
        """
        current_name = os.path.basename(current_csv_path)
        key = self._series_key(current_name)
        candidates = []
        for csv_file in os.listdir(self.raw_dir):
            if not csv_file.endswith(".csv"):
                continue
            if csv_file == current_name:
                continue
            if self._series_key(csv_file) != key:
                continue
            path = os.path.join(self.raw_dir, csv_file)
            try:
                mtime = os.path.getmtime(path)
            except Exception:
                continue
            candidates.append((mtime, path))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    
    def load_metadata(self):
        """Load existing file metadata"""
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_metadata(self):
        """Save file metadata"""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2, default=str)
    
    def get_file_hash(self, filepath):
        """Calculate file hash for change detection"""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def detect_changes(self, filepath):
        """Detect if file has changed since last run"""
        filename = os.path.basename(filepath)
        current_hash = self.get_file_hash(filepath)
        
        if filename in self.metadata:
            old_hash = self.metadata[filename].get('hash')
            return old_hash != current_hash
        return True  # New file

    @staticmethod
    def _normalize_header_cell(value, fallback_index):
        """Normalize noisy Excel header cells into stable CSV column names."""
        if pd.isna(value):
            return f"unnamed_col_{fallback_index + 1}"
        text = str(value).strip()
        if not text:
            return f"unnamed_col_{fallback_index + 1}"
        text = " ".join(text.replace("\n", " ").replace("\r", " ").split())
        return text

    @staticmethod
    def _make_unique_columns(columns):
        """Ensure duplicate column names are made unique deterministically."""
        seen = {}
        output = []
        for col in columns:
            count = seen.get(col, 0)
            if count == 0:
                output.append(col)
            else:
                output.append(f"{col}_{count + 1}")
            seen[col] = count + 1
        return output

    def _score_date_series(self, series):
        """Return parseability score for date-like columns."""
        if series is None or len(series) == 0:
            return 0.0
        parsed = rbi_handler.convert_rbi_period_to_datetime(series)
        valid_ratio = float(parsed.notna().sum()) / float(max(len(parsed), 1))
        return valid_ratio

    def _infer_date_column(self, df):
        """Infer the most likely date/period column with keyword + parse scoring."""
        if df is None or df.empty:
            return None, 0.0

        best_col = None
        best_score = 0.0
        for col in df.columns:
            series = df[col]
            parse_score = self._score_date_series(series)
            col_text = str(col).lower()
            keyword_bonus = 0.2 if any(k in col_text for k in self.date_keywords) else 0.0
            score = min(1.0, parse_score + keyword_bonus)
            if score > best_score:
                best_score = score
                best_col = col

        if best_score < 0.35:
            return None, best_score
        return best_col, best_score

    def _extract_sheet_dataframe(self, xlsx_path, sheet_name):
        """
        Extract one sheet robustly:
        - detect header row in messy RBI workbooks
        - infer date column via parseability
        - return cleaned dataframe with normalized headers
        """
        raw_df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None)
        if raw_df.empty:
            return pd.DataFrame(), None

        raw_df = raw_df.dropna(how="all").dropna(axis=1, how="all")
        if raw_df.empty:
            return pd.DataFrame(), None

        candidate_limit = min(15, max(len(raw_df) - 1, 1))
        best = {"score": -1.0, "header_row": 0, "df": None, "date_col": None}

        for header_row in range(candidate_limit):
            header_values = [
                self._normalize_header_cell(v, idx) for idx, v in enumerate(raw_df.iloc[header_row].tolist())
            ]
            candidate = raw_df.iloc[header_row + 1 :].copy()
            if candidate.empty:
                continue
            candidate.columns = self._make_unique_columns(header_values)
            candidate = candidate.dropna(how="all")
            if candidate.empty:
                continue
            date_col, parse_score = self._infer_date_column(candidate)
            header_text = " ".join([str(x).lower() for x in header_values])
            keyword_hits = sum(1 for key in self.date_keywords if key in header_text)
            composite_score = float(parse_score) + min(0.25, keyword_hits * 0.05)
            if composite_score > best["score"]:
                best = {
                    "score": composite_score,
                    "header_row": header_row,
                    "df": candidate,
                    "date_col": date_col,
                }

        candidate_df = best["df"] if best["df"] is not None else raw_df.copy()
        if best["df"] is None:
            header_values = [self._normalize_header_cell(v, idx) for idx, v in enumerate(raw_df.iloc[0].tolist())]
            candidate_df.columns = self._make_unique_columns(header_values)
            candidate_df = candidate_df.iloc[1:].copy()
            candidate_df = candidate_df.dropna(how="all")
            date_col, _ = self._infer_date_column(candidate_df)
        else:
            date_col = best["date_col"]

        candidate_df = self.clean_dataframe(candidate_df)
        if date_col and date_col in candidate_df.columns:
            parsed_dates = rbi_handler.convert_rbi_period_to_datetime(candidate_df[date_col])
            valid_ratio = float(parsed_dates.notna().sum()) / float(max(len(parsed_dates), 1))
            if valid_ratio >= 0.25:
                candidate_df[date_col] = parsed_dates
                if date_col != "Period":
                    candidate_df = candidate_df.rename(columns={date_col: "Period"})
                candidate_df = candidate_df.dropna(subset=["Period"])
                date_col = "Period"
            else:
                date_col = None

        return candidate_df, date_col
    
    def generate_csv_name(self, df, sheet_name, source_type, index):
        """Generate intelligent CSV names based on content analysis"""
        
        # Clean sheet name
        clean_sheet = sheet_name.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
        
        # Content analysis - look at column names and first few rows
        content_str = ' '.join([str(col) for col in df.columns]).lower()
        if not df.empty:
            content_str += ' ' + ' '.join([str(val) for val in df.iloc[0] if pd.notna(val)]).lower()
        
        # Frequency detection
        frequency = ""
        if any(freq in clean_sheet or freq in content_str for freq in ['daily']):
            frequency = "_daily"
        elif any(freq in clean_sheet or freq in content_str for freq in ['weekly']):
            frequency = "_weekly"
        elif any(freq in clean_sheet or freq in content_str for freq in ['monthly']):
            frequency = "_monthly"
        elif any(freq in clean_sheet or freq in content_str for freq in ['quarterly']):
            frequency = "_quarterly"
        elif any(freq in clean_sheet or freq in content_str for freq in ['annual', 'yearly']):
            frequency = "_annual"
        
        # Content-based categorization
        category_patterns = {
            'fx_reserves': ['foreign', 'exchange', 'reserve', 'forex', 'fx'],
            'policy_rates': ['repo', 'rate', 'policy', 'crr', 'slr', 'mclr'],
            'exchange_rates': ['usd', 'inr', 'eur', 'gbp', 'jpy', 'currency'],
            'inflation': ['cpi', 'wpi', 'inflation', 'price', 'consumer'],
            'gdp_growth': ['gdp', 'gross', 'domestic', 'product', 'growth'],
            'money_supply': ['money', 'supply', 'm1', 'm2', 'm3', 'currency'],
            'banking': ['credit', 'deposit', 'bank', 'lending', 'npa'],
            'equity_indices': ['nifty', 'sensex', 'bse', 'nse', 'index'],
            'government_securities': ['gsec', 'government', 'securities', 'bond'],
            'treasury_bills': ['treasury', 'bill', 'tbill', '91', '182', '364'],
            'trade_balance': ['export', 'import', 'trade', 'balance', 'merchandise'],
            'fiscal_deficit': ['fiscal', 'deficit', 'revenue', 'expenditure'],
            'industrial_production': ['iip', 'industrial', 'production', 'manufacturing']
        }
        
        # Find best matching category
        best_category = None
        max_score = 0
        
        for category, keywords in category_patterns.items():
            score = sum(1 for keyword in keywords if keyword in content_str)
            if score > max_score:
                max_score = score
                best_category = category
        
        # Generate final name
        if best_category and max_score >= 2:
            return f"{source_type}_{best_category}{frequency}"
        elif len(clean_sheet) > 3 and clean_sheet not in ['sheet1', 'sheet2', 'sheet3']:
            return f"{source_type}_{clean_sheet[:25]}{frequency}"
        else:
            return f"{source_type}_sheet_{index + 1}{frequency}"
    
    def clean_dataframe(self, df):
        """Clean dataframe for better data quality"""
        # Remove completely empty rows and columns
        df = df.dropna(how='all').dropna(axis=1, how='all')
        
        # Clean column names
        df.columns = self._make_unique_columns([self._normalize_header_cell(col, idx) for idx, col in enumerate(df.columns)])
        
        # Try to identify and parse date columns
        date_col, score = self._infer_date_column(df)
        if date_col and score >= 0.35:
            parsed = rbi_handler.convert_rbi_period_to_datetime(df[date_col])
            if parsed.notna().sum() > 0:
                df[date_col] = parsed
        
        return df
    
    def convert_xlsx_to_csv(self, xlsx_path):
        """Convert XLSX to multiple CSVs with intelligent naming"""
        print(f"📊 Converting {os.path.basename(xlsx_path)}...")
        
        try:
            # Determine source type from filename
            filename = os.path.basename(xlsx_path).lower()
            if "50" in filename or "macro" in filename:
                source_type = "core_macro"
            else:
                source_type = "market_data"
            
            # Read all sheets
            xls_file = pd.ExcelFile(xlsx_path)
            converted_files = []
            
            print(f"   📋 Found {len(xls_file.sheet_names)} sheets to convert")
            
            for i, sheet_name in enumerate(xls_file.sheet_names):
                try:
                    df, inferred_date_col = self._extract_sheet_dataframe(xlsx_path, sheet_name)
                    
                    if df.empty:
                        print(f"   ⚠️  Skipping empty sheet: {sheet_name}")
                        continue
                    
                    # Generate intelligent name
                    csv_name = self.generate_csv_name(df, sheet_name, source_type, i)
                    csv_filename = f"{csv_name}.csv"
                    csv_path = os.path.join(self.raw_dir, csv_filename)
                    
                    # Handle duplicates by adding version numbers
                    counter = 1
                    original_csv_path = csv_path
                    while os.path.exists(csv_path):
                        name_part = os.path.splitext(original_csv_path)[0]
                        csv_path = f"{name_part}_v{counter}.csv"
                        csv_filename = os.path.basename(csv_path)
                        counter += 1
                    
                    # Clean and save CSV
                    df_clean = self.clean_dataframe(df)
                    df_clean.to_csv(csv_path, index=False)
                    converted_files.append(csv_filename)
                    if inferred_date_col and inferred_date_col in df_clean.columns:
                        valid_dates = int(df_clean[inferred_date_col].notna().sum())
                        print(
                            f"   📋 Sheet '{sheet_name}' → {csv_filename} "
                            f"({len(df_clean)} rows, date_col={inferred_date_col}, valid_dates={valid_dates})"
                        )
                    else:
                        print(f"   📋 Sheet '{sheet_name}' → {csv_filename} ({len(df_clean)} rows, date_col=none)")
                    
                except Exception as e:
                    print(f"   ⚠️  Failed to convert sheet '{sheet_name}': {e}")
                    continue
            
            print(f"   ✅ Successfully converted {len(converted_files)} sheets")
            return converted_files
            
        except Exception as e:
            print(f"   ❌ Conversion failed: {e}")
            return []
    
    def detect_retrospective_changes(self, new_csv_path, old_csv_path):
        """
        Detect retrospective changes between new and existing CSV data
        Returns detailed change analysis
        """
        
        if not os.path.exists(old_csv_path):
            return {'type': 'new_file', 'changes': 0, 'details': []}
        
        try:
            # Load both datasets
            new_df = pd.read_csv(new_csv_path)
            old_df = pd.read_csv(old_csv_path)
            
            if new_df.empty or old_df.empty:
                return {'type': 'empty_data', 'changes': 0, 'details': []}
            
            # Find date/period column using robust parser scoring.
            date_col, date_score = self._infer_date_column(new_df)
            if date_col is None:
                return {'type': 'no_date_column', 'changes': 0, 'details': []}
            if date_score < 0.35:
                return {'type': 'weak_date_column_detection', 'changes': 0, 'details': []}
            old_date_col = date_col if date_col in old_df.columns else None
            if old_date_col is None:
                old_date_col, old_score = self._infer_date_column(old_df)
                if old_date_col is None or old_score < 0.35:
                    return {'type': 'no_date_column_old', 'changes': 0, 'details': []}
            
            # Convert date columns to datetime
            try:
                new_df[date_col] = rbi_handler.convert_rbi_period_to_datetime(new_df[date_col])
                old_df[old_date_col] = rbi_handler.convert_rbi_period_to_datetime(old_df[old_date_col])
            except Exception:
                return {'type': 'date_conversion_error', 'changes': 0, 'details': []}
            
            # Remove rows with invalid dates
            new_df = new_df.dropna(subset=[date_col])
            old_df = old_df.dropna(subset=[old_date_col])
            
            if new_df.empty or old_df.empty:
                return {'type': 'no_valid_dates', 'changes': 0, 'details': []}
            
            # Find common columns (excluding date)
            new_cols = set(new_df.columns) - {date_col}
            old_cols = set(old_df.columns) - {old_date_col}
            common_cols = new_cols.intersection(old_cols)
            
            if not common_cols:
                return {'type': 'no_common_columns', 'changes': len(new_cols), 'details': []}
            
            # Find overlapping periods
            new_periods = set(new_df[date_col])
            old_periods = set(old_df[old_date_col])
            overlap_periods = new_periods.intersection(old_periods)
            
            if not overlap_periods:
                return {'type': 'no_overlap', 'new_periods': len(new_periods), 'details': []}
            
            # Check for retrospective changes in overlapping periods
            changes_detected = 0
            change_details = []
            
            for period in sorted(overlap_periods):
                new_row = new_df[new_df[date_col] == period]
                old_row = old_df[old_df[old_date_col] == period]
                
                if len(new_row) == 1 and len(old_row) == 1:
                    for col in common_cols:
                        if col in new_row.columns and col in old_row.columns:
                            try:
                                new_val = new_row[col].iloc[0]
                                old_val = old_row[col].iloc[0]
                                
                                # Compare values (handle NaN)
                                if pd.notna(new_val) and pd.notna(old_val):
                                    if abs(float(new_val) - float(old_val)) > 0.001:  # Threshold for change
                                        changes_detected += 1
                                        change_details.append({
                                            'period': period.strftime('%Y-%m-%d'),
                                            'column': col,
                                            'old_value': float(old_val),
                                            'new_value': float(new_val),
                                            'change': float(new_val) - float(old_val),
                                            'change_pct': ((float(new_val) - float(old_val)) / float(old_val)) * 100 if float(old_val) != 0 else 0
                                        })
                                elif pd.notna(new_val) != pd.notna(old_val):
                                    # One is NaN, other is not
                                    changes_detected += 1
                                    change_details.append({
                                        'period': period.strftime('%Y-%m-%d'),
                                        'column': col,
                                        'old_value': old_val,
                                        'new_value': new_val,
                                        'change': 'na_change',
                                        'change_pct': 0
                                    })
                            except Exception as e:
                                continue
            
            return {
                'type': 'retrospective_analysis',
                'changes': changes_detected,
                'overlap_periods': len(overlap_periods),
                'new_periods': len(new_periods - old_periods),
                'details': change_details[:20]  # Limit to first 20 changes
            }
            
        except Exception as e:
            return {'type': 'analysis_error', 'error': str(e), 'changes': 0, 'details': []}
    
    def save_retrospective_changes(self, filename, change_analysis):
        """Save retrospective changes to a log file"""
        
        if change_analysis['changes'] == 0:
            return
        
        changes_dir = "data/macro/changes"
        os.makedirs(changes_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        changes_file = os.path.join(changes_dir, f"retrospective_changes_{timestamp}.json")
        
        change_log = {
            'timestamp': datetime.now().isoformat(),
            'filename': filename,
            'analysis': change_analysis
        }
        
        try:
            # Load existing changes log if it exists
            all_changes_file = os.path.join(changes_dir, "all_retrospective_changes.json")
            if os.path.exists(all_changes_file):
                with open(all_changes_file, 'r') as f:
                    all_changes = json.load(f)
            else:
                all_changes = []
            
            # Add new change log
            all_changes.append(change_log)
            
            # Keep only last 100 change logs
            all_changes = all_changes[-100:]
            
            # Save individual change file
            with open(changes_file, 'w') as f:
                json.dump(change_log, f, indent=2, default=str)
            
            # Save consolidated changes file
            with open(all_changes_file, 'w') as f:
                json.dump(all_changes, f, indent=2, default=str)
            
            print(f"   📊 Retrospective changes saved: {os.path.basename(changes_file)}")
            
        except Exception as e:
            print(f"   ⚠️ Error saving retrospective changes: {e}")

    def merge_with_existing(self, new_csv_path):
        """Merge new CSV with existing data if available"""
        filename = os.path.basename(new_csv_path)
        canonical_name = f"{self._series_key(filename)}.csv"
        canonical_path = os.path.join(self.raw_dir, canonical_name)
        
        try:
            new_df = pd.read_csv(new_csv_path)
            previous_path = self._find_previous_series_file(new_csv_path)
            if previous_path and os.path.exists(previous_path):
                # Preserve previous canonical snapshot for audit before merge.
                backup_path = os.path.join(
                    self.archive_dir,
                    f"{os.path.basename(previous_path)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.backup",
                )
                shutil.copy2(previous_path, backup_path)

                # Detect retrospective changes against prior stored series.
                change_analysis = self.detect_retrospective_changes(new_csv_path, previous_path)
                if change_analysis.get("changes", 0) > 0:
                    print(f"   🔍 Retrospective changes detected: {change_analysis['changes']} changes")
                    self.save_retrospective_changes(canonical_name, change_analysis)

                try:
                    old_df = pd.read_csv(previous_path)

                    # Find date columns for merging using parseability scoring.
                    date_col, score = self._infer_date_column(new_df)
                    old_date_col = date_col if date_col and date_col in old_df.columns else None
                    if old_date_col is None:
                        old_date_col, _ = self._infer_date_column(old_df)

                    if date_col and old_date_col and score >= 0.35:
                        print(
                            f"   🔄 Merging {filename} with previous {os.path.basename(previous_path)} "
                            f"using date column: {date_col} (old={old_date_col})"
                        )

                        # Convert dates
                        new_df[date_col] = rbi_handler.convert_rbi_period_to_datetime(new_df[date_col])
                        old_df[old_date_col] = rbi_handler.convert_rbi_period_to_datetime(old_df[old_date_col])

                        # Remove rows with invalid dates
                        new_df = new_df.dropna(subset=[date_col])
                        old_df = old_df.dropna(subset=[old_date_col])
                        if old_date_col != date_col:
                            old_df = old_df.rename(columns={old_date_col: date_col})

                        # Merge datasets - new data takes precedence
                        combined_df = pd.concat([old_df, new_df]).drop_duplicates(subset=[date_col], keep='last')
                        combined_df = combined_df.sort_values(date_col).reset_index(drop=True)

                        # Save merged result to canonical series filename.
                        combined_df.to_csv(canonical_path, index=False)

                        print(
                            f"   ✅ Merged {canonical_name}: {len(old_df)} + {len(new_df)} "
                            f"→ {len(combined_df)} rows"
                        )
                    else:
                        # Fallback: replace canonical file when no merge key is available.
                        shutil.copy2(new_csv_path, canonical_path)
                        print(f"   🔄 Replaced {canonical_name}: no valid date column for merge")

                except Exception as e:
                    print(f"   ⚠️  Merge failed for {filename}: {e}")
                    shutil.copy2(new_csv_path, canonical_path)
            else:
                # First seen series: publish as canonical.
                if new_csv_path != canonical_path:
                    shutil.copy2(new_csv_path, canonical_path)
                print(f"   ✅ New file: {canonical_name} ({len(new_df)} rows)")

            # Remove temporary versioned file once canonical output is written.
            if os.path.abspath(new_csv_path) != os.path.abspath(canonical_path):
                try:
                    os.remove(new_csv_path)
                except Exception:
                    pass
                
        except Exception as e:
            print(f"   ❌ Error processing {filename}: {e}")
    
    def update_metadata(self):
        """Update metadata for all CSV files"""
        print("📋 Updating metadata...")
        
        csv_files = [f for f in os.listdir(self.raw_dir) if f.endswith('.csv')]
        
        for csv_file in csv_files:
            csv_path = os.path.join(self.raw_dir, csv_file)
            
            self.metadata[csv_file] = {
                'hash': self.get_file_hash(csv_path),
                'last_updated': datetime.now().isoformat(),
                'size': os.path.getsize(csv_path),
                'rows': len(pd.read_csv(csv_path))
            }
        
        self.save_metadata()
        print(f"   ✅ Updated metadata for {len(csv_files)} files")
    
    def cleanup_xlsx_files(self):
        """Archive XLSX files after processing"""
        print("🧹 Archiving XLSX files...")
        
        xlsx_files = [f for f in os.listdir(self.raw_dir) if f.endswith(('.xlsx', '.xls'))]
        
        for xlsx_file in xlsx_files:
            xlsx_path = os.path.join(self.raw_dir, xlsx_file)
            archive_path = os.path.join(self.archive_dir, f"{xlsx_file}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            shutil.move(xlsx_path, archive_path)
            print(f"   📦 Archived: {xlsx_file}")
    
    def process_all_xlsx(self):
        """Process all XLSX files in the raw directory"""
        print("🔄 Processing RBI XLSX files...")
        
        xlsx_files = [f for f in os.listdir(self.raw_dir) if f.endswith(('.xlsx', '.xls'))]
        
        if not xlsx_files:
            print("   ❌ No XLSX files found to process")
            return False
        
        print(f"   Found {len(xlsx_files)} XLSX files to process")
        
        total_csv_files = []
        
        for xlsx_file in xlsx_files:
            xlsx_path = os.path.join(self.raw_dir, xlsx_file)
            
            # Check if file has changed
            if self.detect_changes(xlsx_path):
                print(f"   🔍 Processing {xlsx_file} (changes detected)")
                csv_files = self.convert_xlsx_to_csv(xlsx_path)
                total_csv_files.extend(csv_files)
            else:
                print(f"   ✅ Skipping {xlsx_file} (no changes)")
        
        # Merge with existing data
        print(f"\n🔄 Merging {len(total_csv_files)} CSV files...")
        for csv_file in total_csv_files:
            csv_path = os.path.join(self.raw_dir, csv_file)
            if os.path.exists(csv_path):
                self.merge_with_existing(csv_path)
        
        # Update metadata
        self.update_metadata()
        
        # Cleanup XLSX files
        self.cleanup_xlsx_files()
        
        print(f"\n✅ RBI data processing complete!")
        print(f"   Processed: {len(xlsx_files)} XLSX files")
        print(f"   Generated: {len(total_csv_files)} CSV files")
        
        return True

def main():
    """Main function"""
    processor = RBIProcessor()
    success = processor.process_all_xlsx()
    
    if success:
        print("\n✅ RBI data processing completed")
        print("   Next step: python src/preprocessing/macro_cleaner.py")
    else:
        print("\n❌ RBI data processing failed")

if __name__ == "__main__":
    processor = RBIProcessor()
    ok = bool(processor.process_all_xlsx())
    raise SystemExit(0 if ok else 1)
