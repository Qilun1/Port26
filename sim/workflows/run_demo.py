from __future__ import annotations

import argparse

from sim.workflows.common import load_workflow_config, run_module


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the config-defined demo flow: train the model, write validation metrics, and execute the example inference request."
    )
    parser.add_argument("--config", default=None, help="Optional path to the simplified workflow TOML.")
    args = parser.parse_args()

    workflow = load_workflow_config(args.config)
    run_module("sim.workflows.train_model", workflow.path)
    run_module("sim.workflows.run_inference_request", workflow.path)

    run_dir = workflow.paths.model_runs_root / workflow.train.run_name
    request_dir = workflow.paths.inference_runs_root / workflow.request.request_name
    print(f"Demo training run saved to {run_dir}")
    print(f"Demo inference request saved to {request_dir}")


if __name__ == "__main__":
    main()
