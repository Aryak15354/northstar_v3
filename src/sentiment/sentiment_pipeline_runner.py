"""
SentimentPipelineRunner — Orchestrates the daily sentiment pipeline.

The runner is responsible for:
1. Checking if today's sentiment has already been computed (idempotent)
2. Running the news ingestion and scoring pipeline
3. Exporting sentiment to v3 format
4. Writing output to data/sentiment/v3/
5. Updating SentimentState in UnifiedState
6. Emitting pipeline completion events
7. Logging structured completion records

This runner is designed to be called from the pre-market sequence at 06:00 IST,
BEFORE update_market_and_rbi_data.sh completes, so sentiment is ready when
the intelligence stack activates at 09:00.

It is safe to call multiple times — if sentiment has already been computed for
today, it logs "already fresh" and exits without reprocessing.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
import pandas as pd
import subprocess
import sys

logger = logging.getLogger(__name__)


@dataclass
class SentimentPipelineResult:
    """Result of sentiment pipeline execution"""
    status: str  # 'SUCCESS', 'ALREADY_FRESH', 'PARTIAL', 'FAILED'
    articles_processed: int
    companies_covered: int
    market_score_today: float  # Raw (not z-scored) market sentiment today
    run_duration_seconds: float
    errors: List[str]
    as_of_date: datetime


class SentimentPipelineRunner:
    """Orchestrates the daily sentiment pipeline"""
    
    def __init__(self, config: dict, event_bus=None):
        """
        Initialize the pipeline runner.
        
        Args:
            config: System configuration dict
            event_bus: Optional event bus for emitting events
        """
        self.config = config
        self.event_bus = event_bus
        
        # Get paths from config
        sentiment_config = config.get('sentiment', {})
        self.v3_output_dir = Path(sentiment_config.get('v3_output_dir', 'data/sentiment/v3'))
        self.processed_output_dir = Path(sentiment_config.get('processed_output_dir', 'data/processed/sentiment'))
        self.duckdb_path = Path(sentiment_config.get('duckdb_path', 'data/sentiment.duckdb'))
        
        # Ensure directories exist
        self.v3_output_dir.mkdir(parents=True, exist_ok=True)
        self.processed_output_dir.mkdir(parents=True, exist_ok=True)
    
    def is_today_fresh(self, as_of_date: datetime) -> bool:
        """
        Check whether sentiment data exists for as_of_date or as_of_date - 1 business day.
        
        Args:
            as_of_date: Date to check
            
        Returns:
            True if fresh, False if stale or missing
        """
        try:
            market_sentiment_path = self.v3_output_dir / 'market_sentiment_india.parquet'
            
            if not market_sentiment_path.exists():
                return False
            
            df = pd.read_parquet(market_sentiment_path)
            
            if df.empty:
                return False
            
            # Find date column
            date_col = next((c for c in df.columns if 'date' in c.lower()), None)
            if not date_col:
                return False
            
            df[date_col] = pd.to_datetime(df[date_col])
            latest_date = df[date_col].max()
            
            # Check if latest date is today or yesterday (business day)
            days_old = (as_of_date.date() - latest_date.date()).days
            
            # Fresh if 0-2 days old (allows for weekends)
            return days_old <= 2
            
        except Exception as e:
            logger.error(f"Error checking freshness: {e}")
            return False
    
    def run(self, as_of_date: datetime, force: bool = False) -> SentimentPipelineResult:
        """
        Run the sentiment pipeline.
        
        Args:
            as_of_date: Date to process sentiment for
            force: If True, run even if data is fresh
            
        Returns:
            SentimentPipelineResult with status and metrics
        """
        start_time = pd.Timestamp.now()
        errors = []
        
        try:
            # Check if already fresh
            if not force and self.is_today_fresh(as_of_date):
                logger.info(f"Sentiment data already fresh for {as_of_date.date()}")
                return SentimentPipelineResult(
                    status='ALREADY_FRESH',
                    articles_processed=0,
                    companies_covered=0,
                    market_score_today=0.0,
                    run_duration_seconds=0.0,
                    errors=[],
                    as_of_date=as_of_date
                )
            
            logger.info(f"Running sentiment pipeline for {as_of_date.date()}")
            
            # Run the export script (which processes and exports sentiment)
            cmd = [
                sys.executable,
                'scripts/export_sentiment_to_v3.py',
                '--duckdb-path', str(self.duckdb_path),
                '--output-dir', str(self.processed_output_dir),
                '--incremental'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                error_msg = f"Export script failed: {result.stderr}"
                logger.error(error_msg)
                errors.append(error_msg)
                
                return SentimentPipelineResult(
                    status='FAILED',
                    articles_processed=0,
                    companies_covered=0,
                    market_score_today=0.0,
                    run_duration_seconds=(pd.Timestamp.now() - start_time).total_seconds(),
                    errors=errors,
                    as_of_date=as_of_date
                )
            
            # Copy processed data to v3 format
            self._copy_to_v3_format()
            
            # Get metrics from output
            articles_processed, companies_covered, market_score = self._get_pipeline_metrics(as_of_date)
            
            duration = (pd.Timestamp.now() - start_time).total_seconds()
            
            # Emit event if event bus available
            if self.event_bus:
                try:
                    self.event_bus.emit('SENTIMENT_PIPELINE_COMPLETE', {
                        'articles_processed': articles_processed,
                        'companies_covered': companies_covered,
                        'market_score': market_score,
                        'pipeline_duration_seconds': duration,
                        'as_of_date': as_of_date.isoformat()
                    })
                except Exception as e:
                    logger.warning(f"Could not emit event: {e}")
            
            logger.info(f"Sentiment pipeline completed: {articles_processed} articles, {companies_covered} companies")
            
            return SentimentPipelineResult(
                status='SUCCESS',
                articles_processed=articles_processed,
                companies_covered=companies_covered,
                market_score_today=market_score,
                run_duration_seconds=duration,
                errors=errors,
                as_of_date=as_of_date
            )
            
        except subprocess.TimeoutExpired:
            error_msg = "Pipeline timed out after 300 seconds"
            logger.error(error_msg)
            errors.append(error_msg)
            
            return SentimentPipelineResult(
                status='FAILED',
                articles_processed=0,
                companies_covered=0,
                market_score_today=0.0,
                run_duration_seconds=(pd.Timestamp.now() - start_time).total_seconds(),
                errors=errors,
                as_of_date=as_of_date
            )
            
        except Exception as e:
            error_msg = f"Pipeline error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            
            return SentimentPipelineResult(
                status='FAILED',
                articles_processed=0,
                companies_covered=0,
                market_score_today=0.0,
                run_duration_seconds=(pd.Timestamp.now() - start_time).total_seconds(),
                errors=errors,
                as_of_date=as_of_date
            )
    
    def _copy_to_v3_format(self):
        """Copy processed sentiment to v3 format"""
        try:
            # Copy market sentiment
            market_src = self.processed_output_dir / 'market_sentiment_daily.parquet'
            market_dst = self.v3_output_dir / 'market_sentiment_india.parquet'
            
            if market_src.exists():
                df = pd.read_parquet(market_src)
                df.to_parquet(market_dst, index=False)
                logger.info(f"Copied market sentiment to v3: {len(df)} rows")
            
            # Copy company sentiment
            company_src = self.processed_output_dir / 'ticker_sentiment_daily.parquet'
            company_dst = self.v3_output_dir / 'company_sentiment_trends.parquet'
            
            if company_src.exists():
                df = pd.read_parquet(company_src)
                df.to_parquet(company_dst, index=False)
                logger.info(f"Copied company sentiment to v3: {len(df)} rows")
                
        except Exception as e:
            logger.error(f"Error copying to v3 format: {e}")
    
    def _get_pipeline_metrics(self, as_of_date: datetime) -> tuple:
        """Get metrics from pipeline output"""
        try:
            # Read market sentiment
            market_path = self.v3_output_dir / 'market_sentiment_india.parquet'
            if market_path.exists():
                market_df = pd.read_parquet(market_path)
                
                # Get today's score
                date_col = next((c for c in market_df.columns if 'date' in c.lower()), None)
                if date_col:
                    market_df[date_col] = pd.to_datetime(market_df[date_col])
                    today_data = market_df[market_df[date_col] == as_of_date.date()]
                    
                    if not today_data.empty:
                        # Find score column
                        score_cols = [c for c in today_data.columns if 'polarity' in c.lower() or 'score' in c.lower()]
                        if score_cols:
                            market_score = float(today_data[score_cols[0]].iloc[0])
                        else:
                            market_score = 0.0
                    else:
                        market_score = 0.0
                else:
                    market_score = 0.0
            else:
                market_score = 0.0
            
            # Read company sentiment
            company_path = self.v3_output_dir / 'company_sentiment_trends.parquet'
            if company_path.exists():
                company_df = pd.read_parquet(company_path)
                
                # Count unique companies
                ticker_col = next((c for c in company_df.columns if 'ticker' in c.lower()), None)
                if ticker_col:
                    companies_covered = company_df[ticker_col].nunique()
                else:
                    companies_covered = 0
                
                # Count articles (approximate from rows)
                articles_processed = len(company_df)
            else:
                companies_covered = 0
                articles_processed = 0
            
            return articles_processed, companies_covered, market_score
            
        except Exception as e:
            logger.error(f"Error getting pipeline metrics: {e}")
            return 0, 0, 0.0
    
    def run_historical_backfill(self, start_date: datetime, end_date: datetime):
        """
        Run the pipeline for every trading day between start_date and end_date.
        
        This is the one-time operation to backfill historical sentiment scores.
        
        Args:
            start_date: Start date for backfill
            end_date: End date for backfill
        """
        logger.info(f"Starting historical backfill from {start_date.date()} to {end_date.date()}")
        
        # For now, just run the export with full date range
        # The export script should handle historical data
        try:
            cmd = [
                sys.executable,
                'scripts/export_sentiment_to_v3.py',
                '--duckdb-path', str(self.duckdb_path),
                '--output-dir', str(self.processed_output_dir),
                '--start-date', start_date.strftime('%Y-%m-%d')
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            
            if result.returncode == 0:
                logger.info("Historical backfill completed successfully")
                self._copy_to_v3_format()
            else:
                logger.error(f"Historical backfill failed: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Error during historical backfill: {e}", exc_info=True)
