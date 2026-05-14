import argparse

from src.graph import run_graph


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Phase 1 SEC filing analyst graph skeleton.")
    parser.add_argument("query", nargs="*", help="Natural-language query to send through the graph.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    query = " ".join(args.query).strip()

    if not query:
        query = input("Query: ").strip()

    if len(query) > 500:
        raise SystemExit("Query must be 500 characters or fewer.")

    result = run_graph(query)
    print(result["final_answer"])


if __name__ == "__main__":
    main()
