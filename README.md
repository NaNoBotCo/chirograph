# Chirograph

The settlement track of a civil case, from the first offer to the dismissal: a ladder of offers with each running clock, a reading of the agreement against a list of terms, a closing list whose tasks move only with a file that shows it, and a mediation statement. A date prints with its arithmetic and its citation, in the court's time zone and the reader's.

A chirograph was a medieval record of a settlement: the terms written out once for each side on one sheet, the sheet cut apart, each side taking a part.

It runs on a Mac with Python 3.9 and two Python packages. The rule table is California superior court. The example matter, *Jane Doe v. Roe Holdings, LLC*, Case No. 26CV000000, is fictional, and so are the names, amounts and dates in it. The desk window, showing that matter: https://nanobotco.github.io/chirograph/

Chirograph gives dates and document text.

## Install

```sh
cd chirograph
python3 -m pip install --user -r requirements.txt     # pypdf, reportlab
bin/chirograph --help
```

Put `bin/` on your PATH, or symlink `bin/chirograph` into a folder that is, to type `chirograph` anywhere. `python3 -m chirograph` works from this folder. [INSTALL.txt](INSTALL.txt) has the same steps in plain words.

## A matter folder

```sh
chirograph new-matter ~/Matters/doe-v-roe --plaintiff "Jane Doe" --defendant "Roe Holdings, LLC" \
    --case-no 26CV000000 --county Alameda --reader-tz Europe/London
```

```
matter.json      parties, case number, court, court_tz, reader_tz, trial_date
offers.json      the ladder
closing.json     closing facts and the task list
statement.json   the parts of the mediation statement a person writes
STATUS.md        narrative, append-only; the last dated block wins
DONE.md          ledger; a dated line is done
muzzles.txt      words and topics that stay out of the mediation statement
CLAUDE.md        the matter's rules for Claude Code
offers/  agreements/  evidence/  received/  out/
```

The layout follows [Cursitor](https://github.com/NaNoBotCo/cursitor)'s matter folder, so one folder can serve both.

## Commands

| Command | What it does |
|---|---|
| `new-matter <dir>` | Scaffolds a matter folder |
| `offer add --made D --from A --to B --kind K --amount N --document FILE` | Enters an offer: `letter`, `998`, `counter` or `mediator` |
| `offer list [--today D] [--json]` | The ladder oldest first, each side's last position, the gap, the midpoint, the clocks |
| `offer decide ID rejected\|countered\|accepted\|withdrawn [--document FILE]` | Records an answer to an offer |
| `terms check FILE [--release-only NAME] [--expect-none TERM,TERM]` | Reads an agreement (PDF or text) against the term list |
| `closing build --signed D ...` | Builds the closing list from the closing facts |
| `closing list [--today D] [--json]` | Each task, its date, its arithmetic and its state |
| `closing done TASK [--state S] --evidence FILE` | Enters a state on a task, with the file that shows it |
| `statement new` / `statement build` | A blank `statement.json`; then text and PDF, checked against `muzzles.txt` |
| `brief [--today D]` | Today, the next 7 days, clocks running, tasks with no evidence, open offers |
| `ics [-o FILE]` | Calendar file with the arithmetic in each event |
| `rules` | The rule table, each rule with its citation and verify status |
| `desk [--matter DIR]` | Large-type window in the browser at 127.0.0.1:8775, English and Thai |

## The ladder

An offer has a date, a sender, a recipient, a kind, an amount, its terms in a line, the way it was served and the document that made it.

Statuses:

- **OPEN**: the document is on disk and the clock, if there is one, has not run out.
- **UNSOURCED**: no document is named, or the file named is not on this disk.
- **LAPSED**: the clock ran out. Lapse follows from the date; it is not entered by hand, and the offer stays in `offers.json`.
- **REJECTED, COUNTERED, ACCEPTED, WITHDRAWN**: entered with `offer decide`.

Clocks. An expiry stated in the offer wins. A statutory offer to compromise (Code of Civil Procedure §998: a written offer to let judgment be entered on stated terms, with cost consequences for a side that turns it down and then does no better) with no stated expiry gets the statute's clock:

```
Lapses Fri Sep 11 2026 — made Aug 12 + 30 days (CCP §998(b)(2)) = Fri Sep 11.
```

When `matter.json` has a `trial_date` and trial comes before day 30, the clock stops at trial. A day 30 on a weekend or court holiday is left where the count lands, with the next court day in a note. The extension for service by mail or by electronic means is left off unless the offer is entered with `--extend`; the rule table marks that question "from memory, not read". A statutory offer answered with a counter or a rejection still shows its clock until the date passes.

## The terms check

```sh
chirograph terms check "agreements/2026-09-17 settlement agreement.pdf" \
    --release-only "Roe Holdings, LLC" --expect-none confidentiality,non-disparagement
```

For each term in `rules/terms.json` the result is `FOUND` with the passage quoted and cited `page:line`, or `not found in this text`. The second wording means what it says: the patterns did not match the text that was read, and an agreement can say a thing in other words. A scanned PDF with no text layer needs OCR first.

The term list covers payment (amount, payor, due date, method), the release (who, mutual or one-way, the Civil Code §1542 waiver of unknown claims), dismissal (with or without prejudice, and of which pleadings: complaint, cross-complaint), withdrawal of a lis pendens (a recorded notice that a case about the property is pending), the transfer instrument with notarisation and recording, tax allocation and reporting forms, confidentiality, non-disparagement, retained jurisdiction under CCP §664.6, fees and costs, liens, a cure period, time of the essence, counterparts and electronic signature, integration and governing law. Edit the file to fit the kind of case.

The release gets a closer read: each clause with who releases whom, and the classes that ride along (heirs, insurers, agents). `--release-only NAME` exits 1 and names any other released person or entity. `--by NAME` reads only the clauses that party gives. `--strict` counts the classes too. `--expect-none` exits 1 when a listed term is found.

## The closing list

```sh
chirograph closing build --signed 2026-09-17 --payment-amount 120000 --payment-days 21 --payment-cite "Agreement §1" \
    --instrument "Quitclaim deed" --signer-abroad --instrument-sign-days 14 --instrument-cite "Agreement §6" \
    --retain --hearing "2026-09-24 09:00 Case management conference"
```

Tasks, each with a date and the arithmetic behind it:

- notice of settlement, due the day the case settles (Cal. Rules of Court, rule 3.1385(a)(1)), with a note when a hearing falls within 10 days;
- payment, wire instructions and the tax form, on the agreement's own dates;
- the deed or other instrument: signed before a notary or, for a signer abroad, a consular officer; dispatched; its outside date;
- withdrawal of the lis pendens;
- request for dismissal, 45 days after settlement (rule 3.1385(b)), rolled under rule 1.10(b), with the last day to ask for more time (rule 3.1385(e)); or, for a conditional settlement, the date named in the notice (rule 3.1385(c));
- the stipulation for the court to retain jurisdiction (CCP §664.6(a));
- each hearing still on calendar.

A court paper moves through `BUILT → SIGNED → SERVED → FILED → DONE`. A state is entered with `--evidence` naming a file on disk: a receipt, a sent message saved as .txt, a conformed copy. Without the file the command exits 1, prints `no evidence on this disk`, and the task stays in its state. Each move appends a dated line to `DONE.md`.

A hearing shows `ON CALENDAR` until `closing done hearing-1 --state OFF --evidence FILE` names an order or the court's own page saved to disk.

Times print in two zones, worked out with `zoneinfo`, so the offset follows the clock changes: Los Angeles to Bangkok is 14 hours in summer and 15 in winter.

```
Thu Sep 24 2026 09:00 court time = Thu Sep 24 2026 17:00 in Europe/London.
```

## The mediation statement

`statement.json` carries the parties, the posture of the case, the facts, a claims-and-damages table and the terms sought. `statement build` adds the offer history from `offers.json` and writes `out/mediation-statement.txt` (one paragraph per line) and `out/mediation-statement.pdf` (US Letter, Times 12, one-inch margins, page numbers).

Before a file is written the text is checked against `muzzles.txt`: one word, phrase or regular expression per line. A match exits 1 and prints the line numbers. The example matter's list has words about motive, bargaining pressure and hardship.

## The rule table

`rules/ca_settlement.json` has one entry per rule: period, direction, citation, the text relied on, `source` and `verify`. `verify` reads `read <url> <date>` when the text was read at its official page on that date, and `from memory, not read` otherwise. `chirograph rules` prints the table. Statutes and rules of court change; read a rule again before relying on its date.

Read on 2026-11-23: CCP §998, CCP §664.6, CCP §1013(a), CCP §1010.6(a)(3)(B) and Civil Code §1542 at leginfo.legislature.ca.gov; rules 3.1385 and 1.10 at courts.ca.gov. From memory, not read: whether the service extensions reach the 30 days in §998 (the table names *Poster v. Southern California Rapid Transit Dist.* (1990) 52 Cal.3d 266), whether a counter or a rejection ends a statutory offer, and the extensions for overnight delivery and fax.

Court holidays come from `holidays/*.json`, written from the rules that define them; edit a table to match a court's own closures.

## The desk

```sh
chirograph desk --matter examples/doe-v-roe
```

A page on 127.0.0.1 with the ladder drawn as bars, the clocks, the closing list with its states, and the terms check for a file in `agreements/` or for pasted text. Labels switch between English and Thai. The desk reads the matter folder; changes go through the command line. When port 8775 is taken it tries the next one.

## The example

`python3 scripts/make_example.py` rebuilds `examples/doe-v-roe`: four offers, a signed agreement in text and PDF, a closing list with the notice of settlement served and not yet filed, a mediation statement, a calendar file, and the printed outputs in `out/`.

## Tests

```sh
python3 tests/run.py
```

82 tests. The runner uses pytest when it is installed and its own small loop when it is not.

## Licence

See [NOTICE.txt](NOTICE.txt). The court-day counting, the holiday tables, the calendar-file writer and the desk server are vendored from Cursitor.
