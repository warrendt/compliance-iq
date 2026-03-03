#!/usr/bin/env python3
"""
ComplianceIQ Compliance Pipeline — PDF/CSV to Defender for Cloud Initiative

End-to-end automation:
  PDF input:  1. Extract text from a compliance PDF
              2. Use Azure OpenAI to extract structured controls
              3. Map each control to Azure Policy definitions via LLM
              4. Validate all mappings
              5. Generate deployable initiative artifacts (JSON + PowerShell)

  CSV input:  Skips stages 1-2. Reads pre-structured controls directly from a CSV
              file, then maps to Azure Policies (stages 3-5).

Usage:
  python pipeline.py <path-to-pdf>
  python pipeline.py <path-to-csv>
  python pipeline.py <path-to-csv> --framework-name "My Framework"
  python pipeline.py <path-to-pdf> --output ./my-output --min-confidence 0.6
  python pipeline.py <path-to-pdf> --locations uaenorth,uaecentral

CSV Column Names (flexible, case-insensitive):
  Control ID:   Control_ID, ControlID, ID, No
  Domain:       Domain, Category, Section, Group
  Title:        Control_Title, Title, Requirement, Name
  Description:  Control_Description, Description, Requirement_Summary, Details
  Type:         Control_Type, ControlType, Type

Environment:
  AZURE_OPENAI_ENDPOINT         (required) Azure OpenAI endpoint URL
  AZURE_OPENAI_DEPLOYMENT_NAME  (optional) Model deployment name (default: gpt-4.1)
  AZURE_OPENAI_API_KEY          (optional) API key — if omitted, uses DefaultAzureCredential
  AZURE_OPENAI_API_VERSION      (optional) API version (default: 2024-12-01-preview)
"""

import argparse
import csv
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Add this directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from config import PipelineConfig
from pdf_extractor import extract_text_from_pdf, get_pdf_metadata
from control_extractor import extract_controls_from_text
from policy_mapper import map_controls_to_azure_policies
from validator import validate_mappings
from initiative_builder import build_initiative_artifacts
from models import PipelineResult, ControlExtractionResult, ExtractedControl


def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)-7s] %(name)s — %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")
    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("azure").setLevel(logging.WARNING)


def print_banner():
    """Print the pipeline banner."""
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   ComplianceIQ Compliance Pipeline                            ║")
    print("║   PDF → Controls → Azure Policy → Defender for Cloud       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


def print_stage(num: int, title: str):
    """Print a stage header."""
    print(f"\n{'─' * 60}")
    print(f"  Stage {num}: {title}")
    print(f"{'─' * 60}\n")


def parse_csv_to_extraction(
    csv_path: str,
    framework_name: str | None = None,
) -> ControlExtractionResult:
    """
    Parse a compliance framework CSV into a ControlExtractionResult.

    Supports flexible column names — detects the following variants:
      - Control ID:    Control_ID, ControlID, ID, control_id, id
      - Domain:        Domain, Category, Section, domain, category
      - Title:         Control_Title, ControlTitle, Title, Requirement, Name
      - Description:   Control_Description, Description, Requirement_Summary,
                       Requirements, Requirement_Text, Details, Text
      - Control Type:  Control_Type, ControlType, Type

    The CSV may optionally include a header row with these column names.
    Any columns not recognised are ignored.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    fw_name = framework_name or path.stem.replace("_", " ").replace("-", " ")

    # Column name aliases (lower-cased for matching)
    ID_COLS     = {"control_id", "controlid", "id", "ctrl_id", "ctrl id", "no", "number"}
    DOMAIN_COLS = {"domain", "category", "section", "group", "pillar"}
    TITLE_COLS  = {"control_title", "controltitle", "title", "requirement", "name",
                   "control_name", "controlname", "control name", "requirement_name"}
    DESC_COLS   = {"control_description", "description", "requirement_summary",
                   "requirements", "requirement_text", "details", "text",
                   "summary", "description_text", "objective", "intent"}
    TYPE_COLS   = {"control_type", "controltype", "type"}

    def _find_col(headers: list[str], candidates: set[str]) -> int | None:
        for i, h in enumerate(headers):
            if h.lower().strip() in candidates:
                return i
        return None

    controls: list[ExtractedControl] = []

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        raw_rows = list(reader)

    if not raw_rows:
        raise ValueError(f"CSV file is empty: {csv_path}")

    # Detect header row
    first_row = [c.strip() for c in raw_rows[0]]
    id_col     = _find_col(first_row, ID_COLS)
    domain_col = _find_col(first_row, DOMAIN_COLS)
    title_col  = _find_col(first_row, TITLE_COLS)
    desc_col   = _find_col(first_row, DESC_COLS)
    type_col   = _find_col(first_row, TYPE_COLS)

    # If no header matched, assume positional: col0=ID, col1=Domain, col2=Title, col3=Desc
    has_header = any(v is not None for v in [id_col, domain_col, title_col, desc_col])
    data_rows = raw_rows[1:] if has_header else raw_rows
    if not has_header:
        id_col, domain_col, title_col, desc_col = 0, 1, 2, 3

    seen_ids: set[str] = set()
    for row_num, row in enumerate(data_rows, start=2 if has_header else 1):
        if not row or all(c.strip() == "" for c in row):
            continue  # Skip blank rows

        def _get(col: int | None, fallback: str = "") -> str:
            if col is None or col >= len(row):
                return fallback
            return row[col].strip()

        control_id    = _get(id_col)   or f"CTRL-{row_num:03d}"
        domain        = _get(domain_col) or "Governance & Policy"
        title         = _get(title_col) or control_id
        description   = _get(desc_col) or title
        control_type  = _get(type_col) or "Technical"

        # Deduplicate
        if control_id in seen_ids:
            control_id = f"{control_id}_{row_num}"
        seen_ids.add(control_id)

        controls.append(ExtractedControl(
            control_id=control_id,
            control_title=title,
            control_description=description,
            domain=domain,
            control_type=control_type,
            sub_controls=[],
        ))

    if not controls:
        raise ValueError(f"No controls found in CSV: {csv_path}")

    return ControlExtractionResult(
        framework_name=fw_name,
        framework_version=None,
        issuing_authority=None,
        country_or_region=None,
        controls=controls,
        summary=f"{fw_name} compliance framework with {len(controls)} controls (imported from CSV).",
    )


def run_pipeline(
    pdf_path: str | None = None,
    csv_path: str | None = None,
    framework_name: str | None = None,
    output_dir: str = "./output",
    min_confidence: float = 0.5,
    allowed_locations: list[str] | None = None,
    env_file: str | None = None,
    verbose: bool = False,
) -> PipelineResult:
    """
    Execute the full pipeline from either a PDF or a CSV file.

    For PDF inputs: runs all 5 stages (extract text → LLM controls → map → validate → artifacts).
    For CSV inputs: skips stages 1-2 and goes directly to Azure Policy mapping.

    Args:
        pdf_path: Path to the compliance PDF (mutually exclusive with csv_path).
        csv_path: Path to a CSV with pre-structured controls (mutually exclusive with pdf_path).
        framework_name: Override the framework name (useful for CSV inputs).
        output_dir: Directory for output artifacts.
        min_confidence: Minimum confidence threshold.
        allowed_locations: Optional Azure regions for location policies.
        env_file: Optional path to .env file.
        verbose: Enable debug logging.

    Returns:
        PipelineResult with summary and file paths.
    """
    if not pdf_path and not csv_path:
        raise ValueError("Either pdf_path or csv_path must be provided")
    if pdf_path and csv_path:
        raise ValueError("Provide either pdf_path or csv_path, not both")
    logger = logging.getLogger("pipeline")
    started_at = datetime.utcnow()
    t0 = time.time()

    # ── Load config ───────────────────────────────────────────────────────
    config = PipelineConfig.from_env(env_file)
    config.output_dir = output_dir
    config.min_confidence_threshold = min_confidence

    errors = config.validate()
    if errors:
        for err in errors:
            logger.error(f"Config error: {err}")
        print("\n❌ Configuration errors — set required environment variables.")
        print("   Required: AZURE_OPENAI_ENDPOINT")
        print("   Optional: AZURE_OPENAI_API_KEY (or use az login for DefaultAzureCredential)")
        sys.exit(1)

    # ══════════════════════════════════════════════════════════════════════
    # STAGE 1 & 2: Input Processing (PDF extraction + LLM, or CSV parse)
    # ══════════════════════════════════════════════════════════════════════
    if csv_path:
        print_stage(1, "CSV Control Import (skipping PDF extraction + LLM)")
        extraction = parse_csv_to_extraction(csv_path, framework_name=framework_name)
        print(f"  ✓ Framework:  {extraction.framework_name}")
        print(f"  ✓ Controls:   {len(extraction.controls)} imported from CSV")
        print(f"  ✓ Source:     {csv_path}")
    else:
        # ── STAGE 1: PDF Text Extraction ──────────────────────────────────
        print_stage(1, "PDF Text Extraction")

        pdf_metadata = get_pdf_metadata(pdf_path)
        logger.info(f"PDF: {Path(pdf_path).name} ({pdf_metadata['pages']} pages, {pdf_metadata['file_size_bytes']:,} bytes)")
        if pdf_metadata.get("title"):
            logger.info(f"Title: {pdf_metadata['title']}")

        pdf_text = extract_text_from_pdf(pdf_path, max_pages=config.max_pdf_pages)
        print(f"  ✓ Extracted {len(pdf_text):,} characters from {pdf_metadata['pages']} pages")

        # ── STAGE 2: LLM Control Extraction ──────────────────────────────
        print_stage(2, "AI Control Extraction (Azure OpenAI)")

        print(f"  Sending to {config.azure_openai_deployment}...")
        extraction = extract_controls_from_text(pdf_text, config, pdf_metadata)

        # Override framework name if provided
        if framework_name:
            extraction.framework_name = framework_name

    if csv_path:
        # If coming from CSV, print domain breakdown here (stage 2 equivalent)
        print_stage(2, "Controls Overview")
        print(f"  ✓ Framework:  {extraction.framework_name}")

    if not csv_path:
        print(f"  ✓ Framework:  {extraction.framework_name}")
        if extraction.framework_version:
            print(f"  ✓ Version:    {extraction.framework_version}")
        if extraction.issuing_authority:
            print(f"  ✓ Authority:  {extraction.issuing_authority}")
        if extraction.country_or_region:
            print(f"  ✓ Region:     {extraction.country_or_region}")
        print(f"  ✓ Controls:   {len(extraction.controls)} extracted")

    # Show domain breakdown
    domains: dict[str, int] = {}
    for ctrl in extraction.controls:
        domains[ctrl.domain] = domains.get(ctrl.domain, 0) + 1
    print(f"\n  Domain Breakdown:")
    for domain, count in sorted(domains.items(), key=lambda x: -x[1]):
        print(f"    {domain}: {count}")

    # ══════════════════════════════════════════════════════════════════════
    # STAGE 3: Azure Policy Mapping
    # ══════════════════════════════════════════════════════════════════════
    print_stage(3, "Azure Policy Mapping (Azure OpenAI)")

    def progress(current, total):
        pct = (current / total) * 100
        print(f"  Mapping controls: {current}/{total} ({pct:.0f}%)", end="\r")

    mappings = map_controls_to_azure_policies(extraction, config, progress_callback=progress)
    print()  # Clear the progress line

    automatable = sum(1 for m in mappings if m.is_automatable)
    manual = len(mappings) - automatable
    total_policies = sum(len(m.azure_policies) for m in mappings)
    unique_policies = len({p.policy_definition_id for m in mappings for p in m.azure_policies})
    avg_conf = sum(m.confidence_score for m in mappings) / len(mappings) if mappings else 0

    print(f"  ✓ Mapped:     {len(mappings)} controls")
    print(f"  ✓ Automatable: {automatable} (via Azure Policy)")
    print(f"  ✓ Manual:      {manual} (require attestation)")
    print(f"  ✓ Policies:    {unique_policies} unique Azure Policy definitions")
    print(f"  ✓ Confidence:  {avg_conf:.2f} average")

    # ══════════════════════════════════════════════════════════════════════
    # STAGE 4: Validation
    # ══════════════════════════════════════════════════════════════════════
    print_stage(4, "Mapping Validation")

    validation = validate_mappings(extraction, mappings, min_confidence)

    errors_count = sum(1 for i in validation.issues if i.severity == "error")
    warnings_count = sum(1 for i in validation.issues if i.severity == "warning")
    infos_count = sum(1 for i in validation.issues if i.severity == "info")

    status = "✓ PASSED" if validation.is_valid else "✗ FAILED"
    color = "Green" if validation.is_valid else "Red"

    print(f"  {status}")
    print(f"  Errors:   {errors_count}")
    print(f"  Warnings: {warnings_count}")
    print(f"  Info:     {infos_count}")

    if errors_count > 0:
        print(f"\n  Errors:")
        for issue in validation.issues:
            if issue.severity == "error":
                print(f"    ❌ [{issue.control_id}] {issue.message}")
                if issue.suggestion:
                    print(f"       → {issue.suggestion}")

    if warnings_count > 0 and verbose:
        print(f"\n  Warnings:")
        for issue in validation.issues:
            if issue.severity == "warning":
                print(f"    ⚠️  [{issue.control_id}] {issue.message}")

    # ══════════════════════════════════════════════════════════════════════
    # STAGE 5: Generate Initiative Artifacts
    # ══════════════════════════════════════════════════════════════════════
    print_stage(5, "Generate Defender for Cloud Initiative")

    files = build_initiative_artifacts(
        extraction=extraction,
        mappings=mappings,
        validation=validation,
        output_dir=output_dir,
        allowed_locations=allowed_locations,
    )

    print(f"  Output directory: {output_dir}/")
    print(f"  Files generated:")
    for f in files:
        fname = Path(f).name
        size = Path(f).stat().st_size
        print(f"    📄 {fname} ({size:,} bytes)")

    # ══════════════════════════════════════════════════════════════════════
    # Summary
    # ══════════════════════════════════════════════════════════════════════
    elapsed = time.time() - t0
    completed_at = datetime.utcnow()

    print(f"\n{'═' * 60}")
    print(f"  Pipeline Complete — {elapsed:.1f}s")
    print(f"{'═' * 60}")
    print(f"  Framework:      {extraction.framework_name}")
    print(f"  Controls:       {len(extraction.controls)}")
    print(f"  Automatable:    {automatable}")
    print(f"  Manual:         {manual}")
    print(f"  Unique Policies: {unique_policies}")
    print(f"  Avg Confidence: {avg_conf:.2f}")
    print(f"  Validation:     {'PASSED' if validation.is_valid else 'FAILED'}")
    print()
    print(f"  Deploy to Azure:")
    print(f"    PowerShell:  cd {output_dir} && .\\Deploy-Initiative.ps1")
    print(f"    Azure CLI:   cd {output_dir} && bash deploy-initiative.sh")
    print()

    return PipelineResult(
        framework_name=extraction.framework_name,
        framework_version=extraction.framework_version,
        issuing_authority=extraction.issuing_authority,
        country_or_region=extraction.country_or_region,
        total_controls_extracted=len(extraction.controls),
        total_policies_mapped=unique_policies,
        automatable_controls=automatable,
        manual_controls=manual,
        avg_confidence=avg_conf,
        validation=validation,
        output_directory=output_dir,
        files_generated=files,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=elapsed,
    )


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ComplianceIQ Compliance Pipeline — PDF/CSV to Defender for Cloud Initiative",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # From PDF (full AI extraction)
  python pipeline.py ./my-framework.pdf

  # From CSV (skips PDF extraction; goes straight to policy mapping)
  python pipeline.py ./my-framework.csv

  # From CSV with explicit framework name
  python pipeline.py ./my-framework.csv --framework-name "SAMA Cybersecurity Framework"

  # Custom output directory
  python pipeline.py ./my-framework.pdf --output ./my-framework-output

  # With Azure region restrictions
  python pipeline.py ./my-framework.pdf --locations uaenorth,uaecentral

  # Higher confidence threshold (exclude weak mappings)
  python pipeline.py ./my-framework.pdf --min-confidence 0.7

  # Verbose logging for debugging
  python pipeline.py ./my-framework.pdf --verbose

CSV Column Names (flexible, case‑insensitive):
  Control ID:    Control_ID, ControlID, ID, No
  Domain:        Domain, Category, Section, Group
  Title:         Control_Title, Title, Requirement, Name
  Description:   Control_Description, Description, Requirement_Summary, Details
  Type:          Control_Type, ControlType, Type

Environment Variables:
  AZURE_OPENAI_ENDPOINT          Azure OpenAI endpoint (required)
  AZURE_OPENAI_DEPLOYMENT_NAME   Model deployment name (default: gpt-4.1)
  AZURE_OPENAI_API_KEY           API key (optional — uses DefaultAzureCredential if omitted)
  AZURE_OPENAI_API_VERSION       API version (default: 2024-12-01-preview)
""",
    )

    parser.add_argument(
        "input",
        help="Path to the compliance document — PDF or CSV",
    )
    parser.add_argument(
        "--framework-name", "-n",
        default=None,
        help="Override the framework name (useful when importing a CSV without a clear name)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory for generated files (default: ./output/<input-stem>)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.5,
        help="Minimum confidence threshold for including mappings (default: 0.5)",
    )
    parser.add_argument(
        "--locations",
        default=None,
        help="Comma-separated Azure region names for location policies (e.g., uaenorth,uaecentral)",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Path to .env file with Azure OpenAI credentials",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Also write pipeline result summary as JSON",
    )

    args = parser.parse_args()

    setup_logging(args.verbose)
    print_banner()

    # Auto-detect input type from extension
    input_path = Path(args.input)
    is_csv = input_path.suffix.lower() == ".csv"

    if not input_path.exists():
        print(f"❌ File not found: {args.input}")
        sys.exit(1)

    # Parse locations
    locations = None
    if args.locations:
        locations = [loc.strip() for loc in args.locations.split(",") if loc.strip()]

    # Determine output directory
    output_dir = args.output
    if not output_dir:
        output_dir = f"./output/{input_path.stem}"

    # Run the pipeline
    result = run_pipeline(
        pdf_path=None if is_csv else args.input,
        csv_path=args.input if is_csv else None,
        framework_name=args.framework_name,
        output_dir=output_dir,
        min_confidence=args.min_confidence,
        allowed_locations=locations,
        env_file=args.env_file,
        verbose=args.verbose,
    )

    # Optionally write result summary
    if args.json_output:
        result_path = Path(output_dir) / "pipeline_result.json"
        with open(result_path, "w") as f:
            json.dump(result.model_dump(), f, indent=2, default=str)
        print(f"  Pipeline result: {result_path}")

    # Exit code based on validation
    sys.exit(0 if result.validation.is_valid else 1)


if __name__ == "__main__":
    main()
