import unittest
from unittest import mock
import gzip
import tap_sftp.client as client
import paramiko

@mock.patch("tap_sftp.client.SFTPConnection.sftp")
@mock.patch("tap_sftp.client.LOGGER.warn")
class TestEmptyCSVinGZ(unittest.TestCase):

    @mock.patch("gzip.GzipFile")
    def test_empty_file_negative(self, mocked_gzip, mocked_logger, mocked_connect):

        mocked_connect.return_value = paramiko.SFTPClient
        mocked_gzip.side_effect = mock.mock_open(read_data='')

        conn = client.SFTPConnection("10.0.0.1", "username", port="22")

        gzip = conn.should_skip_gzip_file("/root_dir/file.csv.gz")

        self.assertEquals(gzip, True)
        mocked_logger.assert_called_with("Skipping %s file because it is empty.", "/root_dir/file.csv.gz")

    @mock.patch("gzip.GzipFile")
    def test_empty_file_positive(self, mocked_gzip, mocked_logger, mocked_connect):

        mocked_connect.return_value = paramiko.SFTPClient
        mocked_gzip.side_effect = mock.mock_open(read_data='a')

        conn = client.SFTPConnection("10.0.0.1", "username", port="22")

        gzip = conn.should_skip_gzip_file("/root_dir/file.csv.gz")

        self.assertEquals(gzip, False)

    @mock.patch("gzip.GzipFile.read")
    def test_empty_file_OSError(self, mocked_gzip, mocked_logger, mocked_connect):

        mocked_connect.return_value = paramiko.SFTPClient
        mocked_gzip.side_effect = OSError
        conn = client.SFTPConnection("10.0.0.1", "username", port="22")

        gzip = conn.should_skip_gzip_file("/root_dir/file.csv.gz")

        self.assertEquals(gzip, True)
        mocked_logger.assert_called_with("Skipping %s file because it is not a gzipped file.", "/root_dir/file.csv.gz")

    @mock.patch("gzip.GzipFile.read")
    def test_empty_file_PermissionDenied(self, mocked_gzip, mocked_logger, mocked_connect):

        mocked_connect.return_value = paramiko.SFTPClient
        mocked_gzip.side_effect = PermissionError("Permission denied")
        conn = client.SFTPConnection("10.0.0.1", "username", port="22")

        gzip = conn.should_skip_gzip_file("/root_dir/file.csv.gz")

        self.assertEquals(gzip, True)
        mocked_logger.assert_called_with("Skipping %s file because you do not have enough permissions.", "/root_dir/file.csv.gz")
