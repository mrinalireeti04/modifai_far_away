"""
Entry point for running the Modifai pipeline.
"""
import argparse
from modifai.config.settings import PipelineConfig
from modifai.pipeline import run_pipeline

def main():
    parser = argparse.ArgumentParser(description="Run the Modifai Data Generation Pipeline.")
    parser.add_argument("input_pdf", help="Path to the input PDF document.")
    parser.add_argument("--output-dir", default=".", help="Directory to save output files.")
    parser.add_argument("--mode", default="QA", choices=["QA", "instruction", "tutor"], help="Generation mode.")
    parser.add_argument("--samples-per-chunk", type=int, default=3, help="Samples to generate per chunk.")
    parser.add_argument("--validation-mode", default="fast", choices=["fast", "validated"], help="Validation mode.")
    parser.add_argument("--qc-threshold", type=float, default=0.6, help="Quality control threshold.")
    
    args = parser.parse_args()
    
    config = PipelineConfig(
        mode=args.mode,
        samples_per_chunk=args.samples_per_chunk,
        validation_mode=args.validation_mode,
        qc_threshold=args.qc_threshold
    )
    
    run_pipeline(args.input_pdf, config, output_dir=args.output_dir)

if __name__ == "__main__":
    main()
