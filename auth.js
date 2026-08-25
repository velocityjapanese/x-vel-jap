#!/usr/bin/env node
// ---------------------------------------------------------------------------
// AUTHORIZE A SINGLE X ACCOUNT  (3-legged OAuth 1.0a, localhost redirect)
//
// Double-click auth.bat. It opens your browser to the X authorize page.
// Log in as the TARGET account, click Authorize, and X redirects back to a
// tiny local server that captures the grant and saves the account's
// token+secret into tokens/<account>.json. No PIN typing needed.
//
// REQUIRED: in the X Developer Portal, set your app's Callback URL to:
//   http://localhost:3000/callback
// ---------------------------------------------------------------------------

require('dotenv').config();
const crypto = require('crypto');
const fs = require('fs');
const http = require('http');
const path = require('path');
const { exec } = require('child_process');
const OAuth = require('oauth-1.0a');

const CALLBACK = 'http://localhost:3000/callback';
const PORT = 3000;

const consumerKey = process.env.X_CONSUMER_KEY;
const consumerSecret = process.env.X_CONSUMER_SECRET;
if (!consumerKey || !consumerSecret) {
  console.error('ERROR: X_CONSUMER_KEY / X_CONSUMER_SECRET missing from .env');
  process.exit(1);
}

const oauth = OAuth({
  consumer: { key: consumerKey, secret: consumerSecret },
  signature_method: 'HMAC-SHA1',
  hash_function: (base, key) =>
    crypto.createHmac('sha1', key).update(base).digest('base64'),
});

function signedPost(url, data, token) {
  const requestData = { url, method: 'POST', data };
  const authToken = token ? { key: token.key, secret: token.secret } : undefined;
  const headers = oauth.toHeader(oauth.authorize(requestData, authToken));
  return fetch(url, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/x-www-form-urlencoded' },
  });
}

(async () => {
  let server;
  try {
    // Step 1: request token
    const rtRes = await signedPost('https://api.twitter.com/oauth/request_token', {
      oauth_callback: CALLBACK,
    });
    const rtText = await rtRes.text();
    if (!rtRes.ok) throw new Error('request_token failed: ' + rtText);
    const rt = new URLSearchParams(rtText);

    const authorizeUrl =
      'https://api.twitter.com/oauth/authorize?oauth_token=' + rt.get('oauth_token');

    // Step 2: wait for the browser redirect, then exchange for access token
    const result = await new Promise((resolve, reject) => {
      server = http.createServer(async (req, res) => {
        try {
          const u = new URL(req.url, CALLBACK);
          if (!u.pathname.endsWith('/callback')) {
            res.writeHead(404); res.end(); return;
          }
          const oauthToken = u.searchParams.get('oauth_token');
          const verifier = u.searchParams.get('oauth_verifier');
          if (!verifier) throw new Error('No oauth_verifier in redirect.');

          const atRes = await fetch('https://api.twitter.com/oauth/access_token', {
            method: 'POST',
            headers: {
              ...oauth.toHeader(
                oauth.authorize(
                  { url: 'https://api.twitter.com/oauth/access_token', method: 'POST', data: { oauth_token: oauthToken, oauth_verifier: verifier } },
                  { key: oauthToken, secret: rt.get('oauth_token_secret') }
                )
              ),
              'Content-Type': 'application/x-www-form-urlencoded',
            },
          });
          const atText = await atRes.text();
          if (!atRes.ok) throw new Error('access_token failed: ' + atText);
          const at = new URLSearchParams(atText);
          res.writeHead(200, { 'Content-Type': 'text/html' });
          res.end('<h2>Authorized! You can close this tab and return to the terminal.</h2>');
          resolve({ handle: '@' + at.get('screen_name'), token: at.get('oauth_token'), secret: at.get('oauth_token_secret') });
        } catch (e) {
          res.writeHead(500, { 'Content-Type': 'text/html' });
          res.end('<h2>Authorization failed: ' + e.message + '</h2>');
          reject(e);
        }
      });
      server.listen(PORT, 'localhost', () => {
        console.log('\nOpening browser for authorization...\n');
        exec('start "" "' + authorizeUrl + '"');
      });
    });

    // Step 3: save to its own file
    const dir = 'tokens';
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const name = result.handle.replace(/^@/, '');
    const file = path.join(dir, name + '.json');
    fs.writeFileSync(file, JSON.stringify(result, null, 2));

    console.log('\n=== AUTHORIZED ' + result.handle + ' ===');
    console.log('Saved to: ' + file);
    console.log(JSON.stringify(result, null, 2));
    console.log('\nWhen all accounts are done, run:  node collect.js');
    console.log('and paste its output into the GitHub secret X_ACCOUNTS_JSON.');
  } catch (e) {
    console.error('\nERROR: ' + e.message);
  } finally {
    if (server) server.close();
  }
})();
