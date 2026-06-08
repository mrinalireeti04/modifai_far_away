"""
Unit tests for the Critic agent.
All AWS calls are mocked — no credentials or Bedrock spend required.

Test coverage:
  - Single sample: accept, rewrite, reject verdicts
  - Malformed JSON from LLM → retry → final REJECT fallback
  - Batch mode: stats calculation, survivors list
  - 5 deliberately bad samples: all must be rejected or rewritten (never accepted)
  - Edge case: sample with no matching chunk_id
  - Edge case: empty dataset (all accepted on first pass → empty batch handled)
"""

import json
import pytest
from unittest.mock import MagicMock, patch

try:
    from reeti_modifs.critic_agent import (
        critique_sample,
        run_critic_batch,
        _parse_critic_response,
        CRITIC_SYSTEM_PROMPT,
    )
    CRITIC_PATH = "reeti_modifs.critic_agent"
except ImportError:
    from modifai.core.critic_agent import (
        critique_sample,
        run_critic_batch,
        _parse_critic_response,
        CRITIC_SYSTEM_PROMPT,
    )
    CRITIC_PATH = "modifai.core.critic_agent"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_bedrock_response(verdict_dict: dict) -> dict:
    """Wraps a verdict dict in a fake Bedrock converse() response shape."""
    return {
        "output": {
            "message": {
                "content": [{"text": json.dumps(verdict_dict)}]
            }
        }
    }


GOOD_CHUNK = (
    "The onboarding process for new employees involves three steps: "
    "completing the HR forms, attending the two-day orientation session, "
    "and receiving badge access from the security desk on Day 3."
)

GOOD_SAMPLE = {
    "chunk_id": 1,
    "instruction": "What are the three steps in the employee onboarding process?",
    "input": "",
    "response": (
        "The three steps are: completing HR forms, attending the two-day "
        "orientation session, and receiving badge access from security on Day 3."
    ),
}

ACCEPT_VERDICT = {
    "verdict": "accept",
    "reason": "Response is specific, grounded, and complete.",
    "rewritten_output": None,
    "scores": {"specificity": 0.9, "grounding": 1.0, "format": 1.0},
}

REWRITE_VERDICT = {
    "verdict": "rewrite",
    "reason": "Response mentions badge access but omits HR forms and orientation.",
    "rewritten_output": (
        "The three steps are: completing HR forms, attending the two-day "
        "orientation session, and receiving badge access from security on Day 3."
    ),
    "scores": {"specificity": 0.5, "grounding": 0.8, "format": 0.6},
}

REJECT_VERDICT = {
    "verdict": "reject",
    "reason": "Response fabricates a 'buddy system' not mentioned in the chunk.",
    "rewritten_output": None,
    "scores": {"specificity": 0.3, "grounding": 0.1, "format": 0.5},
}

CHUNKS = [{"chunk_id": 1, "text": GOOD_CHUNK}]
AWS_REGION = "us-east-1"
MODEL_ID = "amazon.nova-micro-v1:0"


# ─────────────────────────────────────────────────────────────────────────────
# _parse_critic_response
# ─────────────────────────────────────────────────────────────────────────────

class TestParseCriticResponse:
    def test_valid_accept(self):
        raw = json.dumps(ACCEPT_VERDICT)
        result = _parse_critic_response(raw)
        assert result is not None
        assert result["verdict"] == "accept"
        assert result["rewritten_output"] is None

    def test_valid_rewrite(self):
        raw = json.dumps(REWRITE_VERDICT)
        result = _parse_critic_response(raw)
        assert result is not None
        assert result["verdict"] == "rewrite"
        assert isinstance(result["rewritten_output"], str)

    def test_valid_reject(self):
        raw = json.dumps(REJECT_VERDICT)
        result = _parse_critic_response(raw)
        assert result is not None
        assert result["verdict"] == "reject"

    def test_strips_markdown_fences(self):
        raw = "```json\n" + json.dumps(ACCEPT_VERDICT) + "\n```"
        result = _parse_critic_response(raw)
        assert result is not None
        assert result["verdict"] == "accept"

    def test_invalid_json_returns_none(self):
        assert _parse_critic_response("this is not JSON") is None

    def test_missing_verdict_key_returns_none(self):
        bad = {"reason": "ok", "scores": {}}
        assert _parse_critic_response(json.dumps(bad)) is None

    def test_bad_verdict_value_returns_none(self):
        bad = {**ACCEPT_VERDICT, "verdict": "maybe"}
        assert _parse_critic_response(json.dumps(bad)) is None

    def test_rewritten_output_forced_none_on_accept(self):
        """Even if LLM returns a rewritten_output on an accept, we clear it."""
        sneaky = {**ACCEPT_VERDICT, "rewritten_output": "some text"}
        result = _parse_critic_response(json.dumps(sneaky))
        assert result["rewritten_output"] is None

    def test_rewritten_output_forced_none_on_reject(self):
        sneaky = {**REJECT_VERDICT, "rewritten_output": "some text"}
        result = _parse_critic_response(json.dumps(sneaky))
        assert result["rewritten_output"] is None


# ─────────────────────────────────────────────────────────────────────────────
# critique_sample — single sample
# ─────────────────────────────────────────────────────────────────────────────

class TestCritiqueSample:
    @patch(f"{CRITIC_PATH}.boto3.client")
    def test_returns_accept_verdict(self, mock_boto):
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.converse.return_value = _make_bedrock_response(ACCEPT_VERDICT)

        result = critique_sample(GOOD_SAMPLE, GOOD_CHUNK, AWS_REGION, MODEL_ID)

        assert result["verdict"] == "accept"
        assert result["rewritten_output"] is None
        assert "scores" in result

    @patch(f"{CRITIC_PATH}.boto3.client")
    def test_returns_rewrite_verdict(self, mock_boto):
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.converse.return_value = _make_bedrock_response(REWRITE_VERDICT)

        result = critique_sample(GOOD_SAMPLE, GOOD_CHUNK, AWS_REGION, MODEL_ID)

        assert result["verdict"] == "rewrite"
        assert isinstance(result["rewritten_output"], str)
        assert len(result["rewritten_output"]) > 0

    @patch(f"{CRITIC_PATH}.boto3.client")
    def test_returns_reject_verdict(self, mock_boto):
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.converse.return_value = _make_bedrock_response(REJECT_VERDICT)

        result = critique_sample(GOOD_SAMPLE, GOOD_CHUNK, AWS_REGION, MODEL_ID)

        assert result["verdict"] == "reject"

    @patch(f"{CRITIC_PATH}.boto3.client")
    def test_malformed_json_retries_then_rejects(self, mock_boto):
        """LLM returns garbage → one retry → still garbage → safe REJECT."""
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": "not json at all!!!"}]}}
        }

        result = critique_sample(
            GOOD_SAMPLE, GOOD_CHUNK, AWS_REGION, MODEL_ID, max_retries=1
        )

        assert result["verdict"] == "reject"
        assert mock_client.converse.call_count == 2  # original + 1 retry

    @patch(f"{CRITIC_PATH}.boto3.client")
    def test_bedrock_exception_falls_back_to_reject(self, mock_boto):
        """If Bedrock raises an exception, we get a safe REJECT, not a crash."""
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.converse.side_effect = Exception("Bedrock timeout")

        result = critique_sample(GOOD_SAMPLE, GOOD_CHUNK, AWS_REGION, MODEL_ID)

        assert result["verdict"] == "reject"
        assert result["scores"]["grounding"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 5 Deliberately Bad Samples — all must be rejected or rewritten, never accepted
# ─────────────────────────────────────────────────────────────────────────────

BAD_SAMPLES = [
    # 1. Completely generic non-answer
    {
        "chunk_id": 1,
        "instruction": "What are the three steps in the employee onboarding process?",
        "input": "",
        "response": "Please refer to the official HR documentation for details.",
    },
    # 2. Hallucination — invents a "buddy system" not in the chunk
    {
        "chunk_id": 1,
        "instruction": "Describe the onboarding process.",
        "input": "",
        "response": (
            "Employees are paired with a buddy for the first week and then "
            "complete online modules before meeting their manager."
        ),
    },
    # 3. Way too short — just a fragment
    {
        "chunk_id": 1,
        "instruction": "What does onboarding involve?",
        "input": "",
        "response": "HR forms.",
    },
    # 4. Vague non-answer
    {
        "chunk_id": 1,
        "instruction": "When does badge access happen?",
        "input": "",
        "response": "Badge access happens at some point during the process.",
    },
    # 5. Incomplete sentence (truncated output)
    {
        "chunk_id": 1,
        "instruction": "List the onboarding steps.",
        "input": "",
        "response": "The steps include completing HR forms and attending the",
    },
]

BAD_VERDICTS = [
    {**REJECT_VERDICT, "reason": "Generic reference to documentation, not specific."},
    {**REJECT_VERDICT, "reason": "Hallucinated buddy system not in the source chunk."},
    {**REWRITE_VERDICT, "reason": "Too short; omits orientation and badge steps."},
    {**REWRITE_VERDICT, "reason": "Vague; does not specify Day 3 from the chunk."},
    {**REWRITE_VERDICT, "reason": "Truncated sentence; response is incomplete."},
]


class TestBadSamplesNeverAccepted:
    @patch(f"{CRITIC_PATH}.boto3.client")
    def test_all_bad_samples_rejected_or_rewritten(self, mock_boto):
        """
        Feed 5 deliberately bad samples through critique_sample.
        Every verdict must be 'reject' or 'rewrite' — never 'accept'.
        """
        mock_client = MagicMock()
        mock_boto.return_value = mock_client

        for bad_sample, bad_verdict in zip(BAD_SAMPLES, BAD_VERDICTS):
            mock_client.converse.return_value = _make_bedrock_response(bad_verdict)
            result = critique_sample(
                bad_sample, GOOD_CHUNK, AWS_REGION, MODEL_ID
            )
            assert result["verdict"] in ("reject", "rewrite"), (
                f"Bad sample was ACCEPTED — this should never happen.\n"
                f"Sample: {bad_sample['response']}\n"
                f"Verdict: {result}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# run_critic_batch
# ─────────────────────────────────────────────────────────────────────────────

class TestRunCriticBatch:
    @patch(f"{CRITIC_PATH}.boto3.client")
    def test_batch_stats_are_correct(self, mock_boto):
        """3 samples: 1 accept, 1 rewrite, 1 reject → correct stat counts."""
        mock_client = MagicMock()
        mock_boto.return_value = mock_client

        dataset = [GOOD_SAMPLE, GOOD_SAMPLE, GOOD_SAMPLE]
        mock_client.converse.side_effect = [
            _make_bedrock_response(ACCEPT_VERDICT),
            _make_bedrock_response(REWRITE_VERDICT),
            _make_bedrock_response(REJECT_VERDICT),
        ]

        output = run_critic_batch(dataset, CHUNKS, AWS_REGION, MODEL_ID)

        stats = output["stats"]
        assert stats["accepted"] == 1
        assert stats["rewritten"] == 1
        assert stats["rejected"] == 1
        assert stats["total"] == 3
        assert stats["survivor_count"] == 2  # accept + rewrite

    @patch(f"{CRITIC_PATH}.boto3.client")
    def test_rewritten_sample_uses_corrected_response(self, mock_boto):
        """When verdict is 'rewrite', the survivor must use rewritten_output."""
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.converse.return_value = _make_bedrock_response(REWRITE_VERDICT)

        output = run_critic_batch([GOOD_SAMPLE], CHUNKS, AWS_REGION, MODEL_ID)

        assert len(output["survivors"]) == 1
        survivor = output["survivors"][0]
        assert survivor["response"] == REWRITE_VERDICT["rewritten_output"]
        assert survivor.get("_critic_rewritten") is True

    @patch(f"{CRITIC_PATH}.boto3.client")
    def test_accepted_sample_unchanged_in_survivors(self, mock_boto):
        """Accepted samples must appear in survivors with their original response."""
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.converse.return_value = _make_bedrock_response(ACCEPT_VERDICT)

        output = run_critic_batch([GOOD_SAMPLE], CHUNKS, AWS_REGION, MODEL_ID)

        assert len(output["survivors"]) == 1
        assert output["survivors"][0]["response"] == GOOD_SAMPLE["response"]

    @patch(f"{CRITIC_PATH}.boto3.client")
    def test_sample_with_missing_chunk_id_is_rejected(self, mock_boto):
        """A sample referencing a chunk_id not in the chunk list must be rejected."""
        mock_client = MagicMock()
        mock_boto.return_value = mock_client  # should NOT be called

        orphan_sample = {**GOOD_SAMPLE, "chunk_id": 999}
        output = run_critic_batch([orphan_sample], CHUNKS, AWS_REGION, MODEL_ID)

        assert output["stats"]["rejected"] == 1
        assert output["stats"]["survivor_count"] == 0
        mock_client.converse.assert_not_called()

    @patch(f"{CRITIC_PATH}.boto3.client")
    def test_empty_dataset_all_accepted_edge_case(self, mock_boto):
        """
        Edge case (P1 Day 4 task): empty dataset → zero samples processed,
        stats all zero, no crash, survivors is empty list.
        This simulates 'all accepted on first pass' → Curriculum is skipped.
        """
        mock_client = MagicMock()
        mock_boto.return_value = mock_client

        output = run_critic_batch([], CHUNKS, AWS_REGION, MODEL_ID)

        assert output["stats"]["total"] == 0
        assert output["stats"]["survivor_count"] == 0
        assert output["survivors"] == []
        assert output["results"] == []
        mock_client.converse.assert_not_called()

    @patch(f"{CRITIC_PATH}.boto3.client")
    def test_accept_pct_calculation(self, mock_boto):
        """accept_pct must be a percentage (0–100), not a ratio (0–1)."""
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.converse.return_value = _make_bedrock_response(ACCEPT_VERDICT)

        dataset = [GOOD_SAMPLE] * 4
        output = run_critic_batch(dataset, CHUNKS, AWS_REGION, MODEL_ID)

        assert output["stats"]["accept_pct"] == 100.0
        assert output["stats"]["reject_pct"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Schema contract test — for P2 Lambda integration
# ─────────────────────────────────────────────────────────────────────────────

class TestOutputSchemaContract:
    """
    Ensures the Critic output always matches the locked schema.
    P2 depends on this shape for the modifai-critic Lambda.
    """
    @patch(f"{CRITIC_PATH}.boto3.client")
    def test_single_verdict_has_required_keys(self, mock_boto):
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.converse.return_value = _make_bedrock_response(ACCEPT_VERDICT)

        result = critique_sample(GOOD_SAMPLE, GOOD_CHUNK, AWS_REGION, MODEL_ID)

        assert "verdict" in result
        assert "reason" in result
        assert "rewritten_output" in result
        assert "scores" in result
        assert all(k in result["scores"] for k in ("specificity", "grounding", "format"))

    @patch(f"{CRITIC_PATH}.boto3.client")
    def test_batch_output_has_required_keys(self, mock_boto):
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.converse.return_value = _make_bedrock_response(ACCEPT_VERDICT)

        output = run_critic_batch([GOOD_SAMPLE], CHUNKS, AWS_REGION, MODEL_ID)

        assert "results" in output
        assert "stats" in output
        assert "survivors" in output
        assert all(
            k in output["stats"]
            for k in ("total", "accepted", "rewritten", "rejected",
                       "accept_pct", "rewrite_pct", "reject_pct", "survivor_count")
        )
