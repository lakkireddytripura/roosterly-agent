"""Eval on the 10 labelled examples. Labels come from the helpdesk, never from a model.
Usage: python eval.py --tag before   (then change the code)   python eval.py --tag after"""
import config  # noqa: F401  (loads .env first)
import argparse
import json
import os

from decide import decide
from helpdesk import Helpdesk, items

FIELDS = ("language", "category", "priority", "action")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="run")
    args = ap.parse_args()
    examples = items(Helpdesk().call("GET", "/examples"), ("examples", "items", "data"))
    rows, hits = [], {f: 0 for f in FIELDS}
    tok_in = tok_out = 0
    for ex in examples:
        d = decide(ex)
        lab = ex["label"]
        row = {"id": ex["id"], "got": {f: d.get(f) for f in FIELDS}, "label": {f: lab.get(f) for f in FIELDS},
               "source": d.get("source"), "reason": d.get("reason"), "gloss": d.get("english_gloss"),
               "label_reason": lab.get("reason"), "subject": ex.get("subject")}
        for f in FIELDS:
            hits[f] += row["got"][f] == row["label"][f]
        tok_in += d["tokens"][0]
        tok_out += d["tokens"][1]
        rows.append(row)
        bad = [f for f in FIELDS if row["got"][f] != row["label"][f]]
        print(ex["id"], "OK" if not bad else f"MISMATCH {bad}: got {row['got']} want {row['label']}")
        if bad:
            print("   subject     :", row["subject"])
            print("   our reason  :", row["reason"].encode("ascii", "replace").decode())
            print("   label reason:", (row["label_reason"] or "").encode("ascii", "replace").decode())
    n = len(examples)
    summary = {f: f"{hits[f]}/{n}" for f in FIELDS}
    summary["tokens_in_per_ticket"] = tok_in / n
    summary["tokens_out_per_ticket"] = tok_out / n
    print("\nSUMMARY", summary)
    os.makedirs("eval_results", exist_ok=True)
    json.dump({"summary": summary, "rows": rows}, open(f"eval_results/{args.tag}.json", "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
