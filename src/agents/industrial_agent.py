"""
Industrial AI Agent — routes user questions to the right data source,
builds a rich text context, then calls GPT-4 for a grounded answer.

Routing logic
-------------
  "live"       — question about current/now/alarm/status  → read OPC UA
  "historical" — question about trends/history/average     → query MongoDB
  "general"    — anything else                            → no extra context

No LangGraph dependency needed — the routing is a single cheap GPT-4 call
before the main answer call.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert industrial systems analyst with deep knowledge of:
- Process automation and control systems
- OPC UA and industrial communication protocols
- Predictive maintenance and condition monitoring
- Statistical process control (SPC)
- Sensor data interpretation and anomaly analysis

You have access to real-time and historical data from an industrial monitoring system.

When answering questions:
- Be specific: reference actual values, timestamps, and units from the provided context
- Flag anything that warrants immediate attention clearly (use ⚠️ WARNING or 🚨 ALERT)
- Give actionable recommendations, not just observations
- Keep answers clear and structured — use bullet points for multiple items
- If no data context is provided, say so honestly and give general guidance only
"""

ROUTER_PROMPT = """Classify this industrial monitoring question into exactly one category:

"live"       — asks about current values, alarms, status right now
"historical" — asks about trends, history, averages, past events, anomalies
"general"    — general advice, explanations, or questions with no specific data needed

Reply with only the single word: live, historical, or general."""


class IndustrialAgent:
    def __init__(
        self,
        api_key: str,
        mongo_handler=None,
        opcua_client=None,
        tags: Optional[List[Dict]] = None,
        model: str = "gpt-4o-mini",
    ):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.mongo = mongo_handler
        self.opcua = opcua_client
        self.tags = tags or []
        self.model = model

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def chat(
        self,
        history: List[Dict[str, str]],
        question: str,
    ) -> Tuple[str, str, str]:
        """
        Process one user turn.

        Parameters
        ----------
        history  : list of {"role": "user"/"assistant", "content": "..."}
        question : the new user message

        Returns
        -------
        answer      : GPT-4 response string
        query_type  : "live" | "historical" | "general"
        context_str : the data context injected into the prompt (for display)
        """
        query_type = self._classify(question)
        context_str = self._build_context(query_type, question)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if context_str:
            messages.append(
                {
                    "role": "system",
                    "content": f"=== DATA CONTEXT ===\n{context_str}\n=== END CONTEXT ===",
                }
            )

        messages.extend(history)
        messages.append({"role": "user", "content": question})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.4,
            max_tokens=1200,
        )
        answer = response.choices[0].message.content
        return answer, query_type, context_str

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _classify(self, question: str) -> str:
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": ROUTER_PROMPT},
                    {"role": "user", "content": question},
                ],
                temperature=0,
                max_tokens=5,
            )
            label = resp.choices[0].message.content.strip().lower()
            return label if label in ("live", "historical", "general") else "general"
        except Exception as exc:
            logger.warning(f"Router call failed, defaulting to 'general': {exc}")
            return "general"

    # ------------------------------------------------------------------
    # Context builders
    # ------------------------------------------------------------------

    def _build_context(self, query_type: str, question: str) -> str:
        if query_type == "live":
            return self._live_context()
        if query_type == "historical":
            return self._historical_context()
        return ""

    def _live_context(self) -> str:
        if not self.opcua or not self.opcua.connected:
            return "[OPC UA not connected — no real-time data available]"

        tag_paths = [t["path"] for t in self.tags]
        raw = self.opcua.read_tags(tag_paths)
        ts = datetime.now(tz=timezone.utc).strftime("%H:%M:%S UTC")

        lines = [f"REAL-TIME TAG VALUES (as of {ts})", ""]
        for tag in self.tags:
            val = raw.get(tag["path"])
            unit = tag.get("unit", "")
            lo, hi = tag.get("min_range", 0), tag.get("max_range", 100)
            status = ""
            if isinstance(val, (int, float)):
                pct = (float(val) - lo) / (hi - lo) if hi != lo else 0.5
                if pct >= 0.9:
                    status = "  ⚠️ HIGH"
                elif pct <= 0.05:
                    status = "  ⚠️ LOW"
            val_str = f"{val:.4g} {unit}" if isinstance(val, (int, float)) else str(val)
            lines.append(f"  {tag.get('name', tag['path'])}: {val_str} (range {lo}–{hi} {unit}){status}")

        return "\n".join(lines)

    def _historical_context(self, hours: int = 24) -> str:
        if not self.mongo or not self.mongo.connected:
            return "[MongoDB not connected — no historical data available]"

        start = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
        lines = [f"HISTORICAL SUMMARY (last {hours} hours)", ""]

        for tag in self.tags:
            docs = self.mongo.query(tag["path"], start=start)
            if not docs:
                lines.append(f"  {tag.get('name', tag['path'])}: No data in period")
                lines.append("")
                continue

            import pandas as pd
            df = pd.DataFrame(docs)
            df["value"] = pd.to_numeric(df["value"], errors="coerce").dropna()
            vals = df["value"].astype(float)

            # Trend via linear slope
            slope = float(np.polyfit(np.arange(len(vals)), vals, 1)[0]) if len(vals) > 1 else 0
            mean_v = float(vals.mean())
            rel = slope / abs(mean_v) if mean_v != 0 else slope
            trend = "↑ Increasing" if rel > 0.001 else "↓ Decreasing" if rel < -0.001 else "→ Stable"

            # Anomaly count (Z-score > 2.5)
            z = np.abs((vals - vals.mean()) / (vals.std() or 1))
            n_anom = int((z > 2.5).sum())

            unit = tag.get("unit", "")
            name = tag.get("name", tag["path"])
            lines.append(f"  {name}:")
            lines.append(f"    Records : {len(vals):,}")
            lines.append(f"    Mean    : {mean_v:.4g} {unit}")
            lines.append(f"    Range   : {float(vals.min()):.4g} – {float(vals.max()):.4g} {unit}")
            lines.append(f"    Std Dev : {float(vals.std()):.4g} {unit}")
            lines.append(f"    Anomalies (Z>2.5): {n_anom}")
            lines.append(f"    Trend   : {trend}")
            lines.append("")

        return "\n".join(lines)
