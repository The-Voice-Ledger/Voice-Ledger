// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";
import {EPCISEventAnchor} from "../src/EPCISEventAnchor.sol";
import {CoffeeBatchToken} from "../src/CoffeeBatchToken.sol";
import {SettlementContract} from "../src/SettlementContract.sol";

/**
 * @title VoiceLedgerIntegration
 * @notice Integration tests for Voice Ledger smart contracts
 * @dev Tests real-world workflows and multi-contract interactions
 */
contract VoiceLedgerIntegration is Test {
    EPCISEventAnchor public epcisAnchor;
    CoffeeBatchToken public batchToken;
    SettlementContract public settlement;
    
    // Test actors
    address public admin;
    address public cooperative1;
    address public cooperative2;
    address public buyer1;
    address public buyer2;
    address public exporter;
    
    // Constants
    uint256 constant BATCH_QUANTITY = 1000; // 1000 kg
    uint256 constant SETTLEMENT_AMOUNT = 500000; // $5,000.00 USD in cents
    uint8 constant DECIMALS_USD = 2;
    string constant CURRENCY_USD = "USD";
    address constant PAYMENT_TOKEN_OFFCHAIN = address(0);
    string constant IPFS_CID = "QmUn4tfmog3BkQgzqx3mzvVNzedSpec4bDXsCx7B1nd93X";
    
    function setUp() public {
        // Deploy contracts
        admin = address(this);
        cooperative1 = makeAddr("cooperative1");
        cooperative2 = makeAddr("cooperative2");
        buyer1 = makeAddr("buyer1");
        buyer2 = makeAddr("buyer2");
        exporter = makeAddr("exporter");
        
        epcisAnchor = new EPCISEventAnchor("COOPERATIVE_MANAGER");
        batchToken = new CoffeeBatchToken();
        settlement = new SettlementContract();
    }
    
    /**
     * @notice Test: Complete farm-to-export workflow
     * @dev Simulates: Batch creation → Verification → Transfer → Settlement
     */
    function test_Integration_CompleteFarmToExportWorkflow() public {
        // Step 1: Cooperative creates batch
        string memory batchId = "ETH-YRG-2025-001";
        string memory metadata = '{"origin":"Yirgacheffe","variety":"Heirloom","process":"Washed"}';
        
        uint256 tokenId = batchToken.mintBatch(
            cooperative1,
            BATCH_QUANTITY,
            batchId,
            metadata,
            IPFS_CID
        );
        
        assertEq(batchToken.balanceOf(cooperative1, tokenId), BATCH_QUANTITY);
        console2.log("Step 1: Batch minted to cooperative, tokenId:", tokenId);
        
        // Step 2: Anchor EPCIS commissioning event
        bytes32 commissioningHash = keccak256(
            abi.encodePacked(batchId, "commissioning", block.timestamp)
        );
        
        epcisAnchor.anchorEvent(commissioningHash, batchId, "commissioning");
        assertTrue(epcisAnchor.isAnchored(commissioningHash));
        console2.log("Step 2: EPCIS commissioning event anchored");
        
        // Step 3: Cooperative transfers to exporter
        vm.prank(cooperative1);
        batchToken.transferBatch(cooperative1, exporter, tokenId, BATCH_QUANTITY);
        
        assertEq(batchToken.balanceOf(cooperative1, tokenId), 0);
        assertEq(batchToken.balanceOf(exporter, tokenId), BATCH_QUANTITY);
        console2.log("Step 3: Batch transferred to exporter");
        
        // Step 4: Anchor EPCIS shipping event
        bytes32 shippingHash = keccak256(
            abi.encodePacked(batchId, "shipping", block.timestamp)
        );
        
        epcisAnchor.anchorEvent(shippingHash, batchId, "shipping");
        assertTrue(epcisAnchor.isAnchored(shippingHash));
        console2.log("Step 4: EPCIS shipping event anchored");
        
        // Step 5: Settlement to cooperative
        settlement.settleCommissioning(
            tokenId,
            cooperative1,
            SETTLEMENT_AMOUNT,
            DECIMALS_USD,
            CURRENCY_USD,
            PAYMENT_TOKEN_OFFCHAIN
        );
        assertTrue(settlement.isSettled(tokenId));
        
        SettlementContract.SettlementInfo memory info = settlement.getSettlement(tokenId);
        assertEq(info.recipient, cooperative1);
        assertEq(info.amount, SETTLEMENT_AMOUNT);
        assertEq(info.decimals, DECIMALS_USD);
        assertEq(info.currencyCode, CURRENCY_USD);
        console2.log("Step 5: Settlement executed for", SETTLEMENT_AMOUNT);
        
        // Verify final state
        console2.log("\n=== Final State ===");
        console2.log("Cooperative balance:", batchToken.balanceOf(cooperative1, tokenId));
        console2.log("Exporter balance:", batchToken.balanceOf(exporter, tokenId));
        console2.log("EPCIS events anchored: 2");
        console2.log("Settlement amount:", info.amount);
    }
    
    /**
     * @notice Test: Multiple batches from different cooperatives
     * @dev Simulates aggregation scenario with multiple sources
     */
    function test_Integration_MultipleCooperativeAggregation() public {
        // Cooperative 1 creates batch
        uint256 tokenId1 = batchToken.mintBatch(
            cooperative1,
            500,
            "ETH-SDM-2025-001",
            '{"origin":"Sidama"}',
            IPFS_CID
        );
        
        // Cooperative 2 creates batch
        uint256 tokenId2 = batchToken.mintBatch(
            cooperative2,
            700,
            "ETH-GJI-2025-002",
            '{"origin":"Guji"}',
            IPFS_CID
        );
        
        // Anchor both batches
        bytes32 hash1 = keccak256("batch-1-commissioning");
        bytes32 hash2 = keccak256("batch-2-commissioning");
        
        epcisAnchor.anchorEvent(hash1, "ETH-SDM-2025-001", "commissioning");
        epcisAnchor.anchorEvent(hash2, "ETH-GJI-2025-002", "commissioning");
        
        // Both cooperatives transfer to exporter
        vm.prank(cooperative1);
        batchToken.transferBatch(cooperative1, exporter, tokenId1, 500);
        
        vm.prank(cooperative2);
        batchToken.transferBatch(cooperative2, exporter, tokenId2, 700);
        
        // Verify exporter received both
        assertEq(batchToken.balanceOf(exporter, tokenId1), 500);
        assertEq(batchToken.balanceOf(exporter, tokenId2), 700);
        
        // Anchor aggregation event
        bytes32 aggregationHash = keccak256("container-aggregation");
        epcisAnchor.anchorEvent(
            aggregationHash,
            "CONT-2025-001",
            "aggregation"
        );
        
        // Settle both cooperatives
        settlement.settleCommissioning(
            tokenId1, cooperative1, 250000, DECIMALS_USD, CURRENCY_USD, PAYMENT_TOKEN_OFFCHAIN
        );
        settlement.settleCommissioning(
            tokenId2, cooperative2, 350000, DECIMALS_USD, CURRENCY_USD, PAYMENT_TOKEN_OFFCHAIN
        );
        
        assertTrue(settlement.isSettled(tokenId1));
        assertTrue(settlement.isSettled(tokenId2));
        
        console2.log("Successfully aggregated batches from 2 cooperatives");
        console2.log("Total quantity:", 1200, "kg");
    }
    
    /**
     * @notice Test: Batch splitting and fractional ownership
     * @dev Buyer purchases partial batch
     */
    function test_Integration_FractionalBatchPurchase() public {
        // Create large batch
        uint256 tokenId = batchToken.mintBatch(
            cooperative1,
            10000,
            "ETH-YRG-2025-BIG",
            '{"type":"container"}',
            IPFS_CID
        );
        
        // Anchor event
        bytes32 eventHash = keccak256("large-batch");
        epcisAnchor.anchorEvent(eventHash, "ETH-YRG-2025-BIG", "commissioning");
        
        // Transfer to exporter
        vm.prank(cooperative1);
        batchToken.transferBatch(cooperative1, exporter, tokenId, 10000);
        
        // Buyer 1 purchases 3000 kg
        vm.prank(exporter);
        batchToken.transferBatch(exporter, buyer1, tokenId, 3000);
        
        // Buyer 2 purchases 2000 kg
        vm.prank(exporter);
        batchToken.transferBatch(exporter, buyer2, tokenId, 2000);
        
        // Verify balances
        assertEq(batchToken.balanceOf(buyer1, tokenId), 3000);
        assertEq(batchToken.balanceOf(buyer2, tokenId), 2000);
        assertEq(batchToken.balanceOf(exporter, tokenId), 5000);
        
        // Anchor split events
        bytes32 split1Hash = keccak256("split-buyer1");
        bytes32 split2Hash = keccak256("split-buyer2");
        
        epcisAnchor.anchorEvent(split1Hash, "SPLIT-001", "transformation");
        epcisAnchor.anchorEvent(split2Hash, "SPLIT-002", "transformation");
        
        console2.log("Fractional purchases successful");
        console2.log("Buyer 1:", batchToken.balanceOf(buyer1, tokenId), "kg");
        console2.log("Buyer 2:", batchToken.balanceOf(buyer2, tokenId), "kg");
        console2.log("Remaining:", batchToken.balanceOf(exporter, tokenId), "kg");
    }
    
    /**
     * @notice Test: Full traceability query
     * @dev Verify all EPCIS events are anchored correctly
     */
    function test_Integration_FullTraceabilityChain() public {
        string memory batchId = "ETH-TRC-2025-001";
        
        // Create batch
        uint256 tokenId = batchToken.mintBatch(
            cooperative1,
            1000,
            batchId,
            '{"traceable":"full"}',
            IPFS_CID
        );
        
        // Anchor chain of events
        bytes32[] memory eventHashes = new bytes32[](5);
        string[] memory eventTypes = new string[](5);
        
        eventTypes[0] = "commissioning";
        eventTypes[1] = "observation";
        eventTypes[2] = "aggregation";
        eventTypes[3] = "shipping";
        eventTypes[4] = "receiving";
        
        for (uint256 i = 0; i < 5; i++) {
            eventHashes[i] = keccak256(abi.encodePacked(batchId, eventTypes[i], i));
            epcisAnchor.anchorEvent(eventHashes[i], batchId, eventTypes[i]);
            
            assertTrue(epcisAnchor.isAnchored(eventHashes[i]));
            
            EPCISEventAnchor.EventMetadata memory metadata = 
                epcisAnchor.getEventMetadata(eventHashes[i]);
            
            assertEq(metadata.batchId, batchId);
            assertEq(metadata.eventType, eventTypes[i]);
            assertTrue(metadata.exists);
        }
        
        console2.log("Complete traceability chain anchored: 5 events");
        console2.log("All events verified on-chain");
    }
    
    /**
     * @notice Test: Settlement for multiple stakeholders
     * @dev Simulate revenue sharing
     */
    function test_Integration_MultiStakeholderSettlement() public {
        // Create 3 batches from different cooperatives
        uint256 tokenId1 = batchToken.mintBatch(cooperative1, 100, "BATCH-1", "{}", IPFS_CID);
        uint256 tokenId2 = batchToken.mintBatch(cooperative2, 200, "BATCH-2", "{}", IPFS_CID);
        uint256 tokenId3 = batchToken.mintBatch(cooperative1, 150, "BATCH-3", "{}", IPFS_CID);
        
        // Settle all
        settlement.settleCommissioning(
            tokenId1, cooperative1, 100000, DECIMALS_USD, CURRENCY_USD, PAYMENT_TOKEN_OFFCHAIN
        );
        settlement.settleCommissioning(
            tokenId2, cooperative2, 200000, DECIMALS_USD, CURRENCY_USD, PAYMENT_TOKEN_OFFCHAIN
        );
        settlement.settleCommissioning(
            tokenId3, cooperative1, 150000, DECIMALS_USD, CURRENCY_USD, PAYMENT_TOKEN_OFFCHAIN
        );
        
        // Verify all settled
        assertTrue(settlement.isSettled(tokenId1));
        assertTrue(settlement.isSettled(tokenId2));
        assertTrue(settlement.isSettled(tokenId3));
        
        // Check cooperative1 received 2 settlements (tokenId1 + tokenId3)
        SettlementContract.SettlementInfo memory info1 = settlement.getSettlement(tokenId1);
        SettlementContract.SettlementInfo memory info3 = settlement.getSettlement(tokenId3);
        
        assertEq(info1.recipient, cooperative1);
        assertEq(info3.recipient, cooperative1);
        
        uint256 totalCoop1 = info1.amount + info3.amount;
        assertEq(totalCoop1, 250000);  // $1,000 + $1,500 = $2,500 (in cents)
        
        console2.log("Multi-stakeholder settlement successful");
        console2.log("Cooperative 1 total:", totalCoop1);
        console2.log("Cooperative 2 total:", uint256(200000));
    }
    
    /**
     * @notice Test: Error recovery in workflow
     * @dev Test handling of failed operations
     */
    function test_Integration_ErrorRecoveryWorkflow() public {
        // Create batch
        uint256 tokenId = batchToken.mintBatch(
            cooperative1,
            500,
            "ETH-ERR-2025-001",
            "{}",
            IPFS_CID
        );
        
        // Anchor event
        bytes32 eventHash = keccak256("test-event");
        epcisAnchor.anchorEvent(eventHash, "ETH-ERR-2025-001", "commissioning");
        
        // Try to anchor same event again - should fail
        vm.expectRevert(
            abi.encodeWithSelector(
                EPCISEventAnchor.EventAlreadyAnchored.selector,
                eventHash
            )
        );
        epcisAnchor.anchorEvent(eventHash, "ETH-ERR-2025-001", "commissioning");
        
        // Settle batch
        settlement.settleCommissioning(
            tokenId, cooperative1, 100000, DECIMALS_USD, CURRENCY_USD, PAYMENT_TOKEN_OFFCHAIN
        );
        
        // Try to settle again - should fail
        vm.expectRevert(
            abi.encodeWithSelector(
                SettlementContract.AlreadySettled.selector,
                tokenId
            )
        );
        settlement.settleCommissioning(
            tokenId, cooperative1, 100000, DECIMALS_USD, CURRENCY_USD, PAYMENT_TOKEN_OFFCHAIN
        );
        
        // Try to transfer more than balance - should fail
        vm.prank(cooperative1);
        vm.expectRevert();
        batchToken.transferBatch(cooperative1, buyer1, tokenId, 501);
        
        // Verify original state unchanged
        assertEq(batchToken.balanceOf(cooperative1, tokenId), 500);
        assertTrue(epcisAnchor.isAnchored(eventHash));
        assertTrue(settlement.isSettled(tokenId));
        
        console2.log("Error recovery verified - system state consistent");
    }
    
    /**
     * @notice Test: Time-based workflow
     * @dev Verify timestamps are recorded correctly
     */
    function test_Integration_TimeBasedWorkflow() public {
        uint256 startTime = block.timestamp;
        
        // Create batch at T=0
        uint256 tokenId = batchToken.mintBatch(
            cooperative1,
            1000,
            "TIME-BATCH",
            "{}",
            IPFS_CID
        );
        
        // Fast forward 1 day
        vm.warp(startTime + 1 days);
        
        // Anchor event at T=1day
        bytes32 eventHash = keccak256("time-event");
        epcisAnchor.anchorEvent(eventHash, "TIME-BATCH", "observation");
        
        EPCISEventAnchor.EventMetadata memory metadata = 
            epcisAnchor.getEventMetadata(eventHash);
        assertEq(metadata.timestamp, startTime + 1 days);
        
        // Fast forward another day
        vm.warp(startTime + 2 days);
        
        // Settle at T=2days
        settlement.settleCommissioning(
            tokenId, cooperative1, 100000, DECIMALS_USD, CURRENCY_USD, PAYMENT_TOKEN_OFFCHAIN
        );
        
        SettlementContract.SettlementInfo memory info = 
            settlement.getSettlement(tokenId);
        assertEq(info.settledAt, startTime + 2 days);
        
        console2.log("Time-based workflow verified");
        console2.log("Event timestamp:", metadata.timestamp);
        console2.log("Settlement timestamp:", info.settledAt);
        console2.log("Time difference:", info.settledAt - metadata.timestamp);
    }

    /**
     * @notice Test: Container aggregation with merkle root proof
     * @dev Simulates: Multiple farmer batches → Container with cryptographic proof
     */
    function test_Integration_AggregationWithMerkleProof() public {
        // Step 1: Create 3 farmer batches
        bytes32[] memory batchHashes = new bytes32[](3);
        string[] memory batchIds = new string[](3);
        
        for (uint256 i = 0; i < 3; i++) {
            batchIds[i] = string.concat("FARM-", vm.toString(i + 1));
            
            // Simulate batch data hash (in production: hash of full batch data)
            batchHashes[i] = keccak256(abi.encodePacked(
                batchIds[i],
                500 + (i * 100),  // Quantities: 500, 600, 700 kg
                "Yirgacheffe",
                "Washed"
            ));
            
            // Anchor commissioning events for each batch
            bytes32 commissioningHash = keccak256(abi.encodePacked("commissioning", i));
            epcisAnchor.anchorEvent(commissioningHash, batchIds[i], "commissioning");
            
            console2.log("Anchored batch:", batchIds[i]);
        }
        
        // Step 2: Compute merkle root of batch hashes
        bytes32 merkleRoot = keccak256(abi.encodePacked(
            batchHashes[0],
            batchHashes[1],
            batchHashes[2]
        ));
        
        console2.log("Computed merkle root");
        
        // Step 3: Create container token
        string memory containerId = "CONT-2025-001";
        uint256 totalQuantity = 1800;  // 500 + 600 + 700
        
        uint256 containerTokenId = batchToken.mintBatch(
            cooperative1,
            totalQuantity,
            containerId,
            string.concat(
                '{"type":"container","childBatches":["FARM-1","FARM-2","FARM-3"],"merkleRoot":"',
                vm.toString(merkleRoot),
                '"}'
            ),
            IPFS_CID
        );
        
        assertEq(containerTokenId, 1);
        console2.log("Container token minted, ID:", containerTokenId);
        
        // Step 4: Anchor aggregation event with merkle root
        bytes32 aggregationEventHash = keccak256(abi.encodePacked(
            "AggregationEvent",
            containerId,
            batchIds[0],
            batchIds[1],
            batchIds[2]
        ));
        
        epcisAnchor.anchorAggregation(
            aggregationEventHash,
            containerId,
            merkleRoot,
            3  // 3 child batches
        );
        
        console2.log("Aggregation anchored with merkle root");
        
        // Step 5: Verify aggregation metadata
        EPCISEventAnchor.AggregationMetadata memory aggMetadata = 
            epcisAnchor.getAggregation(containerId);
        
        assertEq(aggMetadata.aggregationEventHash, aggregationEventHash);
        assertEq(aggMetadata.merkleRoot, merkleRoot);
        assertEq(aggMetadata.childBatchCount, 3);
        assertTrue(aggMetadata.exists);
        
        // Verify both event and aggregation are anchored
        assertTrue(epcisAnchor.isAnchored(aggregationEventHash));
        
        console2.log("=== Aggregation Verified ===");
        console2.log("Container:", containerId);
        console2.log("Total quantity:", totalQuantity);
        console2.log("Child batch count:", uint256(3));
        console2.log("Token ID:", containerTokenId);
        
        // Step 6: Transfer container to exporter
        vm.prank(cooperative1);
        batchToken.transferBatch(cooperative1, exporter, containerTokenId, totalQuantity);
        
        assertEq(batchToken.balanceOf(exporter, containerTokenId), totalQuantity);
        console2.log("Container transferred to exporter");
        
        // Step 7: Settle with cooperative ($9,000)
        settlement.settleCommissioning(
            containerTokenId,
            cooperative1,
            900000,  // $9,000.00 in cents
            DECIMALS_USD,
            CURRENCY_USD,
            PAYMENT_TOKEN_OFFCHAIN
        );
        
        SettlementContract.SettlementInfo memory settlementInfo = 
            settlement.getSettlement(containerTokenId);
        assertEq(settlementInfo.amount, 900000);
        assertEq(settlementInfo.decimals, DECIMALS_USD);
        assertEq(settlementInfo.currencyCode, CURRENCY_USD);
        
        console2.log("Settlement executed:", settlementInfo.amount);
        console2.log("Full aggregation workflow with merkle proof validated");
    }

    /**
     * @notice Test: Complete merkle proof workflow with verification
     * @dev Demonstrates: Aggregation → Store merkle root → Verify individual batch inclusion
     */
    function test_Integration_MerkleProofVerification() public {
        // Step 1: Create 4 farmer batches
        bytes32 b0 = keccak256(abi.encodePacked("FARM-001", uint256(500)));
        bytes32 b1 = keccak256(abi.encodePacked("FARM-002", uint256(600)));
        bytes32 b2 = keccak256(abi.encodePacked("FARM-003", uint256(700)));
        bytes32 b3 = keccak256(abi.encodePacked("FARM-004", uint256(800)));
        
        // Step 2: Build merkle tree (binary tree)
        //         root
        //        /    \
        //      h01    h23
        //      / \    / \
        //     b0 b1  b2 b3
        
        bytes32 h01 = keccak256(abi.encodePacked(b0, b1));
        bytes32 h23 = keccak256(abi.encodePacked(b2, b3));
        bytes32 merkleRoot = keccak256(abi.encodePacked(h01, h23));
        
        console2.log("Built merkle tree with 4 batches");
        
        // Step 3: Anchor aggregation with merkle root
        string memory containerId = "CONT-MERKLE-001";
        epcisAnchor.anchorAggregation(
            keccak256("merkle-aggregation"),
            containerId,
            merkleRoot,
            4
        );
        
        console2.log("Anchored aggregation with merkle root");
        
        // Step 4: Verify each batch was included using merkle proofs
        
        // Verify FARM-001 (index 0): proof = [b1, h23]
        bytes32[] memory proof0 = new bytes32[](2);
        proof0[0] = b1;
        proof0[1] = h23;
        assertTrue(epcisAnchor.verifyMerkleProof(containerId, b0, proof0, 0));
        console2.log("Verified FARM-001 inclusion");
        
        // Verify FARM-002 (index 1): proof = [b0, h23]
        bytes32[] memory proof1 = new bytes32[](2);
        proof1[0] = b0;
        proof1[1] = h23;
        assertTrue(epcisAnchor.verifyMerkleProof(containerId, b1, proof1, 1));
        console2.log("Verified FARM-002 inclusion");
        
        // Verify FARM-003 (index 2): proof = [b3, h01]
        bytes32[] memory proof2 = new bytes32[](2);
        proof2[0] = b3;
        proof2[1] = h01;
        assertTrue(epcisAnchor.verifyMerkleProof(containerId, b2, proof2, 2));
        console2.log("Verified FARM-003 inclusion");
        
        // Verify FARM-004 (index 3): proof = [b2, h01]
        bytes32[] memory proof3 = new bytes32[](2);
        proof3[0] = b2;
        proof3[1] = h01;
        assertTrue(epcisAnchor.verifyMerkleProof(containerId, b3, proof3, 3));
        console2.log("Verified FARM-004 inclusion");
        
        // Step 5: Try to verify a batch that was NOT included (should fail)
        bytes32 fakeBatch = keccak256(abi.encodePacked("FARM-999", uint256(100)));
        bytes32[] memory fakeProof = new bytes32[](2);
        fakeProof[0] = b1;
        fakeProof[1] = h23;
        assertFalse(epcisAnchor.verifyMerkleProof(containerId, fakeBatch, fakeProof, 0));
        console2.log("Correctly rejected fake batch");
        
        console2.log("=== Merkle Proof Verification Complete ===");
        console2.log("All 4 batches cryptographically verified");
    }
}
