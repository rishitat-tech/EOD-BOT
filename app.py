import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from db import (
    init_db,
    upsert_team_member,
    replace_active_team_members,
    save_eod_update,
    get_updates_by_date,
    get_active_team_members
)

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

EOD_CHANNEL_ID = os.getenv("EOD_CHANNEL_ID")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")

EOD_REMINDER_HOUR = int(os.getenv("EOD_REMINDER_HOUR", "17"))
EOD_REMINDER_MINUTE = int(os.getenv("EOD_REMINDER_MINUTE", "0"))

EOD_SUMMARY_HOUR = int(os.getenv("EOD_SUMMARY_HOUR", "18"))
EOD_SUMMARY_MINUTE = int(os.getenv("EOD_SUMMARY_MINUTE", "0"))

app = App(token=SLACK_BOT_TOKEN)


def today_str():
    return datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")


def now_display():
    return datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")


def get_user_name(client, user_id):
    try:
        result = client.users_info(user=user_id)
        user = result["user"]

        return (
            user.get("profile", {}).get("real_name")
            or user.get("real_name")
            or user.get("name")
            or user_id
        )

    except Exception as e:
        print(f"Failed to fetch user name for {user_id}: {e}")
        return user_id


def send_dm(client, user_id, text):
    try:
        result = client.conversations_open(users=user_id)
        dm_channel = result["channel"]["id"]

        client.chat_postMessage(
            channel=dm_channel,
            text=text
        )
    except Exception as e:
        print(f"Failed to send DM to {user_id}: {e}")


def sync_channel_members(client):
    if not EOD_CHANNEL_ID:
        print("EOD_CHANNEL_ID missing. Cannot sync members.")
        return []

    members = []
    cursor = None

    try:
        while True:
            response = client.conversations_members(
                channel=EOD_CHANNEL_ID,
                cursor=cursor
            )

            user_ids = response.get("members", [])

            for user_id in user_ids:
                try:
                    info = client.users_info(user=user_id)
                    user = info["user"]

                    if user.get("deleted"):
                        continue

                    if user.get("is_bot"):
                        continue

                    if user.get("id") == "USLACKBOT":
                        continue

                    user_name = (
                        user.get("profile", {}).get("real_name")
                        or user.get("real_name")
                        or user.get("name")
                        or user_id
                    )

                    members.append({
                        "slack_user_id": user_id,
                        "user_name": user_name
                    })

                except Exception as e:
                    print(f"Failed to fetch user info for {user_id}: {e}")

            cursor = response.get("response_metadata", {}).get("next_cursor")

            if not cursor:
                break

        replace_active_team_members(members)
        print(f"Synced {len(members)} active members.")
        return members

    except Exception as e:
        print(f"Failed to sync channel members: {e}")
        return []


def build_eod_modal():
    return {
        "type": "modal",
        "callback_id": "eod_modal_submit",
        "title": {
            "type": "plain_text",
            "text": "EOD Update"
        },
        "submit": {
            "type": "plain_text",
            "text": "Submit"
        },
        "close": {
            "type": "plain_text",
            "text": "Cancel"
        },
        "blocks": [
            {
                "type": "input",
                "block_id": "completed_block",
                "label": {
                    "type": "plain_text",
                    "text": "What did you complete today?"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "completed_input",
                    "multiline": True
                }
            },
            {
                "type": "input",
                "block_id": "tomorrow_block",
                "label": {
                    "type": "plain_text",
                    "text": "What are you planning for tomorrow?"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "tomorrow_input",
                    "multiline": True
                }
            },
            {
                "type": "input",
                "block_id": "blocker_block",
                "label": {
                    "type": "plain_text",
                    "text": "Any blockers?"
                },
                "element": {
                    "type": "static_select",
                    "action_id": "blocker_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select one"
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "No"
                            },
                            "value": "No"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Yes"
                            },
                            "value": "Yes"
                        }
                    ]
                }
            },
            {
                "type": "input",
                "block_id": "blocker_details_block",
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "Blocker details"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "blocker_details_input",
                    "multiline": True
                }
            },
            {
                "type": "input",
                "block_id": "help_block",
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "Help needed from anyone?"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "help_input",
                    "multiline": True
                }
            },
            {
                "type": "input",
                "block_id": "status_block",
                "label": {
                    "type": "plain_text",
                    "text": "Overall status"
                },
                "element": {
                    "type": "static_select",
                    "action_id": "status_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select status"
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Green"
                            },
                            "value": "Green"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Yellow"
                            },
                            "value": "Yellow"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Red"
                            },
                            "value": "Red"
                        }
                    ]
                }
            }
        ]
    }


def post_eod_reminder():
    try:
        sync_channel_members(app.client)

        app.client.chat_postMessage(
            channel=EOD_CHANNEL_ID,
            text="EOD Reminder: Please submit your EOD update.",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":spiral_calendar_pad: *EOD Reminder*\nPlease submit your EOD update for today."
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Submit EOD"
                            },
                            "style": "primary",
                            "action_id": "open_eod_modal"
                        }
                    ]
                }
            ]
        )

        print(f"EOD reminder posted at {now_display()}")

    except Exception as e:
        print(f"Failed to post EOD reminder: {e}")


def generate_summary(date):
    updates = get_updates_by_date(date)
    members = get_active_team_members()

    submitted_user_ids = {row[0] for row in updates}
    all_members = {row[0]: row[1] for row in members}

    missing = [
        name
        for user_id, name in all_members.items()
        if user_id not in submitted_user_ids
    ]

    green = 0
    yellow = 0
    red = 0

    completed_lines = []
    tomorrow_lines = []
    blocker_lines = []
    help_lines = []

    for row in updates:
        (
            user_id,
            user_name,
            completed,
            tomorrow,
            has_blocker,
            blocker_details,
            help_needed,
            status,
            submitted_at
        ) = row

        if status == "Green":
            green += 1
        elif status == "Yellow":
            yellow += 1
        elif status == "Red":
            red += 1

        completed_lines.append(f"• *{user_name}:* {completed}")
        tomorrow_lines.append(f"• *{user_name}:* {tomorrow}")

        if has_blocker == "Yes":
            detail = blocker_details or "No blocker details provided"
            blocker_lines.append(f"• :warning: *{user_name}:* {detail}")

        if help_needed:
            help_lines.append(f"• *{user_name}:* {help_needed}")

    total_members = len(members)
    submitted_count = len(updates)

    summary = f"*EOD Report — {date}*\n\n"

    summary += "*Submissions:*\n"
    summary += f"• Submitted: {submitted_count}/{total_members}\n"
    summary += f"• Missing: {', '.join(missing) if missing else 'None'}\n\n"

    summary += "*Status:*\n"
    summary += f"• :large_green_circle: Green: {green}\n"
    summary += f"• :large_yellow_circle: Yellow: {yellow}\n"
    summary += f"• :red_circle: Red: {red}\n\n"

    summary += "*Completed Today:*\n"
    summary += "\n".join(completed_lines) if completed_lines else "No updates submitted"
    summary += "\n\n"

    summary += "*Plan for Tomorrow:*\n"
    summary += "\n".join(tomorrow_lines) if tomorrow_lines else "No plans submitted"
    summary += "\n\n"

    summary += "*Blockers:*\n"
    summary += "\n".join(blocker_lines) if blocker_lines else "No blockers reported"
    summary += "\n\n"

    summary += "*Help Needed:*\n"
    summary += "\n".join(help_lines) if help_lines else "No help requests"
    summary += "\n"

    return summary


def post_eod_summary():
    try:
        sync_channel_members(app.client)

        date = today_str()
        summary = generate_summary(date)
        title = f"EOD Report — {date}"

        parent_message = app.client.chat_postMessage(
            channel=EOD_CHANNEL_ID,
            text=title,
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": title,
                        "emoji": True
                    }
                }
            ]
        )

        app.client.chat_postMessage(
            channel=EOD_CHANNEL_ID,
            thread_ts=parent_message["ts"],
            text=summary
        )

        print(f"EOD report posted at {now_display()}")

    except Exception as e:
        print(f"Failed to post EOD report: {e}")


@app.command("/eod")
def handle_eod_command(ack, body, client):
    ack()

    user_id = body["user_id"]
    user_name = body.get("user_name") or get_user_name(client, user_id)

    upsert_team_member(user_id, user_name)

    client.views_open(
        trigger_id=body["trigger_id"],
        view=build_eod_modal()
    )


@app.command("/eod-summary")
def handle_summary_command(ack, body, client):
    ack()

    date = today_str()
    summary = generate_summary(date)

    client.chat_postMessage(
        channel=body["channel_id"],
        text=summary
    )


@app.command("/eod-sync-members")
def handle_sync_members_command(ack, body, client):
    ack()

    members = sync_channel_members(client)

    client.chat_postMessage(
        channel=body["channel_id"],
        text=f"Synced {len(members)} active team members from the EOD channel."
    )


@app.action("open_eod_modal")
def handle_open_eod_modal(ack, body, client):
    ack()

    user_id = body["user"]["id"]
    user_name = get_user_name(client, user_id)

    upsert_team_member(user_id, user_name)

    client.views_open(
        trigger_id=body["trigger_id"],
        view=build_eod_modal()
    )


@app.view("eod_modal_submit")
def handle_eod_modal_submit(ack, body, client, view):
    values = view["state"]["values"]

    completed_today = values["completed_block"]["completed_input"]["value"]
    plan_tomorrow = values["tomorrow_block"]["tomorrow_input"]["value"]
    has_blocker = values["blocker_block"]["blocker_input"]["selected_option"]["value"]

    blocker_details = values["blocker_details_block"]["blocker_details_input"].get("value") or ""
    help_needed = values["help_block"]["help_input"].get("value") or ""
    status = values["status_block"]["status_input"]["selected_option"]["value"]

    errors = {}

    if has_blocker == "Yes" and not blocker_details.strip():
        errors["blocker_details_block"] = "Please provide blocker details."

    if errors:
        ack(response_action="errors", errors=errors)
        return

    ack()

    user_id = body["user"]["id"]
    user_name = get_user_name(client, user_id)
    date = today_str()

    upsert_team_member(user_id, user_name)

    save_eod_update(
        slack_user_id=user_id,
        user_name=user_name,
        date=date,
        completed_today=completed_today,
        plan_tomorrow=plan_tomorrow,
        has_blocker=has_blocker,
        blocker_details=blocker_details,
        help_needed=help_needed,
        status=status
    )

    send_dm(
        client,
        user_id,
        "Thanks! Your EOD update has been submitted. You can submit again today if you need to update it."
    )


def start_scheduler():
    scheduler = BackgroundScheduler(timezone=TIMEZONE)

    scheduler.add_job(
        post_eod_reminder,
        "cron",
        hour=EOD_REMINDER_HOUR,
        minute=EOD_REMINDER_MINUTE,
        id="daily_eod_reminder",
        replace_existing=True
    )

    scheduler.add_job(
        post_eod_summary,
        "cron",
        hour=EOD_SUMMARY_HOUR,
        minute=EOD_SUMMARY_MINUTE,
        id="daily_eod_summary",
        replace_existing=True
    )

    scheduler.start()

    print("Scheduler started.")
    print(f"Reminder time: {EOD_REMINDER_HOUR}:{EOD_REMINDER_MINUTE:02d} {TIMEZONE}")
    print(f"Summary time: {EOD_SUMMARY_HOUR}:{EOD_SUMMARY_MINUTE:02d} {TIMEZONE}")


def validate_env():
    missing = []

    if not SLACK_BOT_TOKEN:
        missing.append("SLACK_BOT_TOKEN")

    if not SLACK_APP_TOKEN:
        missing.append("SLACK_APP_TOKEN")

    if not EOD_CHANNEL_ID:
        missing.append("EOD_CHANNEL_ID")

    if missing:
        raise RuntimeError(f"Missing required env variables: {', '.join(missing)}")


if __name__ == "__main__":
    validate_env()
    init_db()
    start_scheduler()

    print("EOD Slack Bot is running...")
    print("Available commands: /eod, /eod-summary, /eod-sync-members")

    SocketModeHandler(app, SLACK_APP_TOKEN).start()
