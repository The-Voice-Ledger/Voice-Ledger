// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";
import {CoffeeBatchToken} from "../src/CoffeeBatchToken.sol";

contract CoffeeBatchTokenTest is Test {
    CoffeeBatchToken public token;
    address public owner;
    address public cooperative;
    address public buyer;
    
    // Test data
    string public constant BATCH_ID_1 = "BATCH-001";
    string public constant BATCH_ID_2 = "BATCH-002";
    string public constant METADATA_JSON = '{"origin":"Ethiopia","variety":"Yirgacheffe"}';
    string public constant IPFS_CID = "QmUn4tfmog3BkQgzqx3mzvVNzedSpec4bDXsCx7B1nd93X";
    uint256 public constant QUANTITY = 100;
    
    event BatchMinted(
        uint256 indexed tokenId,
        string batchId,
        address indexed recipient,
        uint256 quantity,
        string metadata
    );
    
    event BatchTransferred(
        uint256 indexed tokenId,
        address indexed from,
        address indexed to,
        uint256 amount
    );

    function setUp() public {
        owner = address(this);
        cooperative = makeAddr("cooperative");
        buyer = makeAddr("buyer");
        token = new CoffeeBatchToken();
    }

    function test_Constructor() public view {
        assertEq(token.owner(), owner);
        // Note: uri() now requires token to exist, tested in test_URI
    }

    function test_MintBatch() public {
        vm.expectEmit(true, true, false, true);
        emit BatchMinted(1, BATCH_ID_1, cooperative, QUANTITY, METADATA_JSON);
        
        uint256 tokenId = token.mintBatch(cooperative, QUANTITY, BATCH_ID_1, METADATA_JSON, IPFS_CID);
        
        assertEq(tokenId, 1);
        assertEq(token.balanceOf(cooperative, tokenId), QUANTITY);
        assertEq(token.batchIdToTokenId(BATCH_ID_1), tokenId);
        
        // Check batch metadata
        (
            string memory batchId,
            uint256 quantity,
            string memory metadata,
            string memory ipfsCid,
            uint256 createdAt,
            bool exists
        ) = token.batches(tokenId);
        
        assertEq(batchId, BATCH_ID_1);
        assertEq(quantity, QUANTITY);
        assertEq(metadata, METADATA_JSON);
        assertGt(createdAt, 0);
        assertTrue(exists);
    }

    function test_MintMultipleBatches() public {
        uint256 tokenId1 = token.mintBatch(cooperative, QUANTITY, BATCH_ID_1, METADATA_JSON, IPFS_CID);
        uint256 tokenId2 = token.mintBatch(cooperative, QUANTITY * 2, BATCH_ID_2, METADATA_JSON, IPFS_CID);
        
        assertEq(tokenId1, 1);
        assertEq(tokenId2, 2);
        assertEq(token.balanceOf(cooperative, tokenId1), QUANTITY);
        assertEq(token.balanceOf(cooperative, tokenId2), QUANTITY * 2);
    }

    function test_RevertWhen_MintingWithEmptyBatchId() public {
        vm.expectRevert(CoffeeBatchToken.BatchIdRequired.selector);
        token.mintBatch(cooperative, QUANTITY, "", METADATA_JSON, IPFS_CID);
    }

    function test_RevertWhen_MintingDuplicateBatchId() public {
        token.mintBatch(cooperative, QUANTITY, BATCH_ID_1, METADATA_JSON, IPFS_CID);
        
        vm.expectRevert(
            abi.encodeWithSelector(
                CoffeeBatchToken.BatchIdAlreadyExists.selector,
                BATCH_ID_1
            )
        );
        token.mintBatch(cooperative, QUANTITY, BATCH_ID_1, METADATA_JSON, IPFS_CID);
    }

    function test_RevertWhen_NonOwnerMints() public {
        vm.prank(cooperative);
        vm.expectRevert();
        token.mintBatch(cooperative, QUANTITY, BATCH_ID_1, METADATA_JSON, IPFS_CID);
    }

    function test_TransferBatch() public {
        uint256 tokenId = token.mintBatch(cooperative, QUANTITY, BATCH_ID_1, METADATA_JSON, IPFS_CID);
        
        vm.prank(cooperative);
        vm.expectEmit(true, true, true, true);
        emit BatchTransferred(tokenId, cooperative, buyer, 50);
        
        token.transferBatch(cooperative, buyer, tokenId, 50);
        
        assertEq(token.balanceOf(cooperative, tokenId), 50);
        assertEq(token.balanceOf(buyer, tokenId), 50);
    }

    function test_RevertWhen_TransferringNonExistentBatch() public {
        vm.prank(cooperative);
        vm.expectRevert();
        token.transferBatch(cooperative, buyer, 999, 50);
    }

    function test_RevertWhen_TransferringMoreThanBalance() public {
        uint256 tokenId = token.mintBatch(cooperative, QUANTITY, BATCH_ID_1, METADATA_JSON, IPFS_CID);
        
        vm.prank(cooperative);
        vm.expectRevert();
        token.transferBatch(cooperative, buyer, tokenId, QUANTITY + 1);
    }

    function test_GetBatchMetadata() public {
        uint256 tokenId = token.mintBatch(cooperative, QUANTITY, BATCH_ID_1, METADATA_JSON, IPFS_CID);
        
        CoffeeBatchToken.BatchMetadata memory batchMetadata = token.getBatchMetadata(tokenId);
        
        string memory batchId = batchMetadata.batchId;
        uint256 quantity = batchMetadata.quantity;
        string memory metadata = batchMetadata.metadata;
        bool exists = batchMetadata.exists;
        
        assertEq(batchId, BATCH_ID_1);
        assertEq(quantity, QUANTITY);
        assertEq(metadata, METADATA_JSON);
        assertTrue(exists);
    }

    function test_GetTokenIdByBatchId() public {
        uint256 tokenId = token.mintBatch(cooperative, QUANTITY, BATCH_ID_1, METADATA_JSON, IPFS_CID);
        
        uint256 retrievedTokenId = token.getTokenIdByBatchId(BATCH_ID_1);
        assertEq(retrievedTokenId, tokenId);
    }

    function test_RevertWhen_GetTokenIdForNonExistentBatchId() public {
        vm.expectRevert(
            abi.encodeWithSelector(
                CoffeeBatchToken.BatchIdNotFound.selector,
                "NON-EXISTENT"
            )
        );
        token.getTokenIdByBatchId("NON-EXISTENT");
    }

    function test_SupportsInterface() public view {
        // ERC1155 interface
        assertTrue(token.supportsInterface(0xd9b67a26));
        // ERC165 interface
        assertTrue(token.supportsInterface(0x01ffc9a7));
    }

    function test_URI() public {
        uint256 tokenId = token.mintBatch(cooperative, QUANTITY, BATCH_ID_1, METADATA_JSON, IPFS_CID);
        
        string memory expectedUri = string(abi.encodePacked(
            "https://violet-rainy-toad-577.mypinata.cloud/ipfs/",
            IPFS_CID
        ));
        
        assertEq(token.uri(tokenId), expectedUri);
    }

    function test_RevertWhen_GetURIForNonExistentToken() public {
        vm.expectRevert(
            abi.encodeWithSelector(
                CoffeeBatchToken.BatchDoesNotExist.selector,
                999
            )
        );
        token.uri(999);
    }

    function testFuzz_MintBatch(
        address recipient,
        uint256 quantity,
        uint8 batchNumber
    ) public {
        vm.assume(recipient != address(0));
        vm.assume(quantity > 0 && quantity < 1000000);
        // Assume recipient is an EOA (has no code) to avoid ERC1155 receiver issues
        vm.assume(recipient.code.length == 0);
        
        string memory batchId = string.concat("BATCH-", vm.toString(batchNumber));
        
        // Skip if batch ID already exists
        if (token.batchIdToTokenId(batchId) != 0) return;
        
        uint256 tokenId = token.mintBatch(recipient, quantity, batchId, METADATA_JSON, IPFS_CID);
        
        assertEq(token.balanceOf(recipient, tokenId), quantity);
        assertEq(token.batchIdToTokenId(batchId), tokenId);
    }
}
