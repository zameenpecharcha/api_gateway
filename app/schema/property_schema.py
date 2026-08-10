import typing
from datetime import datetime

import strawberry
from strawberry.types import Info

from app.clients.property.property_client import property_dict, property_service_client, rating_dict
from app.clients.user.user_client import user_service_client
from app.exception.UserException import REException
from app.utils.jwt_utils import decode_jwt_token, get_token
from app.utils.log_utils import log_msg


def _viewer_id(token: str) -> str:
    if not token:
        return ""
    try:
        payload = decode_jwt_token(token)
        return str(payload.get("sub") or payload.get("user_id") or "").strip()
    except Exception:
        return ""


def _viewer_role(token: str) -> str:
    if not token:
        return ""
    try:
        payload = decode_jwt_token(token)
        return str(payload.get("role") or "").strip().upper()
    except Exception:
        return ""


def _require_login(token: str) -> str:
    user_id = _viewer_id(token)
    if not user_id:
        raise REException("UNAUTHORIZED", "Login required", "Missing user").to_graphql_error()
    return user_id


def _require_admin(token: str) -> str:
    user_id = _require_login(token)
    if _viewer_role(token) != "ADMIN":
        raise REException("FORBIDDEN", "Admin access required", "Not admin").to_graphql_error()
    return user_id


def _creation_status_for_role(role: str) -> tuple[str, str]:
    """Return (property_status, verification_status) for new listings."""
    if role in ("ADMIN", "BUILDER"):
        return "PUBLISHED", "VERIFIED"
    return "PENDING_VERIFICATION", "PENDING"


def _to_rating(data: dict) -> "PropertyRating":
    return PropertyRating(
        id=data["id"],
        propertyId=data["propertyId"],
        userId=data["userId"],
        overallRating=data["overallRating"],
        title=data.get("title", ""),
        review=data.get("review", ""),
        isAnonymous=data.get("isAnonymous", False),
        likeCount=data.get("likeCount", 0),
        createdAt=data.get("createdAt"),
    )


def _enrich_creator(prop_dict: dict, token: str) -> dict:
    creator_id = prop_dict.get("createdBy") or ""
    if not creator_id:
        return prop_dict
    try:
        user = user_service_client.get_user(creator_id, token=token)
        if user and getattr(user, "success", False):
            prop_dict["creatorFirstName"] = getattr(user, "first_name", "") or ""
            prop_dict["creatorLastName"] = getattr(user, "last_name", "") or ""
            prop_dict["creatorEmail"] = getattr(user, "email", "") or ""
            prop_dict["creatorRole"] = getattr(user, "role", "") or ""
    except Exception as e:
        log_msg("warning", f"creator enrichment failed: {e}")
    return prop_dict


def _to_property(data: dict) -> "Property":
    return Property(
        id=data["id"],
        propertyCode=data.get("propertyCode", ""),
        title=data.get("title", ""),
        description=data.get("description", ""),
        createdBy=data.get("createdBy", ""),
        creatorFirstName=data.get("creatorFirstName", ""),
        creatorLastName=data.get("creatorLastName", ""),
        creatorEmail=data.get("creatorEmail", ""),
        creatorRole=data.get("creatorRole", ""),
        builderName=data.get("builderName", ""),
        projectName=data.get("projectName", ""),
        propertyType=data.get("propertyType", ""),
        listingType=data.get("listingType", ""),
        price=data.get("price", 0.0),
        currency=data.get("currency", "INR"),
        city=data.get("city", ""),
        state=data.get("state", ""),
        country=data.get("country", ""),
        status=data.get("status", ""),
        verificationStatus=data.get("verificationStatus", ""),
        averageRating=data.get("averageRating", 0.0),
        ratingCount=data.get("ratingCount", 0),
        viewCount=data.get("viewCount", 0),
        saveCount=data.get("saveCount", 0),
        createdAt=data.get("createdAt"),
        updatedAt=data.get("updatedAt"),
    )


@strawberry.type
class PropertyMedia:
    id: str
    propertyId: str = strawberry.field(name="propertyId")
    mediaType: str = strawberry.field(name="mediaType")
    mediaUrl: str = strawberry.field(name="mediaUrl")
    displayOrder: int = strawberry.field(name="displayOrder")
    fileSize: int = strawberry.field(name="fileSize")
    isCover: bool = strawberry.field(name="isCover")


@strawberry.type
class PropertyFeature:
    id: str
    featureName: str = strawberry.field(name="featureName")
    featureValue: str = strawberry.field(name="featureValue")
    displayOrder: int = strawberry.field(name="displayOrder")


@strawberry.type
class PropertyRating:
    id: str
    propertyId: str = strawberry.field(name="propertyId")
    userId: str = strawberry.field(name="userId")
    overallRating: float = strawberry.field(name="overallRating")
    title: str
    review: str
    isAnonymous: bool = strawberry.field(name="isAnonymous")
    likeCount: int = strawberry.field(name="likeCount", default=0)
    createdAt: typing.Optional[datetime] = strawberry.field(name="createdAt")


@strawberry.type
class Property:
    id: str
    propertyCode: str = strawberry.field(name="propertyCode")
    title: str
    description: str
    createdBy: str = strawberry.field(name="createdBy")
    creatorFirstName: str = strawberry.field(name="creatorFirstName")
    creatorLastName: str = strawberry.field(name="creatorLastName")
    creatorEmail: str = strawberry.field(name="creatorEmail")
    creatorRole: str = strawberry.field(name="creatorRole")
    builderName: str = strawberry.field(name="builderName")
    projectName: str = strawberry.field(name="projectName")
    propertyType: str = strawberry.field(name="propertyType")
    listingType: str = strawberry.field(name="listingType")
    price: float
    currency: str
    city: str
    state: str
    country: str
    status: str
    verificationStatus: str = strawberry.field(name="verificationStatus")
    averageRating: float = strawberry.field(name="averageRating")
    ratingCount: int = strawberry.field(name="ratingCount")
    viewCount: int = strawberry.field(name="viewCount")
    saveCount: int = strawberry.field(name="saveCount")
    createdAt: typing.Optional[datetime] = strawberry.field(name="createdAt")
    updatedAt: typing.Optional[datetime] = strawberry.field(name="updatedAt")


@strawberry.type
class PropertyListPage:
    properties: typing.List[Property]
    total: int
    page: int
    limit: int


@strawberry.type
class GenericResult:
    success: bool
    message: str


@strawberry.input
class CreatePropertyInput:
    title: str
    description: str = ""
    builderName: str = ""
    projectName: str = ""
    propertyType: str = "APARTMENT"
    listingType: str = "SALE"
    price: float = 0.0
    currency: str = "INR"
    city: str = ""
    state: str = ""
    country: str = "India"
    location: str = ""
    bedrooms: int = 0
    bathrooms: int = 0


@strawberry.input
class UpdatePropertyInput:
    propertyId: str
    title: typing.Optional[str] = None
    description: typing.Optional[str] = None
    builderName: typing.Optional[str] = None
    projectName: typing.Optional[str] = None
    propertyType: typing.Optional[str] = None
    listingType: typing.Optional[str] = None
    price: typing.Optional[float] = None
    currency: typing.Optional[str] = None
    city: typing.Optional[str] = None
    state: typing.Optional[str] = None
    country: typing.Optional[str] = None
    location: typing.Optional[str] = None
    bedrooms: typing.Optional[int] = None
    bathrooms: typing.Optional[int] = None


@strawberry.input
class FeatureInput:
    featureName: str
    featureValue: str = ""
    displayOrder: int = 0


@strawberry.input
class PropertyMediaInput:
    filePath: str
    mediaType: str = "image"
    displayOrder: int = 1
    fileName: str = ""
    contentType: str = ""
    isCover: bool = False


@strawberry.type
class Query:
    @strawberry.field
    def property(self, info: Info, propertyId: str) -> typing.Optional[Property]:
        token = get_token(info)
        resp = property_service_client.get_property(propertyId, token=token)
        if not resp.success:
            return None
        data = _enrich_creator(property_dict(resp.property), token)
        return _to_property(data)

    @strawberry.field
    def propertyByCode(self, info: Info, propertyCode: str) -> typing.Optional[Property]:
        token = get_token(info)
        resp = property_service_client.get_property_by_code(propertyCode, token=token)
        if not resp.success:
            return None
        data = _enrich_creator(property_dict(resp.property), token)
        return _to_property(data)

    @strawberry.field
    def publicProperties(
        self, info: Info, page: int = 1, limit: int = 20,
        city: typing.Optional[str] = None,
        propertyType: typing.Optional[str] = None,
        listingType: typing.Optional[str] = None,
    ) -> PropertyListPage:
        token = get_token(info)
        resp = property_service_client.list_public_properties(
            token=token, page=page, limit=limit,
            city=city or "", property_type=propertyType or "", listing_type=listingType or "",
        )
        props = []
        for p in resp.properties:
            data = _enrich_creator(property_dict(p), token)
            props.append(_to_property(data))
        return PropertyListPage(properties=props, total=resp.total, page=resp.page, limit=resp.limit)

    @strawberry.field
    def userProperties(self, info: Info, userId: str, page: int = 1, limit: int = 20) -> PropertyListPage:
        token = get_token(info)
        resp = property_service_client.get_user_properties(userId, page=page, limit=limit, token=token)
        props = [_to_property(_enrich_creator(property_dict(p), token)) for p in resp.properties]
        return PropertyListPage(properties=props, total=resp.total, page=resp.page, limit=resp.limit)

    @strawberry.field
    def myProperties(self, info: Info, page: int = 1, limit: int = 20) -> PropertyListPage:
        token = get_token(info)
        user_id = _viewer_id(token)
        if not user_id:
            raise REException("UNAUTHORIZED", "Login required", "Missing user").to_graphql_error()
        return Query.userProperties(self, info, userId=user_id, page=page, limit=limit)

    @strawberry.field
    def propertyRatings(self, info: Info, propertyId: str) -> typing.List[PropertyRating]:
        token = get_token(info)
        resp = property_service_client.get_property_ratings(propertyId, token=token)
        return [_to_rating(rating_dict(x)) for x in resp.ratings]

    @strawberry.field
    def propertyReviews(self, info: Info, propertyId: str) -> typing.List[PropertyRating]:
        return Query.propertyRatings(self, info, propertyId=propertyId)

    @strawberry.field
    def propertyAmenities(self, info: Info, propertyId: str) -> typing.List[PropertyFeature]:
        token = get_token(info)
        resp = property_service_client.get_property_features(propertyId, token=token)
        return [
            PropertyFeature(
                id=str(getattr(f, "id", "") or ""),
                featureName=f.feature_name or "",
                featureValue=f.feature_value or "",
                displayOrder=f.display_order or 0,
            )
            for f in resp.features
        ]

    @strawberry.field
    def userPropertyRatings(self, info: Info, userId: str, page: int = 1, limit: int = 20) -> typing.List[PropertyRating]:
        token = get_token(info)
        resp = property_service_client.get_user_property_ratings(userId, page=page, limit=limit, token=token)
        return [_to_rating(rating_dict(x)) for x in resp.ratings]

    @strawberry.field
    def pendingProperties(self, info: Info, page: int = 1, limit: int = 20) -> PropertyListPage:
        token = get_token(info)
        _require_admin(token)
        resp = property_service_client.get_pending_properties(page=page, limit=limit, token=token)
        props = [_to_property(_enrich_creator(property_dict(p), token)) for p in resp.properties]
        return PropertyListPage(properties=props, total=resp.total, page=resp.page, limit=resp.limit)

    @strawberry.field
    def savedProperties(self, info: Info, page: int = 1, limit: int = 20) -> PropertyListPage:
        token = get_token(info)
        user_id = _viewer_id(token)
        resp = property_service_client.get_saved_properties(user_id, page=page, limit=limit, token=token)
        props = [_to_property(_enrich_creator(property_dict(p), token)) for p in resp.properties]
        return PropertyListPage(properties=props, total=resp.total, page=resp.page, limit=resp.limit)


@strawberry.type
class Mutation:
    @strawberry.mutation
    def createProperty(self, info: Info, input: CreatePropertyInput) -> Property:
        token = get_token(info)
        user_id = _require_login(token)
        role = _viewer_role(token)
        status, verification_status = _creation_status_for_role(role)
        resp = property_service_client.create_property(
            token=token, created_by=user_id,
            title=input.title, description=input.description,
            builder_name=input.builderName, project_name=input.projectName,
            property_type=input.propertyType, listing_type=input.listingType,
            price=input.price, currency=input.currency,
            city=input.city, state=input.state, country=input.country,
            location=input.location, bedrooms=input.bedrooms, bathrooms=input.bathrooms,
            status=status, verification_status=verification_status,
        )
        if not resp.success:
            raise REException("CREATE_FAILED", resp.message, resp.message).to_graphql_error()
        return _to_property(_enrich_creator(property_dict(resp.property), token))

    @strawberry.mutation
    def updateProperty(self, info: Info, input: UpdatePropertyInput) -> Property:
        token = get_token(info)
        _require_login(token)
        kwargs = {"property_id": input.propertyId, "token": token}
        for field, key in (
            ("title", "title"), ("description", "description"),
            ("builderName", "builder_name"), ("projectName", "project_name"),
            ("propertyType", "property_type"), ("listingType", "listing_type"),
            ("price", "price"), ("currency", "currency"),
            ("city", "city"), ("state", "state"), ("country", "country"),
            ("location", "location"), ("bedrooms", "bedrooms"), ("bathrooms", "bathrooms"),
        ):
            val = getattr(input, field, None)
            if val is not None:
                kwargs[key] = val
        resp = property_service_client.update_property(**kwargs)
        if not resp.success:
            raise REException("UPDATE_FAILED", resp.message, resp.message).to_graphql_error()
        return _to_property(_enrich_creator(property_dict(resp.property), token))

    @strawberry.mutation
    def submitPropertyForReview(self, info: Info, propertyId: str) -> Property:
        token = get_token(info)
        _require_login(token)
        resp = property_service_client.submit_property_for_review(propertyId, token=token)
        if not resp.success:
            raise REException("SUBMIT_FAILED", resp.message, resp.message).to_graphql_error()
        return _to_property(_enrich_creator(property_dict(resp.property), token))

    @strawberry.mutation
    def deleteProperty(self, info: Info, propertyId: str) -> GenericResult:
        token = get_token(info)
        resp = property_service_client.delete_property(propertyId, token=token)
        return GenericResult(success=resp.success, message=resp.message)

    @strawberry.mutation
    def updatePropertyStatus(self, info: Info, propertyId: str, status: str) -> Property:
        token = get_token(info)
        resp = property_service_client.update_property_status(propertyId, status, token=token)
        if not resp.success:
            raise REException("UPDATE_FAILED", resp.message, resp.message).to_graphql_error()
        return _to_property(_enrich_creator(property_dict(resp.property), token))

    @strawberry.mutation
    def saveProperty(self, info: Info, propertyId: str) -> GenericResult:
        token = get_token(info)
        user_id = _viewer_id(token)
        resp = property_service_client.save_property(user_id, propertyId, token=token)
        return GenericResult(success=resp.success, message=resp.message)

    @strawberry.mutation
    def removeSavedProperty(self, info: Info, propertyId: str) -> GenericResult:
        token = get_token(info)
        user_id = _viewer_id(token)
        resp = property_service_client.remove_saved_property(user_id, propertyId, token=token)
        return GenericResult(success=resp.success, message=resp.message)

    @strawberry.mutation
    def createPropertyRating(
        self, info: Info, propertyId: str, overallRating: float,
        title: str = "", review: str = "", isAnonymous: bool = False,
    ) -> GenericResult:
        token = get_token(info)
        user_id = _require_login(token)
        resp = property_service_client.create_property_rating(
            token=token, property_id=propertyId, user_id=user_id,
            overall_rating=overallRating, title=title, review=review, is_anonymous=isAnonymous,
        )
        return GenericResult(success=resp.success, message=resp.message)

    @strawberry.mutation
    def updatePropertyRating(
        self, info: Info, ratingId: str, overallRating: float,
        title: str = "", review: str = "", isAnonymous: bool = False,
    ) -> GenericResult:
        token = get_token(info)
        user_id = _require_login(token)
        resp = property_service_client.update_property_rating(
            token=token, rating_id=ratingId, user_id=user_id,
            overall_rating=overallRating, title=title, review=review, is_anonymous=isAnonymous,
        )
        return GenericResult(success=resp.success, message=resp.message)

    @strawberry.mutation
    def deletePropertyRating(self, info: Info, ratingId: str) -> GenericResult:
        token = get_token(info)
        user_id = _require_login(token)
        resp = property_service_client.delete_property_rating(ratingId, user_id, token=token)
        return GenericResult(success=resp.success, message=resp.message)

    @strawberry.mutation
    def addPropertyReview(
        self, info: Info, propertyId: str, overallRating: float,
        title: str = "", review: str = "", isAnonymous: bool = False,
    ) -> GenericResult:
        return Mutation.createPropertyRating(
            self, info, propertyId=propertyId, overallRating=overallRating,
            title=title, review=review, isAnonymous=isAnonymous,
        )

    @strawberry.mutation
    def updatePropertyReview(
        self, info: Info, ratingId: str, overallRating: float,
        title: str = "", review: str = "", isAnonymous: bool = False,
    ) -> GenericResult:
        return Mutation.updatePropertyRating(
            self, info, ratingId=ratingId, overallRating=overallRating,
            title=title, review=review, isAnonymous=isAnonymous,
        )

    @strawberry.mutation
    def deletePropertyReview(self, info: Info, ratingId: str) -> GenericResult:
        return Mutation.deletePropertyRating(self, info, ratingId=ratingId)

    @strawberry.mutation
    def likePropertyReview(self, info: Info, ratingId: str) -> GenericResult:
        token = get_token(info)
        user_id = _require_login(token)
        resp = property_service_client.like_property_rating(ratingId, user_id, token=token)
        return GenericResult(success=resp.success, message=resp.message)

    @strawberry.mutation
    def unlikePropertyReview(self, info: Info, ratingId: str) -> GenericResult:
        token = get_token(info)
        user_id = _require_login(token)
        resp = property_service_client.unlike_property_rating(ratingId, user_id, token=token)
        return GenericResult(success=resp.success, message=resp.message)

    @strawberry.mutation
    def reportPropertyReview(
        self, info: Info, ratingId: str, reasonCode: str = "", description: str = "",
    ) -> GenericResult:
        token = get_token(info)
        user_id = _require_login(token)
        resp = property_service_client.report_property_review(
            token=token, rating_id=ratingId, reported_by=user_id,
            reason_code=reasonCode, description=description,
        )
        return GenericResult(success=resp.success, message=resp.message)

    @strawberry.mutation
    def approveProperty(self, info: Info, propertyId: str) -> Property:
        token = get_token(info)
        admin_id = _require_admin(token)
        resp = property_service_client.approve_property(propertyId, admin_id, token=token)
        if not resp.success:
            raise REException("APPROVE_FAILED", resp.message, resp.message).to_graphql_error()
        return _to_property(_enrich_creator(property_dict(resp.property), token))

    @strawberry.mutation
    def rejectProperty(self, info: Info, propertyId: str, reason: str) -> Property:
        token = get_token(info)
        admin_id = _require_admin(token)
        resp = property_service_client.reject_property(propertyId, admin_id, reason, token=token)
        if not resp.success:
            raise REException("REJECT_FAILED", resp.message, resp.message).to_graphql_error()
        return _to_property(_enrich_creator(property_dict(resp.property), token))

    @strawberry.mutation
    def verifyBuilderProperty(self, info: Info, propertyId: str) -> Property:
        token = get_token(info)
        admin_id = _require_admin(token)
        resp = property_service_client.verify_builder_property(propertyId, admin_id, token=token)
        if not resp.success:
            raise REException("VERIFY_FAILED", resp.message, resp.message).to_graphql_error()
        return _to_property(_enrich_creator(property_dict(resp.property), token))

    @strawberry.mutation
    def addPropertyFeatures(self, info: Info, propertyId: str, features: typing.List[FeatureInput]) -> GenericResult:
        token = get_token(info)
        resp = property_service_client.add_property_features(
            propertyId,
            [{"feature_name": f.featureName, "feature_value": f.featureValue, "display_order": f.displayOrder} for f in features],
            token=token,
        )
        return GenericResult(success=resp.success, message=resp.message)

    @strawberry.mutation
    def updatePropertyAmenities(self, info: Info, propertyId: str, features: typing.List[FeatureInput]) -> GenericResult:
        token = get_token(info)
        resp = property_service_client.update_property_features(
            propertyId,
            [{"feature_name": f.featureName, "feature_value": f.featureValue, "display_order": f.displayOrder} for f in features],
            token=token,
        )
        return GenericResult(success=resp.success, message=resp.message)

    @strawberry.mutation
    def addPropertyMedia(self, info: Info, propertyId: str, media: typing.List[PropertyMediaInput]) -> GenericResult:
        token = get_token(info)
        user_id = _viewer_id(token)
        resp = property_service_client.add_property_media(
            propertyId, user_id,
            [{"file_path": m.filePath, "media_type": m.mediaType, "display_order": m.displayOrder,
              "file_name": m.fileName, "content_type": m.contentType, "is_cover": m.isCover} for m in media],
            token=token,
        )
        return GenericResult(success=resp.success, message=resp.message)

    @strawberry.mutation
    def recordPropertyView(self, info: Info, propertyId: str) -> GenericResult:
        token = get_token(info)
        user_id = _viewer_id(token)
        resp = property_service_client.record_property_view(propertyId, user_id, token=token)
        return GenericResult(success=resp.success, message=resp.message)

    @strawberry.mutation
    def recordPropertyShare(self, info: Info, propertyId: str) -> GenericResult:
        token = get_token(info)
        _require_login(token)
        resp = property_service_client.record_property_share(propertyId, token=token)
        return GenericResult(success=resp.success, message=resp.message)
