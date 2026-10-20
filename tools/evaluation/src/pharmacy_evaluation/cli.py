"""One explicit entry point for scoring, evidence checks and budgeted live runs."""
import argparse
import importlib
import sys

COMMANDS = {
    'baseline': 'runners.baseline', 'development': 'runners.development',
    'held-out': 'runners.held_out', 'interpretation': 'runners.interpretation',
    'freeze': 'reporting.freeze', 'report': 'reporting.analysis', 'merge': 'reporting.merge',
    'datasets': 'datasets.baseline',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=[*COMMANDS, 'scenarios'])
    args = parser.parse_args(sys.argv[1:2])
    remaining = sys.argv[2:]
    if args.command == 'scenarios':
        scenarios = argparse.ArgumentParser(prog='pharmacy-evaluate scenarios', description='Budgeted development scenarios; no saved-answer fallback.')
        scenarios.add_argument('scenario', choices=['conversation', 'pharmacy'])
        selected = scenarios.parse_args(remaining[:1])
        remaining = remaining[1:]
        module = 'runners.scenarios.' + selected.scenario
    else:
        module = COMMANDS[args.command]
    sys.argv = [f'pharmacy-evaluate {args.command}', *remaining]
    importlib.import_module('pharmacy_evaluation.' + module).main()


if __name__ == '__main__':
    main()
