#!/bin/bash

# Function to copy and set up the .envrc file
setup_envrc() {
    cd ~/optimism
    cp .envrc.example .envrc

    local ENVRC_FILE=".envrc"

    # Replace existing lines for L1_RPC_URL and L1_RPC_KIND
    sed -i 's/^export L1_RPC_KIND=.*/export L1_RPC_KIND="alchemy"/' $ENVRC_FILE
    sed -i '/^export L1_RPC_URL=/d' $ENVRC_FILE
    echo 'export L1_RPC_URL="https://eth-sepolia.g.alchemy.com/v2/NhhIPMo7D3fr8AKPHMqWfrDKbQGWbR7_"' >> $ENVRC_FILE
    echo 'export SENDER_PRIVATE_KEY="71061e8174d4a2df7f51b04c874470b9199af4bf650c6d5a9da5761f6e4f3ad2"' >> $ENVRC_FILE
}

# Function to clean and append the output of the wallets script
process_wallets_output() {
    local ENV_FILE=".envrc"
    local WALLETS_SCRIPT="./packages/contracts-bedrock/scripts/getting-started/wallets.sh"

    # Delete existing lines
    sed -i '/GS_ADMIN_ADDRESS/d' $ENV_FILE
    sed -i '/GS_ADMIN_PRIVATE_KEY/d' $ENV_FILE
    sed -i '/GS_BATCHER_ADDRESS/d' $ENV_FILE
    sed -i '/GS_BATCHER_PRIVATE_KEY/d' $ENV_FILE
    sed -i '/GS_PROPOSER_ADDRESS/d' $ENV_FILE
    sed -i '/GS_PROPOSER_PRIVATE_KEY/d' $ENV_FILE
    sed -i '/GS_SEQUENCER_ADDRESS/d' $ENV_FILE
    sed -i '/GS_SEQUENCER_PRIVATE_KEY/d' $ENV_FILE

    # Append new output
    local output=$($WALLETS_SCRIPT)
    local cleaned_output=$(echo "$output" | sed '/Copy the following into your .envrc file:/d')
    echo "$cleaned_output" >> $ENV_FILE
}

# Function to fund addresses
fund_addresses() {
    cd ~/optimism/funding
    go mod tidy
    go run main.go
}

# Function to deploy L1 contracts and generate artifacts
deploy_contracts() {
    cd ~/optimism/packages/contracts-bedrock
    ./scripts/getting-started/config.sh
    forge script scripts/Deploy.s.sol:Deploy --private-key $GS_ADMIN_PRIVATE_KEY --broadcast --rpc-url $L1_RPC_URL
    forge script scripts/Deploy.s.sol:Deploy --sig 'sync()' --rpc-url $L1_RPC_URL
}

# Function to generate genesis and rollup files
generate_genesis_files() {
    cd ~/optimism/op-node
    go run cmd/main.go genesis l2 \
        --deploy-config ../packages/contracts-bedrock/deploy-config/getting-started.json \
        --deployment-dir ../packages/contracts-bedrock/deployments/getting-started/ \
        --outfile.l2 genesis.json \
        --outfile.rollup rollup.json \
        --l1-rpc $L1_RPC_URL

    openssl rand -hex 32 > jwt.txt
    cp genesis.json ~/op-geth
    cp jwt.txt ~/op-geth
}

# Main execution flow
main() {
    setup_envrc
    process_wallets_output
    direnv allow
    source ~/optimism/.envrc
    fund_addresses
    deploy_contracts
    generate_genesis_files
    echo "Setup completed."
}

main