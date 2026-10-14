import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ranked_choice import read_ballots, run_election


class RankedChoiceTests(unittest.TestCase):
    def write_ballots(self, rows: list[list[str]]) -> Path:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        csv_path = Path(temporary_directory.name) / "ballots.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            csv.writer(csv_file).writerows(rows)
        return csv_path

    def test_winner_is_found_after_candidate_is_eliminated(self) -> None:
        csv_path = self.write_ballots(
            [
                ["Timestamp", "[OPTION A]", "[OPTION B]", "[OPTION C]"],
                ["t1", "1", "2", ""],
                ["t2", "1", "2", ""],
                ["t3", "2", "1", ""],
                ["t4", "", "2", "1"],
                ["t5", "", "2", "1"],
            ]
        )
        ballots, candidates = read_ballots(csv_path)

        with patch("builtins.print") as output:
            winner = run_election(ballots, candidates)

        self.assertEqual(winner, "[OPTION A]")
        self.assertIn(
            "  Eliminated: [OPTION B]",
            [call.args[0] for call in output.call_args_list],
        )

    def test_tied_weighted_scores_are_broken_randomly(self) -> None:
        csv_path = self.write_ballots(
            [
                ["Timestamp", "[OPTION A]", "[OPTION B]"],
                ["t1", "1", ""],
                ["t2", "", "1"],
            ]
        )
        ballots, candidates = read_ballots(csv_path)

        with (
            patch("builtins.print") as output,
            patch("ranked_choice.random.choice", return_value="[OPTION B]") as choose,
        ):
            winner = run_election(ballots, candidates)

        self.assertEqual(winner, "[OPTION A]")
        choose.assert_called_once_with(["[OPTION A]", "[OPTION B]"])
        self.assertIn(
            "  Weighted rank scores are tied; randomly eliminated: [OPTION B]",
            [call.args[0] for call in output.call_args_list],
        )

    def test_weighted_rank_score_breaks_a_vote_tie(self) -> None:
        csv_path = self.write_ballots(
            [
                ["Timestamp", "[OPTION A]", "[OPTION B]", "[OPTION C]"],
                ["t1", "1", "2", ""],
                ["t2", "2", "1", ""],
                ["t3", "2", "", "1"],
                ["t4", "2", "", "1"],
            ]
        )
        ballots, candidates = read_ballots(csv_path)

        with patch("builtins.print") as output:
            winner = run_election(ballots, candidates)

        output_lines = [call.args[0] for call in output.call_args_list]
        self.assertEqual(winner, "[OPTION A]")
        self.assertIn("    [OPTION B]: 3/2", output_lines)
        self.assertIn(
            "  Eliminated by weighted rank score: [OPTION B]",
            output_lines,
        )

    def test_batch_elimination_removes_combined_lowest_candidates(self) -> None:
        csv_path = self.write_ballots(
            [
                [
                    "Timestamp",
                    "[OPTION A]",
                    "[OPTION B]",
                    "[OPTION C]",
                    "[OPTION D]",
                ],
                ["t1", "1", "", "2", ""],
                ["t2", "", "1", "", "2"],
                ["t3", "", "", "1", ""],
                ["t4", "", "", "1", ""],
                ["t5", "", "", "1", ""],
                ["t6", "", "", "", "1"],
                ["t7", "", "", "", "1"],
                ["t8", "", "", "", "1"],
            ]
        )
        ballots, candidates = read_ballots(csv_path)

        with (
            patch("builtins.print") as output,
            patch("ranked_choice.random.choice", return_value="[OPTION D]"),
        ):
            winner = run_election(ballots, candidates, batch_elimination=True)

        output_lines = [call.args[0] for call in output.call_args_list]
        self.assertEqual(winner, "[OPTION C]")
        self.assertIn(
            "  Batch eliminated: [OPTION A], [OPTION B]",
            output_lines,
        )

    def test_disqualified_candidate_votes_transfer_to_next_rank(self) -> None:
        csv_path = self.write_ballots(
            [
                ["Timestamp", "[OPTION A]", "[OPTION B]", "[OPTION C]"],
                ["t1", "1", "2", ""],
                ["t2", "1", "", "2"],
                ["t3", "2", "1", ""],
            ]
        )
        ballots, candidates = read_ballots(csv_path)

        with patch("builtins.print") as output:
            winner = run_election(
                ballots,
                candidates,
                disqualified_candidates=["[option a]"],
            )

        output_lines = [call.args[0] for call in output.call_args_list]
        self.assertEqual(winner, "[OPTION B]")
        self.assertIn("Disqualified: [OPTION A]", output_lines)
        self.assertIn("  [OPTION B]: 2", output_lines)

    def test_unknown_disqualified_candidate_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown disqualified candidate"):
            run_election([], ["[OPTION A]"], disqualified_candidates=["[OPTION Z]"])

    def test_duplicate_candidate_on_ballot_is_rejected(self) -> None:
        csv_path = self.write_ballots(
            [
                ["Timestamp", "[OPTION A]", "[OPTION B]"],
                ["t1", "1", "1"],
            ]
        )

        with self.assertRaisesRegex(ValueError, "assigns rank 1 more than once"):
            read_ballots(csv_path)


if __name__ == "__main__":
    unittest.main()
