.PHONY: help build up down clean setup-buildx bake black pre-commit bump

# Default target: build the container
build:
	docker compose build

# Show this help
help:
	@echo "Targets:"
	@echo "  make / make build   - Build the container (docker-compose.yml)"
	@echo "  make up             - Start containers in background (docker compose up -d)"
	@echo "  make down           - Stop and remove containers"
	@echo "  make clean          - Stop containers, remove build sentinel and other cleanup"
	@echo "  make setup-buildx   - Set up buildx multi-arch builder (buildx/ scripts)"
	@echo "  make bake           - Build and push multi-arch images (arm64, amd64)"
	@echo "  make black          - Run Black code formatter"
	@echo "  make pre-commit     - Run pre-commit hooks on all files"
	@echo "  make bump           - Bump version with commitizen"
	@echo "  make help           - Show this help"

# Sentinel: build only when Dockerfile or app sources are newer than last build
.build.done: Dockerfile docker-compose.yml requirements.txt fcs.py icao_heli_types.py config
	docker compose build && touch .build.done

# Start containers in background; builds first only when inputs have changed
up: .build.done
	docker compose up -d

# Stop and remove containers
down:
	docker compose down

# Stop containers and remove build sentinel so next 'make up' will rebuild
clean: down
	rm -f .build.done

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
