package main

import (
	"context"
	"crypto/ecdsa"
	"fmt"
	"math/big"
	"os"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/crypto"
	"github.com/ethereum/go-ethereum/ethclient"
)

func main() {
	client, err := ethclient.Dial(os.Getenv("L1_RPC_URL"))
	if err != nil {
		fmt.Println("Failed to connect to the Ethereum client: %v", err)
	}

	privateKey, err := crypto.HexToECDSA(os.Getenv("SENDER_PRIVATE_KEY"))
	if err != nil {
		fmt.Println("Failed to parse private key: %v", err)
	}

	// Define the recipient addresses and amounts
	recipients := map[string]string{
		os.Getenv("GS_ADMIN_ADDRESS"):    "0.2", // Amount in ETH
		os.Getenv("GS_PROPOSER_ADDRESS"): "0.2",
		os.Getenv("GS_BATCHER_ADDRESS"):  "0.1",
	}

	for address, amountStr := range recipients {
		amountInEth, ok := new(big.Float).SetString(amountStr)
		if !ok {
			fmt.Println("Invalid amount: %s", amountStr)
		}
		wei := new(big.Int)
		amountInEth.Mul(amountInEth, big.NewFloat(1e18)).Int(wei)

		if err := sendEther(client, privateKey, address, wei); err != nil {
			fmt.Println("Failed to send Ether to %s: %v", address, err)
		}
	}
}

func sendEther(client *ethclient.Client, privateKey *ecdsa.PrivateKey, toAddress string, amount *big.Int) error {
	fromAddress := crypto.PubkeyToAddress(privateKey.PublicKey)
	nonce, err := client.PendingNonceAt(context.Background(), fromAddress)
	if err != nil {
		return err
	}

	gasLimit := uint64(21000) // in units
	gasPrice, err := client.SuggestGasPrice(context.Background())
	if err != nil {
		return err
	}

	to := common.HexToAddress(toAddress)
	tx := types.NewTransaction(nonce, to, amount, gasLimit, gasPrice, nil)

	chainID, err := client.NetworkID(context.Background())
	if err != nil {
		return err
	}

	signedTx, err := types.SignTx(tx, types.NewEIP155Signer(chainID), privateKey)
	if err != nil {
		return err
	}

	err = client.SendTransaction(context.Background(), signedTx)
	if err != nil {
		return err
	}

	fmt.Println("Sent %s ETH to %s: tx hash %s\n", amount.String(), toAddress, signedTx.Hash().Hex())
	return nil
}
