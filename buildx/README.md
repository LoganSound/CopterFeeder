Basic setup for building multi-arch containers and pushing to registry using Kubernetes.

Requires docker-buildx to be installed. See OS and/or Docker documentation for more info. 

buildxkitd.default.toml -- example config file for buildx to specify registry. Copy to $DOCKER_CONFIG/buildx/

setup_buildx_kubernetes_builder.toml -- example script to setup a multiarch-builder in kubernetes. 

This setup assumes you have at native amd64 and arm64 servers in a running kubernetes cluster, and an existing docker registry.
If you don't know what all that means, you likely don't need to worry about this directory or the enclosed files.
