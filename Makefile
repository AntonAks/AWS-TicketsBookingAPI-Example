# Makefile for Ticket Booking System

# Variables
PROJECT_NAME = ticket-booking
ENVIRONMENT ?= dev
AWS_REGION ?= us-east-1
TERRAFORM_DIR = terraform
LAMBDA_DIR = lambdas
LAYER_DIR = layers
LOAD_GEN_DIR = load-generator

# Colors for output
RED = \033[31m
GREEN = \033[32m
YELLOW = \033[33m
BLUE = \033[34m
NC = \033[0m # No Color

.PHONY: help
help: ## Show this help message
	@echo "$(GREEN)Ticket Booking System - Available Commands:$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $1, $2}'

# Setup and initialization
.PHONY: init
init: ## Initialize the project (install dependencies, setup terraform)
	@echo "$(BLUE)Initializing project...$(NC)"
	@terraform -chdir=$(TERRAFORM_DIR) init
	@pip install -r requirements.txt
	@echo "$(GREEN)Project initialized successfully!$(NC)"

.PHONY: setup-env
setup-env: ## Setup environment variables
	@echo "$(BLUE)Setting up environment for $(ENVIRONMENT)...$(NC)"
	@cp terraform/terraform.tfvars.example terraform/terraform.tfvars
	@echo "$(YELLOW)Please update terraform/terraform.tfvars with your specific values$(NC)"

# Lambda layers
.PHONY: build-layers
build-layers: ## Build Lambda layers
	@echo "$(BLUE)Building Lambda layers...$(NC)"
	@mkdir -p $(LAYER_DIR)/common/python/lib
	@mkdir -p $(LAYER_DIR)/external-libs/python/lib
	@pip install -r $(LAYER_DIR)/common/requirements.txt -t $(LAYER_DIR)/common/python/lib/
	@pip install -r $(LAYER_DIR)/external-libs/requirements.txt -t $(LAYER_DIR)/external-libs/python/lib/
	@cd $(LAYER_DIR)/common && zip -r ../common-layer.zip python/
	@cd $(LAYER_DIR)/external-libs && zip -r ../external-libs-layer.zip python/
	@echo "$(GREEN)Lambda layers built successfully!$(NC)"

.PHONY: upload-layers
upload-layers: build-layers ## Upload Lambda layers to S3
	@echo "$(BLUE)Uploading Lambda layers...$(NC)"
	@aws s3 cp $(LAYER_DIR)/common-layer.zip s3://$(PROJECT_NAME)-lambda-artifacts-$(ENVIRONMENT)/layers/
	@aws s3 cp $(LAYER_DIR)/external-libs-layer.zip s3://$(PROJECT_NAME)-lambda-artifacts-$(ENVIRONMENT)/layers/
	@echo "$(GREEN)Lambda layers uploaded successfully!$(NC)"

# Lambda functions
.PHONY: build-lambdas
build-lambdas: ## Build Lambda deployment packages
	@echo "$(BLUE)Building Lambda functions...$(NC)"
	@for dir in $(LAMBDA_DIR)/*; do \
		if [ -d "$dir" ]; then \
			echo "Building $(basename $dir)..."; \
			cd $dir && zip -r ../../../dist/$(basename $dir).zip . && cd ../..; \
		fi \
	done
	@echo "$(GREEN)Lambda functions built successfully!$(NC)"

.PHONY: upload-lambdas
upload-lambdas: build-lambdas ## Upload Lambda functions to S3
	@echo "$(BLUE)Uploading Lambda functions...$(NC)"
	@mkdir -p dist
	@aws s3 sync dist/ s3://$(PROJECT_NAME)-lambda-artifacts-$(ENVIRONMENT)/functions/
	@echo "$(GREEN)Lambda functions uploaded successfully!$(NC)"

# Infrastructure
.PHONY: plan
plan: ## Show Terraform execution plan
	@echo "$(BLUE)Creating Terraform plan for $(ENVIRONMENT)...$(NC)"
	@terraform -chdir=$(TERRAFORM_DIR) plan \
		-var="environment=$(ENVIRONMENT)" \
		-var="aws_region=$(AWS_REGION)" \
		-var="project_name=$(PROJECT_NAME)"

.PHONY: deploy-infra
deploy-infra: ## Deploy infrastructure with Terraform
	@echo "$(BLUE)Deploying infrastructure for $(ENVIRONMENT)...$(NC)"
	@terraform -chdir=$(TERRAFORM_DIR) apply \
		-var="environment=$(ENVIRONMENT)" \
		-var="aws_region=$(AWS_REGION)" \
		-var="project_name=$(PROJECT_NAME)" \
		-auto-approve
	@echo "$(GREEN)Infrastructure deployed successfully!$(NC)"

.PHONY: destroy-infra
destroy-infra: ## Destroy infrastructure
	@echo "$(RED)Destroying infrastructure for $(ENVIRONMENT)...$(NC)"
	@read -p "Are you sure you want to destroy the infrastructure? (y/N): " confirm && \
	if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then \
		terraform -chdir=$(TERRAFORM_DIR) destroy \
			-var="environment=$(ENVIRONMENT)" \
			-var="aws_region=$(AWS_REGION)" \
			-var="project_name=$(PROJECT_NAME)" \
			-auto-approve; \
		echo "$(GREEN)Infrastructure destroyed successfully!$(NC)"; \
	else \
		echo "$(YELLOW)Destruction cancelled.$(NC)"; \
	fi

# Full deployment
.PHONY: deploy
deploy: build-layers upload-layers build-lambdas upload-lambdas deploy-infra ## Full deployment (layers + lambdas + infrastructure)
	@echo "$(GREEN)Full deployment completed successfully!$(NC)"

# Database operations
.PHONY: seed-data
seed-data: ## Seed database with sample data
	@echo "$(BLUE)Seeding database with sample data...$(NC)"
	@python scripts/seed_data.py --environment $(ENVIRONMENT)
	@echo "$(GREEN)Database seeded successfully!$(NC)"

.PHONY: backup-db
backup-db: ## Backup DynamoDB tables
	@echo "$(BLUE)Creating database backup...$(NC)"
	@python scripts/backup_db.py --environment $(ENVIRONMENT)
	@echo "$(GREEN)Database backup completed!$(NC)"

# Load testing
.PHONY: build-load-generator
build-load-generator: ## Build load generator Docker image
	@echo "$(BLUE)Building load generator...$(NC)"
	@docker build -t $(PROJECT_NAME)-load-generator $(LOAD_GEN_DIR)
	@echo "$(GREEN)Load generator built successfully!$(NC)"

.PHONY: run-load-test
run-load-test: ## Run load test
	@echo "$(BLUE)Starting load test...$(NC)"
	@docker run --rm \
		-v $(PWD)/$(LOAD_GEN_DIR)/config:/app/config \
		-v $(PWD)/$(LOAD_GEN_DIR)/results:/app/results \
		-e API_BASE_URL=$(terraform -chdir=$(TERRAFORM_DIR) output -raw api_gateway_url) \
		-e ENVIRONMENT=$(ENVIRONMENT) \
		$(PROJECT_NAME)-load-generator
	@echo "$(GREEN)Load test completed! Check results in $(LOAD_GEN_DIR)/results/$(NC)"

.PHONY: run-stress-test
run-stress-test: ## Run stress test with high load
	@echo "$(BLUE)Starting stress test...$(NC)"
	@docker run --rm \
		-v $(PWD)/$(LOAD_GEN_DIR)/config:/app/config \
		-v $(PWD)/$(LOAD_GEN_DIR)/results:/app/results \
		-e API_BASE_URL=$(terraform -chdir=$(TERRAFORM_DIR) output -raw api_gateway_url) \
		-e ENVIRONMENT=$(ENVIRONMENT) \
		-e TEST_TYPE=stress \
		$(PROJECT_NAME)-load-generator
	@echo "$(GREEN)Stress test completed!$(NC)"

# Monitoring and debugging
.PHONY: logs
logs: ## Show recent Lambda logs
	@echo "$(BLUE)Fetching recent logs...$(NC)"
	@aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/$(PROJECT_NAME)" --query 'logGroups[].logGroupName' --output text | \
	while read log_group; do \
		echo "$(YELLOW)Logs from $log_group:$(NC)"; \
		aws logs tail $log_group --since 1h --format short; \
		echo ""; \
	done

.PHONY: metrics
metrics: ## Show CloudWatch metrics
	@echo "$(BLUE)Fetching CloudWatch metrics...$(NC)"
	@python scripts/show_metrics.py --environment $(ENVIRONMENT)

.PHONY: health-check
health-check: ## Check system health
	@echo "$(BLUE)Performing health check...$(NC)"
	@python scripts/health_check.py --environment $(ENVIRONMENT)

# Development
.PHONY: lint
lint: ## Run code linting
	@echo "$(BLUE)Running linting...$(NC)"
	@flake8 $(LAMBDA_DIR) $(LOAD_GEN_DIR) scripts/
	@pylint $(LAMBDA_DIR) $(LOAD_GEN_DIR) scripts/
	@echo "$(GREEN)Linting completed!$(NC)"

.PHONY: test
test: ## Run unit tests
	@echo "$(BLUE)Running tests...$(NC)"
	@python -m pytest tests/ -v
	@echo "$(GREEN)Tests completed!$(NC)"

.PHONY: local-dev
local-dev: ## Start local development environment
	@echo "$(BLUE)Starting local development environment...$(NC)"
	@docker-compose up -d
	@echo "$(GREEN)Local environment started!$(NC)"
	@echo "$(YELLOW)DynamoDB Local: http://localhost:8000$(NC)"
	@echo "$(YELLOW)Redis: localhost:6379$(NC)"

.PHONY: local-stop
local-stop: ## Stop local development environment
	@echo "$(BLUE)Stopping local development environment...$(NC)"
	@docker-compose down
	@echo "$(GREEN)Local environment stopped!$(NC)"

# Cleanup
.PHONY: clean
clean: ## Clean build artifacts
	@echo "$(BLUE)Cleaning build artifacts...$(NC)"
	@rm -rf dist/
	@rm -rf $(LAYER_DIR)/*.zip
	@rm -rf $(LAMBDA_DIR)/*/__pycache__/
	@rm -rf $(LOAD_GEN_DIR)/__pycache__/
	@find . -name "*.pyc" -delete
	@echo "$(GREEN)Cleanup completed!$(NC)"

.PHONY: clean-all
clean-all: clean ## Clean everything including Docker images
	@echo "$(BLUE)Cleaning everything...$(NC)"
	@docker image rm $(PROJECT_NAME)-load-generator 2>/dev/null || true
	@docker system prune -f
	@echo "$(GREEN)Full cleanup completed!$(NC)"

# Utilities
.PHONY: validate
validate: ## Validate Terraform configuration
	@echo "$(BLUE)Validating Terraform configuration...$(NC)"
	@terraform -chdir=$(TERRAFORM_DIR) validate
	@echo "$(GREEN)Terraform configuration is valid!$(NC)"

.PHONY: format
format: ## Format Terraform and Python code
	@echo "$(BLUE)Formatting code...$(NC)"
	@terraform -chdir=$(TERRAFORM_DIR) fmt -recursive
	@black $(LAMBDA_DIR) $(LOAD_GEN_DIR) scripts/
	@echo "$(GREEN)Code formatting completed!$(NC)"

.PHONY: docs
docs: ## Generate documentation
	@echo "$(BLUE)Generating documentation...$(NC)"
	@python scripts/generate_docs.py
	@echo "$(GREEN)Documentation generated in docs/$(NC)"

# Emergency procedures
.PHONY: emergency-scale-down
emergency-scale-down: ## Emergency scale down (reduce costs)
	@echo "$(RED)Emergency scale down activated!$(NC)"
	@python scripts/emergency_scale.py --action scale-down --environment $(ENVIRONMENT)
	@echo "$(GREEN)System scaled down for cost reduction$(NC)"

.PHONY: emergency-scale-up
emergency-scale-up: ## Emergency scale up (handle traffic spike)
	@echo "$(RED)Emergency scale up activated!$(NC)"
	@python scripts/emergency_scale.py --action scale-up --environment $(ENVIRONMENT)
	@echo "$(GREEN)System scaled up for high traffic$(NC)"

# Information
.PHONY: info
info: ## Show deployment information
	@echo "$(GREEN)=== Ticket Booking System Info ===$(NC)"
	@echo "$(BLUE)Project:$(NC) $(PROJECT_NAME)"
	@echo "$(BLUE)Environment:$(NC) $(ENVIRONMENT)"
	@echo "$(BLUE)AWS Region:$(NC) $(AWS_REGION)"
	@echo ""
	@if terraform -chdir=$(TERRAFORM_DIR) output api_gateway_url >/dev/null 2>&1; then \
		echo "$(BLUE)API Gateway URL:$(NC) $(terraform -chdir=$(TERRAFORM_DIR) output -raw api_gateway_url)"; \
		echo "$(BLUE)Status:$(NC) $(GREEN)Deployed$(NC)"; \
	else \
		echo "$(BLUE)Status:$(NC) $(YELLOW)Not deployed$(NC)"; \
	fi

.PHONY: outputs
outputs: ## Show Terraform outputs
	@echo "$(BLUE)Terraform outputs:$(NC)"
	@terraform -chdir=$(TERRAFORM_DIR) output