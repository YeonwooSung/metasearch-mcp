import os
import logging
from collections.abc import Sequence
from typing import Any, Dict, Union
from tavily import AsyncTavilyClient
from dotenv import load_dotenv
from mcp.server import Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
)
from pydantic import AnyUrl
import asyncio
import aiohttp


load_dotenv()

# create logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("metasearch-mcp")


# API key for Tavily API
API_KEY = os.getenv("TAVILY_API_KEY", "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")
if not API_KEY:
    logger.error("TAVILY_API_KEY environment variable not found")
    raise ValueError("TAVILY_API_KEY environment variable required")

# SearXNG URL
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://searxng:8080")
logger.info(f"Using SearXNG URL: {SEARXNG_URL}")


# Prepare the server
app = Server("metasearch-mcp")


@app.list_resources()
async def list_resources() -> list[Resource]:
    logger.info("Listing available resources")
    resources = [
        Resource(
            uri=AnyUrl("websearch://query=`who is current Prime Minister of Japan 2024`,search_depth=`basic`"),
            name="Web Search about `who is current Prime Minister of Japan 2024`.\
                There are two types of search_depth: 'basic' and 'advanced', with 'advanced' searching deeper.'",
            mimeType="application/json",
            description="General web search using Tavily API"
        ),
        Resource(
            uri=AnyUrl("imagesearch://query=`Tokyo skyline`,limit=5"),
            name="Image Search for `Tokyo skyline` with limit of 5 results",
            mimeType="application/json",
            description="Image search using SearXNG API"
        )
    ]
    logger.debug(f"Returning resources with full content: {resources}")
    return resources


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Return a list of available tools"""
    logger.info("Listing available tools")
    tools = [
        Tool(
            name="search",
            description="Search the web using Tavily API",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "search_depth": {
                        "type": "string",
                        "description": "Search depth (basic or advanced)",
                        "enum": ["basic", "advanced"]
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="image_search",
            description="Search for images using SearXNG API",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Image search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of images to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        )
    ]
    logger.debug(f"Returning tools: {tools}")
    return tools


async def process_search_results(results: dict) -> TextContent:
    """Process search results and return TextContent"""
    if not results:
        logger.warning("Empty search results received")
        return TextContent(
            type="text",
            text="No results were found for your query. Please try a different search term."
        )

    response_text = []

    if 'answer' in results and results['answer']:
        logger.info("Search successful - Answer generated")
        response_text.append("AI Answer:")
        response_text.append(results['answer'])
        response_text.append("\n")

    if 'results' in results and results['results']:
        logger.info("Search successful - Results available")
        response_text.append("\nSearch Results:")
        for i, result in enumerate(results['results'], 1):
            response_text.append(f"\n{i}. {result.get('title', 'Title not found')}")
            response_text.append(f"URL: {result.get('url', 'URL not found')}")
            response_text.append(f"Summary: {result.get('snippet', 'Summary not found')}\n")

    if response_text:
        return TextContent(type="text", text="\n".join(response_text))
    
    logger.warning("No answer or results found in search results")
    return TextContent(
        type="text",
        text="The search was completed but no relevant information was found. Please try refining your query."
    )


async def perform_searxng_image_search(query: str, limit: int = 5) -> Dict:
    """Perform image search using SearXNG API"""
    logger.info(f"Performing SearXNG image search for: '{query}' with limit {limit}")
    
    params = {
        "q": query,
        "format": "json",
        "categories": "images",
        "language": "en",
        "pageno": 1,
        "time_range": "",
        "safesearch": 1,
        "theme": "simple"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{SEARXNG_URL}/search", params=params, timeout=30) as response:
                if response.status != 200:
                    logger.error(f"SearXNG API returned status code {response.status}")
                    return {"error": f"SearXNG API returned status code {response.status}"}
                
                data = await response.json()
                logger.debug(f"SearXNG raw response: {data}")
                
                # Extract only relevant image results
                results = []
                if "results" in data:
                    for item in data["results"][:limit]:
                        result = {
                            "title": item.get("title", "No title"),
                            "url": item.get("url", ""),
                            "img_src": item.get("img_src", ""),
                            "source": item.get("source", "Unknown source"),
                            "thumbnail": item.get("thumbnail", ""),
                            "height": item.get("img_height", 0),
                            "width": item.get("img_width", 0)
                        }
                        results.append(result)
                
                return {"query": query, "results": results}
    
    except aiohttp.ClientError as e:
        logger.error(f"Error connecting to SearXNG: {str(e)}")
        return {"error": f"Connection error: {str(e)}"}
    except asyncio.TimeoutError:
        logger.error("SearXNG request timed out")
        return {"error": "Request timed out"}
    except Exception as e:
        logger.error(f"Error during SearXNG image search: {str(e)}", exc_info=True)
        return {"error": f"Error during search: {str(e)}"}


async def process_image_search_results(results: Dict) -> Sequence[Union[TextContent, ImageContent]]:
    """Process image search results and return a sequence of content items"""
    contents = []
    
    if "error" in results:
        return [TextContent(
            type="text",
            text=f"Error in image search: {results['error']}"
        )]
    
    if not results.get("results"):
        return [TextContent(
            type="text",
            text="No image results were found for your query. Please try a different search term."
        )]
    
    # Add text summary of results
    summary_text = f"Found {len(results['results'])} images matching '{results['query']}':\n\n"
    for idx, img in enumerate(results['results'], 1):
        summary_text += f"{idx}. {img['title']}\n"
        summary_text += f"   Source: {img['source']}\n"
        summary_text += f"   URL: {img['url']}\n"
        if img['height'] and img['width']:
            summary_text += f"   Size: {img['width']}x{img['height']}\n"
        summary_text += "\n"
    
    contents.append(TextContent(type="text", text=summary_text))
    
    # Add actual images
    for img in results['results']:
        if img.get('img_src'):
            contents.append(ImageContent(
                type="image",
                url=img['img_src'],
                title=img['title']
            ))
    
    return contents


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[Union[TextContent, ImageContent]]:
    """Calling a tool based on name"""
    logger.info(f"TOOL_CALL_DEBUG: Tool called - name: {name}, arguments: {arguments}")
    
    if name == "search":
        return await handle_tavily_search(arguments)
    elif name == "image_search":
        return await handle_searxng_image_search(arguments)
    else:
        logger.error(f"Unknown tool requested: {name}")
        return [TextContent(
            type="text",
            text=f"Error: Unknown tool '{name}'. Supported tools are 'search' and 'image_search'."
        )]


async def handle_tavily_search(arguments: Dict) -> Sequence[TextContent]:
    """Handle Tavily web search"""
    if not isinstance(arguments, dict) or "query" not in arguments:
        logger.error(f"Invalid arguments provided: {arguments}")
        return [TextContent(
            type="text",
            text="Error: Invalid arguments. A 'query' parameter is required."
        )]

    try:
        client = AsyncTavilyClient(API_KEY)
        query = arguments["query"]
        
        logger.info(f"Executing Tavily search with query: '{query}'")

        search_task = client.search(
            query=query,
            search_depth=arguments.get("search_depth", "basic"),
            include_images=False,
            include_answer=True,
            max_results=3,
            topic="general"
        )

        try:
            # Execute the search with a timeout
            results = await asyncio.wait_for(search_task, timeout=30.0)
            logger.debug(f"Raw search results: {results}")
            
            # Process the results
            return [await process_search_results(results)]

        except asyncio.TimeoutError:
            logger.error("Search operation timed out after 30 seconds")
            return [TextContent(
                type="text",
                text="The search operation timed out. Please try again with a more specific query or check your internet connection."
            )]
            
    except Exception as e:
        error_message = str(e)
        logger.error(f"Search failed: {error_message}", exc_info=True)
        
        # Convert error message to user-friendly format
        if "api_key" in error_message.lower():
            return [TextContent(
                type="text",
                text="Authentication error occurred. Please check the API key configuration."
            )]
        elif "rate limit" in error_message.lower():
            return [TextContent(
                type="text",
                text="Rate limit exceeded. Please wait a moment before trying again."
            )]
        else:
            return [TextContent(
                type="text",
                text=f"An unexpected error occurred during the search. Please try again later. Error: {error_message}"
            )]


async def handle_searxng_image_search(arguments: Dict) -> Sequence[Union[TextContent, ImageContent]]:
    """Handle SearXNG image search"""
    if not isinstance(arguments, dict) or "query" not in arguments:
        logger.error(f"Invalid arguments provided for image search: {arguments}")
        return [TextContent(
            type="text",
            text="Error: Invalid arguments. A 'query' parameter is required for image search."
        )]

    try:
        query = arguments["query"]
        limit = int(arguments.get("limit", 5))
        
        # Ensure limit is reasonable
        if limit < 1:
            limit = 1
        elif limit > 20:
            limit = 20
            
        logger.info(f"Executing SearXNG image search with query: '{query}', limit: {limit}")
        
        # Perform the search
        search_results = await perform_searxng_image_search(query, limit)
        
        # Process the results
        return await process_image_search_results(search_results)
            
    except Exception as e:
        error_message = str(e)
        logger.error(f"Image search failed: {error_message}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"An unexpected error occurred during image search. Please try again later. Error: {error_message}"
        )]


# start the server
async def main():
    logger.info("Starting metasearch server")
    try:
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            logger.info("Server initialized, starting main loop")
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )

    except Exception as e:
        logger.error(f"Server failed to start: {str(e)}", exc_info=True)
        raise


def main_entry():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main_entry()
