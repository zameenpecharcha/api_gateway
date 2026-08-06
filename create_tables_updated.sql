-- =============================================================================
-- ZPC Platform — Microservices Database Schema (PostgreSQL)
-- File: create_tables_updated.sql
--
-- One physical database; logical isolation via PostgreSQL schemas per service.
-- Schemas are added incrementally. Currently implemented:
--   • user   — users, followers, user_ratings
--   • post      — posts, comments, post_likes, post_shares, comment_likes
--   • property  — properties, property_features, property_ratings, property_views,
--                 saved_properties, property_documents
--   • auth        — auth_users
--   • api_gateway — reports, media
--
-- Upcoming (to be added in follow-up revisions):
--   • chat, ...
--
-- Temporal columns: all use TIMESTAMPTZ (timestamp with time zone).
-- Audit columns created_at / updated_at default to CURRENT_TIMESTAMP.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Extensions
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- Service schemas
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS "user";
CREATE SCHEMA IF NOT EXISTS "post";
CREATE SCHEMA IF NOT EXISTS "property";
CREATE SCHEMA IF NOT EXISTS "auth";
CREATE SCHEMA IF NOT EXISTS api_gateway;

-- =============================================================================
-- USER SCHEMA
-- =============================================================================

-- -----------------------------------------------------------------------------
-- user.users
-- Core user profile and aggregate counters (credentials live in auth schema).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "user".users (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_code           VARCHAR(30)     NOT NULL,
    first_name          VARCHAR(100),
    last_name           VARCHAR(100),
    email               VARCHAR(255)    NOT NULL,
    phone               VARCHAR(30),
    role                VARCHAR(30)     NOT NULL DEFAULT 'USER',
    bio                 TEXT,
    profile_photo_id    UUID,
    cover_photo_id      UUID,
    latitude            DECIMAL(10, 7),
    longitude           DECIMAL(10, 7),
    report_count        INT             NOT NULL DEFAULT 0,
    average_rating      DECIMAL(3, 2)   NOT NULL DEFAULT 0,
    rating_count        INT             NOT NULL DEFAULT 0,
    follower_count      INT             NOT NULL DEFAULT 0,
    following_count     INT             NOT NULL DEFAULT 0,
    post_count          INT             NOT NULL DEFAULT 0,
    property_count      INT             NOT NULL DEFAULT 0,
    review_count        INT             NOT NULL DEFAULT 0,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    email_verified      BOOLEAN         NOT NULL DEFAULT FALSE,
    phone_verified      BOOLEAN         NOT NULL DEFAULT FALSE,
    last_login_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ     DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMPTZ,

    CONSTRAINT users_user_code_unique UNIQUE (user_code),
    CONSTRAINT users_email_unique UNIQUE (email),
    CONSTRAINT users_phone_unique UNIQUE (phone),
    CONSTRAINT users_average_rating_range CHECK (average_rating >= 0 AND average_rating <= 5),
    CONSTRAINT users_rating_count_non_negative CHECK (rating_count >= 0),
    CONSTRAINT users_follower_count_non_negative CHECK (follower_count >= 0),
    CONSTRAINT users_following_count_non_negative CHECK (following_count >= 0),
    CONSTRAINT users_post_count_non_negative CHECK (post_count >= 0),
    CONSTRAINT users_property_count_non_negative CHECK (property_count >= 0),
    CONSTRAINT users_review_count_non_negative CHECK (review_count >= 0),
    CONSTRAINT users_report_count_non_negative CHECK (report_count >= 0),
    CONSTRAINT users_role_valid
        CHECK (role IN ('USER', 'BUILDER', 'AGENT', 'ADMIN', 'LAWYER', 'INVESTOR'))
);

COMMENT ON TABLE "user".users IS 'User profiles and denormalized counters; owned by user_service.';
COMMENT ON COLUMN "user".users.role IS 'User role: USER, BUILDER, AGENT, ADMIN, LAWYER, INVESTOR.';
COMMENT ON COLUMN "user".users.profile_photo_id IS 'FK → api_gateway.media(id).';
COMMENT ON COLUMN "user".users.cover_photo_id IS 'FK → api_gateway.media(id).';
COMMENT ON COLUMN "user".users.deleted_at IS 'Soft-delete timestamp; NULL means active.';

-- -----------------------------------------------------------------------------
-- user.followers
-- User-to-user follow relationships.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "user".followers (
    id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    follower_id             UUID            NOT NULL,
    following_id            UUID            NOT NULL,
    follow_type             VARCHAR(20)     NOT NULL DEFAULT 'USER',
    status                  VARCHAR(20)     NOT NULL DEFAULT 'ACTIVE',
    notification_enabled    BOOLEAN         NOT NULL DEFAULT TRUE,
    followed_at             TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMPTZ     DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_followers_follower
        FOREIGN KEY (follower_id) REFERENCES "user".users (id) ON DELETE CASCADE,
    CONSTRAINT fk_followers_following
        FOREIGN KEY (following_id) REFERENCES "user".users (id) ON DELETE CASCADE,
    CONSTRAINT followers_no_self_follow CHECK (follower_id <> following_id),
    CONSTRAINT followers_pair_unique UNIQUE (follower_id, following_id),
    CONSTRAINT followers_follow_type_valid
        CHECK (follow_type IN ('USER', 'BUILDER', 'AGENT','LAWYER','INVESTOR')),
    CONSTRAINT followers_status_valid
        CHECK (status IN ('ACTIVE', 'BLOCKED', 'UNFOLLOWED'))
);

COMMENT ON TABLE "user".followers IS 'Directed follow edges between users; owned by user_service.';
COMMENT ON COLUMN "user".followers.follow_type IS 'Type of follow: USER, BUILDER, AGENT.';
COMMENT ON COLUMN "user".followers.status IS 'Follow status: ACTIVE, BLOCKED, UNFOLLOWED.';

-- -----------------------------------------------------------------------------
-- user.user_ratings
-- Ratings and reviews given to users.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "user".user_ratings (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    rated_user_id   UUID            NOT NULL,
    rated_by        UUID            NOT NULL,
    rating_value    DECIMAL(2, 1)   NOT NULL,
    title           VARCHAR(255),
    review          TEXT,
    rating_type     VARCHAR(30)     NOT NULL DEFAULT 'GENERAL',
    is_anonymous    BOOLEAN         NOT NULL DEFAULT FALSE,
    status          VARCHAR(30)     NOT NULL DEFAULT 'ACTIVE',
    created_at      TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ     DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_user_ratings_rated_user
        FOREIGN KEY (rated_user_id) REFERENCES "user".users (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_ratings_rated_by
        FOREIGN KEY (rated_by) REFERENCES "user".users (id) ON DELETE CASCADE,
    CONSTRAINT user_ratings_no_self_rating CHECK (rated_user_id <> rated_by),
    CONSTRAINT user_ratings_value_range
        CHECK (rating_value >= 1.0 AND rating_value <= 5.0),
    CONSTRAINT user_ratings_rating_type_valid
        CHECK (rating_type IN ('BUILDER', 'AGENT', 'SELLER', 'GENERAL')),
    CONSTRAINT user_ratings_status_valid
        CHECK (status IN ('ACTIVE', 'HIDDEN', 'DELETED')),
    CONSTRAINT user_ratings_pair_unique UNIQUE (rated_user_id, rated_by)
);

COMMENT ON TABLE "user".user_ratings IS 'Peer ratings for users; owned by user_service.';
COMMENT ON COLUMN "user".user_ratings.rating_value IS 'Rating score from 1.0 to 5.0.';
COMMENT ON COLUMN "user".user_ratings.rating_type IS 'Rating category: BUILDER, AGENT, SELLER, GENERAL.';
COMMENT ON COLUMN "user".user_ratings.status IS 'Rating visibility: ACTIVE, HIDDEN, DELETED.';

-- -----------------------------------------------------------------------------
-- Indexes — user schema
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_users_email ON "user".users (email);
CREATE INDEX IF NOT EXISTS idx_users_phone ON "user".users (phone);
CREATE INDEX IF NOT EXISTS idx_users_user_code ON "user".users (user_code);
CREATE INDEX IF NOT EXISTS idx_users_role ON "user".users (role);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON "user".users (is_active) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_created_at ON "user".users (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_followers_follower_id ON "user".followers (follower_id);
CREATE INDEX IF NOT EXISTS idx_followers_following_id ON "user".followers (following_id);
CREATE INDEX IF NOT EXISTS idx_followers_status ON "user".followers (status);

CREATE INDEX IF NOT EXISTS idx_user_ratings_rated_user_id ON "user".user_ratings (rated_user_id);
CREATE INDEX IF NOT EXISTS idx_user_ratings_rated_by ON "user".user_ratings (rated_by);
CREATE INDEX IF NOT EXISTS idx_user_ratings_status ON "user".user_ratings (status);

-- =============================================================================
-- END USER SCHEMA
-- =============================================================================

-- =============================================================================
-- POST SCHEMA
-- =============================================================================

-- -----------------------------------------------------------------------------
-- post.posts
-- Feed / listing posts (may optionally link to a property listing).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "post".posts (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    post_code           VARCHAR(30)     NOT NULL,
    user_id             UUID            NOT NULL,
    title               VARCHAR(255),
    content             TEXT,
    post_type           VARCHAR(30)     NOT NULL DEFAULT 'TEXT',
    property_id         UUID,
    visibility          VARCHAR(30)     NOT NULL DEFAULT 'PUBLIC',
    location            VARCHAR(255),
    latitude            DECIMAL(10, 7),
    longitude           DECIMAL(10, 7),
    price               DECIMAL(18, 2),
    currency            VARCHAR(10),
    is_anonymous        BOOLEAN         NOT NULL DEFAULT FALSE,
    allow_comments      BOOLEAN         NOT NULL DEFAULT TRUE,
    allow_share         BOOLEAN         NOT NULL DEFAULT TRUE,
    allow_reactions     BOOLEAN         NOT NULL DEFAULT TRUE,
    status              VARCHAR(30)     NOT NULL DEFAULT 'DRAFT',
    like_count          INT             NOT NULL DEFAULT 0,
    comment_count       INT             NOT NULL DEFAULT 0,
    share_count         INT             NOT NULL DEFAULT 0,
    view_count          BIGINT          NOT NULL DEFAULT 0,
    report_count        INT             NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ     DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMPTZ,

    CONSTRAINT posts_post_code_unique UNIQUE (post_code),
    CONSTRAINT fk_posts_user
        FOREIGN KEY (user_id) REFERENCES "user".users (id) ON DELETE CASCADE,
    CONSTRAINT posts_like_count_non_negative CHECK (like_count >= 0),
    CONSTRAINT posts_comment_count_non_negative CHECK (comment_count >= 0),
    CONSTRAINT posts_share_count_non_negative CHECK (share_count >= 0),
    CONSTRAINT posts_view_count_non_negative CHECK (view_count >= 0),
    CONSTRAINT posts_report_count_non_negative CHECK (report_count >= 0),
    CONSTRAINT posts_post_type_valid
        CHECK (post_type IN ('TEXT', 'IMAGE', 'VIDEO', 'PROPERTY', 'POLL', 'REVIEW')),
    CONSTRAINT posts_visibility_valid
        CHECK (visibility IN ('PUBLIC', 'FOLLOWERS_ONLY', 'PRIVATE')),
    CONSTRAINT posts_status_valid
        CHECK (status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED', 'DELETED'))
);

COMMENT ON TABLE "post".posts IS 'Social / property feed posts; owned by post_service.';
COMMENT ON COLUMN "post".posts.post_type IS 'Post format: TEXT, IMAGE, VIDEO, PROPERTY, POLL, REVIEW.';
COMMENT ON COLUMN "post".posts.visibility IS 'Audience: PUBLIC, FOLLOWERS_ONLY, PRIVATE.';
COMMENT ON COLUMN "post".posts.status IS 'Lifecycle: DRAFT, PUBLISHED, ARCHIVED, DELETED.';
COMMENT ON COLUMN "post".posts.property_id IS 'Optional link to property.properties (FK: fk_posts_property).';
COMMENT ON COLUMN "post".posts.deleted_at IS 'Soft-delete timestamp; NULL means active.';

-- -----------------------------------------------------------------------------
-- post.comments
-- Threaded comments on posts (self-referencing parent_comment_id).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "post".comments (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id             UUID            NOT NULL,
    parent_comment_id   UUID,
    user_id             UUID            NOT NULL,
    content             TEXT,
    is_anonymous        BOOLEAN         NOT NULL DEFAULT FALSE,
    like_count          INT             NOT NULL DEFAULT 0,
    reply_count         INT             NOT NULL DEFAULT 0,
    report_count        INT             NOT NULL DEFAULT 0,
    status              VARCHAR(30)     NOT NULL DEFAULT 'ACTIVE',
    created_at          TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ     DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMPTZ,

    CONSTRAINT fk_comments_post
        FOREIGN KEY (post_id) REFERENCES "post".posts (id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_parent
        FOREIGN KEY (parent_comment_id) REFERENCES "post".comments (id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_user
        FOREIGN KEY (user_id) REFERENCES "user".users (id) ON DELETE CASCADE,
    CONSTRAINT comments_like_count_non_negative CHECK (like_count >= 0),
    CONSTRAINT comments_reply_count_non_negative CHECK (reply_count >= 0),
    CONSTRAINT comments_report_count_non_negative CHECK (report_count >= 0),
    CONSTRAINT comments_valid_parent CHECK (parent_comment_id IS NULL OR parent_comment_id <> id),
    CONSTRAINT comments_status_valid
        CHECK (status IN ('ACTIVE', 'DELETED', 'HIDDEN'))
);

COMMENT ON TABLE "post".comments IS 'Comments and nested replies on posts; owned by post_service.';
COMMENT ON COLUMN "post".comments.status IS 'Lifecycle: ACTIVE, DELETED, HIDDEN.';

-- -----------------------------------------------------------------------------
-- post.post_likes
-- Reactions on posts.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "post".post_likes (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id         UUID            NOT NULL,
    user_id         UUID            NOT NULL,
    reaction_type   VARCHAR(20)     NOT NULL DEFAULT 'LIKE',
    created_at      TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_post_likes_post
        FOREIGN KEY (post_id) REFERENCES "post".posts (id) ON DELETE CASCADE,
    CONSTRAINT fk_post_likes_user
        FOREIGN KEY (user_id) REFERENCES "user".users (id) ON DELETE CASCADE,
    CONSTRAINT post_likes_pair_unique UNIQUE (post_id, user_id),
    CONSTRAINT post_likes_reaction_type_valid
        CHECK (reaction_type IN ('LIKE', 'LOVE', 'WOW', 'HAHA', 'SAD', 'ANGRY'))
);

COMMENT ON TABLE "post".post_likes IS 'Per-user reactions on posts; owned by post_service.';
COMMENT ON COLUMN "post".post_likes.reaction_type IS 'Reaction: LIKE, LOVE, WOW, HAHA, SAD, ANGRY.';

-- -----------------------------------------------------------------------------
-- post.post_shares
-- Share events for posts.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "post".post_shares (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    share_code      VARCHAR(30)     NOT NULL,
    post_id         UUID            NOT NULL,
    shared_by       UUID            NOT NULL,
    share_type      VARCHAR(20)     NOT NULL DEFAULT 'SHARE',
    caption         TEXT,
    visibility      VARCHAR(30)     NOT NULL DEFAULT 'PUBLIC',
    created_at      TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT post_shares_share_code_unique UNIQUE (share_code),
    CONSTRAINT fk_post_shares_post
        FOREIGN KEY (post_id) REFERENCES "post".posts (id) ON DELETE CASCADE,
    CONSTRAINT fk_post_shares_shared_by
        FOREIGN KEY (shared_by) REFERENCES "user".users (id) ON DELETE CASCADE,
    CONSTRAINT post_shares_share_type_valid
        CHECK (share_type IN ('REPOST', 'SHARE')),
    CONSTRAINT post_shares_visibility_valid
        CHECK (visibility IN ('PUBLIC', 'FOLLOWERS_ONLY', 'PRIVATE'))
);

COMMENT ON TABLE "post".post_shares IS 'Post share records; owned by post_service.';
COMMENT ON COLUMN "post".post_shares.share_type IS 'Share mode: REPOST, SHARE.';
COMMENT ON COLUMN "post".post_shares.visibility IS 'Audience: PUBLIC, FOLLOWERS_ONLY, PRIVATE.';

-- -----------------------------------------------------------------------------
-- post.comment_likes (comment_reactions)
-- Reactions on comments.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "post".comment_likes (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id      UUID            NOT NULL,
    user_id         UUID            NOT NULL,
    reaction_type   VARCHAR(20)     NOT NULL DEFAULT 'LIKE',
    created_at      TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_comment_likes_comment
        FOREIGN KEY (comment_id) REFERENCES "post".comments (id) ON DELETE CASCADE,
    CONSTRAINT fk_comment_likes_user
        FOREIGN KEY (user_id) REFERENCES "user".users (id) ON DELETE CASCADE,
    CONSTRAINT comment_likes_pair_unique UNIQUE (comment_id, user_id),
    CONSTRAINT comment_likes_reaction_type_valid
        CHECK (reaction_type IN ('LIKE', 'LOVE', 'WOW', 'HAHA'))
);

COMMENT ON TABLE "post".comment_likes IS 'Per-user reactions on comments (comment_reactions); owned by post_service.';
COMMENT ON COLUMN "post".comment_likes.reaction_type IS 'Reaction: LIKE, LOVE, WOW, HAHA.';

-- -----------------------------------------------------------------------------
-- Indexes — post schema
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_posts_user_id ON "post".posts (user_id);
CREATE INDEX IF NOT EXISTS idx_posts_post_code ON "post".posts (post_code);
CREATE INDEX IF NOT EXISTS idx_posts_post_type ON "post".posts (post_type);
CREATE INDEX IF NOT EXISTS idx_posts_property_id ON "post".posts (property_id) WHERE property_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_posts_status ON "post".posts (status);
CREATE INDEX IF NOT EXISTS idx_posts_visibility ON "post".posts (visibility);
CREATE INDEX IF NOT EXISTS idx_posts_created_at ON "post".posts (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_location ON "post".posts (location);
CREATE INDEX IF NOT EXISTS idx_posts_active ON "post".posts (is_anonymous, status) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_comments_post_id ON "post".comments (post_id);
CREATE INDEX IF NOT EXISTS idx_comments_user_id ON "post".comments (user_id);
CREATE INDEX IF NOT EXISTS idx_comments_parent_comment_id ON "post".comments (parent_comment_id);
CREATE INDEX IF NOT EXISTS idx_comments_status ON "post".comments (status);
CREATE INDEX IF NOT EXISTS idx_comments_created_at ON "post".comments (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_post_likes_post_id ON "post".post_likes (post_id);
CREATE INDEX IF NOT EXISTS idx_post_likes_user_id ON "post".post_likes (user_id);

CREATE INDEX IF NOT EXISTS idx_post_shares_post_id ON "post".post_shares (post_id);
CREATE INDEX IF NOT EXISTS idx_post_shares_shared_by ON "post".post_shares (shared_by);
CREATE INDEX IF NOT EXISTS idx_post_shares_share_code ON "post".post_shares (share_code);

CREATE INDEX IF NOT EXISTS idx_comment_likes_comment_id ON "post".comment_likes (comment_id);
CREATE INDEX IF NOT EXISTS idx_comment_likes_user_id ON "post".comment_likes (user_id);

-- =============================================================================
-- END POST SCHEMA
-- =============================================================================

-- =============================================================================
-- PROPERTY SCHEMA
-- =============================================================================

-- -----------------------------------------------------------------------------
-- property.properties
-- Real-estate listings with verification, ratings, and activity counters.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "property".properties (
    id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    property_code           VARCHAR(30)     NOT NULL,
    title                   VARCHAR(255)    NOT NULL,
    description             TEXT,
    created_by              UUID            NOT NULL,
    builder_name            VARCHAR(255),
    project_name            VARCHAR(255),
    rera_id                 VARCHAR(100),
    year_built              SMALLINT,
    property_type           VARCHAR(50),
    listing_type            VARCHAR(30),
    price                   DECIMAL(18, 2),
    currency                VARCHAR(10)     DEFAULT 'INR',
    area_size               DECIMAL(10, 2),
    area_unit               VARCHAR(20),
    bedrooms                SMALLINT,
    bathrooms               SMALLINT,
    balconies               SMALLINT,
    parking_count           SMALLINT,
    floor_number            SMALLINT,
    total_floors            SMALLINT,
    no_of_units             INT,
    construction_status     VARCHAR(50),
    furnishing_status       VARCHAR(30),
    availability_date       DATE,
    location                TEXT,
    city                    VARCHAR(100),
    state                   VARCHAR(100),
    country                 VARCHAR(100),
    pin_code                VARCHAR(20),
    latitude                DECIMAL(10, 7),
    longitude               DECIMAL(10, 7),
    verification_status     VARCHAR(30)     NOT NULL DEFAULT 'PENDING',
    verified_by             UUID,
    verified_at             TIMESTAMPTZ,
    rejected_reason         TEXT,
    status                  VARCHAR(30)     NOT NULL DEFAULT 'DRAFT',
    average_rating          DECIMAL(3, 2)   NOT NULL DEFAULT 0,
    rating_count            INT             NOT NULL DEFAULT 0,
    review_count            INT             NOT NULL DEFAULT 0,
    view_count              BIGINT          NOT NULL DEFAULT 0,
    save_count              INT             NOT NULL DEFAULT 0,
    share_count             INT             NOT NULL DEFAULT 0,
    post_count              INT             NOT NULL DEFAULT 0,
    report_count            INT             NOT NULL DEFAULT 0,
    last_activity_at        TIMESTAMPTZ,
    published_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at              TIMESTAMPTZ,

    CONSTRAINT properties_property_code_unique UNIQUE (property_code),
    CONSTRAINT fk_properties_created_by
        FOREIGN KEY (created_by) REFERENCES "user".users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_properties_verified_by
        FOREIGN KEY (verified_by) REFERENCES "user".users (id) ON DELETE SET NULL,
    CONSTRAINT properties_average_rating_range CHECK (average_rating >= 0 AND average_rating <= 5),
    CONSTRAINT properties_rating_count_non_negative CHECK (rating_count >= 0),
    CONSTRAINT properties_review_count_non_negative CHECK (review_count >= 0),
    CONSTRAINT properties_view_count_non_negative CHECK (view_count >= 0),
    CONSTRAINT properties_save_count_non_negative CHECK (save_count >= 0),
    CONSTRAINT properties_share_count_non_negative CHECK (share_count >= 0),
    CONSTRAINT properties_post_count_non_negative CHECK (post_count >= 0),
    CONSTRAINT properties_report_count_non_negative CHECK (report_count >= 0),
    CONSTRAINT properties_property_type_valid
        CHECK (property_type IS NULL OR property_type IN (
            'APARTMENT', 'VILLA', 'PLOT', 'COMMERCIAL', 'OFFICE', 'SHOP', 'HOUSE', 'LAND'
        )),
    CONSTRAINT properties_listing_type_valid
        CHECK (listing_type IS NULL OR listing_type IN ('SALE', 'RENT', 'LEASE')),
    CONSTRAINT properties_area_unit_valid
        CHECK (area_unit IS NULL OR area_unit IN ('SQFT', 'SQM', 'ACRE', 'HECTARE')),
    CONSTRAINT properties_construction_status_valid
        CHECK (construction_status IS NULL OR construction_status IN (
            'READY_TO_MOVE', 'UNDER_CONSTRUCTION', 'NEW_LAUNCH'
        )),
    CONSTRAINT properties_furnishing_status_valid
        CHECK (furnishing_status IS NULL OR furnishing_status IN (
            'UNFURNISHED', 'SEMI_FURNISHED', 'FULLY_FURNISHED'
        )),
    CONSTRAINT properties_verification_status_valid
        CHECK (verification_status IN ('PENDING', 'UNDER_REVIEW', 'VERIFIED', 'REJECTED')),
    CONSTRAINT properties_status_valid
        CHECK (status IN ('DRAFT', 'PUBLISHED', 'SOLD', 'RENTED', 'INACTIVE', 'ARCHIVED')),
    CONSTRAINT properties_bedrooms_non_negative CHECK (bedrooms IS NULL OR bedrooms >= 0),
    CONSTRAINT properties_bathrooms_non_negative CHECK (bathrooms IS NULL OR bathrooms >= 0),
    CONSTRAINT properties_balconies_non_negative CHECK (balconies IS NULL OR balconies >= 0),
    CONSTRAINT properties_parking_count_non_negative CHECK (parking_count IS NULL OR parking_count >= 0),
    CONSTRAINT properties_floor_number_non_negative CHECK (floor_number IS NULL OR floor_number >= 0),
    CONSTRAINT properties_total_floors_non_negative CHECK (total_floors IS NULL OR total_floors >= 0),
    CONSTRAINT properties_no_of_units_non_negative CHECK (no_of_units IS NULL OR no_of_units >= 0),
    CONSTRAINT properties_year_built_valid CHECK (year_built IS NULL OR year_built BETWEEN 1800 AND 2100)
);

COMMENT ON TABLE "property".properties IS 'Property listings; owned by property_service.';
COMMENT ON COLUMN "property".properties.property_type IS 'Type: APARTMENT, VILLA, PLOT, COMMERCIAL, OFFICE, SHOP, HOUSE, LAND.';
COMMENT ON COLUMN "property".properties.listing_type IS 'Listing intent: SALE, RENT, LEASE.';
COMMENT ON COLUMN "property".properties.currency IS 'ISO currency code; default INR.';
COMMENT ON COLUMN "property".properties.area_unit IS 'Area unit: SQFT, SQM, ACRE, HECTARE.';
COMMENT ON COLUMN "property".properties.construction_status IS 'Stage: READY_TO_MOVE, UNDER_CONSTRUCTION, NEW_LAUNCH.';
COMMENT ON COLUMN "property".properties.furnishing_status IS 'Furnishing: UNFURNISHED, SEMI_FURNISHED, FULLY_FURNISHED.';
COMMENT ON COLUMN "property".properties.verification_status IS 'Moderation: PENDING, UNDER_REVIEW, VERIFIED, REJECTED.';
COMMENT ON COLUMN "property".properties.status IS 'Lifecycle: DRAFT, PUBLISHED, SOLD, RENTED, INACTIVE, ARCHIVED.';
COMMENT ON COLUMN "property".properties.deleted_at IS 'Soft-delete timestamp; NULL means active.';

-- -----------------------------------------------------------------------------
-- property.property_features
-- Key/value features and amenities per property.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "property".property_features (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id     UUID            NOT NULL,
    feature_name    VARCHAR(100)    NOT NULL,
    feature_value   VARCHAR(255),
    display_order   SMALLINT        NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ     DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_property_features_property
        FOREIGN KEY (property_id) REFERENCES "property".properties (id) ON DELETE CASCADE
);

COMMENT ON TABLE "property".property_features IS 'Named features/amenities for a property; owned by property_service.';

-- -----------------------------------------------------------------------------
-- property.property_ratings
-- Multi-dimensional ratings and reviews for properties.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "property".property_ratings (
    id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id             UUID            NOT NULL,
    user_id                 UUID            NOT NULL,
    overall_rating          DECIMAL(2, 1),
    location_rating         DECIMAL(2, 1),
    amenities_rating        DECIMAL(2, 1),
    construction_rating       DECIMAL(2, 1),
    value_for_money_rating  DECIMAL(2, 1),
    title                   VARCHAR(255),
    review                  TEXT,
    is_anonymous            BOOLEAN         NOT NULL DEFAULT FALSE,
    status                  VARCHAR(30),
    created_at              TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMPTZ     DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_property_ratings_property
        FOREIGN KEY (property_id) REFERENCES "property".properties (id) ON DELETE CASCADE,
    CONSTRAINT fk_property_ratings_user
        FOREIGN KEY (user_id) REFERENCES "user".users (id) ON DELETE CASCADE,
    CONSTRAINT property_ratings_pair_unique UNIQUE (property_id, user_id),
    CONSTRAINT property_ratings_overall_range
        CHECK (overall_rating IS NULL OR (overall_rating >= 1 AND overall_rating <= 5)),
    CONSTRAINT property_ratings_location_range
        CHECK (location_rating IS NULL OR (location_rating >= 1 AND location_rating <= 5)),
    CONSTRAINT property_ratings_amenities_range
        CHECK (amenities_rating IS NULL OR (amenities_rating >= 1 AND amenities_rating <= 5)),
    CONSTRAINT property_ratings_construction_range
        CHECK (construction_rating IS NULL OR (construction_rating >= 1 AND construction_rating <= 5)),
    CONSTRAINT property_ratings_value_range
        CHECK (value_for_money_rating IS NULL OR (value_for_money_rating >= 1 AND value_for_money_rating <= 5))
);

COMMENT ON TABLE "property".property_ratings IS 'User reviews and granular ratings for properties; owned by property_service.';

-- -----------------------------------------------------------------------------
-- property.property_views
-- View/impression events for listings (authenticated or anonymous).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "property".property_views (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id     UUID            NOT NULL,
    user_id         UUID,
    session_id      VARCHAR(100),
    device_type     VARCHAR(30),
    ip_address      VARCHAR(45),
    viewed_at       TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_property_views_property
        FOREIGN KEY (property_id) REFERENCES "property".properties (id) ON DELETE CASCADE,
    CONSTRAINT fk_property_views_user
        FOREIGN KEY (user_id) REFERENCES "user".users (id) ON DELETE SET NULL
);

COMMENT ON TABLE "property".property_views IS 'Property view analytics; owned by property_service.';

-- -----------------------------------------------------------------------------
-- property.saved_properties
-- User bookmarks / saved listings.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "property".saved_properties (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID            NOT NULL,
    property_id     UUID            NOT NULL,
    created_at      TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_saved_properties_user
        FOREIGN KEY (user_id) REFERENCES "user".users (id) ON DELETE CASCADE,
    CONSTRAINT fk_saved_properties_property
        FOREIGN KEY (property_id) REFERENCES "property".properties (id) ON DELETE CASCADE,
    CONSTRAINT saved_properties_pair_unique UNIQUE (user_id, property_id)
);

COMMENT ON TABLE "property".saved_properties IS 'User-saved property bookmarks; owned by property_service.';

-- -----------------------------------------------------------------------------
-- property.property_documents
-- Verification and legal documents linked to a property.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "property".property_documents (
    id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id             UUID            NOT NULL,
    media_id                UUID,
    uploaded_by             UUID,
    verified_by             UUID,
    document_code           VARCHAR(30),
    document_name           VARCHAR(255)    NOT NULL,
    document_type           VARCHAR(50),
    document_number         VARCHAR(100),
    verification_status     VARCHAR(30),
    verified_at             TIMESTAMPTZ,
    rejected_reason         TEXT,
    expiry_date             DATE,
    status                  VARCHAR(30),
    created_at              TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMPTZ     DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT property_documents_document_code_unique UNIQUE (document_code),
    CONSTRAINT fk_property_documents_property
        FOREIGN KEY (property_id) REFERENCES "property".properties (id) ON DELETE CASCADE,
    CONSTRAINT fk_property_documents_uploaded_by
        FOREIGN KEY (uploaded_by) REFERENCES "user".users (id) ON DELETE SET NULL,
    CONSTRAINT fk_property_documents_verified_by
        FOREIGN KEY (verified_by) REFERENCES "user".users (id) ON DELETE SET NULL
);

COMMENT ON TABLE "property".property_documents IS 'Legal/verification documents for properties; owned by property_service.';
COMMENT ON COLUMN "property".property_documents.media_id IS 'FK → api_gateway.media(id).';

-- -----------------------------------------------------------------------------
-- Cross-schema FK: post.posts → property.properties
-- (Added after property table exists; post schema is defined earlier.)
-- -----------------------------------------------------------------------------
DO $body$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_posts_property'
    ) THEN
        ALTER TABLE "post".posts
            ADD CONSTRAINT fk_posts_property
            FOREIGN KEY (property_id) REFERENCES "property".properties (id) ON DELETE SET NULL;
    END IF;
END $body$;

-- -----------------------------------------------------------------------------
-- Indexes — property schema
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_properties_created_by ON "property".properties (created_by);
CREATE INDEX IF NOT EXISTS idx_properties_property_code ON "property".properties (property_code);
CREATE INDEX IF NOT EXISTS idx_properties_property_type ON "property".properties (property_type);
CREATE INDEX IF NOT EXISTS idx_properties_listing_type ON "property".properties (listing_type);
CREATE INDEX IF NOT EXISTS idx_properties_city ON "property".properties (city);
CREATE INDEX IF NOT EXISTS idx_properties_state ON "property".properties (state);
CREATE INDEX IF NOT EXISTS idx_properties_status ON "property".properties (status);
CREATE INDEX IF NOT EXISTS idx_properties_verification_status ON "property".properties (verification_status);
CREATE INDEX IF NOT EXISTS idx_properties_price ON "property".properties (price);
CREATE INDEX IF NOT EXISTS idx_properties_created_at ON "property".properties (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_properties_published_at ON "property".properties (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_properties_active ON "property".properties (status) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_property_features_property_id ON "property".property_features (property_id);
CREATE INDEX IF NOT EXISTS idx_property_features_display_order ON "property".property_features (property_id, display_order);

CREATE INDEX IF NOT EXISTS idx_property_ratings_property_id ON "property".property_ratings (property_id);
CREATE INDEX IF NOT EXISTS idx_property_ratings_user_id ON "property".property_ratings (user_id);
CREATE INDEX IF NOT EXISTS idx_property_ratings_status ON "property".property_ratings (status);

CREATE INDEX IF NOT EXISTS idx_property_views_property_id ON "property".property_views (property_id);
CREATE INDEX IF NOT EXISTS idx_property_views_user_id ON "property".property_views (user_id);
CREATE INDEX IF NOT EXISTS idx_property_views_viewed_at ON "property".property_views (viewed_at DESC);

CREATE INDEX IF NOT EXISTS idx_saved_properties_user_id ON "property".saved_properties (user_id);
CREATE INDEX IF NOT EXISTS idx_saved_properties_property_id ON "property".saved_properties (property_id);

CREATE INDEX IF NOT EXISTS idx_property_documents_property_id ON "property".property_documents (property_id);
CREATE INDEX IF NOT EXISTS idx_property_documents_uploaded_by ON "property".property_documents (uploaded_by);
CREATE INDEX IF NOT EXISTS idx_property_documents_verification_status ON "property".property_documents (verification_status);
CREATE INDEX IF NOT EXISTS idx_property_documents_document_code ON "property".property_documents (document_code);

-- =============================================================================
-- END PROPERTY SCHEMA
-- =============================================================================

-- =============================================================================
-- AUTH SCHEMA
-- =============================================================================

-- -----------------------------------------------------------------------------
-- auth.auth_users
-- Credentials and login security state (profile data lives in user.users).
-- id matches user.users.id (1:1).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "auth".auth_users (
    id                          UUID            PRIMARY KEY,
    password_hash               TEXT            NOT NULL,
    auth_provider               VARCHAR(30)     NOT NULL DEFAULT 'LOCAL',
    password_changed_at         TIMESTAMPTZ,
    failed_login_attempts       INT             NOT NULL DEFAULT 0,
    account_locked_until        TIMESTAMPTZ,
    last_login_at               TIMESTAMPTZ,
    last_login_ip               VARCHAR(45),
    last_login_device           VARCHAR(100),
    is_password_reset_required  BOOLEAN         NOT NULL DEFAULT FALSE,
    status                      VARCHAR(20)     NOT NULL DEFAULT 'ACTIVE',
    created_at                  TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_auth_users_user
        FOREIGN KEY (id) REFERENCES "user".users (id) ON DELETE CASCADE,
    CONSTRAINT auth_users_failed_attempts_non_negative
        CHECK (failed_login_attempts >= 0),
    CONSTRAINT auth_users_status_valid
        CHECK (status IN ('ACTIVE', 'LOCKED', 'DISABLED', 'PENDING_VERIFICATION'))
);

COMMENT ON TABLE "auth".auth_users IS 'Authentication credentials and session security; owned by auth_service.';
COMMENT ON COLUMN "auth".auth_users.id IS 'Same UUID as user.users.id (shared identity across schemas).';
COMMENT ON COLUMN "auth".auth_users.auth_provider IS 'e.g. LOCAL, GOOGLE, FACEBOOK, MOBILE_OTP.';
COMMENT ON COLUMN "auth".auth_users.account_locked_until IS 'Login blocked until this timestamp when set.';
COMMENT ON COLUMN "auth".auth_users.status IS 'Account auth status: ACTIVE, LOCKED, DISABLED, PENDING_VERIFICATION.';

-- -----------------------------------------------------------------------------
-- Indexes — auth schema
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_auth_users_auth_provider ON "auth".auth_users (auth_provider);
CREATE INDEX IF NOT EXISTS idx_auth_users_status ON "auth".auth_users (status);
CREATE INDEX IF NOT EXISTS idx_auth_users_account_locked_until ON "auth".auth_users (account_locked_until)
    WHERE account_locked_until IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_auth_users_last_login_at ON "auth".auth_users (last_login_at DESC);

-- =============================================================================
-- END AUTH SCHEMA
-- =============================================================================

-- =============================================================================
-- API_GATEWAY SCHEMA
-- Shared platform tables: moderation reports and centralized media metadata.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- api_gateway.reports
-- User-submitted reports against arbitrary platform entities.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS api_gateway.reports (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    report_code         VARCHAR(30)     NOT NULL,
    entity_type         VARCHAR(30)     NOT NULL,
    entity_id           UUID            NOT NULL,
    reported_by         UUID            NOT NULL,
    reported_user_id    UUID,
    reason_code         VARCHAR(50),
    description         TEXT,
    status              VARCHAR(30)     NOT NULL DEFAULT 'PENDING',
    priority            VARCHAR(20)     NOT NULL DEFAULT 'MEDIUM',
    reviewed_by         UUID,
    reviewed_at         TIMESTAMPTZ,
    action_taken        VARCHAR(50),
    action_note         TEXT,
    created_at          TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ     DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT reports_report_code_unique UNIQUE (report_code),
    CONSTRAINT fk_reports_reported_by
        FOREIGN KEY (reported_by) REFERENCES "user".users (id) ON DELETE CASCADE,
    CONSTRAINT fk_reports_reported_user
        FOREIGN KEY (reported_user_id) REFERENCES "user".users (id) ON DELETE SET NULL,
    CONSTRAINT fk_reports_reviewed_by
        FOREIGN KEY (reviewed_by) REFERENCES "user".users (id) ON DELETE SET NULL,
    CONSTRAINT reports_entity_type_valid
        CHECK (entity_type IN (
            'POST', 'COMMENT', 'PROPERTY', 'USER', 'CHAT_MESSAGE',
            'PROPERTY_REVIEW', 'USER_REVIEW'
        )),
    CONSTRAINT reports_reason_code_valid
        CHECK (reason_code IS NULL OR reason_code IN (
            'SPAM', 'FAKE_PROPERTY', 'ABUSIVE_LANGUAGE', 'MISLEADING_INFORMATION',
            'HARASSMENT', 'INAPPROPRIATE_CONTENT', 'SCAM', 'COPYRIGHT', 'OTHER'
        )),
    CONSTRAINT reports_status_valid
        CHECK (status IN ('PENDING', 'UNDER_REVIEW', 'RESOLVED', 'REJECTED', 'ESCALATED')),
    CONSTRAINT reports_priority_valid
        CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))
);

COMMENT ON TABLE api_gateway.reports IS 'Content/user moderation reports; owned by api_gateway.';
COMMENT ON COLUMN api_gateway.reports.entity_type IS 'Target type: POST, COMMENT, PROPERTY, USER, CHAT_MESSAGE, PROPERTY_REVIEW, USER_REVIEW.';
COMMENT ON COLUMN api_gateway.reports.entity_id IS 'Polymorphic target id (no cross-schema FK; enforced in application).';
COMMENT ON COLUMN api_gateway.reports.reason_code IS 'Standard reason: SPAM, FAKE_PROPERTY, ABUSIVE_LANGUAGE, MISLEADING_INFORMATION, etc.';
COMMENT ON COLUMN api_gateway.reports.status IS 'Moderation: PENDING, UNDER_REVIEW, RESOLVED, REJECTED, ESCALATED.';
COMMENT ON COLUMN api_gateway.reports.priority IS 'Severity: LOW, MEDIUM, HIGH, CRITICAL.';
COMMENT ON COLUMN api_gateway.reports.action_taken IS 'Final moderation action applied after review (free-form code).';

-- -----------------------------------------------------------------------------
-- api_gateway.media
-- Central media registry for users, properties, posts, documents, etc.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS api_gateway.media (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    media_code          VARCHAR(30)     NOT NULL,
    entity_type         VARCHAR(30),
    entity_id           UUID,
    uploaded_by         UUID,
    media_type          VARCHAR(30),
    file_name           VARCHAR(255),
    file_url            TEXT,
    thumbnail_url       TEXT,
    mime_type           VARCHAR(100),
    file_size           BIGINT,
    width               INT,
    height              INT,
    duration_seconds    INT,
    display_order       SMALLINT        NOT NULL DEFAULT 1,
    is_cover            BOOLEAN         NOT NULL DEFAULT FALSE,
    storage_provider    VARCHAR(30),
    bucket_name         VARCHAR(100),
    object_key          VARCHAR(255),
    status              VARCHAR(30),
    created_at          TIMESTAMPTZ       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ     DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT media_media_code_unique UNIQUE (media_code),
    CONSTRAINT fk_media_uploaded_by
        FOREIGN KEY (uploaded_by) REFERENCES "user".users (id) ON DELETE SET NULL,
    CONSTRAINT media_file_size_non_negative CHECK (file_size IS NULL OR file_size >= 0),
    CONSTRAINT media_dimensions_non_negative
        CHECK (
            (width IS NULL OR width >= 0)
            AND (height IS NULL OR height >= 0)
            AND (duration_seconds IS NULL OR duration_seconds >= 0)
        )
);

COMMENT ON TABLE api_gateway.media IS 'Uploaded file metadata and storage pointers; owned by api_gateway.';
COMMENT ON COLUMN api_gateway.media.entity_type IS 'Owning entity type, e.g. user, property, post, property_document.';
COMMENT ON COLUMN api_gateway.media.entity_id IS 'Owning entity id (polymorphic; no cross-schema FK).';

-- -----------------------------------------------------------------------------
-- Cross-schema FKs → api_gateway.media
-- -----------------------------------------------------------------------------
DO $body$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_users_profile_photo') THEN
        ALTER TABLE "user".users
            ADD CONSTRAINT fk_users_profile_photo
            FOREIGN KEY (profile_photo_id) REFERENCES api_gateway.media (id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_users_cover_photo') THEN
        ALTER TABLE "user".users
            ADD CONSTRAINT fk_users_cover_photo
            FOREIGN KEY (cover_photo_id) REFERENCES api_gateway.media (id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_property_documents_media') THEN
        ALTER TABLE "property".property_documents
            ADD CONSTRAINT fk_property_documents_media
            FOREIGN KEY (media_id) REFERENCES api_gateway.media (id) ON DELETE SET NULL;
    END IF;
END $body$;

-- -----------------------------------------------------------------------------
-- Indexes — api_gateway schema
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_reports_report_code ON api_gateway.reports (report_code);
CREATE INDEX IF NOT EXISTS idx_reports_entity ON api_gateway.reports (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_reports_reported_by ON api_gateway.reports (reported_by);
CREATE INDEX IF NOT EXISTS idx_reports_reported_user_id ON api_gateway.reports (reported_user_id);
CREATE INDEX IF NOT EXISTS idx_reports_status ON api_gateway.reports (status);
CREATE INDEX IF NOT EXISTS idx_reports_priority ON api_gateway.reports (priority);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON api_gateway.reports (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_media_media_code ON api_gateway.media (media_code);
CREATE INDEX IF NOT EXISTS idx_media_entity ON api_gateway.media (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_media_uploaded_by ON api_gateway.media (uploaded_by);
CREATE INDEX IF NOT EXISTS idx_media_media_type ON api_gateway.media (media_type);
CREATE INDEX IF NOT EXISTS idx_media_status ON api_gateway.media (status);
CREATE INDEX IF NOT EXISTS idx_media_display_order ON api_gateway.media (entity_type, entity_id, display_order);
CREATE INDEX IF NOT EXISTS idx_media_is_cover ON api_gateway.media (entity_type, entity_id, is_cover)
    WHERE is_cover = TRUE;

-- =============================================================================
-- END API_GATEWAY SCHEMA
-- =============================================================================
