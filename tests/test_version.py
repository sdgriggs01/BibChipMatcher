from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from utils.version import __version__


class VersionSyncTests(unittest.TestCase):
    def test_matches_pyproject_version(self) -> None:
        pyproject_path = Path(__file__).resolve().parent.parent / 'pyproject.toml'
        data = tomllib.loads(pyproject_path.read_text(encoding='utf-8'))
        self.assertEqual(__version__, data['project']['version'])


if __name__ == '__main__':
    unittest.main()
