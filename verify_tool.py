from crewai import Agent, Tool
from langchain_community.tools import DuckDuckGoSearchRun

# Attempt 3: Using Tool class from crewai (if available directly or via encapsulation)
try:
    print("\nTesting CrewAI Tool wrapper...")
    
    # Define a custom tool class inheriting/using what CrewAI expects
    # In recent CrewAI, one can typically pass a custom tool object
    
    # Try creating a class that matches BaseTool signature if possible, 
    # OR better, use the LangChain tool BUT ensure pydantic compat.
    
    # If the issue is Pydantic V2, we might need a shim.
    
    # Let's try to inspect what Agent expects
    # agent = Agent(..., tools=[...])
    
    # Try the decorator approach which is standard
    try:
        from crewai_tools import tool
        print("Imported tool from crewai_tools")
        
        @tool
        def search(query: str):
            """Search the web."""
            return DuckDuckGoSearchRun().run(query)
            
        agent = Agent(role='T', goal='G', backstory='B', tools=[search], verbose=True)
        print("Decorator tool Success!")
        
    except ImportError:
        print("crewai_tools not found, trying 'from crewai import tool'")
        try:
            from crewai import tool
            @tool("Search")
            def search(query: str):
                """Search the web."""
                return DuckDuckGoSearchRun().run(query)
                
            agent = Agent(role='T', goal='G', backstory='B', tools=[search], verbose=True)
            print("Decorator tool from crewai Success!")
        except Exception as e:
             print(f"Decorator from crewai failed: {e}")

except Exception as e:
    print(f"Wrapper Failed: {e}")
