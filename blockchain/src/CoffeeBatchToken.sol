// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ERC1155} from "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title CoffeeBatchToken
 * @notice ERC-1155 token representing coffee batches
 * @dev Each token ID represents a unique batch with associated metadata
 */
contract CoffeeBatchToken is ERC1155, Ownable {
    
    // Custom errors
    error BatchIdRequired();
    error BatchIdAlreadyExists(string batchId);
    error BatchDoesNotExist(uint256 tokenId);
    error BatchIdNotFound(string batchId);
    error NotAuthorized();
    
    // Counter for generating unique batch token IDs
    uint256 private _nextTokenId;
    
    // Mapping from token ID to batch metadata
    mapping(uint256 => BatchMetadata) public batches;
    
    // Mapping from batch ID string to token ID
    mapping(string => uint256) public batchIdToTokenId;
    
    struct BatchMetadata {
        string batchId;
        uint256 quantity;
        string metadata; // JSON string with origin, cooperative, process type, etc.
        uint256 createdAt;
        bool exists;
    }
    
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

    /**
     * @notice Initialize the contract
     * @dev URI can be updated per token
     */
    constructor() ERC1155("https://voiceledger.org/api/batch/{id}") Ownable(msg.sender) {
        _nextTokenId = 1;
    }

    /**
     * @notice Mint a new coffee batch token
     * @param recipient Address to receive the tokens
     * @param quantity Number of units (e.g., bags of coffee)
     * @param metadata JSON string with batch details
     * @return tokenId The newly created token ID
     */
    function mintBatch(
        address recipient,
        uint256 quantity,
        string calldata batchIdStr,
        string calldata metadata
    ) external onlyOwner returns (uint256) {
        if (bytes(batchIdStr).length == 0) revert BatchIdRequired();
        if (batchIdToTokenId[batchIdStr] != 0) revert BatchIdAlreadyExists(batchIdStr);
        
        uint256 tokenId = _nextTokenId++;
        
        // Store metadata
        batches[tokenId] = BatchMetadata({
            batchId: batchIdStr,
            quantity: quantity,
            metadata: metadata,
            createdAt: block.timestamp,
            exists: true
        });
        
        // Map batch ID to token ID
        batchIdToTokenId[batchIdStr] = tokenId;
        
        // Mint the tokens
        _mint(recipient, tokenId, quantity, "");
        
        emit BatchMinted(tokenId, batchIdStr, recipient, quantity, metadata);
        
        return tokenId;
    }

    /**
     * @notice Transfer batch tokens between addresses
     * @param from Sender address
     * @param to Recipient address
     * @param tokenId The batch token ID
     * @param amount Number of units to transfer
     */
    function transferBatch(
        address from,
        address to,
        uint256 tokenId,
        uint256 amount
    ) external {
        if (from != msg.sender && !isApprovedForAll(from, msg.sender)) {
            revert NotAuthorized();
        }
        
        safeTransferFrom(from, to, tokenId, amount, "");
        
        emit BatchTransferred(tokenId, from, to, amount);
    }

    /**
     * @notice Get batch metadata by token ID
     * @param tokenId The token ID
     * @return Batch metadata struct
     */
    function getBatchMetadata(uint256 tokenId) 
        external 
        view 
        returns (BatchMetadata memory) 
    {
        if (!batches[tokenId].exists) revert BatchDoesNotExist(tokenId);
        return batches[tokenId];
    }

    /**
     * @notice Get token ID by batch ID string
     * @param batchIdStr The batch identifier string
     * @return tokenId The corresponding token ID
     */
    function getTokenIdByBatchId(string calldata batchIdStr) 
        external 
        view 
        returns (uint256) 
    {
        uint256 tokenId = batchIdToTokenId[batchIdStr];
        if (tokenId == 0) revert BatchIdNotFound(batchIdStr);
        return tokenId;
    }

    /**
     * @notice Check batch balance for an address
     * @param account Address to check
     * @param tokenId Token ID to check
     * @return balance Number of units held
     */
    function batchBalance(address account, uint256 tokenId) 
        external 
        view 
        returns (uint256) 
    {
        return balanceOf(account, tokenId);
    }
}
