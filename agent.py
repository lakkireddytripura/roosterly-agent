"""Run: python agent.py [--dry-run]. Reads open tickets, posts one decision each. Safe to re-run."""
import config  # noqa: F401  (loads .env first)
import argparse
import json
import os
import time
from datetime import datetime, timezone

from decide import decide, redact
from helpdesk import AlreadyHandled, ApiError, Helpdesk, items

STATE = "state.jsonl"  # ticket ids already sent by this agent (extra guard on top of status=open)


def load_state():
    if not os.path.exists(STATE):
        return set()
    return {json.loads(l)["id"] for l in open(STATE) if l.strip()}


def mark_done(tid, action):
    with open(STATE, "a") as f:
        f.write(json.dumps({"id": tid, "action": action, "ts": time.time()}) + "\n")


def payload(d):
    p = {k: d[k] for k in ("language", "category", "priority", "reason")}
    p["confidence"] = d["confidence"]
    if d["action"] == "reply":
        p["draft_reply"] = d["draft_reply"]
    elif d["action"] == "handoff":
        p["handoff_note"] = d["handoff_note"]
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="decide but do not post")
    args = ap.parse_args()

    hd = Helpdesk()
    done = load_state()
    os.makedirs("logs", exist_ok=True)
    log = open(f"logs/run-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.jsonl", "a", encoding="utf-8")

    tickets = list(hd.pages("/tickets", ("tickets", "items", "data"), {"status": "open"}))
    print(f"{len(tickets)} open tickets")
    for t in tickets:
        tid = t["id"]
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "id": tid}
        if tid in done:
            rec["outcome"] = "skipped_already_in_state"
        else:
            d = decide(t)
            rec.update({k: d.get(k) for k in ("action", "language", "category", "priority", "confidence",
                                              "faq_ids", "source", "reason", "english_gloss")})
            rec["tokens"] = d.get("tokens")
            if args.dry_run:
                rec["outcome"] = "dry_run"
            else:
                try:
                    hd.call("POST", f"/tickets/{tid}/{d['action']}",
                            json=payload(d))
                    rec["outcome"] = "sent"
                    mark_done(tid, d["action"])
                except AlreadyHandled:
                    rec["outcome"] = "already_handled_409"  # never retry
                    mark_done(tid, d["action"])
                except ApiError as e:
                    rec["outcome"] = f"error_{e.status}"
                    rec["error"] = redact(e.body)[:300]
        log.write(json.dumps(rec, ensure_ascii=False) + "\n")
        log.flush()
        print(tid, rec.get("action"), rec.get("priority"), rec["outcome"])
    log.close()


if __name__ == "__main__":
    main()
