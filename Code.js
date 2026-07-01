const PROP_SLACK_BOT_TOKEN = "SLACK_BOT_TOKEN";
const PROP_EOD_CHANNEL_ID = "EOD_CHANNEL_ID";
const PROP_FORM_ID = "EOD_FORM_ID";
const PROP_FORM_URL = "EOD_FORM_URL";

const Q_NAME = "Your name";
const Q_COMPLETED = "What did you complete today?";
const Q_TOMORROW = "What are you planning for tomorrow?";
const Q_BLOCKER = "Any blockers?";
const Q_BLOCKER_DETAILS = "Blocker details";
const Q_HELP = "Help needed from anyone?";
const Q_STATUS = "Overall status";

function getProp(name) {
  return PropertiesService.getScriptProperties().getProperty(name);
}

function setProp(name, value) {
  PropertiesService.getScriptProperties().setProperty(name, value);
}

function todayStr() {
  return Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd");
}

function dateStr(date) {
  return Utilities.formatDate(date, Session.getScriptTimeZone(), "yyyy-MM-dd");
}

function slackApi(method, payload) {
  const token = getProp(PROP_SLACK_BOT_TOKEN);

  const response = UrlFetchApp.fetch(`https://slack.com/api/${method}`, {
    method: "post",
    contentType: "application/json",
    headers: {
      Authorization: `Bearer ${token}`
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  const result = JSON.parse(response.getContentText());

  if (!result.ok) {
    console.log(`Slack API error ${method}: ${JSON.stringify(result)}`);
  }

  return result;
}

function createEodForm() {
  let formId = getProp(PROP_FORM_ID);

  if (formId) {
    const existingForm = FormApp.openById(formId);
    setProp(PROP_FORM_URL, existingForm.getPublishedUrl());
    return existingForm.getPublishedUrl();
  }

  const form = FormApp.create("EOD Update Form");

  form.setDescription("Submit your daily EOD update.");
  form.setCollectEmail(false);
  form.setAllowResponseEdits(true);
  form.setLimitOneResponsePerUser(false);

  form.addTextItem()
    .setTitle(Q_NAME)
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle(Q_COMPLETED)
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle(Q_TOMORROW)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle(Q_BLOCKER)
    .setRequired(true)
    .setChoiceValues(["No", "Yes"]);

  form.addParagraphTextItem()
    .setTitle(Q_BLOCKER_DETAILS)
    .setRequired(false);

  form.addParagraphTextItem()
    .setTitle(Q_HELP)
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle(Q_STATUS)
    .setRequired(true)
    .setChoiceValues(["Green", "Yellow", "Red"]);

  setProp(PROP_FORM_ID, form.getId());
  setProp(PROP_FORM_URL, form.getPublishedUrl());

  return form.getPublishedUrl();
}

function getFormUrl() {
  let formUrl = getProp(PROP_FORM_URL);

  if (!formUrl) {
    formUrl = createEodForm();
  }

  return formUrl;
}

function postEodReminder() {
  const channelId = "C0ALYC9T0N5";
  const formUrl = getFormUrl();

  slackApi("chat.postMessage", {
    channel: channelId,
    text:
      ":spiral_calendar_pad: *EOD Reminder*\n" +
      "Please submit your EOD update here:\n" +
      formUrl
  });

  return "Reminder posted.";
}

function parseFormResponsesForDate(targetDate) {
  const formId = getProp(PROP_FORM_ID);
  if (!formId) return [];

  const form = FormApp.openById(formId);
  const responses = form.getResponses();

  const latestByName = {};

  responses.forEach(response => {
    const responseDate = dateStr(response.getTimestamp());
    if (responseDate !== targetDate) return;

    const row = {
      date: responseDate,
      timestamp: response.getTimestamp(),
      user_name: "",
      completed_today: "",
      plan_tomorrow: "",
      has_blocker: "",
      blocker_details: "",
      help_needed: "",
      status: ""
    };

    response.getItemResponses().forEach(itemResponse => {
      const title = itemResponse.getItem().getTitle();
      const answer = itemResponse.getResponse();

      if (title === Q_NAME) {
        row.user_name = answer;
      } else if (title === Q_COMPLETED) {
        row.completed_today = answer;
      } else if (title === Q_TOMORROW) {
        row.plan_tomorrow = answer;
      } else if (title === Q_BLOCKER) {
        row.has_blocker = answer;
      } else if (title === Q_BLOCKER_DETAILS) {
        row.blocker_details = answer;
      } else if (title === Q_HELP) {
        row.help_needed = answer;
      } else if (title === Q_STATUS) {
        row.status = answer;
      }
    });

    if (!row.user_name) return;

    const key = row.user_name.trim().toLowerCase();
    const existing = latestByName[key];

    if (!existing || row.timestamp > existing.timestamp) {
      latestByName[key] = row;
    }
  });

  return Object.values(latestByName).sort((a, b) => a.user_name.localeCompare(b.user_name));
}

function generateSummary(date) {
  const updates = parseFormResponsesForDate(date);

  let green = 0;
  let yellow = 0;
  let red = 0;

  const completedLines = [];
  const tomorrowLines = [];
  const blockerLines = [];
  const helpLines = [];

  updates.forEach(update => {
    if (update.status === "Green") green++;
    if (update.status === "Yellow") yellow++;
    if (update.status === "Red") red++;

    completedLines.push(`• *${update.user_name}:* ${update.completed_today}`);
    tomorrowLines.push(`• *${update.user_name}:* ${update.plan_tomorrow}`);

    if (update.has_blocker === "Yes") {
      blockerLines.push(`• :warning: *${update.user_name}:* ${update.blocker_details || "No details provided"}`);
    }

    if (update.help_needed) {
      helpLines.push(`• *${update.user_name}:* ${update.help_needed}`);
    }
  });

  let summary = `*EOD Summary — ${date}*\n\n`;

  summary += `*Submissions:*\n`;
  summary += `• Submitted: ${updates.length}\n\n`;

  summary += `*Status:*\n`;
  summary += `• :large_green_circle: Green: ${green}\n`;
  summary += `• :large_yellow_circle: Yellow: ${yellow}\n`;
  summary += `• :red_circle: Red: ${red}\n\n`;

  summary += `*Completed Today:*\n`;
  summary += completedLines.length ? completedLines.join("\n") : "No updates submitted";
  summary += `\n\n`;

  summary += `*Plan for Tomorrow:*\n`;
  summary += tomorrowLines.length ? tomorrowLines.join("\n") : "No plans submitted";
  summary += `\n\n`;

  summary += `*Blockers:*\n`;
  summary += blockerLines.length ? blockerLines.join("\n") : "No blockers reported";
  summary += `\n\n`;

  summary += `*Help Needed:*\n`;
  summary += helpLines.length ? helpLines.join("\n") : "No help requests";

  return summary;
}

function postEodSummary() {
  const channelId = "C0ALYC9T0N5";
  const summary = generateSummary(todayStr());

  slackApi("chat.postMessage", {
    channel: channelId,
    text: summary
  });

  return "Summary posted.";
}

function setupDailyTriggers() {
  ScriptApp.getProjectTriggers().forEach(trigger => {
    const fn = trigger.getHandlerFunction();

    if (fn === "postEodReminder" || fn === "postEodSummary") {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  ScriptApp.newTrigger("postEodReminder")
    .timeBased()
    .everyDays(1)
    .atHour(18)
    .create();

  ScriptApp.newTrigger("postEodSummary")
    .timeBased()
    .everyDays(1)
    .atHour(21)
    .create();

  return "Daily triggers created.";
}

function setupAll() {
  const formUrl = createEodForm();
  setupDailyTriggers();

  return "Setup complete. Form URL: " + formUrl;
}


function postEodSummary() {
  const summaryChannelIds = [
    "C0ALYC9T0N5",
    "C0AKFH5A406",
    "C0AVBEWQX7T"
  ];

  const summary = generateSummary(todayStr());

  summaryChannelIds.forEach(function(channelId) {
    slackApi("chat.postMessage", {
      channel: channelId,
      text: summary
    });
  });

  return "Summary posted to " + summaryChannelIds.length + " channel(s).";
}


/***********************
 * SAFE TEST FUNCTIONS
 * These post only to the current working/test channel.
 ***********************/

const TEST_CHANNEL_ID = "C0ALYC9T0N5"; // v2d-multi-view-data-collection test channel


function previewMainSummary() {
  const summary = generateSummary(todayStr());
  console.log(summary);
  return summary;
}


function previewEgoSummary() {
  const formId = getProp(PROP_EGO_FORM_ID);
  const updates = parseResponsesForFormId(formId, todayStr());
  const summary = generateSummaryFromUpdates("EGO EOD Summary", todayStr(), updates);
  console.log(summary);
  return summary;
}


function postMainReminderToTestChannel() {
  const formUrl = getFormUrl();

  slackApi("chat.postMessage", {
    channel: TEST_CHANNEL_ID,
    text:
      ":test_tube: *TEST - Main EOD Reminder*\n" +
      "Please submit your EOD update here:\n" +
      formUrl
  });

  return "Test main reminder posted.";
}


function postEgoReminderToTestChannel() {
  const formUrl = getEgoFormUrl();

  slackApi("chat.postMessage", {
    channel: TEST_CHANNEL_ID,
    text:
      ":test_tube: *TEST - EGO EOD Reminder*\n" +
      "Please submit your EGO EOD update here:\n" +
      formUrl
  });

  return "Test ego reminder posted.";
}


function postMainSummaryToTestChannel() {
  const summary = generateSummary(todayStr());

  slackApi("chat.postMessage", {
    channel: TEST_CHANNEL_ID,
    text: ":test_tube: *TEST MAIN/LAB SUMMARY*\n\n" + summary
  });

  return "Test main summary posted.";
}


function postEgoSummaryToTestChannel() {
  const formId = getProp(PROP_EGO_FORM_ID);
  const updates = parseResponsesForFormId(formId, todayStr());
  const summary = generateSummaryFromUpdates("EGO EOD Summary", todayStr(), updates);

  slackApi("chat.postMessage", {
    channel: TEST_CHANNEL_ID,
    text: ":test_tube: *TEST EGO SUMMARY*\n\n" + summary
  });

  return "Test ego summary posted.";
}


/***********************
 * EGO EOD FUNCTIONS
 * These are available for manual use or future triggers.
 * They are NOT automatically scheduled unless triggers are added manually.
 ***********************/

const EGO_EOD_CHANNEL_ID_MANUAL = "C0AKFH5A406"; // v2d-ego-data-collection
const EGO_FORM_ID_PROP_MANUAL = "EGO_EOD_FORM_ID";
const EGO_FORM_URL_PROP_MANUAL = "EGO_EOD_FORM_URL";


function createEgoEodForm() {
  let formId = getProp(EGO_FORM_ID_PROP_MANUAL);

  if (formId) {
    const existingForm = FormApp.openById(formId);
    setProp(EGO_FORM_URL_PROP_MANUAL, existingForm.getPublishedUrl());
    return existingForm.getPublishedUrl();
  }

  const form = FormApp.create("EGO EOD Update Form");

  form.setDescription("Submit your daily EGO EOD update.");
  form.setCollectEmail(false);
  form.setAllowResponseEdits(true);
  form.setLimitOneResponsePerUser(false);

  form.addTextItem()
    .setTitle(Q_NAME)
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle(Q_COMPLETED)
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle(Q_TOMORROW)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle(Q_BLOCKER)
    .setRequired(true)
    .setChoiceValues(["No", "Yes"]);

  form.addParagraphTextItem()
    .setTitle(Q_BLOCKER_DETAILS)
    .setRequired(false);

  form.addParagraphTextItem()
    .setTitle(Q_HELP)
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle(Q_STATUS)
    .setRequired(true)
    .setChoiceValues(["Green", "Yellow", "Red"]);

  setProp(EGO_FORM_ID_PROP_MANUAL, form.getId());
  setProp(EGO_FORM_URL_PROP_MANUAL, form.getPublishedUrl());

  return form.getPublishedUrl();
}


function getEgoFormUrl() {
  let formUrl = getProp(EGO_FORM_URL_PROP_MANUAL);

  if (!formUrl) {
    formUrl = createEgoEodForm();
  }

  return formUrl;
}


function postEgoEodReminder() {
  const formUrl = getEgoFormUrl();

  slackApi("chat.postMessage", {
    channel: EGO_EOD_CHANNEL_ID_MANUAL,
    text:
      ":spiral_calendar_pad: *EGO EOD Reminder*\n" +
      "Please submit your EGO EOD update here:\n" +
      formUrl
  });

  return "Ego EOD reminder posted.";
}


function postEgoEodSummary() {
  const formId = getProp(EGO_FORM_ID_PROP_MANUAL);
  const updates = parseResponsesForFormId(formId, todayStr());
  const summary = generateSummaryFromUpdates("EGO EOD Summary", todayStr(), updates);

  slackApi("chat.postMessage", {
    channel: EGO_EOD_CHANNEL_ID_MANUAL,
    text: summary
  });

  return "Ego EOD summary posted.";
}
