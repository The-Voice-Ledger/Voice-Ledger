// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";
import {SettlementContract} from "../src/SettlementContract.sol";

contract SettlementContractTest is Test {
    SettlementContract public settlement;
    address public cooperative;
    
    // Test data
    uint256 public constant BATCH_ID_1 = 1;
    uint256 public constant BATCH_ID_2 = 2;
    uint256 public constant SETTLEMENT_AMOUNT = 1 ether;
    
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

    function setUp() public {
        cooperative = makeAddr("cooperative");
        settlement = new SettlementContract();
    }

    function test_SettleCommissioning() public {
        vm.expectEmit(true, true, false, true);
        emit SettlementExecuted(BATCH_ID_1, cooperative, SETTLEMENT_AMOUNT, block.timestamp);
        
        settlement.settleCommissioning(BATCH_ID_1, cooperative, SETTLEMENT_AMOUNT);
        
        assertTrue(settlement.isSettled(BATCH_ID_1));
        
        (
            address recipient,
            uint256 amount,
            uint256 settledAt,
            bool settled
        ) = settlement.settlements(BATCH_ID_1);
        
        assertEq(recipient, cooperative);
        assertEq(amount, SETTLEMENT_AMOUNT);
        assertEq(settledAt, block.timestamp);
        assertTrue(settled);
    }

    function test_IsSettled() public {
        assertFalse(settlement.isSettled(BATCH_ID_1));
        
        settlement.settleCommissioning(BATCH_ID_1, cooperative, SETTLEMENT_AMOUNT);
        
        assertTrue(settlement.isSettled(BATCH_ID_1));
    }

    function test_GetSettlement() public {
        settlement.settleCommissioning(BATCH_ID_1, cooperative, SETTLEMENT_AMOUNT);
        
        SettlementContract.SettlementInfo memory info = settlement.getSettlement(BATCH_ID_1);
        
        address recipient = info.recipient;
        uint256 amount = info.amount;
        uint256 settledAt = info.settledAt;
        bool settled = info.settled;
        
        assertEq(recipient, cooperative);
        assertEq(amount, SETTLEMENT_AMOUNT);
        assertGt(settledAt, 0);
        assertTrue(settled);
    }

    function test_RevertWhen_SettlingAlreadySettledBatch() public {
        settlement.settleCommissioning(BATCH_ID_1, cooperative, SETTLEMENT_AMOUNT);
        
        vm.expectRevert(
            abi.encodeWithSelector(
                SettlementContract.AlreadySettled.selector,
                BATCH_ID_1
            )
        );
        settlement.settleCommissioning(BATCH_ID_1, cooperative, SETTLEMENT_AMOUNT);
    }

    function test_RevertWhen_SettlingWithZeroAddress() public {
        vm.expectRevert(SettlementContract.InvalidRecipient.selector);
        settlement.settleCommissioning(BATCH_ID_1, address(0), SETTLEMENT_AMOUNT);
    }

    function test_RevertWhen_SettlingWithZeroAmount() public {
        vm.expectRevert(SettlementContract.InvalidAmount.selector);
        settlement.settleCommissioning(BATCH_ID_1, cooperative, 0);
    }

    function test_RevertWhen_GetInfoForUnsettledBatch() public {
        vm.expectRevert(
            abi.encodeWithSelector(
                SettlementContract.NotSettled.selector,
                BATCH_ID_1
            )
        );
        settlement.getSettlement(BATCH_ID_1);
    }

    function test_SettleMultipleBatches() public {
        address cooperative2 = makeAddr("cooperative2");
        
        settlement.settleCommissioning(BATCH_ID_1, cooperative, SETTLEMENT_AMOUNT);
        settlement.settleCommissioning(BATCH_ID_2, cooperative2, SETTLEMENT_AMOUNT * 2);
        
        assertTrue(settlement.isSettled(BATCH_ID_1));
        assertTrue(settlement.isSettled(BATCH_ID_2));
        
        SettlementContract.SettlementInfo memory info1 = settlement.getSettlement(BATCH_ID_1);
        SettlementContract.SettlementInfo memory info2 = settlement.getSettlement(BATCH_ID_2);
        
        address recipient1 = info1.recipient;
        uint256 amount1 = info1.amount;
        address recipient2 = info2.recipient;
        uint256 amount2 = info2.amount;
        
        assertEq(recipient1, cooperative);
        assertEq(amount1, SETTLEMENT_AMOUNT);
        assertEq(recipient2, cooperative2);
        assertEq(amount2, SETTLEMENT_AMOUNT * 2);
    }

    function test_SettlementTimestamp() public {
        uint256 beforeTimestamp = block.timestamp;
        
        settlement.settleCommissioning(BATCH_ID_1, cooperative, SETTLEMENT_AMOUNT);
        
        (,, uint256 settledAt,) = settlement.settlements(BATCH_ID_1);
        
        assertGe(settledAt, beforeTimestamp);
        assertLe(settledAt, block.timestamp);
    }

    function testFuzz_SettleCommissioning(
        uint256 batchId,
        address recipient,
        uint256 amount
    ) public {
        vm.assume(recipient != address(0));
        vm.assume(amount > 0 && amount < type(uint128).max);
        vm.assume(batchId < type(uint128).max);
        
        settlement.settleCommissioning(batchId, recipient, amount);
        
        assertTrue(settlement.isSettled(batchId));
        
        (
            address storedRecipient,
            uint256 storedAmount,
            ,
            bool settled
        ) = settlement.settlements(batchId);
        
        assertEq(storedRecipient, recipient);
        assertEq(storedAmount, amount);
        assertTrue(settled);
    }
}
