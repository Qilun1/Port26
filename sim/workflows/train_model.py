from __future__ import annotations

import argparse

from sim.common import ensure_directories
from sim.workflows.common import (
    build_runtime_payload,
    copy_workflow_config,
    load_workflow_config,
    run_module,
    write_run_summary,
    write_runtime_config,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess, train, and summarize a model run using the simplified workflow config.")
    parser.add_argument("--config", default=None, help="Optional path to the simplified workflow TOML.")
    parser.add_argument("--run-name", default=None, help="Optional run name override.")
    parser.add_argument("--fetch-first", action="store_true", help="Fetch data before preprocessing and training.")
    args = parser.parse_args()

    workflow = load_workflow_config(args.config)
    run_name = args.run_name or workflow.train.run_name
    fetch_first = args.fetch_first or workflow.train.fetch_first
    run_dir = workflow.paths.model_runs_root / run_name
    ensure_directories(run_dir, workflow.paths.training_data, workflow.paths.processed)

    runtime_config = run_dir / "resolved_config.toml"
    payload = build_runtime_payload(
        workflow,
        model_registry=run_dir,
        output_dir=workflow.paths.inference_runs_root,
    )
    write_runtime_config(payload, runtime_config)
    copy_workflow_config(workflow.path, run_dir / "workflow_config.toml")

    if fetch_first:
        run_module("sim.data_in.download_training_data", runtime_config)
    run_module("sim.preprocess.build_dataset", runtime_config)
    run_module("sim.models.train_xgboost", runtime_config)
    run_module("sim.visualize_validation", runtime_config)
    summary_path = write_run_summary(run_dir)

    print(f"Training run saved to {run_dir}")
    print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()