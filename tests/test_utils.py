from __future__ import annotations

import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from utils.bib_chip_matcher_utils import (
    Athlete,
    AssignedAthlete,
    Chip,
    assign_chips_to_athletes,
    compile_team_list,
    extract_team_names_from_sheets,
    field_for_row,
    format_hytek_e_record,
    format_team_code,
    group_athletes_by_team,
    normalize_cell_value,
    normalize_team_name,
    parse_chip_map,
    parse_google_sheet_id,
    read_roster_csv,
    read_roster_from_google_sheet,
    slugify,
    write_hytek_entries,
    write_tag_file,
    write_printable_sheets,
)


class BibChipMatcherUtilsTests(unittest.TestCase):
    def test_normalize_cell_value_empty_and_whitespace(self) -> None:
        self.assertEqual(normalize_cell_value(None), '')
        self.assertEqual(normalize_cell_value('  Hello  '), 'Hello')
        self.assertEqual(normalize_cell_value(2.0), '2')
        self.assertEqual(normalize_cell_value(2.5), '2.5')

    def test_field_for_row_matches_case_insensitive_headers(self) -> None:
        row = {' FIRST ': 'Jane', 'last': 'Doe'}
        value = field_for_row(row, ['first', 'first name'])
        self.assertEqual(value, 'Jane')

    def test_slugify_and_normalize_team_name(self) -> None:
        self.assertEqual(slugify('Team Name!'), 'team_name')
        self.assertEqual(slugify('   '), 'team')
        self.assertEqual(normalize_team_name('  GREEN  team  '), 'Green Team')

    def test_parse_google_sheet_id_accepts_url_and_raw_id(self) -> None:
        url = 'https://docs.google.com/spreadsheets/d/abcd1234/edit#gid=0'
        self.assertEqual(parse_google_sheet_id(url), 'abcd1234')
        self.assertEqual(parse_google_sheet_id('  raw-id-5678  '), 'raw-id-5678')

    def test_parse_chip_map_uses_num_tag_headers_and_ignores_empty_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'chip_map.csv'
            path.write_text('num,tag\nA,111\nB,\n,222\nC,333\n', encoding='utf-8')
            chips = parse_chip_map(path)

        self.assertEqual(len(chips), 2)
        self.assertEqual(chips[0], Chip(label='A', chip_id='111'))
        self.assertEqual(chips[1], Chip(label='C', chip_id='333'))

    def test_parse_chip_map_raises_for_empty_file_or_headerless_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'chip_map.csv'
            path.write_text('', encoding='utf-8')
            with self.assertRaises(ValueError):
                parse_chip_map(path)

    def test_parse_chip_map_raises_when_file_has_only_one_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'chip_map.csv'
            path.write_text('num\nA\nB\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                parse_chip_map(path)

    def test_parse_chip_map_keeps_duplicate_labels_and_ids_as_separate_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'chip_map.csv'
            path.write_text('num,tag\nA,111\nA,111\nB,222\n', encoding='utf-8')
            chips = parse_chip_map(path)

        # parse_chip_map performs no de-duplication; every non-empty row is kept.
        self.assertEqual(chips, [Chip(label='A', chip_id='111'), Chip(label='A', chip_id='111'), Chip(label='B', chip_id='222')])

    def test_read_roster_csv_parses_expected_columns_and_extra_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'roster.csv'
            path.write_text(
                'Team,First,Last,Bib,Gender,Birth Date,School Year,Initial,Team Code,Notes\n'
                'Blue,John,Doe,10,M,2005-01-01,12,A,BLU,Needs chip 123\n',
                encoding='utf-8-sig',
            )

            athletes = read_roster_csv(path)

        self.assertEqual(len(athletes), 1)
        athlete = athletes[0]
        self.assertEqual(athlete.team_name, 'Blue')
        self.assertEqual(athlete.first_name, 'John')
        self.assertEqual(athlete.last_name, 'Doe')
        self.assertEqual(athlete.gender, 'M')
        self.assertEqual(athlete.competitor_number, '10')
        self.assertEqual(athlete.team_code, 'BLU')
        self.assertEqual(athlete.birth_date, '2005-01-01')
        self.assertEqual(athlete.school_year, '12')
        self.assertEqual(athlete.initial, 'A')
        self.assertEqual(athlete.extra, {'Notes': 'Needs chip 123'})

    def test_read_roster_csv_raises_on_missing_competitor_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'roster.csv'
            path.write_text('Team,First,Last,Bib\nBlue,John,Doe,\n', encoding='utf-8-sig')
            with self.assertRaises(ValueError):
                read_roster_csv(path)

    def test_read_roster_csv_skips_rows_missing_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'roster.csv'
            path.write_text('Team,First,Last,Bib\nBlue,,,\n', encoding='utf-8-sig')
            with self.assertRaises(ValueError):
                read_roster_csv(path)

    def test_compile_team_list_inline_overrides_file_and_handles_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / 'teams.txt'
            file_path.write_text('Alpha\nBeta\n', encoding='utf-8-sig')
            self.assertEqual(compile_team_list(str(file_path), 'Gamma,Delta'), ['Gamma', 'Delta'])
            self.assertEqual(compile_team_list(str(file_path), None), ['Alpha', 'Beta'])
            with self.assertRaises(FileNotFoundError):
                compile_team_list(str(file_path.with_name('missing.txt')), None)

    def test_extract_team_names_from_sheets_returns_unique_normalized_names(self) -> None:
        sheets = {
            'Sheet1': pd.DataFrame([
                [None, '  Alpha Team  '],
                [None, 'A1'],
                ['First', 'Last', 'Bib'],
                ['Joe', 'Smith', '1'],
            ]),
            'Sheet2': pd.DataFrame([
                [None, 'alpha   team'],
                [None, 'A2'],
                ['First', 'Last', 'Bib'],
                ['Jane', 'Doe', '2'],
            ]),
            'Sheet3': pd.DataFrame([
                [None, 'Hello! Welcome to the 2026 XC Season Bib Sheet'],
                [None, ''],
                ['First', 'Last', 'Bib'],
                ['Mike', 'Green', '3'],
            ]),
            'Sheet4': pd.DataFrame([[None, None], [None, None]]),
        }

        teams = extract_team_names_from_sheets(sheets)
        self.assertEqual(teams, ['Alpha Team'])

    def test_group_athletes_by_team_uses_provided_order_and_preserves_remaining(self) -> None:
        athletes = [
            Athlete('John', 'Doe', 'M', '1', 'Red'),
            Athlete('Jane', 'Smith', 'F', '2', 'Blue'),
            Athlete('Bob', 'Brown', 'M', '3', 'Green'),
        ]
        grouped = group_athletes_by_team(athletes, ['Green', 'Red'])
        self.assertEqual([team for team, _ in grouped], ['Green', 'Red', 'Blue'])
        self.assertEqual([a.competitor_number for a in grouped[0][1]], ['3'])

    def test_assign_chips_to_athletes_assigns_in_team_order_and_raises_for_insufficient_chips(self) -> None:
        athletes = [
            Athlete('John', 'Doe', 'M', '1', 'Red'),
            Athlete('Jane', 'Smith', 'F', '2', 'Blue'),
        ]
        chips = [Chip('A', '111'), Chip('B', '222')]
        assigned = assign_chips_to_athletes(athletes, chips, ['Blue', 'Red'])
        self.assertEqual([a.chip_label for a in assigned], ['A', 'B'])
        self.assertEqual([a.chip_id for a in assigned], ['111', '222'])
        self.assertEqual([a.chip_index for a in assigned], [1, 2])

        with self.assertRaises(ValueError):
            assign_chips_to_athletes(athletes, [Chip('A', '111')], None)

    def test_format_team_code_and_hytek_e_record_output(self) -> None:
        self.assertEqual(format_team_code('Green Team'), 'GREE')
        self.assertEqual(format_team_code('!!!'), 'UNA')
        athlete = AssignedAthlete(
            first_name='John',
            last_name='Doe',
            gender='M',
            competitor_number='99',
            team_name='Green Team',
            team_code='GRN',
            birth_date='2005-05-05',
            school_year='12',
            initial='A',
            chip_label='X1',
            chip_id='ABC',
            chip_index=1,
        )
        record = format_hytek_e_record(athlete, 'XC5K', 'M')
        self.assertTrue(record.startswith('D;Doe;John;A;M;2005-05-05;GRN;Green Team;;12;XC5K;'))
        self.assertIn(';99;', record)

    def test_format_hytek_e_record_leaves_blank_fields_empty_when_optional_data_missing(self) -> None:
        athlete = AssignedAthlete(
            first_name='John',
            last_name='Doe',
            gender='',
            competitor_number='5',
            team_name='Red',
            chip_label='X',
            chip_id='1',
        )
        record = format_hytek_e_record(athlete, 'XC5K', 'M')
        fields = record.split(';')
        self.assertEqual(len(fields), 16)
        self.assertEqual(fields, ['D', 'Doe', 'John', '', '', '', '', 'Red', '', '', 'XC5K', '', 'M', '', '5', ''])

    def test_format_hytek_e_record_does_not_escape_semicolons_in_name_fields(self) -> None:
        # A semicolon inside a name shifts every subsequent field, since the
        # record is joined with ';' and no escaping/quoting is applied.
        athlete = AssignedAthlete(
            first_name='Jo;Ann',
            last_name='Doe',
            gender='F',
            competitor_number='5',
            team_name='Red',
            chip_label='X',
            chip_id='1',
        )
        record = format_hytek_e_record(athlete, 'XC5K', 'M')
        fields = record.split(';')
        self.assertEqual(len(fields), 17)
        # The semicolon in the first name pushed every later field one slot to
        # the right, so competitor_number ('5') lands at index 15 instead of 14.
        self.assertEqual(fields[2:4], ['Jo', 'Ann'])
        self.assertEqual(fields[15], '5')

    def test_write_tag_file_hytek_entries_and_printable_sheets(self) -> None:
        assigned = [
            AssignedAthlete('John', 'Doe', 'M', '1', 'Red', chip_label='A', chip_id='111'),
            AssignedAthlete('Jane', 'Smith', 'F', '2', 'Red', chip_label='B', chip_id='222'),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            tag_path = base / 'tag_output.txt'
            hytek_path = base / 'hytek_output.txt'
            output_dir = base / 'printables'

            write_tag_file(tag_path, assigned)
            write_hytek_entries(hytek_path, assigned, 'XC5K', 'M')
            write_printable_sheets(output_dir, assigned, 'XC5K')

            self.assertTrue(tag_path.exists())
            self.assertTrue(hytek_path.exists())
            self.assertTrue((output_dir / 'team_assignments.txt').exists())
            self.assertTrue((output_dir / 'red_assignments.txt').exists())
            self.assertTrue((output_dir / 'team_assignments.pdf').exists())

            with tag_path.open(encoding='utf-8') as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[0], ['Bib Number', 'Chip ID'])
            self.assertEqual(rows[1], ['1', '111'])
            self.assertEqual(rows[2], ['2', '222'])

            with hytek_path.open(encoding='utf-8') as handle:
                lines = handle.read().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertTrue(lines[0].startswith('D;Doe;John;'))

            with (output_dir / 'red_assignments.txt').open(encoding='utf-8') as handle:
                content = handle.read()
            self.assertIn('Team: Red', content)
            self.assertIn('Doe', content)
            self.assertIn('Smith', content)

    @patch('utils.bib_chip_matcher_utils.download_google_sheet_xlsx')
    def test_read_roster_from_google_sheet_parses_sheets_and_filters_teams(self, mock_download):
        mock_download.return_value = {
            'Alpha': pd.DataFrame([
                [None, 'Alpha Team'],
                [None, 'A1'],
                ['First', 'Last', 'Bib', 'Gender', 'Team Code'],
                ['Joe', 'Smith', '10', 'M', 'ALP'],
                ['Jane', 'Doe', '', 'F', 'ALP'],
            ]),
            'Beta': pd.DataFrame([
                [None, 'Beta Club'],
                [None, 'B2'],
                ['First', 'Last', 'Bib', 'Gender'],
                ['Ann', 'White', '11', 'F'],
            ]),
        }

        athletes = read_roster_from_google_sheet('raw-id', selected_teams=['Beta Club'])
        self.assertEqual(len(athletes), 1)
        self.assertEqual(athletes[0].team_name, 'Beta Club')
        self.assertEqual(athletes[0].competitor_number, '11')

        with self.assertRaises(ValueError):
            read_roster_from_google_sheet('raw-id', selected_teams=['Alpha Team'])

    @patch('utils.bib_chip_matcher_utils.download_google_sheet_xlsx')
    def test_read_roster_from_google_sheet_raises_on_missing_competitor_number(self, mock_download):
        mock_download.return_value = {
            'Alpha': pd.DataFrame([
                [None, 'Alpha Team'],
                [None, 'A1'],
                ['First', 'Last', 'Bib'],
                ['Joe', 'Smith', '', 'M'],
            ]),
        }
        with self.assertRaises(ValueError):
            read_roster_from_google_sheet('raw-id')


if __name__ == '__main__':
    unittest.main()
