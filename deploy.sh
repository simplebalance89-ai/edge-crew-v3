#!/bin/bash
# Edge Crew v3.0 - Deployment Script
# Usage: ./deploy.sh [local|gke|eks|aks]

set -e

DEPLOYMENT_TYPE=${1:-local}
echo "🚀 Edge Crew v3.0 Deployment: $DEPLOYMENT_TYPE"

case $DEPLOYMENT_TYPE in
  local)
    echo "📦 Local Docker Compose Deployment"
    
    # Check prerequisites
    command -v docker >/dev/null 2>&1 || { echo "❌ Docker required"; exit 1; }
    command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose required"; exit 1; }
    
    # Setup environment
    if [ ! -f .env ]; then
      cp .env.example .env
      echo "⚠️  Created .env from example - UPDATE WITH YOUR API KEYS!"
    fi
    
    # Build and start
    docker-compose build
    docker-compose up -d
    
    # Wait for services
    echo "⏳ Waiting for services..."
    sleep 10
    
    # Health checks
    echo "🏥 Health Checks:"
    curl -s http://localhost:8000/health | jq . || echo "API Gateway not ready"
    curl -s http://localhost:8001/health | jq . || echo "Convergence not ready"
    curl -s http://localhost:8002/health | jq . || echo "AI Processor not ready"
    
    echo ""
    echo "✅ Local deployment complete!"
    echo "🌐 Web UI: http://localhost:3000"
    echo "🔌 API: http://localhost:8000"
    echo "📊 pgAdmin: http://localhost:5050"
    echo ""
    echo "Logs: docker-compose logs -f"
    ;;
    
  gke)
    echo "☸️  Google Kubernetes Engine Deployment"
    
    command -v gcloud >/dev/null 2>&1 || { echo "❌ gcloud CLI required"; exit 1; }
    command -v kubectl >/dev/null 2>&1 || { echo "❌ kubectl required"; exit 1; }
    command -v terraform >/dev/null 2>&1 || { echo "❌ terraform required"; exit 1; }
    
    # Terraform
    cd infrastructure/terraform/environments/prod
    terraform init
    terraform plan
    read -p "Proceed with apply? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      terraform apply
    fi
    
    # Configure kubectl
    gcloud container clusters get-credentials edge-crew-prod --zone us-central1-a
    
    # Deploy services
    cd ../../../k8s
    kubectl apply -k .
    
    # Wait for rollout
    kubectl rollout status deployment/api-gateway -n edge-crew
    kubectl rollout status deployment/ai-processor -n edge-crew
    kubectl rollout status deployment/convergence -n edge-crew
    
    # Get endpoint
    echo "✅ GKE Deployment Complete!"
    kubectl get ingress -n edge-crew
    ;;
    
  *)
    echo "❌ Unknown deployment type: $DEPLOYMENT_TYPE"
    echo "Usage: ./deploy.sh [local|gke]"
    exit 1
    ;;
esac
