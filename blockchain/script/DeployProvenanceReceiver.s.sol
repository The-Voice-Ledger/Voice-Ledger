// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";
import {ProvenanceDataReceiver} from "../src/ProvenanceDataReceiver.sol";

/**
 * @title  DeployProvenanceReceiver
 * @notice Standalone deployment for the CRE DON report receiver.
 * @dev    Deploys only ProvenanceDataReceiver - use this when the other
 *         Voice Ledger contracts are already live and unchanged.
 *
 *  Usage (Base Sepolia):
 *    source .env && forge script script/DeployProvenanceReceiver.s.sol:DeployProvenanceReceiver \
 *      --rpc-url $BASE_SEPOLIA_RPC_URL \
 *      --private-key $PRIVATE_KEY_SEP \
 *      --broadcast \
 *      --verify \
 *      --verifier-url "https://api.etherscan.io/v2/api?chainid=84532" \
 *      --etherscan-api-key $ETHERSCAN_API_KEY \
 *      --via-ir
 *
 *  Usage (local Anvil):
 *    forge script script/DeployProvenanceReceiver.s.sol:DeployProvenanceReceiver \
 *      --rpc-url http://127.0.0.1:8545 \
 *      --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
 *      --broadcast
 */
contract DeployProvenanceReceiver is Script {

    function run() external returns (ProvenanceDataReceiver) {
        vm.startBroadcast();

        // Forwarder = deployer.  In production this would be the KeystoneRouter address.
        ProvenanceDataReceiver receiver = new ProvenanceDataReceiver(msg.sender);

        vm.stopBroadcast();

        console2.log("==========================================");
        console2.log("ProvenanceDataReceiver Deployed");
        console2.log("==========================================");
        console2.log("");
        console2.log("  Address:", address(receiver));
        console2.log("  Forwarder (deployer):", msg.sender);
        console2.log("  Chain ID:", block.chainid);
        console2.log("");
        console2.log("Update your .env:");
        console2.log(string.concat("  PROVENANCE_RECEIVER_ADDRESS=", _addrStr(address(receiver))));
        console2.log("");

        return receiver;
    }

    function _addrStr(address _a) private pure returns (string memory) {
        bytes memory s = new bytes(40);
        for (uint256 i = 0; i < 20; i++) {
            bytes1 b = bytes1(uint8(uint256(uint160(_a)) / (2 ** (8 * (19 - i)))));
            bytes1 hi = bytes1(uint8(b) / 16);
            bytes1 lo = bytes1(uint8(b) - 16 * uint8(hi));
            s[2 * i] = _char(hi);
            s[2 * i + 1] = _char(lo);
        }
        return string(abi.encodePacked("0x", string(s)));
    }

    function _char(bytes1 b) private pure returns (bytes1 c) {
        if (uint8(b) < 10) return bytes1(uint8(b) + 0x30);
        else return bytes1(uint8(b) + 0x57);
    }
}
