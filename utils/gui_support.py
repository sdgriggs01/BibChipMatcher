#!/usr/bin/env python3
"""Pure helper functions extracted from the Tkinter GUI for testability."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def build_settings_payload(
    sheet_id: str,
    chip_map: str,
    sheet_gid: str,
    output_dir: str,
    output_prefix: str,
    event_code: str,
    event_measure: str,
    selected_teams: Sequence[str],
) -> Dict[str, Any]:
    """Build the JSON-serializable settings payload cached between GUI runs.

    Args:
        sheet_id (str): Google spreadsheet ID or URL entry value.
        chip_map (str): Chip map file path entry value.
        sheet_gid (str): Optional sheet gid entry value.
        output_dir (str): Output directory entry value.
        output_prefix (str): Output file prefix entry value.
        event_code (str): Selected HyTek event code.
        event_measure (str): Selected HyTek event measure code.
        selected_teams (Sequence[str]): Team names currently checked in the UI.

    Returns:
        Dict[str, Any]: A settings dictionary suitable for JSON serialization.

    Assumptions:
        Each string field is stripped of surrounding whitespace before storage.
    """
    return {
        'sheet-id': sheet_id.strip(),
        'chip-map': chip_map.strip(),
        'sheet-gid': sheet_gid.strip(),
        'output-dir': output_dir.strip(),
        'output-prefix': output_prefix.strip(),
        'event-code': event_code.strip(),
        'event-measure': event_measure.strip(),
        'selected-teams': list(selected_teams),
    }


def write_settings_cache(cache_path: Path, settings: Dict[str, Any]) -> None:
    """Persist a settings payload to disk as formatted JSON.

    Args:
        cache_path (Path): Destination file path for the cached settings.
        settings (Dict[str, Any]): Settings payload to serialize.

    Returns:
        None: The file is written to disk.

    Assumptions:
        The parent directory is created if it does not already exist.
    """
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(settings, indent=2), encoding='utf-8')


def read_settings_cache(cache_path: Path) -> Optional[Dict[str, Any]]:
    """Read a previously cached settings payload from disk.

    Args:
        cache_path (Path): File path of the cached settings.

    Returns:
        Optional[Dict[str, Any]]: The parsed settings dictionary, or ``None``
            when the file is missing or contains invalid JSON.

    Assumptions:
        A missing file or unparseable JSON is treated as "no saved settings"
        rather than as an error.
    """
    if not cache_path.exists():
        return None
    try:
        return json.loads(cache_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None


def build_cli_args(
    chip_map: str,
    sheet_id: str,
    sheet_gid: str,
    teams: str,
    output_dir: str,
    output_prefix: str,
    event_code: str,
    event_measure: str,
) -> List[str]:
    """Build an argv-style argument list from GUI field values.

    Args:
        chip_map (str): Chip map file path.
        sheet_id (str): Google spreadsheet ID or URL.
        sheet_gid (str): Optional sheet gid.
        teams (str): Comma-separated selected team names.
        output_dir (str): Output directory path.
        output_prefix (str): Output file prefix.
        event_code (str): HyTek event code.
        event_measure (str): HyTek event measure code.

    Returns:
        List[str]: Arguments suitable for ``argparse.ArgumentParser.parse_args``,
            matching the CLI's flag names.

    Assumptions:
        Blank values are omitted entirely rather than passed as empty strings,
        so argparse defaults apply for unset fields.
    """
    values = {
        '--chip-map': chip_map,
        '--sheet-id': sheet_id,
        '--sheet-gid': sheet_gid,
        '--teams': teams,
        '--output-dir': output_dir,
        '--output-prefix': output_prefix,
        '--event-code': event_code,
        '--event-measure': event_measure,
    }
    args: List[str] = []
    for key, value in values.items():
        if value:
            args.extend([key, value])
    return args
