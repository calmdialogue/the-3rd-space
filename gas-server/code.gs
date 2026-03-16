/**
 * Minimal LINE ↔ GAS ↔ OpenAI bridge (v0)
 * - Receives text messages from LINE webhook
 * - Calls OpenAI Responses API
 * - Replies via LINE Reply API
 *
 * Required Script Properties:
 * - LINE_CHANNEL_ACCESS_TOKEN
 * - OPENAI_API_KEY
 */

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents || "{}");

    // LINE webhook payload has "events" array
    if (!body.events || !Array.isArray(body.events)) {
      return jsonResponse({ ok: true, note: "No events (probably non-LINE request)" });
    }

    for (const ev of body.events) {
      // Handle only message(text) for the minimal smoke test
      if (ev.type === "message" && ev.message && ev.message.type === "text") {
        const replyToken = ev.replyToken;
        const userText = (ev.message.text || "").trim();

        // Ignore empty
        if (!userText) continue;

        // Call OpenAI
        const aiText = callOpenAI_Text(userText);

        // Reply to LINE
        replyLineText(replyToken, aiText);
      } else {
        // For now, ignore other event types (postback, follow, join, etc.)
        continue;
      }
    }

    return jsonResponse({ ok: true });
  } catch (err) {
    // Never throw to LINE; return 200 with error to avoid retries storm
    return jsonResponse({ ok: false, error: String(err && err.stack ? err.stack : err) });
  }
}

function callOpenAI_Text(userText) {
  const apiKey = getProp_("OPENAI_API_KEY");

  // Use a stable text model. (gpt-4.1-mini is documented for Responses usage)
  // You can swap later.
  const payload = {
    model: "gpt-4.1-mini",
    input: [
      {
        role: "system",
        content: [
          {
            type: "input_text",
            text:
              "You are a calm, neutral counselor assistant. Reply in Japanese. Keep it concise and non-judgmental.",
          },
        ],
      },
      {
        role: "user",
        content: [{ type: "input_text", text: userText }],
      },
    ],
  };

  const res = UrlFetchApp.fetch("https://api.openai.com/v1/responses", {
    method: "post",
    contentType: "application/json",
    headers: {
      Authorization: "Bearer " + apiKey,
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });

  const status = res.getResponseCode();
  const text = res.getContentText();

  if (status < 200 || status >= 300) {
    // Surface minimal error to user (avoid leaking keys)
    return "（エラー）OpenAI API呼び出しに失敗しました。status=" + status;
  }

  const json = JSON.parse(text);

  // Robust extraction:
  // - SDKs expose output_text, but raw JSON might not always include it.
  // Try json.output_text first, else scan json.output array.
  if (typeof json.output_text === "string" && json.output_text.trim()) {
    return json.output_text.trim();
  }

  const extracted = extractOutputText_(json);
  return extracted || "（空）";
}

function extractOutputText_(json) {
  // Attempt to traverse Responses API output structure
  // Typical shape: { output: [ { type: "...", content: [ { type:"output_text", text:"..." } ] } ] }
  const out = json && json.output;
  if (!Array.isArray(out)) return "";

  let acc = [];
  for (const item of out) {
    // Some items might be "message"
    const content = item && item.content;
    if (!Array.isArray(content)) continue;

    for (const part of content) {
      if (!part) continue;
      if (part.type === "output_text" && typeof part.text === "string") {
        acc.push(part.text);
      }
      // Sometimes content parts may be nested; ignore for v0
    }
  }
  return acc.join("\n").trim();
}

function replyLineText(replyToken, messageText) {
  const token = getProp_("LINE_CHANNEL_ACCESS_TOKEN");

  // LINE has message length limits; keep safe
  const safeText = (messageText || "").toString().slice(0, 4500);

  const payload = {
    replyToken: replyToken,
    messages: [{ type: "text", text: safeText }],
  };

  const res = UrlFetchApp.fetch("https://api.line.me/v2/bot/message/reply", {
    method: "post",
    contentType: "application/json",
    headers: {
      Authorization: "Bearer " + token,
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });

  const status = res.getResponseCode();
  if (status < 200 || status >= 300) {
    // If reply fails, log for debugging
    console.log("LINE reply failed status=", status, "body=", res.getContentText());
  }
}

function getProp_(key) {
  const v = PropertiesService.getScriptProperties().getProperty(key);
  if (!v) throw new Error("Missing Script Property: " + key);
  return v;
}

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}