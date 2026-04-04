# 🚂 Deploy to Railway

## Prerequisites

1. **Railway CLI**
   ```bash
   npm install -g @railway/cli
   ```

2. **Login**
   ```bash
   railway login
   ```

## Quick Deploy (One Command)

```bash
# Set your API keys first
export AZURE_SWEDEN_KEY="your-key"
export AZURE_NC_KEY="your-key"
export AZURE_GCE_KEY="your-key"
export DEEPSEEK_API_KEY="your-key"
export GROK_API_KEY="your-key"
export KIMI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export ODDS_API_KEY="your-key"

# Deploy
./deploy-railway.sh
```

## Manual Deploy (Step by Step)

### Step 1: Create Project
```bash
cd edge-crew-v3
railway init
```

### Step 2: Add Database Services
In Railway dashboard or CLI:
```bash
railway add --database postgres
railway add --database redis
```

### Step 3: Deploy AI Processor
```bash
cd services/ai-processor
railway up
```

### Step 4: Deploy Convergence
```bash
cd services/convergence
railway up
```

### Step 5: Deploy Web
```bash
cd web
railway up
```

### Step 6: Add Environment Variables
In Railway dashboard → Variables:

```
AZURE_SWEDEN_KEY=xxx
AZURE_NC_KEY=xxx
AZURE_GCE_KEY=xxx
DEEPSEEK_API_KEY=xxx
GROK_API_KEY=xxx
KIMI_API_KEY=xxx
ANTHROPIC_API_KEY=xxx
ODDS_API_KEY=xxx
BALLDONTLIE_API_KEY=xxx
```

## 🎉 Done!

Your app will be live at: `https://your-project.up.railway.app`

## Useful Commands

```bash
# View logs
railway logs

# View specific service
railway logs --service ai-processor

# Redeploy
railway up

# Scale up
railway scale --replicas 3

# Add domain
railway domain

# Environment variables
railway variables
railway variables set KEY=value
```

## 💰 Railway Pricing

| Tier | Cost | What You Get |
|------|------|--------------|
| **Starter** | $5/mo | 512MB RAM, shared CPU, 1GB disk |
| **Pro** | $10/mo | 1GB RAM, 1 vCPU, 5GB disk |
| **Business** | $50/mo | 4GB RAM, 2 vCPU, 20GB disk |

For Edge Crew v3.0, you'll need:
- AI Processor: Pro tier ($10)
- Convergence: Starter tier ($5)
- Postgres: Included free
- Redis: Included free

**Total: ~$15/month**

## 🔥 Features on Railway

✅ **Private networking** between services
✅ **Auto-deploy** on git push
✅ **Environment variables** management
✅ **Multiple regions** (US, EU, Asia)
✅ **Custom domains** with SSL
✅ **Monitoring** dashboards
✅ **Logs** streaming
