# Build the container using standard docker-compose.yml
build:
	docker compose build

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
