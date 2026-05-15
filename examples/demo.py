import argparse
import uuid

from src.graph import resume_graph, run_graph


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the compliance-aware SEC filing analyst graph.")
    parser.add_argument("query", nargs="*", help="Natural-language query to send through the graph.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    query = " ".join(args.query).strip()

    if not query:
        query = input("Query: ").strip()

    if len(query) > 500:
        raise SystemExit("Query must be 500 characters or fewer.")

    thread_id = f"demo-{uuid.uuid4()}"
    result = run_graph(query, thread_id=thread_id)
    if "__interrupt__" in result:
        interrupt_payload = result["__interrupt__"][0].value
        print("\nHuman review required")
        print(f"Triggered rules: {', '.join(interrupt_payload['triggered_rules'])}")
        print(f"Reasoning: {interrupt_payload['reviewer_reasoning']}")
        print("\nDraft answer:")
        print(interrupt_payload["draft_answer"])

        decision = input("\nApprove or reject? ").strip().lower()
        feedback = input("Feedback (optional): ").strip() or None
        result = resume_graph(decision=decision, feedback=feedback, thread_id=thread_id)

    print(result["final_answer"])


if __name__ == "__main__":
    main()
