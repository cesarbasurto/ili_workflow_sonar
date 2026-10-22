import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.qgis_utils import build_qgis_environment


class QgisEnvironmentTests(unittest.TestCase):
    def test_environment_uses_private_runtime_directory(self):
        with tempfile.TemporaryDirectory() as root:
            runtime = str(Path(root) / "runtime")
            with patch.dict(os.environ, {
                "XDG_RUNTIME_DIR": "stale-directory",
                "QGIS_CUSTOM_CONFIG_PATH": "custom-profile",
            }), patch("utils.qgis_utils.tempfile.mkdtemp", return_value=runtime):
                environment = build_qgis_environment()

        self.assertEqual(environment["QT_QPA_PLATFORM"], "offscreen")
        self.assertEqual(environment["XDG_RUNTIME_DIR"], runtime)
        self.assertEqual(environment["QGIS_CUSTOM_CONFIG_PATH"], "custom-profile")


if __name__ == "__main__":
    unittest.main()
