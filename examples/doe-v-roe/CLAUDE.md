# Matter rules for Claude — Jane Doe v. Roe Holdings

Boot order for a session on the settlement track:
1. STATUS.md — the narrative. Append-only. The last dated block wins.
2. DONE.md — the ledger. A dated line means done. A line without a date, or an unclear one, means not done.
3. offers.json — the ladder. `chirograph offer list` prints it with each running clock.
4. closing.json — the closing list. `chirograph closing list` prints each task, its date and its state.

Working rules for this matter:
- An offer is OPEN only when the document that made it is on disk and named in the offer. Otherwise it shows UNSOURCED.
- A date goes out with its arithmetic, in one line. `chirograph offer list` and `chirograph closing list` write the lines.
- A closing task moves from one state to the next (BUILT, SIGNED, SERVED, FILED, DONE) only with a file on disk that shows it: a receipt, a sent message saved as .txt, a conformed copy. Without the file the task stays in its state.
- A hearing stays ON CALENDAR until an order or the court's own page, saved to disk, shows it is off.
- When a term or a document is not in the text that was read, say "not found in this text" or "not on this disk".
- muzzles.txt lists words and topics that stay out of a mediation statement. `chirograph statement build` checks the statement against it.
- Decisions about offers belong to the person: the amount, the terms, whether to accept. Print the ladder and the clocks; do not choose.
