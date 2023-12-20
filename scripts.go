package main

import (
    "bufio"
    "context"
    "crypto/ecdsa"
    "fmt"
    "log"
    "math/big"
    "os"
    "os/exec"
    "regexp"
    "strings"

    "github.com/ethereum/go-ethereum"
    "github.com/ethereum/go-ethereum/common"
    "github.com/ethereum/go-ethereum/core/types"
    "github.com/ethereum/go-ethereum/crypto"
    "github.com/ethereum/go-ethereum/ethclient"
)

func main() {
    // Set the necessary environment variables
    os.Setenv("L1_RPC_URL", "https://eth-sepolia.g.alchemy.com/v2/NhhIPMo7D3fr8AKPHMqWfrDKbQGWbR7_")
    os.Setenv("L1_RPC_KIND", "sepolia")

    // Execute the necessary shell commands
    runShellCommand("cd", "~/optimism")
    runShellCommand("cp", ".envrc.example", ".envrc")

    // Generate new Ethereum addresses and write them to .envrc file
    output := runShellCommandAndGetOutput("./packages/contracts-bedrock/scripts/getting-started/wallets.sh")
    parseAndAppendEnvVariables(output)

    // Load the environment variables
    runShellCommand("direnv", "allow")

    // Funding logic
    client, err := ethclient.Dial(os.Getenv("L1_RPC_URL"))
    if err != nil {
        log.Fatalf("Failed to connect to the Ethereum client: %v", err)
    }

    privateKey, err := crypto.HexToECDSA(os.Getenv("71061e8174d4a2df7f51b04c874470b9199af4bf650c6d5a9da5761f6e4f3ad2"))
    if err != nil {
        log.Fatalf("Failed to parse private key: %v", err)
    }

    fundAddresses(client, privateKey)

    // Configure the network
    runShellCommand("cd", "packages/contracts-bedrock")
    runShellCommand("./scripts/getting-started/config.sh")

    // Deploy the L1 contracts
    privateKey := os.Getenv("GS_ADMIN_PRIVATE_KEY")
    l1RPCURL := os.Getenv("L1_RPC_URL")
    deployContracts(privateKey, l1RPCURL)

    // Generate contract artifacts
    generateArtifacts(l1RPCURL)

    // Navigate to the op-node package
    runShellCommand("cd", "~/optimism/op-node")

    // Generate the genesis.json and rollup.json files
    generateGenesisFiles()

    // Create a JSON Web Token for authentication
    runShellCommand("openssl", "rand", "-hex", "32", ">", "jwt.txt")

    // Copy genesis files into the op-geth directory
    runShellCommand("cp", "genesis.json", "~/op-geth")
    runShellCommand("cp", "jwt.txt", "~/op-geth")

    fmt.Println("Setup completed.")
}

func generateGenesisFiles() {
    deployConfig := "../packages/contracts-bedrock/deploy-config/getting-started.json"
    deploymentDir := "../packages/contracts-bedrock/deployments/getting-started/"
    l1RPCURL := os.Getenv("L1_RPC_URL")
    runShellCommand("go", "run", "cmd/main.go", "genesis", "l2",
        "--deploy-config", deployConfig,
        "--deployment-dir", deploymentDir,
        "--outfile.l2", "genesis.json",
        "--outfile.rollup", "rollup.json",
        "--l1-rpc", l1RPCURL)
}

func deployContracts(privateKey string, rpcURL string) {
    runShellCommand("forge", "script", "scripts/Deploy.s.sol:Deploy", "--private-key", privateKey, "--broadcast", "--rpc-url", rpcURL)
}

// generateArtifacts generates contract artifacts
func generateArtifacts(rpcURL string) {
    runShellCommand("forge", "script", "scripts/Deploy.s.sol:Deploy", "--sig", "sync()", "--rpc-url", rpcURL)
}

// runShellCommand executes a shell command
func runShellCommand(command string, args ...string) {
    cmd := exec.Command(command, args...)
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr
    err := cmd.Run()
    if err != nil {
        log.Fatalf("Error running %s: %v", command, err)
    }
}

// runShellCommandAndGetOutput executes a shell command and returns its output
func runShellCommandAndGetOutput(command string, args ...string) string {
    cmd := exec.Command(command, args...)
    output, err := cmd.Output()
    if err != nil {
        log.Fatalf("Error running %s: %v", command, err)
    }
    return string(output)
}

// parseAndAppendEnvVariables parses the output of wallets.sh and appends variables to .envrc
func parseAndAppendEnvVariables(output string) {
    lines := strings.Split(output, "\n")
    regex := regexp.MustCompile(`export (\w+)=(\w+)`)

    file, err := os.OpenFile(".envrc", os.O_APPEND|os.O_WRONLY, 0644)
    if err != nil {
        log.Fatalf("Error opening .envrc file: %v", err)
    }
    defer file.Close()

    for _, line := range lines {
        matches := regex.FindStringSubmatch(line)
        if len(matches) == 3 {
            _, err := file.WriteString(fmt.Sprintf("export %s=%s\n", matches[1], matches[2]))
            if err != nil {
                log.Fatalf("Error writing to .envrc file: %v", err)
            }
        }
    }
}

// fundAddresses sends ETH to the specified Ethereum addresses
func fundAddresses(client *ethclient.Client, privateKey *ecdsa.PrivateKey) {
    // Define the recipient addresses and amounts
    recipients := map[string]*big.Int{
        os.Getenv("GS_ADMIN_ADDRESS"):    big.NewInt(0.2e18),
        os.Getenv("GS_PROPOSER_ADDRESS"): big.NewInt(0.2e18),
        os.Getenv("GS_BATCHER_ADDRESS"):  big.NewInt(0.1e18),
    }

    for address, amount := range recipients {
        if err := sendEther(client, privateKey, address, amount); err != nil {
            log.Printf("Failed to send Ether to %s: %v", address, err)
        }
    }
}

// sendEther performs the actual sending of Ether
func sendEther(client *ethclient.Client, privateKey *ecdsa.PrivateKey, toAddress string, amount *big.Int) error {
    fromAddress := crypto.PubkeyToAddress(privateKey.PublicKey)
    nonce, err := client.PendingNonceAt(context.Background(), fromAddress)
    if err != nil {
        return err
    }

    gasPrice, err := client.SuggestGasPrice(context.Background())
    if err != nil {
        return err
    }

    auth := bind.NewKeyedTransactor(privateKey)
    auth.Nonce = big.NewInt(int64(nonce))
    auth.Value = amount       // amount in wei
    auth.GasLimit = uint64(0) // set to 0 for simplicity
    auth.GasPrice = gasPrice

    tx := types.NewTransaction(nonce, common.HexToAddress(toAddress), amount, auth.GasLimit, gasPrice, nil)

    signedTx, err := auth.Signer(types.HomesteadSigner{}, auth.From, tx)
    if err != nil {
        return err
    }

    err = client.SendTransaction(context.Background(), signedTx)
    if err != nil {
        return err
    }

    fmt.Printf("tx sent: %s\n", signedTx.Hash().Hex())
    return nil
}

// Additional functions as necessary ...
