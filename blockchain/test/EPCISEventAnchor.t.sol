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
}
