from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json
import uuid

from app.database import get_db
from app.models.project import Project, ProjectStatus
from app.services.aws_service import AWSService

router = APIRouter()


# --- Pydantic Schemas ---

class ProjectCreateReq(BaseModel):
    name: str
    description: Optional[str] = None
    mode: str = "full"
    intent: Optional[str] = None
    base_model: Optional[str] = "apac.amazon.nova-micro-v1:0"
    config: Optional[dict] = None


class ProjectRes(BaseModel):
    id: str
    name: str
    description: Optional[str]
    status: ProjectStatus
    mode: str
    intent: Optional[str] = None
    s3_prefix: Optional[str]
    base_model: Optional[str]
    execution_arn: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UploadUrlRes(BaseModel):
    presigned_url: str
    file_key: str


class StartPipelineReq(BaseModel):
    config: dict
    uploaded_filenames: list[str] = []  # actual filenames the user uploaded


class StartPipelineRes(BaseModel):
    message: str
    execution_arn: str


class ProjectStatusRes(BaseModel):
    project_status: ProjectStatus
    pipeline_status: str


class ProjectResultsRes(BaseModel):
    status: str
    error: Optional[dict] = None
    dataset_download_url: Optional[str] = None
    model_endpoint_url: Optional[str] = None
    training_metrics: Optional[dict] = None
    step_results: Optional[dict] = None


class DatasetExampleUpdate(BaseModel):
    instruction: Optional[str] = None
    response: Optional[str] = None


class DatasetExportRes(BaseModel):
    download_url: str


# --- Helper ---

async def _get_project_or_404(project_id: str, db: AsyncSession) -> Project:
    """Fetch a project by ID or raise 404."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# --- Endpoints ---

# Task 4.3: List all projects
@router.get("/", response_model=list[ProjectRes])
async def list_projects(db: AsyncSession = Depends(get_db)):
    """List all projects, newest first."""
    result = await db.execute(
        select(Project).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return projects


# Task 4.2: Create project
@router.post("/", response_model=ProjectRes)
async def create_project(req: ProjectCreateReq, db: AsyncSession = Depends(get_db)):
    """Create a new Modifai project."""
    project_id = str(uuid.uuid4())
    s3_prefix = f"projects/{project_id}/"

    project = Project(
        id=project_id,
        name=req.name,
        description=req.description,
        mode=req.mode,
        intent=req.intent,
        s3_prefix=s3_prefix,
        base_model=req.base_model,
        config_json=json.dumps(req.config) if req.config else None,
        status=ProjectStatus.PENDING,
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)

    return project


# Task 4.4: Get project detail
@router.get("/{project_id}", response_model=ProjectRes)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get project details."""
    return await _get_project_or_404(project_id, db)


# Task 4.5: Delete project
@router.delete("/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a project and its associated S3 data."""
    project = await _get_project_or_404(project_id, db)

    # Best-effort S3 cleanup
    if project.s3_prefix:
        AWSService.delete_s3_prefix(project.s3_prefix)

    await db.delete(project)
    await db.commit()

    return {"message": "Project deleted successfully"}


# --- Presigned Upload URL ---

@router.post("/{project_id}/upload-url", response_model=UploadUrlRes)
async def get_upload_url(project_id: str, filename: str, db: AsyncSession = Depends(get_db)):
    """Generate a presigned S3 URL for uploading a raw document."""
    project = await _get_project_or_404(project_id, db)

    try:
        url = AWSService.generate_presigned_url(project.s3_prefix, filename)
        return UploadUrlRes(
            presigned_url=url,
            file_key=f"{project.s3_prefix}data/{filename}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Pipeline Execution ---

# Task 5.2: Start pipeline
@router.post("/{project_id}/start", response_model=StartPipelineRes)
async def start_pipeline(project_id: str, req: StartPipelineReq, db: AsyncSession = Depends(get_db)):
    """Start the Step Functions execution for this project."""
    project = await _get_project_or_404(project_id, db)

    if project.status == ProjectStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Pipeline is already running")

    try:
        execution_arn = AWSService.start_pipeline_execution(
            project_id=project.id,
            s3_prefix=project.s3_prefix,
            mode=project.mode,
            config=req.config,
            uploaded_filenames=req.uploaded_filenames,
        )

        project.execution_arn = execution_arn
        project.config_json = json.dumps(req.config)
        project.status = ProjectStatus.RUNNING
        await db.commit()

        return StartPipelineRes(message="Pipeline started", execution_arn=execution_arn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Task 5.3: Poll status
@router.get("/{project_id}/status", response_model=ProjectStatusRes)
async def get_project_status(project_id: str, db: AsyncSession = Depends(get_db)):
    """Poll the status of the Step Functions execution."""
    project = await _get_project_or_404(project_id, db)

    if project.status != ProjectStatus.RUNNING or not project.execution_arn:
        return ProjectStatusRes(
            project_status=project.status,
            pipeline_status="NOT_STARTED" if project.status == ProjectStatus.PENDING else "SUCCEEDED",
        )

    try:
        sf_state = AWSService.get_pipeline_status(project.execution_arn)
        sf_status = sf_state["status"]

        if sf_status == "SUCCEEDED":
            project.status = ProjectStatus.COMPLETED
            await db.commit()
        elif sf_status in ("FAILED", "TIMED_OUT", "ABORTED"):
            project.status = ProjectStatus.FAILED
            await db.commit()

        return ProjectStatusRes(project_status=project.status, pipeline_status=sf_status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Task 5.4: Get results
@router.get("/{project_id}/results", response_model=ProjectResultsRes)
async def get_project_results(project_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch final pipeline outputs: dataset download URL, model endpoint, training metrics."""
    project = await _get_project_or_404(project_id, db)

    if not project.execution_arn:
        return ProjectResultsRes(status="NOT_STARTED")

    try:
        exec_output = AWSService.get_execution_output(project.execution_arn)
        step_results = exec_output.get("output", {}).get("step_results", {})

        # Generate presigned download URL for dataset if available
        dataset_url = None
        qc_result = step_results.get("quality_control", {})
        if qc_result.get("clean_dataset_key"):
            dataset_key = f"{project.s3_prefix}{qc_result['clean_dataset_key']}"
            dataset_url = AWSService.generate_presigned_get_url(dataset_key)

        # Fallback: try the default dataset path if step_results didn't include the key
        if not dataset_url:
            try:
                # Verify the file actually exists before generating a URL
                fallback_key = f"{project.s3_prefix}temp_processing/clean_dataset.jsonl"
                s3_client.head_object(Bucket="modifai-bucket", Key=fallback_key)
                dataset_url = AWSService.generate_presigned_get_url(fallback_key)
            except Exception:
                pass  # Dataset doesn't exist yet

        # Extract model endpoint URL if available
        model_endpoint = None
        deploy_result = step_results.get("deployment", {})
        if deploy_result.get("endpoint_url"):
            model_endpoint = deploy_result["endpoint_url"]

        # Extract training metrics if available
        training_metrics = None
        ft_result = step_results.get("fine_tuning", {})
        if ft_result:
            training_metrics = {
                "duration_min": ft_result.get("duration_min"),
                "final_loss": ft_result.get("final_loss"),
                "job_name": ft_result.get("job_name"),
            }

        return ProjectResultsRes(
            status=exec_output["status"],
            error=exec_output.get("error"),
            dataset_download_url=dataset_url,
            model_endpoint_url=model_endpoint,
            training_metrics=training_metrics,
            step_results=step_results,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Dataset Review Endpoints ---

# Task 6.1: List dataset examples
@router.get("/{project_id}/dataset")
async def get_dataset(project_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch the final generated dataset from S3 if available."""
    project = await _get_project_or_404(project_id, db)

    try:
        dataset = AWSService.get_generated_dataset(project.s3_prefix)
        return {"dataset": dataset, "total": len(dataset)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Task 6.2: Edit a training example
@router.put("/{project_id}/dataset/{example_id}")
async def update_dataset_example(
    project_id: str,
    example_id: int,
    data: DatasetExampleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Edit a training example in the generated dataset."""
    project = await _get_project_or_404(project_id, db)

    update_data = data.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        updated = AWSService.update_dataset_example(project.s3_prefix, example_id, update_data)
        return {"example": updated}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Task 6.3: Delete a training example
@router.delete("/{project_id}/dataset/{example_id}")
async def delete_dataset_example(
    project_id: str,
    example_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a training example from the generated dataset."""
    project = await _get_project_or_404(project_id, db)

    try:
        AWSService.delete_dataset_example(project.s3_prefix, example_id)
        return {"message": "Example deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Task 6.4: Search dataset examples
@router.get("/{project_id}/dataset/search")
async def search_dataset(
    project_id: str,
    q: str = Query(..., min_length=1, description="Search query"),
    db: AsyncSession = Depends(get_db),
):
    """Search training examples by content."""
    project = await _get_project_or_404(project_id, db)

    try:
        results = AWSService.search_dataset(project.s3_prefix, q)
        return {"results": results, "total": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Task 6.5: Export dataset as JSONL download
@router.get("/{project_id}/dataset/export", response_model=DatasetExportRes)
async def export_dataset(project_id: str, db: AsyncSession = Depends(get_db)):
    """Generate a presigned download URL for the JSONL dataset."""
    project = await _get_project_or_404(project_id, db)

    try:
        download_url = AWSService.get_dataset_export_url(project.s3_prefix)
        return DatasetExportRes(download_url=download_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Execution Logs ---

@router.get("/{project_id}/logs")
async def get_project_logs(project_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch the raw Step Functions execution logs."""
    project = await _get_project_or_404(project_id, db)

    if not project.execution_arn:
        return {"logs": []}

    try:
        logs = AWSService.get_execution_history(project.execution_arn)
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
