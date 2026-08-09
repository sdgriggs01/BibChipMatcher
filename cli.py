#!/usr/bin/env python3
"""Bib chip matcher CLI for HyTek entry generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from utils.bib_chip_matcher_utils import (
    assign_chips_to_athletes,
    compile_team_list,
    normalize_team_name,
    parse_chip_map,
    read_roster_from_google_sheet,
    write_hytek_entries,
    write_printable_sheets,
    write_tag_file,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Assign bib numbers to chips and generate HyTek E records for team entries.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('--chip-map', default='input/chipLabel_chipID_map.txt', help='CSV file mapping chip label to chip ID')
    parser.add_argument('--sheet-id', required=True, help='Google spreadsheet ID or URL')
    parser.add_argument('--sheet-gid', help='Optional Google sheet gid to select a specific worksheet')
    team_group = parser.add_mutually_exclusive_group()
    team_group.add_argument('--teams', help='Comma-separated list of participating team names, in assignment order')
    team_group.add_argument('--team-list-file', help='Optional file containing participating team names, one per line')
    parser.add_argument('--output-dir', default='output', help='Directory for generated output files')
    parser.add_argument('--output-prefix', default='meet', help='Optional output file prefix')
    parser.add_argument('--event-code', required=True, help='HyTek event code for the meet (for example 5000 or XC5K)')
    parser.add_argument('--event-measure', default='M', choices=['M', 'E'], help='HyTek event measure code')
    return parser


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def run_pipeline(args: argparse.Namespace) -> int:
    chip_path = Path(args.chip_map)
    if not chip_path.exists():
        print(f'Error: chip map file not found: {chip_path}', file=sys.stderr)
        return 1

    chips = parse_chip_map(chip_path)
    team_list_file = args.team_list_file if args.team_list_file is not None else 'input/teams.txt'
    teams = compile_team_list(team_list_file if not args.teams else None, args.teams)

    athletes = read_roster_from_google_sheet(args.sheet_id, args.sheet_gid, teams)

    if teams:
        selected_normalized = {normalize_team_name(t) for t in teams}
        athletes = [ath for ath in athletes if normalize_team_name(ath.team_name) in selected_normalized]
        if not athletes:
            print('Error: no athletes remain after filtering with the selected teams.', file=sys.stderr)
            return 1

    assigned = assign_chips_to_athletes(athletes, chips, teams)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tag_output = output_dir / f'{args.output_prefix}_tag_assignments.txt'
    hytek_output = output_dir / f'{args.output_prefix}_hytek_entries.txt'
    write_tag_file(tag_output, assigned)
    write_hytek_entries(hytek_output, assigned, args.event_code, args.event_measure)
    write_printable_sheets(output_dir, assigned, args.event_code)

    print(f'Wrote {tag_output}')
    print(f'Wrote {hytek_output}')
    print(f'Wrote printable team sheets to {output_dir}')
    return 0


def main() -> int:
    return run_pipeline(parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
