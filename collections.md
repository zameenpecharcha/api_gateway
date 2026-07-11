# API Collections

This document contains all the API endpoints organized by service. Each request includes a cURL command that can be imported into Postman.

## Auth Service Collection

### 1. Login
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation Login { login(email: \"user@example.com\", password: \"yourpassword\") { success token refreshToken message userInfo { id firstName lastName email phone profilePhoto role address latitude longitude bio isactive emailVerified phoneVerified createdAt } } }"
}'
```

Example Response:
```json
{
  "data": {
    "login": {
      "success": true,
      "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "message": "Login successful",
      "userInfo": {
        "id": 1,
        "firstName": "John",
        "lastName": "Doe",
        "email": "user@example.com",
        "phone": "+1234567890",
        "profilePhoto": null,
        "role": "user",
        "address": "123 Main St",
        "latitude": 12.345678,
        "longitude": 45.678901,
        "bio": "Software Developer",
        "isactive": true,
        "emailVerified": true,
        "phoneVerified": false,
        "createdAt": "2024-02-26T12:00:00Z"
      }
    }
  }
}
```

### 2. Send OTP

a) For Email Verification:
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation SendVerificationOTP { sendOtp(email: \"user@example.com\", type: VERIFICATION) { success message channels } }"
}'
```

b) For Password Reset:
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation SendPasswordResetOTP { sendOtp(email: \"user@example.com\", type: PASSWORD_RESET) { success message channels } }"
}'
```

c) For Login OTP:
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation SendLoginOTP { sendOtp(email: \"user@example.com\", type: LOGIN) { success message channels } }"
}'
```

Example Response:
```json
{
  "data": {
    "sendOtp": {
      "success": true,
      "message": "OTP sent successfully via email",
      "channels": ["email"]
    }
  }
}
```

### 3. Verify OTP

a) Verify Email:
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation VerifyEmailOTP { verifyOtp(email: \"user@example.com\", otpCode: \"123456\", type: VERIFICATION) { success message userInfo { email emailVerified } } }"
}'
```

b) Verify Password Reset OTP:
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation VerifyPasswordResetOTP { verifyOtp(email: \"user@example.com\", otpCode: \"123456\", type: PASSWORD_RESET) { success message userInfo { email emailVerified } } }"
}'
```

c) Verify Login OTP:
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation VerifyLoginOTP { verifyOtp(email: \"user@example.com\", otpCode: \"123456\", type: LOGIN) { success token message userInfo { id email emailVerified } } }"
}'
```

Example Response:
```json
{
  "data": {
    "verifyOtp": {
      "success": true,
      "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "message": "OTP verified successfully",
      "userInfo": {
        "id": 1,
        "email": "user@example.com",
        "emailVerified": true
      }
    }
  }
}
```

### 4. Password Reset Flow

1. Request Password Reset OTP:
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation RequestPasswordReset { sendOtp(email: \"user@example.com\", type: PASSWORD_RESET) { success message channels } }"
}'
```

2. Reset Password with OTP:
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation ResetPassword { resetPassword(email: \"user@example.com\", otpCode: \"123456\", newPassword: \"newSecurePassword123\", confirmPassword: \"newSecurePassword123\") { success message userInfo { email emailVerified } } }"
}'
```

Example Response:
```json
{
  "data": {
    "resetPassword": {
      "success": true,
      "message": "Password reset successful",
      "userInfo": {
        "email": "user@example.com",
        "emailVerified": true
      }
    }
  }
}
```

### Error Responses

1. User Not Found:
```json
{
  "errors": [{
    "message": "User not found",
    "path": ["sendOtp"]
  }]
}
```

2. Invalid OTP:
```json
{
  "errors": [{
    "message": "Invalid OTP",
    "path": ["verifyOtp"]
  }]
}
```

3. OTP Expired:
```json
{
  "errors": [{
    "message": "OTP expired or not found",
    "path": ["verifyOtp"]
  }]
}
```

4. Invalid Credentials:
```json
{
  "errors": [{
    "message": "Invalid credentials",
    "path": ["login"]
  }]
}
```

5. Password Mismatch:
```json
{
  "errors": [{
    "message": "Passwords do not match",
    "path": ["resetPassword"]
  }]
}
```

## User Service Collection

### 1. Create User
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation CreateUser { createUser(firstName: \"John\", lastName: \"Doe\", email: \"john@example.com\", phone: \"+1234567890\", password: \"securepassword123\", role: \"user\", address: \"123 Main St\", latitude: 12.345678, longitude: 45.678901, bio: \"Software Developer\") { id firstName lastName email phone profilePhoto role address latitude longitude bio isactive emailVerified phoneVerified createdAt } }"
}'
```

Example Response:
```json
{
  "data": {
    "createUser": {
      "id": 1,
      "firstName": "John",
      "lastName": "Doe",
      "email": "john@example.com",
      "phone": "+1234567890",
      "profilePhoto": null,
      "role": "user",
      "address": "123 Main St",
      "latitude": 12.345678,
      "longitude": 45.678901,
      "bio": "Software Developer",
      "isactive": true,
      "emailVerified": false,
      "phoneVerified": false,
      "createdAt": "2024-02-26T12:00:00Z"
    }
  }
}
```

### 2. Get User
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "query GetUser { user(id: 1) { id firstName lastName email phone profilePhoto role address latitude longitude bio isactive emailVerified phoneVerified createdAt ratings { id ratedUserId ratedByUserId ratingValue review ratingType createdAt updatedAt } followersCount followingCount } }"
}'
```

Example Response:
```json
{
  "data": {
    "user": {
      "id": 1,
      "firstName": "John",
      "lastName": "Doe",
      "email": "john@example.com",
      "phone": "+1234567890",
      "profilePhoto": null,
      "role": "user",
      "address": "123 Main St",
      "latitude": 12.345678,
      "longitude": 45.678901,
      "bio": "Software Developer",
      "isactive": true,
      "emailVerified": false,
      "phoneVerified": false,
      "createdAt": "2024-02-26T12:00:00Z",
      "ratings": [],
      "followersCount": 0,
      "followingCount": 0
    }
  }
}
```

### 3. Create User Rating
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation CreateUserRating { createUserRating(ratedUserId: 2, ratedByUserId: 1, ratingValue: 5, title: \"Great experience\", review: \"Excellent service!\", ratingType: \"PROFESSIONAL\", isAnonymous: false) { id ratedUserId ratedByUserId ratingValue review ratingType createdAt updatedAt } }"
}'
```

Example Response:
```json
{
  "data": {
    "createUserRating": {
      "id": 1,
      "ratedUserId": 2,
      "ratedByUserId": 1,
      "ratingValue": 5,
      "review": "Excellent service!",
      "ratingType": "PROFESSIONAL",
      "createdAt": "2024-02-26T12:00:00Z",
      "updatedAt": "2024-02-26T12:00:00Z"
    }
  }
}
```

### 4. Get User Ratings
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "query GetUserRatings { userRatings(userId: 1) { id ratedUserId ratedByUserId ratingValue review ratingType createdAt updatedAt } }"
}'
```

### 5. Follow User
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation FollowUser { followUser(userId: 1, followingId: 2) { id userId followingId status followedAt } }"
}'
```

### 6. Get User Followers
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "query GetUserFollowers { userFollowers(userId: 1) { id userId followingId status followedAt } }"
}'
```

### 7. Get User Following
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "query GetUserFollowing { userFollowing(userId: 1) { id userId followingId status followedAt } }"
}'
```

### 8. Check Following Status
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "query CheckFollowingStatus { checkFollowingStatus(userId: 1, followingId: 2) { id userId followingId status followedAt } }"
}'
```

### 9. Update Profile Photo
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation UpdateProfilePhoto($userId:Int!, $filePath:String!, $file:String, $ctype:String) { updateProfilePhoto(userId:$userId, filePath:$filePath, fileName:$file, contentType:$ctype, caption:\"Profile picture\") { id firstName lastName email createdAt } }",
  "variables": {
    "userId": 1,
    "filePath": "C:/path/to/profile.jpg",
    "file": "profile.jpg",
    "ctype": "image/jpeg"
  }
}'
```

### 10. Update Cover Photo
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation UpdateCoverPhoto($userId:Int!, $filePath:String!, $file:String, $ctype:String) { updateCoverPhoto(userId:$userId, filePath:$filePath, fileName:$file, contentType:$ctype, caption:\"Cover photo\") { id firstName lastName email createdAt } }",
  "variables": {
    "userId": 1,
    "filePath": "C:/path/to/cover.jpg",
    "file": "cover.jpg",
    "ctype": "image/jpeg"
  }
}'
```

## Comments Service Collection

### Create Comment
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation { createComment(postId: \"5401108a-e58f-4c26-9938-bde0984fb18e\", userId: \"bc90e095-837e-40f7-9226-a1fa587626eb\", content: \"Hello\") { commentId postId userId content createdAt updatedAt likeCount } }"
}'
```

### Get Comment
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "query { comment(commentId: \"b529ea5d-0410-48cb-813a-1a25d43b6a2c\") { commentId postId userId content parentCommentId createdAt updatedAt likeCount } }"
}'
```

### Get Comments by Post
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "query { commentsByPost(postId: \"5401108a-e58f-4c26-9938-bde0984fb18e\") { commentId postId userId content parentCommentId createdAt updatedAt likeCount } }"
}'
```

### Get Comment Replies
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "query { commentReplies(commentId: \"b529ea5d-0410-48cb-813a-1a25d43b6a2c\") { commentId postId userId content parentCommentId createdAt updatedAt likeCount } }"
}'
```

### Update Comment
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation { updateComment(commentId: \"b529ea5d-0410-48cb-813a-1a25d43b6a2c\", content: \"Updated content\") { commentId content updatedAt } }"
}'
```

### Delete Comment
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation { deleteComment(commentId: \"b529ea5d-0410-48cb-813a-1a25d43b6a2c\") }"
}'
```

### Like Comment
```bash
curl -X POST http://localhost:8000/api/v1/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation { likeComment(commentId: \"b529ea5d-0410-48cb-813a-1a25d43b6a2c\", userId: \"bc90e095-837e-40f7-9226-a1fa587626eb\") { commentId likeCount } }"
}'
```

### Unlike Comment
```bash
curl -X POST http://localhost:8000/api/v1/comments/graphql \
-H "Content-Type: application/json" \
-d '{
  "query": "mutation { unlikeComment(commentId: \"b529ea5d-0410-48cb-813a-1a25d43b6a2c\", userId: \"bc90e095-837e-40f7-9226-a1fa587626eb\") { commentId likeCount } }"
}'
```

# Posts Service Collection

## Queries

### Get Single Post
```graphql
query {
  post(postId: 1) {
    id
    userId
    title
    content
    visibility
    propertyType
    location
    latitude
    longitude
    price
    status
    createdAt
    media {
      id
      mediaType
      mediaUrl
      mediaOrder
      caption
    }
    likeCount
    commentCount
  }
}
```

### Get Posts by User
```graphql
query {
  postsByUser(userId: 2, page: 1, limit: 10) {
    id
    title
    content
    visibility
    propertyType
    location
    latitude
    longitude
    price
    status
    createdAt
    media {
      mediaUrl
      caption
    }
    likeCount
    commentCount
  }
}
```

### Search Posts
```graphql
query {
  searchPosts(
    propertyType: "house"
    location: "New York"
    minPrice: 100000
    maxPrice: 500000
    status: "active"
    page: 1
    limit: 10
  ) {
    id
    title
    propertyType
    location
    price
    status
    media {
      mediaUrl
    }
  }
}
```

### Get Post Comments
```graphql
query {
  postComments(postId: 1, page: 1, limit: 10) {
    id
    postId
    userId
    comment
    parentCommentId
    status
    addedAt
    commentedAt
    replies {
      id
      comment
    }
    likeCount
  }
}
```

## Mutations

### Create Post
```graphql
mutation {
  createPost(
    userId: 2
    title: "Beautiful House for Sale"
    content: "3 bedroom house with garden"
    visibility: "public"
    propertyType: "house"
    location: "New York"
    latitude: 40.7128,
    longitude: -74.0060
    price: 500000.0
    status: "active"
    media: [
      {
        mediaType: "image"
        mediaData: "<base64 bytes>"
        mediaOrder: 1
        caption: "Front view"
      }
    ]
  ) {
    success
    message
    post {
      id
      title
      media {
        id
        mediaUrl
        caption
      }
    }
  }
}
```

Response:
```json
{
  "data": {
    "createPost": {
      "success": true,
      "message": "Post created successfully",
      "post": {
        "id": 1,
        "title": "Beautiful House for Sale",
        "media": [
          {
            "id": 1,
            "mediaUrl": "https://<bucket>.s3.<region>.amazonaws.com/post/1/1/front.jpg",
            "caption": "Front view"
          }
        ]
      }
    }
  }
}
```

### Update Post
```graphql
mutation {
  updatePost(
    postId: 1
    title: "Updated House Title"
    price: 550000.0
    status: "pending"
  ) {
    success
    message
    post {
      id
      title
      price
      status
      createdAt
    }
  }
}
```

### Delete Post
```graphql
mutation {
  deletePost(postId: 1) {
    success
    message
  }
}
```

### Add Media to Post
```graphql
mutation {
  addPostMedia(
    postId: 1
    media: [
      {
        mediaType: "image"
        mediaData: "base64_encoded_image_data"
        mediaOrder: 2
        caption: "Garden view"
      }
    ]
  ) {
    success
    message
    post {
      id
      media {
        id
        mediaUrl
        caption
      }
    }
  }
}
```

### Delete Media
```graphql
mutation {
  deletePostMedia(mediaId: 1) {
    success
    message
  }
}
```

### Like/Unlike Post
```graphql
mutation {
  likePost(postId: 1, userId: 2) {
    success
    message
    post {
      id
      likeCount
    }
  }
}

mutation {
  unlikePost(postId: 1, userId: 2) {
    success
    message
    post {
      id
      likeCount
    }
  }
}
```

### Create Comment
```graphql
# Create top-level comment
mutation {
  createComment(
    postId: 1
    userId: 2
    comment: "Great property!"
  ) {
    success
    message
    comment {
      id
      comment
      addedAt
      likeCount
    }
  }
}

# Create reply to a comment
mutation {
  createComment(
    postId: 1
    userId: 2
    comment: "Thanks for your feedback!"
    parentCommentId: 1
  ) {
    success
    message
    comment {
      id
      parentCommentId
      comment
      addedAt
    }
  }
}
```

### Update Comment
```graphql
mutation {
  updateComment(
    commentId: 1
    comment: "Updated comment text"
  ) {
    success
    message
    comment {
      id
      comment
      commentedAt
    }
  }
}
```

### Delete Comment
```graphql
mutation {
  deleteComment(commentId: 1) {
    success
    message
  }
}
```

### Like/Unlike Comment
```graphql
mutation {
  likeComment(commentId: 1, userId: 2) {
    success
    message
    comment {
      id
      likeCount
    }
  }
}

mutation {
  unlikeComment(commentId: 1, userId: 2) {
    success
    message
    comment {
      id
      likeCount
    }
  }
}
```

## Error Responses

Posts service can return the following error types:

1. Not Found (404):
```json
{
  "data": null,
  "errors": [
    {
      "message": "Post not found",
      "path": ["post"]
    }
  ]
}
```

2. Validation Error (400):
```json
{
  "data": null,
  "errors": [
    {
      "message": "Invalid input: price must be greater than 0",
      "path": ["createPost"]
    }
  ]
}
```

3. Authorization Error (401/403):
```json
{
  "data": null,
  "errors": [
    {
      "message": "User not authorized to perform this action",
      "path": ["updatePost"]
    }
  ]
}
```

4. Media Error:
```json
{
  "data": null,
  "errors": [
    {
      "message": "Invalid media data format",
      "path": ["createPost"]
    }
  ]
}
```

5. Comment Error:
```json
{
  "data": null,
  "errors": [
    {
      "message": "Parent comment not found",
      "path": ["createComment"]
    }
  ]
}
```

## Property Service Collection

### Authorization Header

All requests require this header:

```
Authorization: Bearer <JWT>
```

### Create Property
```graphql
mutation CreateProperty(
  $userId: String!, $title: String!, $description: String!,
  $price: Float!, $location: String!, $propertyType: PropertyType!, $status: PropertyStatus!,
  $bedrooms: Int!, $bathrooms: Int!, $area: Float!, $yearBuilt: Int!,
  $images: [String!]!, $amenities: [String!]!,
  $latitude: Float!, $longitude: Float!, $address: String!,
  $city: String!, $state: String!, $country: String!, $zipCode: String!
) {
  createProperty(
    userId: $userId, title: $title, description: $description,
    price: $price, location: $location, propertyType: $propertyType, status: $status,
    bedrooms: $bedrooms, bathrooms: $bathrooms, area: $area, yearBuilt: $yearBuilt,
    images: $images, amenities: $amenities,
    latitude: $latitude, longitude: $longitude, address: $address,
    city: $city, state: $state, country: $country, zipCode: $zipCode,
    isActive: true
  ) { propertyId title price city state country }
}
```
Variables:
```json
{
  "userId": "1",
  "title": "2 BHK Apartment",
  "description": "Nice flat",
  "price": 7500000,
  "location": "Noida",
  "propertyType": "APARTMENT",
  "status": "ACTIVE",
  "bedrooms": 2,
  "bathrooms": 2,
  "area": 1200,
  "yearBuilt": 2018,
  "images": [],
  "amenities": [],
  "latitude": 28.614,
  "longitude": 77.362,
  "address": "Sector 62",
  "city": "Noida",
  "state": "UP",
  "country": "India",
  "zipCode": "201301"
}
```

### Get Property
```graphql
query GetProperty($id: String!) {
  property(propertyId: $id) {
    propertyId title description price location
    propertyType status bedrooms bathrooms area yearBuilt
    images amenities latitude longitude address city state country zipCode
    createdAt updatedAt viewCount isActive coverPhotoId profilePhotoId
  }
}
```
Variables:
```json
{ "id": "6" }
```

### Search Properties
```graphql
query SearchProperties(
  $query:String, $propertyType:PropertyType, $minPrice:Float, $maxPrice:Float,
  $location:String, $minBedrooms:Int, $minBathrooms:Int, $minArea:Float, $maxArea:Float
) {
  searchProperties(
    query:$query, propertyType:$propertyType, minPrice:$minPrice, maxPrice:$maxPrice,
    location:$location, minBedrooms:$minBedrooms, minBathrooms:$minBathrooms,
    minArea:$minArea, maxArea:$maxArea
  ) {
    propertyId title price city state
  }
}
```
Variables:
```json
{ "location": "Noida" }
```

### Update Property
```graphql
mutation UpdateProperty($id:String!, $title:String, $price:Float, $status:PropertyStatus) {
  updateProperty(propertyId:$id, title:$title, price:$price, status:$status) {
    propertyId title price status
  }
}
```
Variables:
```json
{ "id":"5", "title":"Updated Title", "price":7999999, "status":"ACTIVE" }
```

### Delete Property
```graphql
mutation DeleteProperty($id:String!) { deleteProperty(propertyId:$id) }
```
Variables:
```json
{ "id":"6" }
```

### Increment View Count
```graphql
mutation IncViews($id: String!) {
  incrementViewCount(propertyId: $id) {
    propertyId
    viewCount
    title
  }
}
```
Variables:
```json
{ "id":"5" }
```

### Rate Property
```graphql
mutation RateProperty(
  $propertyId: Int!
  $ratedBy: Int!
  $value: Int!
  $title: String
  $review: String
  $ratingType: String
  $isAnonymous: Boolean
) {
  createPropertyRating(
    propertyId: $propertyId
    ratedByUserId: $ratedBy
    ratingValue: $value
    title: $title
    review: $review
    ratingType: $ratingType
    isAnonymous: $isAnonymous
  ) {
    id propertyId ratedByUserId ratingValue title review
  }
}
```
Variables:
```json
{
  "propertyId": 5,
  "ratedBy": 4,
  "value": 5,
  "title": "Great",
  "review": "Nice project",
  "ratingType": "quality",
  "isAnonymous": false
}
```

### Property Ratings
```graphql
query PropertyRatings($propertyId:Int!) {
  propertyRatings(propertyId:$propertyId) {
    id propertyId ratedByUserId ratingValue title review ratingType isAnonymous createdAt updatedAt
  }
}
```
Variables:
```json
{ "propertyId": 6 }
```

### Property Followers
```graphql
query PropertyFollowers($propertyId:Int!) {
  propertyFollowers(propertyId:$propertyId) {
    id userId propertyId status followedAt
  }
}
```
Variables:
```json
{ "propertyId": 3 }
```

### Follow Property
```graphql
mutation FollowProperty($userId:Int!, $propertyId:Int!, $status:String) {
  followProperty(userId:$userId, propertyId:$propertyId, status:$status) {
    id userId propertyId status followedAt
  }
}
```
Variables:
```json
{ "userId":4, "propertyId":5, "status":"active" }
```

### Add Property Media
```graphql
mutation AddPropertyMedia($propertyId:Int!, $media:[PropertyMediaInput!]!) {
  addPropertyMedia(propertyId:$propertyId, media:$media) {
    success
    message
    media { id propertyId mediaUrl mediaType mediaOrder caption uploadedAt }
  }
}
```
Variables:
```json
{
  "propertyId":5,
  "media":[
    { "filePath":"C:/Users/ram91/Downloads/photo.jpg", "mediaType":"image", "mediaOrder":1, "caption":"Front", "contentType":"image/jpeg" }
  ]
}
```

### Update Property Profile Photo
```graphql
mutation UpdatePropertyProfilePhoto($propertyId:Int!, $media:PropertyMediaInput!) {
  updatePropertyProfilePhoto(propertyId:$propertyId, media:$media) {
    propertyId
    title
    coverPhotoId
    profilePhotoId
    updatedAt
  }
}
```
Variables:
```json
{
  "propertyId": 5,
  "media": {
    "filePath": "C:/Users/ram91/Downloads/photo.jpg",
    "mediaType": "image",
    "mediaOrder": 1,
    "caption": "profile photo",
    "contentType": "image/jpeg"
  }
}
```

### Update Property Cover Photo
```graphql
mutation UpdatePropertyCoverPhoto($propertyId:Int!, $media:PropertyMediaInput!) {
  updatePropertyCoverPhoto(propertyId:$propertyId, media:$media) {
    propertyId
    title
    coverPhotoId
    profilePhotoId
    updatedAt
  }
}
```
Variables:
```json
{
  "propertyId": 5,
  "media": {
    "filePath": "C:/Users/ram91/Downloads/photo.jpg",
    "mediaType": "image",
    "mediaOrder": 1,
    "caption": "Cover",
    "contentType": "image/jpeg"
  }
}
```

## Ola API

```graphql
query {
  olaAutocomplete(input: "srouthy krupa chikkad") {
    reference
    placeId
    description
    lat
    lng
    types
  }
}
```
### Create Property
```