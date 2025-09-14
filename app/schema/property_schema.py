import typing
import strawberry
from enum import Enum
from app.exception.UserException import REException
from app.utils.log_utils import log_msg
from app.clients.property.property_client import property_service_client

@strawberry.enum
class PropertyType(Enum):
    APARTMENT = 0
    VILLA = 1
    HOUSE = 2
    LAND = 3

@strawberry.enum
class PropertyStatus(Enum):
    ACTIVE = 0
    INACTIVE = 1
    SOLD = 2
    RENTED = 3

@strawberry.type
class Property:
    propertyId: str = strawberry.field(name="propertyId")
    userId: str = strawberry.field(name="userId")
    title: str
    description: str
    price: float
    location: str
    propertyType: PropertyType = strawberry.field(name="propertyType")
    status: PropertyStatus
    bedrooms: int
    bathrooms: int
    area: float
    yearBuilt: int = strawberry.field(name="yearBuilt")
    images: typing.List[str]
    amenities: typing.List[str]
    createdAt: int = strawberry.field(name="createdAt")
    updatedAt: int = strawberry.field(name="updatedAt")
    viewCount: int = strawberry.field(name="viewCount")
    latitude: float
    longitude: float
    address: str
    city: str
    state: str
    country: str
    zipCode: str = strawberry.field(name="zipCode")
    isActive: bool = strawberry.field(name="isActive")

@strawberry.type
class Query:
    @strawberry.field
    def property(self, propertyId: str) -> typing.Optional[Property]:
        try:
            response = property_service_client.get_property(propertyId)
            if not response.success:
                raise REException("PROPERTY_NOT_FOUND", response.message, "Property not found")
            
            return Property(
                propertyId=response.property.property_id,
                userId=response.property.user_id,
                title=response.property.title,
                description=response.property.description,
                price=response.property.price,
                location=response.property.location,
                propertyType=response.property.property_type,
                status=response.property.status,
                bedrooms=response.property.bedrooms,
                bathrooms=response.property.bathrooms,
                area=response.property.area,
                yearBuilt=response.property.year_built,
                images=list(response.property.images),
                amenities=list(response.property.amenities),
                createdAt=response.property.created_at,
                updatedAt=response.property.updated_at,
                viewCount=response.property.view_count,
                latitude=response.property.latitude,
                longitude=response.property.longitude,
                address=response.property.address,
                city=response.property.city,
                state=response.property.state,
                country=response.property.country,
                zipCode=response.property.zip_code,
                isActive=response.property.is_active
            )
        except Exception as e:
            log_msg("error", f"Error fetching property: {str(e)}")
            raise REException(
                "PROPERTY_NOT_FOUND",
                "Failed to fetch property",
                str(e)
            ).to_graphql_error()

    @strawberry.field
    def search_properties(
        self,
        query: typing.Optional[str] = None,
        propertyType: typing.Optional[PropertyType] = None,
        minPrice: typing.Optional[float] = None,
        maxPrice: typing.Optional[float] = None,
        location: typing.Optional[str] = None,
        minBedrooms: typing.Optional[int] = None,
        minBathrooms: typing.Optional[int] = None,
        minArea: typing.Optional[float] = None,
        maxArea: typing.Optional[float] = None
    ) -> typing.List[Property]:
        try:
            response = property_service_client.search_properties(
                query=query or "",
                property_type=propertyType if propertyType is not None else 0,
                min_price=minPrice or 0,
                max_price=maxPrice or 0,
                location=location or "",
                min_bedrooms=minBedrooms or 0,
                min_bathrooms=minBathrooms or 0,
                min_area=minArea or 0,
                max_area=maxArea or 0
            )
            
            if not response.success:
                raise REException("PROPERTY_SEARCH_FAILED", response.message, "Failed to search properties")
            
            return [
                Property(
                    propertyId=prop.property_id,
                    userId=prop.user_id,
                    title=prop.title,
                    description=prop.description,
                    price=prop.price,
                    location=prop.location,
                    propertyType=prop.property_type,
                    status=prop.status,
                    bedrooms=prop.bedrooms,
                    bathrooms=prop.bathrooms,
                    area=prop.area,
                    yearBuilt=prop.year_built,
                    images=list(prop.images),
                    amenities=list(prop.amenities),
                    createdAt=prop.created_at,
                    updatedAt=prop.updated_at,
                    viewCount=prop.view_count,
                    latitude=prop.latitude,
                    longitude=prop.longitude,
                    address=prop.address,
                    city=prop.city,
                    state=prop.state,
                    country=prop.country,
                    zipCode=prop.zip_code,
                    isActive=prop.is_active
                )
                for prop in response.properties.properties
            ]
        except Exception as e:
            log_msg("error", f"Error searching properties: {str(e)}")
            raise REException(
                "PROPERTY_SEARCH_FAILED",
                "Failed to search properties",
                str(e)
            ).to_graphql_error()

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_property(
        self,
        userId: str,
        title: str,
        description: str,
        price: float,
        location: str,
        propertyType: PropertyType,
        status: PropertyStatus,
        bedrooms: int,
        bathrooms: int,
        area: float,
        yearBuilt: int,
        images: typing.List[str],
        amenities: typing.List[str],
        latitude: float,
        longitude: float,
        address: str,
        city: str,
        state: str,
        country: str,
        zipCode: str,
        isActive: bool = True
    ) -> Property:
        try:
            response = property_service_client.create_property(
                user_id=userId,
                title=title,
                description=description,
                price=price,
                location=location,
                property_type=propertyType.value,  # Convert enum to integer
                status=status.value,  # Convert enum to integer
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                area=area,
                year_built=yearBuilt,
                images=images,
                amenities=amenities,
                latitude=latitude,
                longitude=longitude,
                address=address,
                city=city,
                state=state,
                country=country,
                zip_code=zipCode,
                is_active=isActive
            )
            
            if not response.success:
                raise REException("PROPERTY_CREATION_FAILED", response.message, "Failed to create property")
            
            return Property(
                propertyId=response.property.property_id,
                userId=response.property.user_id,
                title=response.property.title,
                description=response.property.description,
                price=response.property.price,
                location=response.property.location,
                propertyType=PropertyType(response.property.property_type),  # Convert integer back to enum
                status=PropertyStatus(response.property.status),  # Convert integer back to enum
                bedrooms=response.property.bedrooms,
                bathrooms=response.property.bathrooms,
                area=response.property.area,
                yearBuilt=response.property.year_built,
                images=list(response.property.images),
                amenities=list(response.property.amenities),
                createdAt=response.property.created_at,
                updatedAt=response.property.updated_at,
                viewCount=response.property.view_count,
                latitude=response.property.latitude,
                longitude=response.property.longitude,
                address=response.property.address,
                city=response.property.city,
                state=response.property.state,
                country=response.property.country,
                zipCode=response.property.zip_code,
                isActive=response.property.is_active
            )
        except Exception as e:
            log_msg("error", f"Error creating property: {str(e)}")
            raise REException(
                "PROPERTY_CREATION_FAILED",
                "Failed to create property",
                str(e)
            ).to_graphql_error()

    @strawberry.mutation
    async def update_property(
        self,
        propertyId: str,
        title: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
        price: typing.Optional[float] = None,
        location: typing.Optional[str] = None,
        propertyType: typing.Optional[PropertyType] = None,
        status: typing.Optional[PropertyStatus] = None,
        bedrooms: typing.Optional[int] = None,
        bathrooms: typing.Optional[int] = None,
        area: typing.Optional[float] = None,
        yearBuilt: typing.Optional[int] = None,
        images: typing.Optional[typing.List[str]] = None,
        amenities: typing.Optional[typing.List[str]] = None,
        latitude: typing.Optional[float] = None,
        longitude: typing.Optional[float] = None,
        address: typing.Optional[str] = None,
        city: typing.Optional[str] = None,
        state: typing.Optional[str] = None,
        country: typing.Optional[str] = None,
        zipCode: typing.Optional[str] = None,
        isActive: typing.Optional[bool] = None
    ) -> Property:
        try:
            # Get current property first
            current = property_service_client.get_property(propertyId)
            if not current.success:
                raise REException("PROPERTY_NOT_FOUND", current.message, "Property not found")
            
            # Update with new values or keep current ones
            response = property_service_client.update_property(
                property_id=propertyId,
                title=title or current.property.title,
                description=description or current.property.description,
                price=price or current.property.price,
                location=location or current.property.location,
                property_type=propertyType if propertyType is not None else current.property.property_type,
                status=status if status is not None else current.property.status,
                bedrooms=bedrooms or current.property.bedrooms,
                bathrooms=bathrooms or current.property.bathrooms,
                area=area or current.property.area,
                year_built=yearBuilt or current.property.year_built,
                images=images or list(current.property.images),
                amenities=amenities or list(current.property.amenities),
                latitude=latitude or current.property.latitude,
                longitude=longitude or current.property.longitude,
                address=address or current.property.address,
                city=city or current.property.city,
                state=state or current.property.state,
                country=country or current.property.country,
                zip_code=zipCode or current.property.zip_code,
                is_active=isActive if isActive is not None else current.property.is_active
            )
            
            if not response.success:
                raise REException("PROPERTY_UPDATE_FAILED", response.message, "Failed to update property")
            
            return Property(
                propertyId=response.property.property_id,
                userId=response.property.user_id,
                title=response.property.title,
                description=response.property.description,
                price=response.property.price,
                location=response.property.location,
                propertyType=response.property.property_type,
                status=response.property.status,
                bedrooms=response.property.bedrooms,
                bathrooms=response.property.bathrooms,
                area=response.property.area,
                yearBuilt=response.property.year_built,
                images=list(response.property.images),
                amenities=list(response.property.amenities),
                createdAt=response.property.created_at,
                updatedAt=response.property.updated_at,
                viewCount=response.property.view_count,
                latitude=response.property.latitude,
                longitude=response.property.longitude,
                address=response.property.address,
                city=response.property.city,
                state=response.property.state,
                country=response.property.country,
                zipCode=response.property.zip_code,
                isActive=response.property.is_active
            )
        except Exception as e:
            log_msg("error", f"Error updating property: {str(e)}")
            raise REException(
                "PROPERTY_UPDATE_FAILED",
                "Failed to update property",
                str(e)
            ).to_graphql_error()

    @strawberry.mutation
    async def delete_property(self, propertyId: str) -> bool:
        try:
            response = property_service_client.delete_property(propertyId)
            if not response.success:
                raise REException("PROPERTY_DELETION_FAILED", response.message, "Failed to delete property")
            return True
        except Exception as e:
            log_msg("error", f"Error deleting property: {str(e)}")
            raise REException(
                "PROPERTY_DELETION_FAILED",
                "Failed to delete property",
                str(e)
            ).to_graphql_error()

    @strawberry.mutation
    async def increment_view_count(self, propertyId: str) -> Property:
        try:
            response = property_service_client.increment_view_count(propertyId)
            if not response.success:
                raise REException("VIEW_COUNT_UPDATE_FAILED", response.message, "Failed to update view count")
            
            return Property(
                propertyId=response.property.property_id,
                userId=response.property.user_id,
                title=response.property.title,
                description=response.property.description,
                price=response.property.price,
                location=response.property.location,
                propertyType=response.property.property_type,
                status=response.property.status,
                bedrooms=response.property.bedrooms,
                bathrooms=response.property.bathrooms,
                area=response.property.area,
                yearBuilt=response.property.year_built,
                images=list(response.property.images),
                amenities=list(response.property.amenities),
                createdAt=response.property.created_at,
                updatedAt=response.property.updated_at,
                viewCount=response.property.view_count,
                latitude=response.property.latitude,
                longitude=response.property.longitude,
                address=response.property.address,
                city=response.property.city,
                state=response.property.state,
                country=response.property.country,
                zipCode=response.property.zip_code,
                isActive=response.property.is_active
            )
        except Exception as e:
            log_msg("error", f"Error incrementing view count: {str(e)}")
            raise REException(
                "VIEW_COUNT_UPDATE_FAILED",
                "Failed to increment view count",
                str(e)
            ).to_graphql_error() 