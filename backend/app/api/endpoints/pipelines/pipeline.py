from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime
from app.db.database import pipelines_collection, pipelines_history_collection, users_collection
from app.services.storage.mongodb_service import get_pipelines
from app.services.storage.storage_keys import (
    PipelineStatus,
    PipelineStorageKeys,
    PipelineDisplayStatus,
)
from app.schemas.models import (
    RunPipelineRequest,
    RunPipelineResponse,
    GetPipelinesResponse,
    PipelineHistoryResponse,
    PipelineStatistics,
    ExecutionLogRecord,
    PipelineItem,
)
from app.services.tasks.task_executor import submit_task
from app.auth.user_auth import get_current_user, get_user_details
from typing import Optional, List
from bson import ObjectId

run_router = APIRouter()


@run_router.get("/pipelines", response_model=GetPipelinesResponse, operation_id="get_pipelines")
def get_pipelines_endpoint(current_user: dict = Depends(get_current_user)) -> GetPipelinesResponse:
    pipelines = get_pipelines()
    return GetPipelinesResponse(data=pipelines)


@run_router.post("/pipelines/run", response_model=RunPipelineResponse, operation_id="run_pipeline")
def run_pipeline(request: RunPipelineRequest, fastapi_request: Request, current_user: dict = Depends(get_current_user)) -> RunPipelineResponse:
    result, exec_id = submit_task(
        dataset_id=request.pipeline_id,
        dataset_name=request.pipeline_name,
        user_id=str(current_user.get("_id")),
        pipeline_id=request.pipeline_id,
    )
    status = result.get("status", PipelineStatus.RUNNING.value)
    executed_at = result.get("executed_at")
    return RunPipelineResponse(status=status, execution_id=exec_id, executed_at=executed_at)


@run_router.get("/pipeline/status", response_model=PipelineStatus, operation_id="get_pipeline_status")
def get_pipeline_status(pipeline_id: str, execution_id: str, current_user: dict = Depends(get_current_user)) -> PipelineStatus:
    # Safely query pipeline by pipeline_id supporting both ObjectId and string UUIDs
    id_queries = [{"_id": pipeline_id}]
    if ObjectId.is_valid(str(pipeline_id)):
        id_queries.append({"_id": ObjectId(str(pipeline_id))})
    pipeline = pipelines_collection.find_one({"$or": id_queries})

    if not pipeline:
        raise HTTPException(
            status_code=404, detail="No pipeline with the given pipeline_id")

    # Query history by canonical execution_id
    history_doc = pipelines_history_collection.find_one({
        PipelineStorageKeys.EXECUTION_ID: execution_id
    })

    if not history_doc:
        raise HTTPException(
            status_code=404, detail="No history available with the given execution_id")

    raw_status = history_doc.get(PipelineStorageKeys.STATUS, PipelineStatus.NULL.value)
    if raw_status == PipelineStatus.COMPLETED.value:
        return PipelineStatus.COMPLETED
    elif raw_status == PipelineStatus.ERROR.value:
        return PipelineStatus.ERROR
    elif raw_status == PipelineStatus.RUNNING.value:
        return PipelineStatus.RUNNING
    else:
        return PipelineStatus.NULL


@run_router.get("/pipelines/filter", response_model=GetPipelinesResponse)
def get_filtered_pipelines(
    pipeline: Optional[str] = None,
    date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
) -> GetPipelinesResponse:
    match_stage = {}
    if pipeline:
        match_stage[PipelineStorageKeys.NAME] = {"$regex": pipeline, "$options": "i"}

    pipelines_cursor = pipelines_collection.find(match_stage)
    pipelines = []

    for doc in pipelines_cursor:
        history_ids = doc.get(PipelineStorageKeys.HISTORY, [])
        history = []
        latest_status = PipelineStatus.NULL

        for history_id in history_ids:
            hist_queries = [{"_id": history_id}]
            if ObjectId.is_valid(str(history_id)):
                hist_queries.append({"_id": ObjectId(str(history_id))})
            history_doc = pipelines_history_collection.find_one({"$or": hist_queries})

            if history_doc:
                exec_id = history_doc.get(PipelineStorageKeys.EXECUTION_ID) or str(history_doc.get(PipelineStorageKeys.ID))
                st = history_doc.get(PipelineStorageKeys.STATUS)
                if st == PipelineStatus.COMPLETED.value:
                    latest_status = PipelineStatus.COMPLETED
                elif st == PipelineStatus.ERROR.value:
                    latest_status = PipelineStatus.ERROR
                elif st == PipelineStatus.RUNNING.value:
                    latest_status = PipelineStatus.RUNNING

                user_details = get_user_details(history_doc.get(PipelineStorageKeys.USER_ID))
                record = {
                    "_id": str(history_doc.get(PipelineStorageKeys.ID)),
                    "execution_id": exec_id,
                    "status": st,
                    "first_name": user_details["first_name"],
                    "last_name": user_details["last_name"],
                    "email": user_details["email"],
                    "created_at": history_doc.get(PipelineStorageKeys.CREATED_AT),
                    "updated_at": history_doc.get(PipelineStorageKeys.UPDATED_AT),
                }

                if date:
                    try:
                        filter_date = datetime.fromisoformat(date).isoformat()
                        if history_doc.get(PipelineStorageKeys.CREATED_AT, "") >= filter_date:
                            history.append(record)
                    except ValueError:
                        history.append(record)
                else:
                    history.append(record)

        pipelines.append(
            {
                "_id": str(doc.get(PipelineStorageKeys.ID)),
                "pipeline_name": doc.get(PipelineStorageKeys.NAME),
                "is_enabled": doc.get(PipelineStorageKeys.IS_ENABLED, True),
                "pipeline_status": latest_status,
                "history_ids": [str(hid) for hid in history_ids],
                "history": history,
            }
        )

    return GetPipelinesResponse(data=pipelines)


@run_router.get("/pipelines/history", response_model=PipelineHistoryResponse, operation_id="get_pipeline_history")
def get_pipeline_history(
    pipeline_id: Optional[str] = None,
    limit: Optional[int] = 50,
    current_user: dict = Depends(get_current_user),
) -> PipelineHistoryResponse:
    """
    Get real execution history and aggregate statistics from pipelines_history_collection.
    Single source of truth for Pipeline Statistics and Run Logs.
    """
    # 1. Compute aggregate statistics from all execution history
    all_docs = list(pipelines_history_collection.find({}))
    total_execs = len(all_docs)
    successful_execs = 0
    failed_execs = 0
    running_execs = 0

    for doc in all_docs:
        st = str(doc.get(PipelineStorageKeys.STATUS, "")).lower()
        if st == PipelineStatus.COMPLETED.value:
            successful_execs += 1
        elif st == PipelineStatus.ERROR.value:
            failed_execs += 1
        elif st == PipelineStatus.RUNNING.value:
            running_execs += 1

    stats = PipelineStatistics(
        total_executions=total_execs,
        successful_executions=successful_execs,
        failed_executions=failed_execs,
        running_executions=running_execs,
    )

    # 2. Build filter query if pipeline_id is provided
    filter_query = {}
    if pipeline_id and pipeline_id != "all":
        id_queries = [{"_id": pipeline_id}]
        if ObjectId.is_valid(str(pipeline_id)):
            id_queries.append({"_id": ObjectId(str(pipeline_id))})
        target_pipe = pipelines_collection.find_one({"$or": id_queries})

        names = [pipeline_id]
        ids = [pipeline_id]
        if target_pipe:
            if target_pipe.get(PipelineStorageKeys.NAME):
                names.append(target_pipe.get(PipelineStorageKeys.NAME))
            ids.append(str(target_pipe.get(PipelineStorageKeys.ID, "")))

        filter_query = {
            "$or": [
                {PipelineStorageKeys.PIPELINE_ID: {"$in": ids}},
                {PipelineStorageKeys.PIPELINE_NAME: {"$in": names}},
            ]
        }

    # 3. Retrieve execution records sorted by created_at descending
    cursor = pipelines_history_collection.find(filter_query).sort(PipelineStorageKeys.CREATED_AT, -1).limit(limit)

    execution_records: List[ExecutionLogRecord] = []
    for doc in cursor:
        exec_id = doc.get(PipelineStorageKeys.EXECUTION_ID) or str(doc.get(PipelineStorageKeys.ID))
        pipe_name = doc.get(PipelineStorageKeys.PIPELINE_NAME) or "Unknown Pipeline"
        created_at_raw = doc.get(PipelineStorageKeys.CREATED_AT, "")
        updated_at_raw = doc.get(PipelineStorageKeys.UPDATED_AT, "")
        st = doc.get(PipelineStorageKeys.STATUS, PipelineStatus.NULL.value)

        # Compute duration
        duration_str = "--"
        if created_at_raw and updated_at_raw and st != PipelineStatus.RUNNING.value:
            try:
                dt_start = datetime.fromisoformat(created_at_raw)
                dt_end = datetime.fromisoformat(updated_at_raw)
                secs = int((dt_end - dt_start).total_seconds())
                duration_str = f"{secs}s" if secs >= 0 else "--"
            except Exception:
                duration_str = "--"

        # Format display date
        display_date = created_at_raw
        if created_at_raw:
            try:
                dt = datetime.fromisoformat(created_at_raw)
                display_date = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

        # Format user display
        user_id = doc.get(PipelineStorageKeys.USER_ID)
        user_display = "System"
        if user_id:
            try:
                user_info = get_user_details(user_id)
                full_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
                user_display = full_name if full_name else user_info.get("email", "System")
            except Exception:
                user_display = str(user_id)

        # Status display formatting
        status_disp = PipelineDisplayStatus.UNKNOWN
        if st == PipelineStatus.RUNNING.value:
            status_disp = PipelineDisplayStatus.RUNNING
        elif st == PipelineStatus.COMPLETED.value:
            status_disp = PipelineDisplayStatus.COMPLETED
        elif st == PipelineStatus.ERROR.value:
            status_disp = PipelineDisplayStatus.ERROR

        execution_records.append(
            ExecutionLogRecord(
                id=exec_id,
                commands=pipe_name,
                dateTime=display_date,
                user=user_display,
                status=status_disp,
                duration=duration_str,
                pipeline_id=doc.get(PipelineStorageKeys.PIPELINE_ID),
                created_at=created_at_raw,
                updated_at=updated_at_raw,
                error=doc.get(PipelineStorageKeys.ERROR),
            )
        )

    return PipelineHistoryResponse(statistics=stats, executions=execution_records)
