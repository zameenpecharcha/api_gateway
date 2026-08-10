import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

from app.clients.grpc_base_client import GRPCBaseClient
from app.proto_files.property import property_pb2, property_pb2_grpc

load_dotenv()


def _str_id(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _ts(value) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromtimestamp(value)


def _property_dict(p) -> Optional[dict]:
    if not p or not _str_id(getattr(p, "id", None)):
        return None
    return {
        "id": _str_id(p.id),
        "propertyCode": p.property_code or "",
        "title": p.title or "",
        "description": p.description or "",
        "createdBy": _str_id(p.created_by),
        "builderName": p.builder_name or "",
        "projectName": p.project_name or "",
        "reraId": p.rera_id or "",
        "yearBuilt": p.year_built or 0,
        "propertyType": p.property_type or "",
        "listingType": p.listing_type or "",
        "price": float(p.price or 0),
        "currency": p.currency or "INR",
        "areaSize": float(p.area_size or 0),
        "areaUnit": p.area_unit or "",
        "bedrooms": p.bedrooms or 0,
        "bathrooms": p.bathrooms or 0,
        "balconies": p.balconies or 0,
        "parkingCount": p.parking_count or 0,
        "floorNumber": p.floor_number or 0,
        "totalFloors": p.total_floors or 0,
        "noOfUnits": p.no_of_units or 0,
        "constructionStatus": p.construction_status or "",
        "furnishingStatus": p.furnishing_status or "",
        "availabilityDate": p.availability_date or "",
        "location": p.location or "",
        "city": p.city or "",
        "state": p.state or "",
        "country": p.country or "",
        "pinCode": p.pin_code or "",
        "latitude": float(p.latitude or 0),
        "longitude": float(p.longitude or 0),
        "verificationStatus": p.verification_status or "",
        "verifiedBy": _str_id(p.verified_by),
        "verifiedAt": _ts(p.verified_at),
        "rejectedReason": p.rejected_reason or "",
        "status": p.status or "",
        "averageRating": float(p.average_rating or 0),
        "ratingCount": p.rating_count or 0,
        "reviewCount": p.review_count or 0,
        "viewCount": int(p.view_count or 0),
        "saveCount": p.save_count or 0,
        "shareCount": p.share_count or 0,
        "postCount": p.post_count or 0,
        "reportCount": p.report_count or 0,
        "lastActivityAt": _ts(p.last_activity_at),
        "publishedAt": _ts(p.published_at),
        "createdAt": _ts(p.created_at),
        "updatedAt": _ts(p.updated_at),
        "media": [
            {
                "id": _str_id(m.id),
                "propertyId": _str_id(m.property_id),
                "mediaType": m.media_type or "",
                "mediaUrl": m.media_url or "",
                "displayOrder": m.display_order or 0,
                "fileSize": int(m.file_size or 0),
                "fileName": m.file_name or "",
                "isCover": bool(m.is_cover),
            }
            for m in getattr(p, "media", [])
        ],
        "features": [
            {
                "id": _str_id(f.id),
                "featureName": f.feature_name or "",
                "featureValue": f.feature_value or "",
                "displayOrder": f.display_order or 0,
            }
            for f in getattr(p, "features", [])
        ],
    }


def _rating_dict(r) -> dict:
    return {
        "id": _str_id(r.id),
        "propertyId": _str_id(r.property_id),
        "userId": _str_id(r.user_id),
        "overallRating": float(r.overall_rating or 0),
        "locationRating": float(r.location_rating or 0),
        "amenitiesRating": float(r.amenities_rating or 0),
        "constructionRating": float(r.construction_rating or 0),
        "valueForMoneyRating": float(r.value_for_money_rating or 0),
        "title": r.title or "",
        "review": r.review or "",
        "isAnonymous": bool(r.is_anonymous),
        "status": r.status or "",
        "createdAt": _ts(r.created_at),
        "updatedAt": _ts(r.updated_at),
        "likeCount": int(getattr(r, "like_count", 0) or 0),
    }


class PropertyServiceClient(GRPCBaseClient):
    def __init__(self):
        target = os.getenv("PROPERTY_SERVICE_URL", "localhost:50054")
        super().__init__(property_pb2_grpc.PropertyServiceStub, target=target)

    def create_property(self, token=None, **kwargs):
        req = property_pb2.CreatePropertyRequest(
            created_by=_str_id(kwargs["created_by"]),
            title=kwargs.get("title", ""),
            description=kwargs.get("description", ""),
            builder_name=kwargs.get("builder_name", ""),
            project_name=kwargs.get("project_name", ""),
            rera_id=kwargs.get("rera_id", ""),
            year_built=int(kwargs.get("year_built") or 0),
            property_type=kwargs.get("property_type", ""),
            listing_type=kwargs.get("listing_type", ""),
            price=float(kwargs.get("price") or 0),
            currency=kwargs.get("currency", "INR"),
            area_size=float(kwargs.get("area_size") or 0),
            area_unit=kwargs.get("area_unit", ""),
            bedrooms=int(kwargs.get("bedrooms") or 0),
            bathrooms=int(kwargs.get("bathrooms") or 0),
            balconies=int(kwargs.get("balconies") or 0),
            parking_count=int(kwargs.get("parking_count") or 0),
            floor_number=int(kwargs.get("floor_number") or 0),
            total_floors=int(kwargs.get("total_floors") or 0),
            no_of_units=int(kwargs.get("no_of_units") or 0),
            construction_status=kwargs.get("construction_status", ""),
            furnishing_status=kwargs.get("furnishing_status", ""),
            availability_date=kwargs.get("availability_date", ""),
            location=kwargs.get("location", ""),
            city=kwargs.get("city", ""),
            state=kwargs.get("state", ""),
            country=kwargs.get("country", ""),
            pin_code=kwargs.get("pin_code", ""),
            latitude=float(kwargs.get("latitude") or 0),
            longitude=float(kwargs.get("longitude") or 0),
            status=kwargs.get("status", "DRAFT"),
            verification_status=kwargs.get("verification_status", ""),
        )
        return self._call("CreateProperty", req, token=token)

    def get_property(self, property_id: str, token=None):
        return self._call(
            "GetProperty",
            property_pb2.PropertyIdRequest(property_id=_str_id(property_id)),
            token=token,
        )

    def get_property_by_code(self, property_code: str, token=None):
        return self._call(
            "GetPropertyByCode",
            property_pb2.PropertyCodeRequest(property_code=property_code),
            token=token,
        )

    def update_property(self, token=None, **kwargs):
        req = property_pb2.UpdatePropertyRequest(
            property_id=_str_id(kwargs["property_id"]),
            title=kwargs.get("title", ""),
            description=kwargs.get("description", ""),
            builder_name=kwargs.get("builder_name", ""),
            project_name=kwargs.get("project_name", ""),
            rera_id=kwargs.get("rera_id", ""),
            year_built=int(kwargs.get("year_built") or 0),
            property_type=kwargs.get("property_type", ""),
            listing_type=kwargs.get("listing_type", ""),
            price=float(kwargs.get("price") or 0),
            currency=kwargs.get("currency", ""),
            area_size=float(kwargs.get("area_size") or 0),
            area_unit=kwargs.get("area_unit", ""),
            bedrooms=int(kwargs.get("bedrooms") or 0),
            bathrooms=int(kwargs.get("bathrooms") or 0),
            balconies=int(kwargs.get("balconies") or 0),
            parking_count=int(kwargs.get("parking_count") or 0),
            floor_number=int(kwargs.get("floor_number") or 0),
            total_floors=int(kwargs.get("total_floors") or 0),
            no_of_units=int(kwargs.get("no_of_units") or 0),
            construction_status=kwargs.get("construction_status", ""),
            furnishing_status=kwargs.get("furnishing_status", ""),
            availability_date=kwargs.get("availability_date", ""),
            location=kwargs.get("location", ""),
            city=kwargs.get("city", ""),
            state=kwargs.get("state", ""),
            country=kwargs.get("country", ""),
            pin_code=kwargs.get("pin_code", ""),
            latitude=float(kwargs.get("latitude") or 0),
            longitude=float(kwargs.get("longitude") or 0),
        )
        return self._call("UpdateProperty", req, token=token)

    def delete_property(self, property_id: str, token=None):
        return self._call(
            "DeleteProperty",
            property_pb2.PropertyIdRequest(property_id=_str_id(property_id)),
            token=token,
        )

    def get_user_properties(self, user_id: str, page: int = 1, limit: int = 20, token=None):
        return self._call(
            "GetUserProperties",
            property_pb2.UserIdRequest(user_id=_str_id(user_id), page=page, limit=limit),
            token=token,
        )

    def list_public_properties(self, token=None, **kwargs):
        return self._call(
            "ListPublicProperties",
            property_pb2.ListPropertiesRequest(
                page=int(kwargs.get("page") or 1),
                limit=int(kwargs.get("limit") or 20),
                city=kwargs.get("city", ""),
                property_type=kwargs.get("property_type", ""),
                listing_type=kwargs.get("listing_type", ""),
                min_price=float(kwargs.get("min_price") or 0),
                max_price=float(kwargs.get("max_price") or 0),
            ),
            token=token,
        )

    def update_property_status(self, property_id: str, status: str, token=None):
        return self._call(
            "UpdatePropertyStatus",
            property_pb2.UpdatePropertyStatusRequest(
                property_id=_str_id(property_id), status=status,
            ),
            token=token,
        )

    def record_property_view(self, property_id: str, user_id: str = "", token=None, **kwargs):
        return self._call(
            "RecordPropertyView",
            property_pb2.RecordPropertyViewRequest(
                property_id=_str_id(property_id),
                user_id=_str_id(user_id),
                session_id=kwargs.get("session_id", ""),
                device_type=kwargs.get("device_type", ""),
                ip_address=kwargs.get("ip_address", ""),
            ),
            token=token,
        )

    def adjust_property_counter(
        self, property_id: str, counter: str, delta: int = 1, token=None,
    ):
        return self._call(
            "AdjustPropertyCounter",
            property_pb2.AdjustPropertyCounterRequest(
                property_id=_str_id(property_id),
                counter=counter,
                delta=int(delta),
            ),
            token=token,
        )

    def record_property_share(self, property_id: str, token=None):
        return self.adjust_property_counter(property_id, "share_count", 1, token=token)

    def add_property_features(self, property_id: str, features: list, token=None):
        return self._call(
            "AddPropertyFeatures",
            property_pb2.AddFeaturesRequest(
                property_id=_str_id(property_id),
                features=[
                    property_pb2.FeatureInput(
                        feature_name=f.get("feature_name", ""),
                        feature_value=f.get("feature_value", ""),
                        display_order=int(f.get("display_order") or 0),
                    )
                    for f in features
                ],
            ),
            token=token,
        )

    def get_property_features(self, property_id: str, token=None):
        return self._call(
            "GetPropertyFeatures",
            property_pb2.PropertyIdRequest(property_id=_str_id(property_id)),
            token=token,
        )

    def update_property_features(self, property_id: str, features: list, token=None):
        return self._call(
            "UpdatePropertyFeatures",
            property_pb2.UpdateFeaturesRequest(
                property_id=_str_id(property_id),
                features=[
                    property_pb2.FeatureInput(
                        feature_name=f.get("feature_name", ""),
                        feature_value=f.get("feature_value", ""),
                        display_order=int(f.get("display_order") or 0),
                    )
                    for f in features
                ],
            ),
            token=token,
        )

    def create_property_rating(self, token=None, **kwargs):
        return self._call(
            "CreatePropertyRating",
            property_pb2.CreateRatingRequest(
                property_id=_str_id(kwargs["property_id"]),
                user_id=_str_id(kwargs["user_id"]),
                overall_rating=float(kwargs.get("overall_rating") or 0),
                location_rating=float(kwargs.get("location_rating") or 0),
                amenities_rating=float(kwargs.get("amenities_rating") or 0),
                construction_rating=float(kwargs.get("construction_rating") or 0),
                value_for_money_rating=float(kwargs.get("value_for_money_rating") or 0),
                title=kwargs.get("title", ""),
                review=kwargs.get("review", ""),
                is_anonymous=bool(kwargs.get("is_anonymous", False)),
            ),
            token=token,
        )

    def get_property_ratings(self, property_id: str, token=None):
        return self._call(
            "GetPropertyRatings",
            property_pb2.PropertyIdRequest(property_id=_str_id(property_id)),
            token=token,
        )

    def update_property_rating(self, token=None, **kwargs):
        return self._call(
            "UpdatePropertyRating",
            property_pb2.UpdateRatingRequest(
                rating_id=_str_id(kwargs["rating_id"]),
                user_id=_str_id(kwargs["user_id"]),
                overall_rating=float(kwargs.get("overall_rating") or 0),
                location_rating=float(kwargs.get("location_rating") or 0),
                amenities_rating=float(kwargs.get("amenities_rating") or 0),
                construction_rating=float(kwargs.get("construction_rating") or 0),
                value_for_money_rating=float(kwargs.get("value_for_money_rating") or 0),
                title=kwargs.get("title", ""),
                review=kwargs.get("review", ""),
                is_anonymous=bool(kwargs.get("is_anonymous", False)),
            ),
            token=token,
        )

    def delete_property_rating(self, rating_id: str, user_id: str, token=None):
        return self._call(
            "DeletePropertyRating",
            property_pb2.RatingIdRequest(rating_id=_str_id(rating_id), user_id=_str_id(user_id)),
            token=token,
        )

    def get_user_property_ratings(self, user_id: str, page: int = 1, limit: int = 20, token=None):
        return self._call(
            "GetUserPropertyRatings",
            property_pb2.UserIdRequest(user_id=_str_id(user_id), page=page, limit=limit),
            token=token,
        )

    def like_property_rating(self, rating_id: str, user_id: str, token=None):
        return self._call(
            "LikePropertyRating",
            property_pb2.RatingIdRequest(rating_id=_str_id(rating_id), user_id=_str_id(user_id)),
            token=token,
        )

    def unlike_property_rating(self, rating_id: str, user_id: str, token=None):
        return self._call(
            "UnlikePropertyRating",
            property_pb2.RatingIdRequest(rating_id=_str_id(rating_id), user_id=_str_id(user_id)),
            token=token,
        )

    def report_property_review(self, token=None, **kwargs):
        return self._call(
            "ReportPropertyReview",
            property_pb2.ReportPropertyReviewRequest(
                rating_id=_str_id(kwargs["rating_id"]),
                reported_by=_str_id(kwargs["reported_by"]),
                reported_user_id=_str_id(kwargs.get("reported_user_id", "")),
                reason_code=kwargs.get("reason_code", ""),
                description=kwargs.get("description", ""),
            ),
            token=token,
        )

    def submit_property_for_review(self, property_id: str, token=None):
        return self._call(
            "SubmitPropertyForReview",
            property_pb2.SubmitPropertyForReviewRequest(property_id=_str_id(property_id)),
            token=token,
        )

    def verify_builder_property(self, property_id: str, verified_by: str, token=None):
        return self._call(
            "VerifyBuilderProperty",
            property_pb2.ApprovePropertyRequest(
                property_id=_str_id(property_id), verified_by=_str_id(verified_by),
            ),
            token=token,
        )

    def save_property(self, user_id: str, property_id: str, token=None):
        return self._call(
            "SaveProperty",
            property_pb2.SavePropertyRequest(
                user_id=_str_id(user_id), property_id=_str_id(property_id),
            ),
            token=token,
        )

    def remove_saved_property(self, user_id: str, property_id: str, token=None):
        return self._call(
            "RemoveSavedProperty",
            property_pb2.SavePropertyRequest(
                user_id=_str_id(user_id), property_id=_str_id(property_id),
            ),
            token=token,
        )

    def get_saved_properties(self, user_id: str, page: int = 1, limit: int = 20, token=None):
        return self._call(
            "GetSavedProperties",
            property_pb2.UserIdRequest(user_id=_str_id(user_id), page=page, limit=limit),
            token=token,
        )

    def get_pending_properties(self, page: int = 1, limit: int = 20, token=None):
        return self._call(
            "GetPendingProperties",
            property_pb2.ListPropertiesRequest(page=page, limit=limit),
            token=token,
        )

    def approve_property(self, property_id: str, verified_by: str, token=None):
        return self._call(
            "ApproveProperty",
            property_pb2.ApprovePropertyRequest(
                property_id=_str_id(property_id), verified_by=_str_id(verified_by),
            ),
            token=token,
        )

    def reject_property(self, property_id: str, verified_by: str, reason: str, token=None):
        return self._call(
            "RejectProperty",
            property_pb2.RejectPropertyRequest(
                property_id=_str_id(property_id),
                verified_by=_str_id(verified_by),
                reason=reason,
            ),
            token=token,
        )

    def add_property_media(self, property_id: str, uploaded_by: str, media: list, token=None):
        uploads = []
        for m in media:
            uploads.append(property_pb2.PropertyMediaUpload(
                file_path=m.get("file_path") or m.get("filePath", ""),
                media_type=m.get("media_type") or m.get("mediaType", "image"),
                display_order=int(m.get("display_order") or m.get("displayOrder") or 1),
                file_name=m.get("file_name") or m.get("fileName", ""),
                content_type=m.get("content_type") or m.get("contentType", ""),
                is_cover=bool(m.get("is_cover") or m.get("isCover", False)),
            ))
        return self._call(
            "AddPropertyMedia",
            property_pb2.AddPropertyMediaRequest(
                property_id=_str_id(property_id),
                uploaded_by=_str_id(uploaded_by),
                media=uploads,
            ),
            token=token,
        )

    def delete_property_media(self, media_id: str, token=None):
        return self._call(
            "DeletePropertyMedia",
            property_pb2.MediaIdRequest(media_id=_str_id(media_id)),
            token=token,
        )


property_service_client = PropertyServiceClient()
property_dict = _property_dict
rating_dict = _rating_dict
