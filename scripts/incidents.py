#!/usr/bin/env python3
"""Read the incident log and answer the people who wrote to you.

    python scripts/incidents.py list                  # oldest unanswered first
    python scripts/incidents.py show <id>
    python scripts/incidents.py answer <id> --outcome fixed \
        --note "You were right..." --by "Martin Hawkes"

This is the tool for whoever ends up named on the rota in
`docs/INCIDENTS.md`. It exists because that document describes a process
with no instrument: it says `dangerous_miss` is worked the same day and
says nothing about how a person would find one.

Three things it does on purpose.

**`list` sorts by severity and then by age, oldest first.** A queue sorted
newest-first buries the report that has been waiting longest, which is the
one most likely to be the one you are failing.

**It will not let you answer a `medical` report.** Those are not defect
reports and `docs/INCIDENTS.md` is emphatic that they must never be queued
as one. What is owed there is owed to a person, not to the codebase.

**Every answer is appended, never written over.** The log is evidence. An
outcome quietly changed from "fixed" to "no change" is exactly the record
nobody could trust, so the history of what you said stays readable.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.config import settings  # noqa: E402
from app.incidents import (  # noqa: E402
    CLOSED_OUTCOMES,
    IncidentStore,
    IncidentUpdate,
    Outcome,
    Severity,
    status_for,
)

# Worst first, which is the order the risk matrix uses and not the order
# reports arrive in.
SEVERITY_ORDER = {
    Severity.MEDICAL.value: 0,
    Severity.DANGEROUS_MISS.value: 1,
    Severity.DANGEROUS_FALSE_ALARM.value: 2,
    Severity.ORDINARY.value: 3,
}

RESPONSE_TIME = {
    Severity.MEDICAL.value: "not a defect report -- see docs/INCIDENTS.md",
    Severity.DANGEROUS_MISS.value: "same day",
    Severity.DANGEROUS_FALSE_ALARM.value: "within the week",
    Severity.ORDINARY.value: "batched",
}


def _store() -> IncidentStore:
    return IncidentStore(settings.incident_log_path)


def _age_days(received_at: str) -> float:
    try:
        then = datetime.fromisoformat(received_at)
    except ValueError:
        return 0.0
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).total_seconds() / 86400


def cmd_list(args: argparse.Namespace) -> int:
    store = _store()
    reports = store.all()
    if not reports:
        print("No reports. The log is empty.")
        return 0

    updates = store.updates()
    rows = []
    for report in reports:
        status = status_for(report, updates)
        if args.all or not status.closed:
            rows.append((report, status))

    rows.sort(key=lambda r: (SEVERITY_ORDER.get(r[0].severity, 9), r[0].received_at))

    shown = "all" if args.all else "unanswered"
    print(f"{len(rows)} {shown} of {len(reports)} reports, worst and oldest first\n")
    print(f"  {'severity':<22}{'age':>7}  {'outcome':<26}id")
    for report, status in rows:
        age = f"{_age_days(report.received_at):.0f}d"
        flag = "" if status.closed else "  <-- waiting"
        print(
            f"  {report.severity:<22}{age:>7}  {status.outcome:<26}"
            f"{report.incident_id}{flag}"
        )
    print()

    overdue = [
        r for r, s in rows
        if r.severity == Severity.DANGEROUS_MISS.value
        and not s.closed
        and _age_days(r.received_at) >= 1
    ]
    if overdue:
        print(
            f"  {len(overdue)} dangerous_miss report(s) older than a day and "
            f"unanswered.\n  docs/INCIDENTS.md says same day. That is the "
            f"failure the app exists to prevent.\n"
        )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    store = _store()
    report = next((r for r in store.all() if r.incident_id == args.incident_id), None)
    if report is None:
        print(f"No report with id {args.incident_id}", file=sys.stderr)
        return 1

    status = status_for(report, store.updates())
    wrap = lambda t: textwrap.fill(t or "(none)", 76, subsequent_indent="    ")

    print(f"\n  {report.incident_id}")
    print(f"  {report.severity}  --  {RESPONSE_TIME.get(report.severity, '')}")
    print(f"  received {report.received_at}  ({_age_days(report.received_at):.0f}d ago)")
    print(f"\n  WHAT THE APP SAID")
    print(f"    verdict      {report.verdict}")
    print(f"    candidates   {', '.join(report.reported_candidates) or '(none)'}")
    print(f"    model        {report.model_version}  calibrated={report.calibrated}")
    print(f"\n  WHAT THE REPORTER SAYS")
    print(f"    believed     {report.believed_species or '(not named)'}")
    print(f"    ate it       {report.anyone_ate_it}   unwell {report.anyone_unwell}")
    print(f"    account      {wrap(report.account)}")
    print(f"    contact      {report.contact or '(not left)'}")
    print(f"\n  CURRENT OUTCOME")
    print(f"    {status.outcome}  closed={status.closed}")
    print(f"    {wrap(status.public_note)}")

    history = [u for u in store.updates() if u.incident_id == report.incident_id]
    if history:
        print(f"\n  HISTORY")
        for u in sorted(history, key=lambda u: u.recorded_at):
            who = f" by {u.responder}" if u.responder else ""
            print(f"    {u.recorded_at}  {u.outcome}{who}")
            if u.internal_note:
                print(f"      internal: {wrap(u.internal_note)}")
    print()
    return 0


def cmd_answer(args: argparse.Namespace) -> int:
    store = _store()
    report = next((r for r in store.all() if r.incident_id == args.incident_id), None)
    if report is None:
        print(f"No report with id {args.incident_id}", file=sys.stderr)
        return 1

    if report.severity == Severity.MEDICAL.value:
        print(
            "This is a medical report and must not be answered as a defect.\n"
            "docs/INCIDENTS.md: nothing is owed to the codebase here and "
            "everything is owed to the person. If they left a contact, a "
            "human replies with the emergency information and nothing else.",
            file=sys.stderr,
        )
        return 1

    note = args.note.strip()
    if len(note) < 10:
        print(
            "The public note is what the reporter reads. Write them a "
            "sentence.",
            file=sys.stderr,
        )
        return 1

    update = IncidentUpdate(
        incident_id=report.incident_id,
        recorded_at=datetime.now(timezone.utc).isoformat(),
        outcome=args.outcome,
        public_note=note,
        internal_note=args.internal or "",
        responder=args.by or "",
    )
    store.append_update(update)

    closed = Outcome(args.outcome) in CLOSED_OUTCOMES
    print(f"Recorded {args.outcome} on {report.incident_id}.")
    print(f"The reporter sees this at GET /incident/{report.incident_id}")
    if not closed:
        print("Still open -- it will stay in `list` until you give an outcome.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="the queue, worst and oldest first")
    p_list.add_argument("--all", action="store_true", help="include answered reports")
    p_list.set_defaults(fn=cmd_list)

    p_show = sub.add_parser("show", help="one report in full")
    p_show.add_argument("incident_id")
    p_show.set_defaults(fn=cmd_show)

    p_ans = sub.add_parser("answer", help="record an outcome the reporter will see")
    p_ans.add_argument("incident_id")
    p_ans.add_argument(
        "--outcome", required=True,
        choices=[o.value for o in Outcome if o is not Outcome.RECEIVED],
    )
    p_ans.add_argument("--note", required=True, help="written FOR THE REPORTER")
    p_ans.add_argument("--internal", help="written for us; never shown")
    p_ans.add_argument("--by", help="who answered")
    p_ans.set_defaults(fn=cmd_answer)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
