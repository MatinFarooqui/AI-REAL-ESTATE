"""RealtyKey AI valuation engine.

Uses the trained scikit-learn model when available, then stabilizes the model
prediction with train-set geographic benchmark rates. Geographic fallback is:
Locality -> City -> State/Regional -> National baseline.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "ml" / "real_estate_price_model_v6.pkl"
FALLBACK_MODEL_PATH = BASE_DIR / "ml" / "real_estate_price_model_v2.pkl"
_BUNDLE = None


def load_valuation_bundle():
    global _BUNDLE
    if _BUNDLE is not None:
        return _BUNDLE

    for path in (MODEL_PATH, FALLBACK_MODEL_PATH):
        if not path.exists():
            continue
        try:
            loaded = joblib.load(path)
            if isinstance(loaded, dict):
                bundle = loaded
            else:
                bundle = {"version": "legacy_pipeline", "pipeline": loaded, "benchmarks": {}}
            bundle.setdefault("benchmarks", {})
            if path == FALLBACK_MODEL_PATH and "metrics" not in bundle:
                bundle["metrics"] = {
                    "mae": 4487337.0,
                    "rmse": 11303007.0,
                    "r2": 0.4569,
                    "med_ape": 28.8,
                    "within_10_pct": 20.5,
                    "within_20_pct": 37.2,
                }
            _BUNDLE = bundle
            print(f"Loaded valuation model bundle: {path.name}")
            return _BUNDLE
        except Exception as error:
            print(f"Error loading valuation bundle {path.name}: {error}")

    return None


def get_model_metrics() -> Dict[str, Any]:
    bundle = load_valuation_bundle()
    if not bundle:
        return {
            "available": False,
            "message": "No trained valuation model bundle found.",
            "mae": None,
            "rmse": None,
            "r2": None,
            "r2_score": None,
            "med_ape": None,
            "median_ape": None,
            "within_10_pct": None,
            "within_20_pct": None,
        }
    raw = dict(bundle.get("metrics") or {})
    r2 = raw.get("r2_score", raw.get("r2"))
    med_ape = raw.get("median_ape", raw.get("med_ape"))
    result = {
        **raw,
        "available": True,
        "r2": r2,
        "r2_score": r2,
        "med_ape": med_ape,
        "median_ape": med_ape,
    }
    return result


def _lookup_stat(mapping, key, fallback=0.0):
    value = mapping.get(key)
    if isinstance(value, dict):
        return value
    return fallback


def _resolve_benchmark(benchmarks, city, locality, state):
    locality_rates = benchmarks.get("locality_rates") or {}
    city_rates = benchmarks.get("city_rates") or {}
    state_rates = benchmarks.get("state_rates") or {}
    overall = float(benchmarks.get("overall_rate") or 6000.0)

    loc_key = (city.lower(), locality.lower())
    city_key = city.lower()
    state_key = state.lower()

    loc_stat = locality_rates.get(loc_key) or locality_rates.get((city.capitalize(), locality.capitalize()))
    if isinstance(loc_stat, dict) and int(loc_stat.get("count", 0)) >= 2:
        return float(loc_stat.get("median_rate") or overall), "locality", int(loc_stat.get("count") or 0), loc_stat

    city_stat = city_rates.get(city_key)
    if isinstance(city_stat, dict) and int(city_stat.get("count", 0)) >= 3:
        return float(city_stat.get("median_rate") or overall), "city_fallback", int(city_stat.get("count") or 0), city_stat

    state_stat = state_rates.get(state_key)
    if isinstance(state_stat, dict) and int(state_stat.get("count", 0)) >= 5:
        return float(state_stat.get("median_rate") or overall), "state_fallback", int(state_stat.get("count") or 0), state_stat

    return overall, "national_baseline", 0, {"median_rate": overall, "count": 0}


def _model_predict_price(bundle, city, locality, property_type, area, bhk, bathrooms, balcony):
    input_df = pd.DataFrame([{
        "city": city,
        "locality": locality,
        "property_type": property_type,
        "bhk": float(bhk),
        "area_sqft": float(area),
        "bathrooms": float(bathrooms),
        "balcony": float(balcony),
    }])

    if "model" in bundle and "preprocessor" in bundle:
        X = bundle["preprocessor"].transform(input_df)
        return float(bundle["model"].predict(X)[0])
    if "pipeline" in bundle:
        return float(bundle["pipeline"].predict(input_df)[0])
    raise RuntimeError("Valuation model format is not supported.")


def _confidence(level, count, metrics):
    med_ape = metrics.get("median_ape")
    r2 = metrics.get("r2_score")

    if level == "locality":
        if count >= 10 and med_ape is not None and med_ape <= 25 and (r2 is None or r2 >= 0.45):
            return "High"
        return "Moderate"
    if level == "city_fallback":
        return "Moderate" if count >= 20 else "Fair"
    if level == "state_fallback":
        return "Fair"
    return "Broader"


def _interval_pct(level, metrics):
    # Intervals are deliberately derived from measured model error where available,
    # not presented as a confidence interval in a statistical sense.
    med_ape = float(metrics.get("median_ape") or 28.0)
    base = max(0.15, min(0.34, (med_ape / 100.0) * 1.15))
    adjustment = {
        "locality": -0.03,
        "city_fallback": 0.00,
        "state_fallback": 0.04,
        "national_baseline": 0.08,
    }.get(level, 0.0)
    return max(0.12, min(0.38, base + adjustment))


def estimate_property_value(
    city: str,
    locality: str,
    property_type: str,
    area_sqft: float,
    bhk: Optional[float] = None,
    bathrooms: Optional[float] = None,
    balcony: Optional[float] = None,
    asking_price: Optional[float] = None,
    state: Optional[str] = None,
) -> Dict[str, Any]:
    bundle = load_valuation_bundle()
    if not bundle:
        raise RuntimeError("AI valuation model is currently not available. Train the model with ml/train_model_v6.py first.")

    city = str(city or "").strip()
    locality = str(locality or "").strip()
    property_type = str(property_type or "Apartment").strip().title()
    area = float(area_sqft or 0)
    bhk_value = float(bhk if bhk is not None else (0 if property_type == "Plot" else 2))
    bathroom_value = float(bathrooms if bathrooms is not None else (0 if property_type == "Plot" else max(1, round(bhk_value))))
    balcony_value = float(balcony if balcony is not None else (0 if property_type == "Plot" else 1))
    if area <= 0:
        raise ValueError("Property area must be greater than 0.")
    if not city:
        raise ValueError("City is required.")
    if not locality:
        raise ValueError("Locality is required.")

    city_state = {
        "pune": "Maharashtra",
        "mumbai": "Maharashtra",
        "thane": "Maharashtra",
        "aurangabad": "Maharashtra",
        "chhatrapati sambhajinagar": "Maharashtra",
        "nashik": "Maharashtra",
        "nagpur": "Maharashtra",
        "parbhani": "Maharashtra",
        "bangalore": "Karnataka",
        "bengaluru": "Karnataka",
        "new delhi": "Delhi",
        "delhi": "Delhi",
        "chennai": "Tamil Nadu",
        "kolkata": "West Bengal",
        "hyderabad": "Telangana",
    }
    resolved_state = str(state or "").strip() or city_state.get(city.lower(), "Other")

    benchmarks = bundle.get("benchmarks") or {}
    benchmark_rate, level, sample_count, stat = _resolve_benchmark(benchmarks, city, locality, resolved_state)
    metrics = get_model_metrics()

    model_price = None
    try:
        model_price = _model_predict_price(bundle, city, locality, property_type, area, bhk_value, bathroom_value, balcony_value)
    except Exception as error:
        print("Model prediction warning:", error)

    benchmark_price = benchmark_rate * area
    if model_price is None or model_price <= 0:
        estimated_price = benchmark_price
        model_source = "geographic benchmark"
    else:
        blend = {
            "locality": 0.70,
            "city_fallback": 0.55,
            "state_fallback": 0.35,
            "national_baseline": 0.20,
        }.get(level, 0.20)
        estimated_price = (blend * model_price) + ((1.0 - blend) * benchmark_price)
        model_source = "ML model + geographic benchmark"

    if property_type in {"House", "Villa"}:
        # Keep the adjustment modest; geographic price rates remain the dominant signal.
        estimated_price *= 1.02
    elif property_type == "Plot":
        estimated_price *= 0.98

    estimated_price = max(100000.0, float(estimated_price))
    rate_per_sqft = round(estimated_price / area)
    interval_pct = _interval_pct(level, metrics)
    lower = max(50000.0, round(estimated_price * (1 - interval_pct)))
    upper = round(estimated_price * (1 + interval_pct))

    confidence = _confidence(level, sample_count, metrics)
    source_reason = {
        "locality": f"Direct locality benchmark available for {locality}, {city} ({sample_count:,} training records).",
        "city_fallback": f"The locality is not sufficiently represented, so the estimate uses {city} city-level market data ({sample_count:,} records).",
        "state_fallback": f"The city/locality is outside strong model coverage, so the estimate uses {resolved_state} regional data.",
        "national_baseline": "The requested location has limited benchmark coverage, so a broader national baseline is used.",
    }[level]

    factors = [
        f"Location: {locality}, {city}, {resolved_state}",
        f"Property type: {property_type}",
        f"Area: {area:,.0f} sq ft",
    ]
    if property_type != "Plot":
        factors.append(f"Configuration: {int(bhk_value)} BHK / {int(bathroom_value)} bathrooms")

    result = {
        "success": True,
        "estimated_price": round(estimated_price),
        "rate_per_sqft": rate_per_sqft,
        "price_range": {"lower": lower, "upper": upper},
        "lower_price": lower,
        "upper_price": upper,
        "confidence_level": confidence,
        "fallback_level": level,
        "benchmark_rate_per_sqft": round(benchmark_rate),
        "benchmark_sample_count": sample_count,
        "coverage_explanation": source_reason,
        "why_estimate": f"The estimate combines {model_source} using the available geographic coverage. The range reflects measured model error and the fallback level; it is not a guarantee.",
        "factors": factors,
        "model_metrics": metrics,
        "model_source": model_source,
        "model_price": round(model_price) if model_price is not None and model_price > 0 else None,
        "model_rate_per_sqft": round(model_price / area, 2) if model_price is not None and model_price > 0 else None,
        "model_weight": round(blend, 3) if model_price is not None and model_price > 0 else 0.0,
        "benchmark_price": round(benchmark_price),
        "benchmark_rate_per_sqft": round(benchmark_rate),
        "benchmark_sample_count": sample_count,
        "valuation_basis": f"{model_source}; benchmark ₹{benchmark_rate:,.0f}/sq ft across {sample_count:,} records at the selected geographic level.",
        "interval_percent": round(interval_pct * 100, 1),
    }

    if asking_price is not None and float(asking_price) > 0:
        asking = float(asking_price)
        result["asking_price"] = round(asking)
        delta = asking - estimated_price
        delta_pct = round((delta / estimated_price) * 100, 1)
        if asking > upper:
            status = "Above estimated range"
            badge = "high"
        elif asking < lower:
            status = "Below estimated range"
            badge = "low"
        else:
            status = "Within estimated range"
            badge = "fair"
        result["asking_vs_estimate_percent"] = delta_pct
        result["anomaly"] = {
            "status": status,
            "badge": badge,
            "diff_inr": round(delta),
            "diff_pct": delta_pct,
            "message": f"Asking price is {abs(delta_pct):0.1f}% {'above' if delta_pct >= 0 else 'below'} the model estimate and is {status.lower()}.",
        }

    return result
