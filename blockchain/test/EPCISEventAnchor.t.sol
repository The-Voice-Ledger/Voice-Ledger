// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";
import {EPCISEventAnchor} from "../src/EPCISEventAnchor.sol";

contract EPCISEventAnchorTest is Test {
    EPCISEventAnchor public anchor;
    address public cooperativeManager;
    
    // Test data
    bytes32 public constant TEST_EVENT_HASH = keccak256("test-event-1");
    string public constant TEST_BATCH_ID = "BATCH-001";
    string public constant TEST_EVENT_TYPE = "commissioning";
    
    event EventAnchored(
        bytes32 indexed eventHash,
        string batchId,
        string eventType,
        uint256 timestamp,
        address indexed submitter
    );

    function setUp() public {
        cooperativeManager = makeAddr("cooperativeManager");
        anchor = new EPCISEventAnchor("COOPERATIVE_MANAGER");
    }

    function test_Constructor() public view {
        assertEq(anchor.requiredRole(), "COOPERATIVE_MANAGER");
    }

    function test_AnchorEvent() public {
        vm.prank(cooperativeManager);
        
        vm.expectEmit(true, false, false, true);
        emit EventAnchored(
            TEST_EVENT_HASH,
            TEST_BATCH_ID,
            TEST_EVENT_TYPE,
            block.timestamp,
            cooperativeManager
        );
        
        anchor.anchorEvent(TEST_EVENT_HASH, TEST_BATCH_ID, TEST_EVENT_TYPE);
        
        // Verify event is anchored
        assertTrue(anchor.anchored(TEST_EVENT_HASH));
        
        // Verify metadata
        EPCISEventAnchor.EventMetadata memory metadata = anchor.getEventMetadata(TEST_EVENT_HASH);
        
        string memory batchId = metadata.batchId;
        string memory eventType = metadata.eventType;
        uint256 timestamp = metadata.timestamp;
        address submitter = metadata.submitter;
        bool exists = metadata.exists;
        
        assertEq(batchId, TEST_BATCH_ID);
        assertEq(eventType, TEST_EVENT_TYPE);
        assertEq(timestamp, block.timestamp);
        assertEq(submitter, cooperativeManager);
        assertTrue(exists);
    }

    function test_RevertWhen_AnchoringDuplicateEvent() public {
        // Anchor first time
        vm.prank(cooperativeManager);
        anchor.anchorEvent(TEST_EVENT_HASH, TEST_BATCH_ID, TEST_EVENT_TYPE);
        
        // Try to anchor again - should revert
        vm.prank(cooperativeManager);
        vm.expectRevert(
            abi.encodeWithSelector(
                EPCISEventAnchor.EventAlreadyAnchored.selector,
                TEST_EVENT_HASH
            )
        );
        anchor.anchorEvent(TEST_EVENT_HASH, TEST_BATCH_ID, TEST_EVENT_TYPE);
    }

    function test_IsAnchored() public {
        assertFalse(anchor.isAnchored(TEST_EVENT_HASH));
        
        vm.prank(cooperativeManager);
        anchor.anchorEvent(TEST_EVENT_HASH, TEST_BATCH_ID, TEST_EVENT_TYPE);
        
        assertTrue(anchor.isAnchored(TEST_EVENT_HASH));
    }

    function test_GetEventMetadata() public {
        vm.prank(cooperativeManager);
        anchor.anchorEvent(TEST_EVENT_HASH, TEST_BATCH_ID, TEST_EVENT_TYPE);
        
        EPCISEventAnchor.EventMetadata memory metadata = anchor.getEventMetadata(TEST_EVENT_HASH);
        
        string memory batchId = metadata.batchId;
        string memory eventType = metadata.eventType;
        address submitter = metadata.submitter;
        bool exists = metadata.exists;
        
        assertEq(batchId, TEST_BATCH_ID);
        assertEq(eventType, TEST_EVENT_TYPE);
        assertEq(submitter, cooperativeManager);
        assertTrue(exists);
    }

    function test_RevertWhen_GetMetadataForNonExistentEvent() public {
        bytes32 nonExistentHash = keccak256("non-existent");
        
        vm.expectRevert(
            abi.encodeWithSelector(
                EPCISEventAnchor.EventNotFound.selector,
                nonExistentHash
            )
        );
        anchor.getEventMetadata(nonExistentHash);
    }

    function testFuzz_AnchorMultipleEvents(
        bytes32[] memory eventHashes,
        string memory batchIdBase
    ) public {
        vm.assume(eventHashes.length > 0 && eventHashes.length < 100);
        vm.assume(bytes(batchIdBase).length > 0);
        
        for (uint256 i = 0; i < eventHashes.length; i++) {
            // Skip if already anchored (fuzz might generate duplicates)
            if (anchor.anchored(eventHashes[i])) continue;
            
            string memory batchId = string.concat(batchIdBase, vm.toString(i));
            
            vm.prank(cooperativeManager);
            anchor.anchorEvent(eventHashes[i], batchId, TEST_EVENT_TYPE);
            
            assertTrue(anchor.isAnchored(eventHashes[i]));
        }
    }

    // ============================================
    // Aggregation Tests
    // ============================================

    function test_AnchorAggregation() public {
        bytes32 aggregationHash = keccak256("aggregation-event-1");
        string memory containerId = "CONT-2025-001";
        bytes32 merkleRoot = keccak256(abi.encodePacked("batch1", "batch2", "batch3"));
        uint256 childCount = 3;
        
        vm.prank(cooperativeManager);
        anchor.anchorAggregation(aggregationHash, containerId, merkleRoot, childCount);
        
        // Verify event is anchored
        assertTrue(anchor.isAnchored(aggregationHash));
        
        // Verify aggregation metadata
        EPCISEventAnchor.AggregationMetadata memory agg = anchor.getAggregation(containerId);
        assertEq(agg.aggregationEventHash, aggregationHash);
        assertEq(agg.merkleRoot, merkleRoot);
        assertEq(agg.childBatchCount, childCount);
        assertEq(agg.submitter, cooperativeManager);
        assertTrue(agg.exists);
    }

    function test_RevertWhen_AnchoringDuplicateAggregation() public {
        bytes32 aggregationHash = keccak256("aggregation-event-1");
        string memory containerId = "CONT-2025-001";
        bytes32 merkleRoot = keccak256("merkle-root");
        
        vm.prank(cooperativeManager);
        anchor.anchorAggregation(aggregationHash, containerId, merkleRoot, 5);
        
        // Try to anchor same container again
        vm.prank(cooperativeManager);
        vm.expectRevert(
            abi.encodeWithSelector(
                EPCISEventAnchor.AggregationAlreadyAnchored.selector,
                containerId
            )
        );
        anchor.anchorAggregation(aggregationHash, containerId, merkleRoot, 5);
    }

    function test_RevertWhen_AnchoringWithZeroMerkleRoot() public {
        bytes32 aggregationHash = keccak256("aggregation-event-1");
        string memory containerId = "CONT-2025-001";
        bytes32 zeroMerkleRoot = bytes32(0);
        
        vm.prank(cooperativeManager);
        vm.expectRevert(EPCISEventAnchor.InvalidMerkleRoot.selector);
        anchor.anchorAggregation(aggregationHash, containerId, zeroMerkleRoot, 5);
    }

    function test_RevertWhen_GetNonExistentAggregation() public {
        string memory nonExistentId = "CONT-DOES-NOT-EXIST";
        
        vm.expectRevert();
        anchor.getAggregation(nonExistentId);
    }

    function test_AnchorMultipleAggregations() public {
        for (uint256 i = 1; i <= 5; i++) {
            bytes32 aggHash = keccak256(abi.encodePacked("agg", i));
            string memory containerId = string.concat("CONT-", vm.toString(i));
            bytes32 merkleRoot = keccak256(abi.encodePacked("merkle", i));
            
            vm.prank(cooperativeManager);
            anchor.anchorAggregation(aggHash, containerId, merkleRoot, i * 10);
            
            // Verify each aggregation
            EPCISEventAnchor.AggregationMetadata memory agg = anchor.getAggregation(containerId);
            assertEq(agg.merkleRoot, merkleRoot);
            assertEq(agg.childBatchCount, i * 10);
        }
    }

    function testFuzz_AnchorAggregation(
        bytes32 aggregationHash,
        string memory containerId,
        bytes32 merkleRoot,
        uint256 childCount
    ) public {
        vm.assume(bytes(containerId).length > 0 && bytes(containerId).length < 100);
        vm.assume(merkleRoot != bytes32(0));
        vm.assume(childCount > 0 && childCount < 1000);
        
        vm.prank(cooperativeManager);
        anchor.anchorAggregation(aggregationHash, containerId, merkleRoot, childCount);
        
        assertTrue(anchor.isAnchored(aggregationHash));
        
        EPCISEventAnchor.AggregationMetadata memory agg = anchor.getAggregation(containerId);
        assertEq(agg.aggregationEventHash, aggregationHash);
        assertEq(agg.merkleRoot, merkleRoot);
        assertEq(agg.childBatchCount, childCount);
        assertTrue(agg.exists);
    }

    // ============================================
    // Merkle Proof Verification Tests
    // ============================================

    function test_VerifyMerkleProof_TwoBatches() public {
        // Setup: 2 batches
        bytes32 batch1Hash = keccak256("batch-1-data");
        bytes32 batch2Hash = keccak256("batch-2-data");
        
        // Compute merkle root: hash(batch1 + batch2)
        bytes32 merkleRoot = keccak256(abi.encodePacked(batch1Hash, batch2Hash));
        
        // Anchor aggregation
        vm.prank(cooperativeManager);
        anchor.anchorAggregation(
            keccak256("aggregation-event"),
            "CONT-001",
            merkleRoot,
            2
        );
        
        // Verify batch1 (left child, index 0)
        bytes32[] memory proof1 = new bytes32[](1);
        proof1[0] = batch2Hash;
        assertTrue(anchor.verifyMerkleProof("CONT-001", batch1Hash, proof1, 0));
        
        // Verify batch2 (right child, index 1)
        bytes32[] memory proof2 = new bytes32[](1);
        proof2[0] = batch1Hash;
        assertTrue(anchor.verifyMerkleProof("CONT-001", batch2Hash, proof2, 1));
    }

    function test_VerifyMerkleProof_FourBatches() public {
        // Setup: 4 batches forming a tree:
        //         root
        //        /    \
        //      h01    h23
        //      / \    / \
        //     b0 b1  b2 b3
        
        bytes32 b0 = keccak256("batch-0");
        bytes32 b1 = keccak256("batch-1");
        bytes32 b2 = keccak256("batch-2");
        bytes32 b3 = keccak256("batch-3");
        
        bytes32 h01 = keccak256(abi.encodePacked(b0, b1));
        bytes32 h23 = keccak256(abi.encodePacked(b2, b3));
        bytes32 root = keccak256(abi.encodePacked(h01, h23));
        
        // Anchor aggregation
        vm.prank(cooperativeManager);
        anchor.anchorAggregation(
            keccak256("agg-4-batches"),
            "CONT-002",
            root,
            4
        );
        
        // Verify batch 0 (index 0): proof = [b1, h23]
        bytes32[] memory proof0 = new bytes32[](2);
        proof0[0] = b1;   // sibling at level 0
        proof0[1] = h23;  // sibling at level 1
        assertTrue(anchor.verifyMerkleProof("CONT-002", b0, proof0, 0));
        
        // Verify batch 2 (index 2): proof = [b3, h01]
        bytes32[] memory proof2 = new bytes32[](2);
        proof2[0] = b3;   // sibling at level 0
        proof2[1] = h01;  // sibling at level 1
        assertTrue(anchor.verifyMerkleProof("CONT-002", b2, proof2, 2));
    }

    function test_VerifyMerkleProof_InvalidProof() public {
        // Setup
        bytes32 batch1Hash = keccak256("batch-1");
        bytes32 batch2Hash = keccak256("batch-2");
        bytes32 merkleRoot = keccak256(abi.encodePacked(batch1Hash, batch2Hash));
        
        vm.prank(cooperativeManager);
        anchor.anchorAggregation(
            keccak256("agg"),
            "CONT-003",
            merkleRoot,
            2
        );
        
        // Try to verify with wrong proof
        bytes32[] memory wrongProof = new bytes32[](1);
        wrongProof[0] = keccak256("wrong-hash");
        assertFalse(anchor.verifyMerkleProof("CONT-003", batch1Hash, wrongProof, 0));
    }

    function test_VerifyMerkleProof_NonExistentContainer() public {
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = keccak256("some-hash");
        
        // Should return false for non-existent container
        assertFalse(anchor.verifyMerkleProof("CONT-DOES-NOT-EXIST", keccak256("batch"), proof, 0));
    }
}
