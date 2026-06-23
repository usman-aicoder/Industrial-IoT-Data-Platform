"""
Anomaly detection and statistical analysis for time-series tag data.

Methods
-------
zscore       — fast, no extra dependencies, good for Gaussian distributions
isolation_forest — sklearn, handles non-Gaussian and multi-modal data well
combined     — union of both methods (higher recall, some extra false positives)
"""

from typing import Dict, Optional
import numpy as np
import pandas as pd


# ------------------------------------------------------------------
# Core detection
# ------------------------------------------------------------------

def detect_anomalies(
    df: pd.DataFrame,
    value_col: str = "value",
    method: str = "zscore",
    zscore_threshold: float = 2.5,
    contamination: float = 0.05,
) -> pd.DataFrame:
    """
    Return df with added columns:
      is_anomaly  — bool
      z_score     — absolute Z-score (always computed, useful as hover info)
      anomaly_score — IsolationForest score (only when method uses IF)
    """
    if df.empty:
        df = df.copy()
        df["is_anomaly"] = False
        df["z_score"] = np.nan
        return df

    result = df.copy()
    values = result[value_col].astype(float).to_numpy()

    # Z-score is always computed (cheap, useful for display)
    mean, std = np.mean(values), np.std(values)
    std = std if std > 0 else 1.0
    result["z_score"] = np.abs((values - mean) / std)

    if method == "zscore":
        result["is_anomaly"] = result["z_score"] > zscore_threshold

    elif method == "isolation_forest":
        result["is_anomaly"] = False
        if len(values) >= 10:
            try:
                from sklearn.ensemble import IsolationForest
                model = IsolationForest(
                    contamination=contamination, random_state=42, n_estimators=100
                )
                X = values.reshape(-1, 1)
                preds = model.fit_predict(X)
                result["anomaly_score"] = -model.score_samples(X)
                result["is_anomaly"] = preds == -1
            except ImportError:
                # Fall back to Z-score if sklearn not available
                result["is_anomaly"] = result["z_score"] > zscore_threshold

    elif method == "combined":
        z_flags = result["z_score"] > zscore_threshold
        if_flags = pd.Series(False, index=result.index)
        if len(values) >= 10:
            try:
                from sklearn.ensemble import IsolationForest
                model = IsolationForest(
                    contamination=contamination, random_state=42, n_estimators=100
                )
                if_flags = pd.Series(
                    model.fit_predict(values.reshape(-1, 1)) == -1,
                    index=result.index,
                )
                result["anomaly_score"] = -model.score_samples(values.reshape(-1, 1))
            except ImportError:
                pass
        result["is_anomaly"] = z_flags | if_flags

    return result


# ------------------------------------------------------------------
# Statistics
# ------------------------------------------------------------------

def compute_statistics(df: pd.DataFrame, value_col: str = "value") -> Dict:
    """Descriptive statistics for one tag's series."""
    vals = df[value_col].dropna().astype(float)
    if vals.empty:
        return {}
    return {
        "Count": int(len(vals)),
        "Mean": round(float(vals.mean()), 4),
        "Std Dev": round(float(vals.std()), 4),
        "Min": round(float(vals.min()), 4),
        "P25": round(float(vals.quantile(0.25)), 4),
        "Median": round(float(vals.median()), 4),
        "P75": round(float(vals.quantile(0.75)), 4),
        "P95": round(float(vals.quantile(0.95)), 4),
        "Max": round(float(vals.max()), 4),
    }


def build_stats_table(tag_data: Dict[str, pd.DataFrame], value_col: str = "value") -> pd.DataFrame:
    """
    Build a single stats DataFrame with metrics as rows and tag names as columns.
    tag_data: {display_name: dataframe}
    """
    rows = {}
    for name, df in tag_data.items():
        stats = compute_statistics(df, value_col)
        for metric, val in stats.items():
            if metric not in rows:
                rows[metric] = {}
            rows[metric][name] = val

    return pd.DataFrame(rows).T  # metrics as rows, tags as columns
