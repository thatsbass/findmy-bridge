import unittest
import sys
import types
from pathlib import Path
from unittest.mock import Mock, patch

from integrations.anisette.provider import create_provider


class ProviderSelectionTests(unittest.TestCase):
    def test_rejects_http_mode_without_url_before_loading_dependency(self) -> None:
        with self.assertRaisesRegex(ValueError, "ANISETTE_URL"):
            create_provider("http", libs_path=Path("libs"))

    def test_rejects_unknown_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            create_provider("unknown", libs_path=Path("libs"))

    def test_local_mode_delegates_to_findmy_provider(self) -> None:
        provider = object()
        factory = Mock(return_value=provider)
        anisette_module = types.ModuleType("findmy.reports.anisette")
        anisette_module.LocalAnisetteProvider = factory
        reports_module = types.ModuleType("findmy.reports")
        findmy_module = types.ModuleType("findmy")
        with patch.dict(
            sys.modules,
            {
                "findmy": findmy_module,
                "findmy.reports": reports_module,
                "findmy.reports.anisette": anisette_module,
            },
        ):
            self.assertIs(
                create_provider("local", libs_path=Path("libs")),
                provider,
            )
        factory.assert_called_once_with(libs_path=Path("libs"))
