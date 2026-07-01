# EOD Bot

Google Apps Script based Slack bot for sending EOD reminders.

## What it does

- Sends an EOD reminder to Slack
- Shares a Google Form link for collecting updates
- Runs using Google Apps Script triggers
- Does not require a laptop or server to stay running

## Setup

1. Configure the Slack bot token in Apps Script Script Properties:

SLACK_BOT_TOKEN

2. Configure the required channel IDs in the Apps Script code.

3. Run the setup function from Apps Script.

4. Set up Apps Script triggers for the reminder.

## Notes

- Do not commit Slack tokens or secrets.
- The bot uses Slack API and Google Apps Script.
