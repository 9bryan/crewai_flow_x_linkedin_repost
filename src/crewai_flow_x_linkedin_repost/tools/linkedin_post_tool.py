import os
from typing import Type

import requests
from pydantic import BaseModel, Field

from crewai.tools import BaseTool


class LinkedInPostToolInput(BaseModel):
    """Input schema for LinkedInPostTool."""

    post_text: str = Field(
        ...,
        description="The text content to publish as a LinkedIn post.",
    )


class LinkedInPostTool(BaseTool):
    name: str = "LinkedIn Post Publisher"
    description: str = (
        "Publishes a text post to LinkedIn on behalf of the authenticated user. "
        "Provide the full post text including any hashtags. "
        "Do NOT include markdown formatting in the post text."
    )
    args_schema: Type[BaseModel] = LinkedInPostToolInput

    def _run(self, post_text: str) -> str:
        access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        if not access_token:
            return (
                "Error: LINKEDIN_ACCESS_TOKEN environment variable not set. "
                "Please add your LinkedIn OAuth2 access token to the .env file."
            )

        person_id = os.getenv("LINKEDIN_PERSON_ID")
        if not person_id:
            return (
                "Error: LINKEDIN_PERSON_ID environment variable not set. "
                "Please add your LinkedIn person ID (from /v2/userinfo 'sub' field) to the .env file."
            )

        author_urn = f"urn:li:person:{person_id}"

        payload = {
            "author": author_urn,
            "commentary": post_text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202602",
        }

        try:
            response = requests.post(
                "https://api.linkedin.com/rest/posts",
                json=payload,
                headers=headers,
            )

            if response.status_code == 201:
                post_id = response.headers.get("x-restli-id", "unknown")
                return f"Successfully published LinkedIn post. Post ID: {post_id}"

            return (
                f"Error publishing to LinkedIn. "
                f"Status: {response.status_code}, "
                f"Response: {response.text}"
            )

        except requests.RequestException as e:
            return f"Error connecting to LinkedIn API: {str(e)}"
