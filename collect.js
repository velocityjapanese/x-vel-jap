#!/usr/bin/env node
// Collect every account token file in tokens/ into one JSON array,
// ready to paste into the GitHub secret X_ACCOUNTS_JSON.
const fs = require('fs');
const path = require('path');

const dir = 'tokens';
if (!fs.existsSync(dir)) {
  console.error('No tokens/ folder found. Run auth.bat for each account first.');
  process.exit(1);
}

const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
const accounts = files.map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')));

console.log(JSON.stringify(accounts, null, 2));
console.log('\n=> ' + accounts.length + ' account(s). Paste the JSON above into');
console.log('   the GitHub secret X_ACCOUNTS_JSON.');
