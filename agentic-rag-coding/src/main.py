from __future__ import annotations

import argparse
import json

from src.api import app, llm, settings, store
from src.contracts.rag_contract_models import Language, UserRequestContract
from src.orchestration.agentic_rag_workflow import AgenticRagWorkflow, MockRetrieverTool


def main() -> None:
    parser = argparse.ArgumentParser(description="Agentic RAG local tools")
    parser.add_argument("command", choices=["demo", "rebuild", "query"])
    parser.add_argument("--question", default="请比较这些论文中的 IMU 步态事件检测方法。")
    args = parser.parse_args()

    if args.command == "rebuild":
        print(json.dumps(store.rebuild(), ensure_ascii=False, indent=2))
        return

    request = UserRequestContract(
        request_id="req_cli_001",
        user_query=args.question,
        task_template="literature_comparison",
        uploaded_paper_ids=[],
        language=Language.ZH,
    )
    retriever = store if args.command == "query" else MockRetrieverTool()
    workflow = AgenticRagWorkflow(retriever_tool=retriever, llm=llm if llm.configured else None)
    response = workflow.run(request)
    print(response.model_dump_json(indent=2, by_alias=True))


if __name__ == "__main__":
    main()
