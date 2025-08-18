# run_local.py

import os, asyncio
from orchestrator.agent import Orchestrator

if __name__ == "__main__":
    convo_id = int(os.getenv("TEST_CONVO_ID", "1"))
    result = asyncio.run(Orchestrator().run_once(convo_id))
    print(result)