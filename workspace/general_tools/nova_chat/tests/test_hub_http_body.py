# @nova: Verify control-POST acknowledgement waits for bounded complete JSON using disposable HTTP hubs only.
from contextlib import contextmanager
import http.client
import json
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from general_tools.nova_console import hub as hub_module
from general_tools.nova_console.hub import LogHub


@contextmanager
def fixture(chat_only=True):
    with tempfile.TemporaryDirectory() as folder:
        hub = LogHub(Path(folder))
        hub.configure_nova(chat_only, Mock())
        hub.serve(0)
        connection = http.client.HTTPConnection('127.0.0.1', hub._httpd.server_port, timeout=2)
        try:
            yield hub, connection
        finally:
            connection.close()
            hub.shutdown()


def unchanged(hub):
    return not hub.nova_status()['pending'] and not hub._shutdown_req and not hub._restart_req


class HubBodyTests(unittest.TestCase):
    def test_delayed_body_keeps_all_actions_unaccepted_until_complete_and_preserves_202(self):
        for path in ('/api/nova/start', '/api/nova/stop', '/api/shutdown', '/api/restart'):
            with self.subTest(path=path), fixture(chat_only=path != '/api/nova/stop') as (hub, conn):
                conn.putrequest('POST', path)
                conn.putheader('Content-Type', 'application/json')
                conn.putheader('Content-Length', '2')
                conn.endheaders()
                conn.send(b'{')
                time.sleep(.05)
                self.assertTrue(unchanged(hub))
                conn.send(b'}')
                response = conn.getresponse()
                self.assertEqual(response.status, 202)
                self.assertTrue(json.loads(response.read())['ok'])
                self.assertFalse(unchanged(hub))

    def test_origin_and_content_type_guards_still_reject_after_body_consumption(self):
        for headers in ({'Origin':'https://example.invalid'}, {'X-Forwarded-Host':'example.invalid'},
                        {'Host':'example.invalid'}, {'Content-Type':'text/plain'}):
            with self.subTest(headers=headers), fixture() as (hub, conn):
                conn.request('POST', '/api/nova/start', body=b'{}',
                             headers={'Content-Type':'application/json', **headers})
                response = conn.getresponse()
                self.assertEqual(response.status, 403)
                self.assertFalse(json.loads(response.read())['ok'])
                self.assertTrue(unchanged(hub))

    def test_malformed_or_nonobject_json_never_admits_mode_or_shutdown(self):
        for path in ('/api/nova/start', '/api/shutdown'):
            for body in (b'{', b'[]', b'null', b'\xff', b'{"value":NaN}'):
                with self.subTest(path=path, body=body), fixture() as (hub, conn):
                    conn.request('POST', path, body=body, headers={'Content-Type':'application/json'})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 400)
                    self.assertFalse(json.loads(response.read())['ok'])
                    self.assertTrue(unchanged(hub))

    def test_bad_framing_and_oversize_are_rejected_without_waiting_for_body(self):
        for headers, expected in (([('Content-Length','4097')],413),
                                  ([('Content-Length','-1')],400),
                                  ([('Content-Length','2'),('Content-Length','2')],400),
                                  ([('Transfer-Encoding','chunked')],400)):
            with self.subTest(headers=headers), fixture() as (hub, conn):
                conn.putrequest('POST','/api/restart')
                for name,value in headers:conn.putheader(name,value)
                conn.endheaders()
                response = conn.getresponse()
                self.assertEqual(response.status,expected)
                self.assertFalse(json.loads(response.read())['ok'])
                self.assertTrue(unchanged(hub))

    def test_incomplete_body_and_timeout_never_admit_action(self):
        with fixture() as (hub,conn):
            conn.putrequest('POST','/api/shutdown');conn.putheader('Content-Length','2');conn.endheaders()
            conn.send(b'{');conn.sock.shutdown(socket.SHUT_WR)
            response=conn.getresponse()
            self.assertEqual(response.status,400);self.assertFalse(json.loads(response.read())['ok'])
            self.assertTrue(unchanged(hub))
        with patch.object(hub_module,'_CONTROL_BODY_TIMEOUT',.05), fixture() as (hub,conn):
            conn.putrequest('POST','/api/restart');conn.putheader('Content-Length','2');conn.endheaders()
            conn.send(b'{')
            response=conn.getresponse()
            self.assertEqual(response.status,408);self.assertFalse(json.loads(response.read())['ok'])
            self.assertTrue(unchanged(hub))

    def test_legacy_bodyless_stopnova_and_health_remain_available(self):
        with fixture() as (hub,conn):
            conn.request('GET','/health')
            response=conn.getresponse()
            self.assertEqual(response.status,200);self.assertTrue(json.loads(response.read())['ok'])
            conn.request('POST','/api/shutdown')
            response=conn.getresponse()
            self.assertEqual(response.status,202);self.assertTrue(json.loads(response.read())['accepted'])
            self.assertTrue(hub._shutdown_req)


if __name__=='__main__':unittest.main()
