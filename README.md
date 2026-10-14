# Ranked-choice election script

`ranked_choice.py` counts an instant-runoff (ranked-choice) election using up to
four preferences per ballot. It uses only the Python standard library.

## `jerseys.csv` schema

`jerseys.csv` contains one ballot per row. It uses a column for the timestamp
and one column for each jersey option:

| Column | Meaning | Value |
| --- | --- | --- |
| `Timestamp` | Submission time | Ignored by the count |
| `[OPTION A]`, `[OPTION B]`, etc. | Jersey candidates | Rank `1` through `4`, or blank |

The rank number in a jersey's column indicates that ballot's preference; `1` is
the first choice. A voter can rank up to four jerseys. Blank cells are allowed,
and a row with no ranked jersey is ignored. A ballot cannot assign the same
rank to multiple jerseys.

Example:

```csv
Timestamp,[OPTION A],[OPTION B],[OPTION C]
10/13/2026 13:28:40,,2,1
10/13/2026 13:34:28,1,,3
```

The actual jersey columns in `jerseys.csv` are used as the candidate names.

## Run

```sh
python ranked_choice.py
```

The script defaults to `jerseys.csv` in the same folder. You can provide a
different CSV path as an argument.

To enable batch elimination, run:

```sh
python ranked_choice.py --batch-elimination
```

In batch mode, the script eliminates the largest group of lowest-vote
candidates whose combined vote total is strictly less than the next
candidate's vote total. If there is no such group of two or more candidates,
the normal single-candidate elimination and tie-break rules apply.

To disqualify a jersey before round one and transfer those ballots to their
next active ranked jersey, run:

```sh
python ranked_choice.py --disqualify "[OPTION A]"
```

You can specify `--disqualify` more than once. Disqualified options are
excluded from the initial count; ballots transfer to their next ranked
non-disqualified option, or become exhausted if none remains. Batch
elimination can be combined with disqualification.

The script prints each round's vote totals, eliminates the lowest candidate,
and declares a winner upon reaching a majority of non-exhausted ballots.
Options tied at zero votes are eliminated together because they have no ballots
to transfer. If candidates tie for elimination, their weighted rank scores
across all ballots are compared: first choice is worth `1`, second `1/2`, third
`1/4`, and fourth `1/8`. The candidate with the lower score is eliminated. If
their weighted scores are still tied, one of the tied candidates is chosen
randomly for elimination. Ballots with no
remaining ranked jersey become exhausted and are excluded from the majority
threshold.
