import logging
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from heiman.database.model_repo import ModelRepo, get_model_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=dict)
async def get_models(
    model_repo: ModelRepo = Depends(get_model_repo),
):
    try:
        models = model_repo.get_all()
        logger.info("[MODEL API] Query models - count=%d", len(models))
        return {"success": True, "data": models}
    except Exception as e:
        logger.error("[MODEL API] Failed to get models: %s", e)
        return {"success": False, "data": [], "message": str(e)}


@router.get("/{model_id}", response_model=dict)
async def get_model(
    model_id: str,
    model_repo: ModelRepo = Depends(get_model_repo),
):
    try:
        model = model_repo.get_by_id(model_id)
        if not model:
            logger.warning("[MODEL API] Model not found: %s", model_id)
            raise HTTPException(status_code=404, detail="Model not found")
        
        logger.info("[MODEL API] Get model - id=%s, name=%s", model_id, model.get("name"))
        return {"success": True, "data": model}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[MODEL API] Failed to get model %s: %s", model_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{model_id}/deploy", response_model=dict)
async def deploy_model(
    model_id: str,
    model_repo: ModelRepo = Depends(get_model_repo),
):
    try:
        model = model_repo.get_by_id(model_id)
        if not model:
            logger.warning("[MODEL API] Model not found for deploy: %s", model_id)
            raise HTTPException(status_code=404, detail="Model not found")
        
        if model["status"] == "training":
            logger.warning("[MODEL API] Model is still training: %s", model_id)
            raise HTTPException(status_code=400, detail="Model is still training")
        
        success = model_repo.deploy(model_id)
        if success:
            logger.info("[MODEL API] Model deployed: %s", model_id)
            return {"success": True, "message": "Model deployed successfully"}
        else:
            logger.error("[MODEL API] Failed to deploy model: %s", model_id)
            return {"success": False, "message": "Failed to deploy model"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[MODEL API] Failed to deploy model %s: %s", model_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{model_id}/stop", response_model=dict)
async def stop_model(
    model_id: str,
    model_repo: ModelRepo = Depends(get_model_repo),
):
    try:
        model = model_repo.get_by_id(model_id)
        if not model:
            logger.warning("[MODEL API] Model not found for stop: %s", model_id)
            raise HTTPException(status_code=404, detail="Model not found")
        
        success = model_repo.stop(model_id)
        if success:
            logger.info("[MODEL API] Model stopped: %s", model_id)
            return {"success": True, "message": "Model stopped successfully"}
        else:
            logger.error("[MODEL API] Failed to stop model: %s", model_id)
            return {"success": False, "message": "Failed to stop model"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[MODEL API] Failed to stop model %s: %s", model_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{model_id}/configure", response_model=dict)
async def configure_model(
    model_id: str,
    data: dict,
    model_repo: ModelRepo = Depends(get_model_repo),
):
    try:
        model = model_repo.get_by_id(model_id)
        if not model:
            logger.warning("[MODEL API] Model not found for configure: %s", model_id)
            raise HTTPException(status_code=404, detail="Model not found")
        
        model_repo.update(model_id, data)
        logger.info("[MODEL API] Model configured: %s, data=%s", model_id, data)
        return {"success": True, "message": "Model configured successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[MODEL API] Failed to configure model %s: %s", model_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=dict)
async def upload_model(
    file: UploadFile = File(...),
    model_repo: ModelRepo = Depends(get_model_repo),
):
    try:
        import json
        content = await file.read()
        model_data = json.loads(content.decode())
        
        if "id" not in model_data:
            raise HTTPException(status_code=400, detail="Model ID is required")
        
        model_repo.create(model_data)
        logger.info("[MODEL API] Model uploaded: %s", model_data.get("id"))
        return {"success": True, "message": "Model uploaded successfully"}
    except HTTPException:
        raise
    except json.JSONDecodeError:
        logger.error("[MODEL API] Invalid JSON in uploaded model")
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        logger.error("[MODEL API] Failed to upload model: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=dict)
async def create_model(
    data: dict,
    model_repo: ModelRepo = Depends(get_model_repo),
):
    try:
        if "id" not in data:
            raise HTTPException(status_code=400, detail="Model ID is required")
        
        model_repo.create(data)
        logger.info("[MODEL API] Model created: %s", data.get("id"))
        return {"success": True, "message": "Model created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[MODEL API] Failed to create model: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{model_id}", response_model=dict)
async def update_model(
    model_id: str,
    data: dict,
    model_repo: ModelRepo = Depends(get_model_repo),
):
    try:
        model = model_repo.get_by_id(model_id)
        if not model:
            logger.warning("[MODEL API] Model not found for update: %s", model_id)
            raise HTTPException(status_code=404, detail="Model not found")
        
        model_repo.update(model_id, data)
        logger.info("[MODEL API] Model updated: %s", model_id)
        return {"success": True, "message": "Model updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[MODEL API] Failed to update model %s: %s", model_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{model_id}", response_model=dict)
async def delete_model(
    model_id: str,
    model_repo: ModelRepo = Depends(get_model_repo),
):
    try:
        model = model_repo.get_by_id(model_id)
        if not model:
            logger.warning("[MODEL API] Model not found for delete: %s", model_id)
            raise HTTPException(status_code=404, detail="Model not found")
        
        success = model_repo.delete(model_id)
        if success:
            logger.info("[MODEL API] Model deleted: %s", model_id)
            return {"success": True, "message": "Model deleted successfully"}
        else:
            logger.error("[MODEL API] Failed to delete model: %s", model_id)
            return {"success": False, "message": "Failed to delete model"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[MODEL API] Failed to delete model %s: %s", model_id, e)
        raise HTTPException(status_code=500, detail=str(e))
