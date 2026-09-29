from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

dotenv.load_dotenv(".env")

from app.agent import LabAgent
from app.tracing import get_langfuse_client


def main():
    client = get_langfuse_client()
    agent = LabAgent()

    queries_path = Path("data/sample_queries.jsonl")
    if not queries_path.exists():
        print("data/sample_queries.jsonl not found!")
        return

    queries = [
        json.loads(line)
        for line in queries_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    print(f"Starting generation of {len(queries)} traces on Langfuse...")

    # We will generate traces:
    # First 8 queries with prompt label 'production' (v1)
    # Next 2 queries with prompt label 'candidate' (v2)
    for idx, q in enumerate(queries):
        if idx >= 8:
            os.environ["LANGFUSE_PROMPT_LABEL"] = "candidate"
        else:
            os.environ["LANGFUSE_PROMPT_LABEL"] = "production"

        correlation_id = f"req-tr-{idx+1:02d}-{os.urandom(2).hex()}"
        print(f"[{idx+1}/{len(queries)}] Sending '{q['feature']}' ({os.getenv('LANGFUSE_PROMPT_LABEL')}) | cid: {correlation_id}")
        
        result = agent.run(
            user_id=q["user_id"],
            feature=q["feature"],
            session_id=q["session_id"],
            message=q["message"],
            correlation_id=correlation_id,
        )
        time.sleep(0.1)

    print("Flushing traces to Langfuse Cloud...")
    client.flush()
    print("Done! All traces successfully flushed to Langfuse.")


if __name__ == "__main__":
    main()
