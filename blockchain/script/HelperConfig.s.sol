// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";

/**
 * @title HelperConfig
 * @notice Network-specific configurations for Voice Ledger contract deployments
 * @dev Supports Base Sepolia (testnet) and Anvil (local testing)
 */
contract HelperConfig is Script {
    
    struct NetworkConfig {
        string requiredRole;        // Role required for EPCISEventAnchor
        string baseTokenURI;        // Base URI for CoffeeBatchToken metadata
    }

    function activeNetworkConfig() public view returns (NetworkConfig memory) {
        if (block.chainid == 84532) {
            // Base Sepolia testnet
            return getBaseSepoliaConfig();
        } else if (block.chainid == 31337) {
            // Anvil local testing
            return getAnvilConfig();
        } else {
            // Default to Anvil config for unknown networks
            return getAnvilConfig();
        }
    }

    /**
     * @notice Get Base Sepolia network configuration
     * @return NetworkConfig struct with Base Sepolia settings
     */
    function getBaseSepoliaConfig() public pure returns (NetworkConfig memory) {
        NetworkConfig memory baseSepoliaConfig = NetworkConfig({
            requiredRole: "COOPERATIVE_MANAGER",
            baseTokenURI: "https://voiceledger.org/api/batch/{id}"
        });
        return baseSepoliaConfig;
    }

    /**
     * @notice Get Anvil local network configuration
     * @return NetworkConfig struct with Anvil settings
     */
    function getAnvilConfig() public pure returns (NetworkConfig memory) {
        NetworkConfig memory anvilConfig = NetworkConfig({
            requiredRole: "COOPERATIVE_MANAGER",
            baseTokenURI: "http://localhost:8000/api/batch/{id}"
        });
        return anvilConfig;
    }
}
