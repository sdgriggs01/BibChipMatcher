from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from utils.gui_support import (
    build_cli_args,
    build_settings_payload,
    read_settings_cache,
    write_settings_cache,
)


class BuildSettingsPayloadTests(unittest.TestCase):
    def test_strips_whitespace_and_preserves_selected_teams_order(self) -> None:
        payload = build_settings_payload(
            sheet_id='  raw-id  ',
            chip_map=' input/chipLabel_chipID_map.txt ',
            sheet_gid=' 123 ',
            output_dir=' output ',
            output_prefix=' meet ',
            event_code=' 5000 ',
            event_measure=' M ',
            selected_teams=['Blue', 'Red'],
        )
        self.assertEqual(
            payload,
            {
                'sheet-id': 'raw-id',
                'chip-map': 'input/chipLabel_chipID_map.txt',
                'sheet-gid': '123',
                'output-dir': 'output',
                'output-prefix': 'meet',
                'event-code': '5000',
                'event-measure': 'M',
                'selected-teams': ['Blue', 'Red'],
            },
        )


class SettingsCacheRoundTripTests(unittest.TestCase):
    def test_write_then_read_round_trips_the_payload(self) -> None:
        payload = build_settings_payload(
            sheet_id='raw-id',
            chip_map='chips.csv',
            sheet_gid='',
            output_dir='output',
            output_prefix='',
            event_code='5000',
            event_measure='M',
            selected_teams=['Green Hope'],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / 'nested' / 'settings.json'
            write_settings_cache(cache_path, payload)
            self.assertTrue(cache_path.exists())
            self.assertEqual(read_settings_cache(cache_path), payload)

    def test_read_settings_cache_returns_none_when_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / 'settings.json'
            self.assertIsNone(read_settings_cache(cache_path))

    def test_read_settings_cache_returns_none_for_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / 'settings.json'
            cache_path.write_text('{not valid json', encoding='utf-8')
            self.assertIsNone(read_settings_cache(cache_path))


class BuildCliArgsTests(unittest.TestCase):
    def test_omits_blank_values(self) -> None:
        args = build_cli_args(
            chip_map='input/chipLabel_chipID_map.txt',
            sheet_id='raw-id',
            sheet_gid='',
            teams='Blue,Red',
            output_dir='output',
            output_prefix='',
            event_code='5000',
            event_measure='M',
        )
        self.assertEqual(
            args,
            [
                '--chip-map', 'input/chipLabel_chipID_map.txt',
                '--sheet-id', 'raw-id',
                '--teams', 'Blue,Red',
                '--output-dir', 'output',
                '--event-code', '5000',
                '--event-measure', 'M',
            ],
        )

    def test_result_is_parseable_by_the_cli_argument_parser(self) -> None:
        from cli import build_parser

        args = build_cli_args(
            chip_map='chips.csv',
            sheet_id='raw-id',
            sheet_gid='123',
            teams='Blue,Red',
            output_dir='output',
            output_prefix='meet',
            event_code='5000',
            event_measure='M',
        )
        parsed = build_parser().parse_args(args)
        self.assertEqual(parsed.sheet_id, 'raw-id')
        self.assertEqual(parsed.teams, 'Blue,Red')
        self.assertEqual(parsed.sheet_gid, '123')


if __name__ == '__main__':
    unittest.main()
