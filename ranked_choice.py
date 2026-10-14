#!/usr/bin/env python3
"""Count an instant-runoff election from jerseys.csv."""

import argparse
import csv
import random
import sys
from fractions import Fraction
from pathlib import Path


TIMESTAMP_COLUMN = "Timestamp"
MAX_RANK = 4


def read_ballots(
    csv_path: Path,
) -> tuple[list[tuple[tuple[str, int], ...]], list[str]]:
    ballots: list[tuple[tuple[str, int], ...]] = []
    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise ValueError("The CSV file is empty or missing a header row.")
            reader.fieldnames = [name.strip() for name in reader.fieldnames]
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise ValueError("The CSV header contains duplicate column names.")
            if TIMESTAMP_COLUMN not in reader.fieldnames:
                raise ValueError(f"Missing required column: {TIMESTAMP_COLUMN}")

            candidates = [name for name in reader.fieldnames if name != TIMESTAMP_COLUMN]
            if not candidates:
                raise ValueError("The CSV must contain at least one jersey column.")

            for row_number, row in enumerate(reader, start=2):
                if None in row or any(row[candidate] is None for candidate in candidates):
                    raise ValueError(
                        f"Row {row_number} has a different number of fields "
                        "than the header."
                    )

                ranked: list[tuple[int, str]] = []
                seen_ranks: set[int] = set()
                for candidate in candidates:
                    value = (row[candidate] or "").strip()
                    if not value:
                        continue
                    try:
                        rank = int(value)
                    except ValueError as error:
                        raise ValueError(
                            f"Row {row_number}: rank for {candidate} must be a number from 1 to {MAX_RANK}."
                        ) from error
                    if not 1 <= rank <= MAX_RANK:
                        raise ValueError(
                            f"Row {row_number}: rank for {candidate} must be from 1 to {MAX_RANK}."
                        )
                    if rank in seen_ranks:
                        raise ValueError(f"Row {row_number} assigns rank {rank} more than once.")
                    seen_ranks.add(rank)
                    ranked.append((rank, candidate))

                if ranked:
                    ballots.append(tuple((candidate, rank) for rank, candidate in sorted(ranked)))
    except OSError as error:
        raise ValueError(f"Could not read {csv_path}: {error}") from error
    except csv.Error as error:
        raise ValueError(f"Could not parse {csv_path}: {error}") from error

    if not ballots:
        raise ValueError("The CSV contains no ballots with a ranked jersey.")
    return ballots, candidates


def count_round(
    ballots: list[tuple[tuple[str, int], ...]], active_candidates: set[str]
) -> tuple[dict[str, int], int]:
    tallies = {candidate: 0 for candidate in active_candidates}
    exhausted = 0
    for ballot in ballots:
        for candidate, _ in ballot:
            if candidate in active_candidates:
                tallies[candidate] += 1
                break
        else:
            exhausted += 1
    return tallies, exhausted


def ranked_score(
    ballots: list[tuple[tuple[str, int], ...]], candidate: str
) -> Fraction:
    return sum(
        (
            Fraction(1, 2 ** (rank - 1))
            for ballot in ballots
            for ranked_candidate, rank in ballot
            if ranked_candidate == candidate
        ),
        Fraction(),
    )


def batch_candidates_to_eliminate(tallies: dict[str, int]) -> list[str]:
    ordered = sorted(tallies, key=lambda candidate: (tallies[candidate], candidate))
    batch: list[str] = []
    best_batch: list[str] = []
    batch_votes = 0
    for index, candidate in enumerate(ordered[:-1]):
        batch.append(candidate)
        batch_votes += tallies[candidate]
        if batch_votes < tallies[ordered[index + 1]]:
            best_batch = batch.copy()

    return best_batch


def run_election(
    ballots: list[tuple[tuple[str, int], ...]],
    candidates: list[str],
    batch_elimination: bool = False,
    disqualified_candidates: list[str] | None = None,
) -> str | None:
    active_candidates = set(candidates)
    candidate_lookup = {candidate.casefold(): candidate for candidate in candidates}
    disqualified = {
        candidate_lookup[name.strip().casefold()]
        for name in (disqualified_candidates or [])
        if name.strip().casefold() in candidate_lookup
    }
    unknown_candidates = sorted(
        {
            name.strip()
            for name in (disqualified_candidates or [])
            if name.strip().casefold() not in candidate_lookup
        }
    )
    if unknown_candidates:
        raise ValueError(
            "Unknown disqualified candidate(s): " + ", ".join(unknown_candidates)
        )
    if disqualified:
        print(f"Disqualified: {', '.join(sorted(disqualified))}")
        active_candidates.difference_update(disqualified)
    if not active_candidates:
        print("No winner: all candidates are disqualified.")
        return None

    round_number = 1

    while active_candidates:
        tallies, exhausted = count_round(ballots, active_candidates)
        active_ballots = len(ballots) - exhausted
        print(f"\nRound {round_number} (continuing ballots: {active_ballots})")
        for candidate in sorted(active_candidates):
            print(f"  {candidate}: {tallies[candidate]}")
        if exhausted:
            print(f"  Exhausted: {exhausted}")

        if active_ballots == 0:
            print("\nNo winner: all ballots are exhausted.")
            return None

        majority = active_ballots // 2 + 1
        winner = next(
            (candidate for candidate, votes in tallies.items() if votes >= majority),
            None,
        )
        if winner is not None:
            print(f"\nWinner: {winner}")
            return winner

        if batch_elimination:
            batch = batch_candidates_to_eliminate(tallies)
            if len(batch) > 1:
                eliminated_candidates = ", ".join(sorted(batch))
                print(f"  Batch eliminated: {eliminated_candidates}")
                active_candidates.difference_update(batch)
                round_number += 1
                continue

        lowest_votes = min(tallies.values())
        lowest_candidates = [
            candidate for candidate, votes in tallies.items() if votes == lowest_votes
        ]
        if len(lowest_candidates) > 1:
            scores = {
                candidate: ranked_score(ballots, candidate)
                for candidate in lowest_candidates
            }
            lowest_score = min(scores.values())
            weakest_candidates = [
                candidate
                for candidate, score in scores.items()
                if score == lowest_score
            ]
            print("  Weighted rank scores (1st=1, 2nd=1/2, 3rd=1/4, 4th=1/8):")
            for candidate in sorted(lowest_candidates):
                print(f"    {candidate}: {scores[candidate]}")

            if len(weakest_candidates) > 1:
                eliminated = random.choice(sorted(weakest_candidates))
                print(
                    "  Weighted rank scores are tied; randomly eliminated: "
                    f"{eliminated}"
                )
                active_candidates.remove(eliminated)
            else:
                eliminated = weakest_candidates[0]
                print(f"  Eliminated by weighted rank score: {eliminated}")
                active_candidates.remove(eliminated)

        else:
            eliminated = lowest_candidates[0]
            print(f"  Eliminated: {eliminated}")
            active_candidates.remove(eliminated)
        round_number += 1

    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Determine a ranked-choice winner from jerseys.csv."
    )
    parser.add_argument(
        "csv_file",
        nargs="?",
        type=Path,
        default=Path(__file__).with_name("jerseys.csv"),
        help="CSV path (defaults to jerseys.csv next to this script)",
    )
    parser.add_argument(
        "--batch-elimination",
        action="store_true",
        help=(
            "eliminate the largest lowest-vote group whose combined votes "
            "are less than the next candidate's"
        ),
    )
    parser.add_argument(
        "--disqualify",
        action="append",
        default=[],
        metavar="CANDIDATE",
        help="exclude a candidate before round one; may be specified more than once",
    )
    args = parser.parse_args()

    try:
        ballots, candidates = read_ballots(args.csv_file)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    print(
        f"Counting {len(ballots)} ballot(s) across "
        f"{len(candidates)} jersey option(s)."
    )
    try:
        run_election(
            ballots,
            candidates,
            batch_elimination=args.batch_elimination,
            disqualified_candidates=args.disqualify,
        )
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())