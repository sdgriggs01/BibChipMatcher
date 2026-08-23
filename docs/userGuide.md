# Bib Chip Matcher — User Guide

Bib Chip Matcher assigns timing chips to cross-country athletes pulled from a
team roster spreadsheet, then generates the files a meet needs: a HyTek
entries file, a bib-to-chip tag file, and printable team assignment sheets.

## 1. What you need before you start

- **A chip map file.** A CSV with a header row and two columns: the chip
  label (the number printed on the chip/bib) and the chip's timing ID. If the
  headers are named `num` and `tag` those columns are used; otherwise the
  first two columns are used. The default location is
  `input/chipLabel_chipID_map.txt`.
- **A Google Sheet with the team rosters.** The sheet must be shared so that
  "Anyone with the link can view" — the app downloads it as an XLSX export
  without signing in, so a private/restricted sheet will fail to download.
  Copy the sheet's URL or just the ID (the long string between `/d/` and
  the next `/` in the URL).
- **The list of teams participating in this meet.** You can select teams by
  checkbox in the app, or (CLI only) pass `--teams` or a team list file.

### Roster spreadsheet layout

Each worksheet (tab) in the spreadsheet represents one team:

- Row 1, column B: the team name.
- Row 2, column B: an optional team code.
- Row 3: column headers for the athlete table (first name, last name,
  gender, competitor/bib number, and optionally birth date, school year,
  and middle initial — header names are matched loosely, so "First Name",
  "First", and "fname" all work).
- Row 4 onward: one athlete per row.

Rows missing a first or last name are skipped. A row with a name but no
competitor/bib number will stop the run with an error, since every athlete
must have a number to assign a chip to.

## 2. Running the app

1. Launch **Bib Chip Matcher** from the Start menu (or desktop shortcut, if
   you created one during install).
2. On the **Basic** tab, paste the Sheet ID or URL. The app will fetch the
   list of team names from the spreadsheet automatically — check the boxes
   for the teams competing in this meet. Team order determines assignment
   order: chips are handed out one team at a time, in the order shown, so
   each team gets a continuous block of chip numbers.
3. Pick the **Event code** (distance) for the HyTek output.
4. Switch to the **Advanced** tab only if you need to override the chip map
   file, target a specific worksheet by GID, change the output directory, or
   set an output file prefix.
5. Click **Run**. Your settings (except the Run button state) are saved
   automatically and restored the next time you open the app.

A command-line interface is also available for scripting or batch use — run
`python cli.py --help` from the project for the full list of options (the
installed `bibchipmatcher` command launches the GUI, not the CLI).

## 3. Output files

All outputs are written to the chosen output directory (`output/` by
default):

| File | Purpose |
| --- | --- |
| `<prefix>_tag_assignments.txt` | CSV mapping each bib number to its chip ID. This is the tag file to feed into your timing system. |
| `<prefix>_hytek_entries.txt` | HyTek E-record entries file for importing into HyTek meet management software. |
| `team_assignments.txt` | A single text file with one page (form-feed separated) per team, listing each athlete's bib number and chip assignment — printable for handing out at check-in. |
| `<team>_assignments.txt` | The same per-team listing, one file per team. |
| `team_assignments.pdf` | A formatted, printable PDF with one page per team. |

## 4. Troubleshooting

- **"Unable to download Google Sheet XLSX export"** — the sheet isn't
  shared publicly, or the Sheet ID/URL is wrong. Open the sheet's share
  settings and set link access to "Viewer", then try again.
- **"Not enough chips for N athletes"** — the chip map file has fewer rows
  than the number of athletes across the selected teams. Add more chip
  rows or select fewer teams.
- **"Missing competitor number for athlete ..."** — a roster row is missing
  a bib/competitor number. Fix the spreadsheet and re-run.
- **No teams appear after entering a Sheet ID** — double check the sheet is
  shared with link access, and that each team tab follows the layout in
  section 1 (team name in row 1, column B).

## 5. Where things are stored

The app caches your last-used settings (sheet ID, chip map path, selected
teams, etc.) in `%APPDATA%\BibChipMatcher\settings.json` so you don't have
to re-enter them every meet.
