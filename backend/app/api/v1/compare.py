"""
Model Comparison endpoint — Task 28.

Sends the same prompt to both the base foundation model (Bedrock Nova Micro)
and a fine-tuned model (SageMaker endpoint), returning both responses
with latency metrics for side-by-side comparison.
"""
import asyncio
import time

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.services.aws_service import AWSService
from sqlalchemy import select

router = APIRouter()


class CompareRequest(BaseModel):
    project_id: str
    prompt: str
    system_prompt: Optional[str] = None


class ModelResult(BaseModel):
    response: str
    latency_ms: int
    model_id: str
    error: Optional[str] = None


class CompareResponse(BaseModel):
    base_model: ModelResult
    fine_tuned: ModelResult


@router.post("/", response_model=CompareResponse)
async def compare_models(req: CompareRequest, db: AsyncSession = Depends(get_db)):
    """
    Compare base model vs fine-tuned model by sending the same prompt to both.
    """
    # Fetch project to get the SageMaker endpoint
    result = await db.execute(select(Project).where(Project.id == req.project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get the fine-tuned model endpoint from execution results
    endpoint_name = None
    if project.execution_arn:
        try:
            exec_output = AWSService.get_execution_output(project.execution_arn)
            step_results = exec_output.get("output", {}).get("step_results", {})
            deploy_result = step_results.get("deployment", {})
            endpoint_name = deploy_result.get("endpoint_name") or deploy_result.get("endpoint_url")
        except Exception:
            pass

    # Call base model
    async def call_base():
        start = time.perf_counter()
        result = AWSService.invoke_base_model(req.prompt, req.system_prompt)
        elapsed = int((time.perf_counter() - start) * 1000)
        return ModelResult(
            response=result.get("response", ""),
            latency_ms=elapsed,
            model_id="amazon.nova-micro-v1:0",
            error=result.get("error"),
        )

    # Call fine-tuned model (or return a placeholder if no endpoint)
    async def call_finetuned():
        if not endpoint_name:
            return ModelResult(
                response="⚠️ No fine-tuned model endpoint is available for this project. "
                         "The model may not have been deployed yet, or this project "
                         "didn't include a fine-tuning step.",
                latency_ms=0,
                model_id="not-deployed",
                error="No SageMaker endpoint found",
            )
        start = time.perf_counter()
        result = AWSService.invoke_sagemaker_endpoint(endpoint_name, req.prompt, req.system_prompt)
        elapsed = int((time.perf_counter() - start) * 1000)
        return ModelResult(
            response=result.get("response", ""),
            latency_ms=elapsed,
            model_id=endpoint_name,
            error=result.get("error"),
        )

    # Run both calls concurrently
    base_result, ft_result = await asyncio.gather(call_base(), call_finetuned())

    return CompareResponse(base_model=base_result, fine_tuned=ft_result)
