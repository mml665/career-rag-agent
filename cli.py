from rag_agent import RagAssistant


def main() -> None:
    assistant = RagAssistant()
    if not assistant.is_configured():
        print("请先复制 .env 为 .env，并设置 DASHSCOPE_API_KEY。")
        return

    count = assistant.ingest_all()
    print(f"已索引 {count} 个资料片段。")
    print("输入问题开始问答，输入 /exit 退出。")

    while True:
        question = input("\n问题> ").strip()
        if question in {"/exit", "exit", "quit"}:
            break
        if not question:
            continue
        result = assistant.ask(question)
        print("\n回答：")
        print(result["answer"])
        print("\n来源：")
        for source in result["sources"]:
            page = f" p.{source['page']}" if source.get("page") else ""
            print(f"- {source['source']}{page}: {source['content']}")


if __name__ == "__main__":
    main()
