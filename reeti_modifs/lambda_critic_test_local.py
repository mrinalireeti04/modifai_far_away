"""
Local test for the Critic Lambda handler.

Mocks boto3 entirely — no AWS credentials, no Bedrock spend, no S3 needed.
Tests the full Lambda handler() function end-to-end with patched S3 + Bedrock.

Run from this directory:
    python test_local.py

Or with pytest from the repo root:
    pytest lambdas/critic/test_local.py -v
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

# ── shared fixtures ────────────────────────────────────────────────────────────

CHUNK = {
    "chunk_id": 1,
    "text": (
        "The onboarding process for new employees involves three steps: "
        "completing the HR forms, attending the two-day orientation session, "
        "and receiving badge access from the security desk on Day 3."
    ),
}

GOOD_EXAMPLE = {
    "example_id": 1,
    "chunk_id": 1,
    "instruction": "What are the three steps in the employee onboarding process?",
    "input": "",
    "response": (
        "The three steps are: completing HR forms, attending the two-day "
        "orientation session, and receiving badge access from security on Day 3."
    ),
    "source_file": "onboarding.pdf",
}

HALLUCINATED_EXAMPLE = {
    "example_id": 2,
    "chunk_id": 1,
    "instruction": "Describe onboarding.",
    "input": "",
    "response": (
        "Employees are paired with a buddy for the first week and then "
        "complete online modules before meeting their manager."
    ),
    "source_file": "onboarding.pdf",
}

VAGUE_EXAMPLE = {
    "example_id": 3,
    "chunk_id": 1,
    "instruction": "What does onboarding involve?",
    "input": "",
    "response": "Please refer to the official documentation.",
    "source_file": "onboarding.pdf",
}

# Duplicate of GOOD_EXAMPLE
DUPLICATE_EXAMPLE = {
    "example_id": 4,
    "chunk_id": 1,
    "instruction": "What are the three steps in the employee onboarding process?",
    "input": "",
    "response": (
        "The three steps are: completing HR forms, attending the two-day "
        "orientation session, and receiving badge access from security on Day 3."
    ),
    "source_file": "onboarding.pdf",
}

ACCEPT_VERDICT = {
    "verdict": "accept",
    "reason": "Specific, grounded, complete.",
    "rewritten_output": None,
    "scores": {"specificity": 0.9, "grounding": 1.0, "format": 1.0},
}

REJECT_VERDICT = {
    "verdict": "reject",
    "reason": "Fabricates buddy system not in chunk.",
    "rewritten_output": None,
    "scores": {"specificity": 0.2, "grounding": 0.1, "format": 0.6},
}

BASE_EVENT = {
    "project_id": "test-project-001",
    "s3_prefix": "test-user/test-project/",
    "mode": "dataset_only",
    "config": {
        "quality_threshold": 0.7,
        "bedrock_model_id": "amazon.nova-micro-v1:0",
    },
    "step_results": {
        "chunking": {
            "chunks_key": "temp_processing/chunks.json",
            "chunk_count": 1,
        },
        "generation": {
            "examples_key": "temp_processing/examples.json",
            "example_count": 4,
        },
    },
}


def _make_s3_body(obj):
    """Return a mock S3 get_object() Body that .read() returns JSON bytes."""
    mock_body = MagicMock()
    mock_body.read.return_value = json.dumps(obj).encode("utf-8")
    return {"Body": mock_body}


def _make_bedrock_response(verdict_dict):
    return {
        "output": {
            "message": {"content": [{"text": json.dumps(verdict_dict)}]}
        }
    }


# ── tests ──────────────────────────────────────────────────────────────────────

class TestCriticLambdaHandler(unittest.TestCase):

    @patch("handler.boto3.client")
    def test_happy_path_accept_and_reject(self, mock_boto):
        """
        Dataset: 1 good + 1 hallucinated + 1 vague + 1 duplicate of good.
        Expected after dedup (removes duplicate): 3 unique samples sent to Critic.
        Critic returns: accept, reject, reject.
        Survivors = 1 (the accepted example).
        """
        s3_mock = MagicMock()
        bedrock_mock = MagicMock()

        def client_factory(service, **kwargs):
            if service == "s3":
                return s3_mock
            return bedrock_mock

        mock_boto.side_effect = client_factory

        # S3 reads: first call = examples, second call = chunks
        examples = [GOOD_EXAMPLE, HALLUCINATED_EXAMPLE, VAGUE_EXAMPLE, DUPLICATE_EXAMPLE]
        s3_mock.get_object.side_effect = [
            _make_s3_body(examples),
            _make_s3_body([CHUNK]),
        ]

        # Bedrock: 3 calls (after dedup) → accept, reject, reject
        bedrock_mock.converse.side_effect = [
            _make_bedrock_response(ACCEPT_VERDICT),
            _make_bedrock_response(REJECT_VERDICT),
            _make_bedrock_response(REJECT_VERDICT),
        ]

        from handler import handler
        result = handler(dict(BASE_EVENT), None)

        qc = result["step_results"]["quality_control"]
        print(f"\n✅ QC Result: {json.dumps(qc, indent=2)}")

        self.assertEqual(qc["total_input"], 4)
        self.assertEqual(qc["duplicates_removed"], 1)
        self.assertEqual(qc["kept"], 1)
        self.assertEqual(qc["discarded"], 2)
        self.assertIn("critic_stats", qc)
        self.assertEqual(qc["critic_stats"]["accepted"], 1)
        self.assertEqual(qc["critic_stats"]["rejected"], 2)
        self.assertEqual(qc["critic_stats"]["accept_pct"], 33.3)

        # S3 write happened exactly once (the clean dataset)
        s3_mock.put_object.assert_called_once()
        call_kwargs = s3_mock.put_object.call_args[1]
        self.assertIn("clean_dataset.jsonl", call_kwargs["Key"])

    @patch("handler.boto3.client")
    def test_rewrite_verdict_replaces_response(self, mock_boto):
        """When Critic rewrites, survivors must use the corrected response."""
        s3_mock = MagicMock()
        bedrock_mock = MagicMock()

        def client_factory(service, **kwargs):
            return s3_mock if service == "s3" else bedrock_mock

        mock_boto.side_effect = client_factory

        s3_mock.get_object.side_effect = [
            _make_s3_body([VAGUE_EXAMPLE]),
            _make_s3_body([CHUNK]),
        ]

        corrected = (
            "The three steps are completing HR forms, attending orientation, "
            "and receiving badge access on Day 3."
        )
        rewrite_verdict = {
            "verdict": "rewrite",
            "reason": "Too vague — missing specific steps.",
            "rewritten_output": corrected,
            "scores": {"specificity": 0.4, "grounding": 0.8, "format": 0.5},
        }
        bedrock_mock.converse.return_value = _make_bedrock_response(rewrite_verdict)

        from handler import handler
        result = handler(dict(BASE_EVENT), None)

        qc = result["step_results"]["quality_control"]
        self.assertEqual(qc["kept"], 1)
        self.assertEqual(qc["critic_stats"]["rewritten"], 1)

        # Verify the written JSONL contains the corrected response
        written_body = s3_mock.put_object.call_args[1]["Body"]
        written_sample = json.loads(written_body.strip().split("\n")[0])
        self.assertEqual(written_sample["response"], corrected)
        self.assertTrue(written_sample.get("_critic_rewritten"))

    @patch("handler.boto3.client")
    def test_empty_examples_handled_gracefully(self, mock_boto):
        """Empty dataset: zero Bedrock calls, stats all zero, no crash."""
        s3_mock = MagicMock()
        bedrock_mock = MagicMock()

        def client_factory(service, **kwargs):
            return s3_mock if service == "s3" else bedrock_mock

        mock_boto.side_effect = client_factory

        s3_mock.get_object.side_effect = [
            _make_s3_body([]),
            _make_s3_body([CHUNK]),
        ]

        from handler import handler
        result = handler(dict(BASE_EVENT), None)

        qc = result["step_results"]["quality_control"]
        self.assertEqual(qc["total_input"], 0)
        self.assertEqual(qc["kept"], 0)
        self.assertEqual(qc["critic_stats"]["survivor_count"], 0)
        bedrock_mock.converse.assert_not_called()

    @patch("handler.boto3.client")
    def test_output_schema_is_backward_compatible(self, mock_boto):
        """
        The output schema must be identical to what the old QC Lambda returned.
        Keys checked: clean_dataset_key, total_input, duplicates_removed, kept,
                      discarded, threshold.
        The extra 'critic_stats' key is additive — does not break anything.
        """
        s3_mock = MagicMock()
        bedrock_mock = MagicMock()

        def client_factory(service, **kwargs):
            return s3_mock if service == "s3" else bedrock_mock

        mock_boto.side_effect = client_factory

        s3_mock.get_object.side_effect = [
            _make_s3_body([GOOD_EXAMPLE]),
            _make_s3_body([CHUNK]),
        ]
        bedrock_mock.converse.return_value = _make_bedrock_response(ACCEPT_VERDICT)

        from handler import handler
        result = handler(dict(BASE_EVENT), None)

        qc = result["step_results"]["quality_control"]
        required_keys = {
            "clean_dataset_key",
            "total_input",
            "duplicates_removed",
            "kept",
            "discarded",
            "threshold",
        }
        for key in required_keys:
            self.assertIn(key, qc, f"Missing required key: {key}")

        self.assertEqual(qc["clean_dataset_key"], "temp_processing/clean_dataset.jsonl")


# ── standalone runner ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Critic Lambda — Local Tests (mocked, no AWS calls)")
    print("=" * 60)
    unittest.main(verbosity=2)
