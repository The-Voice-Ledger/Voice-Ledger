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
    
    // Event emitted when an EPCIS event is anchored
    event EventAnchored(
        bytes32 indexed eventHash,
        string batchId,
        string eventType,
        uint256 timestamp,
        address indexed submitter
    );

    // Mapping to track which events have been anchored
    mapping(bytes32 => bool) public anchored;
    
    // Mapping to store event metadata
    mapping(bytes32 => EventMetadata) public eventMetadata;
    
    struct EventMetadata {
        string batchId;
        string eventType;
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
}
