# CrewAI Flow: X to LinkedIn Repost

A CrewAI Flow that monitors X.com (Twitter) profiles, generates LinkedIn posts with your commentary, and publishes after your approval via a human-in-the-loop (HITL) email workflow.

Uses a lightweight flow-with-inline-agents architecture - no crews. Each step is a focused agent or direct tool call, giving you full control and fast retries.

## How It Works

```
@start fetch_posts             Calls XReaderTool directly (last 24h, all profiles in one call)
    |
@listen select_post            Inline agent picks the single best post
    |
@listen draft_linkedin_post    Inline agent writes a LinkedIn post with your commentary
    |
@human_feedback review_post    You approve/reject via email (Enterprise) or console (local)
    |
    +-- "approved" --> post_to_linkedin     Publishes to LinkedIn via API
    |
    +-- "rejected" --> handle_rejection     Loops back to draft_linkedin_post only
                                            (no re-fetching from X, up to 3 attempts)
```

## Prerequisites

- Python >=3.11, <3.14
- [uv](https://docs.astral.sh/uv/) for dependency management
- An X.com (Twitter) developer account with API access
- A LinkedIn developer app with OAuth2 credentials

## Installation

```bash
pip install uv
crewai install
```

## Configuration

All secrets go in the `.env` file at the project root.

### 1. OpenAI API Key

```
OPENAI_API_KEY=sk-...
```

### 2. X.com (Twitter) Bearer Token

Get this from the [Twitter Developer Portal](https://developer.x.com/en/portal/dashboard).

```
X_BEARER_TOKEN=your_x_bearer_token
```

Note: The free tier has strict rate limits (1 request per 15 minutes). The tool uses `wait_on_rate_limit=True` so it will automatically pause and resume - it just takes a while with multiple profiles.

### 3. LinkedIn API Credentials

This requires a few steps to set up.

#### Step 1: Create a LinkedIn App

1. Go to [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps/) and create a new app
2. Under the **Products** tab, request access to:
   - **Share on LinkedIn** (grants `w_member_social` scope)
   - **Sign In with LinkedIn using OpenID Connect** (grants `openid` and `profile` scopes)
3. Under the **Auth** tab, add your redirect URL under **"Authorized redirect URLs for your app"** (e.g. `http://yoursite.com`)
4. Note your **Client ID** and **Client secret** from the Auth tab

#### Step 2: Get an Authorization Code

Open this URL in your browser (replace the placeholders):

```
https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT_URI&scope=openid%20profile%20w_member_social
```

After authorizing, you'll be redirected to your redirect URI with a `?code=XXXXX` parameter in the URL. Copy that code.

#### Step 3: Exchange the Code for an Access Token

Run this immediately (codes expire within minutes):

```bash
curl -X POST https://www.linkedin.com/oauth/v2/accessToken \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "code=YOUR_AUTHORIZATION_CODE" \
  -d "redirect_uri=YOUR_REDIRECT_URI" \
  -d "client_id=YOUR_CLIENT_ID" \
  --data-urlencode "client_secret=YOUR_CLIENT_SECRET"
```

The response will contain your `access_token`. These tokens last **60 days**.

**Important**: Use `--data-urlencode` for the client secret to properly handle special characters like `==`.

#### Step 4: Get Your Person ID

```bash
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
     https://api.linkedin.com/v2/userinfo
```

The `sub` field in the response is your person ID.

#### Step 5: Add to .env

```
LINKEDIN_ACCESS_TOKEN=your_access_token
LINKEDIN_PERSON_ID=your_person_id_from_sub_field
```

### 4. X.com Profiles to Monitor (Optional)

By default the flow monitors a few profiles. Override with a comma-separated list of usernames (without @):

```
X_PROFILES=joaomdmoura,crewAIInc,AndrewYNg
```

## Running

```bash
crewai run
```

When run locally, the HITL approval step will prompt in the console. When deployed to CrewAI Enterprise, it sends approval emails automatically.

## Project Structure

```
crewai_flow_x_linkedin_repost/
├── .env                                   # API keys and config
├── knowledge/
│   └── user_preference.txt                # Your persona/voice for content
├── pyproject.toml
└── src/crewai_flow_x_linkedin_repost/
    ├── main.py                            # Flow with inline agents + HITL
    └── tools/
        ├── x_reader_tool.py               # Fetches X posts (last 24h, batch)
        └── linkedin_post_tool.py          # Publishes to LinkedIn (Posts API)
```

## Customization

- **Profiles**: Set `X_PROFILES` in `.env` or edit the defaults in `main.py`
- **Your voice**: Edit `knowledge/user_preference.txt` with your name, interests, and writing style
- **Agent behavior**: Edit the agent `role`, `goal`, and `backstory` strings in `main.py`
- **Max retries**: Change `max_attempts` in `LinkedInRepostState` in `main.py` (default: 3)
