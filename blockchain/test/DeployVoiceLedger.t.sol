// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";
import {DeployVoiceLedger} from "../script/DeployVoiceLedger.s.sol";
import {HelperConfig} from "../script/HelperConfig.s.sol";
import {EPCISEventAnchor} from "../src/EPCISEventAnchor.sol";
import {CoffeeBatchToken} from "../src/CoffeeBatchToken.sol";
import {SettlementContract} from "../src/SettlementContract.sol";

contract DeployVoiceLedgerTest is Test {
    DeployVoiceLedger public deployer;
    HelperConfig public helperConfig;

    function setUp() public {
        deployer = new DeployVoiceLedger();
        helperConfig = new HelperConfig();
    }

    function test_DeployAllContracts() public {
        DeployVoiceLedger.DeployedContracts memory contracts = deployer.run();
        
        // Verify all contracts are deployed
        assertTrue(address(contracts.epcisEventAnchor) != address(0));
        assertTrue(address(contracts.coffeeBatchToken) != address(0));
        assertTrue(address(contracts.settlementContract) != address(0));
        
        // Verify EPCISEventAnchor is configured correctly
        assertEq(
            contracts.epcisEventAnchor.requiredRole(),
            "COOPERATIVE_MANAGER"
        );
        
        // Note: Owner will be the deployer (address(this) from deployer's perspective)
        // which is different in test context
    }

    function test_HelperConfigBaseSepoliaChainId() public {
        // Simulate Base Sepolia network
        vm.chainId(84532);
        
        HelperConfig config = new HelperConfig();
        HelperConfig.NetworkConfig memory networkConfig = config.activeNetworkConfig();
        
        assertEq(networkConfig.requiredRole, "COOPERATIVE_MANAGER");
        assertEq(networkConfig.baseTokenURI, "https://voiceledger.org/api/batch/{id}");
    }

    function test_HelperConfigAnvilChainId() public {
        // Simulate Anvil local network
        vm.chainId(31337);
        
        HelperConfig config = new HelperConfig();
        HelperConfig.NetworkConfig memory networkConfig = config.activeNetworkConfig();
        
        assertEq(networkConfig.requiredRole, "COOPERATIVE_MANAGER");
        assertEq(networkConfig.baseTokenURI, "http://localhost:8000/api/batch/{id}");
    }

    function test_IntegrationEndToEnd() public {
        // Deploy fresh contracts for this test
        vm.startPrank(address(this));
        EPCISEventAnchor epcisAnchor = new EPCISEventAnchor("COOPERATIVE_MANAGER");
        CoffeeBatchToken coffeeBatchToken = new CoffeeBatchToken();
        SettlementContract settlementContract = new SettlementContract();
        vm.stopPrank();
        
        address cooperative = makeAddr("cooperative");
        bytes32 eventHash = keccak256("test-event");
        string memory batchId = "BATCH-001";
        string memory metadata = '{"origin":"Ethiopia"}';
        
        // 1. Mint a batch token
        uint256 tokenId = coffeeBatchToken.mintBatch(
            cooperative,
            100,
            batchId,
            metadata,
            "QmUn4tfmog3BkQgzqx3mzvVNzedSpec4bDXsCx7B1nd93X"
        );
        assertEq(tokenId, 1);
        
        // 2. Anchor EPCIS event
        epcisAnchor.anchorEvent(
            eventHash,
            batchId,
            "commissioning"
        );
        assertTrue(epcisAnchor.isAnchored(eventHash));
        
        // 3. Execute settlement ($10,000 USD)
        settlementContract.settleCommissioning(
            tokenId,
            cooperative,
            1000000,  // $10,000.00 in cents
            2,        // 2 decimals
            "USD",
            address(0)  // Off-chain payment
        );
        assertTrue(settlementContract.isSettled(tokenId));
        
        // Verify final state
        assertEq(coffeeBatchToken.balanceOf(cooperative, tokenId), 100);
        
        SettlementContract.SettlementInfo memory settlementInfo = settlementContract.getSettlement(tokenId);
        
        assertEq(settlementInfo.recipient, cooperative);
        assertEq(settlementInfo.amount, 1000000);
        assertEq(settlementInfo.decimals, 2);
        assertEq(settlementInfo.currencyCode, "USD");
        assertTrue(settlementInfo.settled);
    }
}
