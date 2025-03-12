from tavily import AsyncTavilyClient
import asyncio
from typing import List, Dict, Optional
import os


class SearchClient:
    def __init__(self,api_key: str):
        """
        Initialize the Tavily search client
        
        Args:
            api_key: Tavily API key
        """
        self.client = AsyncTavilyClient(api_key)

    async def search(self, 
               query: str, 
               search_depth: str = "basic",
               include_images: bool = False,
               include_answer: bool = True,
               max_results: int = 5) -> Dict:
        """
        Execute a search
        
        Args:
            query: Search query
            search_depth: Depth of the search ("basic" or "advanced")
            include_images: Whether to include image results
            include_answer: Whether to include AI-generated answers
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary containing the search results
        """
        try:
            response = await self.client.search(
                query=query,
                search_depth=search_depth,
                include_images=include_images,
                include_answer=include_answer,
                max_results=max_results
            )
            return response
        except Exception as e:
            print(f"Exception: {e}")
            raise RuntimeError(f"Search error occurred: {e}")

    async def qna_search(self,
                        query: str,
                        search_depth: str = "advanced",
                        topic: str = "general",
                        max_results: int = 5) -> str:
        """
        Execute a search and return a direct answer to the question
        
        Args:
            query: The question text
            search_depth: Depth of the search ("basic" or "advanced")
            topic: Search category ("general" or "news")
            max_results: Maximum number of results to return
            
        Returns:
            String containing the answer to the question
        """
        try:
            answer = await self.client.qna_search(
                query=query,
                search_depth=search_depth,
                topic=topic,
                max_results=max_results
            )
            return answer
        except Exception as e:
            print(f"QnA search error occurred: {e}")
            raise RuntimeError(f"QnA search error occurred: {e}")


async def main():
    # Set API key
    API_KEY = os.getenv("TAVILY_API_KEY")
    if not API_KEY:
        print("TAVILY_API_KEY environment variable not found")
        raise ValueError("TAVILY_API_KEY environment variable required")
    client = SearchClient(API_KEY)
    
    # Search example
    query = "How does artificial intelligence impact society?"
    
    # Basic search
    print("Basic search results:")
    results = await client.search(query)
    if results:
        # Display AI-generated answer
        if 'answer' in results:
            print("\nAI Answer:")
            print(results['answer'])
        
        # Display search results
        print("\nSearch Results:")
        for i, result in enumerate(results.get('results', []), 1):
            print(f"\n{i}. {result.get('title', 'No title')}")
            print(f"URL: {result.get('url', 'No URL')}")
            print(f"Summary: {result.get('snippet', 'No summary')}")
    
    # QnA search example
    print("\n\nQnA Search:")
    answer = await client.qna_search(
        "What can be done to address climate change?"
    )
    print(f"Answer: {answer}")


if __name__ == "__main__":
    asyncio.run(main())
