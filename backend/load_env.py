#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ENV_FILE="$SCRIPT_DIR/.envs/.local/.django"

if [ -f "$ENV_FILE" ]; then
    echo "Loading environment variables from $ENV_FILE"
    unset GOOGLE_CLIENT_ID
    
    # Read each line from the env file
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip empty lines and comments
        if [ -z "$line" ] || [[ $line == \#* ]]; then
            continue
        fi
        
        # Extract key and value
        if [[ $line == *"="* ]]; then
            key=$(echo "$line" | cut -d '=' -f 1)
            value=$(echo "$line" | cut -d '=' -f 2-)
            
            # Remove leading/trailing whitespace
            key=$(echo "$key" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
            value=$(echo "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
            
            # Remove quotes if present
            value=$(echo "$value" | sed -e 's/^["\x27]//' -e 's/["\x27]$//')
            
            # Export the variable
            export "$key=$value"
        fi
    done < "$ENV_FILE"
    
    echo "Environment variables loaded successfully"
else
    echo "Warning: Environment file not found at $ENV_FILE"
    echo "Current directory: $PWD"
fi 