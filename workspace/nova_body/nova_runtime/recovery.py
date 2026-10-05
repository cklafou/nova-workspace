# @nova: Persist restartable body work and fail closed before uncertain side effects can be repeated.
"""Atomic body-relative checkpoints; never claim exactly-once external execution.

A start receipt without a durable terminal result is uncertain. Only explicit
reconciliation can clear that barrier. Read-only inspection remains available.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

READ_ONLY_TOOLS = frozenset({'read_file', 'list_files', 'list_directory', 'search_files',
    'memory_search', 'web_search', 'web_read', 'computer_look', 'list_tools',
    'get_task', 'list_tasks', 'get_time', 'get_date', 'current_time'})


class RecoveryWriteError(RuntimeError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode('utf-8')).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def input_key(entry):
    identity = [entry.get(k) for k in ('conversation_id', 'reply_to', 'request_id')]
    return str(entry.get('input_key') or ('input-' + digest(identity) if any(identity) else uuid4().hex))


class RecoveryStore:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {'version': 1, 'active': None, 'inputs': [], 'history': []}
        if self.path.exists():
            try:
                value = json.loads(self.path.read_text(encoding='utf-8'))
                if (not isinstance(value, dict) or value.get('version') != 1
                        or not isinstance(value.get('inputs'), list)
                        or not isinstance(value.get('history'), list)
                        or (value.get('active') is not None and not isinstance(value['active'], dict))):
                    raise ValueError('unsupported checkpoint schema')
                self.data = value
            except Exception as exc:
                raise RecoveryWriteError('Work checkpoint is unreadable; preserved for repair, not reset') from exc

    def update(self, edit):
        next_data = deepcopy(self.data)
        result = edit(next_data)
        next_data['updated_at'] = now()
        temporary = self.path.with_name(self.path.name + '.' + uuid4().hex + '.tmp')
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open('w', encoding='utf-8', newline='\n') as out:
                json.dump(next_data, out, ensure_ascii=False, separators=(',', ':'))
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, self.path)
        except Exception as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise RecoveryWriteError('Work checkpoint could not be saved; action was not authorized') from exc
        self.data = next_data
        return result

    def receive(self, entry):
        if not isinstance(entry, dict) or entry.get('role', 'user') != 'user':
            raise ValueError('Recovery input must be a user perception')
        content = entry.get('content')
        if not isinstance(content, (str, list)) or not content:
            raise ValueError('Recovery input needs content')
        accepted = {k: deepcopy(entry.get(k)) for k in
                    ('content', 'request_id', 'reply_to', 'conversation_id', 'register', 'images', 'directed_at', 'author')}
        accepted.update(role='user', input_key=input_key(entry), state='received', received_at=now())
        json.dumps(accepted)
        key = accepted['input_key']
        existing = next((row for row in self.data['inputs'] if row['input_key'] == key), None)
        if existing:
            if existing['content'] != accepted['content']:
                raise ValueError('An admitted input identity cannot change content')
            return key
        self.update(lambda data: data['inputs'].append(accepted))
        return key

    def pending_inputs(self):
        return [deepcopy(row) for row in self.data['inputs'] if row['state'] in ('received', 'attending')]

    def resumable(self):
        active = self.data.get('active')
        if not active or active.get('state') not in ('active', 'interrupted', 'recovery_pending', 'paused'):
            return None
        saved = deepcopy(active)
        saved['state'] = 'recovery_pending'
        for attempt in saved.get('attempts', {}).values():
            if attempt.get('state') == 'started':
                attempt['state'] = 'uncertain'
                attempt['reason'] = 'Process ended without a durable completion receipt'
        for generation in saved.get('generations', {}).values():
            if generation.get('state') == 'active':
                generation['state'] = 'interrupted'
        saved['interrupted'] = False
        for segment in saved.get('segments', {}).values():
            if segment.get('state') == 'prepared':
                segment['state'] = 'publication_uncertain'
        return saved

    def start(self, snapshot):
        def edit(data):
            old = data.get('active')
            if old and old.get('state') == 'stopping' and old.get('id') != snapshot['id']:
                old['state'] = 'stopped'
                data['history'] = (data['history'] + [old])[-8:]
                for row in data['inputs']:
                    if row.get('work_id') == old['id'] and row['state'] in ('received', 'attending'):
                        row['state'] = 'cancelled'
            data['active'] = deepcopy(snapshot)
        self.update(edit)

    def sync(self, snapshot):
        self.start(snapshot)

    def bind(self, work_id, keys):
        def edit(data):
            active = data['active']
            if not active or active['id'] != work_id:
                raise ValueError('Input binding requires current work')
            for key in keys:
                row = next((r for r in data['inputs'] if r['input_key'] == key), None)
                if row is None:
                    raise ValueError('Input must be durably received before binding')
                if row['state'] not in ('covered', 'cancelled'):
                    row.update(state='attending', work_id=work_id)
                if key not in active['input_keys']:
                    active['input_keys'].append(key)
            if not active.get('goal'):
                active['goal'] = '\n'.join(str(r['content']) for r in data['inputs'] if r['input_key'] in keys)
        self.update(edit)

    def cancel_input(self, key_or_reply, conversation_id=None):
        def edit(data):
            count = 0
            for row in data['inputs']:
                if ((row['input_key'] == key_or_reply or row.get('reply_to') == key_or_reply)
                        and (conversation_id is None or row.get('conversation_id') == conversation_id)
                        and row['state'] not in ('covered', 'cancelled')):
                    row.update(state='cancelled', cancelled_at=now()); count += 1
            return count
        return self.update(edit)

    def event(self, work_id, event, bound_keys):
        kind = event.get('type')
        def edit(data):
            active = data['active']
            if not active or active['id'] != work_id:
                raise ValueError('Checkpoint requires current work')
            active['last_checkpoint'] = now()
            turn = str(event.get('turn_id') or '')
            generations = active.setdefault('generations', {})
            if kind == 'generation_started':
                for previous in generations.values():
                    if previous.get('state') == 'interrupted':
                        previous.update(state='continued', continued_by=turn)
                generations[turn] = {'state':'active', 'input_revisions':{'0':[] if event.get('autonomous') else list(bound_keys)}}
                if event.get('request_context'):
                    active['request_context'] = deepcopy(event['request_context'])
            elif kind == 'inputs_applied':
                previous = generations.setdefault(turn, {'state':'active', 'input_revisions':{}})
                keys = list(dict.fromkeys([key for values in previous['input_revisions'].values() for key in values] + list(bound_keys)))
                previous['input_revisions'][str(event['input_revision'])] = keys
            elif kind == 'tool_started':
                tool, args = str(event['tool']), deepcopy(event.get('args', {}))
                attempts = active.setdefault('attempts', {})
                fingerprint = digest({'tool':tool, 'args':args})
                if active.get('recovered') and tool not in READ_ONLY_TOOLS:
                    unresolved = [a for a in attempts.values() if a['state'] in ('started', 'uncertain') and a['tool'] not in READ_ONLY_TOOLS]
                    duplicate = [a for a in attempts.values() if a.get('fingerprint') == fingerprint
                                 and a['state'] not in ('verified_not_applied',)]
                    if unresolved or duplicate:
                        active['needs_reconciliation'] = bool(unresolved)
                        return {'allow':False, 'reason':'Recovery held this side effect: an earlier attempt is uncertain or already completed. Inspect the saved receipt and environment; do not replay it automatically.'}
                operation = str(event['operation_id'])
                if operation in attempts:
                    return {'allow':False, 'reason':'Operation identity already exists; not executed twice'}
                attempts[operation] = {'operation_id':operation, 'tool':tool, 'args':args,
                    'fingerprint':fingerprint, 'state':'started', 'started_at':now(), 'turn_id':turn}
                return {'allow':True}
            elif kind == 'reconcile_attempt':
                operation = str(event.get('operation_id') or '')
                attempt = active.setdefault('attempts', {}).get(operation)
                outcome = event.get('outcome')
                evidence = str(event.get('evidence') or '').strip()
                verification_ids = event.get('verification_operation_ids')
                if attempt is None or outcome not in ('verified_completed', 'verified_not_applied', 'uncertain') or not evidence:
                    return {'allow':False, 'reason':'Reconciliation requires a known attempt, explicit outcome and evidence explanation'}
                if not isinstance(verification_ids, list) or not verification_ids:
                    return {'allow':False, 'reason':'Inspect the environment first and cite completed read-only operation IDs'}
                for verification_id in verification_ids:
                    check = active['attempts'].get(str(verification_id))
                    if (not check or check.get('tool') not in READ_ONLY_TOOLS or check.get('state') != 'completed'
                            or str(check.get('started_at','')) < str(attempt.get('started_at',''))):
                        return {'allow':False, 'reason':'Each cited verification must be a completed read-only receipt after the attempted action'}
                attempt.update(state=outcome, reconciliation={'evidence':evidence,
                    'verification_operation_ids':list(verification_ids), 'at':now(),
                    'basis':'Explicit model conclusion tied to actual observations; not an external exactly-once guarantee'})
                active['needs_reconciliation'] = any(a['state'] in ('started','uncertain') and a['tool'] not in READ_ONLY_TOOLS
                                                    for a in active['attempts'].values())
                return {'allow':True, 'reason':'Reconciliation recorded with its cited observations', 'outcome':outcome}
            elif kind == 'tool_completed':
                attempt = active.setdefault('attempts', {}).get(str(event['operation_id']))
                if attempt is None:
                    raise ValueError('Completion has no persisted start')
                outcome = deepcopy(event.get('outcome') or {})
                # A failure/partial/cancelled return can still have produced side effects.
                certain = outcome.get('ok') is True and outcome.get('status') not in ('unknown', 'partial', 'cancellation_requested')
                attempt.update(state='completed' if certain else 'uncertain', outcome=outcome, completed_at=now())
            elif kind in ('segment_prepared', 'segment_delivered'):
                key = str(event['turn_id']) + ':' + str(event['segment_index'])
                segments = active.setdefault('segments', {})
                segment = segments.setdefault(key, {})
                segment.update({k:deepcopy(v) for k,v in event.items() if k!='type'})
                segment['state'] = 'delivered' if kind=='segment_delivered' else 'prepared'
                revision = str(event.get('input_revision', 0))
                keys = generations.get(turn, {}).get('input_revisions', {}).get(revision, [])
                segment['input_keys'] = list(keys)
                if kind == 'segment_delivered' and event.get('final') is True:
                    for row in data['inputs']:
                        if row['input_key'] in keys and row['state'] != 'cancelled':
                            row.update(state='covered', segment=key, covered_at=now())
            elif kind == 'generation_finished':
                generations.setdefault(turn, {})['state'] = 'completed'
            elif kind == 'generation_error':
                generations.setdefault(turn, {})['state'] = 'interrupted'
                active['interrupted'] = True
            return None
        return self.update(edit)

    def finish(self, snapshot, state):
        def edit(data):
            unresolved = any(a['state'] in ('started', 'uncertain') and a['tool'] not in READ_ONLY_TOOLS for a in snapshot.get('attempts', {}).values())
            unfinished = any(g.get('state') not in ('completed', 'continued') for g in snapshot.get('generations', {}).values())
            uncovered = any(row.get('input_key') in snapshot.get('input_keys', []) and row['state'] in ('received','attending') for row in data['inputs'])
            if state == 'completed' and (unresolved or unfinished or uncovered):
                state_value = 'interrupted'
                snapshot['needs_reconciliation'] = unresolved
            else:
                state_value = state
            snapshot['state'] = state_value
            snapshot['ended_at'] = now()
            if state_value in ('interrupted', 'paused'):
                data['active'] = deepcopy(snapshot)
                return
            if state_value == 'stopped':
                for row in data['inputs']:
                    if row.get('work_id') == snapshot['id'] and row['state'] in ('received', 'attending'):
                        row.update(state='cancelled', cancelled_at=now())
            data['history'] = (data['history'] + [deepcopy(snapshot)])[-8:]
            data['active'] = None
        self.update(edit)

    def confirm_publication(self, turn_id, segment_index, text, *, finalize=True):
        active = self.data.get('active') or {}
        key = str(turn_id) + ':' + str(segment_index)
        segment = active.get('segments', {}).get(key)
        if not segment or segment.get('text') != text:
            return False

        self.event(active['id'], {'type':'segment_delivered', **{k:v for k,v in segment.items()
                   if k not in ('state','input_keys','type')}}, [])
        if segment.get('final') is True:
            def complete_generation(data):
                saved = data.get('active')
                if not saved:
                    return
                saved.setdefault('generations', {}).setdefault(str(turn_id), {})['state'] = 'completed'
                unresolved = any(a['state'] in ('started','uncertain') and a['tool'] not in READ_ONLY_TOOLS
                                 for a in saved.get('attempts', {}).values())
                unfinished = any(g.get('state') not in ('completed','continued') for g in saved['generations'].values())
                uncovered = any(row.get('work_id') == saved['id'] and row['state'] in ('received','attending')
                                for row in data['inputs'])
                if finalize and saved.get('kind') == 'conversation' and not (unresolved or unfinished or uncovered):
                    saved.update(state='completed', ended_at=now(), completion_basis='durable final transcript publication')
                    data['history'] = (data['history'] + [deepcopy(saved)])[-8:]
                    data['active'] = None
            self.update(complete_generation)
        return True

    def resolve_attempt(self, operation_id, outcome, evidence):
        if outcome not in ('verified_completed', 'verified_not_applied', 'uncertain') or not str(evidence).strip():
            raise ValueError('Reconciliation needs an explicit outcome and evidence')
        def edit(data):
            attempt = (data.get('active') or {}).get('attempts', {}).get(operation_id)
            if attempt is None:
                raise ValueError('Unknown recovery attempt')
            attempt.update(state=outcome, reconciliation={'evidence':str(evidence), 'at':now()})
            data['active']['needs_reconciliation'] = any(a['state'] in ('started', 'uncertain') and a['tool'] not in READ_ONLY_TOOLS for a in data['active']['attempts'].values())
        self.update(edit)
