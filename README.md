# EOD Bot Setup Guide

This bot sends EOD reminders to Slack using Google Apps Script and Google Forms.

## What it does

- Sends Slack reminder with Google Form link
- Collects EOD updates using Google Form
- Posts EOD summary using Apps Script trigger
- Does not need a laptop/server running

## Setup Steps

### 1. Clone repo

git clone <repo-url>
cd EOD-BOT

### 2. Install clasp

npm install -g @google/clasp

### 3. Login to Google

clasp login

### 4. Create or connect Apps Script project

If using existing Apps Script project:

clasp clone <SCRIPT_ID>

If using a new one, create Apps Script project first, then push code.

### 5. Push code

clasp push

### 6. Add Slack bot token

In Apps Script:

Project Settings → Script Properties

Add:

SLACK_BOT_TOKEN = xoxb-your-token

Do not commit this token to Git.

### 7. Update Slack channel IDs

In Code.js, update the channel IDs for the Slack channels where reminders/summaries should be posted.

Example:

const MAIN_EOD_CHANNEL_ID = "CXXXXXXXXXX";

Use Slack channel IDs, not channel names.

### 8. Add bot to Slack channel

In Slack channel, add the bot:

/invite @your-bot-name

Or:

Channel → Integrations → Add apps

### 9. Run setup

In Apps Script editor, run:

setupAllEodGroups

This creates forms and required triggers.

### 10. Set trigger times manually

In Apps Script:

Triggers → edit trigger time

Example:

Reminder: 6 PM to 7 PM
Summary: 9 PM to 10 PM

### 11. Test

Run these functions manually from Apps Script:

postEodReminder
postEodSummary

Check Slack to confirm messages are posted.

## Important Notes

- Do not commit Slack tokens.
- Bot must be added to every Slack channel it posts to.
- Use channel IDs like C123 or G123, not channel names.
- Apps Script triggers run within a time window, not exact minute.
