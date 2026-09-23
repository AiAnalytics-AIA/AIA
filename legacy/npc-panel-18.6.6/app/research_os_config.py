from __future__ import annotations
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DB_PATH=ROOT/'data'/'research_os.sqlite'
WORKER_HEARTBEAT_PATH=ROOT/'data'/'worker_heartbeat.json'
WORKER_POLL_S=float(os.environ.get('NPC_WORKER_POLL_S','0.5'))
LEASE_SECONDS=int(os.environ.get('NPC_JOB_LEASE_SECONDS','120'))
HEARTBEAT_SECONDS=int(os.environ.get('NPC_JOB_HEARTBEAT_SECONDS','10'))
COST_MODES={
 'ECONOMY':{'default_budget_usd':1.0,'qualitative_provider':'selected','respondent_route':'economy','phase_models':{'research':'sonnet','run':'haiku','interpret':'sonnet','verify':'sonnet','alignment':'sonnet','report':'sonnet'}},
 'STANDARD':{'default_budget_usd':3.0,'qualitative_provider':'selected','respondent_route':'reference','phase_models':{'research':'sonnet','run':'sonnet','interpret':'sonnet','verify':'sonnet','alignment':'sonnet','report':'sonnet'}},
 'REFERENCE':{'default_budget_usd':10.0,'qualitative_provider':'selected','respondent_route':'reference','phase_models':{'research':'sonnet','run':'sonnet','interpret':'sonnet','verify':'sonnet','alignment':'sonnet','report':'sonnet'}},
}
DEFAULT_COST_MODE=os.environ.get('NPC_COST_MODE','REFERENCE').upper()
if DEFAULT_COST_MODE not in COST_MODES: DEFAULT_COST_MODE='REFERENCE'
