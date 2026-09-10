import tempfile
from pathlib import Path

from essos_travel.advanced_agent import AdvancedAgent
from essos_travel.config import sample_context
from essos_travel.providers import MockFlights
from essos_travel.storage import Store


CASES = [
    ("Find flights for my appointment", "Which airport"),
    ("Chicago under 900", "cheapest first"),
    ("nonstop only", "Example Direct"),
    ("what do you know about my trip?", "$900"),
    ("when do I need to arrive?", "arrive by"),
    ("no budget limit", "Example Direct"),
    ("compare the options", "quick comparison"),
    ("which one would you recommend?", "I’d pick option"),
]


def main():
    failures = []
    with tempfile.TemporaryDirectory() as folder:
        store = Store(Path(folder) / "state.sqlite3")
        agent = AdvancedAgent(store, sample_context(), MockFlights())
        for text, expected in CASES:
            answer = agent.reply("eval", text)
            print(f"> {text}\n{answer}\n")
            if expected not in answer:
                failures.append((text, expected))
        store.db.close()

    if failures:
        print("FAILED")
        for text, expected in failures:
            print(f"- {text!r}: expected {expected!r}")
        raise SystemExit(1)

    print(f"PASS: {len(CASES)} scripted agent checks")


if __name__ == "__main__":
    main()
