"""
Financial Data Pipeline - Entry Point
Usage: python main.py [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--no-cache]
"""
import argparse
from datetime import date
from config import DEFAULT_START


def parse_args():
    parser = argparse.ArgumentParser(description="Financial data pipeline")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=str(date.today()))
    parser.add_argument("--no-cache", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    use_cache = not args.no_cache

    print(f"Pipeline: {args.start} ~ {args.end}, cache={use_cache}")
    # TODO: collectors -> processors -> analysis -> visualization


if __name__ == "__main__":
    main()
