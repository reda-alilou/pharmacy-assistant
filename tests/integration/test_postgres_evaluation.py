"""Actual PostgreSQL attempt accounting across resumptions; inference is mocked."""
import asyncio
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import uuid
import unittest

from sqlalchemy import delete
from pharmacy_contracts.interpretation import InferenceError, InterpretationResponse
from pharmacy_evaluation.config import EvaluationSettings
from pharmacy_evaluation.runners.interpretation import run_smoke
from pharmacy_language.storage.postgres.models import evaluation_budgets
from tests.support.postgres import TemporaryPostgresCase


@unittest.skipUnless(os.environ.get('PHARMACY_PG_TEST_ENV') and os.environ.get('PHARMACY_ISOLATED_TEST_PROJECT'),
                     'Run through the explicit isolated verification stack')
class PostgresEvaluationTests(TemporaryPostgresCase):
    load_catalogue=False

    def settings(self):
        return EvaluationSettings(language_database_url=self.values['LANGUAGE_DATABASE_URL'],
            inference_provider='groq',groq_api_key='offline-evaluation-fixture',
            groq_output_mode='json_object',inference_quota_scope='eval-'+uuid.uuid4().hex)

    def cases(self):
        return [dict(id='fixture-'+str(index),group='fr',text=text,expected_intents=['price'],
                     expected_medications=[dict(name=['ABIP'],strength=[None],quantity=[None],form=[None],presentation=[None])],
                     expected_context={key:[None] for key in ('pharmacy','city','area','date','time','symptom')})
                for index,text in enumerate(['Prix ABIP ?', 'Quel est le prix de ABIP ?'])]

    def factory(self,calls):
        def create(settings,*,control):
            class Offline:
                async def interpret(self,request):
                    await control.before_attempt()
                    calls.append(request.text)
                    return InterpretationResponse.model_validate(dict(
                        interpretation=dict(language='fr',reply_language='fr',reply_script='latin',intents=['price'],
                            entities=dict(medications=[dict(name='ABIP',strength=None,quantity=None,form=None,presentation=None)],
                                          **{key:None for key in ('pharmacy','city','area','date','time','symptom')})),
                        metadata=dict(provider=settings.inference_provider,requested_model=settings.inference_model,
                            model='isolated-offline-fixture',prompt_version='isolated-fixture-not-model-accuracy',latency_ms=0,
                            attempts=1,completion_id=None,usage=dict(prompt_tokens=None,completion_tokens=None,total_tokens=None))))
                async def close(self):
                    control.close()
            return Offline()
        return create

    def test_budget_resume_and_no_replay_use_persisted_postgres_counts(self):
        async def scenario():
            settings,calls=self.settings(),[]
            with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()), \
                 patch('pharmacy_evaluation.runners.interpretation.create_interpreter',side_effect=self.factory(calls)):
                path=Path(directory)/'run.json'
                options=dict(cases=self.cases(),fixture_label='isolated-ledger-check-not-accuracy',
                             summarize_results=lambda rows,total:dict(passed=len(rows)==total,completed_cases=len(rows)))
                first=await run_smoke(settings,path,0,max_requests=1,**options)
                self.assertEqual(first['status'],'paused_budget')
                second=await run_smoke(settings,path,0,max_requests=1,resume=True,**options)
                self.assertEqual(second['status'],'passed')
                self.assertEqual(len(calls),2)
                self.assertEqual(len(set(calls)),2)
                self.assertEqual(second['invocations'][-1]['total_attempts_reserved'],2)
                await run_smoke(settings,path,0,max_requests=1,resume=True,**options)
                self.assertEqual(len(calls),2)
        asyncio.run(scenario())

    def test_missing_budget_rejects_resume_before_any_additional_request(self):
        async def scenario():
            settings,calls=self.settings(),[]
            with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()), \
                 patch('pharmacy_evaluation.runners.interpretation.create_interpreter',side_effect=self.factory(calls)):
                path=Path(directory)/'run.json'
                options=dict(cases=self.cases(),fixture_label='isolated-ledger-check-not-accuracy')
                report=await run_smoke(settings,path,0,max_requests=1,**options)
                with self.language.begin() as db:
                    db.execute(delete(evaluation_budgets).where(evaluation_budgets.c.id==report['invocations'][0]['id']))
                with self.assertRaises(InferenceError) as caught:
                    await run_smoke(settings,path,0,max_requests=1,resume=True,**options)
                self.assertEqual(caught.exception.detail.code,'quota_state_unavailable')
                self.assertEqual(len(calls),1)
        asyncio.run(scenario())
