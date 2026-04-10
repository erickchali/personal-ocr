import uuid

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

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

        for stream_message in graph.stream(
            {"messages": [HumanMessage(content=user_input)]},
            config=config,
            stream_mode=["updates", "custom"],
            version="v2",
        ):
            chunk_type = stream_message.get("type")
            chunk = stream_message.get("data")

            if chunk_type == "custom":
                print(chunk)
            if "__interrupt__" in chunk:
                interrupt_payload = chunk["__interrupt__"][0].value
                print(interrupt_payload["question"])
                print(interrupt_payload["details"])
                user_choice = input("[y/n]: ").strip().lower()
                decision = user_choice == "y"
                for resume_chunk in graph.stream(
                    Command(resume=decision),
                    config=config,
                    stream_mode="updates",
                    version="v2",
                ):
                    node_name = next(iter(resume_chunk))
                    update = resume_chunk[node_name]
                    if update and "messages" in update:
                        print(f"\nAssistant: {update['messages'][-1].content}")
            else:
                node_name = next(iter(chunk))
                update = chunk[node_name]
                if update and "messages" in update:
                    print(f"\nAssistant: {update['messages'][-1].content}")


if __name__ == "__main__":
    main()
