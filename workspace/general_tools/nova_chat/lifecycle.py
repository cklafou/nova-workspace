# Last updated: 2026-10-05 21:27:11
# @nova: Coordinate Nova on/off with its owning launcher and hold updater work during transitions.
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from nova_updater import jobs
from nova_updater.api import make_guard, LOOPBACK_CLIENTS


def launcher_request(method, action):
    request = urllib.request.Request(
        'http://127.0.0.1:8799/api/nova/' + action,
        data=b'{}' if method == 'POST' else None,
        headers={'Content-Type': 'application/json'}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response), response.status
    except urllib.error.HTTPError as error:
        try:
            result = json.load(error)
        except (ValueError, OSError):
            result = {'ok': False, 'error': 'Restart Nova Chat to enable the new Nova on/off control.'}
        return result, error.code


class NovaLifecycle:
    """Retain the exclusive updater slot until the launcher confirms a terminal state."""
    def __init__(self, *, chat_only, before_stop=None, quiesce=None, transport=launcher_request,
                 manager=None, allowed_clients=LOOPBACK_CLIENTS, poll_seconds=1):
        self.chat_only = chat_only
        self.before_stop = before_stop
        self.quiesce_callback = quiesce
        self.transport = transport
        self.jobs = manager if manager is not None else jobs.JOBS
        self.poll_seconds = poll_seconds
        self._guard = self._target = self._watch = None
        self._remote_pending = False
        self._lock = asyncio.Lock()
        self.router = APIRouter(prefix='/api/nova', dependencies=[Depends(make_guard(allowed_clients))])
        self.router.add_api_route('/lifecycle', self.status, methods=['GET'])
        self.router.add_api_route('/start', self.start, methods=['POST'])
        self.router.add_api_route('/stop', self.stop, methods=['POST'])
        self.router.add_api_route('/quiesce', self.quiesce, methods=['POST'])
        self.router.add_event_handler('startup', self.initialize)
        self.router.add_event_handler('shutdown', self.close)

    @property
    def pending(self):
        return self._guard is not None or self._remote_pending

    def _release(self):
        guard, self._guard = self._guard, None
        self._target = None
        self._remote_pending = False
        if guard is not None:
            guard.__exit__(None, None, None)

    def _decorate(self, result, code):
        state = result.get('state', 'unavailable')
        return {**result, 'available': code < 400 and state in {'off', 'starting', 'on', 'stopping', 'error'},
                'state': state, 'launcher_chat_only': result.get('chat_only'),
                'chat_only': self.chat_only, 'nova_enabled': not self.chat_only,
                'target_enabled': result.get('target') == 'on' if result.get('target') else None,
                'busy': bool(result.get('pending')) or self.pending}

    def _unavailable(self):
        return {'ok': False, 'available': False, 'state': 'unavailable',
                'chat_only': self.chat_only, 'nova_enabled': not self.chat_only,
                'pending': self.pending, 'busy': self.pending, 'target': self._target,
                'error': 'Nova launcher is unavailable. Restart Nova Chat with NovaStart or NovaChatOnly.'}

    async def _read_status(self):
        async with self._lock:
            result, code = await asyncio.to_thread(self.transport, 'GET', 'status')
            if code < 400 and result.get('pending'):
                self._remote_pending = True
                self._target = result.get('target')
                if self._guard is None:
                    guard = self.jobs.exclusive('Finishing Nova mode change')
                    try:
                        guard.__enter__()
                    except jobs.Conflict:
                        pass
                    else:
                        self._guard = guard
                self._ensure_watch()
            elif code < 400 and result.get('state') in {'off', 'on', 'error'}:
                self._release()
            return self._decorate(result, code), code

    async def initialize(self):
        # Startup completes before serving routes: inherit the old worker's transition hold.
        try:
            await self._read_status()
        except (OSError, ValueError):
            pass  # Standalone/old launchers have no mode transition facility.

    async def status(self):
        try:
            result, code = await self._read_status()
            return JSONResponse(result, status_code=code)
        except (OSError, ValueError):
            return JSONResponse(self._unavailable(), status_code=503)

    async def _watch_transition(self):
        while self.pending:
            await asyncio.sleep(self.poll_seconds)
            try:
                await self._read_status()
            except (OSError, ValueError):
                continue  # Keep paid jobs blocked while the launcher's outcome is uncertain.

    async def _change(self, target):
        async with self._lock:
            newly_guarded = not self.pending
            if newly_guarded:
                guard = self.jobs.exclusive('Switching Nova ' + target)
                try:
                    guard.__enter__()
                except jobs.Conflict as error:
                    return JSONResponse({'ok': False, 'error': str(error)}, status_code=409)
                self._guard, self._target = guard, target
            attempted = False
            try:
                if newly_guarded and target == 'off' and not self.chat_only and self.before_stop:
                    stopped = await self.before_stop()
                    if isinstance(stopped, JSONResponse):
                        stopped = json.loads(stopped.body)
                    if isinstance(stopped, dict) and stopped.get('stopped') is False:
                        self._release()
                        return JSONResponse({'ok': False, 'error': 'Nova still has work stopping. Wait for it to finish, then press Stop Nova again.', 'operations': stopped.get('operations', [])}, status_code=409)
                attempted = True
                result, code = await asyncio.to_thread(self.transport, 'POST', 'start' if target == 'on' else 'stop')
                if newly_guarded and (code >= 400 or not result.get('pending')):
                    self._release()
                self._ensure_watch()
                return JSONResponse(self._decorate(result, code), status_code=code)
            except (OSError, ValueError):
                if not attempted:
                    self._release()
                self._ensure_watch()
                return JSONResponse(self._unavailable(), status_code=503)
            except Exception:
                if newly_guarded and not attempted:
                    self._release()
                raise

    def _ensure_watch(self):
        if self.pending and (self._watch is None or self._watch.done()):
            self._watch = asyncio.create_task(self._watch_transition(), name='nova-lifecycle-transition')

    async def start(self):
        return await self._change('on')

    async def stop(self):
        return await self._change('off')

    async def quiesce(self):
        if not self.pending:
            return JSONResponse({'ok': False, 'error': 'No accepted Nova mode transition.'}, status_code=409)
        if self.quiesce_callback:
            return await self.quiesce_callback()
        return JSONResponse({'ok': True, 'stopped': True})

    async def close(self):
        if self._watch and not self._watch.done():
            self._watch.cancel()
            try:
                await self._watch
            except asyncio.CancelledError:
                pass
        self._release()
