import json
import unittest
from unittest.mock import patch
from test_switchboard import local_temp
from switchboard import server

try:
    from fastapi.testclient import TestClient
    from switchboard.api import app
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, "Install requirements-dev.txt to test FastAPI")
class FastAPITests(unittest.TestCase):
    def test_public_demo_exact_origin_and_no_shared_message_history(self):
        with patch.object(server,'PUBLIC_ORIGIN','https://demo.example'),patch.object(server,'PROFILE','demo'):
            with patch('switchboard.server.sqlite3.connect',side_effect=AssertionError('Public input persisted')):
                response=self.client.post('/api/enforce',json={'message':'Hello!'},headers={**self.headers,'Origin':'https://demo.example'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(self.client.get('/api/evidence',headers=self.headers).json()['events'],[])
            self.assertTrue(self.client.get('/api/demo-config').json()['public_demo'])
            rejected=self.client.post('/api/enforce',json={'message':'Hello!'},headers={**self.headers,'Origin':'https://demo.example.evil.test'})
            self.assertEqual(rejected.status_code,403)

    def test_public_setting_does_not_disable_private_service_evidence(self):
        with patch.object(server,'PUBLIC_ORIGIN','https://demo.example'),patch.object(server,'PROFILE','service'),\
             patch('switchboard.server.sqlite3.connect',side_effect=OSError('Evidence storage unavailable')):
            with self.assertRaises(OSError):server.record({})
    def test_invalid_shadow_version_and_corrupt_report_fail_closed(self):
        result=self.client.post('/api/shadow',json={'message':'Hello','version':'../../outside'},headers=self.headers)
        self.assertEqual(result.status_code,400)
        with patch('switchboard.api.load_experiments',side_effect=ValueError('Corrupt report')):
            result=self.client.get('/api/experiments',headers=self.headers)
        self.assertEqual(result.status_code,503)
    @classmethod
    def setUpClass(cls):
        cls.tmp = local_temp()
        cls.path = cls.tmp.__enter__()
        cls.old_db = server.DB
        server.DB = cls.path / "api.sqlite"
        cls.client = TestClient(app, base_url="http://127.0.0.1:8765")
        cls.headers = {"Authorization":"Bearer demo-harbor-key"}

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        server.DB = cls.old_db
        cls.tmp.__exit__(None, None, None)

    def test_typed_contract_and_openapi(self):
        self.assertEqual(self.client.get("/api/health").json()["api_framework"], "FastAPI")
        self.assertIn("/api/enforce",self.client.get("/openapi.json").json()["paths"])
        for payload in ({"message":123},{"message":"Hello!","extra":"bad"},{"message":""}):
            self.assertEqual(self.client.post("/api/enforce",json=payload,headers=self.headers).status_code,422)

    def test_authorization(self):
        self.assertEqual(self.client.post("/api/enforce",json={"message":"Hello!"}).status_code,401)
        result=self.client.post("/api/enforce",json={"message":"Hello!","tenant":"cedar"},headers=self.headers)
        self.assertEqual(result.status_code,403)
        self.assertEqual(self.client.get('/api/experiments').status_code,401)
        self.assertEqual(self.client.post('/api/shadow',json={'message':'Hello!'}).status_code,401)
        wrong=self.client.post('/api/shadow',json={'message':'Hello!','tenant':'cedar'},headers=self.headers)
        self.assertEqual(wrong.status_code,403)

    def test_versioned_refund_and_evidence(self):
        payload={"message":"I can refund your $15 transfer fee now.","version":"v2", "context":{"fee_amount":15,"currency":"USD","supervisor_approved":False}}
        result=self.client.post("/api/enforce",json=payload,headers=self.headers)
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()["verdict"],"escalate")
        self.assertIsNone(result.json()["delivered_output"])
        events=self.client.get("/api/evidence",headers=self.headers).json()["events"]
        self.assertTrue(any(e["evidence_id"]==result.json()["evidence_id"] for e in events))

    def test_secret_redaction_and_isolation(self):
        result=self.client.post("/api/enforce",json={"message":"API key sk-demo123456789"},headers=self.headers)
        self.assertEqual(result.json()["verdict"],"block")
        harbor=self.client.get("/api/evidence",headers=self.headers).json()
        cedar=self.client.get("/api/evidence",headers={"Authorization":"Bearer demo-cedar-key"}).json()
        self.assertNotIn("sk-demo123456789",json.dumps(harbor))
        self.assertFalse(any(e["evidence_id"]==result.json()["evidence_id"] for e in cedar["events"]))

    def test_storage_failure_withholds_response(self):
        with patch("switchboard.server.record",side_effect=OSError("Unavailable")):
            result=self.client.post("/api/enforce",json={"message":"Hello!"},headers=self.headers)
        self.assertEqual(result.status_code,503)
        self.assertNotIn("delivered_output",result.json())

    def test_full_and_selective_evaluations(self):
        full=self.client.post("/api/evaluate",json={"mode":"full"},headers=self.headers).json()
        triage=self.client.post("/api/evaluate",json={"mode":"triage"},headers=self.headers).json()
        self.assertEqual(full["correct"],72)
        self.assertEqual(triage["total"],48)
        self.assertIsNone(full["cost_usd"])

    def test_origin_and_static_paths(self):
        result=self.client.post("/api/enforce",json={"message":"Hello!"},headers={**self.headers,"Origin":"https://outside.example"})
        self.assertEqual(result.status_code,403)
        self.assertEqual(self.client.get("/README.md").status_code,404)
        self.assertIn("Can this message",self.client.get("/").text)

    def test_service_context_cannot_be_forged_or_cross_tenant(self):
        from switchboard.context_store import write
        path=self.path/'trusted.sqlite'
        write(path,'harbor','case-15','15',False)
        with patch.object(server,'PROFILE','service'),patch.object(server,'TRUSTED_DB',path):
            self.assertEqual(self.client.get('/api/demo-config').status_code,404)
            payload={'message':'I can refund your $15 transfer fee now.','version':'v2','ticket_id':'case-15'}
            response=self.client.post('/api/enforce',json=payload,headers=self.headers)
            self.assertEqual(response.json()['verdict'],'escalate')
            forged={**payload,'context':{'supervisor_approved':True}}
            self.assertEqual(self.client.post('/api/enforce',json=forged,headers=self.headers).status_code,400)
            other=self.client.post('/api/enforce',json=payload,headers={'Authorization':'Bearer demo-cedar-key'})
            self.assertEqual(other.status_code,404)
            with patch('switchboard.context_store.read',side_effect=OSError('Unavailable')):
                self.assertEqual(self.client.post('/api/enforce',json=payload,headers=self.headers).status_code,503)


if __name__ == "__main__":
    unittest.main()
