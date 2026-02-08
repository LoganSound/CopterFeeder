#!/usr/bin/env bash

# This script adds the Google Cloud IP ranges to the whitelist for the CopterFeeder project.
# It uses the Atlas CLI to add the IP ranges to the whitelist.
# It uses the jq command to parse the JSON output from the curl command.
# It uses the sleep command to wait for 1 second between each IP range.
# It uses the atlas accesslist create command to add the IP ranges to the whitelist.


# Get the project ID from the environment variable ATLAS_PROJECT_ID
PROJECT_ID=${ATLAS_PROJECT_ID}

for i in `curl -s https://www.gstatic.com/ipranges/cloud.json | jq -r '.prefixes[] | select(.scope == "us-central1") | .ipv4Prefix'`;
do
    echo Adding $i to whitelist
    atlas accesslist create --projectId $PROJECT_ID --comment google --type cidrBlock $i

    sleep 1

done
