from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cli import build_parser, run_pipeline
from utils.bib_chip_matcher_utils import Athlete


def make_athletes() -> list[Athlete]:
    return [
        Athlete('John', 'Doe', 'M', '1', 'Red'),
        Athlete('Jane', 'Smith', 'F', '2', 'Blue'),
    ]


class CliRunPipelineTests(unittest.TestCase):
    def test_run_pipeline_errors_when_chip_map_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            args = build_parser().parse_args([
                '--chip-map', str(Path(tmpdir) / 'missing.csv'),
                '--sheet-id', 'raw-id',
                '--event-code', 'XC5K',
                '--teams', 'Red,Blue',
                '--output-dir', str(Path(tmpdir) / 'output'),
            ])
            self.assertEqual(run_pipeline(args), 1)

    @patch('cli.read_roster_from_google_sheet')
    def test_run_pipeline_errors_when_no_athletes_remain_after_filtering(self, mock_read) -> None:
        mock_read.return_value = [Athlete('John', 'Doe', 'M', '1', 'Green')]
        with tempfile.TemporaryDirectory() as tmpdir:
            chip_map = Path(tmpdir) / 'chip_map.csv'
            chip_map.write_text('num,tag\nA,111\nB,222\n', encoding='utf-8')

            args = build_parser().parse_args([
                '--chip-map', str(chip_map),
                '--sheet-id', 'raw-id',
                '--event-code', 'XC5K',
                '--teams', 'Red,Blue',
                '--output-dir', str(Path(tmpdir) / 'output'),
            ])
            self.assertEqual(run_pipeline(args), 1)

    @patch('cli.read_roster_from_google_sheet')
    def test_run_pipeline_writes_expected_output_files(self, mock_read) -> None:
        mock_read.return_value = make_athletes()
        with tempfile.TemporaryDirectory() as tmpdir:
            chip_map = Path(tmpdir) / 'chip_map.csv'
            chip_map.write_text('num,tag\nA,111\nB,222\n', encoding='utf-8')
            output_dir = Path(tmpdir) / 'output'

            args = build_parser().parse_args([
                '--chip-map', str(chip_map),
                '--sheet-id', 'raw-id',
                '--event-code', 'XC5K',
                '--teams', 'Blue,Red',
                '--output-dir', str(output_dir),
                '--output-prefix', 'meet',
            ])
            result = run_pipeline(args)

            self.assertEqual(result, 0)
            tag_path = output_dir / 'meet_tag_assignments.txt'
            hytek_path = output_dir / 'meet_hytek_entries.txt'
            self.assertTrue(tag_path.exists())
            self.assertTrue(hytek_path.exists())
            self.assertTrue((output_dir / 'team_assignments.txt').exists())

            with tag_path.open(encoding='utf-8') as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[0], ['Bib Number', 'Chip ID'])
            # Blue is listed first in --teams, so Jane Smith (Blue) is assigned first.
            self.assertEqual(rows[1], ['2', '111'])
            self.assertEqual(rows[2], ['1', '222'])

    @patch('cli.read_roster_from_google_sheet')
    def test_run_pipeline_errors_when_not_enough_chips(self, mock_read) -> None:
        mock_read.return_value = make_athletes()
        with tempfile.TemporaryDirectory() as tmpdir:
            chip_map = Path(tmpdir) / 'chip_map.csv'
            chip_map.write_text('num,tag\nA,111\n', encoding='utf-8')

            args = build_parser().parse_args([
                '--chip-map', str(chip_map),
                '--sheet-id', 'raw-id',
                '--event-code', 'XC5K',
                '--teams', 'Blue,Red',
                '--output-dir', str(Path(tmpdir) / 'output'),
            ])
            with self.assertRaises(ValueError):
                run_pipeline(args)

    def test_build_parser_rejects_teams_and_team_list_file_together(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args([
                '--sheet-id', 'raw-id',
                '--event-code', 'XC5K',
                '--teams', 'Red',
                '--team-list-file', 'input/teams.txt',
            ])


if __name__ == '__main__':
    unittest.main()
