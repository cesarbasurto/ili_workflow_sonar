import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from utils import file_utils


class FileTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.output_patch = patch.object(file_utils, "OUTPUT_DIR", str(self.root / "output"))
        self.output_patch.start()
        self.addCleanup(self.output_patch.stop)

    def test_local_xtf_is_copied_and_zip_contains_original_content(self):
        source = self.root / "source.xtf"
        source.write_bytes(b"<transfer>valid</transfer>")

        copied = Path(file_utils.download_or_copy_xtf("42", str(source), "etl"))
        self.assertEqual(copied.relative_to(self.root / "output"), Path("etl/42/42.xtf"))
        self.assertEqual(copied.read_bytes(), source.read_bytes())

        archive = Path(file_utils.compress_xtf_file(str(copied)))
        with zipfile.ZipFile(archive) as zipped:
            self.assertEqual(zipped.namelist(), ["42.xtf"])
            self.assertEqual(zipped.read("42.xtf"), source.read_bytes())

    def test_local_transfer_rejects_missing_or_wrong_extension(self):
        with self.assertRaises(FileNotFoundError):
            file_utils.download_or_copy_xtf("42", str(self.root / "absent.xtf"), "etl")

        source = self.root / "source.txt"
        source.write_text("wrong format")
        with self.assertRaisesRegex(ValueError, "extension"):
            file_utils.download_or_copy_xtf("42", str(source), "etl")

    @patch("utils.file_utils.requests.get")
    def test_remote_xtf_streams_nonempty_chunks(self, get):
        response = MagicMock()
        response.iter_content.return_value = [b"first", b"", b"second"]
        get.return_value.__enter__.return_value = response

        saved = file_utils.download_or_copy_xtf("42", "https://example.test/data.xtf", "etl")

        self.assertEqual(Path(saved).read_bytes(), b"firstsecond")
        get.assert_called_once_with("https://example.test/data.xtf", stream=True)
        response.raise_for_status.assert_called_once()

    @patch("utils.file_utils.requests.get")
    def test_remote_transfer_rejects_non_xtf_url(self, get):
        with self.assertRaisesRegex(ValueError, "URL"):
            file_utils.download_or_copy_xtf("42", "https://example.test/data.txt", "etl")
        get.assert_not_called()

    def test_compression_requires_existing_file(self):
        with self.assertRaises(FileNotFoundError):
            file_utils.compress_xtf_file(str(self.root / "absent.xtf"))

    @patch("utils.file_utils.boto3.client")
    def test_s3_upload_uses_configured_bucket_and_key(self, client):
        with patch.dict(os.environ, {"S3_AWS_BUCKET_NAME": "test-bucket"}):
            key = file_utils.upload_file_to_aws_s3(self.root / "42.zip", "ili-workflow/etl")
        self.assertEqual(key, "test-bucket/ili-workflow/etl/42.zip")
        client.return_value.upload_file.assert_called_once_with(
            self.root / "42.zip", "test-bucket", "ili-workflow/etl/42.zip",
            ExtraArgs={"ACL": "public-read"},
        )

    @patch("utils.file_utils.boto3.client")
    def test_s3_upload_reports_missing_file_and_credentials(self, client):
        for error, expected in (
            (FileNotFoundError(), FileNotFoundError),
            (NoCredentialsError(), RuntimeError),
            (PartialCredentialsError(provider="env", cred_var="secret"), RuntimeError),
        ):
            with self.subTest(error=type(error).__name__):
                client.return_value.upload_file.side_effect = error
                with self.assertRaises(expected):
                    file_utils.upload_file_to_aws_s3(self.root / "42.zip")

        client.return_value.upload_file.side_effect = OSError("network unavailable")
        with self.assertRaisesRegex(RuntimeError, "network unavailable"):
            file_utils.upload_file_to_aws_s3(self.root / "42.zip")

    @patch("utils.file_utils.upload_file_to_aws_s3", return_value="bucket/key")
    @patch("utils.file_utils.compress_xtf_file", return_value="output.zip")
    def test_publishing_ladm_uploads_compressed_output(self, compress, upload):
        file_utils.upload_to_s3_xtf_ladm("42", "etl")

        compress.assert_called_once_with(
            os.path.join(str(self.root / "output"), "etl", "42", "output_42.xtf")
        )
        upload.assert_called_once_with(
            file_path="output.zip", folder_name=os.path.join("ili-workflow", "etl")
        )


if __name__ == "__main__":
    unittest.main()
