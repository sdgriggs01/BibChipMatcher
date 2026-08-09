#!/usr/bin/env python3
"""Utility functions for the Bib chip matcher CLI."""

from __future__ import annotations

import csv
import io
import re
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import pandas as pd
import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


@dataclass
class Chip:
    """Represents a single timing chip label-to-ID mapping.

    Attributes:
        label (str): The chip label used in the assignment process.
        chip_id (str): The identifier associated with the chip label.
    """

    label: str
    chip_id: str


@dataclass
class Athlete:
    """Represents an athlete loaded from a roster source.

    Attributes:
        first_name (str): Athlete's first name.
        last_name (str): Athlete's last name.
        gender (str): Gender value as supplied by the roster.
        competitor_number (str): Bib number or competitor number.
        team_name (str): Team name associated with the athlete.
        team_code (Optional[str]): Optional team code from the roster.
        birth_date (Optional[str]): Optional birth date string.
        school_year (Optional[str]): Optional school year or grade string.
        initial (Optional[str]): Optional middle initial.
        extra (Dict[str, str]): Additional roster columns not otherwise modeled.
    """

    first_name: str
    last_name: str
    gender: str
    competitor_number: str
    team_name: str
    team_code: Optional[str] = None
    birth_date: Optional[str] = None
    school_year: Optional[str] = None
    initial: Optional[str] = None
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass
class AssignedAthlete:
    """Represents an athlete after a chip has been assigned.

    Attributes:
        first_name (str): Athlete's first name.
        last_name (str): Athlete's last name.
        gender (str): Gender value as supplied by the roster.
        competitor_number (str): Bib number or competitor number.
        team_name (str): Team name associated with the athlete.
        team_code (Optional[str]): Optional team code from the roster.
        birth_date (Optional[str]): Optional birth date string.
        school_year (Optional[str]): Optional school year or grade string.
        initial (Optional[str]): Optional middle initial.
        extra (Dict[str, str]): Additional roster columns not otherwise modeled.
        chip_label (str): The assigned chip label.
        chip_id (str): The assigned chip ID.
        chip_index (int): One-based index of the assignment order.
    """

    first_name: str
    last_name: str
    gender: str
    competitor_number: str
    team_name: str
    team_code: Optional[str] = None
    birth_date: Optional[str] = None
    school_year: Optional[str] = None
    initial: Optional[str] = None
    extra: Dict[str, str] = field(default_factory=dict)
    chip_label: str = ''
    chip_id: str = ''
    chip_index: int = 0


def parse_chip_map(path: Path) -> List[Chip]:
    """Load chip label-to-chip ID mappings from a CSV file.

    Args:
        path (Path): Path to a CSV file containing chip label/chip ID rows.
            The file must include a header row; if the headers contain ``num`` and
            ``tag`` then those columns are used, otherwise the first two columns
            are used.

    Returns:
        List[Chip]: A list of Chip objects for every non-empty row with a label
            and chip ID.

    Assumptions:
        The file is UTF-8 encoded and comma-delimited. Rows with blank labels or
        chip IDs are ignored, and at least one valid mapping row must exist or a
        ValueError is raised.
    """
    with path.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"Chip map file '{path}' has no header row")

        normalized = [name.strip().lower() for name in reader.fieldnames]
        if 'num' in normalized and 'tag' in normalized:
            label_field = reader.fieldnames[normalized.index('num')]
            chip_field = reader.fieldnames[normalized.index('tag')]
        elif len(reader.fieldnames) >= 2:
            label_field, chip_field = reader.fieldnames[0], reader.fieldnames[1]
        else:
            raise ValueError(f"Chip map file '{path}' needs at least two columns")

        chips: List[Chip] = []
        for row in reader:
            label = row.get(label_field, '').strip()
            chip_id = row.get(chip_field, '').strip()
            if label and chip_id:
                chips.append(Chip(label=label, chip_id=chip_id))
        if not chips:
            raise ValueError(f"No valid chip rows found in '{path}'")
        return chips


def make_candidate_names() -> Dict[str, Tuple[str, ...]]:
    """Return common header name variants for roster fields.

    Returns:
        Dict[str, Tuple[str, ...]]: A mapping of logical field names, such as
            ``team_name`` and ``competitor_number``, to accepted header aliases.

    Assumptions:
        Header matching is case-insensitive and whitespace-insensitive against
        the raw roster column names.
    """
    return {
        'team_name': ('team', 'team name', 'team_name', 'teamname', 'club', 'school'),
        'team_code': ('team code', 'team_code', 'teamcode', 'code'),
        'first_name': ('first', 'first name', 'first_name', 'fname', 'given name', 'given_name'),
        'last_name': ('last', 'last name', 'last_name', 'lname', 'surname', 'family name'),
        'gender': ('gender', 'gender (m/f)', 'sex'),
        'competitor_number': ('bib', 'bib number', 'bib_number', 'competitor number', 'comp #', 'competitor', 'number', 'comp_number'),
        'birth_date': ('birth date', 'birth_date', 'dob', 'birthdate', 'birthday'),
        'school_year': ('school year', 'school_year', 'year', 'grade'),
        'initial': ('initial', 'middle initial', 'mi'),
    }


def normalize_cell_value(value: Any) -> str:
    """Normalize a cell value from pandas or CSV into a string.

    Args:
        value (Any): A value extracted from a pandas DataFrame, CSV row, or other
            Python object.

    Returns:
        str: A stripped string representation of the value. Whole-number floats
            are converted to their integer string form.

    Assumptions:
        ``None`` is treated as an empty string, and surrounding whitespace is
        removed from string values.
    """
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def field_for_row(row: Dict[str, Any], candidates: Sequence[str]) -> Optional[str]:
    """Find a matching value from a row using candidate header names.

    Args:
        row (Dict[str, Any]): A mapping of column/header names to cell values.
        candidates (Sequence[str]): Candidate header names to match, in priority
            order.

    Returns:
        Optional[str]: The normalized value from the first matching header, or
            ``None`` if no candidate matches.

    Assumptions:
        Matching is case-insensitive and whitespace-insensitive, and the row may
        contain string-like or non-string keys.
    """
    for candidate in candidates:
        for key in row.keys():
            if key is None:
                continue
            if str(key).strip().lower() == candidate.strip().lower():
                return normalize_cell_value(row.get(key))
    return None


def read_roster_csv(path: Path) -> List[Athlete]:
    """Read athlete roster records from a local CSV file.

    Args:
        path (Path): Path to a CSV roster file with a header row.

    Returns:
        List[Athlete]: Athletes parsed from the file.

    Assumptions:
        The file contains headers for team, first/last name, and competitor
        number, with optional gender, birth date, school year, initial, and team
        code columns. Rows missing both first and last names are skipped, and
        rows missing a competitor number raise a ValueError.
    """
    with path.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"Roster file '{path}' has no header row")

        candidates = make_candidate_names()
        athletes: List[Athlete] = []
        for row in reader:
            team_name = field_for_row(row, candidates['team_name']) or 'Unknown'
            first_name = field_for_row(row, candidates['first_name']) or ''
            last_name = field_for_row(row, candidates['last_name']) or ''
            if not first_name or not last_name:
                continue
            competitor_number = field_for_row(row, candidates['competitor_number']) or ''
            if not competitor_number:
                raise ValueError(f"Missing competitor number for athlete {first_name} {last_name} in '{path}'")
            gender = field_for_row(row, candidates['gender']) or ''
            birth_date = field_for_row(row, candidates['birth_date']) or None
            school_year = field_for_row(row, candidates['school_year']) or None
            initial = field_for_row(row, candidates['initial']) or None
            team_code = field_for_row(row, candidates['team_code']) or None
            athletes.append(
                Athlete(
                    first_name=first_name,
                    last_name=last_name,
                    gender=gender.upper() if gender else '',
                    competitor_number=str(competitor_number).strip(),
                    team_name=team_name.strip(),
                    team_code=team_code.strip() if team_code else None,
                    birth_date=birth_date,
                    school_year=school_year,
                    initial=initial,
                    extra={k: v.strip() for k, v in row.items() if k and k.strip().lower() not in set().union(*candidates.values()) and v.strip()},
                )
            )
        if not athletes:
            raise ValueError(f"No athletes were parsed from roster file '{path}'")
        return athletes


def parse_google_sheet_id(spreadsheet_url_or_id: str) -> str:
    """Extract the Google Sheets document ID from a URL or accept a raw ID.

    Args:
        spreadsheet_url_or_id (str): A Google Sheets URL or a raw spreadsheet ID.

    Returns:
        str: The extracted document ID when a URL is provided; otherwise the
            trimmed raw input.

    Assumptions:
        The function recognizes Google Sheets URLs that use the ``/d/<id>``
        pattern. Other strings are passed through unchanged after trimming.
    """
    parsed = urlparse(spreadsheet_url_or_id)
    if parsed.netloc.endswith('docs.google.com'):
        match = re.search(r'/d/([^/]+)', parsed.path)
        if match:
            return match.group(1)
    return spreadsheet_url_or_id.strip()


def download_google_sheet_xlsx(spreadsheet_id: str, sheet_gid: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """Download a Google Sheet XLSX export and parse it into DataFrames.

    Args:
        spreadsheet_id (str): The Google Sheets document ID to export.
        sheet_gid (Optional[str]): Optional worksheet ID used to target a
            specific sheet within the workbook.

    Returns:
        Dict[str, pd.DataFrame]: A mapping of sheet names to pandas DataFrames.

    Assumptions:
        The spreadsheet is publicly accessible and the export endpoint can be
        reached over the network. A ValueError is raised if the download or
        XLSX parsing fails.
    """
    export_url = f'https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=xlsx'
    if sheet_gid:
        export_url += f'&gid={sheet_gid}'
    try:
        response = requests.get(export_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f'Unable to download Google Sheet XLSX export: {exc}') from exc

    try:
        return pd.read_excel(io.BytesIO(response.content), sheet_name=None, header=None)
    except Exception as exc:
        raise ValueError(f'Unable to parse downloaded spreadsheet as XLSX: {exc}') from exc


def read_roster_from_google_sheet(spreadsheet_id_or_url: str, sheet_gid: Optional[str] = None, selected_teams: Optional[List[str]] = None) -> List[Athlete]:
    """Read athlete roster records from a Google Sheet.

    Args:
        spreadsheet_id_or_url (str): A Google Sheets document ID or URL.
        sheet_gid (Optional[str]): Optional worksheet ID for a single sheet.
        selected_teams (Optional[List[str]]): Optional team names to filter the
            roster to before parsing.

    Returns:
        List[Athlete]: Athletes parsed from the requested worksheet(s).

    Assumptions:
        The workbook is expected to follow the existing layout: row 3 contains
        headers, row 0/1 contain the team name/code, and athlete data begins on
        row 4. Team filtering is normalized using the title-cased team name, and
        missing competitor numbers raise a ValueError.
    """
    spreadsheet_id = parse_google_sheet_id(spreadsheet_id_or_url)
    sheets = download_google_sheet_xlsx(spreadsheet_id, sheet_gid)

    candidates = make_candidate_names()
    normalized_selected = {normalize_team_name(team) for team in selected_teams} if selected_teams else None

    athletes: List[Athlete] = []
    for sheet_name, df in sheets.items():
        if df.empty or len(df) < 4:
            continue

        df = df.where(pd.notna(df), None)
        team_name = ''
        if df.shape[1] > 1:
            team_name = normalize_cell_value(df.iat[0, 1])
            team_code = normalize_cell_value(df.iat[1, 1]) or None
        else:
            team_name = normalize_cell_value(df.iat[0, 0])
            team_code = None

        if not team_name:
            team_name = 'Unknown'

        if normalized_selected and normalize_team_name(team_name) not in normalized_selected:
            continue

        headers = [normalize_cell_value(value) for value in df.iloc[2].tolist()]
        if not any(headers):
            raise ValueError(f"Sheet '{sheet_name}' does not contain athlete headers on row 3")

        ignored_headers = {
            value.strip().lower()
            for values in candidates.values()
            for value in values
        }

        records = df.iloc[3:].to_dict(orient='records')
        for row_values in records:
            row = {
                headers[idx] or f'column_{idx}': row_values.get(col)
                for idx, col in enumerate(df.columns)
            }
            if not any(normalize_cell_value(value) for value in row.values()):
                continue

            first_name = field_for_row(row, candidates['first_name']) or ''
            last_name = field_for_row(row, candidates['last_name']) or ''
            if not first_name or not last_name:
                continue

            competitor_number = field_for_row(row, candidates['competitor_number']) or ''
            if not competitor_number:
                raise ValueError(
                    f"Missing competitor number for athlete {first_name} {last_name} in team '{team_name}'"
                )

            gender = field_for_row(row, candidates['gender']) or ''
            birth_date = field_for_row(row, candidates['birth_date']) or None
            school_year = field_for_row(row, candidates['school_year']) or None
            initial = field_for_row(row, candidates['initial']) or None
            team_code_from_sheet = field_for_row(row, candidates['team_code']) or team_code

            athletes.append(
                Athlete(
                    first_name=first_name.strip(),
                    last_name=last_name.strip(),
                    gender=gender.upper().strip(),
                    competitor_number=str(competitor_number).strip(),
                    team_name=team_name.strip(),
                    team_code=team_code_from_sheet.strip() if team_code_from_sheet else None,
                    birth_date=birth_date,
                    school_year=school_year,
                    initial=initial,
                    extra={
                        str(k).strip(): normalize_cell_value(v)
                        for k, v in row.items()
                        if k
                        and normalize_cell_value(v)
                        and str(k).strip().lower() not in ignored_headers
                    },
                )
            )

    if not athletes:
        raise ValueError('No athletes were loaded from the Google sheet roster')
    return athletes


def normalize_team_name(name: str) -> str:
    """Normalize a team name for matching and ordering.

    Args:
        name (str): The raw team name to normalize.

    Returns:
        str: A title-cased team name with collapsed internal whitespace.

    Assumptions:
        Leading and trailing whitespace is removed, and multiple consecutive
        whitespace characters are collapsed to single spaces.
    """
    return re.sub(r'\s+', ' ', name.strip()).title()


def extract_team_names_from_sheets(sheets: Dict[str, pd.DataFrame]) -> List[str]:
    """Extract unique team names from spreadsheet sheets.

    Args:
        sheets (Dict[str, pd.DataFrame]): Spreadsheet sheets parsed from a Google
            Sheets export.

    Returns:
        List[str]: Unique team names discovered from the sheets, preserving the
            first-seen order.

    Assumptions:
        Each sheet is expected to contain the team name in row 0/1 of the first
        column/second column. Empty or missing team names are ignored.
    """
    teams: List[str] = []
    seen: set[str] = set()
    for _, df in sheets.items():
        if df.empty or len(df) < 2:
            continue

        df = df.where(pd.notna(df), None)
        if df.shape[1] > 1:
            team_name = normalize_cell_value(df.iat[0, 1])
        else:
            team_name = normalize_cell_value(df.iat[0, 0])

        if not team_name:
            continue

        normalized = normalize_team_name(team_name)
        if normalized.lower() in {'hello! welcome to the 2026 xc season bib sheet', 'day', 'monday', 'nan', 'none', 'n/a', 'na'}:
            continue

        if normalized not in seen:
            seen.add(normalized)
            teams.append(normalized)

    return teams


def slugify(text: str) -> str:
    """Convert a string into a filesystem-safe slug.

    Args:
        text (str): The source string to transform.

    Returns:
        str: A lowercase slug composed of letters, numbers, and underscores.

    Assumptions:
        Any non-alphanumeric sequence is replaced with an underscore, surrounding
        underscores are trimmed, and an empty result falls back to ``team``.
    """
    return re.sub(r'[^A-Za-z0-9]+', '_', text.strip()).strip('_').lower() or 'team'


def group_athletes_by_team(athletes: Iterable[Athlete], team_order: Optional[List[str]] = None) -> List[Tuple[str, List[Athlete]]]:
    """Group athletes by normalized team name, preserving optional order.

    Args:
        athletes (Iterable[Athlete]): Athlete records to group.
        team_order (Optional[List[str]]): Optional team names that define the
            preferred ordering of the groups.

    Returns:
        List[Tuple[str, List[Athlete]]]: A list of ``(team_name, athletes)``
            pairs ordered by the requested team order when provided.

    Assumptions:
        Team matching uses normalized team names, and any teams not named in
        ``team_order`` are appended afterward in insertion order.
    """
    grouped: Dict[str, List[Athlete]] = OrderedDict()
    normalized_order = [normalize_team_name(name) for name in team_order] if team_order else []

    for athlete in athletes:
        key = normalize_team_name(athlete.team_name)
        grouped.setdefault(key, []).append(athlete)

    ordered_groups: List[Tuple[str, List[Athlete]]] = []
    if normalized_order:
        for name in normalized_order:
            if name in grouped:
                ordered_groups.append((name, grouped.pop(name)))
        for remaining_name, remaining_athletes in grouped.items():
            ordered_groups.append((remaining_name, remaining_athletes))
    else:
        ordered_groups = list(grouped.items())
    return ordered_groups


def assign_chips_to_athletes(athletes: List[Athlete], chips: List[Chip], team_order: Optional[List[str]] = None) -> List[AssignedAthlete]:
    """Assign chip labels and IDs to athletes in team order.

    Args:
        athletes (List[Athlete]): Athletes to assign chips to.
        chips (List[Chip]): Available chip mappings in assignment order.
        team_order (Optional[List[str]]): Optional team names that define the
            ordering of the athlete assignment sequence.

    Returns:
        List[AssignedAthlete]: Assigned athlete records containing chip label,
            chip ID, and chip index information.

    Assumptions:
        The number of athletes must not exceed the number of available chips, or
        a ValueError is raised. Assignment proceeds in the grouped team order
        and consumes chips sequentially.
    """
    grouped = group_athletes_by_team(athletes, team_order)
    total_count = sum(len(team_athletes) for _, team_athletes in grouped)
    if total_count > len(chips):
        raise ValueError(f"Not enough chips ({len(chips)}) for {total_count} athletes")

    assigned: List[AssignedAthlete] = []
    chip_index = 0
    for team_name, team_athletes in grouped:
        for athlete in team_athletes:
            chip = chips[chip_index]
            assigned.append(
                AssignedAthlete(
                    first_name=athlete.first_name,
                    last_name=athlete.last_name,
                    gender=athlete.gender,
                    competitor_number=athlete.competitor_number,
                    team_name=team_name,
                    team_code=athlete.team_code,
                    birth_date=athlete.birth_date,
                    school_year=athlete.school_year,
                    initial=athlete.initial,
                    extra=athlete.extra,
                    chip_label=chip.label,
                    chip_id=chip.chip_id,
                    chip_index=chip_index + 1,
                )
            )
            chip_index += 1
    return assigned


def format_team_code(team_name: str) -> str:
    """Convert a team name into a 4-character HyTek team code.

    Args:
        team_name (str): The human-readable team name.

    Returns:
        str: A four-character uppercase code derived from alphanumeric characters
            in the team name, or ``UNA`` when no usable characters remain.

    Assumptions:
        Non-alphanumeric characters are removed before truncation, and only the
        first four characters are preserved.
    """
    cleaned = re.sub(r'[^A-Za-z0-9]', '', team_name.upper())
    return cleaned[:4] if cleaned else 'UNA'


def format_hytek_e_record(athlete: AssignedAthlete, event_code: str, event_measure: str) -> str:
    """Render an athlete as a HyTek D record line.

    Args:
        athlete (AssignedAthlete): The assigned athlete to serialize.
        event_code (str): HyTek event code for the entry.
        event_measure (str): HyTek measure code such as ``M`` or ``E``.

    Returns:
        str: A semicolon-delimited HyTek-style record string.

    Assumptions:
        The output format mirrors the project's current HyTek record shape and
        uses empty strings for fields that are not populated by the input data.
    """
    team_code = athlete.team_code or ''
    fields = [
        'D',
        athlete.last_name,
        athlete.first_name,
        athlete.initial or '',
        athlete.gender or '',
        athlete.birth_date or '',
        team_code,
        athlete.team_name,
        '',
        athlete.school_year or '',
        event_code,
        '',
        event_measure,
        '',
        athlete.competitor_number,
        '',
    ]
    return ';'.join(fields)


def write_tag_file(path: Path, assigned: List[AssignedAthlete]) -> None:
    """Write the bib number to chip ID mapping as plain text.

    Args:
        path (Path): Destination file path for the CSV mapping output.
        assigned (List[AssignedAthlete]): Assigned athlete records containing the
            bib number and chip ID values.

    Returns:
        None: The file is written to disk.

    Assumptions:
        The output file is created with comma delimiters and a header row of
        ``Bib Number`` and ``Chip ID``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, delimiter=',')
        writer.writerow(['Bib Number', 'Chip ID'])
        for athlete in assigned:
            writer.writerow([athlete.competitor_number, athlete.chip_id])


def write_hytek_entries(path: Path, assigned: List[AssignedAthlete], event_code: str, event_measure: str) -> None:
    """Write HyTek E record entries to the specified output file.

    Args:
        path (Path): Destination file path for the HyTek entry output.
        assigned (List[AssignedAthlete]): Assigned athlete records to serialize.
        event_code (str): HyTek event code for each entry.
        event_measure (str): HyTek measure code such as ``M`` or ``E``.

    Returns:
        None: The output file is written to disk.

    Assumptions:
        Athletes with both first and last names blank are skipped. The output is
        written with Windows-style ``\r\n`` line endings.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    def name_is_blank(value: str) -> bool:
        return not value or value.strip().lower() in {'nan', 'none'}

    with path.open('w', encoding='utf-8', newline='') as handle:
        for athlete in assigned:
            if name_is_blank(athlete.first_name) and name_is_blank(athlete.last_name):
                continue
            handle.write(format_hytek_e_record(athlete, event_code, event_measure) + '\r\n')


def write_printable_sheets(output_dir: Path, assigned: List[AssignedAthlete], event_code: str) -> None:
    """Write printable assignment sheets for each team and one combined file.

    Args:
        output_dir (Path): Directory where the text and PDF assignment files are
            written.
        assigned (List[AssignedAthlete]): Assigned athlete records to include in
            the printable sheets.
        event_code (str): Event identifier shown in the generated sheets.

    Returns:
        None: The output files are written to disk.

    Assumptions:
        Athletes with both first and last names blank are excluded. Team files are
        named using a slugified team name, and a PDF summary is generated in the
        same directory.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    def name_is_blank(value: str) -> bool:
        return not value or value.strip().lower() in {'nan', 'none'}

    teams: Dict[str, List[AssignedAthlete]] = defaultdict(list)
    for athlete in assigned:
        if name_is_blank(athlete.first_name) and name_is_blank(athlete.last_name):
            continue
        teams[athlete.team_name].append(athlete)

    combined_path = output_dir / 'team_assignments.txt'
    with combined_path.open('w', encoding='utf-8', newline='') as combined:
        for team_name, athletes in teams.items():
            page_header = [
                f'Team: {team_name}',
                f'Event: {event_code}',
                f'Athlete count: {len(athletes)}',
                '-' * 108,
                f"{'Last Name':<16}{'First Name':<16}{'Gender':<8}{'Bib':<8}{'Chip Label':<16}{'Chip ID'}",
            ]
            combined.write('\n'.join(page_header) + '\n')
            for athlete in athletes:
                combined.write(
                    f"{athlete.last_name:<16}{athlete.first_name:<16}{athlete.gender:<8}"
                    f"{athlete.competitor_number:<8}{athlete.chip_label:<16}{athlete.chip_id}\n"
                )
            combined.write('\f\n')

    for team_name, athletes in teams.items():
        suffix = slugify(team_name)
        team_path = output_dir / f'{suffix}_assignments.txt'
        with team_path.open('w', encoding='utf-8', newline='') as team_file:
            team_file.write(f'Team: {team_name}\n')
            team_file.write(f'Event: {event_code}\n')
            team_file.write(f'Total athletes: {len(athletes)}\n')
            team_file.write('-' * 108 + '\n')
            team_file.write(f"{'Last Name':<16}{'First Name':<16}{'Gender':<8}{'Bib':<8}{'Chip Label':<16}{'Chip ID'}\n")
            for athlete in athletes:
                team_file.write(
                    f"{athlete.last_name:<16}{athlete.first_name:<16}{athlete.gender:<8}"
                    f"{athlete.competitor_number:<8}{athlete.chip_label:<16}{athlete.chip_id}\n"
                )

    pdf_path = output_dir / 'team_assignments.pdf'
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def footer(canvas, doc_ref):
        canvas.saveState()
        footer_text = f'Bell Lap Timing — Generated {created_at}'
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(
            letter[0] - 0.75 * inch,
            0.5 * inch,
            footer_text,
        )
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    story = []

    for team_name, athletes in teams.items():
        story.append(Paragraph(f'Team: {team_name}', styles['Heading2']))
        story.append(Paragraph(f'Total athletes: {len(athletes)}', styles['Normal']))
        story.append(Spacer(1, 0.15 * inch))

        table_data = [
            ['Last Name', 'First Name', 'Gender', 'Bib', 'Chip Label', 'Chip ID'],
        ]
        table_data.extend(
            [
                athlete.last_name,
                athlete.first_name,
                athlete.gender,
                athlete.competitor_number,
                athlete.chip_label,
                athlete.chip_id,
            ]
            for athlete in athletes
        )

        table = Table(
            table_data,
            colWidths=[1.5 * inch, 1.5 * inch, 0.8 * inch, 0.8 * inch, 1.2 * inch, 1.8 * inch],
            repeatRows=1,
        )
        table.setStyle(
            TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-2, -1), 'LEFT'),
                ('ALIGN', (-1, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ])
        )
        story.append(table)
        story.append(PageBreak())

    if story:
        doc.build(story, onFirstPage=footer, onLaterPages=footer)


def compile_team_list(team_csv: Optional[str], selected_teams: Optional[str]) -> Optional[List[str]]:
    """Compile a team list from an inline string or a line-separated file.

    Args:
        team_csv (Optional[str]): Optional path to a text file containing team
            names, one per line.
        selected_teams (Optional[str]): Optional comma-separated list of team
            names supplied directly by the caller.

    Returns:
        Optional[List[str]]: A list of trimmed team names when either input is
            provided; otherwise ``None``.

    Assumptions:
        Inline team names take precedence over the file input. Empty entries are
        ignored, and a missing team list file raises FileNotFoundError.
    """
    if selected_teams:
        return [team.strip() for team in selected_teams.split(',') if team.strip()]
    if team_csv:
        path = Path(team_csv)
        if not path.exists():
            raise FileNotFoundError(f"Team list file not found: {path}")
        with path.open(newline='', encoding='utf-8-sig') as handle:
            return [line.strip() for line in handle if line.strip()]
    return None
