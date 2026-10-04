# @nova: Route computer tools to Nova's desktop with explicit environment metadata and verified application outcomes.
# Last updated: 2026-10-04 14:28:11
"""Normal tool-route adapters for Nova's computer and explicit human handoff."""
import json
import os
import uuid
from nova_paths import body_path
from nova_voice.tool_result import ToolResult
from nova_computer.computer import NovaComputer
from nova_computer.hands import Hands
from nova_computer.backends import nova_desktop_command

TOOLS = ('computer_status','computer_look','computer_exec','computer_action')


def handoff(owner=None):
    p=body_path('memory','computer_control.json')
    if owner is not None:
        if owner not in {'human','nova'}: raise ValueError('owner must be human or nova')
        p.parent.mkdir(parents=True,exist_ok=True)
        tmp=p.with_suffix('.tmp'); tmp.write_text(json.dumps({'owner':owner}),encoding='utf-8'); os.replace(tmp,p)
    if not p.exists(): return {'owner':'nova'}
    return json.loads(p.read_text(encoding='utf-8'))


def call(tool,args):
    pc=NovaComputer(); hands=Hands(pc)
    from nova_computer.session import ensure
    session=ensure(pc.backend)
    if tool=='computer_status':
        # Probing the guest can start WSL, so collect status after the probe.
        available=hands.available()
        data={**pc.status(),'hands':available,'control':handoff(),'session':session,
              'viewer':{'url':'http://127.0.0.1:6080/vnc.html','password_file':'nova_body/nova_computer/desktop_secret.json'}}
        return ToolResult(json.dumps(data), status='succeeded' if data['hands']['ready'] else 'failed')
    if tool=='computer_look':
        image=hands.look()
        if not image: return ToolResult('Could not capture the guest display.',status='failed')
        p=body_path('logs','computer',uuid.uuid4().hex+'.png')
        p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(image)
        response=ToolResult(f'Guest screenshot on DISPLAY={hands.display}: {p}',artifacts=[{'kind':'image','path':str(p),'display':hands.display}])
        response.environment={'backend':pc.backend.name,'target':'nova_desktop','display':hands.display}
        return response
    if handoff()['owner']=='human':
        return ToolResult('Cole has control of the VM. Observation remains available; actions are paused.',status='refused')
    if tool=='computer_exec':
        from nova_voice.tool_router import _catastrophic, _sealed_cmd
        command=str(args.get('command',''))
        reason=_catastrophic(command) or _sealed_cmd(command)
        if reason: return ToolResult(reason,status='refused')
        rc,out=pc.bash(nova_desktop_command(command,hands.display),timeout=min(120,max(1,int(args.get('timeout',30)))))
    else:
        action=args.get('action')
        if action=='launch':
            from nova_voice.tool_router import _catastrophic, _sealed_cmd
            command=str(args.get('parameters',{}).get('command',''))
            reason=_catastrophic(command) or _sealed_cmd(command)
            if reason: return ToolResult(reason,status='refused')
        allowed={'click':hands.click,'double_click':hands.double_click,'move':hands.move,
                 'scroll':hands.scroll,'key':hands.key,'type_text':hands.type_text,
                 'drag':hands.drag,'windows':hands.windows,
                 'launch':hands.launch,'open_url':hands.open_url}
        if action not in allowed:
            return ToolResult('Unknown computer action. Use '+', '.join(allowed),status='failed')
        result=allowed[action](**args.get('parameters',{}))
        if isinstance(result,dict) and action in {'launch','open_url'}:
            response=ToolResult(json.dumps(result),status=result['status'],exit_code=result.get('exit_code'),
                                stdout=result.get('stdout',''),stderr=result.get('stderr',''))
            response.environment={'backend':pc.backend.name,'target':'nova_desktop','shell':'bash','display':hands.display}
            return response
        if not isinstance(result,tuple):
            return ToolResult(json.dumps(result),status='unknown')
        rc,out=result
    status={0:'succeeded',124:'timed_out',130:'cancelled'}.get(rc,'failed')
    response=ToolResult(out,status=status,exit_code=rc,stdout=out)
    response.environment={'backend':pc.backend.name,'target':'guest','shell':'bash','default_display':hands.display,
                          'note':'computer_exec may explicitly override its environment; screenshots and launch actions target Nova desktop.'}
    return response
