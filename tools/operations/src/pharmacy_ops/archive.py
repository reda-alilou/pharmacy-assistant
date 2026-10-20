"""Verify preserved historical inputs and active relocations without changing files."""
import argparse
import json

from pharmacy_infrastructure.evidence import verify_archive


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        result=verify_archive()
    except (OSError,ValueError,KeyError,TypeError):
        parser.exit(1,'Archive verification failed; inspect the manifest and preserved files.\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
