// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";
import {CoffeeBatchToken} from "../src/CoffeeBatchToken.sol";

/**
 * @title CoffeeBatchAggregationTest
 * @notice Tests for container minting and token burning during aggregation
 */
contract CoffeeBatchAggregationTest is Test {
    CoffeeBatchToken public token;
    address public owner;
    address public farmer1;
    address public farmer2;
    address public farmer3;
    address public cooperative;
    
    string constant IPFS_CID = "QmUn4tfmog3BkQgzqx3mzvVNzedSpec4bDXsCx7B1nd93X";
    
    event ContainerMinted(
        uint256 indexed tokenId,
        string batchId,
        address indexed recipient,
        uint256 quantity,
        uint256[] childTokenIds
    );
    
    event BatchBurned(
        uint256 indexed tokenId,
        address indexed from,
        uint256 amount
    );

    function setUp() public {
        owner = address(this);
        farmer1 = makeAddr("farmer1");
        farmer2 = makeAddr("farmer2");
        farmer3 = makeAddr("farmer3");
        cooperative = makeAddr("cooperative");
        
        token = new CoffeeBatchToken();
    }

    /**
     * @notice Test: Aggregate 3 farmer batches into container
     * @dev Verifies burning, mass balance, and lineage tracking
     */
    function test_AggregateThreeFarmerBatches() public {
        // Step 1: Create 3 farmer batches
        uint256 batch1 = token.mintBatch(
            farmer1,
            3000,
            "ETH-YRG-F1-001",
            '{"farmer":"Abebe","origin":"Yirgacheffe"}',
            IPFS_CID
        );
        
        uint256 batch2 = token.mintBatch(
            farmer2,
            2500,
            "ETH-YRG-F2-002",
            '{"farmer":"Kebede","origin":"Yirgacheffe"}',
            IPFS_CID
        );
        
        uint256 batch3 = token.mintBatch(
            farmer3,
            4500,
            "ETH-YRG-F3-003",
            '{"farmer":"Chaltu","origin":"Yirgacheffe"}',
            IPFS_CID
        );
        
        // Verify farmer balances
        assertEq(token.balanceOf(farmer1, batch1), 3000);
        assertEq(token.balanceOf(farmer2, batch2), 2500);
        assertEq(token.balanceOf(farmer3, batch3), 4500);
        
        console2.log("Step 1: Created 3 farmer batches");
        console2.log("  Farmer 1:", token.balanceOf(farmer1, batch1), "kg");
        console2.log("  Farmer 2:", token.balanceOf(farmer2, batch2), "kg");
        console2.log("  Farmer 3:", token.balanceOf(farmer3, batch3), "kg");
        
        // Step 2: Aggregate into container (burns child tokens)
        uint256[] memory childTokenIds = new uint256[](3);
        childTokenIds[0] = batch1;
        childTokenIds[1] = batch2;
        childTokenIds[2] = batch3;
        
        address[] memory childHolders = new address[](3);
        childHolders[0] = farmer1;
        childHolders[1] = farmer2;
        childHolders[2] = farmer3;
        
        vm.expectEmit(true, false, false, false);
        emit BatchBurned(batch1, farmer1, 3000);
        
        vm.expectEmit(true, false, false, false);
        emit BatchBurned(batch2, farmer2, 2500);
        
        vm.expectEmit(true, false, false, false);
        emit BatchBurned(batch3, farmer3, 4500);
        
        uint256 containerId = token.mintContainer(
            cooperative,
            10000, // 3000 + 2500 + 4500
            "CONTAINER-YRG-2025-001",
            '{"type":"container","batches":3,"location":"Guzo Cooperative"}',
            IPFS_CID,
            childTokenIds,
            childHolders
        );
        
        console2.log("\nStep 2: Aggregated into container");
        console2.log("  Container ID:", containerId);
        console2.log("  Container quantity:", token.balanceOf(cooperative, containerId), "kg");
        
        // Step 3: Verify burns (farmer balances should be 0)
        assertEq(token.balanceOf(farmer1, batch1), 0, "Farmer 1 tokens not burned");
        assertEq(token.balanceOf(farmer2, batch2), 0, "Farmer 2 tokens not burned");
        assertEq(token.balanceOf(farmer3, batch3), 0, "Farmer 3 tokens not burned");
        
        console2.log("\nStep 3: Verified child tokens burned");
        console2.log("  Farmer 1 balance:", token.balanceOf(farmer1, batch1), "kg");
        console2.log("  Farmer 2 balance:", token.balanceOf(farmer2, batch2), "kg");
        console2.log("  Farmer 3 balance:", token.balanceOf(farmer3, batch3), "kg");
        
        // Step 4: Verify container
        assertEq(token.balanceOf(cooperative, containerId), 10000);
        assertTrue(token.isContainer(containerId));
        
        // Step 5: Verify lineage tracking
        uint256[] memory children = token.getChildTokenIds(containerId);
        assertEq(children.length, 3);
        assertEq(children[0], batch1);
        assertEq(children[1], batch2);
        assertEq(children[2], batch3);
        
        console2.log("\nStep 4: Verified container and lineage");
        console2.log("  Container is aggregated:", token.isContainer(containerId));
        console2.log("  Child batches tracked:", children.length);
        
        // Step 6: Verify total supply (only container exists)
        uint256 totalSupply = token.balanceOf(cooperative, containerId);
        assertEq(totalSupply, 10000, "Total supply should match container only");
        
        console2.log("\nStep 5: Mass balance verified");
        console2.log("  Total tokens in circulation:", totalSupply, "kg");
        console2.log("  [OK] No double counting!");
    }

    /**
     * @notice Test: Reject aggregation if mass balance doesn't match
     */
    function test_RevertWhen_MassBalanceViolation() public {
        // Create 2 batches
        uint256 batch1 = token.mintBatch(farmer1, 3000, "BATCH-001", '{}', IPFS_CID);
        uint256 batch2 = token.mintBatch(farmer2, 2000, "BATCH-002", '{}', IPFS_CID);
        
        uint256[] memory childTokenIds = new uint256[](2);
        childTokenIds[0] = batch1;
        childTokenIds[1] = batch2;
        
        address[] memory childHolders = new address[](2);
        childHolders[0] = farmer1;
        childHolders[1] = farmer2;
        
        // Try to create container with wrong quantity (5500 instead of 5000)
        vm.expectRevert(CoffeeBatchToken.InvalidQuantity.selector);
        token.mintContainer(
            cooperative,
            5500, // Wrong! Should be 5000
            "CONTAINER-WRONG",
            '{}',
            IPFS_CID,
            childTokenIds,
            childHolders
        );
    }

    /**
     * @notice Test: Reject aggregation if child token doesn't exist
     */
    function test_RevertWhen_ChildTokenDoesNotExist() public {
        uint256[] memory childTokenIds = new uint256[](1);
        childTokenIds[0] = 999; // Non-existent token
        
        address[] memory childHolders = new address[](1);
        childHolders[0] = farmer1;
        
        vm.expectRevert(abi.encodeWithSelector(CoffeeBatchToken.BatchDoesNotExist.selector, 999));
        token.mintContainer(
            cooperative,
            3000,
            "CONTAINER-BAD",
            '{}',
            IPFS_CID,
            childTokenIds,
            childHolders
        );
    }

    /**
     * @notice Test: Burn tokens at final sale/consumption
     */
    function test_BurnTokensAtConsumption() public {
        // Create batch
        uint256 tokenId = token.mintBatch(
            cooperative,
            5000,
            "BATCH-FINAL",
            '{}',
            IPFS_CID
        );
        
        assertEq(token.balanceOf(cooperative, tokenId), 5000);
        
        // Cooperative burns tokens (e.g., sold to final consumer)
        vm.prank(cooperative);
        vm.expectEmit(true, true, false, true);
        emit BatchBurned(tokenId, cooperative, 5000);
        
        token.burnBatch(tokenId, 5000);
        
        assertEq(token.balanceOf(cooperative, tokenId), 0);
        console2.log("[OK] Tokens burned at final consumption");
    }

    /**
     * @notice Test: Regular batch is not marked as container
     */
    function test_RegularBatchNotContainer() public {
        uint256 tokenId = token.mintBatch(
            farmer1,
            3000,
            "REGULAR-BATCH",
            '{}',
            IPFS_CID
        );
        
        assertFalse(token.isContainer(tokenId));
        
        uint256[] memory children = token.getChildTokenIds(tokenId);
        assertEq(children.length, 0);
    }

    /**
     * @notice Test: Multi-level aggregation (farmers → coop → exporter)
     */
    function test_MultiLevelAggregation() public {
        // Level 1: Farmers create batches
        uint256 f1 = token.mintBatch(farmer1, 2000, "F1-BATCH", '{}', IPFS_CID);
        uint256 f2 = token.mintBatch(farmer2, 2000, "F2-BATCH", '{}', IPFS_CID);
        
        // Level 2: Cooperative aggregates farmer batches
        uint256[] memory farmerBatches = new uint256[](2);
        farmerBatches[0] = f1;
        farmerBatches[1] = f2;
        
        address[] memory farmerHolders = new address[](2);
        farmerHolders[0] = farmer1;
        farmerHolders[1] = farmer2;
        
        uint256 coopContainer = token.mintContainer(
            cooperative,
            4000,
            "COOP-CONTAINER-001",
            '{}',
            IPFS_CID,
            farmerBatches,
            farmerHolders
        );
        
        // Verify Level 2
        assertEq(token.balanceOf(cooperative, coopContainer), 4000);
        assertEq(token.balanceOf(farmer1, f1), 0);
        assertEq(token.balanceOf(farmer2, f2), 0);
        assertTrue(token.isContainer(coopContainer));
        
        // Level 3: Exporter could aggregate multiple coop containers
        // (Not shown here, but same pattern applies)
        
        console2.log("[OK] Multi-level aggregation successful");
        console2.log("  Coop container:", token.balanceOf(cooperative, coopContainer), "kg");
        console2.log("  Child batches tracked:", token.getChildTokenIds(coopContainer).length);
    }

    /**
     * @notice Test: Partial burns are possible (fractional consumption)
     */
    function test_PartialBurn() public {
        uint256 tokenId = token.mintBatch(
            cooperative,
            10000,
            "PARTIAL-BATCH",
            '{}',
            IPFS_CID
        );
        
        // Burn 3000 kg (sold to buyer 1)
        vm.prank(cooperative);
        token.burnBatch(tokenId, 3000);
        
        assertEq(token.balanceOf(cooperative, tokenId), 7000);
        
        // Burn 2000 kg more (sold to buyer 2)
        vm.prank(cooperative);
        token.burnBatch(tokenId, 2000);
        
        assertEq(token.balanceOf(cooperative, tokenId), 5000);
        
        console2.log("[OK] Partial burns work (fractional sales)");
        console2.log("  Remaining balance:", token.balanceOf(cooperative, tokenId), "kg");
    }
}
