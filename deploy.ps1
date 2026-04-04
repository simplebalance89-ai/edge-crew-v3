# Edge Crew v3.0 - Deployment Script (PowerShell)
# Usage: .\deploy.ps1 [local|gke]

param(
    [string]$Type = "local"
)

Write-Host "🚀 Edge Crew v3.0 Deployment: $Type" -ForegroundColor Cyan

switch ($Type) {
    "local" {
        Write-Host "📦 Local Docker Compose Deployment" -ForegroundColor Yellow
        
        # Check prerequisites
        $docker = Get-Command docker -ErrorAction SilentlyContinue
        if (-not $docker) {
            Write-Host "❌ Docker required" -ForegroundColor Red
            exit 1
        }
        
        # Setup environment
        if (-not (Test-Path .env)) {
            Copy-Item .env.example .env
            Write-Host "⚠️  Created .env from example - UPDATE WITH YOUR API KEYS!" -ForegroundColor Yellow
        }
        
        # Build and start
        docker compose build
        docker compose up -d
        
        # Wait for services
        Write-Host "⏳ Waiting for services..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
        
        # Health checks
        Write-Host "🏥 Health Checks:" -ForegroundColor Green
        try {
            $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
            Write-Host "✅ API Gateway: $($health.status)" -ForegroundColor Green
        } catch {
            Write-Host "⏳ API Gateway starting..." -ForegroundColor Yellow
        }
        
        Write-Host ""
        Write-Host "✅ Local deployment complete!" -ForegroundColor Green
        Write-Host "🌐 Web UI: http://localhost:3000" -ForegroundColor Cyan
        Write-Host "🔌 API: http://localhost:8000" -ForegroundColor Cyan
        Write-Host "📊 pgAdmin: http://localhost:5050" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Logs: docker compose logs -f" -ForegroundColor Gray
    }
    
    "gke" {
        Write-Host "☸️  Google Kubernetes Engine Deployment" -ForegroundColor Yellow
        Write-Host "📋 Prerequisites check:" -ForegroundColor Yellow
        
        $gcloud = Get-Command gcloud -ErrorAction SilentlyContinue
        $kubectl = Get-Command kubectl -ErrorAction SilentlyContinue
        $terraform = Get-Command terraform -ErrorAction SilentlyContinue
        
        if (-not $gcloud) { Write-Host "❌ gcloud CLI required" -ForegroundColor Red; exit 1 }
        if (-not $kubectl) { Write-Host "❌ kubectl required" -ForegroundColor Red; exit 1 }
        if (-not $terraform) { Write-Host "❌ terraform required" -ForegroundColor Red; exit 1 }
        
        Write-Host "✅ All prerequisites met" -ForegroundColor Green
        
        # Terraform
        Set-Location infrastructure/terraform/environments/prod
        terraform init
        terraform plan
        
        $confirm = Read-Host "Proceed with apply? (y/n)"
        if ($confirm -eq 'y') {
            terraform apply -auto-approve
        }
        
        # Configure kubectl
        gcloud container clusters get-credentials edge-crew-prod --zone us-central1-a
        
        # Deploy services
        Set-Location ../../../k8s
        kubectl apply -k .
        
        # Wait for rollout
        Write-Host "⏳ Waiting for deployments..." -ForegroundColor Yellow
        kubectl rollout status deployment/api-gateway -n edge-crew
        kubectl rollout status deployment/ai-processor -n edge-crew
        
        # Get endpoint
        Write-Host "✅ GKE Deployment Complete!" -ForegroundColor Green
        kubectl get ingress -n edge-crew
    }
    
    default {
        Write-Host "❌ Unknown deployment type: $Type" -ForegroundColor Red
        Write-Host "Usage: .\deploy.ps1 [local|gke]" -ForegroundColor Gray
        exit 1
    }
}
