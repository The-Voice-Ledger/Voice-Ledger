// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title EPCISEventAnchor
 * @notice Anchors EPCIS event hashes on-chain for immutable traceability
 * @dev Stores cryptographic hashes of EPCIS events with metadata
 */
contract EPCISEventAnchor {
    
    // Custom errors
    error EventAlreadyAnchored(bytes32 eventHash);
    error EventNotFound(bytes32 eventHash);
    error AggregationAlreadyAnchored(string containerId);
    error InvalidMerkleRoot();
    
    // Event emitted when an EPCIS event is anchored
    event EventAnchored(
        bytes32 indexed eventHash,
        string batchId,
        string eventType,
        uint256 timestamp,
        address indexed submitter
    );
    
    // Event emitted when aggregation with merkle root is anchored
    event AggregationAnchored(
        bytes32 indexed aggregationEventHash,
        string indexed containerId,
        bytes32 merkleRoot,
        uint256 childBatchCount,
        uint256 timestamp,
        address indexed submitter
    );

    // Mapping to track which events have been anchored
    mapping(bytes32 => bool) public anchored;
    
    // Mapping to store event metadata
    mapping(bytes32 => EventMetadata) public eventMetadata;
    
    // Mapping to store merkle roots for aggregated containers
    mapping(string => AggregationMetadata) public aggregations;
    
    struct EventMetadata {
        string batchId;
        string eventType;
        uint256 timestamp;
        address submitter;
        bool exists;
    }
    
    struct AggregationMetadata {
        bytes32 aggregationEventHash;
        bytes32 merkleRoot;
        uint256 childBatchCount;
        uint256 timestamp;
        address submitter;
        bool exists;
    }

    // The DID or role this contract trusts (simplified for prototype)
    string public requiredRole;

    /**
     * @notice Initialize the contract with a required role
     * @param _requiredRole The role required to anchor events (e.g., "Guzo")
     */
    constructor(string memory _requiredRole) {
        requiredRole = _requiredRole;
    }

    /**
     * @notice Anchor an EPCIS event hash on-chain
     * @dev In production, this would verify SSI credentials off-chain first
     * @param eventHash The SHA-256 hash of the canonicalized EPCIS event
     * @param batchId The batch identifier
     * @param eventType The type of EPCIS event (e.g., "commissioning")
     */
    function anchorEvent(
        bytes32 eventHash,
        string calldata batchId,
        string calldata eventType
    ) external {
        if (anchored[eventHash]) revert EventAlreadyAnchored(eventHash);
        
        // Mark as anchored
        anchored[eventHash] = true;
        
        // Store metadata
        eventMetadata[eventHash] = EventMetadata({
            batchId: batchId,
            eventType: eventType,
            timestamp: block.timestamp,
            submitter: msg.sender,
            exists: true
        });

        // Emit event for off-chain indexing
        emit EventAnchored(
            eventHash,
            batchId,
            eventType,
            block.timestamp,
            msg.sender
        );
    }

    /**
     * @notice Anchor an aggregation event with merkle root for cryptographic proof
     * @dev Used when aggregating multiple batches into a container
     * @param aggregationEventHash Hash of the EPCIS AggregationEvent
     * @param containerId The container/parent batch identifier
     * @param merkleRoot Merkle root of all child batch data hashes
     * @param childBatchCount Number of child batches aggregated
     */
    function anchorAggregation(
        bytes32 aggregationEventHash,
        string calldata containerId,
        bytes32 merkleRoot,
        uint256 childBatchCount
    ) external {
        if (aggregations[containerId].exists) {
            revert AggregationAlreadyAnchored(containerId);
        }
        if (merkleRoot == bytes32(0)) revert InvalidMerkleRoot();
        
        // Also anchor the event hash using standard method
        if (!anchored[aggregationEventHash]) {
            anchored[aggregationEventHash] = true;
            eventMetadata[aggregationEventHash] = EventMetadata({
                batchId: containerId,
                eventType: "AggregationEvent",
                timestamp: block.timestamp,
                submitter: msg.sender,
                exists: true
            });
        }
        
        // Store aggregation-specific data
        aggregations[containerId] = AggregationMetadata({
            aggregationEventHash: aggregationEventHash,
            merkleRoot: merkleRoot,
            childBatchCount: childBatchCount,
            timestamp: block.timestamp,
            submitter: msg.sender,
            exists: true
        });
        
        emit AggregationAnchored(
            aggregationEventHash,
            containerId,
            merkleRoot,
            childBatchCount,
            block.timestamp,
            msg.sender
        );
    }

    /**
     * @notice Get aggregation metadata for a container
     * @param containerId The container identifier
     * @return AggregationMetadata struct containing merkle root and details
     */
    function getAggregation(string calldata containerId)
        external
        view
        returns (AggregationMetadata memory)
    {
        if (!aggregations[containerId].exists) {
            revert EventNotFound(keccak256(abi.encodePacked(containerId)));
        }
        return aggregations[containerId];
    }

    /**
     * @notice Check if an event hash has been anchored
     * @param eventHash The event hash to check
     * @return bool True if anchored
     */
    function isAnchored(bytes32 eventHash) external view returns (bool) {
        return anchored[eventHash];
    }

    /**
     * @notice Get metadata for an anchored event
     * @param eventHash The event hash
     * @return Metadata struct
     */
    function getEventMetadata(bytes32 eventHash) 
        external 
        view 
        returns (EventMetadata memory) 
    {
        if (!eventMetadata[eventHash].exists) revert EventNotFound(eventHash);
        return eventMetadata[eventHash];
    }

    /**
     * @notice Verify a merkle proof for a batch included in a container
     * @param containerId The container identifier
     * @param batchDataHash Hash of the batch data
     * @param proof Array of sibling hashes in the merkle tree
     * @param index Position of the batch in the tree (0-based)
     * @return bool True if proof is valid
     */
    function verifyMerkleProof(
        string calldata containerId,
        bytes32 batchDataHash,
        bytes32[] calldata proof,
        uint256 index
    ) external view returns (bool) {
        if (!aggregations[containerId].exists) return false;
        
        bytes32 computedHash = batchDataHash;
        
        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 proofElement = proof[i];
            
            if (index % 2 == 0) {
                // Current node is left child
                computedHash = keccak256(abi.encodePacked(computedHash, proofElement));
            } else {
                // Current node is right child
                computedHash = keccak256(abi.encodePacked(proofElement, computedHash));
            }
            
            index = index / 2;
        }
        
        return computedHash == aggregations[containerId].merkleRoot;
    }
}
