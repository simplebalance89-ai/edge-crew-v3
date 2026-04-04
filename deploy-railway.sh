#!/bin/bash
# Deploy Edge Crew v3.0 to Railway

echo "🚂 Edge Crew v3.0 - Railway Deploy"
echo ""

# Check Railway CLI
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Install with: npm install -g @railway/cli"
    exit 1
fi

# Check login
railway whoami || railway login

# Create project or link existing
echo "📦 Setting up Railway project..."
railway link || railway init

# Add PostgreSQL
echo "🐘 Adding PostgreSQL..."
railway add --database postgres

# Add Redis
echo "⚡ Adding Redis..."
railway add --database redis

# Set environment variables
echo "🔑 Setting environment variables..."
railway variables set \
    AZURE_SWEDEN_KEY="$AZURE_SWEDEN_KEY" \
    AZURE_NC_KEY="$AZURE_NC_KEY" \
    AZURE_GCE_KEY="$AZURE_GCE_KEY" \
    DEEPSEEK_API_KEY="$DEEPSEEK_API_KEY" \
    GROK_API_KEY="$GROK_API_KEY" \
    KIMI_API_KEY="$KIMI_API_KEY" \
    ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
    ODDS_API_KEY="$ODDS_API_KEY" \
    BALLDONTLIE_API_KEY="$BALLDONTLIE_API_KEY"

# Deploy
echo "🚀 Deploying..."
railway up --detach

# Get URL
URL=$(railway domain)
echo ""
echo "✅ Deployed!"
echo "🌐 URL: https://$URL"
echo ""
echo "Check logs: railway logs"
