from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from app.config import AIR_QUALITY


@dataclass
class RelativeAirQualityResult:
    score_pct: float
    label: str
    ready: bool
    gas_baseline_kohms: Optional[float]
    humidity_baseline_pct: float
    samples: int
    gas_score_pct: float
    humidity_score_pct: float

    def as_payload(self) -> Dict[str, object]:
        return {
            "air_quality_relative_pct": round(self.score_pct, 1),
            "air_quality_relative_label": self.label,
            "air_quality_relative_ready": self.ready,
            "air_quality_relative_baseline_kohms": (
                round(self.gas_baseline_kohms, 3) if self.gas_baseline_kohms is not None else None
            ),
            "air_quality_relative_samples": self.samples,
            "air_quality_relative_gas_score_pct": round(self.gas_score_pct, 1),
            "air_quality_relative_humidity_score_pct": round(self.humidity_score_pct, 1),
        }


class RelativeAirQualityEstimator:
    def __init__(
        self,
        state_path: str | Path,
        burn_in_samples: int,
        baseline_window: int,
        humidity_baseline_pct: float,
        humidity_weighting: float,
        baseline_adaptation_rate: float,
        score_smoothing: float,
    ) -> None:
        self.state_path = Path(state_path)
        self.burn_in_samples = max(1, burn_in_samples)
        self.baseline_window = max(1, baseline_window)
        self.humidity_baseline_pct = humidity_baseline_pct
        self.humidity_weighting = min(max(humidity_weighting, 0.0), 1.0)
        self.baseline_adaptation_rate = min(max(baseline_adaptation_rate, 0.0), 1.0)
        self.score_smoothing = min(max(score_smoothing, 0.0), 1.0)
        self._state = self._load_state()

    def enrich_payload(self, payload: Dict[str, object]) -> Dict[str, object]:
        gas_kohms = self._coerce_float(payload.get("gas_kohms"))
        humidity_pct = self._coerce_float(payload.get("humidity_pct"))
        if gas_kohms is None or humidity_pct is None:
            return payload

        result = self.update(gas_kohms=gas_kohms, humidity_pct=humidity_pct)
        enriched = dict(payload)
        enriched.update(result.as_payload())
        return enriched

    def update(self, gas_kohms: float, humidity_pct: float) -> RelativeAirQualityResult:
        gas_samples = self._state.setdefault("gas_samples_kohms", [])
        gas_samples.append(gas_kohms)
        if len(gas_samples) > self.baseline_window:
            del gas_samples[:-self.baseline_window]

        if self._state.get("gas_baseline_kohms") is None and len(gas_samples) >= self.burn_in_samples:
            recent = gas_samples[-self.baseline_window :]
            self._state["gas_baseline_kohms"] = sum(recent) / len(recent)

        gas_baseline = self._state.get("gas_baseline_kohms")
        humidity_score = self._humidity_score(humidity_pct)
        gas_score = 0.0
        ready = gas_baseline is not None

        if gas_baseline is not None and gas_baseline > 0:
            ratio = gas_kohms / gas_baseline
            gas_score = min(max(ratio, 0.0), 1.2) / 1.2
            gas_score *= (1.0 - self.humidity_weighting) * 100.0
            if gas_kohms > gas_baseline:
                self._state["gas_baseline_kohms"] = self._blend(
                    gas_baseline,
                    gas_kohms,
                    self.baseline_adaptation_rate,
                )
                gas_baseline = self._state["gas_baseline_kohms"]

        raw_score = humidity_score + gas_score
        previous_score = self._state.get("smoothed_score_pct")
        smoothed_score = raw_score if previous_score is None else self._blend(
            previous_score,
            raw_score,
            self.score_smoothing,
        )
        smoothed_score = min(max(smoothed_score, 0.0), 100.0)
        self._state["smoothed_score_pct"] = smoothed_score
        self._save_state()

        return RelativeAirQualityResult(
            score_pct=smoothed_score,
            label=self._score_label(smoothed_score, ready=ready),
            ready=ready,
            gas_baseline_kohms=gas_baseline,
            humidity_baseline_pct=self.humidity_baseline_pct,
            samples=len(gas_samples),
            gas_score_pct=gas_score,
            humidity_score_pct=humidity_score,
        )

    def _humidity_score(self, humidity_pct: float) -> float:
        baseline = self.humidity_baseline_pct
        weighting = self.humidity_weighting * 100.0
        if humidity_pct >= baseline:
            span = max(1.0, 100.0 - baseline)
            normalized = max(0.0, (100.0 - humidity_pct) / span)
        else:
            span = max(1.0, baseline)
            normalized = max(0.0, humidity_pct / span)
        return normalized * weighting

    @staticmethod
    def _blend(previous: float, current: float, rate: float) -> float:
        return (previous * (1.0 - rate)) + (current * rate)

    def _score_label(self, score_pct: float, ready: bool) -> str:
        if not ready:
            return "Apprentissage"
        if score_pct >= 80:
            return "Bon"
        if score_pct >= 60:
            return "Correct"
        if score_pct >= 40:
            return "Moyen"
        return "Degrade"

    def _load_state(self) -> Dict[str, object]:
        if not self.state_path.exists():
            return {}
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            return state if isinstance(state, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self._state, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _coerce_float(value: object) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


air_quality_estimator = RelativeAirQualityEstimator(
    state_path=AIR_QUALITY["state_path"],
    burn_in_samples=AIR_QUALITY["burn_in_samples"],
    baseline_window=AIR_QUALITY["baseline_window"],
    humidity_baseline_pct=AIR_QUALITY["humidity_baseline_pct"],
    humidity_weighting=AIR_QUALITY["humidity_weighting"],
    baseline_adaptation_rate=AIR_QUALITY["baseline_adaptation_rate"],
    score_smoothing=AIR_QUALITY["score_smoothing"],
)
