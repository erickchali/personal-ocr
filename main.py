import uuid

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from agents.graph import builder

load_dotenv()


def main():
    print("Financial Assistant (type 'quit' to exit)")
    print("-" * 40)

    graph = builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    while True:
        user_input = input("\nYou: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        result = graph.invoke({"messages": [HumanMessage(content=user_input)]}, config=config)
        last_message = result["messages"][-1]
        print(f"\nAssistant: {last_message.content}")


if __name__ == "__main__":
    main()
