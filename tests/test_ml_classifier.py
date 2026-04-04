from __future__ import annotations

import pandas as pd
import pytest

from asteroid_cost_atlas.scoring.ml_classifier import (
    CLASSES,
    add_ml_predictions,
    predict_probabilities,
    train_classifier,
)


def _training_df() -> pd.DataFrame:
    """Build a minimal dataset with known taxonomy for training."""
    import numpy as np

    rng = np.random.RandomState(42)
    n = 500
    classes = rng.choice(["C", "S", "M", "V"], n, p=[0.3, 0.4, 0.1, 0.2])

    # Simulate features correlated with class
    albedo = {
        "C": (0.06, 0.02), "S": (0.25, 0.05),
        "M": (0.14, 0.03), "V": (0.35, 0.08),
    }
    df = pd.DataFrame({
        "spkid": range(20000001, 20000001 + n),
        "taxonomy": classes,
        "albedo": [rng.normal(*albedo[c]) for c in classes],
        "abs_magnitude": rng.normal(12, 3, n),
        "a_au": rng.uniform(1.5, 3.5, n),
        "eccentricity": rng.uniform(0.01, 0.3, n),
        "inclination_deg": rng.uniform(0, 30, n),
    })
    return df


class TestTrainClassifier:
    def test_trains_successfully(self) -> None:
        model, features = train_classifier(_training_df())
        assert model is not None
        assert len(features) >= 3

    def test_too_few_samples_raises(self) -> None:
        df = _training_df().head(10)
        with pytest.raises(ValueError, match="Too few"):
            train_classifier(df)


class TestPredictProbabilities:
    def test_output_shape(self) -> None:
        df = _training_df()
        model, features = train_classifier(df)
        preds = predict_probabilities(model, df, features)
        assert len(preds) == len(df)
        for c in CLASSES:
            assert f"ml_prob_{c}" in preds.columns

    def test_probs_sum_to_one(self) -> None:
        df = _training_df()
        model, features = train_classifier(df)
        preds = predict_probabilities(model, df, features)
        row_sums = sum(preds[f"ml_prob_{c}"] for c in CLASSES)
        assert (abs(row_sums - 1.0) < 0.01).all()


class TestAddMlPredictions:
    def test_adds_columns(self) -> None:
        df = _training_df()
        result = add_ml_predictions(df)
        for c in CLASSES:
            assert f"ml_prob_{c}" in result.columns
        assert "ml_confidence" in result.columns

    def test_confidence_in_range(self) -> None:
        df = _training_df()
        result = add_ml_predictions(df)
        assert (result["ml_confidence"] >= 0).all()
        assert (result["ml_confidence"] <= 1).all()

    def test_does_not_mutate_input(self) -> None:
        df = _training_df()
        _ = add_ml_predictions(df)
        assert "ml_prob_C" not in df.columns
