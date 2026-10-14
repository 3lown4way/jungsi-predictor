"""Offline tests for bounded, privileged Supabase export without exposing source records."""
import json
import pytest
from scripts.supabase_historical import collect


class Response:
    def __init__(self,items):
        self.items=items
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self):return json.dumps(self.items).encode()


def test_supabase_fetch_only_2022_2026_verified_cohorts():
    calls=[]
    row=dict(year=2025,exam_type="september",program_key="target-major",
        applicant_hash="opaque_report_hash_2025",applied=True,verified=True,
        consented=True,admitted=1,student={"korean_std":133,"inquiries":[]})
    def opener(req,timeout):
        calls.append((req.full_url,timeout))
        return Response([row])
    result=collect("https://instance.supabase.co","test-private-key",opener=opener)
    assert result==[row]
    assert "year=gte.2022" in calls[0][0]
    assert "verified=eq.true" in calls[0][0]
    assert "exam_type=eq.september" in calls[0][0]
    assert "private-key" not in calls[0][0]


def test_untrusted_or_future_inputs_fail_closed():
    with pytest.raises(ValueError,match="Secure"):
        collect("http://insecure.example","secret")
    def fake(req,timeout):
        return Response([dict(year=2027,exam_type="september",program_key="test")])
    with pytest.raises(ValueError,match="schema"):
        collect("https://instance.supabase.co","token",opener=fake)
