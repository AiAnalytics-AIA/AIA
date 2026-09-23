from __future__ import annotations
from typing import Any
OPS={'<':lambda a,b:a<b,'<=':lambda a,b:a<=b,'>':lambda a,b:a>b,'>=':lambda a,b:a>=b,'==':lambda a,b:a==b,'!=':lambda a,b:a!=b}
def evaluate(condition:dict[str,Any],metrics:dict[str,Any])->bool:
 metric=str(condition.get('metric') or '')
 if not metric or metric not in metrics:raise KeyError(f'Unknown metric: {metric}')
 op=str(condition.get('op') or '==')
 if op not in OPS:raise ValueError(f'Unsupported op: {op}')
 return bool(OPS[op](metrics[metric],condition.get('value')))
