"""Stable reference-bin PSI and held-out permutation explanations."""
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance


def population_stability_index(reference, current, bins=10):
    reference = pd.Series(reference).dropna()
    current = pd.Series(current).dropna()
    if len(reference) == 0 or len(current) == 0:
        return None
    if pd.api.types.is_numeric_dtype(reference):
        inner = np.unique(np.quantile(reference.astype(float), np.linspace(0, 1, bins + 1)))[1:-1]
        if reference.nunique() == 1:
            value=float(reference.iloc[0]);epsilon=max(abs(value)*1e-6,1e-6)
            inner=np.array([value-epsilon,value+epsilon])
        edges = np.r_[-np.inf, inner, np.inf]
        a = np.histogram(reference.astype(float), edges)[0]
        b = np.histogram(current.astype(float), edges)[0]
    else:
        categories = sorted(set(reference.astype(str)) | set(current.astype(str)))
        a = reference.astype(str).value_counts().reindex(categories, fill_value=0).to_numpy()
        b = current.astype(str).value_counts().reindex(categories, fill_value=0).to_numpy()
    a = (a + 0.5) / (a.sum() + 0.5 * len(a))
    b = (b + 0.5) / (b.sum() + 0.5 * len(b))
    return float(np.sum((b-a) * np.log(b/a)))


def drift_report(reference, current, threshold=0.2):
    result = []
    for col in reference:
        psi = population_stability_index(reference[col], current[col])
        result.append(dict(feature=col, psi=psi, threshold=threshold,
                           status="insufficient_data" if psi is None else
                           "alert" if psi >= threshold else "ok",
                           reference_missing_rate=float(reference[col].isna().mean()),
                           current_missing_rate=float(current[col].isna().mean())))
    return result


def explain(pipeline, X, y, scoring, seed=42):
    result = permutation_importance(pipeline, X, y, scoring=scoring,
                                    n_repeats=5, random_state=seed, n_jobs=1)
    return [dict(feature=col, importance=float(mean), std=float(std))
            for col, mean, std in zip(X.columns, result.importances_mean,
                                      result.importances_std)]


def local_explanations(pipeline, X, reference, classification=False, limit=50):
    """One-at-a-time reference substitutions; not SHAP or causal effects.

    Return observed prediction minus prediction with one feature replaced.
    Individual deltas need not add to the prediction. Stable sign across two
    training-reference windows is included, rather than asserted.
    """
    def predict(frame):
        return pipeline.predict_proba(frame)[:, 1] if classification else pipeline.predict(frame)
    frames = [reference.iloc[:len(reference)//2], reference.iloc[len(reference)//2:]]
    output = []
    for idx, row in X.head(limit).iterrows():
        frame = row.to_frame().T
        actual = float(predict(frame)[0])
        for col in X:
            deltas = []
            for ref in frames:
                values = ref[col].dropna()
                value = values.median() if pd.api.types.is_numeric_dtype(values) else values.mode().iloc[0]
                changed = frame.copy(); changed[col] = value
                deltas.append(actual-float(predict(changed)[0]))
            output.append(dict(row_id=str(idx), feature=col, prediction=actual,
                               reference_delta=deltas[0],
                               stable_direction=bool(np.sign(deltas[0]) == np.sign(deltas[1]))))
    return output
