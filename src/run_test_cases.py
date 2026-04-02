#!/usr/bin/env python3
import sys
import os
import json
import yaml
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add src to Python Path so that stage1 and stage2 modules are recognizable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stage1.oracle_reasoner import run as run_stage1
from stage2.harness_generator import run as run_stage2


def setup_global_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(console_handler)

    # Optionally add a master run log
    file_handler = logging.FileHandler("test_output/master_tests.log", delay=True)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(file_handler)

    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)


def process_test_cases(tests_path: str):
    tests_file = Path(tests_path)
    if not tests_file.exists():
        logging.error(f"Cannot find {tests_file}")
        return

    data = json.loads(tests_file.read_text(encoding="utf-8"))
    findings = data.get("findings", [])

    if not findings:
        logging.info("No findings listed in the file.")
        return

    logging.info(f"Loaded {len(findings)} test cases from {tests_path}.")

    base_s1_config = yaml.safe_load(Path("src/config/stage1_config.yaml").read_text())
    base_s2_config = yaml.safe_load(Path("src/config/stage2_config.yaml").read_text())

    for idx, tc in enumerate(findings):
        tc_id = tc.get("id", f"TC-UNKNOWN-{idx}")
        finding_data = tc.get("finding", {})
        rule_id = finding_data.get("rule_id", "unknown").replace("/", "_")

        logging.info("=" * 60)
        logging.info(f"PROCESSING TEST CASE: {tc_id}")
        logging.info("=" * 60)

        # 1. Create output sandbox
        out_dir = Path(f"test_output/{tc_id}")
        out_dir.mkdir(parents=True, exist_ok=True)

        # 2. Extract standard finding structure
        isolated_finding = {"finding": finding_data}
        finding_path = out_dir / "finding.json"
        finding_path.write_text(json.dumps(isolated_finding, indent=2, ensure_ascii=False), encoding="utf-8")

        # 3. Prepare Stage 1 Run
        s1_config = base_s1_config.copy()
        s1_config["signatures_csv"] = "test_case/signatures_function.csv"
        s1_config["functions_csv"] = "test_case/functions.csv"
        s1_config["oracle_spec_out"] = f"test_output/{tc_id}/oracle_spec.json"

        s1_config_path = out_dir / "stage1_config.yaml"
        s1_config_path.write_text(yaml.dump(s1_config), encoding="utf-8")

        spec_path = out_dir / "oracle_spec.json"

        try:
            # Execute Stage 1
            logging.info(f"[{tc_id}] Running Stage 1...")
            run_stage1(finding_path=str(finding_path), config_path=str(s1_config_path))
            logging.info(f"[{tc_id}] Stage 1 Finished successfully.")
        except Exception as e:
            logging.error(f"[{tc_id}] Stage 1 failed due to: {e}")
            continue

        if not spec_path.exists():
            logging.error(f"[{tc_id}] oracle_spec.json was not generated. Skipping Stage 2.")
            continue

        # 4. Prepare Stage 2 Run
        s2_config = base_s2_config.copy()
        s2_config["repo_root"] = "test_case/"
        s2_config["harness_out"] = f"test_output/{tc_id}/harness_{rule_id}.py"

        s2_config_path = out_dir / "stage2_config.yaml"
        s2_config_path.write_text(yaml.dump(s2_config), encoding="utf-8")

        try:
            # Execute Stage 2
            logging.info(f"[{tc_id}] Running Stage 2...")
            run_stage2(finding_path=str(finding_path), spec_path=str(spec_path), config_path=str(s2_config_path))
            logging.info(f"[{tc_id}] Stage 2 Finished successfully.")
        except Exception as e:
            logging.error(f"[{tc_id}] Stage 2 failed due to: {e}")
            continue

    logging.info("=" * 60)
    logging.info("ALL TEST CASES COMPLETED.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FuzzGen Test Case Batch Runner")
    parser.add_argument("--test-file", default="test_case/findings.json", help="Path to JSON file containing array of test case findings")
    args = parser.parse_args()

    # Create master log folder parent
    Path("test_output").mkdir(parents=True, exist_ok=True)
    setup_global_logging()

    process_test_cases(args.test_file)
