"""Explicit local inference benchmark, isolated from editorial data and platforms."""
import json
import time
from .store_poc import ROOT
from .review_ai import LocalModel
from .ai_settings import settings


def run(conn, model=None):
    cfg=settings(conn,LocalModel().model)
    model=model or LocalModel(model=cfg['model'],policy=cfg['policy'])
    if not model.ready:raise ValueError('Local AI is unavailable')
    cases=json.loads((ROOT/'config/ai_judgment_cases.json').read_text())['cases']
    results=[]
    for case in cases:
        started=time.monotonic()
        try:
            output=model.review(dict(text=case['text'],platform='linkedin',created_at=None))
            results.append(dict(id=case['id'],expected=case['expected'],actual=output['recommendation'],passed=output['recommendation']==case['expected'],reason=output['reason'],seconds=round(time.monotonic()-started,2),source_url=case.get('source_url'),media_count=case.get('media_count',0)))
        except Exception:
            results.append(dict(id=case['id'],expected=case['expected'],actual='error',passed=False,reason='Local inference failed; no retry.',seconds=round(time.monotonic()-started,2)))
    passed=sum(r['passed'] for r in results)
    report=dict(model=model.model,scope='Text judgment only; images/video are not visually analyzed. No posts created, fetched, approved or deleted.',passed=passed,total=len(results),false_rejects=sum(r['expected']=='approve' and r['actual']=='reject' for r in results),results=results)
    return report
