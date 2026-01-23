import crewai
print(f"Version: {getattr(crewai, '__version__', 'unknown')}")
print("dir(crewai):")
for x in dir(crewai):
    print(f" - {x}")

try:
    from crewai.tools import BaseTool
    print("\nBaseTool found in crewai.tools")
except ImportError:
    print("\nBaseTool NOT found in crewai.tools")

try:
    from crewai import tool
    print("tool found in crewai")
except ImportError:
    print("tool NOT found in crewai")
