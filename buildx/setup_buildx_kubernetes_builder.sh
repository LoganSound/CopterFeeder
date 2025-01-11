#!/usr/bin/env bash


# simple command to use buildx with docker-compose file

#docker buildx bake --push --set *.platform=linux/amd64,linux/arm64

if [ -e /etc/docker/buildkitd.toml ]
then
    printf "buildkitd.toml exists\n"
else
    printf "buildkitd.toml not found\n"
    exit
fi

kubectl get namespace fcsbuilder > /dev/null 2>&1 ||  {
    printf "Creating fcsbuilder kubernetes namespace\n"
    kubectl create namespace fcsbuilder
}

docker buildx use fcsbuilder ||
{
    printf "Creating fcsbuilder\n"
    docker buildx create \
        --name fcsbuilder \
        --driver=kubernetes \
        --bootstrap \
        --config /etc/docker/buildkitd.toml \
        --platform=linux/amd64 \
        --node=fcsbuilder-amd64 \
        --driver-opt=nodeselector="kubernetes.io/arch=amd64,namespace=fcsbuilder"

    docker buildx create \
        --append \
        --name fcsbuilder \
        --driver=kubernetes \
        --bootstrap \
        --config /etc/docker/buildkitd.toml \
        --platform=linux/arm64 \
        --node=fcsbuilder-arm64 \
        --driver-opt=nodeselector="kubernetes.io/arch=arm64,namespace=fcsbuilder"

    # Use this to build with Kubernetes builder:

}

printf "Use this command: \n\tdocker buildx bake --builder=fcsbuilder --push --set *.platform=linux/amd64,linux/arm64\n"
