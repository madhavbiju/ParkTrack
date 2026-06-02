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
      } else {
        await sendTelegramMessage(chatId, "⚠️ Unknown command. Use:\n- `/add <keyword>`\n- `/remove <keyword>`\n- `/list`", env);
      }

      return new Response('OK');
    } catch (err) {
      console.error('Error handling webhook:', err);
      return new Response('Internal Server Error', { status: 500 });
    }
  }
};

// 1. Welcome and Help Message
async function handleStart(chatId, env) {
  const message = `🚀 *Welcome to Park Track!* 🚀\n\n` +
    `I can notify you whenever a job matching your keywords is posted on *Technopark* or *Infopark*.\n\n` +
    `*Available Commands:*\n` +
    `• \`/add <keyword>\` — Subscribe to a keyword (e.g. \`/add react\`)\n` +
    `• \`/remove <keyword>\` — Unsubscribe from a keyword (e.g. \`/remove react\`)\n` +
    `• \`/list\` — View all your active keyword subscriptions\n\n` +
    `Let's get started! Try adding your first keyword.`;
  await sendTelegramMessage(chatId, message, env);
}

// 2. Add Subscription
async function handleAdd(chatId, text, env) {
  const rawKeyword = text.slice(4).trim();
  if (!rawKeyword) {
    await sendTelegramMessage(chatId, "❌ Please specify a keyword.\nUsage: \`/add <keyword>\` (e.g. \`/add python\`)", env);
    return;
  }

  // Sanitize keyword: strip special chars, force to lowercase, cap at 30 chars
  // We allow alphanumerics, spaces, dots, and hyphens (useful for next.js, .net, react.js, etc.)
  const sanitizedKeyword = rawKeyword
    .toLowerCase()
    .replace(/[^a-z0-9\s.-]/g, '')
    .trim()
    .substring(0, 30);

  if (!sanitizedKeyword) {
    await sendTelegramMessage(chatId, "❌ Invalid keyword. Only alphanumeric characters, dots, and hyphens are allowed.", env);
    return;
  }

  // Insert into Supabase subscriptions table
  const url = `${env.SUPABASE_URL}/rest/v1/subscriptions`;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'apikey': env.SUPABASE_SERVICE_ROLE_KEY,
      'Authorization': `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
      'Content-Type': 'application/json',
      'Prefer': 'resolution=merge-duplicates'
    },
    body: JSON.stringify({
      chat_id: chatId,
      keyword: sanitizedKeyword,
      sources: ['technopark', 'infopark'] // Default to both sources
    })
  });

  if (response.ok) {
    await sendTelegramMessage(chatId, `✅ Subscribed to keyword: \`${sanitizedKeyword}\` for both Technopark and Infopark jobs.`, env);
  } else {
    const errText = await response.text();
    console.error('Supabase Add Error:', errText);
    await sendTelegramMessage(chatId, "❌ An error occurred while saving your subscription. Please try again later.", env);
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
  const url = `${env.SUPABASE_URL}/rest/v1/subscriptions?${query}`;
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

// 4. List Subscriptions
async function handleList(chatId, env) {
  // Query Supabase subscriptions table
  const query = `chat_id=eq.${chatId}&select=keyword,sources`;
  const url = `${env.SUPABASE_URL}/rest/v1/subscriptions?${query}`;
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
    await sendTelegramMessage(chatId, "ℹ️ You do not have any active subscriptions. Use \`/add <keyword>\` to subscribe.", env);
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
