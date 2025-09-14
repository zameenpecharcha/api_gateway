from fastapi import APIRouter, HTTPException, Query
from app.utils.s3_utils import generate_presigned_put_url

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.get("/presign-post-media")
def presign_post_media(fileName: str = Query(..., alias="fileName"), contentType: str | None = Query(None, alias="contentType")):
    try:
        url, key, public_url = generate_presigned_put_url(file_name=fileName, content_type=contentType)
        return {"url": url, "key": key, "publicUrl": public_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


