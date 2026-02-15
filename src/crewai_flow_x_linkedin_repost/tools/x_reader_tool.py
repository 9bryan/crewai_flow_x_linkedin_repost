import os
from datetime import datetime, timedelta
from typing import List, Type

from pydantic import BaseModel, Field

from crewai.tools import BaseTool


class XReaderToolInput(BaseModel):
    """Input schema for XReaderTool."""

    profile_usernames: List[str] = Field(
        ...,
        description=(
            "List of X.com (Twitter) usernames to fetch posts from (without @ symbol). "
            "Example: ['elonmusk', 'AndrewYNg']"
        ),
    )


class XReaderTool(BaseTool):
    name: str = "X.com Profile Posts Reader"
    description: str = (
        "Reads and retrieves posts from multiple X.com (Twitter) profiles in a single call. "
        "First tries the last 24 hours; if no posts are found, fetches the most recent posts. "
        "Provide all usernames at once to minimize API calls. "
        "Usernames should be without the @ symbol. "
        "This tool handles rate limiting automatically by waiting when limits are hit."
    )
    args_schema: Type[BaseModel] = XReaderToolInput

    def _format_tweets(self, tweets_data, username, period_label):
        section = f"Posts from @{username} ({period_label}):\n\n"
        for idx, tweet in enumerate(tweets_data, 1):
            created_at = tweet.created_at.strftime("%Y-%m-%d %H:%M UTC")
            metrics = tweet.public_metrics
            tweet_url = f"https://x.com/{username}/status/{tweet.id}"

            section += f"--- Post {idx} ---\n"
            section += f"Date: {created_at}\n"
            section += f"Text: {tweet.text}\n"
            section += f"URL: {tweet_url}\n"
            section += f"Likes: {metrics['like_count']}, "
            section += f"Retweets: {metrics['retweet_count']}, "
            section += f"Replies: {metrics['reply_count']}\n\n"

        section += f"Total posts from @{username}: {len(tweets_data)}\n"
        return section

    def _run(self, profile_usernames: List[str]) -> str:
        try:
            import tweepy
        except ImportError:
            return (
                "Error: tweepy library not installed. "
                "Please add 'tweepy>=4.14.0' to your project dependencies."
            )

        bearer_token = os.getenv("X_BEARER_TOKEN")
        if not bearer_token:
            return (
                "Error: X_BEARER_TOKEN environment variable not set. "
                "Please add your X.com API Bearer Token to the .env file."
            )

        client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)

        since = datetime.utcnow() - timedelta(hours=24)
        start_time = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        all_results = []

        for username in profile_usernames:
            username = username.strip().lstrip("@")
            print(f"  Fetching posts for @{username}...")

            try:
                user = client.get_user(username=username)
                if not user.data:
                    all_results.append(f"Error: User '@{username}' not found on X.com\n")
                    continue
                user_id = user.data.id
            except Exception as e:
                all_results.append(f"Error fetching user '@{username}': {str(e)}\n")
                continue

            try:
                # Try last 24 hours first
                tweets = client.get_users_tweets(
                    id=user_id,
                    start_time=start_time,
                    max_results=100,
                    tweet_fields=["created_at", "public_metrics", "text"],
                    exclude=["retweets", "replies"],
                )

                if tweets.data:
                    all_results.append(
                        self._format_tweets(tweets.data, username, "last 24 hours")
                    )
                    continue

                # Fallback: get most recent posts (no time filter)
                print(f"  No recent posts for @{username}, fetching most recent...")
                tweets = client.get_users_tweets(
                    id=user_id,
                    max_results=5,
                    tweet_fields=["created_at", "public_metrics", "text"],
                    exclude=["retweets", "replies"],
                )

                if tweets.data:
                    all_results.append(
                        self._format_tweets(tweets.data, username, "most recent")
                    )
                else:
                    all_results.append(f"No posts found for @{username}.\n")

            except Exception as e:
                all_results.append(
                    f"Error fetching tweets for @{username}: {str(e)}\n"
                )

        if not all_results:
            return "No results retrieved from any profile."

        return "\n".join(all_results)
