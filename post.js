#!/usr/bin/env node
// ---------------------------------------------------------------------------
// POST A TWEET TO ONE OR MORE X ACCOUNTS
//
// Accounts are read from (in priority order):
//   1. env X_ACCOUNTS_JSON  -> a JSON array (recommended for GitHub Actions)
//   2. local file accounts.json
//
// Each account entry needs the token + secret produced by auth.js:
//   { "handle": "@account", "token": "...", "secret": "..." }
//
// Billing is at the APP level: every post draws from your one developer
// app's pay-per-use credit balance, regardless of which account it posts as.
//
// Usage:
//   node post.js "Your tweet text here"
// ---------------------------------------------------------------------------

require('dotenv').config();
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const OAuth = require('oauth-1.0a');

const consumerKey = process.env.X_CONSUMER_KEY;
const consumerSecret = process.env.X_CONSUMER_SECRET;

if (!consumerKey || !consumerSecret) {
  console.error('ERROR: set X_CONSUMER_KEY and X_CONSUMER_SECRET.');
  process.exit(1);
}

const text = process.argv[2];
if (!text) {
  console.error('Usage: node post.js "tweet text"');
  process.exit(1);
}

let accounts;
if (process.env.X_ACCOUNTS_JSON) {
  accounts = JSON.parse(process.env.X_ACCOUNTS_JSON);
} else {
  const dir = 'tokens';
  if (fs.existsSync(dir)) {
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
    accounts = files.map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')));
  }
  if (!accounts || accounts.length === 0) {
    console.error('ERROR: set X_ACCOUNTS_JSON, or add account files under tokens/');
    process.exit(1);
  }
}

const oauth = OAuth({
  consumer: { key: consumerKey, secret: consumerSecret },
  signature_method: 'HMAC-SHA1',
  hash_function: (base, key) =>
    crypto.createHmac('sha1', key).update(base).digest('base64'),
});

async function postAs(account) {
  const url = 'https://api.twitter.com/2/tweets';
  const requestData = { url, method: 'POST', data: { text } };
  const token = { key: account.token, secret: account.secret };
  const headers = oauth.toHeader(oauth.authorize(requestData, token));
  const res = await fetch(url, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  const json = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(json));
  return json;
}

(async () => {
  for (const acc of accounts) {
    try {
      const r = await postAs(acc);
      console.log(`OK   posted as ${acc.handle || acc.token} -> tweet id ${r.data.id}`);
    } catch (e) {
      console.error(`FAIL ${acc.handle || acc.token}: ${e.message}`);
    }
  }
})();
