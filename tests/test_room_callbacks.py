#!/usr/bin/env python3
import json
import hashlib
import os
import pathlib
import time
import threading
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
        lease=self.fx.read_lease(); lease['callback_outbox_version']=2; lease['peer_briefs']={f.PEER_ID:{'assignment_id':'assignment-test','work_epoch':1}}
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
        self.assertTrue(all(x['state'] in {'DELIVERED','UNCERTAIN','BUSY'} for x in results))
        self.assertEqual(len([x for x in self.fx.calls if x[1]=='send_agent_prompt']),1)

    def save_ready(self):
        with mock.patch.object(self.m, 'deliver_callback_outbox', side_effect=SystemExit('crash before send')):
            with self.assertRaises(SystemExit):
                self.m.relay_room_callback(f.PEER_ID)
        return next(iter(self.fx.read_lease()['callback_deliveries'].values()))

    def resolution(self, item, action):
        return {'leadAgentId': f.LEAD_ID, 'messageId': item['message_id'],
                'resolution': action, 'evidence': 'Inspected exact recipient timeline and delivery result',
                'expectedWorkEpoch': 1, 'expectedRevision': self.fx.read_lease()['revision']}

    def test_ready_restart_uses_immutable_payload_without_timeline(self):
        saved = self.save_ready()
        self.assertEqual(saved['state'], 'READY')
        self.fx.activity_content = 'Different later activity'
        original = self.m.upstream_call
        def send_only(agent, payload, **kwargs):
            self.assertEqual(payload['params']['name'], 'send_agent_prompt')
            receipt = self.fx.read_lease()['callback_deliveries'][saved['message_id']]
            self.assertEqual(receipt['state'], 'SENDING')
            self.assertEqual(receipt['payload'], saved['payload'])
            self.assertIn(saved['payload']['handback'], payload['params']['arguments']['prompt'])
            self.assertIn(saved['message_id'], payload['params']['arguments']['prompt'])
            return original(agent, payload, **kwargs)
        self.m.upstream_call = send_only
        result = self.m.reconcile_room_callbacks()['callbacks'][0]
        self.assertEqual(result['state'], 'DELIVERED')
        self.assertEqual(result['payload_digest'], saved['payload_digest'])

    def test_real_sender_exit_after_send_leaves_uncertain_without_replay(self):
        saved = self.save_ready()
        marker = self.m.LEASES_PATH.parent / 'recipient-received'
        pid = os.fork()
        if pid == 0:
            def interrupted(*args, **kwargs):
                marker.write_text(saved['message_id'])
                os._exit(19)  # Recipient got it; process dies before receipt commit.
            self.m.upstream_call = interrupted
            self.m.relay_room_callback(f.PEER_ID)
            os._exit(20)
        _, status = os.waitpid(pid, 0)
        self.assertEqual(os.waitstatus_to_exitcode(status), 19)
        self.assertEqual(marker.read_text(), saved['message_id'])
        self.assertEqual(self.fx.read_lease()['callback_deliveries'][saved['message_id']]['state'], 'SENDING')
        self.m.upstream_call = mock.Mock(side_effect=AssertionError('must not replay'))
        result = self.m.relay_room_callback(f.PEER_ID)
        self.assertEqual(result['state'], 'UNCERTAIN')
        self.assertEqual(result['payload'], saved['payload'])

    def test_crash_before_network_after_reservation_is_also_uncertain(self):
        self.save_ready()
        with mock.patch.object(self.m, 'upstream_call', side_effect=SystemExit('crash before network')):
            with self.assertRaises(SystemExit):
                self.m.relay_room_callback(f.PEER_ID)
        self.m.upstream_call = mock.Mock(side_effect=AssertionError('must not replay'))
        self.assertEqual(self.m.relay_room_callback(f.PEER_ID)['state'], 'UNCERTAIN')

    def test_stale_ready_epoch_or_assignment_is_cancelled(self):
        saved = self.save_ready()
        self.peer['labels']['assignment_id'] = 'replacement'
        self.fx.write_agent(self.peer)
        self.m.upstream_call = mock.Mock(side_effect=AssertionError('stale send'))
        result = self.m.relay_room_callback(f.PEER_ID)
        self.assertEqual(result['state'], 'CANCELLED')
        self.assertEqual(result['payload'], saved['payload'])

    def test_ready_from_previous_epoch_cannot_send(self):
        self.save_ready()
        lease = self.fx.read_lease(); lease['work_epoch'] = 2; self.fx.write_lease(lease)
        self.m.upstream_call = mock.Mock(side_effect=AssertionError('stale epoch send'))
        self.assertEqual(self.m.relay_room_callback(f.PEER_ID)['state'], 'CANCELLED')

    def test_payload_corruption_fails_closed(self):
        saved = self.save_ready()
        lease = self.fx.read_lease()
        lease['callback_deliveries'][saved['message_id']]['payload']['handback'] = 'changed'
        self.fx.write_lease(lease)
        self.m.upstream_call = mock.Mock(side_effect=AssertionError('corrupt send'))
        with self.assertRaisesRegex(self.m.workflow.WorkflowError, 'payload'):
            self.m.relay_room_callback(f.PEER_ID)

    def test_network_releases_registry_but_fences_own_lease(self):
        entered, finish = threading.Event(), threading.Event()
        original = self.m.upstream_call
        def slow_send(agent, payload, **kwargs):
            if payload['params']['name'] == 'send_agent_prompt':
                entered.set()
                if not finish.wait(5): raise AssertionError('registry was blocked by network')
            return original(agent, payload, **kwargs)
        self.m.upstream_call = slow_send
        with ThreadPoolExecutor(max_workers=2) as pool:
            sender = pool.submit(self.m.relay_room_callback, f.PEER_ID)
            self.assertTrue(entered.wait(5))
            def governance():
                with self.m.locked_leases() as registry:
                    other = dict(registry['leases'][f.WORKSPACE_ID], workspace_id='fake-other', lead_agent_id='other-lead', callback_deliveries={})
                    registry['leases']['fake-other'] = other
                with self.assertRaisesRegex(self.m.workflow.WorkflowError, 'fences'):
                    with self.m.locked_leases() as registry:
                        registry['leases'][f.WORKSPACE_ID]['work_epoch'] = 2
                with self.assertRaisesRegex(self.m.workflow.WorkflowError, 'in flight'):
                    self.m.withdraw_binding({'agentId':f.LEAD_ID, 'expectedWorkEpoch':1,
                        'expectedRevision':self.fx.read_lease()['revision'], 'settlementEvidence':'test'}, apply=True)
                with self.m.read_locked_leases() as registry:
                    self.assertIn('fake-other', registry['leases'])
                return True
            try:
                self.assertTrue(pool.submit(governance).result(timeout=3))
                self.assertEqual(self.m.relay_room_callback(f.PEER_ID)['state'], 'BUSY')
            finally:
                finish.set()
            self.assertEqual(sender.result()['state'], 'DELIVERED')

    def test_resolution_requires_human_cas_and_explicit_retry(self):
        original = self.m.upstream_call
        saved = self.save_ready()
        self.m.upstream_call = mock.Mock(side_effect=TimeoutError('lost response'))
        self.m.relay_room_callback(f.PEER_ID)
        request = self.resolution(saved, 'NOT_DELIVERED')
        with self.assertRaises(self.m.workflow.WorkflowError):
            self.m.resolve_callback_delivery(request, apply=True, role='lead')
        with self.assertRaises(self.m.workflow.WorkflowError):
            self.m.resolve_callback_delivery(dict(request, expectedRevision=0), apply=True)
        self.assertFalse(self.m.resolve_callback_delivery(request)['applied'])
        self.assertEqual(self.fx.read_lease()['callback_deliveries'][saved['message_id']]['state'], 'UNCERTAIN')
        self.m.resolve_callback_delivery(request, apply=True)
        self.assertEqual(self.fx.read_lease()['callback_deliveries'][saved['message_id']]['state'], 'REJECTED')
        self.m.upstream_call = original
        result = self.m.resolve_callback_delivery(self.resolution(saved, 'RETRY'), apply=True)
        self.assertEqual(result['receipt']['state'], 'DELIVERED')
        self.assertEqual(result['receipt']['payload'], saved['payload'])
        self.assertEqual(len([x for x in self.fx.calls if x[1]=='send_agent_prompt']), 1)

    def test_followup_activity_gets_new_message_but_duplicates_do_not(self):
        first = self.m.relay_room_callback(f.PEER_ID)
        self.assertEqual(self.m.relay_room_callback(f.PEER_ID)['message_id'], first['message_id'])
        self.fx.activity_update_count += 1
        self.fx.activity_content = 'Task outcome: DONE\nFollow-up proof'
        second = self.m.relay_room_callback(f.PEER_ID)
        self.assertNotEqual(first['message_id'], second['message_id'])
        self.assertEqual(len([x for x in self.fx.calls if x[1]=='send_agent_prompt']), 2)

    def test_legacy_receipt_is_not_upgraded_or_replayed(self):
        key = self.m.digest_payload({'peer':f.PEER_ID, 'epoch':1, 'assignment':'assignment-test',
                                     'activity':self.fx.activity_update_count})
        legacy = {'state':'DELIVERED', 'agent_id':f.PEER_ID, 'assignment_id':'assignment-test', 'work_epoch':1}
        lease = self.fx.read_lease(); lease['callback_deliveries'] = {key:legacy}; self.fx.write_lease(lease)
        self.assertEqual(self.m.relay_room_callback(f.PEER_ID), legacy)
        self.assertFalse(any(x[1]=='send_agent_prompt' for x in self.fx.calls))

    def test_existing_binding_keeps_legacy_transport_until_checkpoint(self):
        lease = self.fx.read_lease(); lease.pop('callback_outbox_version'); self.fx.write_lease(lease)
        result = self.m.relay_room_callback(f.PEER_ID)
        self.assertEqual(result['state'], 'DELIVERED')
        self.assertNotIn('payload', result)
        self.assertNotIn('callback_outbox_version', self.fx.read_lease())

    def test_resolution_cannot_race_active_sender(self):
        saved = self.save_ready()
        request = self.resolution(saved, 'NOT_DELIVERED')
        with self.m.callback_process_lock(f.PEER_ID) as acquired:
            self.assertTrue(acquired)
            with self.assertRaisesRegex(self.m.workflow.WorkflowError, 'still active'):
                self.m.resolve_callback_delivery(request, apply=True)

    def test_oversize_handback_is_not_truncated_and_sent(self):
        self.fx.activity_content = 'Task outcome: DONE\n' + 'x' * 65536
        with self.assertRaisesRegex(self.m.workflow.WorkflowError, '64 KiB'):
            self.m.relay_room_callback(f.PEER_ID)
        self.assertNotIn('callback_deliveries', self.fx.read_lease())

if __name__ == '__main__': unittest.main()
