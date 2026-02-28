# Upstox Access Token Refresh Guide

## Why Tokens Expire

Upstox access tokens expire **daily** for security reasons. You need to generate a new token each day before running the dry run.

## How to Generate New Token

### Method 1: Upstox Developer Console (Recommended)

1. Go to https://api.upstox.com/
2. Login with your Upstox credentials
3. Navigate to **Apps** → **Your App**
4. Click **Generate Token**
5. Authorize the app
6. Copy the new access token

### Method 2: OAuth Flow (Advanced)

If you want to automate token refresh, you'll need to implement the full OAuth flow:

1. Get authorization code
2. Exchange for access token
3. Store refresh token
4. Use refresh token to get new access tokens

See Upstox API documentation: https://upstox.com/developer/api-documentation/

## Setting the New Token

### Option 1: Environment Variable (Recommended)

```bash
export UPSTOX_ACCESS_TOKEN="your_new_token_here"
```

Then run the dry run:
```bash
python scripts/dry_run_options_system.py --mode single --underlying NIFTY
```

### Option 2: Update .env.options File

Edit `.env.options`:
```
UPSTOX_ACCESS_TOKEN=your_new_token_here
```

### Option 3: Update Script Directly

Edit `scripts/dry_run_options_system.py` line ~60:
```python
self.config.upstox.access_token = "your_new_token_here"
```

## Token Expiry Error

If you see this error:
```
401 Client Error: Unauthorized
NotImplementedError: Token refresh requires manual OAuth flow
```

**Solution**: Generate a new access token using Method 1 above.

## Daily Workflow

For continuous monitoring (14-day dry run):

1. **Morning (before market open - 9:00 AM IST)**:
   - Generate new access token from Upstox dashboard
   - Set environment variable or update .env.options
   - Start/restart dry run script

2. **During market hours**:
   - Monitor logs for any token errors
   - If token expires mid-day, regenerate and restart

3. **After market close**:
   - Review daily summary
   - Check signal count and quality

## Automation (Optional)

To avoid daily manual token refresh, you can:

1. **Implement OAuth refresh flow**:
   - Store refresh token securely
   - Automatically exchange for new access token
   - Update `upstox_adapter.py` `refresh_token()` method

2. **Use Upstox API v3** (if available):
   - Check if longer-lived tokens are supported
   - Update adapter accordingly

3. **Schedule token generation**:
   - Use cron job to generate token daily
   - Store in environment variable
   - Restart dry run script

## Example: Daily Token Update Script

```bash
#!/bin/bash
# daily_token_update.sh

# Get new token (you'll need to implement this based on your OAuth setup)
NEW_TOKEN=$(get_upstox_token.sh)

# Update environment
export UPSTOX_ACCESS_TOKEN="$NEW_TOKEN"

# Restart dry run
pkill -f dry_run_options_system.py
python scripts/dry_run_options_system.py --mode continuous --duration 14 --interval 60 --underlying BOTH &
```

## Troubleshooting

### Token Still Invalid After Refresh

**Possible causes**:
1. Token not copied correctly (check for extra spaces)
2. Token already expired (generate a fresh one)
3. App not authorized (re-authorize in Upstox console)

**Solution**: Generate a completely new token and verify it works with a test API call.

### Token Expires Mid-Run

**Expected behavior**: The dry run will log the error and continue trying.

**Solution**: 
1. Generate new token
2. Update environment variable
3. Script will automatically use new token on next cycle

### Can't Generate Token

**Possible causes**:
1. Upstox account not verified
2. API app not created
3. API access not enabled

**Solution**: Contact Upstox support or check your account status.

## Security Best Practices

⚠️ **Never commit tokens to git**

✅ **Use environment variables**

✅ **Rotate tokens regularly**

✅ **Store tokens securely**

✅ **Use .env.options (already in .gitignore)**

## Quick Reference

```bash
# Generate new token from Upstox dashboard
# Then set it:
export UPSTOX_ACCESS_TOKEN="your_new_token"

# Test it works:
python scripts/dry_run_options_system.py --mode single --underlying NIFTY

# If successful, start continuous monitoring:
python scripts/dry_run_options_system.py --mode continuous --duration 14 --interval 60 --underlying BOTH
```

---

**Remember**: Tokens expire daily. Plan to refresh each morning before market open (9:00 AM IST). 🔄
