"""
Machine-learning composition classifier.

Trains a random forest on spectroscopically confirmed asteroids and
predicts class probabilities for unlabeled objects.  The output feeds
the Bayesian composition model as an additional evidence layer.

Training set: asteroids with known taxonomy (~30K from LCDB/SBDB).
Features: albedo, abs_magnitude, a_au, eccentricity, inclination_deg,
          SDSS color_gr/color_ri, MOVIS movis_yj/movis_jks.
Target: composition class (C/S/M/V).

The classifier outputs vote-fraction probabilities per class which are
more nuanced than the rule-based Gaussian likelihoods in the Bayesian
model, especially for edge cases in the overlapping feature space.

References
----------
Penttila et al. (2021), A&A 649 — ~80% accuracy with random forest
Mahlke et al. (2022), A&A 665 — Gaussian mixture probabilistic taxonomy
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Features used for classification (must be numeric, present in enriched data)
FEATURE_COLS = [
    "albedo",
    "abs_magnitude",
    "a_au",
    "eccentricity",
    "inclination_deg",
    "color_gr",
    "color_ri",
    "movis_yj",
    "movis_jks",
]

CLASSES = ["C", "S", "M", "V"]


def _classify_taxonomy_simple(tax: str) -> str:
    """Map taxonomy to C/S/M/V or empty string (skip)."""
    from asteroid_cost_atlas.scoring.composition import classify_taxonomy

    c = classify_taxonomy(tax)
    return c if c in CLASSES else ""


def train_classifier(
    df: pd.DataFrame,
) -> tuple[Any, list[str]]:
    """
    Train a random forest on asteroids with known taxonomy.

    Returns (fitted_model, feature_names_used).
    Only uses rows with known taxonomy and at least 3 non-null features.
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline

    # Build training set: rows with known taxonomy
    if "taxonomy" not in df.columns:
        raise ValueError("DataFrame must have 'taxonomy' column for training")

    df_train = df.copy()
    df_train["_label"] = df_train["taxonomy"].apply(
        lambda t: _classify_taxonomy_simple(str(t)) if pd.notna(t) else ""
    )
    df_train = df_train[df_train["_label"].isin(CLASSES)]

    # Select features that exist
    available_features = [c for c in FEATURE_COLS if c in df.columns]
    if len(available_features) < 3:
        raise ValueError(
            f"Need at least 3 features, only found: {available_features}"
        )

    # Require at least 3 non-null features per row
    feature_data = df_train[available_features]
    enough_data = feature_data.notna().sum(axis=1) >= 3
    df_train = df_train[enough_data]

    if len(df_train) < 100:
        raise ValueError(
            f"Too few training samples: {len(df_train)} (need >= 100)"
        )

    x_train = df_train[available_features].to_numpy(dtype=float)
    y_train = df_train["_label"].values

    logger.info(
        "Training RF on %d samples, %d features: %s",
        len(x_train),
        len(available_features),
        available_features,
    )

    # Pipeline: impute NaN → random forest
    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("rf", RandomForestClassifier(
            n_estimators=200,
            max_depth=15,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )),
    ])
    model.fit(x_train, y_train)

    # Log class distribution
    from collections import Counter

    dist = Counter(y_train)
    logger.info("Training set: %s", dict(dist))

    # Log accuracy on training set
    train_acc = model.score(x_train, y_train)
    logger.info("Training accuracy: %.1f%%", train_acc * 100)

    return model, available_features


def predict_probabilities(
    model: Any,
    df: pd.DataFrame,
    feature_names: list[str],
) -> pd.DataFrame:
    """
    Predict class probabilities for all rows in df.

    Returns DataFrame with columns: ml_prob_C, ml_prob_S, ml_prob_M, ml_prob_V.
    Rows with insufficient features get uniform probabilities (0.25 each).
    """
    n = len(df)

    # Extract features
    available = [c for c in feature_names if c in df.columns]
    if not available:
        # No features at all — return uniform
        result = pd.DataFrame(index=df.index)
        for c in CLASSES:
            result[f"ml_prob_{c}"] = 0.25
        return result

    x_all = df[available].to_numpy(dtype=float)

    # Rows with at least 3 non-null features get predictions
    enough = np.sum(np.isfinite(x_all), axis=1) >= 3

    # Initialize uniform
    probs = np.full((n, len(CLASSES)), 0.25)

    if enough.sum() > 0:
        x_valid = x_all[enough]
        pred_probs = model.predict_proba(x_valid)

        # Map model classes to our CLASSES order
        model_classes = list(model.classes_)
        for i, c in enumerate(CLASSES):
            if c in model_classes:
                j = model_classes.index(c)
                probs[enough, i] = pred_probs[:, j]
            # else stays at 0.25

    result = pd.DataFrame(index=df.index)
    for i, c in enumerate(CLASSES):
        result[f"ml_prob_{c}"] = probs[:, i]

    return result


def add_ml_predictions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Train ML classifier on known-taxonomy rows, predict for all rows.

    Adds columns: ml_prob_C, ml_prob_S, ml_prob_M, ml_prob_V, ml_confidence.
    """
    try:
        model, features = train_classifier(df)
        preds = predict_probabilities(model, df, features)
    except (ValueError, ImportError) as e:
        logger.warning("ML classifier failed: %s — using uniform probs", e)
        preds = pd.DataFrame(index=df.index)
        for c in CLASSES:
            preds[f"ml_prob_{c}"] = 0.25

    result = df.copy()
    for c in CLASSES:
        result[f"ml_prob_{c}"] = preds[f"ml_prob_{c}"].values

    # ML confidence: 1 - normalized entropy
    import math

    max_entropy = math.log(len(CLASSES))
    ml_conf = np.zeros(len(df))
    for i in range(len(df)):
        probs_i = [result.iloc[i][f"ml_prob_{c}"] for c in CLASSES]
        entropy = -sum(p * math.log(p) for p in probs_i if p > 1e-12)
        ml_conf[i] = 1.0 - entropy / max_entropy
    result["ml_confidence"] = np.round(ml_conf, 4)

    return result
