// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SettlementContract
 * @notice Handles automatic settlement/rewards after valid commissioning events
 * @dev Simplified settlement logic for prototype - in production would integrate with payment systems
 */
contract SettlementContract {
    
    // Custom errors
    error AlreadySettled(uint256 batchId);
    error InvalidRecipient();
    error InvalidAmount();
    error NotSettled(uint256 batchId);
    
    // Mapping from batch token ID to settlement status
    mapping(uint256 => SettlementInfo) public settlements;
    
    struct SettlementInfo {
        address recipient;
        uint256 amount;
        uint256 settledAt;
        bool settled;
    }
    
    event SettlementExecuted(
        uint256 indexed batchId,
        address indexed recipient,
        uint256 amount,
        uint256 timestamp
    );
    
    event SettlementPending(
        uint256 indexed batchId,
        address indexed recipient,
        uint256 amount
    );

    /**
     * @notice Execute settlement for a commissioning event
     * @dev In production, this would integrate with payment rails
     * @param batchId The batch token ID
     * @param recipient Address to receive settlement
     * @param amount Settlement amount (in wei for prototype)
     */
    function settleCommissioning(
        uint256 batchId,
        address recipient,
        uint256 amount
    ) external {
        if (settlements[batchId].settled) revert AlreadySettled(batchId);
        if (recipient == address(0)) revert InvalidRecipient();
        if (amount == 0) revert InvalidAmount();
        
        // Record settlement
        settlements[batchId] = SettlementInfo({
            recipient: recipient,
            amount: amount,
            settledAt: block.timestamp,
            settled: true
        });
        
        emit SettlementExecuted(batchId, recipient, amount, block.timestamp);
    }

    /**
     * @notice Check if a batch has been settled
     * @param batchId The batch token ID
     * @return bool True if settled
     */
    function isSettled(uint256 batchId) external view returns (bool) {
        return settlements[batchId].settled;
    }

    /**
     * @notice Get settlement information
     * @param batchId The batch token ID
     * @return SettlementInfo struct
     */
    function getSettlement(uint256 batchId) 
        external 
        view 
        returns (SettlementInfo memory) 
    {
        if (!settlements[batchId].settled) revert NotSettled(batchId);
        return settlements[batchId];
    }
}
