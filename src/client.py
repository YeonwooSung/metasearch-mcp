from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import os


async def main():
    server_params = StdioServerParameters(
        command="/usr/local/bin/uv",  # path to server.py
        args=[
            "--directory",
            "/usr/src/app/mcp-server-tavily",
            "run",
            "tavily-search"
        ],
        env={
            "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY"),
            "PYTHONIOENCODING": "utf-8"
        }
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            try:
                tools = await session.list_tools()
                print(f"list of tools to use: {tools}")

                tool_result = await session.call_tool(
                    "search",
                    arguments={"query": "今日の東京タワーのイベントを教えて下さい"}
                )
                print(f"result of tool calling: {tool_result}")

            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
