from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from src.config import get_settings
from src.contracts.rag_contract_models import RetrieverFilters, RetrieverInputContract
from src.rag.index_store import ChunkRecord, FaissRagStore


TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z-]{2,}|[\u4e00-\u9fff]{2,}|\d+(?:\.\d+)?")
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "were",
    "was",
    "are",
    "using",
    "used",
    "study",
    "results",
    "method",
    "methods",
    "conclusion",
    "abstract",
    "background",
}


@dataclass
class EvalSample:
    sample_id: str
    sample_unit: str
    query: str
    expected_evidence_id: str
    expected_paper_id: str
    expected_title: str
    expected_page: int
    expected_section: str


@dataclass
class BadCase:
    sample_id: str
    metric: str
    bad_case_type: str
    severity: str
    query_or_claim: str
    expected: str
    actual: str
    detail: str
    suggested_next_step: str


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate Agentic RAG retrieval, citation, claim support, and bad cases."
    )
    parser.add_argument("--sample-size", type=int, default=20, help="Number of random retrieval samples.")
    parser.add_argument(
        "--sample-unit",
        choices=["paper", "chunk"],
        default="paper",
        help="paper: sample one query per paper; chunk: sample individual chunks.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible sampling.")
    parser.add_argument("--top-k", type=int, default=5, help="Top-K cutoff for Recall@K.")
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="Rebuild FAISS index from DATA_DIR before evaluation so newly added PDFs are included.",
    )
    parser.add_argument(
        "--no-auto-rebuild",
        action="store_true",
        help="Skip automatic rebuild when Data PDFs are missing from the current index.",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=None,
        help="Optional generated report JSON to evaluate citation accuracy and claim support rate.",
    )
    parser.add_argument(
        "--requirements",
        type=str,
        default="",
        help="Optional comma-separated requirement/JD keywords for coverage evaluation.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_DIR / "output" / "evaluation",
        help="Directory for metrics_summary.json, bad_cases.csv, and eval_samples.jsonl.",
    )
    args = parser.parse_args()

    if args.top_k < 1:
        raise ValueError("--top-k must be >= 1")

    settings = get_settings()
    store = FaissRagStore(settings)
    indexed_pdf_paths = indexed_sources(store)
    data_pdf_paths = {str(path.resolve()) for path in settings.data_dir.rglob("*.pdf")}
    missing_indexed_pdfs = sorted(data_pdf_paths - indexed_pdf_paths)
    should_rebuild = bool(args.rebuild_index or (missing_indexed_pdfs and not args.no_auto_rebuild))
    if should_rebuild:
        reason = "--rebuild-index" if args.rebuild_index else "Data PDFs missing from index"
        print(f"Rebuilding index from {settings.data_dir} ({reason}) ...")
        print(json.dumps(store.rebuild(), ensure_ascii=False, indent=2))

    records = load_records(store)
    if not records:
        raise RuntimeError(
            "No indexed chunks found. Run with --rebuild-index after placing PDFs in the Data directory."
        )

    samples = build_eval_samples(
        records,
        sample_size=args.sample_size,
        seed=args.seed,
        sample_unit=args.sample_unit,
    )
    bad_cases: list[BadCase] = []
    retrieval_metrics = evaluate_retrieval(store, samples, top_k=args.top_k, bad_cases=bad_cases)

    report_metrics: dict[str, Any] = {}
    if args.report_json:
        report_metrics = evaluate_report_json(args.report_json, bad_cases)

    coverage_metrics: dict[str, Any] = {}
    if args.requirements:
        coverage_metrics = evaluate_requirement_coverage(args.requirements, args.report_json, bad_cases)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_dir": str(settings.data_dir),
        "sample_size_requested": args.sample_size,
        "sample_size_actual": len(samples),
        "sample_unit": args.sample_unit,
        "seed": args.seed,
        "top_k": args.top_k,
        "data_pdf_count": len(data_pdf_paths),
        "indexed_pdf_count_before_rebuild": len(indexed_pdf_paths),
        "missing_indexed_pdf_count_before_rebuild": len(missing_indexed_pdfs),
        "rebuilt_index": should_rebuild,
        "metrics": {
            **retrieval_metrics,
            **report_metrics,
            **coverage_metrics,
        },
        "bad_case_count": len(bad_cases),
    }

    write_json(args.output_dir / "metrics_summary.json", summary)
    write_samples(args.output_dir / "eval_samples.jsonl", samples)
    write_bad_cases(args.output_dir / "bad_cases.csv", bad_cases)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote: {args.output_dir / 'metrics_summary.json'}")
    print(f"Wrote: {args.output_dir / 'bad_cases.csv'}")
    print(f"Wrote: {args.output_dir / 'eval_samples.jsonl'}")


def indexed_sources(store: FaissRagStore) -> set[str]:
    return {str(Path(record.source_path).resolve()) for record in load_records(store)}


def load_records(store: FaissRagStore) -> list[ChunkRecord]:
    _, records = store._load()
    return [
        record
        for record in records
        if record.text.strip() and Path(record.source_path).exists()
    ]


def build_eval_samples(
    records: list[ChunkRecord],
    sample_size: int,
    seed: int,
    sample_unit: str,
) -> list[EvalSample]:
    if sample_unit == "paper":
        return build_paper_eval_samples(records, sample_size, seed)
    return build_chunk_eval_samples(records, sample_size, seed)


def build_paper_eval_samples(records: list[ChunkRecord], sample_size: int, seed: int) -> list[EvalSample]:
    rng = random.Random(seed)
    records_by_paper: dict[str, list[ChunkRecord]] = {}
    for record in records:
        records_by_paper.setdefault(record.paper_id, []).append(record)

    paper_ids = sorted(records_by_paper)
    selected_paper_ids = rng.sample(paper_ids, k=min(sample_size, len(paper_ids)))
    samples = []
    for idx, paper_id in enumerate(selected_paper_ids, start=1):
        paper_records = records_by_paper[paper_id]
        representative = choose_representative_record(paper_records)
        samples.append(
            EvalSample(
                sample_id=f"paper_{idx:03d}",
                sample_unit="paper",
                query=make_query(representative),
                expected_evidence_id=representative.evidence_id,
                expected_paper_id=representative.paper_id,
                expected_title=representative.title,
                expected_page=representative.page_start,
                expected_section=representative.section,
            )
        )
    return samples


def choose_representative_record(records: list[ChunkRecord]) -> ChunkRecord:
    section_priority = {
        "abstract": 0,
        "introduction": 1,
        "methods": 2,
        "results": 3,
        "discussion": 4,
        "conclusion": 5,
    }
    eligible = [
        record
        for record in records
        if len(record.text) >= 240 and len(extract_keywords(record.text, limit=8)) >= 3
    ]
    candidates = eligible or records
    return sorted(
        candidates,
        key=lambda record: (
            section_priority.get(record.section, 9),
            record.page_start,
            record.chunk_index,
        ),
    )[0]


def build_chunk_eval_samples(records: list[ChunkRecord], sample_size: int, seed: int) -> list[EvalSample]:
    rng = random.Random(seed)
    eligible = [
        record
        for record in records
        if len(record.text) >= 240 and len(extract_keywords(record.text, limit=8)) >= 3
    ]
    if not eligible:
        eligible = records
    selected = rng.sample(eligible, k=min(sample_size, len(eligible)))
    return [
        EvalSample(
            sample_id=f"sample_{idx:03d}",
            sample_unit="chunk",
            query=make_query(record),
            expected_evidence_id=record.evidence_id,
            expected_paper_id=record.paper_id,
            expected_title=record.title,
            expected_page=record.page_start,
            expected_section=record.section,
        )
        for idx, record in enumerate(selected, start=1)
    ]


def make_query(record: ChunkRecord) -> str:
    keywords = extract_keywords(record.text, limit=8)
    title_terms = extract_keywords(record.title, limit=5)
    merged = dedupe_preserve_order(title_terms + keywords)
    return " ".join(merged[:10]) or record.title


def extract_keywords(text: str, limit: int) -> list[str]:
    counts: dict[str, int] = {}
    for token in TOKEN_RE.findall(text):
        normalized = token.lower()
        if normalized in STOPWORDS or len(normalized) < 3:
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (item[1], len(item[0])), reverse=True)
    return [token for token, _ in ranked[:limit]]


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def evaluate_retrieval(
    store: FaissRagStore,
    samples: list[EvalSample],
    top_k: int,
    bad_cases: list[BadCase],
) -> dict[str, Any]:
    hits = 0
    reciprocal_ranks: list[float] = []
    precision_scores: list[float] = []
    ndcg_scores: list[float] = []

    for sample in samples:
        payload = RetrieverInputContract(
            request_id=sample.sample_id,
            queries=[sample.query],
            filters=RetrieverFilters(),
            top_k=max(3, min(12, top_k)),
        )
        output = store.retrieve(payload)
        returned = output.evidence_list[:top_k]
        returned_ids = [item.evidence_id for item in returned]
        returned_paper_ids = [item.paper_id for item in returned]
        if sample.sample_unit == "paper":
            relevant_flags = [paper_id == sample.expected_paper_id for paper_id in returned_paper_ids]
            rank = next((idx + 1 for idx, flag in enumerate(relevant_flags) if flag), None)
            expected_label = sample.expected_paper_id
            top_actual = returned_paper_ids[0] if returned_paper_ids else "no_results"
            bad_case_type = "paper_retrieval_miss"
        else:
            relevant_flags = [evidence_id == sample.expected_evidence_id for evidence_id in returned_ids]
            rank = next((idx + 1 for idx, flag in enumerate(relevant_flags) if flag), None)
            expected_label = sample.expected_evidence_id
            top_actual = returned_ids[0] if returned_ids else "no_results"
            bad_case_type = "chunk_retrieval_miss"

        precision_scores.append(sum(relevant_flags) / top_k if top_k else 0.0)
        ndcg_scores.append(ndcg_at_k(relevant_flags, top_k))
        if rank is not None and rank <= top_k:
            hits += 1
            reciprocal_ranks.append(1 / rank)
        else:
            reciprocal_ranks.append(0.0)
            bad_cases.append(
                BadCase(
                    sample_id=sample.sample_id,
                    metric=f"Recall@{top_k}",
                    bad_case_type=bad_case_type if output.evidence_list else "no_retrieval_result",
                    severity="high",
                    query_or_claim=sample.query,
                    expected=expected_label,
                    actual=top_actual,
                    detail=(
                        f"Expected paper={sample.expected_paper_id}, page={sample.expected_page}, "
                        f"section={sample.expected_section}; returned_papers={returned_paper_ids}; "
                        f"returned_evidence={returned_ids}"
                    ),
                    suggested_next_step="Check chunking, metadata freshness, query rewriting, and reranker/hybrid weights.",
                )
            )

    total = len(samples)
    return {
        f"recall@{top_k}": round(hits / total, 4) if total else 0.0,
        "mrr": round(sum(reciprocal_ranks) / total, 4) if total else 0.0,
        f"precision@{top_k}": round(sum(precision_scores) / total, 4) if total else 0.0,
        f"ndcg@{top_k}": round(sum(ndcg_scores) / total, 4) if total else 0.0,
        "retrieval_sample_count": total,
    }


def ndcg_at_k(relevant_flags: list[bool], top_k: int) -> float:
    gains = [1.0 if flag else 0.0 for flag in relevant_flags[:top_k]]
    dcg = sum(gain / math.log2(rank + 2) for rank, gain in enumerate(gains))
    ideal_relevant = sum(gains)
    if ideal_relevant == 0:
        return 0.0
    ideal_gains = [1.0] * int(ideal_relevant)
    idcg = sum(gain / math.log2(rank + 2) for rank, gain in enumerate(ideal_gains))
    return round(dcg / idcg, 4) if idcg else 0.0


def evaluate_report_json(report_path: Path, bad_cases: list[BadCase]) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    evidence = collect_report_evidence(report)
    claims = report.get("claims", [])

    citation_total = 0
    citation_correct = 0
    supported_claims = 0

    for claim in claims:
        claim_id = str(claim.get("claim_id", "unknown_claim"))
        claim_text = str(claim.get("claim_text", ""))
        evidence_ids = list(claim.get("evidence_ids", []))
        evidence_ids.extend(claim.get("data_evidence_ids", []))
        evidence_ids.extend(claim.get("literature_evidence_ids", []))
        evidence_ids = dedupe_preserve_order([str(item) for item in evidence_ids if item])

        if not evidence_ids:
            bad_cases.append(
                BadCase(
                    sample_id=claim_id,
                    metric="Claim Support Rate",
                    bad_case_type="claim_without_evidence",
                    severity="high",
                    query_or_claim=claim_text,
                    expected="at least one evidence id",
                    actual="none",
                    detail="Claim has no bound data_evidence_ids/literature_evidence_ids/evidence_ids.",
                    suggested_next_step="Require claim-evidence binding during synthesis.",
                )
            )
            continue

        citation_total += len(evidence_ids)
        found_ids = [evidence_id for evidence_id in evidence_ids if evidence_id in evidence]
        citation_correct += len(found_ids)
        missing_ids = sorted(set(evidence_ids) - set(found_ids))
        if missing_ids:
            bad_cases.append(
                BadCase(
                    sample_id=claim_id,
                    metric="Citation Accuracy",
                    bad_case_type="missing_citation_target",
                    severity="high",
                    query_or_claim=claim_text,
                    expected=";".join(evidence_ids),
                    actual=f"missing={';'.join(missing_ids)}",
                    detail="Claim cites evidence ids that are not present in report evidence lists.",
                    suggested_next_step="Validate citation ids before exporting the report.",
                )
            )

        support_scores = [support_score(claim_text, evidence[evidence_id]) for evidence_id in found_ids]
        is_supported = bool(support_scores and max(support_scores) >= 0.18)
        if is_supported:
            supported_claims += 1
        else:
            bad_cases.append(
                BadCase(
                    sample_id=claim_id,
                    metric="Claim Support Rate",
                    bad_case_type="weak_claim_support",
                    severity="medium",
                    query_or_claim=claim_text,
                    expected="claim text overlaps with cited evidence meaning or numeric values",
                    actual=f"support_scores={support_scores}",
                    detail="Cited evidence exists, but lexical/numeric support is weak.",
                    suggested_next_step="Ask critic agent to verify each claim against cited evidence text.",
                )
            )

    return {
        "citation_accuracy": round(citation_correct / citation_total, 4) if citation_total else None,
        "claim_support_rate": round(supported_claims / len(claims), 4) if claims else None,
        "claim_count": len(claims),
        "citation_count": citation_total,
    }


def collect_report_evidence(report: dict[str, Any]) -> dict[str, str]:
    evidence: dict[str, str] = {}
    for item in report.get("data_evidence_list", []):
        evidence_id = str(item.get("data_evidence_id", ""))
        text = " ".join(
            str(item.get(key, ""))
            for key in ("feature_name", "value", "unit", "interpretation")
        )
        if evidence_id:
            evidence[evidence_id] = text
    for item in report.get("literature_evidence_list", []):
        evidence_id = str(item.get("evidence_id") or item.get("literature_evidence_id") or "")
        text = " ".join(
            str(item.get(key, ""))
            for key in ("title", "section", "snippet", "text", "interpretation")
        )
        if evidence_id:
            evidence[evidence_id] = text
    return evidence


def support_score(claim_text: str, evidence_text: str) -> float:
    claim_tokens = set(extract_keywords(claim_text, limit=30))
    evidence_tokens = set(extract_keywords(evidence_text, limit=60))
    if not claim_tokens:
        return 0.0
    overlap = len(claim_tokens & evidence_tokens) / len(claim_tokens)
    claim_numbers = set(re.findall(r"\d+(?:\.\d+)?", claim_text))
    evidence_numbers = set(re.findall(r"\d+(?:\.\d+)?", evidence_text))
    numeric_bonus = 0.25 if claim_numbers and claim_numbers <= evidence_numbers else 0.0
    return round(min(1.0, overlap + numeric_bonus), 4)


def evaluate_requirement_coverage(
    requirements: str,
    report_path: Path | None,
    bad_cases: list[BadCase],
) -> dict[str, Any]:
    requirement_terms = [term.strip().lower() for term in requirements.split(",") if term.strip()]
    if not requirement_terms:
        return {}
    report_text = report_path.read_text(encoding="utf-8").lower() if report_path and report_path.exists() else ""
    covered = [term for term in requirement_terms if term in report_text]
    missing = sorted(set(requirement_terms) - set(covered))
    for term in missing:
        bad_cases.append(
            BadCase(
                sample_id=f"requirement_{term}",
                metric="Requirement Coverage",
                bad_case_type="requirement_not_covered",
                severity="medium",
                query_or_claim=term,
                expected="requirement appears in generated report",
                actual="not found",
                detail="Optional requirement/JD term was not covered by the report text.",
                suggested_next_step="Add requirement decomposition before retrieval/synthesis.",
            )
        )
    return {
        "requirement_coverage": round(len(covered) / len(requirement_terms), 4),
        "requirement_count": len(requirement_terms),
        "covered_requirements": covered,
        "missing_requirements": missing,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_samples(path: Path, samples: list[EvalSample]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for sample in samples:
            handle.write(json.dumps(asdict(sample), ensure_ascii=False) + "\n")


def write_bad_cases(path: Path, bad_cases: list[BadCase]) -> None:
    fieldnames = [
        "sample_id",
        "metric",
        "bad_case_type",
        "severity",
        "query_or_claim",
        "expected",
        "actual",
        "detail",
        "suggested_next_step",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in bad_cases:
            writer.writerow(asdict(item))


if __name__ == "__main__":
    main()
