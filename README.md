# X Multi-Account Posting Bot

Post the same (or per-account) tweet to many X accounts from ONE developer app,
billed to that app's single pay-per-use credit balance.

## How authorization works (the part you were unsure about)

X will only let your app post *as* an account if that account has explicitly
granted permission. That grant produces two strings unique to that account:

- **access token**
- **access token secret**

You get these by running `auth.js` while logged in to the target account.
These two strings ARE the "GitHub secret" you store for that account. Without
them your app cannot post as that account.

You do NOT need 56 developer accounts. One app + 56 token pairs is enough.

## Setup

1. In the X Developer Portal, make sure your app has:
   - App permissions: **Read and write** (yours already shows this)
   - A Callback URL is not required for PIN-based auth, but if X complains,
     set it to `oob` or any placeholder like `https://localhost`.

2. Install dependencies:
   ```
   npm install
   ```

3. Authorize YOUR account is already done (the token shown in the portal works
   as `@kreggscode`). For every OTHER account run:

   ```
   X_CONSUMER_KEY=your_consumer_key X_CONSUMER_SECRET=your_consumer_secret node auth.js
   ```

   - It prints a URL. Open it **while logged in as that account**.
   - Click Authorize, copy the PIN, paste it back.
   - It prints a JSON block with `token` + `secret`. Save it.

4. Collect all account blocks into one JSON array and either:
   - save as `accounts.json`, or
   - set it as the GitHub secret `X_ACCOUNTS_JSON` (recommended).

5. Post:
   ```
   node post.js "Hello from my bot"
   ```

## GitHub Secrets (for the Actions workflow)

Create these repository secrets:

- `X_CONSUMER_KEY`      - your app's Consumer Key (API key)
- `X_CONSUMER_SECRET`   - your app's Consumer Secret
- `X_ACCOUNTS_JSON`     - the full JSON array of all account token pairs

Then run the workflow manually (Workflow → Run workflow) and type the tweet.

## Cost note

Each post costs ~$0.015 (or ~$0.20 if it contains a URL) against your app's
pay-per-use balance, for EVERY account. 56 accounts x 1 post = 56 charges.
