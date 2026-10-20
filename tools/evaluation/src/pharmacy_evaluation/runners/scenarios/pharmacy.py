"""Four budgeted development contact checks: live extraction, local directory."""

import argparse
import asyncio
from pathlib import Path

from pharmacy_core.conversation.answers import render_answer
from pharmacy_evaluation.scoring.extraction import aggregate_extraction
from pharmacy_infrastructure.paths import ROOT
from pharmacy_evaluation.config import EvaluationSettings as Settings
from pharmacy_evaluation.runners.baseline import live_score
from pharmacy_evaluation.runners.interpretation import run_smoke
from pharmacy_evaluation.datasets.baseline import load_examples, sha256
from pharmacy_core.pharmacies.directory import PHARMACIES, PharmacyDirectory


CASE_IDS = ('dev-fr-06', 'dev-ar-05', 'dev-darija-04', 'dev-mixed-05')


def smoke_cases():
    examples = {c.id: c for c in load_examples('development')}
    from pharmacy_evaluation.datasets.baseline import workspace_implementation_paths
    source_hashes = {p.relative_to(ROOT).as_posix(): sha256(p) for p in workspace_implementation_paths()}
    return [{'id':identifier, 'group':examples[identifier].group, 'text':examples[identifier].text,
             'baseline_example':examples[identifier].model_dump(),
             'directory_sha256':sha256(PHARMACIES), 'resolver_sha256':source_hashes,
             'scoring_profile':'reviewed_pharmacy_contact_v1'} for identifier in CASE_IDS]


def score_pharmacy(response, case):
    pharmacy = PharmacyDirectory.from_path().search(response.interpretation.entities)
    expected = case['baseline_example']['expected']['pharmacy_ids']
    correct = pharmacy.status == 'matches' and pharmacy.result_count == len(expected) and (
        {r.pharmacy_id for r in pharmacy.pharmacies} == set(expected))
    return {**live_score(response,case), 'pharmacy_resolution_correct':correct,
            'directory_result':pharmacy.model_dump(mode='json'),
            'grounded_answer':render_answer(response.interpretation,[],pharmacy)}


def summarize_pharmacy(results, total):
    summary = aggregate_extraction(results,total)
    summary['pharmacy_resolutions_correct'] = sum(r['pharmacy_resolution_correct'] for r in results)
    summary['is_general_accuracy_measurement'] = False
    summary['held_out_execution'] = 'not_run'
    summary['passed'] = len(results) == total == 4 and all(
        r['intents_correct'] and r['entities_exact'] and r['pharmacy_resolution_correct']
        and r['reply_language_correct'] and r['reply_script_correct'] for r in results)
    return summary


async def run_pharmacy_smoke(settings, output, *, max_requests=4, resume=False):
    return await run_smoke(settings,output,0,max_requests=max_requests,resume=resume,
        cases=smoke_cases(),score=score_pharmacy,summarize_results=summarize_pharmacy,
        fixture_label='baseline_v1/development:4_pharmacy_contact_cases')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/evaluation/pharmacy_live_step6.json')
    parser.add_argument('--max-requests',type=int,default=4)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    if not 0 <= args.max_requests <= 4:
        parser.error('Use a budget between zero and four attempts per invocation')
    report=asyncio.run(run_pharmacy_smoke(Settings.from_env(),args.output,max_requests=args.max_requests,resume=args.resume))
    return 0 if report['summary']['passed'] else 1


if __name__=='__main__': raise SystemExit(main())
