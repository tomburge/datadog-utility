import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ddutil.cli import cli  # type: ignore[import-untyped]


class StatusInlinePolicyDriftTests(unittest.TestCase):
    def test_status_reports_missing_inline_policy_actions(self):
        runner = CliRunner()

        with patch.dict(
            "os.environ",
            {
                "DD_POLICY_ACTIONS": "logs:PutSubscriptionFilter,sns:Publish,events:CreateEventBus",
            },
            clear=False,
        ):
            with patch("ddutil.cli.load_dotenv", return_value=None):
                with patch("ddutil.cli.create_session", return_value=object()):
                    with patch("ddutil.cli.create_client", return_value=object()):
                        with patch(
                            "ddutil.cli.get_role",
                            return_value={
                                "Arn": "arn:aws:iam::123456789012:role/datadog-integration-role"
                            },
                        ):
                            with patch(
                                "ddutil.cli.list_attached_policies",
                                return_value=[
                                    "arn:aws:iam::aws:policy/ReadOnlyAccess",
                                    "arn:aws:iam::aws:policy/SecurityAudit",
                                ],
                            ):
                                with patch(
                                    "ddutil.cli.list_inline_policies",
                                    return_value=["datadog"],
                                ):
                                    with patch(
                                        "ddutil.cli.get_inline_policy_actions",
                                        return_value=[
                                            "events:CreateEventBus",
                                            "logs:PutSubscriptionFilter",
                                        ],
                                    ):
                                        with patch(
                                            "ddutil.cli.get_role_tags", return_value=[]
                                        ):
                                            with patch(
                                                "ddutil.cli.console.print"
                                            ) as mock_print:
                                                result = runner.invoke(
                                                    cli,
                                                    [
                                                        "status",
                                                        "--aws-only",
                                                        "--account-id",
                                                        "123456789012",
                                                        "--dd-account-id",
                                                        "1234567",
                                                        "--output",
                                                        "json",
                                                        "--quiet",
                                                    ],
                                                )

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(mock_print.call_args.args[0])

        self.assertEqual(payload["sync_status"], "out_of_sync")
        self.assertFalse(payload["iam_inline_policy_actions_match"])
        self.assertIn(
            "Missing inline policy actions: sns:Publish",
            payload["issues"],
        )


if __name__ == "__main__":
    unittest.main()
