# Industrial IoT Data Platform

A production-ready multi-page Streamlit application for collecting, storing, visualising, and analysing real-time industrial sensor data via OPC UA and MongoDB Atlas.

---

## Overview

This platform connects directly to OPC UA servers (Kepware, Ignition, Unified Automation, etc.), reads live tag values, stores them in MongoDB Atlas, and presents them through a suite of interactive dashboards — all without writing a single line of custom polling code.

**Core capabilities:**

- Browse the full OPC UA namespace tree and add tags with one click
- Stream live values into auto-refreshing charts and KPI cards
- Store every reading in MongoDB with configurable change-threshold filtering
- Query historical data, compute statistics, and export CSV
- Run Z-score and IsolationForest anomaly detection on any tag
- Generate downloadable HTML / CSV reports

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit 1.58 — `st.navigation()`, `st.fragment(run_every=N)` |
| OPC UA | `asyncua` with `asyncua.sync.Client` (persistent background event loop) |
| Database | MongoDB Atlas via `pymongo` |
| Charts | Plotly — live trend lines, gauges, anomaly scatter plots |
| Analysis | scikit-learn (IsolationForest), SciPy (Z-score) |
| Config | `config/settings.json` (gitignored) — never committed |

---

## Pages

| Page | Description |
|---|---|
| **APP** | Home dashboard — system status, KPI cards, quick navigation |
| **Settings** | OPC UA connection, MongoDB URI, Tag Manager, Tag Browser, Monitoring config |
| **Dashboard** | Auto-refreshing KPI cards, live tag values, rolling trend charts |
| **Realtime Monitor** | Per-tag streaming charts with pause/resume and configurable poll interval |
| **Historical Analysis** | Time-range queries, statistics table, multi-tag comparison, CSV export |
| **Anomaly Detection** | Z-score and IsolationForest detection with annotated Plotly charts |
| **Reports** | Generate and download full HTML or CSV analysis reports |

---

## Getting Started

### Prerequisites

- Python 3.10+
- An OPC UA server (Kepware, Ignition, Unified Automation, etc.)
- A MongoDB Atlas cluster (or local MongoDB instance)

### Installation

```bash
git clone https://github.com/usman-aicoder/Industrial-IoT-Data-Platform.git
cd Industrial-IoT-Data-Platform

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Configuration

Copy the example config and fill in your values:

```bash
cp config/settings.example.json config/settings.json
```

Edit `config/settings.json`:

```json
{
  "opcua": {
    "url": "opc.tcp://your-server:49320",
    "use_auth": false,
    "username": "",
    "password": ""
  },
  "mongodb": {
    "uri": "mongodb+srv://<user>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority",
    "database": "machinedata",
    "collection": "sensor_data"
  },
  "tags": [],
  "monitoring": {
    "poll_interval": 1,
    "store_on_change_only": true,
    "change_threshold": 0.01
  }
}
```

> `config/settings.json` is gitignored — your credentials never leave your machine.

### Run

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Adding Tags

1. Go to **Settings → OPC UA** and connect to your server
2. Open the **Tag Browser** tab — the full OPC UA namespace tree loads inline
3. Expand folders to find variables, click **Add** next to any tag
4. Set a display name, unit, and optional min/max range
5. The tag immediately appears in **Tag Manager** and all dashboards

---

## Project Structure

```
Industrial-IoT-Data-Platform/
├── app.py                        # Navigation router (st.navigation)
├── home.py                       # Home / landing page
├── pages/
│   ├── 01_Settings.py            # OPC UA, MongoDB, Tag Manager, Tag Browser
│   ├── 02_Dashboard.py           # Live KPI cards + trend charts
│   ├── 03_Realtime_Monitor.py    # Per-tag streaming charts
│   ├── 04_Historical_Analysis.py # Time-range query + CSV export
│   ├── 05_Anomaly_Detection.py   # Z-score + IsolationForest
│   └── 07_Reports.py             # HTML / CSV report generator
├── src/
│   ├── core/
│   │   ├── opcua_client.py       # asyncua.sync.Client wrapper
│   │   ├── mongodb_handler.py    # pymongo Atlas handler
│   │   ├── data_collector.py     # Poll + store pipeline
│   │   └── config_manager.py    # settings.json read/write
│   ├── analysis/
│   │   ├── anomaly_detector.py   # Z-score + IsolationForest
│   │   └── report_generator.py  # HTML / CSV generation
│   └── components/
│       └── styles.py             # GLOBAL_CSS, KPI cards, chart helpers
├── config/
│   ├── settings.example.json     # Safe template — commit this
│   └── settings.json             # Your credentials — gitignored
└── requirements.txt
```

---

## Key Design Decisions

**`asyncua.sync.Client` instead of `asyncio.run()`**
Each `asyncio.run()` call creates and destroys an event loop. The asyncua transport is bound to the original loop, so subsequent calls silently fail with `NoneType.send`. Using `asyncua.sync.Client` keeps a single persistent background thread + event loop for the lifetime of the session.

**`st.fragment(run_every=N)` for live charts**
Streamlit's fragment API lets only the chart area rerun on the timer tick, leaving all sidebar controls and page layout untouched. This avoids full-page reruns every second.

**Change-threshold filtering**
To avoid storing identical readings every poll cycle, the data collector compares each new value against the previous one and only writes to MongoDB when the change exceeds the configured threshold (default 1%). This keeps storage lean on slowly-changing tags.

---

## Configuration Reference

| Key | Description | Default |
|---|---|---|
| `opcua.url` | OPC UA endpoint URL | `opc.tcp://localhost:49320` |
| `opcua.use_auth` | Enable username/password auth | `false` |
| `mongodb.uri` | MongoDB connection string | — |
| `mongodb.database` | Database name | `machinedata` |
| `mongodb.collection` | Collection name | `sensor_data` |
| `monitoring.poll_interval` | Seconds between reads | `1` |
| `monitoring.store_on_change_only` | Only write on value change | `true` |
| `monitoring.change_threshold` | Minimum change fraction to store | `0.01` |

---

## License

MIT — free to use, modify, and distribute.
