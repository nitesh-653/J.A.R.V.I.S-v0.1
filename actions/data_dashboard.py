"""
data_dashboard.py — Mark XXXIX Instant Data Dashboard
Converts CSV/Excel files into beautiful self-contained HTML dashboards with Chart.js.
"""
import json
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
import google.generativeai as genai

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _get_api_key() -> str:
    config_path = _base_dir() / "config" / "api_keys.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]

_SYSTEM_PROMPT = """\
You are a data visualization expert. Given CSV/tabular data, generate a stunning self-contained HTML dashboard.
Requirements:
- Use Chart.js (CDN: https://cdn.jsdelivr.net/npm/chart.js)
- Include a summary stats card row at the top (count, mean, min, max for numeric cols)
- 2-3 appropriate charts (bar, line, pie — choose based on data)
- A searchable/sortable HTML table
- Dark theme (#1a1a2e background, accent #7c3aed)
- Smooth fade-in animations
- Fully responsive grid layout
- Title from the data context
Return ONLY the raw HTML file. No markdown, no explanation."""

def _read_file(file_path: Path) -> tuple[str, str]:
    ext = file_path.suffix.lower()
    try:
        if ext in (".csv", ".tsv"):
            sep = "\t" if ext == ".tsv" else ","
            import pandas as pd
            df = pd.read_csv(file_path, sep=sep, nrows=500)
            return df.to_csv(index=False), ""
        elif ext in (".xlsx", ".xls", ".xlsm"):
            import pandas as pd
            df = pd.read_excel(file_path, nrows=500)
            return df.to_csv(index=False), ""
        else:
            return "", f"Unsupported file type: {ext}"
    except ImportError:
        return "", "pandas is not installed. Run: pip install pandas openpyxl"
    except Exception as e:
        return "", str(e)

def data_dashboard(
    parameters: dict,
    player=None,
    speak=None,
) -> str:
    file_path_str = parameters.get("file_path", "").strip()
    if not file_path_str:
        return "Please provide the path to your CSV or Excel file."

    file_path = Path(file_path_str)
    if not file_path.exists():
        desktop = Path.home() / "Desktop" / file_path_str
        if desktop.exists():
            file_path = desktop
        else:
            return f"File not found: {file_path_str}"

    if player:
        player.write_log(f"[Dashboard] Reading: {file_path.name}")
    if speak:
        speak(f"Reading {file_path.name} and building your dashboard, sir.")

    csv_text, error = _read_file(file_path)
    if error:
        return f"Could not read file: {error}"

    if len(csv_text) > 12000:
        lines = csv_text.split("\n")
        header = lines[0]
        csv_text = header + "\n" + "\n".join(lines[1:201])

    try:
        genai.configure(api_key=_get_api_key())
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=_SYSTEM_PROMPT,
        )
        response = model.generate_content(
            f"File name: {file_path.name}\n\nData:\n{csv_text}"
        )
        html = response.text.strip()
        html = re.sub(r"^```html?\s*", "", html, flags=re.IGNORECASE)
        html = re.sub(r"\s*```$", "", html).strip()
    except Exception as e:
        return f"Could not generate dashboard: {e}"

    output_dir = file_path.parent
    ts = datetime.now().strftime("%H%M%S")
    out_path = output_dir / f"{file_path.stem}_dashboard_{ts}.html"
    try:
        out_path.write_text(html, encoding="utf-8")
    except Exception as e:
        out_path = Path.home() / "Desktop" / f"dashboard_{ts}.html"
        out_path.write_text(html, encoding="utf-8")

    try:
        webbrowser.open(out_path.as_uri())
    except Exception:
        pass

    if player:
        player.write_log(f"[Dashboard] ✅ {out_path.name}")
    return f"Dashboard generated from '{file_path.name}' and opened in browser, sir."
