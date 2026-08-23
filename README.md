# Bib Chip Matcher

Assigns timing chips to cross-country athletes pulled from a Google Sheets
team roster, then generates the files a meet needs: a HyTek entries file, a
bib-to-chip tag file for the timing system, and printable team assignment
sheets (text and PDF).

## Install

Download the latest Windows installer from the
[Releases page](https://github.com/sdgriggs01/BibChipMatcher/releases) and
run `BibChipMatcherSetup.exe`. It installs per-user (no admin rights
required) and adds a Start Menu shortcut.

## Using the app

Launch **Bib Chip Matcher**, paste in the Google Sheet ID or URL for the team
roster spreadsheet, check the boxes for the teams competing at this meet, and
click **Run**. Full instructions — spreadsheet layout, chip map format,
output file descriptions, and troubleshooting — are in the in-app **Help ▸
User Guide** menu, and also available at [`docs/userGuide.md`](docs/userGuide.md).

## Development

Requires Python 3.11+.

```
pip install -e ".[dev]"
python -m unittest discover tests
```

- `gui.py` — Tkinter desktop app.
- `cli.py` — command-line interface with the same options, for scripting.
- `utils/bib_chip_matcher_utils.py` — core roster parsing, chip assignment,
  and output generation logic.
- `utils/gui_support.py` — pure helper functions extracted from the GUI for
  testability.

### Building the Windows installer locally

```
pip install -e ".[build]"
pyinstaller packaging/bibchipmatcher.spec --distpath build/dist --workpath build/work --noconfirm
# then, with Inno Setup 6 installed:
ISCC.exe /DMyAppVersion=1.0.0 packaging\installer.iss
```

CI does this automatically: every push to `master` publishes a rolling
`latest` prerelease build, and pushing a version tag (e.g. `1.0.0`)
publishes a versioned GitHub Release.

## License

[MIT](LICENSE)
