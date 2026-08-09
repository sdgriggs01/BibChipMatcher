from __future__ import annotations

import unittest

import pandas as pd

from utils.bib_chip_matcher_utils import extract_team_names_from_sheets


class TeamSelectionTests(unittest.TestCase):
    def test_extract_team_names_from_sheets_returns_unique_team_names(self) -> None:
        sheets = {
            'Team A': pd.DataFrame([
                [None, 'Team A'],
                [None, 'ABC'],
                ['First', 'Last', 'Bib'],
                ['A', 'B', '1'],
            ]),
            'Team B': pd.DataFrame([
                [None, 'Team B'],
                [None, 'XYZ'],
                ['First', 'Last', 'Bib'],
                ['C', 'D', '2'],
            ]),
            'Duplicate': pd.DataFrame([
                [None, 'Team A'],
                [None, 'ABC'],
                ['First', 'Last', 'Bib'],
                ['E', 'F', '3'],
            ]),
        }

        teams = extract_team_names_from_sheets(sheets)

        self.assertEqual(teams, ['Team A', 'Team B'])


if __name__ == '__main__':
    unittest.main()
