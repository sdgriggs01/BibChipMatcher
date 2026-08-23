from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import requests

from utils.bib_chip_matcher_utils import download_google_sheet_xlsx


class DownloadGoogleSheetXlsxTests(unittest.TestCase):
    @patch('utils.bib_chip_matcher_utils.requests.get')
    def test_raises_value_error_when_request_fails(self, mock_get) -> None:
        mock_get.side_effect = requests.ConnectionError('network unreachable')

        with self.assertRaisesRegex(ValueError, 'Unable to download Google Sheet XLSX export'):
            download_google_sheet_xlsx('sheet-id')

    @patch('utils.bib_chip_matcher_utils.requests.get')
    def test_raises_value_error_when_response_status_is_an_error(self, mock_get) -> None:
        response = MagicMock()
        response.raise_for_status.side_effect = requests.HTTPError('404 Client Error')
        mock_get.return_value = response

        with self.assertRaisesRegex(ValueError, 'Unable to download Google Sheet XLSX export'):
            download_google_sheet_xlsx('sheet-id')

    @patch('utils.bib_chip_matcher_utils.requests.get')
    def test_raises_value_error_when_response_body_is_not_valid_xlsx(self, mock_get) -> None:
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.content = b'this is not a spreadsheet, it is plain text'
        mock_get.return_value = response

        with self.assertRaisesRegex(ValueError, 'Unable to parse downloaded spreadsheet as XLSX'):
            download_google_sheet_xlsx('sheet-id')

    @patch('utils.bib_chip_matcher_utils.requests.get')
    def test_appends_gid_to_export_url_when_provided(self, mock_get) -> None:
        response = MagicMock()
        response.raise_for_status.side_effect = requests.HTTPError('boom')
        mock_get.return_value = response

        with self.assertRaises(ValueError):
            download_google_sheet_xlsx('sheet-id', sheet_gid='123456')

        called_url = mock_get.call_args.args[0]
        self.assertIn('sheet-id', called_url)
        self.assertIn('gid=123456', called_url)

    @patch('utils.bib_chip_matcher_utils.requests.get')
    def test_omits_gid_from_export_url_when_not_provided(self, mock_get) -> None:
        response = MagicMock()
        response.raise_for_status.side_effect = requests.HTTPError('boom')
        mock_get.return_value = response

        with self.assertRaises(ValueError):
            download_google_sheet_xlsx('sheet-id')

        called_url = mock_get.call_args.args[0]
        self.assertNotIn('gid=', called_url)


if __name__ == '__main__':
    unittest.main()
