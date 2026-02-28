"""
Implied Volatility Surface Modeling for Northstar V3 Volatility System

Implements IV surface fitting with:
- SVI (Stochastic Volatility Inspired) parameterization
- SABR model support
- No-arbitrage constraint enforcement
- Surface quality metrics and validation
- Fallback to simpler models when fit fails

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from scipy.optimize import minimize, differential_evolution
from scipy.interpolate import RectBivariateSpline, interp1d
from enum import Enum

logger = logging.getLogger(__name__)


class SurfaceModel(Enum):
    """IV surface model types"""
    SVI = "SVI"
    SABR = "SABR"
    FLAT = "FLAT"
    STICKY_STRIKE = "STICKY_STRIKE"


@dataclass
class SVIParameters:
    """SVI model parameters: sigma^2(k) = a + b*(rho*(k-m) + sqrt((k-m)^2 + sigma^2))"""
    a: float  # Vertical shift
    b: float  # Slope
    rho: float  # Rotation (-1 to 1)
    m: float  # Horizontal shift
    sigma: float  # Smoothness
    
    def validate(self) -> bool:
        """Validate SVI parameters satisfy no-arbitrage conditions"""
        # Condition 1: a + b*sigma*sqrt(1-rho^2) >= 0 (non-negative variance)
        if self.a + self.b * self.sigma * np.sqrt(1 - self.rho**2) < 0:
            return False
        
        # Condition 2: b >= 0
        if self.b < 0:
            return False
        
        # Condition 3: |rho| < 1
        if abs(self.rho) >= 1:
            return False
        
        # Condition 4: sigma > 0
        if self.sigma <= 0:
            return False
        
        # Condition 5: b*(1 + |rho|) < 4 (butterfly arbitrage)
        if self.b * (1 + abs(self.rho)) >= 4:
            return False
        
        return True



@dataclass
class SABRParameters:
    """SABR model parameters"""
    alpha: float  # Initial volatility
    beta: float  # CEV exponent (0 to 1)
    rho: float  # Correlation (-1 to 1)
    nu: float  # Vol of vol
    
    def validate(self) -> bool:
        """Validate SABR parameters"""
        if self.alpha <= 0:
            return False
        if not (0 <= self.beta <= 1):
            return False
        if abs(self.rho) >= 1:
            return False
        if self.nu < 0:
            return False
        return True


@dataclass
class SurfaceQuality:
    """IV surface quality metrics"""
    fit_rmse: float  # Root mean squared error
    fit_r_squared: float  # R-squared
    arbitrage_violations: int  # Number of arbitrage violations
    data_coverage: float  # Percentage of strikes/expiries with data
    extrapolation_quality: float  # Quality of extrapolation (0-1)
    model_type: SurfaceModel
    timestamp: datetime
    
    def get_quality_score(self) -> float:
        """Compute overall quality score (0-1)"""
        # Penalize high RMSE
        rmse_score = max(0, 1 - self.fit_rmse / 0.5)  # Normalize by 50% vol
        
        # Reward high R-squared
        r2_score = max(0, self.fit_r_squared)
        
        # Penalize arbitrage violations
        arb_score = 1.0 if self.arbitrage_violations == 0 else 0.5
        
        # Reward good data coverage
        coverage_score = self.data_coverage
        
        # Weight the components
        quality = (
            0.3 * rmse_score +
            0.3 * r2_score +
            0.2 * arb_score +
            0.2 * coverage_score
        )
        
        return max(0.0, min(1.0, quality))


@dataclass
class OptionQuote:
    """Single option quote"""
    underlying: str
    strike: float
    expiry: date
    option_type: str  # 'call' or 'put'
    implied_vol: float
    bid: float
    ask: float
    mid_price: float
    volume: int
    open_interest: int
    timestamp: datetime


class IVSurface:
    """
    Implied Volatility Surface with SVI/SABR fitting.
    
    Implements:
    - Property 1: No-arbitrage constraints (calendar spreads, butterfly spreads)
    - SVI parameterization for robustness
    - SABR model support
    - Fallback to simpler models
    - Surface quality validation
    """
    
    def __init__(self, underlying: str, spot_price: float, risk_free_rate: float = 0.05):
        self.underlying = underlying
        self.spot_price = spot_price
        self.risk_free_rate = risk_free_rate
        
        # Surface data
        self.quotes: List[OptionQuote] = []
        self.fitted_model: Optional[SurfaceModel] = None
        self.svi_params_by_expiry: Dict[date, SVIParameters] = {}
        self.sabr_params_by_expiry: Dict[date, SABRParameters] = {}
        self.flat_vol_by_expiry: Dict[date, float] = {}
        
        # Quality metrics
        self.quality: Optional[SurfaceQuality] = None
        
        # Interpolation objects
        self._surface_interpolator: Optional[RectBivariateSpline] = None
        self._expiry_interpolator: Optional[interp1d] = None
        
        self.last_fit_time: Optional[datetime] = None

    
    def add_quote(self, quote: OptionQuote) -> None:
        """Add option quote to surface data"""
        self.quotes.append(quote)
    
    def add_quotes(self, quotes: List[OptionQuote]) -> None:
        """Add multiple option quotes"""
        self.quotes.extend(quotes)
    
    def fit_surface(self, model: SurfaceModel = SurfaceModel.SVI) -> bool:
        """
        Fit IV surface using specified model.
        
        Implements Property 1: No-arbitrage constraints
        """
        if len(self.quotes) < 10:
            logger.warning(f"Insufficient data for surface fitting: {len(self.quotes)} quotes")
            return self._fallback_to_flat_vol()
        
        try:
            if model == SurfaceModel.SVI:
                success = self._fit_svi_surface()
            elif model == SurfaceModel.SABR:
                success = self._fit_sabr_surface()
            else:
                success = self._fallback_to_flat_vol()
            
            if success:
                self.fitted_model = model
                self._compute_quality_metrics()
                self.last_fit_time = datetime.now()
                
                # Validate no-arbitrage
                if not self._validate_no_arbitrage():
                    logger.warning("Arbitrage violations detected, falling back to simpler model")
                    return self._fallback_to_flat_vol()
                
                return True
            else:
                logger.warning(f"{model.value} fit failed, trying fallback")
                return self._fallback_to_flat_vol()
                
        except Exception as e:
            logger.error(f"Error fitting surface: {e}")
            return self._fallback_to_flat_vol()
    
    def _fit_svi_surface(self) -> bool:
        """Fit SVI model to each expiry slice"""
        # Group quotes by expiry
        quotes_by_expiry = self._group_by_expiry()
        
        if len(quotes_by_expiry) == 0:
            return False
        
        success_count = 0
        
        for expiry, expiry_quotes in quotes_by_expiry.items():
            if len(expiry_quotes) < 5:  # Need at least 5 points per slice
                continue
            
            # Convert to log-moneyness and total variance
            strikes = np.array([q.strike for q in expiry_quotes])
            vols = np.array([q.implied_vol for q in expiry_quotes])
            
            # Time to expiry in years
            tte = (expiry - datetime.now().date()).days / 365.0
            if tte <= 0:
                continue
            
            # Log-moneyness: k = log(K/F) where F = S*exp(r*T)
            forward = self.spot_price * np.exp(self.risk_free_rate * tte)
            log_moneyness = np.log(strikes / forward)
            
            # Total variance: w = sigma^2 * T
            total_variance = vols**2 * tte
            
            # Fit SVI parameters
            svi_params = self._fit_svi_slice(log_moneyness, total_variance)
            
            if svi_params and svi_params.validate():
                self.svi_params_by_expiry[expiry] = svi_params
                success_count += 1
        
        return success_count > 0
    
    def _fit_svi_slice(self, log_moneyness: np.ndarray, total_variance: np.ndarray) -> Optional[SVIParameters]:
        """Fit SVI parameters to a single expiry slice"""
        
        # Initial guess
        a_init = np.mean(total_variance)
        b_init = 0.1
        rho_init = 0.0
        m_init = np.mean(log_moneyness)
        sigma_init = 0.1
        
        x0 = np.array([a_init, b_init, rho_init, m_init, sigma_init])
        
        # Bounds to ensure no-arbitrage
        bounds = [
            (0.001, 2.0),      # a: positive variance
            (0.001, 1.0),      # b: positive slope
            (-0.999, 0.999),   # rho: correlation
            (-2.0, 2.0),       # m: horizontal shift
            (0.001, 2.0)       # sigma: smoothness
        ]
        
        def objective(params):
            a, b, rho, m, sigma = params
            predicted = a + b * (rho * (log_moneyness - m) + 
                               np.sqrt((log_moneyness - m)**2 + sigma**2))
            return np.sum((total_variance - predicted)**2)
        
        def constraint_butterfly(params):
            """Butterfly arbitrage constraint"""
            a, b, rho, m, sigma = params
            return 4 - b * (1 + abs(rho))
        
        def constraint_nonneg(params):
            """Non-negative variance constraint"""
            a, b, rho, m, sigma = params
            return a + b * sigma * np.sqrt(1 - rho**2)
        
        constraints = [
            {'type': 'ineq', 'fun': constraint_butterfly},
            {'type': 'ineq', 'fun': constraint_nonneg}
        ]
        
        try:
            result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints)
            
            if result.success:
                a, b, rho, m, sigma = result.x
                return SVIParameters(a=a, b=b, rho=rho, m=m, sigma=sigma)
        except Exception as e:
            logger.warning(f"SVI fit failed: {e}")
        
        return None

    
    def _fit_sabr_surface(self) -> bool:
        """Fit SABR model to each expiry slice"""
        quotes_by_expiry = self._group_by_expiry()
        
        if len(quotes_by_expiry) == 0:
            return False
        
        success_count = 0
        
        for expiry, expiry_quotes in quotes_by_expiry.items():
            if len(expiry_quotes) < 5:
                continue
            
            strikes = np.array([q.strike for q in expiry_quotes])
            vols = np.array([q.implied_vol for q in expiry_quotes])
            
            tte = (expiry - datetime.now().date()).days / 365.0
            if tte <= 0:
                continue
            
            sabr_params = self._fit_sabr_slice(strikes, vols, tte)
            
            if sabr_params and sabr_params.validate():
                self.sabr_params_by_expiry[expiry] = sabr_params
                success_count += 1
        
        return success_count > 0
    
    def _fit_sabr_slice(self, strikes: np.ndarray, vols: np.ndarray, tte: float) -> Optional[SABRParameters]:
        """Fit SABR parameters to a single expiry slice"""
        
        # Initial guess
        alpha_init = np.mean(vols)
        beta_init = 0.5
        rho_init = 0.0
        nu_init = 0.3
        
        x0 = np.array([alpha_init, beta_init, rho_init, nu_init])
        
        bounds = [
            (0.001, 2.0),      # alpha
            (0.0, 1.0),        # beta
            (-0.999, 0.999),   # rho
            (0.001, 2.0)       # nu
        ]
        
        def objective(params):
            alpha, beta, rho, nu = params
            predicted = self._sabr_vol(strikes, self.spot_price, tte, alpha, beta, rho, nu)
            return np.sum((vols - predicted)**2)
        
        try:
            result = minimize(objective, x0, method='L-BFGS-B', bounds=bounds)
            
            if result.success:
                alpha, beta, rho, nu = result.x
                return SABRParameters(alpha=alpha, beta=beta, rho=rho, nu=nu)
        except Exception as e:
            logger.warning(f"SABR fit failed: {e}")
        
        return None
    
    def _sabr_vol(self, K: np.ndarray, F: float, T: float, alpha: float, beta: float, rho: float, nu: float) -> np.ndarray:
        """SABR volatility formula (Hagan approximation)"""
        # Handle ATM case
        atm_mask = np.abs(K - F) < 1e-6
        
        vols = np.zeros_like(K)
        
        # ATM volatility
        if np.any(atm_mask):
            vols[atm_mask] = alpha / (F ** (1 - beta))
        
        # Non-ATM volatility
        if np.any(~atm_mask):
            K_otm = K[~atm_mask]
            z = (nu / alpha) * (F * K_otm) ** ((1 - beta) / 2) * np.log(F / K_otm)
            x_z = np.log((np.sqrt(1 - 2 * rho * z + z**2) + z - rho) / (1 - rho))
            
            numerator = alpha
            denominator = (F * K_otm) ** ((1 - beta) / 2) * (1 + ((1 - beta)**2 / 24) * (np.log(F / K_otm))**2)
            
            vols[~atm_mask] = numerator / denominator * (z / x_z)
        
        return vols
    
    def _fallback_to_flat_vol(self) -> bool:
        """Fallback to flat volatility per expiry"""
        quotes_by_expiry = self._group_by_expiry()
        
        if len(quotes_by_expiry) == 0:
            return False
        
        for expiry, expiry_quotes in quotes_by_expiry.items():
            vols = [q.implied_vol for q in expiry_quotes]
            self.flat_vol_by_expiry[expiry] = np.median(vols)
        
        self.fitted_model = SurfaceModel.FLAT
        return True

    
    def get_vol(self, strike: float, expiry: date) -> float:
        """
        Get implied volatility for given strike and expiry.
        
        Handles extrapolation for missing strikes.
        """
        if self.fitted_model is None:
            logger.warning("Surface not fitted, returning default vol")
            return 0.20  # Default 20% vol
        
        tte = (expiry - datetime.now().date()).days / 365.0
        if tte <= 0:
            return 0.0
        
        if self.fitted_model == SurfaceModel.SVI:
            return self._get_svi_vol(strike, expiry, tte)
        elif self.fitted_model == SurfaceModel.SABR:
            return self._get_sabr_vol(strike, expiry, tte)
        elif self.fitted_model == SurfaceModel.FLAT:
            return self._get_flat_vol(expiry)
        else:
            return 0.20
    
    def _get_svi_vol(self, strike: float, expiry: date, tte: float) -> float:
        """Get volatility from SVI model"""
        if expiry in self.svi_params_by_expiry:
            params = self.svi_params_by_expiry[expiry]
            
            # Convert to log-moneyness
            forward = self.spot_price * np.exp(self.risk_free_rate * tte)
            k = np.log(strike / forward)
            
            # SVI formula for total variance
            w = params.a + params.b * (params.rho * (k - params.m) + 
                                      np.sqrt((k - params.m)**2 + params.sigma**2))
            
            # Convert to volatility
            vol = np.sqrt(max(w / tte, 0.0001))  # Ensure positive
            return float(vol)
        else:
            # Interpolate between expiries
            return self._interpolate_expiry(strike, expiry, tte)
    
    def _get_sabr_vol(self, strike: float, expiry: date, tte: float) -> float:
        """Get volatility from SABR model"""
        if expiry in self.sabr_params_by_expiry:
            params = self.sabr_params_by_expiry[expiry]
            vol = self._sabr_vol(
                np.array([strike]), 
                self.spot_price, 
                tte, 
                params.alpha, 
                params.beta, 
                params.rho, 
                params.nu
            )[0]
            return float(vol)
        else:
            return self._interpolate_expiry(strike, expiry, tte)
    
    def _get_flat_vol(self, expiry: date) -> float:
        """Get flat volatility for expiry"""
        if expiry in self.flat_vol_by_expiry:
            return self.flat_vol_by_expiry[expiry]
        else:
            # Return median of all flat vols
            if len(self.flat_vol_by_expiry) > 0:
                return np.median(list(self.flat_vol_by_expiry.values()))
            return 0.20
    
    def _interpolate_expiry(self, strike: float, expiry: date, tte: float) -> float:
        """Interpolate volatility between expiries"""
        if len(self.svi_params_by_expiry) == 0 and len(self.flat_vol_by_expiry) == 0:
            return 0.20
        
        # Get available expiries
        available_expiries = sorted(list(self.svi_params_by_expiry.keys()) + 
                                   list(self.flat_vol_by_expiry.keys()))
        
        if len(available_expiries) == 0:
            return 0.20
        
        # Find nearest expiries
        expiry_dates = [e for e in available_expiries]
        expiry_tts = [(e - datetime.now().date()).days / 365.0 for e in expiry_dates]
        
        # Linear interpolation
        if tte <= expiry_tts[0]:
            return self.get_vol(strike, expiry_dates[0])
        elif tte >= expiry_tts[-1]:
            return self.get_vol(strike, expiry_dates[-1])
        else:
            # Find bracketing expiries
            for i in range(len(expiry_tts) - 1):
                if expiry_tts[i] <= tte <= expiry_tts[i+1]:
                    vol1 = self.get_vol(strike, expiry_dates[i])
                    vol2 = self.get_vol(strike, expiry_dates[i+1])
                    
                    # Linear interpolation
                    weight = (tte - expiry_tts[i]) / (expiry_tts[i+1] - expiry_tts[i])
                    return vol1 * (1 - weight) + vol2 * weight
        
        return 0.20
    
    def get_variance(self, strike: float, expiry: date) -> float:
        """Get total variance for strike and expiry"""
        vol = self.get_vol(strike, expiry)
        tte = (expiry - datetime.now().date()).days / 365.0
        return vol**2 * tte

    
    def _validate_no_arbitrage(self) -> bool:
        """
        Validate no-arbitrage constraints.
        
        Implements Property 1: No-arbitrage constraints
        - Calendar spreads: longer expiry should have >= variance
        - Butterfly spreads: convexity constraints
        """
        violations = 0
        
        # Check calendar spread arbitrage
        expiries = sorted(self.svi_params_by_expiry.keys())
        
        for i in range(len(expiries) - 1):
            expiry1 = expiries[i]
            expiry2 = expiries[i + 1]
            
            # Sample strikes
            strikes = np.linspace(self.spot_price * 0.8, self.spot_price * 1.2, 10)
            
            for strike in strikes:
                var1 = self.get_variance(strike, expiry1)
                var2 = self.get_variance(strike, expiry2)
                
                # Calendar spread: longer expiry should have more variance
                if var2 < var1:
                    violations += 1
        
        # Check butterfly spread arbitrage
        for expiry in expiries:
            strikes = np.linspace(self.spot_price * 0.8, self.spot_price * 1.2, 20)
            
            for i in range(1, len(strikes) - 1):
                k1, k2, k3 = strikes[i-1], strikes[i], strikes[i+1]
                
                v1 = self.get_vol(k1, expiry)
                v2 = self.get_vol(k2, expiry)
                v3 = self.get_vol(k3, expiry)
                
                # Butterfly: middle strike vol should be between outer strikes
                # (convexity constraint)
                if v2 > max(v1, v3) + 0.05:  # 5% tolerance
                    violations += 1
        
        if self.quality:
            self.quality.arbitrage_violations = violations
        
        return violations < 5  # Allow up to 5 violations
    
    def _compute_quality_metrics(self) -> None:
        """Compute surface quality metrics"""
        if len(self.quotes) == 0:
            return
        
        # Compute fit RMSE
        errors = []
        for quote in self.quotes:
            fitted_vol = self.get_vol(quote.strike, quote.expiry)
            errors.append((quote.implied_vol - fitted_vol)**2)
        
        rmse = np.sqrt(np.mean(errors))
        
        # Compute R-squared
        actual_vols = np.array([q.implied_vol for q in self.quotes])
        fitted_vols = np.array([self.get_vol(q.strike, q.expiry) for q in self.quotes])
        
        ss_res = np.sum((actual_vols - fitted_vols)**2)
        ss_tot = np.sum((actual_vols - np.mean(actual_vols))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        
        # Compute data coverage
        expiries = set(q.expiry for q in self.quotes)
        strikes_per_expiry = {}
        for expiry in expiries:
            strikes_per_expiry[expiry] = len(set(q.strike for q in self.quotes if q.expiry == expiry))
        
        avg_strikes = np.mean(list(strikes_per_expiry.values()))
        coverage = min(1.0, avg_strikes / 20.0)  # Normalize by 20 strikes
        
        self.quality = SurfaceQuality(
            fit_rmse=rmse,
            fit_r_squared=r_squared,
            arbitrage_violations=0,  # Will be set by _validate_no_arbitrage
            data_coverage=coverage,
            extrapolation_quality=0.8,  # Default
            model_type=self.fitted_model,
            timestamp=datetime.now()
        )
    
    def _group_by_expiry(self) -> Dict[date, List[OptionQuote]]:
        """Group quotes by expiry date"""
        quotes_by_expiry = {}
        for quote in self.quotes:
            if quote.expiry not in quotes_by_expiry:
                quotes_by_expiry[quote.expiry] = []
            quotes_by_expiry[quote.expiry].append(quote)
        return quotes_by_expiry
    
    def get_quality_score(self) -> float:
        """Get overall surface quality score (0-1)"""
        if self.quality is None:
            return 0.0
        return self.quality.get_quality_score()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize surface to dictionary"""
        return {
            'underlying': self.underlying,
            'spot_price': self.spot_price,
            'risk_free_rate': self.risk_free_rate,
            'fitted_model': self.fitted_model.value if self.fitted_model else None,
            'num_quotes': len(self.quotes),
            'quality_score': self.get_quality_score(),
            'last_fit_time': self.last_fit_time.isoformat() if self.last_fit_time else None
        }


def create_iv_surface_from_quotes(
    underlying: str,
    spot_price: float,
    quotes: List[OptionQuote],
    risk_free_rate: float = 0.05,
    model: SurfaceModel = SurfaceModel.SVI
) -> IVSurface:
    """
    Create and fit IV surface from option quotes.
    
    Convenience function for surface creation.
    """
    surface = IVSurface(underlying, spot_price, risk_free_rate)
    surface.add_quotes(quotes)
    surface.fit_surface(model)
    return surface
