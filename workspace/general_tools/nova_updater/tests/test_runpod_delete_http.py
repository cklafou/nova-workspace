# @nova: Verify RunPod deletion and absence detection through mocked HTTP, without network calls or credentials.
from __future__ import annotations

import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from nova_updater import net, runpod


class EmptyResponse(io.BytesIO):
    status = 204


class RunPodDeleteHttp(unittest.TestCase):
    def test_delete_accepts_provider_empty_204_and_only_addresses_selected_pod(self):
        with patch.object(net.urllib.request, "urlopen", return_value=EmptyResponse(b"")) as opening:
            result = runpod.RunPodClient("fixture-key").delete("fixture_pod-123")
        self.assertEqual(result, {})
        request = opening.call_args.args[0]
        self.assertEqual(request.get_method(), "DELETE")
        self.assertEqual(request.full_url, "https://rest.runpod.io/v1/pods/fixture_pod-123")
        self.assertIsNone(request.data)
        self.assertEqual(request.get_header("Authorization"), "Bearer fixture-key")
        self.assertEqual(opening.call_args.kwargs["timeout"], 20.0)

    def test_delete_rejects_path_query_or_fragment_injection_before_http(self):
        client = runpod.RunPodClient("fixture-key")
        with patch.object(net.urllib.request, "urlopen") as opening:
            for pod_id in ("", "../networkvolumes/another", "pod/other", "pod?all=true", "pod#suffix", "%2e%2e", "pod\\other"):
                with self.subTest(pod_id=pod_id):
                    with self.assertRaises(runpod.RunPodError):
                        client.delete(pod_id)
            opening.assert_not_called()

    def test_get_preserves_404_separately_from_auth_and_server_failures(self):
        url = "https://rest.runpod.io/v1/pods/fixture"
        for status in (404, 401, 403, 500):
            failure = urllib.error.HTTPError(url, status, "provider failure", {},
                                             io.BytesIO(b"private-provider-response"))
            with self.subTest(status=status):
                with patch.object(net.urllib.request, "urlopen", side_effect=failure):
                    with self.assertRaises(net.NetError) as raised:
                        runpod.RunPodClient("fixture-key").pod("fixture")
                self.assertEqual(raised.exception.status_code, status)
                self.assertNotIn("fixture-key", str(raised.exception))
                self.assertNotIn("private-provider-response", str(raised.exception))

    def test_get_network_failure_is_unknown_not_absent(self):
        for failure in (urllib.error.URLError("offline"), TimeoutError("timed out")):
            with self.subTest(kind=type(failure).__name__):
                with patch.object(net.urllib.request, "urlopen", side_effect=failure):
                    with self.assertRaises(net.NetError) as raised:
                        runpod.RunPodClient("fixture-key").pod("fixture")
                self.assertIsNone(raised.exception.status_code)
                self.assertNotIn("fixture-key", str(raised.exception))

    def test_get_non_json_response_is_unknown_not_absent(self):
        with patch.object(net.urllib.request, "urlopen", return_value=io.BytesIO(b"<html>error</html>")):
            with self.assertRaises(net.NetError) as raised:
                runpod.RunPodClient("fixture-key").pod("fixture")
        self.assertIsNone(raised.exception.status_code)

    def test_delete_failure_retains_typed_status_without_provider_body(self):
        url = "https://rest.runpod.io/v1/pods/fixture"
        failure = urllib.error.HTTPError(url, 403, "denied", {}, io.BytesIO(b"private-provider-response"))
        with patch.object(net.urllib.request, "urlopen", side_effect=failure):
            with self.assertRaises(net.NetError) as raised:
                runpod.RunPodClient("fixture-key").delete("fixture")
        self.assertEqual(raised.exception.status_code, 403)
        self.assertNotIn("private-provider-response", str(raised.exception))
        self.assertNotIn("fixture-key", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
