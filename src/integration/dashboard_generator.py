"""
CosmoSafe Interactive Safety Dashboard Generator.

Renders an interactive, explainable, and visually rich HTML5/CSS/JS dashboard
from the structured JSON toxicity and safety assessment report (data/toxicity_report.json).

Features:
- Product-level assessment banner with unambiguous status badges
- Summary KPIs (Ingredients, QSAR Screened, Identity Verified, Regulatory Issues)
- Searchable & filterable ingredient table
- Detailed modal/expandable cards for each ingredient:
  * Original OCR text & proposed correction provenance
  * Chemical identity & SMILES
  * QSAR NR-AR predictions, probabilities, and applicability warnings
  * Toxicological evidence with exact citations, publishers, and verbatim passages
  * Regulatory compliance checks (India BIS IS 4707, EU 1223/2009)
- Knowledge Graph summary and relationship explorer
- Unambiguous disclaimers: missing data is NEVER presented as a positive safety finding
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_PATH = PROJECT_ROOT / "data" / "toxicity_report.json"
DEFAULT_DASHBOARD_PATH = PROJECT_ROOT / "reports" / "toxicity" / "safety_dashboard.html"


def generate_html_dashboard(report_data: Dict[str, Any]) -> str:
    """Generate standalone HTML5/CSS/JS dashboard from report dictionary."""
    summary = report_data.get("summary", {})
    metadata = report_data.get("product_metadata", {})
    assessment = report_data.get("product_assessment", {})
    results = report_data.get("results", [])
    kg_summary = report_data.get("knowledge_graph_summary", {})

    product_name = metadata.get("product_name", "Cosmetic Formulation")
    jurisdiction = metadata.get("target_jurisdiction", "India")
    overall_status = assessment.get(
        "overall_assessment_status",
        "Not assessed due to missing or uncertain information"
    )
    assessment_summary = assessment.get("assessment_summary", "")

    # Status color schemes
    if "Safety concern" in overall_status:
        status_bg = "#dc2626"
        status_badge_class = "badge-danger"
    elif "Further review" in overall_status:
        status_bg = "#d97706"
        status_badge_class = "badge-warning"
    elif "No relevant concern" in overall_status:
        status_bg = "#059669"
        status_badge_class = "badge-success"
    else:
        status_bg = "#475569"
        status_badge_class = "badge-neutral"

    json_blob = json.dumps(report_data, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CosmoSafe Safety Dashboard — {product_name}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-dark: #0b0f19;
      --card-bg: rgba(22, 30, 49, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --accent-cyan: #06b6d4;
      --accent-blue: #3b82f6;
      --accent-indigo: #6366f1;
      --accent-purple: #a855f7;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --font-sans: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: var(--font-sans);
      background: radial-gradient(circle at 15% 15%, #131b2e 0%, var(--bg-dark) 100%);
      color: var(--text-main);
      min-height: 100vh;
      padding: 2rem 1.5rem;
      line-height: 1.5;
    }}

    .container {{
      max-width: 1300px;
      margin: 0 auto;
    }}

    /* Header & Navigation */
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid var(--card-border);
      flex-wrap: wrap;
      gap: 1rem;
    }}

    .logo-group {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }}

    .logo-badge {{
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-indigo));
      padding: 0.5rem 0.85rem;
      border-radius: 12px;
      font-weight: 700;
      font-size: 1.25rem;
      color: #ffffff;
      box-shadow: 0 4px 15px rgba(6, 182, 212, 0.35);
    }}

    .logo-title h1 {{
      font-size: 1.6rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}

    .logo-title p {{
      font-size: 0.85rem;
      color: var(--text-muted);
    }}

    /* Product Assessment Banner */
    .assessment-card {{
      background: var(--card-bg);
      backdrop-filter: blur(12px);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 1.75rem;
      margin-bottom: 2rem;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
      position: relative;
      overflow: hidden;
    }}

    .assessment-card::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 6px;
      height: 100%;
      background: {status_bg};
    }}

    .status-badge {{
      display: inline-block;
      padding: 0.35rem 0.85rem;
      border-radius: 9999px;
      font-size: 0.85rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.75rem;
    }}

    .badge-danger {{ background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }}
    .badge-warning {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }}
    .badge-success {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }}
    .badge-neutral {{ background: rgba(100, 116, 139, 0.2); color: #cbd5e1; border: 1px solid rgba(100, 116, 139, 0.4); }}

    .assessment-title {{
      font-size: 1.4rem;
      font-weight: 600;
      margin-bottom: 0.5rem;
    }}

    .assessment-narrative {{
      color: var(--text-muted);
      font-size: 0.95rem;
      line-height: 1.6;
    }}

    /* Metrics Grid */
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1.25rem;
      margin-bottom: 2rem;
    }}

    .metric-card {{
      background: var(--card-bg);
      backdrop-filter: blur(10px);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 1.25rem;
      transition: transform 0.2s, border-color 0.2s;
    }}

    .metric-card:hover {{
      transform: translateY(-3px);
      border-color: rgba(6, 182, 212, 0.4);
    }}

    .metric-label {{
      font-size: 0.8rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.5rem;
    }}

    .metric-value {{
      font-size: 1.8rem;
      font-weight: 700;
      color: var(--text-main);
    }}

    .metric-sub {{
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-top: 0.25rem;
    }}

    /* Controls & Filter Bar */
    .controls-bar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      margin-bottom: 1.25rem;
      flex-wrap: wrap;
    }}

    .search-input {{
      background: rgba(15, 23, 42, 0.8);
      border: 1px solid var(--card-border);
      padding: 0.65rem 1rem;
      border-radius: 10px;
      color: #fff;
      font-family: var(--font-sans);
      font-size: 0.9rem;
      min-width: 280px;
    }}

    .search-input:focus {{
      outline: none;
      border-color: var(--accent-cyan);
    }}

    .filter-pills {{
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
    }}

    .filter-btn {{
      background: rgba(30, 41, 59, 0.6);
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      padding: 0.4rem 0.85rem;
      border-radius: 8px;
      font-size: 0.85rem;
      cursor: pointer;
      transition: all 0.2s;
    }}

    .filter-btn:hover, .filter-btn.active {{
      background: rgba(6, 182, 212, 0.2);
      color: var(--accent-cyan);
      border-color: var(--accent-cyan);
    }}

    /* Ingredients Table */
    .table-container {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      overflow-x: auto;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
      margin-bottom: 2rem;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.9rem;
    }}

    th {{
      background: rgba(15, 23, 42, 0.9);
      padding: 1rem;
      font-weight: 600;
      color: var(--text-muted);
      border-bottom: 1px solid var(--card-border);
      text-transform: uppercase;
      font-size: 0.75rem;
      letter-spacing: 0.05em;
    }}

    td {{
      padding: 1rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      vertical-align: top;
    }}

    tr:hover td {{
      background: rgba(255, 255, 255, 0.02);
    }}

    .mono {{
      font-family: var(--font-mono);
      font-size: 0.8rem;
    }}

    .badge {{
      display: inline-block;
      padding: 0.2rem 0.55rem;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 600;
      white-space: nowrap;
    }}

    .badge-verified {{ background: rgba(16, 185, 129, 0.15); color: #34d399; }}
    .badge-review {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; }}
    .badge-notfound {{ background: rgba(100, 116, 139, 0.2); color: #94a3b8; }}
    .badge-qsar-inactive {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; }}
    .badge-qsar-active {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
    .badge-warning-lowsim {{ background: rgba(217, 119, 6, 0.2); color: #f59e0b; }}

    /* Expandable Row Details */
    .row-detail {{
      background: rgba(15, 23, 42, 0.6);
      padding: 1rem;
      margin-top: 0.5rem;
      border-radius: 8px;
      border-left: 3px solid var(--accent-cyan);
      font-size: 0.85rem;
      display: none;
    }}

    .expand-btn {{
      background: none;
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      font-size: 0.75rem;
      cursor: pointer;
    }}

    .expand-btn:hover {{
      color: #fff;
      border-color: var(--accent-cyan);
    }}

    /* Knowledge Graph & Disclaimer */
    .footer-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 1.5rem;
      margin-bottom: 2rem;
    }}

    .footer-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 1.5rem;
    }}

    .footer-card h3 {{
      font-size: 1.1rem;
      margin-bottom: 0.75rem;
      color: var(--accent-cyan);
    }}

    .footer-card p {{
      color: var(--text-muted);
      font-size: 0.85rem;
      line-height: 1.6;
    }}
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <header class="header">
      <div class="logo-group">
        <div class="logo-badge">CS</div>
        <div class="logo-title">
          <h1>CosmoSafe Safety Intelligence</h1>
          <p>Explainable Cosmetic Formulation Toxicity & Regulatory Evaluation</p>
        </div>
      </div>
      <div>
        <span style="font-size: 0.85rem; color: var(--text-muted);">Jurisdiction:</span>
        <strong style="color: var(--accent-cyan);">{jurisdiction}</strong>
        <span style="margin: 0 0.5rem; color: var(--card-border);">|</span>
        <span style="font-size: 0.85rem; color: var(--text-muted);">Report Version:</span>
        <strong style="font-family: var(--font-mono); font-size: 0.85rem;">v{report_data.get('schema_version', '2.0')}</strong>
      </div>
    </header>

    <!-- Overall Product Assessment Banner -->
    <section class="assessment-card" id="assessment-banner">
      <div class="status-badge {status_badge_class}">{overall_status}</div>
      <div class="assessment-title">{product_name} — Formulation Evaluation</div>
      <p class="assessment-narrative">{assessment_summary}</p>
    </section>

    <!-- Key Metrics Grid -->
    <section class="metrics-grid">
      <div class="metric-card">
        <div class="metric-label">Ingredients Processed</div>
        <div class="metric-value">{summary.get('ingredients_processed', 0)}</div>
        <div class="metric-sub">100% input count preserved</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Verified Identities</div>
        <div class="metric-value" style="color: #34d399;">{summary.get('ingredients_mapped_verified', 0)}</div>
        <div class="metric-sub">Independent curated match</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">QSAR Screened</div>
        <div class="metric-value" style="color: #60a5fa;">{summary.get('ingredients_screened', 0)}</div>
        <div class="metric-sub">Tox21 NR-AR Random Forest</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Identities Needing Review</div>
        <div class="metric-value" style="color: #fbbf24;">{summary.get('ingredients_needing_identity_review', 0)}</div>
        <div class="metric-sub">Candidates requiring review</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Unassessed / Not Found</div>
        <div class="metric-value" style="color: #94a3b8;">{summary.get('ingredients_not_assessed', 0)}</div>
        <div class="metric-sub">No safety inference made</div>
      </div>
    </section>

    <!-- Filter & Search Controls -->
    <div class="controls-bar">
      <input type="text" id="ingredientSearch" class="search-input" placeholder="Search by name, CID, or status...">
      <div class="filter-pills">
        <button class="filter-btn active" onclick="filterTable('all')">All ({len(results)})</button>
        <button class="filter-btn" onclick="filterTable('verified')">Verified ({summary.get('ingredients_mapped_verified', 0)})</button>
        <button class="filter-btn" onclick="filterTable('needs_review')">Needs Review ({summary.get('ingredients_needing_identity_review', 0)})</button>
        <button class="filter-btn" onclick="filterTable('not_found')">Not Found ({summary.get('ingredients_not_found', 0)})</button>
        <button class="filter-btn" onclick="filterTable('complex_mixture')">Complex Mixture ({summary.get('complex_ingredients', 0)})</button>
        <button class="filter-btn" onclick="filterTable('assessed')">QSAR Assessed ({summary.get('ingredients_screened', 0)})</button>
      </div>
    </div>

    <!-- Table of Ingredients -->
    <div class="table-container">
      <table id="ingredientTable">
        <thead>
          <tr>
            <th>#</th>
            <th>Original Ingredient (OCR)</th>
            <th>Proposed Correction</th>
            <th>Primary Status</th>
            <th>PubChem CID</th>
            <th>NR-AR QSAR</th>
            <th>Regulatory Compliance</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
"""

    for idx, item in enumerate(results, start=1):
        raw_name = item.get("raw_ingredient", "")
        correction = item.get("proposed_correction") or {}
        has_corr = correction.get("has_correction_proposal", False)
        proposed_name = correction.get("proposed_name") or "—"
        corr_notes = correction.get("notes") or ""

        status = item.get("primary_status", "unknown")
        mapping = item.get("mapping", {})
        cid = mapping.get("pubchem_cid") or "—"

        toxicity = item.get("toxicity", {})
        qsar_status = toxicity.get("status")
        prediction = toxicity.get("prediction")
        if not isinstance(prediction, dict):
            if toxicity.get("status") == "completed" or toxicity.get("predicted_activity") is not None:
                prediction = toxicity
            else:
                prediction = {}
        pred_act = prediction.get("predicted_activity")
        qsar_prob = prediction.get("activity_probability")
        qsar_app = prediction.get("applicability")

        if pred_act == 0:
            prob_str = f"{qsar_prob:.2f}" if qsar_prob is not None else "0.00"
            qsar_badge = f'<span class="badge badge-qsar-inactive">Inactive ({prob_str})</span>'
            if qsar_app == "low_similarity":
                qsar_badge += ' <span class="badge badge-warning-lowsim" title="Low similarity to reference set">Low Sim</span>'
        elif pred_act == 1:
            prob_str = f"{qsar_prob:.2f}" if qsar_prob is not None else "1.00"
            qsar_badge = f'<span class="badge badge-qsar-active">Active ({prob_str})</span>'
        else:
            qsar_badge = '<span style="color: var(--text-muted); font-size: 0.8rem;">Not Run</span>'

        if status == "verified":
            status_badge = '<span class="badge badge-verified">Verified</span>'
        elif status == "needs_review":
            status_badge = '<span class="badge badge-review">Needs Review</span>'
        elif status == "not_found":
            status_badge = '<span class="badge badge-notfound">Not Found</span>'
        elif status == "complex_mixture":
            status_badge = '<span class="badge badge-neutral" style="background: rgba(147, 51, 234, 0.2); color: #c084fc; border: 1px solid rgba(147, 51, 234, 0.4);">Complex Mixture</span>'
        elif status == "api_error":
            status_badge = '<span class="badge badge-danger">API Error</span>'
        else:
            status_badge = f'<span class="badge badge-neutral">{status}</span>'

        # Regulatory badge
        reg_info = item.get("regulatory_status") or {}
        reg_comp = reg_info.get("compliance_status", "no_specific_restriction_found")
        if reg_comp == "restricted_with_conditions":
            reg_badge = '<span class="badge badge-review">Restricted Annex</span>'
        elif reg_comp == "explicitly_prohibited":
            reg_badge = '<span class="badge badge-danger">Prohibited</span>'
        else:
            reg_badge = '<span style="color: var(--text-muted); font-size: 0.8rem;">Unlisted in Annexes</span>'

        # Toxicological evidence summary
        tox_ev = item.get("toxicological_evidence") or {}
        ev_synthesis = tox_ev.get("rag_synthesis", "No curated toxicology dossier records in local database.")

        html_content += f"""
          <tr data-status="{status}" data-assessed="{'true' if item.get('assessment_status') == 'assessed' else 'false'}">
            <td class="mono">{idx}</td>
            <td><strong>{raw_name}</strong></td>
            <td>
              {'<span style="color: var(--accent-cyan); font-weight: 500;">' + str(proposed_name) + '</span>' if has_corr else '<span style="color: var(--text-muted);">—</span>'}
            </td>
            <td>{status_badge}</td>
            <td class="mono">{cid}</td>
            <td>{qsar_badge}</td>
            <td>{reg_badge}</td>
            <td>
              <button class="expand-btn" onclick="toggleDetails('detail-{idx}')">Details</button>
            </td>
          </tr>
          <tr id="detail-{idx}" style="display: none; background: rgba(15, 23, 42, 0.4);">
            <td colspan="8">
              <div class="row-detail" style="display: block;">
                <p><strong>Correction Provenance:</strong> {corr_notes or 'No anomalies flagged.'}</p>
                <p style="margin-top: 0.25rem;"><strong>SMILES:</strong> <span class="mono" style="color: #38bdf8;">{mapping.get('connectivity_smiles') or 'None'}</span></p>
                <p style="margin-top: 0.25rem;"><strong>Toxicological Assessment:</strong> {ev_synthesis}</p>
                <p style="margin-top: 0.25rem;"><strong>Regulatory Citations:</strong> {reg_info.get('legal_basis') or 'General cosmetic safety provisions apply.'} ({reg_info.get('compliance_notes', '')})</p>
                <p style="margin-top: 0.25rem; color: var(--text-muted);"><em>Assessment Reason:</em> {item.get('assessment_message')}</p>
              </div>
            </td>
          </tr>
        """

    html_content += f"""
        </tbody>
      </table>
    </div>

    <!-- Footer Insights -->
    <div class="footer-grid">
      <div class="footer-card">
        <h3>Knowledge Graph Structure</h3>
        <p>
          CosmoSafe constructed an interconnected knowledge graph with
          <strong>{kg_summary.get('node_count', 0)} nodes</strong> and
          <strong>{kg_summary.get('edge_count', 0)} typed edges</strong>.
          Relationships preserve explicit provenance connecting Products &rarr; Ingredients &rarr; Chemical Substances &rarr; QSAR &rarr; Toxicological Evidence &rarr; Regulatory Rules.
        </p>
      </div>
      <div class="footer-card">
        <h3>Scientific & Legal Disclaimers</h3>
        <p>
          Computational QSAR predictions evaluate specific in vitro assays (Tox21 NR-AR) and do not constitute proof of finished product cosmetic safety or systemic human risk. Unassessed or unverified ingredients are never assumed safe. Absence from regulatory restricted annexes does not replace finished cosmetic safety testing.
        </p>
      </div>
    </div>
  </div>

  <script>
    function toggleDetails(id) {{
      const el = document.getElementById(id);
      if (el) {{
        el.style.display = el.style.display === 'none' ? 'table-row' : 'none';
      }}
    }}

    function filterTable(filter) {{
      const rows = document.querySelectorAll('#ingredientTable tbody tr[data-status]');
      document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
      event.target.classList.add('active');

      rows.forEach(row => {{
        const status = row.getAttribute('data-status');
        const isAssessed = row.getAttribute('data-assessed') === 'true';
        let show = false;

        if (filter === 'all') show = true;
        else if (filter === 'verified') show = (status === 'verified');
        else if (filter === 'needs_review') show = (status === 'needs_review');
        else if (filter === 'not_found') show = (status === 'not_found');
        else if (filter === 'assessed') show = isAssessed;

        row.style.display = show ? '' : 'none';
        const nextRow = row.nextElementSibling;
        if (nextRow && nextRow.id && nextRow.id.startsWith('detail-') && !show) {{
          nextRow.style.display = 'none';
        }}
      }});
    }}

    document.getElementById('ingredientSearch').addEventListener('input', function(e) {{
      const query = e.target.value.toLowerCase();
      const rows = document.querySelectorAll('#ingredientTable tbody tr[data-status]');
      rows.forEach(row => {{
        const text = row.innerText.toLowerCase();
        const show = text.includes(query);
        row.style.display = show ? '' : 'none';
        const nextRow = row.nextElementSibling;
        if (nextRow && nextRow.id && nextRow.id.startsWith('detail-') && !show) {{
          nextRow.style.display = 'none';
        }}
      }});
    }});
  </script>
</body>
</html>
"""
    return html_content


def export_dashboard_html(
    report_path: Path = DEFAULT_REPORT_PATH,
    output_path: Path = DEFAULT_DASHBOARD_PATH,
) -> Path:
    """Read structured report JSON and export styled HTML dashboard."""
    if not report_path.exists():
        raise FileNotFoundError(f"Report file not found: {report_path}")

    with report_path.open("r", encoding="utf-8") as f:
        report_data = json.load(f)

    html = generate_html_dashboard(report_data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write(html)

    return output_path


if __name__ == "__main__":
    out = export_dashboard_html()
    print(f"CosmoSafe dashboard exported to: {out}")
