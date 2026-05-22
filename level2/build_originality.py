"""Level II: originality score (0-1) per repo = share of credit kept by the
repo itself vs. flowing to its dependencies.

No public originality labels exist, so there is nothing to train/validate
against. Instead this uses direct LLM-juror assessment against Pond's rubric
(0.2 = fork/wrapper, 0.5 = heavy deps + substantial own work, 0.8 = mostly
original), informed by what each repo actually is in the Ethereum ecosystem.
"""

from __future__ import annotations
import pandas as pd

# originality keyed by lowercase owner/repo
ORIG = {
    # execution / consensus clients: substantial original impl, real lib use
    "ethereum/go-ethereum": 0.68, "offchainlabs/prysm": 0.58, "sigp/lighthouse": 0.60,
    "erigontech/erigon": 0.60, "consensys/teku": 0.55, "nethermindeth/nethermind": 0.60,
    "hyperledger/besu": 0.58, "paradigmxyz/reth": 0.65, "status-im/nimbus-eth2": 0.60,
    "chainsafe/lodestar": 0.50, "grandinetech/grandine": 0.60, "lambdaclass/ethrex": 0.55,
    "lambdaclass/lambda_ethereum_consensus": 0.55, "erigontech/silkworm": 0.55,
    "nethermindeth/juno": 0.55,
    # compilers / languages: original
    "argotorg/solidity": 0.78, "vyperlang/vyper": 0.76, "argotorg/fe": 0.60,
    # specs / standards / data
    "ethereum/eips": 0.70, "ethereum/consensus-specs": 0.74, "ethereum/execution-apis": 0.65,
    "ethdebug/format": 0.60, "ethereum-lists/chains": 0.30, "defillama/chainlist": 0.30,
    # EVM / crypto / zk
    "ipsilon/evmone": 0.65, "herumi/mcl": 0.70, "supranational/blst": 0.70,
    "consensys/gnark-crypto": 0.62, "arkworks-rs/algebra": 0.62, "paulmillr/noble-curves": 0.62,
    "skalenetwork/libbls": 0.50, "chainsafe/bls": 0.42, "ethereum/py_ecc": 0.55,
    "axiom-crypto/snark-verifier": 0.55, "0xmiden/miden-vm": 0.65, "risc0/risc0-ethereum": 0.42,
    "plonky3/plonky3": 0.65, "succinctlabs/sp1": 0.60, "succinctlabs/op-succinct": 0.40,
    "succinctlabs/rsp": 0.42, "powdr-labs/powdr": 0.60, "lambdaclass/lambdaworks": 0.60,
    "ethereum/js-ethereum-cryptography": 0.40,
    # dev tools / frameworks / libraries
    "foundry-rs/foundry": 0.55, "nomicfoundation/hardhat": 0.50, "wevm/viem": 0.50,
    "ethers-io/ethers.js": 0.55, "ethereum/web3.py": 0.45, "hyperledger-web3j/web3j": 0.45,
    "lfdt-web3j/web3j": 0.45, "nethereum/nethereum": 0.45, "alloy-rs/alloy": 0.50,
    "argotorg/hevm": 0.58, "a16z/halmos": 0.50, "a16z/helios": 0.55, "protofire/solhint": 0.42,
    "argotorg/sourcify": 0.45, "cyfrin/aderyn": 0.42, "certora/certoraprover": 0.60,
    "vyperlang/titanoboa": 0.45, "dl-solarity/solidity-lib": 0.38, "vectorized/solady": 0.55,
    "openzeppelin/openzeppelin-contracts": 0.50, "safe-global/safe-smart-account": 0.55,
    "eth-infinitism/account-abstraction": 0.55, "scaffold-eth/scaffold-eth-2": 0.28,
    "wighawag/hardhat-deploy": 0.35, "intellij-solidity/intellij-solidity": 0.45,
    "remix-project-org/remix-project": 0.50, "shazow/whatsabi": 0.50,
    "evmts/tevm-monorepo": 0.40, "edb-rs/edb": 0.45, "holiman/goevmlab": 0.50,
    "otterscan/otterscan": 0.45, "blockscout/blockscout": 0.55, "trueblocks/trueblocks-core": 0.55,
    "l2beat/l2beat": 0.42, "defillama/defillama-adapters": 0.40, "swiss-knife-xyz/swiss-knife": 0.35,
    "taikoxyz/taiko-mono": 0.45, "offchainlabs/stylus-sdk-rs": 0.45, "argotorg/act": 0.55,
    "apeworx/ape": 0.45, "libp2p/libp2p": 0.60, "wealdtech/ethdo": 0.50,
    # infra / ops / packaging / relays
    "ethpandaops/checkpointz": 0.50, "ethpandaops/ethereum-package": 0.30,
    "ethpandaops/ethereum-helm-charts": 0.30, "ethstaker/eth-docker": 0.25,
    "ethstaker/ethstaker-deposit-cli": 0.35, "dappnode/dappnode": 0.35,
    "smartcontracts/simple-optimism-node": 0.30, "aestus-relay/mev-boost-relay": 0.40,
    "flashbots/mev-boost": 0.55, "flashbots/mev-boost-relay": 0.55, "flashbots/rbuilder": 0.60,
    "commit-boost/commit-boost-client": 0.55,
    "espressosystems/jellyfish": 0.58, "deepfunding/dependency-graph": 0.40,
}


def main() -> None:
    elo = pd.read_csv("level1/data/elo_phase2.csv")
    rows, missing = [], []
    for item in elo["item"]:
        o = ORIG.get(item.lower())
        if o is None:
            missing.append(item)
            o = 0.5
        rows.append({"repo": "https://github.com/" + item, "originality": o})
    if missing:
        print("UNMATCHED (defaulted 0.5):", missing)
    out = pd.DataFrame(rows)
    out.to_csv("level2/submission_originality.csv", index=False)
    print(f"wrote {len(out)} rows; range [{out['originality'].min()}, {out['originality'].max()}], mean {out['originality'].mean():.3f}")


if __name__ == "__main__":
    main()
