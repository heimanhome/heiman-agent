import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from pydantic import BaseModel

from heiman.database.connector import get_db_connector
from heiman.database.product_repo import ProductRepo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["products"])


def get_product_repo() -> ProductRepo:
    db = get_db_connector()
    return ProductRepo(db)


@router.get("")
async def list_products(
    classified_name: str | None = None,
    keyword: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    repo: ProductRepo = Depends(get_product_repo),
):
    try:
        if keyword:
            products = repo.search_products(keyword, limit)
        else:
            products = repo.list_products(classified_name, limit, offset)
        total = repo.get_product_count()
        return {"success": True, "data": {"items": products, "total": total}}
    except Exception as e:
        logger.error("[Products] Failed to list products: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/classifications")
async def list_classifications(
    repo: ProductRepo = Depends(get_product_repo),
):
    try:
        classifications = repo.list_classifications()
        return {"success": True, "data": classifications}
    except Exception as e:
        logger.error("[Products] Failed to list classifications: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{product_id}")
async def get_product(
    product_id: str,
    repo: ProductRepo = Depends(get_product_repo),
):
    try:
        product = repo.get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"success": True, "data": product}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Products] Failed to get product %s: %s", product_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{product_id}/properties")
async def get_product_properties(
    product_id: str,
    repo: ProductRepo = Depends(get_product_repo),
):
    try:
        properties = repo.get_product_properties(product_id)
        return {"success": True, "data": properties}
    except Exception as e:
        logger.error("[Products] Failed to get properties for %s: %s", product_id, e)
        raise HTTPException(status_code=500, detail=str(e))


class ImportRequest(BaseModel):
    sql_path: str | None = None


@router.post("/import")
async def import_products(
    request: ImportRequest | None = None,
    repo: ProductRepo = Depends(get_product_repo),
):
    try:
        sql_path = request.sql_path if request else None
        if not sql_path:
            import os
            sql_path = os.environ.get("HEIMAN_PRODUCT_SQL", "")
            if not sql_path:
                from heiman.config import get_settings
                settings = get_settings()
                sql_path = str(settings.directories.config_dir / "dev_product.sql")

        logger.info("[Products] Importing products from %s", sql_path)
        count = repo.import_from_sql(sql_path)

        return {"success": True, "data": {"count": count, "message": f"Successfully imported {count} products"}}
    except Exception as e:
        logger.error("[Products] Failed to import products: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary")
async def get_product_stats(
    repo: ProductRepo = Depends(get_product_repo),
):
    try:
        total = repo.get_product_count()
        classifications = repo.list_classifications()
        return {
            "success": True,
            "data": {
                "total": total,
                "classifications": len(classifications),
                "by_classification": classifications,
            }
        }
    except Exception as e:
        logger.error("[Products] Failed to get stats: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
