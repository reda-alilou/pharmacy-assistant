from __future__ import annotations

from collections.abc import Mapping
from time import perf_counter

from rapidfuzz import fuzz, process

from .catalog import Catalog
from .config import DEFAULT_WEIGHTS, MATCH_FIELDS, ScoringMode
from .logging_config import get_logger
from .models import MatchResult
from .normalization import extract_dosage_terms, normalize_text

logger = get_logger("matching")


class FuzzyMatcher:
    def __init__(
        self,
        weights: Mapping[str, float] | None = None,
        mode: ScoringMode = "field_aware",
    ) -> None:
        if mode not in ("field_aware", "baseline"):
            raise ValueError(f"Unsupported scoring mode: {mode!r}")

        source_weights = weights or DEFAULT_WEIGHTS
        self.weights = {
            field: max(0.0, float(source_weights.get(field, 0.0)))
            for field in MATCH_FIELDS
        }
        if sum(self.weights.values()) <= 0:
            raise ValueError("At least one matching weight must be positive.")
        self.mode = mode

    def rank(
        self,
        query: str,
        catalog: Catalog,
        top_k: int = 5,
        min_score: float = 0.0,
        group_presentations: bool = True,
    ) -> tuple[MatchResult, ...]:
        started = perf_counter()
        logger.info(
            "Ranking started: mode=%s top_k=%d min_score=%.1f "
            "grouped=%s catalog=%d query=%r",
            self.mode,
            top_k,
            min_score,
            group_presentations,
            catalog.size,
            query,
        )
        normalized_query = normalize_text(query)
        if not normalized_query or catalog.size == 0:
            logger.warning(
                "Ranking skipped: empty query or catalogue (query=%r)",
                query,
            )
            return ()

        field_scores = self._score_fields(
            normalized_query,
            catalog,
            extract_dosage_terms(query),
        )
        if not field_scores:
            logger.warning("Ranking skipped: no scoreable fields")
            return ()

        total_weight = sum(
            self.weights[field] for field in field_scores
        )
        if total_weight <= 0:
            logger.warning("Ranking skipped: total field weight is zero")
            return ()

        combined = [0.0] * catalog.size
        for field, scores in field_scores.items():
            weight = self.weights[field]
            for index, score in enumerate(scores):
                combined[index] += float(score) * weight
        combined = [score / total_weight for score in combined]

        order = sorted(
            range(catalog.size),
            key=lambda index: combined[index],
            reverse=True,
        )
        logger.debug(
            "Ranked %d candidates across fields %s",
            catalog.size,
            ",".join(field_scores),
        )

        if group_presentations:
            results = self._grouped_results(
                order,
                combined,
                field_scores,
                catalog,
                top_k,
                min_score,
            )
        else:
            results = self._record_results(
                order,
                combined,
                field_scores,
                catalog,
                top_k,
                min_score,
            )

        elapsed_ms = (perf_counter() - started) * 1000
        if results:
            best = results[0]
            logger.info(
                "Ranking finished: %d result(s), best=%r score=%.1f, "
                "%.0f ms",
                len(results),
                best.record.brand_name,
                best.score,
                elapsed_ms,
            )
        else:
            logger.info(
                "Ranking finished: no matches above min_score, %.0f ms",
                elapsed_ms,
            )
        return results

    def _score_fields(
        self,
        query: str,
        catalog: Catalog,
        query_dosage_terms: frozenset[str],
    ) -> dict[str, list[float]]:
        if self.mode == "baseline":
            return {
                field: self._score_field(
                    query, catalog.field_values(field), fuzz.partial_ratio
                )
                for field in MATCH_FIELDS
            }

        query_tokens = set(query.split())
        field_scores: dict[str, list[float]] = {}

        brand_values = catalog.field_values("brand_name")
        brand_scores = self._score_field(
            query, brand_values, fuzz.token_set_ratio
        )
        brand_partial = self._score_field(
            query, brand_values, fuzz.partial_ratio
        )
        brand_scores = [
            max(token_score, partial_score)
            for token_score, partial_score in zip(
                brand_scores, brand_partial, strict=False
            )
        ]
        self._apply_exact_token_boost(
            brand_scores, brand_values, query_tokens
        )
        field_scores["brand_name"] = brand_scores

        for field in ("active_substance", "epi", "form", "presentation"):
            scores = self._score_field(
                query, catalog.field_values(field), fuzz.token_set_ratio
            )
            if field == "active_substance":
                self._apply_exact_token_boost(
                    scores, catalog.field_values(field), query_tokens
                )
            field_scores[field] = scores

        if query_dosage_terms:
            field_scores["dosage"] = [
                self._score_dosage(query_dosage_terms, record_terms)
                for record_terms in catalog.dosage_terms
            ]

        return field_scores

    @staticmethod
    def _score_field(query: str, values: tuple[str, ...], scorer) -> list[float]:
        if not values:
            return []
        return process.cdist(
            [query],
            values,
            scorer=scorer,
            workers=-1,
        )[0].tolist()

    @staticmethod
    def _apply_exact_token_boost(
        scores: list[float],
        values: tuple[str, ...],
        query_tokens: set[str],
    ) -> None:
        for index, value in enumerate(values):
            if len(value) < 3:
                continue
            value_tokens = set(value.split())
            if not value_tokens:
                continue
            if any(len(token) < 2 for token in value_tokens):
                continue
            if value_tokens.issubset(query_tokens):
                scores[index] = 100.0

    @staticmethod
    def _score_dosage(
        query_terms: frozenset[str], record_terms: frozenset[str]
    ) -> float:
        if not record_terms:
            return 0.0
        if query_terms & record_terms:
            return 100.0
        return max(
            float(fuzz.ratio(left, right))
            for left in query_terms
            for right in record_terms
        )

    def _record_results(
        self,
        order: list[int],
        combined: list[float],
        field_scores: dict[str, list[float]],
        catalog: Catalog,
        top_k: int,
        min_score: float,
    ) -> tuple[MatchResult, ...]:
        results: list[MatchResult] = []
        for index in order:
            score = combined[index]
            if score < min_score:
                break
            results.append(
                MatchResult(
                    record=catalog.records[index],
                    score=score,
                    field_scores={
                        field: scores[index]
                        for field, scores in field_scores.items()
                    },
                )
            )
            if len(results) >= top_k:
                break
        return tuple(results)

    def _grouped_results(
        self,
        order: list[int],
        combined: list[float],
        field_scores: dict[str, list[float]],
        catalog: Catalog,
        top_k: int,
        min_score: float,
    ) -> tuple[MatchResult, ...]:
        groups: dict[tuple[str, str, str, str], list[int]] = {}
        for index in order:
            if combined[index] < min_score:
                break
            record = catalog.records[index]
            key = (
                normalize_text(record.brand_name),
                normalize_text(record.dosage),
                normalize_text(record.active_substance),
                normalize_text(record.form),
            )
            groups.setdefault(key, []).append(index)

        results: list[MatchResult] = []
        for indices in groups.values():
            best_index = indices[0]
            variants = tuple(catalog.records[index] for index in indices)
            results.append(
                MatchResult(
                    record=catalog.records[best_index],
                    score=combined[best_index],
                    field_scores={
                        field: scores[best_index]
                        for field, scores in field_scores.items()
                    },
                    variants=variants,
                )
            )
            if len(results) >= top_k:
                break
        return tuple(results)
