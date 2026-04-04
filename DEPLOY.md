# Edge Crew v3.0 - Deployment Guide

## 🚀 Quick Deploy Options

### Option 1: Local Development (Fastest)
```bash
# Clone
git clone https://github.com/simplebalance89-ai/edge-crew-v3.git
cd edge-crew-v3

# Start everything
./deploy.sh local

# Access
# - Web UI: http://localhost:3000
# - API: http://localhost:8000
# - pgAdmin: http://localhost:5050 (admin@edgecrew.io / admin)
```

### Option 2: Google Cloud (GKE) - Production

#### Prerequisites
- [gcloud CLI](https://cloud.google.com/sdk/docs/install)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Terraform](https://developer.hashicorp.com/terraform/downloads)
- GCP Project with billing enabled

#### Step 1: Setup GCP Project
```bash
# Login
gcloud auth login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Enable APIs
gcloud services enable container.googleapis.com
```

#### Step 2: Configure Terraform
```bash
cd infrastructure/terraform/environments/prod

# Create terraform.tfvars
cat > terraform.tfvars <<EOF
project_id = "your-project-id"
region     = "us-central1"
EOF
```

#### Step 3: Deploy Infrastructure
```bash
# Initialize
terraform init

# Plan
terraform plan

# Apply (creates GKE cluster, Postgres, Redis)
terraform apply

# Configure kubectl
gcloud container clusters get-credentials edge-crew-prod --zone us-central1-a
```

#### Step 4: Deploy Application
```bash
# From repo root
kubectl apply -k infrastructure/k8s

# Wait for rollout
kubectl rollout status deployment/api-gateway -n edge-crew
kubectl rollout status deployment/ai-processor -n edge-crew
kubectl rollout status deployment/convergence -n edge-crew

# Get endpoint
kubectl get ingress -n edge-crew
```

#### Step 5: Configure DNS
```bash
# Get the ingress IP
INGRESS_IP=$(kubectl get ingress edge-crew-ingress -n edge-crew -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "Point your domain to: $INGRESS_IP"
```

---

## 🔧 Environment Variables

### Required Secrets (set in GitHub or GCP Secret Manager)

```bash
# AI Model API Keys
AZURE_SWEDEN_KEY=xxx
AZURE_NC_KEY=xxx
AZURE_GCE_KEY=xxx
DEEPSEEK_API_KEY=xxx
GROK_API_KEY=xxx
KIMI_API_KEY=xxx
ANTHROPIC_API_KEY=xxx

# Data Sources
ODDS_API_KEY=xxx
BALLDONTLIE_API_KEY=xxx
RAPIDAPI_KEY=xxx

# Database
DATABASE_URL=postgresql://user:pass@host:5432/edgecrew
REDIS_URL=redis://host:6379
```

---

## 📊 Monitoring

### View Logs
```bash
# All pods
kubectl logs -f -l app=edge-crew -n edge-crew

# Specific service
kubectl logs -f deployment/ai-processor -n edge-crew
```

### Check Health
```bash
# API Gateway
curl https://api.edgecrew.io/health

# AI Processor
curl https://api.edgecrew.io/ai/health
```

### Grafana Dashboards
```bash
# Port-forward to Grafana
kubectl port-forward svc/grafana 3000:3000 -n monitoring

# Open http://localhost:3000
```

---

## 🔄 CI/CD

GitHub Actions automatically deploys on push to `main`:

1. **Build** - Docker images for all services
2. **Push** - To Google Container Registry
3. **Deploy** - Rolling update to GKE
4. **Verify** - Health checks

---

## 💰 Cost Estimates (Monthly)

| Component | Size | Cost |
|-----------|------|------|
| GKE (3 nodes, e2-standard-4) | 3x | $290 |
| Cloud SQL (PostgreSQL) | db-g1-small | $25 |
| Memorystore (Redis) | 5GB | $100 |
| Load Balancer | 1x | $18 |
| **Total** | | **~$433/month** |

---

## 🆘 Troubleshooting

### Pods not starting
```bash
kubectl describe pod -n edge-crew
kubectl logs -n edge-crew --previous
```

### Database connection issues
```bash
# Check Cloud SQL proxy
kubectl get pods -n edge-crew | grep cloud-sql-proxy

# Test connection from pod
kubectl exec -it deployment/convergence -n edge-crew -- psql $DATABASE_URL
```

### AI models failing
```bash
# Check circuit breaker status
kubectl logs deployment/ai-processor -n edge-crew | grep "Circuit"

# Test manually
curl -X POST http://localhost:8000/grade \
  -H "Content-Type: application/json" \
  -d '{"game_id":"test","sport":"nba","home_team":"Lakers","away_team":"Warriors","context":{}}'
```

---

## 📞 Support

- **Issues**: https://github.com/simplebalance89-ai/edge-crew-v3/issues
- **Discussions**: https://github.com/simplebalance89-ai/edge-crew-v3/discussions
