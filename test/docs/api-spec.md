# P0 API Specification

This document serves as the authoritative contract for all P0 backend endpoints. Every backend task references this specification.

**Last Updated:** Section 06 from reference/dev.md  
**Status:** Active (P0 Priority)

---

## Table of Contents

1. [Authentication](#authentication)
2. [Integrations - OAuth](#integrations---oauth)
3. [Integrations - Slack Webhook](#integrations---slack-webhook)
4. [Notifications - List](#notifications---list)
5. [Notifications - Stream (SSE)](#notifications---stream-sse)
6. [Focus Session - Start](#focus-session---start)
7. [Focus Session - End](#focus-session---end)
8. [Briefing - Get](#briefing---get)
9. [Feedback - Report](#feedback---report)

---

## Authentication

### Endpoint: POST /api/v1/auth/login

**Method:** `POST`

**Path:** `/api/v1/auth/login`

**Auth Required:** No

**Request Schema:**
```json
{
  "email": "string (required)",
  "password": "string (required)"
}
```

**Response Schema (200 OK):**
```json
{
  "user_id": "string (UUID)",
  "email": "string",
  "token": "string (JWT)",
  "expires_at": "string (ISO 8601 timestamp)"
}
```

**Status Codes:**
- `200 OK` - Login successful
- `400 Bad Request` - Missing or invalid email/password
- `401 Unauthorized` - Invalid credentials
- `429 Too Many Requests` - Rate limited

**Notes:**
- Token must be included in Authorization header: `Authorization: Bearer <token>`
- Token expires at `expires_at` timestamp

---

### Endpoint: POST /api/v1/auth/logout

**Method:** `POST`

**Path:** `/api/v1/auth/logout`

**Auth Required:** Yes (Bearer token)

**Request Schema:**
```json
{}
```

**Response Schema (200 OK):**
```json
{
  "message": "Logged out successfully"
}
```

**Status Codes:**
- `200 OK` - Logout successful
- `401 Unauthorized` - Invalid or missing token
- `500 Internal Server Error` - Server error during logout

**Notes:**
- Token is invalidated server-side
- Client should discard token after successful logout

---

### Endpoint: POST /api/v1/auth/refresh

**Method:** `POST`

**Path:** `/api/v1/auth/refresh`

**Auth Required:** Yes (Bearer token)

**Request Schema:**
```json
{
  "refresh_token": "string"
}
```

**Response Schema (200 OK):**
```json
{
  "token": "string (JWT)",
  "expires_at": "string (ISO 8601 timestamp)"
}
```

**Status Codes:**
- `200 OK` - Token refreshed successfully
- `400 Bad Request` - Missing refresh_token
- `401 Unauthorized` - Invalid or expired refresh_token
- `403 Forbidden` - Refresh token revoked

**Notes:**
- Returns new JWT token with updated expiration
- Refresh token is single-use

---

## Integrations - OAuth

### Endpoint: GET /api/v1/integrations/oauth/authorize

**Method:** `GET`

**Path:** `/api/v1/integrations/oauth/authorize`

**Auth Required:** Yes (Bearer token)

**Query Parameters:**
```
provider: string (required) - "google", "microsoft", "github"
redirect_uri: string (required) - OAuth callback URL
scope: string (optional) - Space-separated list of requested scopes
```

**Response Schema (302 Found):**
- Redirect to OAuth provider authorization endpoint

**Status Codes:**
- `302 Found` - Redirect to OAuth provider
- `400 Bad Request` - Invalid provider or missing redirect_uri
- `401 Unauthorized` - Invalid or missing token

**Notes:**
- Response is a redirect; no JSON body
- State parameter is generated server-side and validated on callback

---

### Endpoint: GET /api/v1/integrations/oauth/callback

**Method:** `GET`

**Path:** `/api/v1/integrations/oauth/callback`

**Auth Required:** No

**Query Parameters:**
```
code: string (required) - Authorization code from OAuth provider
state: string (required) - State parameter for CSRF protection
provider: string (required) - OAuth provider identifier
```

**Response Schema (200 OK):**
```json
{
  "user_id": "string (UUID)",
  "provider": "string",
  "provider_user_id": "string",
  "email": "string",
  "name": "string",
  "token": "string (JWT)",
  "expires_at": "string (ISO 8601 timestamp)"
}
```

**Status Codes:**
- `200 OK` - OAuth flow completed successfully
- `400 Bad Request` - Invalid code, state, or provider
- `401 Unauthorized` - OAuth provider rejected request
- `403 Forbidden` - State mismatch (CSRF protection)
- `500 Internal Server Error` - OAuth provider error

**Notes:**
- State must match value from authorization request
- Creates or updates user account
- Returns JWT token for authenticated session

---

### Endpoint: POST /api/v1/integrations/oauth/disconnect

**Method:** `POST`

**Path:** `/api/v1/integrations/oauth/disconnect`

**Auth Required:** Yes (Bearer token)

**Request Schema:**
```json
{
  "provider": "string (required)"
}
```

**Response Schema (200 OK):**
```json
{
  "message": "OAuth integration disconnected",
  "provider": "string"
}
```

**Status Codes:**
- `200 OK` - OAuth integration disconnected
- `400 Bad Request` - Invalid provider or not connected
- `401 Unauthorized` - Invalid or missing token
- `404 Not Found` - OAuth integration not found for user

**Notes:**
- Revokes stored OAuth tokens for the provider
- User can re-connect later

---

## Integrations - Slack Webhook

### Endpoint: POST /api/v1/integrations/slack/webhook/subscribe

**Method:** `POST`

**Path:** `/api/v1/integrations/slack/webhook/subscribe`

**Auth Required:** Yes (Bearer token)

**Request Schema:**
```json
{
  "webhook_url": "string (required)",
  "channel": "string (required)",
  "events": ["string"] (required array)
}
```

**Response Schema (201 Created):**
```json
{
  "webhook_id": "string (UUID)",
  "user_id": "string (UUID)",
  "webhook_url": "string",
  "channel": "string",
  "events": ["string"],
  "created_at": "string (ISO 8601 timestamp)",
  "is_active": true
}
```

**Status Codes:**
- `201 Created` - Webhook subscription created
- `400 Bad Request` - Invalid webhook_url, channel, or events
- `401 Unauthorized` - Invalid or missing token
- `409 Conflict` - Webhook already subscribed for user

**Notes:**
- Events can include: "notification", "focus_session_end", "briefing_ready"
- Webhook URL is validated before storing
- Webhook must be reachable by the API server

---

### Endpoint: DELETE /api/v1/integrations/slack/webhook/{webhook_id}

**Method:** `DELETE`

**Path:** `/api/v1/integrations/slack/webhook/{webhook_id}`

**Auth Required:** Yes (Bearer token)

**Path Parameters:**
```
webhook_id: string (UUID, required)
```

**Response Schema (200 OK):**
```json
{
  "message": "Webhook subscription deleted",
  "webhook_id": "string (UUID)"
}
```

**Status Codes:**
- `200 OK` - Webhook subscription deleted
- `401 Unauthorized` - Invalid or missing token
- `403 Forbidden` - User does not own webhook
- `404 Not Found` - Webhook not found

**Notes:**
- Only webhook owner can delete
- Stops sending events to webhook URL

---

### Endpoint: POST /api/v1/integrations/slack/webhook/test

**Method:** `POST`

**Path:** `/api/v1/integrations/slack/webhook/test`

**Auth Required:** Yes (Bearer token)

**Request Schema:**
```json
{
  "webhook_id": "string (UUID, required)"
}
```

**Response Schema (200 OK):**
```json
{
  "message": "Test message sent",
  "webhook_id": "string (UUID)",
  "status": "delivered"
}
```

**Status Codes:**
- `200 OK` - Test message delivered
- `400 Bad Request` - Invalid webhook_id
- `401 Unauthorized` - Invalid or missing token
- `403 Forbidden` - User does not own webhook
- `404 Not Found` - Webhook not found
- `502 Bad Gateway` - Webhook URL unreachable

**Notes:**
- Sends test notification payload to webhook URL
- Validates webhook connectivity

---

## Notifications - List

### Endpoint: GET /api/v1/notifications

**Method:** `GET`

**Path:** `/api/v1/notifications`

**Auth Required:** Yes (Bearer token)

**Query Parameters:**
```
limit: integer (optional, default: 50, max: 100)
offset: integer (optional, default: 0)
unread_only: boolean (optional, default: false)
type: string (optional) - Filter by notification type
```

**Response Schema (200 OK):**
```json
{
  "notifications": [
    {
      "notification_id": "string (UUID)",
      "user_id": "string (UUID)",
      "type": "string",
      "title": "string",
      "message": "string",
      "payload": "object",
      "is_read": "boolean",
      "created_at": "string (ISO 8601 timestamp)",
      "read_at": "string (ISO 8601 timestamp, nullable)"
    }
  ],
  "total": "integer",
  "limit": "integer",
  "offset": "integer",
  "has_more": "boolean"
}
```

**Status Codes:**
- `200 OK` - Notifications retrieved successfully
- `400 Bad Request` - Invalid query parameters
- `401 Unauthorized` - Invalid or missing token

**Notes:**
- Returns paginated results in reverse chronological order
- `payload` object contains type-specific data
- `read_at` is null for unread notifications

---

## Notifications - Stream (SSE)

### Endpoint: GET /api/v1/notifications/stream

**Method:** `GET`

**Path:** `/api/v1/notifications/stream`

**Auth Required:** Yes (Bearer token)

**Headers:**
```
Accept: text/event-stream (required)
Authorization: Bearer <token> (required)
```

**Response Format:** Server-Sent Events (text/event-stream)

**Event Stream Structure:**
```
event: notification
data: {
  "notification_id": "string (UUID)",
  "user_id": "string (UUID)",
  "type": "string",
  "title": "string",
  "message": "string",
  "payload": "object",
  "created_at": "string (ISO 8601 timestamp)"
}

event: heartbeat
data: {"timestamp": "string (ISO 8601)"}

event: error
data: {"code": "string", "message": "string"}
```

**Status Codes:**
- `200 OK` - Stream established, events delivered
- `400 Bad Request` - Invalid Accept header
- `401 Unauthorized` - Invalid or missing token
- `503 Service Unavailable` - Server at capacity

**Notes:**
- Connection remains open; events pushed in real-time
- Heartbeat event sent every 30 seconds to keep connection alive
- Client should reconnect on `error` event
- Maximum connection duration: 24 hours
- Up to 100 concurrent streams per user

---

## Focus Session - Start

### Endpoint: POST /api/v1/focus-sessions/start

**Method:** `POST`

**Path:** `/api/v1/focus-sessions/start`

**Auth Required:** Yes (Bearer token)

**Request Schema:**
```json
{
  "duration_minutes": "integer (required, min: 5, max: 480)",
  "title": "string (optional)",
  "tags": ["string"] (optional array)
}
```

**Response Schema (201 Created):**
```json
{
  "session_id": "string (UUID)",
  "user_id": "string (UUID)",
  "duration_minutes": "integer",
  "title": "string (nullable)",
  "tags": ["string"],
  "started_at": "string (ISO 8601 timestamp)",
  "scheduled_end_at": "string (ISO 8601 timestamp)",
  "status": "active"
}
```

**Status Codes:**
- `201 Created` - Focus session started
- `400 Bad Request` - Invalid duration or parameters
- `401 Unauthorized` - Invalid or missing token
- `409 Conflict` - User already has an active focus session

**Notes:**
- Only one active session per user at a time
- `scheduled_end_at` is calculated as `started_at + duration_minutes`
- Tags can be used for categorization (e.g., "work", "learning")

---

## Focus Session - End

### Endpoint: POST /api/v1/focus-sessions/{session_id}/end

**Method:** `POST`

**Path:** `/api/v1/focus-sessions/{session_id}/end`

**Auth Required:** Yes (Bearer token)

**Path Parameters:**
```
session_id: string (UUID, required)
```

**Request Schema:**
```json
{
  "completed": "boolean (required)",
  "notes": "string (optional)"
}
```

**Response Schema (200 OK):**
```json
{
  "session_id": "string (UUID)",
  "user_id": "string (UUID)",
  "duration_minutes": "integer",
  "title": "string (nullable)",
  "tags": ["string"],
  "started_at": "string (ISO 8601 timestamp)",
  "scheduled_end_at": "string (ISO 8601 timestamp)",
  "ended_at": "string (ISO 8601 timestamp)",
  "completed": "boolean",
  "notes": "string (nullable)",
  "status": "completed" | "abandoned"
}
```

**Status Codes:**
- `200 OK` - Focus session ended successfully
- `400 Bad Request` - Invalid completed flag or session_id
- `401 Unauthorized` - Invalid or missing token
- `403 Forbidden` - User does not own session
- `404 Not Found` - Session not found
- `409 Conflict` - Session already ended

**Notes:**
- `status` is "completed" if `completed=true`, otherwise "abandoned"
- `ended_at` is current server timestamp
- Cannot end a session that is already ended

---

## Briefing - Get

### Endpoint: GET /api/v1/briefing

**Method:** `GET`

**Path:** `/api/v1/briefing`

**Auth Required:** Yes (Bearer token)

**Query Parameters:**
```
date: string (optional, ISO 8601 date, default: today)
```

**Response Schema (200 OK):**
```json
{
  "briefing_id": "string (UUID)",
  "user_id": "string (UUID)",
  "date": "string (ISO 8601 date)",
  "sections": [
    {
      "section_id": "string (UUID)",
      "title": "string",
      "type": "string",
      "content": "string",
      "items": ["string"] (optional)
    }
  ],
  "summary": "string",
  "generated_at": "string (ISO 8601 timestamp)",
  "is_read": "boolean"
}
```

**Status Codes:**
- `200 OK` - Briefing retrieved successfully
- `400 Bad Request` - Invalid date parameter
- `401 Unauthorized` - Invalid or missing token
- `404 Not Found` - Briefing not generated yet for date

**Notes:**
- Briefing is typically generated once per day
- If briefing not yet generated for requested date, returns 404
- Client can poll with 202 Accepted during generation
- Sections can have types: "summary", "priorities", "notifications", "insights"

---

## Feedback - Report

### Endpoint: POST /api/v1/feedback

**Method:** `POST`

**Path:** `/api/v1/feedback`

**Auth Required:** Yes (Bearer token)

**Request Schema:**
```json
{
  "type": "string (required, enum: 'bug', 'feature', 'improvement')",
  "title": "string (required)",
  "description": "string (required)",
  "severity": "string (optional, enum: 'low', 'medium', 'high')",
  "tags": ["string"] (optional),
  "attachment_url": "string (optional, URL)"
}
```

**Response Schema (201 Created):**
```json
{
  "feedback_id": "string (UUID)",
  "user_id": "string (UUID)",
  "type": "string",
  "title": "string",
  "description": "string",
  "severity": "string (nullable)",
  "tags": ["string"],
  "attachment_url": "string (nullable)",
  "status": "received",
  "created_at": "string (ISO 8601 timestamp)"
}
```

**Status Codes:**
- `201 Created` - Feedback submitted successfully
- `400 Bad Request` - Missing required fields or invalid type
- `401 Unauthorized` - Invalid or missing token
- `413 Payload Too Large` - Description exceeds 5000 characters

**Notes:**
- Type must be one of: "bug", "feature", "improvement"
- Severity defaults to "medium" if not provided
- Feedback is used for product improvements and bug tracking
- Attachment URL must be publicly accessible

---

## Error Response Format

All endpoints return errors in the following format:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": "object (optional)"
  }
}
```

**Common Error Codes:**
- `INVALID_REQUEST` - Malformed request body
- `UNAUTHORIZED` - Missing or invalid authentication
- `FORBIDDEN` - Authenticated but lacking permissions
- `NOT_FOUND` - Resource does not exist
- `CONFLICT` - Request conflicts with current state
- `RATE_LIMITED` - Too many requests
- `INTERNAL_ERROR` - Server error

---

## Authentication Header Format

All endpoints requiring authentication expect:

```
Authorization: Bearer <JWT_TOKEN>
```

The token is obtained from:
- `/api/v1/auth/login` - Email/password login
- `/api/v1/integrations/oauth/callback` - OAuth completion
- `/api/v1/auth/refresh` - Token refresh

---

## Versioning

Current API version: `v1`

All endpoints are prefixed with `/api/v1/`.

Future breaking changes will introduce new versions (e.g., `/api/v2/`).

---

## Rate Limiting

- **Default:** 100 requests per 15 minutes per user
- **Auth endpoints:** 10 requests per 15 minutes per IP
- **Notifications stream:** 1 stream per user, max 100 concurrent streams

Rate limit headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1234567890
```

---

**End of P0 API Specification**
