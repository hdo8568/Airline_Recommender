import argparse
import getpass
import json
import platform
import shutil
import sys
import tempfile
from pathlib import Path

from .config import LOCAL, load_context, settings, write_private
from .conversation import Agent, ClaudeIntent, basic_intent
from .providers import DuffelFlights, MockFlights
from .storage import Store


def make_agent(args, store, context):
    config = settings()
    provider = MockFlights() if args.provider == "mock" else DuffelFlights(config.get("DUFFEL_ACCESS_TOKEN"))
    interpreter = basic_intent if args.interpreter == "basic" else ClaudeIntent(config.get("ANTHROPIC_API_KEY"), config.get("ANTHROPIC_MODEL"))
    return Agent(store, context, provider, interpreter)


def configure():
    config = settings()
    print("Optional credentials. Enter keeps an existing value. Secrets stay in ignored .local/settings.json.")
    for key, label in (("ANTHROPIC_API_KEY", "Claude API key"), ("DUFFEL_ACCESS_TOKEN", "Duffel access token")):
        answer = getpass.getpass(label + ": ").strip()
        if answer:
            config[key] = answer
    model = input("Claude model ID from your account (Enter keeps current): ").strip()
    if model:
        config["ANTHROPIC_MODEL"] = model
    write_private(LOCAL / "settings.json", config)
    print("Saved. No API request was made.")


def main():
    parser = argparse.ArgumentParser(description="Essos flights-only prototype")
    parser.add_argument("command", choices=["chat", "demo", "configure", "doctor", "messages", "build-decoder", "events"], nargs="?", default="chat")
    parser.add_argument("--provider", choices=["mock", "duffel"], default="mock")
    parser.add_argument("--interpreter", choices=["basic", "claude"], default="basic")
    parser.add_argument("--context", help="Patient context JSON file (otherwise uses local fictional example)")
    parser.add_argument("--peer", help="One tester’s international number or iMessage email")
    parser.add_argument("--send", action="store_true", help="Actually send iMessage replies; default is dry-run")
    args = parser.parse_args()
    if args.command == "configure":
        return configure()
    if args.command == "doctor":
        config = settings()
        print("Python:", platform.python_version())
        print("Messages host:", "Mac available" if sys.platform == "darwin" else "requires macOS")
        print("AppleScript:", "available" if shutil.which("osascript") else "missing")
        print("Message decoder:", "built" if (LOCAL / "decode-message").exists() else "not built")
        print("Claude credentials/model:", "configured" if config.get("ANTHROPIC_API_KEY") and config.get("ANTHROPIC_MODEL") else "not configured")
        print("Duffel token:", "configured" if config.get("DUFFEL_ACCESS_TOKEN") else "not configured")
        print("Messages permissions, delivery, and external API access are not tested by this check.")
        return
    if args.command == "build-decoder":
        from .messages import build_decoder
        build_decoder()
        print("Built Messages text decoder.")
        return
    if args.command == "events":
        store = Store(LOCAL / "state.sqlite3")
        for row in store.db.execute("SELECT created,status FROM events ORDER BY rowid DESC LIMIT 20"):
            print(*row, sep="  ")
        return
    context = load_context(args.context)
    if args.command == "demo":
        if args.provider != "mock" or args.interpreter != "basic":
            raise ValueError("The scripted demo always uses sample flights and the offline parser. Use chat for live providers.")
        with tempfile.TemporaryDirectory() as folder:
            agent = Agent(Store(Path(folder) / "state.sqlite3"), context, MockFlights())
            print("ESSOS / FIRST FLIGHT DEMO\nFictional clinic, invented flights, offline parser. No messages sent.\n")
            for text in ["Find flights for my appointment", "Chicago under 900", "nonstop only", "why option 1?", "under 500", "no budget limit"]:
                print(f"You: {text}\nAssistant: {agent.reply('demo', text)}\n")
        return
    store = Store(LOCAL / "state.sqlite3")
    agent = make_agent(args, store, context)
    if args.command == "messages":
        from .messages import run_bridge
        peer = args.peer or input("Tester’s full number (+country code) or iMessage email: ")
        return run_bridge(agent, store, peer, send=args.send)
    print("\nESSOS / FLIGHTS\n" + agent.provider.label)
    print("Language: " + ("Claude" if args.interpreter == "claude" else "limited offline parser (not AI)"))
    print(f"Clinic: {context['clinic']} · arrive by {context['arrival_deadline']} · return from {context['return_not_before']}")
    print("1 adult, economy, exact dates. Type /help, /reset, or /quit. No messages sent.\n")
    session = f"terminal:{args.provider}:{args.interpreter}"
    while True:
        try:
            text = input("You: ").strip()
        except EOFError:
            break
        if text == "/quit":
            break
        if text == "/reset":
            store.save(session, agent.initial())
            print("Assistant: Trip preferences reset.\n")
        elif text:
            print("Assistant:", agent.reply(session, text), "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Setup: {exc}", file=sys.stderr)
        sys.exit(1)
