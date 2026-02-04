#!/usr/bin/env bash

# simple command to use buildx with docker-compose file

#docker buildx bake --push --set *.platform=linux/amd64,linux/arm64

DOCKER_CONFIG=~/.docker
export DOCKER_CONFIG

if [ -e $DOCKER_CONFIG/buildx/buildkitd.default.toml ]
then
    printf "buildkitd.default.toml exists\n"
else
    printf "buildkitd.default.toml not found\n"
    exit
fi

kubectl get namespace multiarch-builder > /dev/null 2>&1 ||  {
    printf "Creating multiarch-builder kubernetes namespace\n"
    kubectl create namespace multiarch-builder
}

echo foo

docker buildx use multiarch-builder ||
{
    printf "Creating builder\n"
    docker buildx create \
        --name multiarch-builder \
        --driver=kubernetes \
        --bootstrap \
        --config $DOCKER_CONFIG/buildx/buildkitd.default.toml \
        --platform=linux/arm64 \
        --node=multiarch-builder-arm64 \
        --driver-opt nodeselector="kubernetes.io/arch=arm64"\
        --driver-opt namespace="multiarch-builder"\


    docker buildx create \
        --append \
        --name multiarch-builder \
        --driver=kubernetes \
        --bootstrap \
        --config $DOCKER_CONFIG/buildx/buildkitd.default.toml \
        --platform=linux/amd64 \
        --node=multiarch-builder-amd64 \
        --driver-opt nodeselector="kubernetes.io/arch=amd64"\
        --driver-opt namespace="multiarch-builder"

    # Use this to build with Kubernetes builder:

}

printf "Use this command: \n\tdocker buildx bake --builder=multiarch-builder --push --set *.platform=linux/arm64,linux/amd64\n"
