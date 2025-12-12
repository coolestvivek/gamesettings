# Railway Deployment for CGXREGEDIT UIDBYPASS

## Environment Variables Required

Add these environment variables in Railway dashboard:

1. **SECRET_KEY** - Flask secret key (generate a secure random string)
   ```
   Use: python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **DISCORD_BOT_TOKEN** - Your Discord bot token
   ```
   Get from: https://discord.com/developers/applications
   ```

3. **PORT** - Automatically set by Railway (leave empty)

## Deployment Steps

1. Push code to GitHub repository
2. Create new project in Railway
3. Connect your GitHub repository
4. Add environment variables in Railway dashboard
5. Deploy!

## Notes

- Database (SQLite) will be stored in the container
- For persistent data, consider using Railway PostgreSQL
- Discord bot runs in a background thread alongside Flask
- Default login: username=Mani, password=mani123

## Post-Deployment

Your app will be available at: `https://your-app.up.railway.app`
