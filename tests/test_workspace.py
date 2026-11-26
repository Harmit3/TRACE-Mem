from datetime import date
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from trace_mem.workspace import Store, server, generate

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'memory.json'; self.store=Store(self.path)
    def test_persistent_across_restart(self):
        self.store.save('Project','Atlas','2025-01-01')
        self.assertEqual(Store(self.path).snapshot(date.today())[0]['value'],'Atlas')
    def test_temporal_correction(self):
        self.store.save('office','Cedar','2025-01-01'); self.store.save('office','Maple','2025-01-02', replaces=self.store.rows[0]['id'])
        self.assertEqual(self.store.snapshot(date(2025,1,1))[0]['value'],'Cedar')
        self.assertEqual(self.store.snapshot(date(2025,1,2))[0]['value'],'Maple')
    def test_unconfirmed_conflict_leaves_state(self):
        self.store.save('office', 'Cedar', '2025-01-01')
        with self.assertRaisesRegex(ValueError, 'Select Edit'):
            self.store.save('office', 'Maple', '2025-01-02')
        self.assertEqual(Store(self.path).snapshot(date.today())[0]['value'], 'Cedar')

    def test_same_day_replacement(self):
        self.store.save('office','Cedar','2025-01-01'); self.store.save('office','Maple','2025-01-01', replaces=self.store.rows[0]['id'])
        self.assertEqual(len(self.store.rows),1); self.assertNotIn('Cedar',self.path.read_text())
    def test_forget_all_versions(self):
        self.store.save('office','Cedar','2025-01-01'); self.store.save('office','Maple','2025-01-02', replaces=self.store.rows[0]['id'])
        self.assertEqual(self.store.forget('office'),2)
        self.assertEqual(Store(self.path).snapshot(date(2025,1,1)),[]); self.assertNotIn('Cedar',self.path.read_text())
    def test_relevance_and_budget(self):
        self.store.save('project deadline','December 10','2025-01-01'); self.store.save('unrelated','x'*2000,'2025-01-01',True)
        evidence,used,count=self.store.select('What is my project deadline?',date.today(),256)
        self.assertEqual([r['label'] for r in evidence],['project deadline']); self.assertLessEqual(used,256); self.assertEqual(count,2)
    def test_pinned_and_no_match(self):
        self.store.save('office','Cedar','2025-01-01')
        self.assertEqual(self.store.select('banana',date.today(),256)[0],[])
        self.store.save('preference','Python','2025-01-01',True)
        self.assertEqual(self.store.select('banana',date.today(),256)[0][0]['label'],'preference')
    def test_reject_backdated_correction(self):
        self.store.save('office','Maple','2025-01-02')
        with self.assertRaises(ValueError): self.store.save('office','Cedar','2025-01-01', replaces=self.store.rows[0]['id'])
    def test_clear(self):
        self.store.save('office','Cedar','2025-01-01'); self.store.clear(); self.assertEqual(Store(self.path).rows,[])
    def test_failed_write_leaves_state(self):
        self.store.save('office','Cedar','2025-01-01')
        with patch('trace_mem.workspace.os.replace',side_effect=OSError):
            with self.assertRaises(OSError): self.store.save('office','Maple','2025-01-02', replaces=self.store.rows[0]['id'])
        self.assertEqual(self.store.rows[0]['value'],'Cedar'); self.assertFalse(self.path.with_name('memory.json.tmp').exists())

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.srv=server(Path(self.tmp.name)/'memory.json',0); self.port=self.srv.server_port
        self.thread=threading.Thread(target=self.srv.serve_forever,daemon=True); self.thread.start()
        self.addCleanup(self.srv.server_close); self.addCleanup(self.srv.shutdown)
    def req(self,method,path,payload=None,headers=None):
        c=HTTPConnection('127.0.0.1',self.port,timeout=3)
        h={'Origin':f'http://127.0.0.1:{self.port}','X-Workspace-Token':self.srv.token,'Content-Type':'application/json'}; h.update(headers or {})
        c.request(method,path,json.dumps(payload) if payload is not None else None,h); r=c.getresponse(); body=r.read(); c.close(); return r.status,body
    def test_static_and_session(self):
        self.assertEqual(self.req('GET','/')[0],200); self.assertEqual(self.req('GET','/app.js')[0],200)
        self.assertEqual(json.loads(self.req('GET','/api/session')[1])['token'],self.srv.token)
    def test_reject_host_origin_token(self):
        for h in ({'Host':'evil.test'},{'Origin':'https://evil.test'},{'X-Workspace-Token':'bad'}): self.assertEqual(self.req('POST','/api/clear',{},h)[0],403)
    def test_end_to_end_memory(self):
        self.assertEqual(self.req('POST','/api/save',{'key':'project','value':'Atlas','date':'2025-01-01'})[0],200)
        q={'question':'What is my project?','date':date.today().isoformat(),'budget':4000}
        status,body=self.req('POST','/api/ask',q); self.assertEqual(status,200); self.assertIn('Atlas',json.loads(body)['answer'])
        self.assertEqual(self.req('POST','/api/forget',{'key':'project'})[0],200)
        self.assertEqual(json.loads(self.req('POST','/api/ask',q)[1])['evidence'],[])
    def test_local_ai_disabled(self):
        q={'question':'hello','date':date.today().isoformat(),'budget':4000,'mode':'ollama'}
        self.assertEqual(self.req('POST','/api/ask',q)[0],400)
    def test_reject_invalid_body(self):
        self.assertEqual(self.req('POST','/api/save',{'key':'x','value':'y','date':'not-a-date'})[0],400)
    def test_local_ai_mock(self):
        self.srv.model='local-test'; q={'question':'hello','date':date.today().isoformat(),'budget':4000,'mode':'ollama'}
        with patch('trace_mem.workspace.generate',return_value='Mock answer') as model:
            status,body=self.req('POST','/api/ask',q); self.assertEqual(status,200); self.assertEqual(json.loads(body)['answer'],'Mock answer'); model.assert_called_once()
    def test_model_http_mock(self):
        with patch('trace_mem.workspace.build_opener') as builder:
            response=builder.return_value.open.return_value.__enter__.return_value
            response.read.return_value=b'{"message":{"content":"Mock local answer"}}'
            self.assertEqual(generate('local-test','hello',[],date.today()),'Mock local answer')
            request=builder.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url,'http://127.0.0.1:11434/api/chat')

if __name__=='__main__': unittest.main()
