Basic setup for starting CopterFeeder in Kubernetes


This setup assumes you have a running kubernetes cluster, an existing
docker registry, and a pre-built container, which has been uploaded to your registry. 

For building the container - see ../buildx

These .yaml files were created with "kompose" like: 

``` 
kompose -f ./kube-docker-compose.yml_kube_ignore -n fcs convert
```

and then lightly edited.  You'll need to create your own env-configmap.yaml
based on your own .env file - you should be able to use kompose.  Note
you'll need to add a fqdn for the hostname in place of
"host.docker.internal"

If you don't know what all that means, you likely don't need to worry about
this directory or the enclosed files. 
