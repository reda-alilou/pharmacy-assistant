"""Run real database checks only inside the explicit isolated verifier lifecycle."""
import argparse
import json
import os
import unittest

from pharmacy_infrastructure.paths import ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    project=os.environ.get('PHARMACY_ISOLATED_TEST_PROJECT','')
    expected=ROOT / '.runtime' / (project+'-host.env')
    if (not project.startswith('pharmacy-checkpoint4-test-') or len(project)!=58
            or os.environ.get('PHARMACY_PG_TEST_ENV')!=str(expected)):
        parser.error('Run through pharmacy-compose-verify --run-isolated; application databases are not test targets')
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests/integration'),pattern='test_postgres*.py')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    passed=result.wasSuccessful() and not result.skipped and result.testsRun>=17
    print(json.dumps(dict(passed=passed,tests_run=result.testsRun,skipped=len(result.skipped),
                          inference_performed=False)),flush=True)
    return 0 if passed else 1


if __name__=='__main__':
    raise SystemExit(main())
