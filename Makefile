# Show this help
help:
	@echo "Targets:"
	@echo "  make / make build   - Build the container (docker-compose.yml)"
	@echo "  make up             - Start containers in background (docker compose up -d --build)"
	@echo "  make down           - Stop and remove containers"
	@echo "  make setup-buildx   - Set up buildx multi-arch builder (buildx/ scripts)"
	@echo "  make bake           - Build and push multi-arch images (arm64, amd64)"
	@echo "  make black          - Run Black code formatter"
	@echo "  make pre-commit     - Run pre-commit hooks on all files"
	@echo "  make bump           - Bump version with commitizen"
	@echo "  make help           - Show this help"

# Build the container using standard docker-compose.yml
build:
	docker compose build

# Start containers (docker compose up -d); builds first if image is missing or out of date
up:
	docker compose up -d --build

# Stop and remove containers
down:
	docker compose down

# Setup buildx multi-arch builder using scripts under buildx/
setup-buildx:
	./buildx/setup_buildx_kubernetes_builder.sh

# Build and push multi-arch images using docker-compose-buildx.yml
bake:
	docker buildx bake -f docker-compose-buildx.yml --builder=multiarch-builder --push --set '*.platform=linux/arm64,linux/amd64'

# Run black code formatter
black:
	black .

# Run pre-commit on all files
pre-commit:
	pre-commit run --all-files

# Bump version using commitizen (updates version files and CHANGELOG)
bump:
	cz bump
