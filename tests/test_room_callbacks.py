#!/usr/bin/env python3
import json
import hashlib
import os
import pathlib
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock
import test_proxy_handback as f

class CallbackTest(unittest.TestCase):
    def setUp(self):
        self.fx=f.ManagedLifecycleTest(); self.fx.setUp(); self.m=self.fx.module
        self.peer={'id':f.PEER_ID,'provider':'codex-peer','workspaceId':f.WORKSPACE_ID,'archivedAt':None,
          'labels':{'role':'peer','paseo.parent-agent-id':f.LEAD_ID,'room_kind':'managed_slp','work_epoch':'1',
          'assignment_id':'assignment-test','callback_transport':'room-callback-v1'}}
        self.fx.write_agent(self.peer)
        lease=self.fx.read_lease(); lease['peer_briefs']={f.PEER_ID:{'assignment_id':'assignment-test','work_epoch':1}}
        self.fx.write_lease(lease)
    def tearDown(self): self.fx.tearDown()
    def test_automatic_callback_delivers_once_without_acceptance(self):
        out=self.m.relay_room_callback(f.PEER_ID)
        self.assertEqual(out['state'],'DELIVERED')
        sends=[a for _,name,a in self.fx.calls if name=='send_agent_prompt']
        self.assertEqual(len(sends),1); self.assertEqual(sends[0]['agentId'],f.LEAD_ID)
        self.assertFalse(sends[0]['notifyOnFinish']); self.assertIn('Task outcome: DONE',sends[0]['prompt'])
        self.assertTrue(sends[0]['background'])
        self.assertEqual(self.m.relay_room_callback(f.PEER_ID)['state'],'DELIVERED')
        self.assertEqual(len([x for x in self.fx.calls if x[1]=='send_agent_prompt']),1)
        lease=self.fx.read_lease(); self.assertEqual(lease['decision_state'],'WORKING')
        self.assertNotIn('human_decision',lease); self.assertNotIn('peer_reports',lease)
    def test_legacy_wrong_assignment_or_archived_peer_cannot_notify(self):
        for field,value in [('work_epoch','2'),('assignment_id','wrong'),('callback_transport','native')]:
            self.peer['labels'][field]=value; self.fx.write_agent(self.peer)
            self.assertEqual(self.m.relay_room_callback(f.PEER_ID)['state'],'IGNORED')
            self.peer['labels'].update(work_epoch='1',assignment_id='assignment-test',callback_transport='room-callback-v1')
        self.peer['archivedAt']='archived'; self.fx.write_agent(self.peer)
        self.assertEqual(self.m.relay_room_callback(f.PEER_ID)['state'],'IGNORED')
        self.assertFalse(any(x[1]=='send_agent_prompt' for x in self.fx.calls))
    def test_uncertain_delivery_is_not_retried(self):
        original=self.m.upstream_call
        def upstream(agent_id,payload,**kwargs):
            if payload.get('params',{}).get('name')=='send_agent_prompt': raise TimeoutError('unknown transport')
            return original(agent_id,payload,**kwargs)
        self.m.upstream_call=upstream
        self.assertEqual(self.m.relay_room_callback(f.PEER_ID)['state'],'UNCERTAIN')
        self.m.upstream_call=original
        self.fx.activity_update_count += 1
        self.assertEqual(self.m.relay_room_callback(f.PEER_ID)['state'],'UNCERTAIN')
        self.assertFalse(any(x[1]=='send_agent_prompt' for x in self.fx.calls))
    def test_missing_or_stale_handback_never_infers_done(self):
        self.fx.activity_content += '\n[User]\nAnother request with no current handback.'
        self.assertEqual(self.m.relay_room_callback(f.PEER_ID)['outcome'],'NEEDS_LEAD_DECISION')
        sends=[a for _,n,a in self.fx.calls if n=='send_agent_prompt']
        self.assertNotIn('Task outcome: DONE',sends[0]['prompt'])
    def test_startup_reconciles_only_current_opted_in_assignments(self):
        self.m.LEASES_PATH.with_suffix('.json.lock').touch()
        result=self.m.reconcile_room_callbacks()
        self.assertEqual(result['callbacks'][0]['state'],'DELIVERED')
        self.peer['labels']['callback_transport']='native'; self.fx.write_agent(self.peer)
        self.assertEqual(self.m.reconcile_room_callbacks(),{'callbacks':[]})
    def test_relay_preflight_marks_guarded_creation_and_disables_native_notification(self):
        self.m.callback_relay_ready=lambda: True
        calls=[]
        def upstream(agent,payload,**kwargs):
            calls.append((payload,kwargs))
            return {'error':{'code':-32601}} if payload['method']=='tools/list' else {'result':{'isError':False}}
        self.m.upstream_call=upstream
        self.m.run_guard=lambda role,event,agent,name,args,*rest: (True,None,args)
        result=self.m.call_tool(f.LEAD_ID,'lead',1,{'name':'create_agent','arguments':{'notifyOnFinish':True}})
        self.assertFalse(result['result']['isError'])
        payload,options=calls[-1]
        self.assertFalse(options['agent_scoped'])
        self.assertFalse(payload['params']['arguments']['notifyOnFinish'])
        self.assertEqual(payload['params']['arguments']['labels']['callback_transport'],'room-callback-v1')
        self.assertEqual(payload['params']['arguments']['labels']['paseo.parent-agent-id'],f.LEAD_ID)
    def test_pinned_relay_does_not_silently_switch_to_native(self):
        self.m.callback_relay_ready=lambda: False
        self.m.upstream_call=mock.Mock(side_effect=AssertionError('no dispatch'))
        result=self.m.call_tool(f.LEAD_ID,'lead',1,{'name':'send_agent_prompt','arguments':{'agentId':f.PEER_ID}})
        self.assertTrue(result['result']['isError'])
    def test_health_requires_private_fresh_live_matching_proxy(self):
        path=self.m.LEASES_PATH.parent/'callback-relay.json'
        value={'version':1,'pid':os.getpid(),'heartbeat':time.time(),
            'proxyDigest':hashlib.sha256(pathlib.Path(self.m.__file__).read_bytes()).hexdigest()}
        path.write_text(json.dumps(value)); path.chmod(0o600)
        self.assertTrue(self.m.callback_relay_ready())
        for field,bad in [('heartbeat',time.time()-60),('proxyDigest','wrong'),('pid',99999999)]:
            invalid=dict(value); invalid[field]=bad; path.write_text(json.dumps(invalid))
            self.assertFalse(self.m.callback_relay_ready())
        path.write_text(json.dumps(value)); path.chmod(0o644)
        self.assertFalse(self.m.callback_relay_ready())
    def test_running_peer_does_not_produce_done_callback(self):
        self.fx.agent_status='running'
        self.assertEqual(self.m.relay_room_callback(f.PEER_ID)['state'],'WAITING')
        self.assertFalse(any(x[1]=='send_agent_prompt' for x in self.fx.calls))
    def test_native_binding_drift_blocks_delivery(self):
        lease=self.fx.read_lease()
        self.m.workflow.verify_context(lease,self.fx.lead,pin=True); self.fx.write_lease(lease)
        self.fx.lead['config']['model']='drift'; self.fx.write_agent(self.fx.lead)
        with self.assertRaises(self.m.workflow.WorkflowError): self.m.relay_room_callback(f.PEER_ID)
        self.assertFalse(any(x[1]=='send_agent_prompt' for x in self.fx.calls))
    def test_concurrent_end_events_reserve_only_one_notification(self):
        with ThreadPoolExecutor(max_workers=2) as workers:
            results=list(workers.map(self.m.relay_room_callback,[f.PEER_ID,f.PEER_ID]))
        self.assertTrue(all(x['state'] in {'DELIVERED','UNCERTAIN'} for x in results))
        self.assertEqual(len([x for x in self.fx.calls if x[1]=='send_agent_prompt']),1)

if __name__ == '__main__': unittest.main()
