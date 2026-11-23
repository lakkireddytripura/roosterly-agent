# Roosterly support-ticket agent

## How to run
```bash
git clone <repo> && cd roosterly-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in HELPDESK_KEY, HELPDESK_EMAIL, ANTHROPIC_API_KEY
python eval.py --tag before     # eval on the 10 labelled examples (no tickets are sent)
python agent.py --dry-run       # decide only
curl -X POST -H "Authorization: Bearer $HELPDESK_KEY" -H "X-Candidate-Email: $HELPDESK_EMAIL" "$HELPDESK_URL/practice/reset"
python agent.py                 # final run: handles all open tickets once
```

## Decisions
1. **Model proposes, code enforces.** One LLM call returns language, category, priority, action, reason, draft, handoff note
   (forced tool call = structured output). Code then applies the client's rules: regex rules for refunds, cancellations,
   AVG/GDPR, security, legal and leaving customers always force a handoff; a reply needs FAQ ids, confidence >= CONF_MIN and
   a pass from an independent verifier call, otherwise it is downgraded to a handoff. *Assumption:* "unsure" = confidence < 0.75.
2. **Dutch: work in Dutch directly.** Translating first costs an extra call and loses nuance. To check Dutch without reading it:
   the model writes an English gloss of its own draft, a second call audits language/grounding against the FAQ, and the
   eval stores glosses for me to read. *Limit:* this is a model check, not a human check.
3. **FAQ-only grounding.** The whole FAQ (small) is in the prompt; replies must cite FAQ ids. Plan-specific answers use `customer_plan`.
   *Assumption:* asking to cancel or change a contract goes to a human even though upgrading is in F05.
AI tools: built with Claude,Groq ; I reviewed and can explain every file.

## Reliability
- 429: wait `Retry-After`; client also self-limits to 4 req/s. 503: exponential backoff + jitter (nothing was saved, safe to retry).
- 409: never retried; logged as `already_handled_409`. If a POST times out and the retry gets a 409, that is the same safe path.
- Crash/re-run: tickets come from `status=open`, so handled ones are not returned; `state.jsonl` is a second guard.
- Security: keys only in env vars; ticket text is wrapped as data and the prompt says to ignore instructions in it; IBANs and
  card numbers are redacted before the model, in outputs, and in logs; logs hold no ticket text. LLM failure => handoff, never a blind reply.
- One log line per ticket in `logs/`.

## Eval and fix
Before: language 10/10, category 9/10, priority 8/10, action 8/10.
After: language 10/10, category 9/10, priority 10/10, action 9/10.
The fix: replies when the FAQ explains the cause even if the customer is blocked, no filler in drafts, and a checker that only rejects real errors.
Cost per 100 tickets: about 270,600 input and 24,900 output tokens. Free tier cost is €0. Include the formula from my last message.
Still wrong: E01 (the second-check call sometimes rejects a correct reply) and E07 (price questions labelled billing).

## What I would improve
Next: a human-reviewed Dutch test set and a language-id check in code. Brief change: define "unsure" and whether plan upgrades count as contract changes.
