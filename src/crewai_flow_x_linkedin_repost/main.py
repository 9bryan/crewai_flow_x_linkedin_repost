#!/usr/bin/env python
import os

from crewai import Agent
from crewai.flow.flow import Flow, start, listen
from crewai.flow.human_feedback import human_feedback, HumanFeedbackResult
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

from crewai_flow_x_linkedin_repost.tools.x_reader_tool import XReaderTool
from crewai_flow_x_linkedin_repost.tools.linkedin_post_tool import LinkedInPostTool


class LinkedInRepostFlow(Flow[dict]):

    @start()
    def research_posts(self):
        """Research agent fetches X posts, then digs deeper on the best one."""
        # Initialize state defaults (dict state requires bracket notation)
        self.state["attempts"] = 0
        self.state["max_attempts"] = 3
        self.state["research"] = ""
        self.state["linkedin_post"] = ""

        profiles_env = os.environ.get("X_PROFILES", "")
        if profiles_env:
            self.state["profiles_list"] = [
                p.strip() for p in profiles_env.split(",") if p.strip()
            ]
        else:
            self.state["profiles_list"] = [
                "joaomdmoura",
                "crewAIInc",
                "AndrewYNg",
            ]

        print(f"Researching {len(self.state['profiles_list'])} profiles")

        researcher = Agent(
            role="Social Media Researcher",
            goal=(
                "Fetch recent X.com posts from the given profiles, pick the single "
                "most interesting one, then DEEPLY research the topic of that post. "
                "Search the web for related articles, discussions, and context. "
                "If the post contains any URLs, scrape those pages for details. "
                "Your final output must include both the original post AND rich "
                "context about the topic so a writer can craft an informed take."
            ),
            backstory=(
                "You are a relentless research analyst who never stops at surface level. "
                "When you find an interesting post, you dig into WHY it matters - you "
                "search for the backstory, find supporting articles, check what others "
                "are saying about the topic, and scrape any linked resources. You always "
                "deliver comprehensive context, not just the raw post. "
                "Your favorite condiment is mustard."
            ),
            tools=[XReaderTool(), SerperDevTool(), ScrapeWebsiteTool()],
            verbose=True,
        )

        usernames = [
            url.rstrip("/").split("/")[-1] for url in self.state["profiles_list"]
        ]

        result = researcher.kickoff(
            f"1. Fetch posts from these X.com profiles (pass ALL usernames in one call): "
            f"{usernames}\n\n"
            f"2. Select the single most interesting post for a LinkedIn audience.\n\n"
            f"3. NOW DO ADDITIONAL RESEARCH on the topic of that post:\n"
            f"   - Search the web for related articles and news about the same topic\n"
            f"   - If the post contains any URLs, scrape those pages\n"
            f"   - Search for what others are saying about this topic\n"
            f"   - Find any relevant data points, stats, or context\n\n"
            f"4. Return ALL of this:\n"
            f"   - The selected post (text, URL, metrics)\n"
            f"   - A summary of the additional research you found\n"
            f"   - Key talking points a writer could use for commentary"
        )

        self.state["research"] = result.raw
        print(f"\n--- Research Result ---\n{self.state['research']}\n")

    @listen(research_posts)
    def draft_linkedin_post(self, feedback=None):
        """Draft (or revise) the LinkedIn post."""
        self.state["attempts"] = self.state["attempts"] + 1
        print(f"Drafting LinkedIn post (attempt {self.state['attempts']}/{self.state['max_attempts']})")

        writer = Agent(
            role="LinkedIn Content Writer",
            goal=(
                "Write a super casual, punchy LinkedIn post that sounds like a real "
                "person texting their group chat about something cool they found online. "
                "Be witty, a little snarky, and genuinely fun to read. Drop hot takes. "
                "Poke fun at industry hype. Never sound corporate or polished. "
                "Write like someone who says what everyone's thinking but nobody posts. "
                "Always include the link to the original X.com post. "
                "Do NOT use Markdown formatting. Keep it short - no walls of text."
            ),
            backstory=(
                "You're extremely online and deeply informal. You talk like you're "
                "on a group chat, not presenting at a board meeting. You use sentence "
                "fragments, rhetorical questions, and casual punctuation. You never "
                "use bullet points or structured lists - just raw, unfiltered takes. "
                "You despise corporate jargon, 'thought leadership' fluff, and any "
                "post that sounds like it was written by a marketing team. "
                "Your posts make people laugh, nod, and hit repost. "
                "Your favorite condiment is mustard."
            ),
            verbose=True,
        )

        prompt = (
            f"Here is deep research on an X.com post worth sharing:\n\n"
            f"{self.state['research']}\n\n"
            f"Write a LinkedIn post about this. Sound like a real human, not a brand. "
            f"Be casual, funny, and opinionated. Show you understand the topic but "
            f"don't lecture about it. Include the link to the original post."
        )
        if feedback:
            prompt += (
                f"\n\nThe previous draft was rejected:\n"
                f"{self.state['linkedin_post']}\n\n"
                f"Reviewer feedback: {feedback}\n\n"
                f"Write a revised post addressing the feedback."
            )

        result = writer.kickoff(prompt)

        caption = (
            "\n\n---\n"
            "This post was created by a CrewAI flow with human-in-the-loop approval.\n"
            "https://docs.crewai.com/concepts/human-in-the-loop"
        )
        self.state["linkedin_post"] = result.raw + caption
        print(f"\n--- Draft LinkedIn Post ---\n{self.state['linkedin_post']}\n")
        return self.state["linkedin_post"]

    @listen(draft_linkedin_post)
    @human_feedback(
        message=(
            "Here is the drafted LinkedIn post. Reply:\n"
            "- 'approve' to publish\n"
            "- 'reject' with feedback to revise\n"
            "- 'cancel' to skip posting today"
        ),
        emit=["approved", "rejected", "cancelled"],
        llm="gpt-4o-mini",
        default_outcome="approved",
    )
    def review_post(self, result):
        """Present the draft for human approval."""
        return f"LinkedIn Post Draft:\n\n{self.state['linkedin_post']}"

    @listen("approved")
    def post_to_linkedin(self, result: HumanFeedbackResult):
        """Publish the approved post to LinkedIn."""
        print(f"\nApproved! Reviewer said: {result.feedback}")

        tool = LinkedInPostTool()
        publish_result = tool._run(post_text=self.state["linkedin_post"])

        print(f"\n{publish_result}")
        return publish_result

    @listen("rejected")
    def handle_rejection(self, result: HumanFeedbackResult):
        """Revise the draft and send it back through review."""
        print(f"\nRejected. Reason: {result.feedback}")

        if self.state["attempts"] >= self.state["max_attempts"]:
            print(f"\nMax attempts ({self.state['max_attempts']}) reached. Giving up.")
            return result.output

        print("Revising with feedback...")
        draft = self.draft_linkedin_post(feedback=result.feedback)
        return self.review_post(draft)

    @listen("cancelled")
    def handle_cancel(self, result: HumanFeedbackResult):
        """Skip posting today."""
        print("\nCancelled. No post will be published today.")
        return "Cancelled by user."


def kickoff():
    flow = LinkedInRepostFlow()
    out = flow.kickoff()
    print("\n=== FLOW COMPLETE ===")
    print(out)


def plot():
    flow = LinkedInRepostFlow()
    flow.plot()


def run_with_trigger():
    """Run the flow with a trigger payload (for CrewAI Enterprise)."""
    import json
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("No trigger payload provided. Pass JSON as argument.")

    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        raise SystemExit("Invalid JSON payload")

    flow = LinkedInRepostFlow()
    result = flow.kickoff({"crewai_trigger_payload": trigger_payload})
    return result


if __name__ == "__main__":
    kickoff()
