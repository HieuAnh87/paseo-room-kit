#!/usr/bin/env python3
import unittest
import test_workflow as w
import test_proxy_handback as f

class ModesTest(unittest.TestCase):
    def setUp(self):
        self.fx = w.WorkflowAuthorityTest(); self.fx.setUp(); self.fx.root_binding(policy=True)
        self.m = self.fx.module
        with self.m.locked_leases() as r:
            r['leases'].clear()
    def tearDown(self): self.fx.tearDown()
    def test_direct_modes_and_supervisor_mode(self):
        for mode, task_class, observer in [('L','tiny',None),('LP','bounded',None),('SLP','bounded',f.SUPERVISOR_ID)]:
            with self.subTest(mode=mode):
                result = self.m.bind_root_lead(f.LEAD_ID,observer,task_class,apply=False,execution_mode=mode)
                self.assertEqual(result['binding']['execution_mode'],mode)
                self.assertEqual(result['binding']['supervisor_agent_id'],observer)
    def test_mode_cannot_weaken_policy_or_change_topology(self):
        for mode, task_class, observer in [('L','sensitive',None),('SLP','bounded',None),('LP','bounded',f.SUPERVISOR_ID),('bad','tiny',None)]:
            with self.subTest(mode=mode, observer=observer):
                with self.assertRaises(self.m.workflow.WorkflowError):
                    self.m.bind_root_lead(f.LEAD_ID,observer,task_class,apply=False,execution_mode=mode)
    def test_l_rejects_dispatch_before_guard_or_network(self):
        self.m.bind_root_lead(f.LEAD_ID,None,'tiny',apply=True,execution_mode='L')
        self.m.run_guard=lambda *a, **k: self.fail('L must not admit Peer')
        self.m.upstream_call=lambda *a, **k: self.fail('L must not dispatch')
        result=self.m.call_tool(f.LEAD_ID,'lead',1,{'name':'create_agent','arguments':{'notifyOnFinish':True}})
        self.assertTrue(result['result']['isError'])
        self.assertIn('L mode',f.ManagedLifecycleTest.text(result))

if __name__ == '__main__': unittest.main()
