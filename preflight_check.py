"""Pre-flight import check — run this before starting Streamlit."""
import sys
errors = []

checks = [
    ("streamlit", "streamlit"),
    ("plotly", "plotly"),
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("pymongo", "pymongo"),
    ("asyncua", "asyncua"),
    ("openai", "openai"),
    ("scikit-learn", "sklearn"),
    ("langchain", "langchain"),
    ("langchain-openai", "langchain_openai"),
]

print("Checking third-party packages...")
for name, module in checks:
    try:
        __import__(module)
        print(f"  OK  {name}")
    except ImportError as e:
        print(f"  MISSING  {name}: {e}")
        errors.append(name)

print("\nChecking project modules...")
project_modules = [
    "src.core.config_manager",
    "src.core.opcua_client",
    "src.core.mongodb_handler",
    "src.core.data_collector",
    "src.analysis.anomaly_detector",
    "src.analysis.report_generator",
    "src.agents.industrial_agent",
    "src.utils.logger",
]
for mod in project_modules:
    try:
        __import__(mod)
        print(f"  OK  {mod}")
    except Exception as e:
        print(f"  ERROR  {mod}: {e}")
        errors.append(mod)

print()
if errors:
    print(f"FAILED — {len(errors)} issue(s): {errors}")
    sys.exit(1)
else:
    print("All checks passed. Safe to run: streamlit run app.py")
