from __future__ import annotations

import argparse

from sim.common import ensure_directories
from sim.workflows.common import build_runtime_payload, copy_workflow_config, load_workflow_config, run_module, write_runtime_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch training data using the simplified workflow config.")
    parser.add_argument("--config", default=None, help="Optional path to the simplified workflow TOML.")
    args = parser.parse_args()

    workflow = load_workflow_config(args.config)
    ensure_directories(workflow.paths.training_data, workflow.paths.processed, workflow.paths.model_runs_root, workflow.paths.inference_runs_root)

    runtime_config = workflow.paths.training_data / "fetch_runtime_config.toml"
    payload = build_runtime_payload(
        workflow,
        model_registry=workflow.paths.model_runs_root / "_shared_artifacts",
        output_dir=workflow.paths.inference_runs_root,
    )
    write_runtime_config(payload, runtime_config)
    copy_workflow_config(workflow.path, workflow.paths.training_data / "workflow_config.toml")
    run_module("sim.data_in.download_training_data", runtime_config)
    print(f"Fetched training data into {workflow.paths.training_data}")


if __name__ == "__main__":
    main()