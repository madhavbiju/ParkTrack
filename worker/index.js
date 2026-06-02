/**
 * Cloudflare Worker for Telegram Bot Webhook
 * Handles user subscriptions and interacts with Supabase PostgREST API.
 */

export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'POST') {
      return new Response('Only POST requests allowed', { status: 405 });
    }

    try {
      const update = await request.json();
      if (!update.message || !update.message.text || !update.message.chat) {
        return new Response('OK'); // Ignore non-message updates
      }

      const chatId = update.message.chat.id;
      const text = update.message.text.trim();

      // Handle standard Telegram commands
      if (text.startsWith('/start')) {
        await handleStart(chatId, env);
      } else if (text.startsWith('/add')) {
        await handleAdd(chatId, text, env);
      } else if (text.startsWith('/remove')) {
        await handleRemove(chatId, text, env);
      } else if (text.startsWith('/list')) {
        await handleList(chatId, env);
      } else if (text.startsWith('/sources')) {
        await handleSources(chatId, text, env);
      } else if (text.startsWith('/about')) {
        await handleAbout(chatId, env);
      } else {
        await sendTelegramMessage(
          chatId, 
          "⚠️ Unknown command. Use:\n" +
          "• `/add <keywords>` — Add subscriptions\n" +
          "• `/remove <keyword>` — Remove a subscription\n" +
          "• `/sources <technopark|infopark|both>` — Change job sources\n" +
          "• `/about` — About this bot\n" +
          "• `/list` — View your subscriptions", 
          env
        );
      }

      return new Response('OK');
    } catch (err) {
      console.error('Error handling webhook:', err);
      return new Response('Internal Server Error', { status: 500 });
    }
  }
};

// 1. Welcome and Onboarding Guide Message
async function handleStart(chatId, env) {
  const message = `🚀 *Welcome to Park Track!* 🚀\n\n` +
    `I will notify you in real-time when new job matching your keywords are posted on *Technopark* or *Infopark*.\n\n` +
    `*Step 1: Add your keywords*\n` +
    `You can subscribe to keywords (case-insensitive) one by one or as a comma-separated list:\n` +
    `• \`/add react, next.js, nodejs\`\n` +
    `• \`/add python\`\n` +
    `*(Note: You can add up to 6 active keywords)*\n\n` +
    `*Step 2: Choose your job sources*\n` +
    `By default, you listen to *both* parks. Change this anytime for all your subscriptions using:\n` +
    `• \`/sources technopark\` — Only Technopark\n` +
    `• \`/sources infopark\` — Only Infopark\n` +
    `• \`/sources both\` — Both IT Parks\n\n` +
    `*Manage subscriptions:*\n` +
    `• \`/list\` — View active keywords and sources\n` +
    `• \`/remove <keyword>\` — Remove a subscription`;
  await sendTelegramMessage(chatId, message, env);
}

// 2. Add Subscription (Supports comma-separated inputs, sources inheritance, & hard limit of 6)
async function handleAdd(chatId, text, env) {
  const rawInput = text.slice(4).trim();
  if (!rawInput) {
    await sendTelegramMessage(chatId, "❌ Please specify at least one keyword.\nUsage: \`/add <keyword1, keyword2, ...>\` (e.g. \`/add react, python\`)", env);
    return;
  }

  // Split by comma for multi-keyword support
  const rawKeywords = rawInput.split(',');
  let sanitizedKeywords = [];

  for (let raw of rawKeywords) {
    const sanitized = raw
      .toLowerCase()
      .replace(/[^a-z0-9\s.-]/g, '')
      .trim()
      .substring(0, 30);
    if (sanitized && !sanitizedKeywords.includes(sanitized)) {
      sanitizedKeywords.push(sanitized);
    }
  }

  if (sanitizedKeywords.length === 0) {
    await sendTelegramMessage(chatId, "❌ Invalid keywords. Only alphanumeric characters, dots, and hyphens are allowed.", env);
    return;
  }

  // 1. Fetch current subscriptions for this user to check counts and handle duplicates
  let existingCount = 0;
  let userSources = ['technopark', 'infopark']; // Default sources fallback
  const getQuery = `chat_id=eq.${chatId}&select=keyword,sources`;
  const getUrl = env.SUPABASE_URL.endsWith('/') ? `${env.SUPABASE_URL}subscriptions?${getQuery}` : `${env.SUPABASE_URL}/subscriptions?${getQuery}`;
  
  try {
    const getResponse = await fetch(getUrl, {
      method: 'GET',
      headers: {
        'apikey': env.SUPABASE_SERVICE_ROLE_KEY,
        'Authorization': `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`
      }
    });
    if (getResponse.ok) {
      const existing = await getResponse.json();
      existingCount = existing.length;
      
      // Inherit sources preference if they already have subscriptions
      if (existingCount > 0) {
        userSources = existing[0].sources;
      }
      
      // Deduplicate: filter out keywords the user is already subscribed to
      const existingKeywords = existing.map(item => item.keyword);
      sanitizedKeywords = sanitizedKeywords.filter(k => !existingKeywords.includes(k));
      
      if (sanitizedKeywords.length === 0) {
        await sendTelegramMessage(chatId, "ℹ️ You are already subscribed to all of these keywords.", env);
        return;
      }
    }
  } catch (err) {
    console.error("Error querying existing subscriptions:", err);
  }

  // 2. Enforce the hard limit of 6 active subscriptions
  const MAX_LIMIT = 6;
  if (existingCount + sanitizedKeywords.length > MAX_LIMIT) {
    const remaining = MAX_LIMIT - existingCount;
    if (remaining <= 0) {
      await sendTelegramMessage(
        chatId, 
        `❌ You have reached the limit of ${MAX_LIMIT} keyword subscriptions. Please remove some using \`/remove <keyword>\` before adding more.`, 
        env
      );
    } else {
      await sendTelegramMessage(
        chatId, 
        `❌ Adding these keywords would exceed your limit of ${MAX_LIMIT} subscriptions. You currently have ${existingCount} active and can only add ${remaining} more.`, 
        env
      );
    }
    return;
  }

  // Build bulk insert payload
  const payload = sanitizedKeywords.map(keyword => ({
    chat_id: chatId,
    keyword: keyword,
    sources: userSources
  }));

  // Insert into Supabase subscriptions table using PostgREST bulk insert
  const url = env.SUPABASE_URL.endsWith('/') ? `${env.SUPABASE_URL}subscriptions` : `${env.SUPABASE_URL}/subscriptions`;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'apikey': env.SUPABASE_SERVICE_ROLE_KEY,
      'Authorization': `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
      'Content-Type': 'application/json',
      'Prefer': 'resolution=merge-duplicates'
    },
    body: JSON.stringify(payload)
  });

  if (response.ok) {
    const listStr = sanitizedKeywords.map(k => `\`${k}\``).join(', ');
    await sendTelegramMessage(
      chatId, 
      `✅ Subscribed to keyword(s): ${listStr}\n` +
      `Job Sources: *${userSources.join(', ')}*\n` +
      `Total subscriptions: *${existingCount + sanitizedKeywords.length}/${MAX_LIMIT}*`, 
      env
    );
  } else {
    const errText = await response.text();
    console.error('Supabase Add Error:', errText);
    await sendTelegramMessage(chatId, "❌ An error occurred while saving your subscriptions. Please try again later.", env);
  }
}

// 3. Remove Subscription
async function handleRemove(chatId, text, env) {
  const rawKeyword = text.slice(7).trim();
  if (!rawKeyword) {
    await sendTelegramMessage(chatId, "❌ Please specify a keyword to remove.\nUsage: \`/remove <keyword>\` (e.g. \`/remove python\`)", env);
    return;
  }

  const sanitizedKeyword = rawKeyword
    .toLowerCase()
    .replace(/[^a-z0-9\s.-]/g, '')
    .trim()
    .substring(0, 30);

  // Delete from Supabase subscriptions table
  const query = `chat_id=eq.${chatId}&keyword=eq.${sanitizedKeyword}`;
  const url = env.SUPABASE_URL.endsWith('/') ? `${env.SUPABASE_URL}subscriptions?${query}` : `${env.SUPABASE_URL}/subscriptions?${query}`;
  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      'apikey': env.SUPABASE_SERVICE_ROLE_KEY,
      'Authorization': `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`
    }
  });

  if (response.ok) {
    await sendTelegramMessage(chatId, `🗑️ Unsubscribed from keyword: \`${sanitizedKeyword}\`.`, env);
  } else {
    const errText = await response.text();
    console.error('Supabase Delete Error:', errText);
    await sendTelegramMessage(chatId, "❌ An error occurred while removing your subscription.", env);
  }
}

// 4. Update job sources for all active subscriptions
async function handleSources(chatId, text, env) {
  const rawInput = text.slice(8).trim().toLowerCase();
  
  let sources;
  let label;
  
  if (rawInput === 'both') {
    sources = ['technopark', 'infopark'];
    label = 'both Technopark and Infopark';
  } else if (rawInput === 'technopark') {
    sources = ['technopark'];
    label = 'Technopark only';
  } else if (rawInput === 'infopark') {
    sources = ['infopark'];
    label = 'Infopark only';
  } else {
    await sendTelegramMessage(
      chatId, 
      "❌ Invalid source parameter. Choose one of the following:\n" +
      "• `/sources both`\n" +
      "• `/sources technopark`\n" +
      "• `/sources infopark`", 
      env
    );
    return;
  }

  // Update sources for all existing user subscriptions
  const query = `chat_id=eq.${chatId}`;
  const url = env.SUPABASE_URL.endsWith('/') ? `${env.SUPABASE_URL}subscriptions?${query}` : `${env.SUPABASE_URL}/subscriptions?${query}`;
  
  const response = await fetch(url, {
    method: 'PATCH',
    headers: {
      'apikey': env.SUPABASE_SERVICE_ROLE_KEY,
      'Authorization': `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ sources: sources })
  });

  if (response.ok) {
    await sendTelegramMessage(chatId, `🎯 Your job sources have been updated to *${label}* for all your active subscriptions!`, env);
  } else {
    const errText = await response.text();
    console.error('Supabase Patch Error:', errText);
    await sendTelegramMessage(chatId, "❌ An error occurred while updating your sources.", env);
  }
}

// 5. List Subscriptions
async function handleList(chatId, env) {
  // Query Supabase subscriptions table
  const query = `chat_id=eq.${chatId}&select=keyword,sources`;
  const url = env.SUPABASE_URL.endsWith('/') ? `${env.SUPABASE_URL}subscriptions?${query}` : `${env.SUPABASE_URL}/subscriptions?${query}`;
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'apikey': env.SUPABASE_SERVICE_ROLE_KEY,
      'Authorization': `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`
    }
  });

  if (!response.ok) {
    const errText = await response.text();
    console.error('Supabase List Error:', errText);
    await sendTelegramMessage(chatId, "❌ An error occurred while retrieving your subscriptions.", env);
    return;
  }

  const subscriptions = await response.json();
  if (subscriptions.length === 0) {
    await sendTelegramMessage(chatId, "ℹ️ You do not have any active subscriptions. Use \`/add <keywords>\` to subscribe.", env);
    return;
  }

  let message = "📝 *Your Active Subscriptions:*\n";
  subscriptions.forEach(sub => {
    message += `• \`${sub.keyword}\` (${sub.sources.join(', ')})\n`;
  });
  await sendTelegramMessage(chatId, message, env);
}

// Telegram Helper function
async function sendTelegramMessage(chatId, text, env) {
  const url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      chat_id: chatId,
      text: text,
      parse_mode: 'Markdown'
    })
  });
  if (!response.ok) {
    const errText = await response.text();
    console.error('Telegram Send Error:', errText);
  }
}

// 6. About Command
async function handleAbout(chatId, env) {
  const message = `ℹ️ *About Park Track*\n\n` +
    `Park Track is a highly-scalable, zero-cost job notification bot designed to monitor Technopark and Infopark job openings in real-time.\n\n` +
    `👤 *Developer:* Madhav Biju (@madhavbiju)\n` +
    `📂 *GitHub Repository:* [madhavbiju/ParkTrack](https://github.com/madhavbiju/ParkTrack)\n\n` +
    `Feel free to check out the code, report issues, or contribute!`;
  await sendTelegramMessage(chatId, message, env);
}
