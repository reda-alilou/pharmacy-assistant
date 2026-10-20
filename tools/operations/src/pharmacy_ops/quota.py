"""Show PostgreSQL inference quota status without sending a model request."""
import argparse
import json
from pathlib import Path

from pharmacy_infrastructure.paths import ENV_FILE
from pharmacy_language.config import LanguageSettings
from pharmacy_language.quota.control import AttemptControl


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',type=Path,default=ENV_FILE)
    args=parser.parse_args()
    control=AttemptControl.from_settings(LanguageSettings.from_env(args.env_file))
    try:
        print(json.dumps(control.store.status(control.scope),indent=2))
    finally:
        control.close()


if __name__=='__main__':
    main()
