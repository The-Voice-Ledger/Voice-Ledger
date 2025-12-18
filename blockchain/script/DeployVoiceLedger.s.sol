// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";
import {EPCISEventAnchor} from "../src/EPCISEventAnchor.sol";
import {CoffeeBatchToken} from "../src/CoffeeBatchToken.sol";
import {SettlementContract} from "../src/SettlementContract.sol";
import {HelperConfig} from "./HelperConfig.s.sol";

/**
 * @title DeployVoiceLedger
 * @notice Deployment script for all Voice Ledger smart contracts
 * @dev Deploys EPCISEventAnchor, CoffeeBatchToken, and SettlementContract
 */
contract DeployVoiceLedger is Script {
    
    struct DeployedContracts {
        EPCISEventAnchor epcisEventAnchor;
        CoffeeBatchToken coffeeBatchToken;
        SettlementContract settlementContract;
    }

    /**
     * @notice Deploy all Voice Ledger contracts
     * @return DeployedContracts struct containing all deployed contract addresses
     */
    function run() external returns (DeployedContracts memory) {
        // Get network-specific configuration
        HelperConfig helperConfig = new HelperConfig();
        HelperConfig.NetworkConfig memory config = helperConfig.activeNetworkConfig();
        
        // Start broadcasting transactions
        vm.startBroadcast();
        
        // 1. Deploy EPCISEventAnchor (for EPCIS event hash anchoring)
        EPCISEventAnchor epcisEventAnchor = new EPCISEventAnchor(config.requiredRole);
        
        // 2. Deploy CoffeeBatchToken (ERC-1155 for batch tokens)
        CoffeeBatchToken coffeeBatchToken = new CoffeeBatchToken();
        
        // 3. Deploy SettlementContract (for automatic settlements)
        SettlementContract settlementContract = new SettlementContract();
        
        vm.stopBroadcast();
        
        // Log deployed addresses
        _logDeployedAddresses(epcisEventAnchor, coffeeBatchToken, settlementContract);
        
        return DeployedContracts({
            epcisEventAnchor: epcisEventAnchor,
            coffeeBatchToken: coffeeBatchToken,
            settlementContract: settlementContract
        });
    }
    
    /**
     * @notice Log deployed contract addresses for easy reference
     * @dev These addresses should be saved to .env file for backend integration
     */
    function _logDeployedAddresses(
        EPCISEventAnchor epcisEventAnchor,
        CoffeeBatchToken coffeeBatchToken,
        SettlementContract settlementContract
    ) private view {
        console2.log("==========================================");
        console2.log("Voice Ledger Contracts Deployed");
        console2.log("==========================================");
        console2.log("");
        console2.log("EPCISEventAnchor:", address(epcisEventAnchor));
        console2.log("CoffeeBatchToken:", address(coffeeBatchToken));
        console2.log("SettlementContract:", address(settlementContract));
        console2.log("");
        console2.log("==========================================");
        console2.log("Add these to your .env file:");
        console2.log("==========================================");
        console2.log("");
        console2.log(string.concat("EPCIS_EVENT_ANCHOR_ADDRESS=", _addressToString(address(epcisEventAnchor))));
        console2.log(string.concat("COFFEE_BATCH_TOKEN_ADDRESS=", _addressToString(address(coffeeBatchToken))));
        console2.log(string.concat("SETTLEMENT_CONTRACT_ADDRESS=", _addressToString(address(settlementContract))));
        console2.log("");
    }
    
    /**
     * @notice Convert address to string for logging
     * @dev Helper function for console output
     */
    function _addressToString(address _addr) private pure returns (string memory) {
        bytes memory s = new bytes(40);
        for (uint256 i = 0; i < 20; i++) {
            bytes1 b = bytes1(uint8(uint256(uint160(_addr)) / (2**(8*(19 - i)))));
            bytes1 hi = bytes1(uint8(b) / 16);
            bytes1 lo = bytes1(uint8(b) - 16 * uint8(hi));
            s[2*i] = _char(hi);
            s[2*i+1] = _char(lo);
        }
        return string(abi.encodePacked("0x", string(s)));
    }
    
    function _char(bytes1 b) private pure returns (bytes1 c) {
        if (uint8(b) < 10) return bytes1(uint8(b) + 0x30);
        else return bytes1(uint8(b) + 0x57);
    }
}
