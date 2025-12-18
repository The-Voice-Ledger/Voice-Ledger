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
    uint256 public constant SETTLEMENT_AMOUNT = 900000; // $9,000.00 USD in cents
    uint8 public constant DECIMALS_USD = 2;
    string public constant CURRENCY_USD = "USD";
    address public constant PAYMENT_TOKEN_OFFCHAIN = address(0);
    
    event SettlementExecuted(
        uint256 indexed batchId,
        address indexed recipient,
        uint256 amount,
        uint8 decimals,
        string currencyCode,
        address paymentToken,
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
        emit SettlementExecuted(
            BATCH_ID_1,
            cooperative,
            SETTLEMENT_AMOUNT,
            DECIMALS_USD,
            CURRENCY_USD,
            PAYMENT_TOKEN_OFFCHAIN,
            block.timestamp
        );
        
        settlement.settleCommissioning(
            BATCH_ID_1,
            cooperative,
            SETTLEMENT_AMOUNT,
            DECIMALS_USD,
            CURRENCY_USD,
            PAYMENT_TOKEN_OFFCHAIN
        );
        
        assertTrue(settlement.isSettled(BATCH_ID_1));
        
        (
            address recipient,
            uint256 amount,
            uint8 decimals,
            string memory currencyCode,
            address paymentToken,
            uint256 settledAt,
            bool settled
        ) = settlement.settlements(BATCH_ID_1);
        
        assertEq(recipient, cooperative);
        assertEq(amount, SETTLEMENT_AMOUNT);
        assertEq(decimals, DECIMALS_USD);
        assertEq(currencyCode, CURRENCY_USD);
        assertEq(paymentToken, PAYMENT_TOKEN_OFFCHAIN);
        assertEq(settledAt, block.timestamp);
        assertTrue(settled);
    }

    function test_IsSettled() public {
        assertFalse(settlement.isSettled(BATCH_ID_1));
        
        settlement.settleCommissioning(
            BATCH_ID_1,
            cooperative,
            SETTLEMENT_AMOUNT,
            DECIMALS_USD,
            CURRENCY_USD,
            PAYMENT_TOKEN_OFFCHAIN
        );
        
        assertTrue(settlement.isSettled(BATCH_ID_1));
    }

    function test_GetSettlement() public {
        settlement.settleCommissioning(
            BATCH_ID_1,
            cooperative,
            SETTLEMENT_AMOUNT,
            DECIMALS_USD,
            CURRENCY_USD,
            PAYMENT_TOKEN_OFFCHAIN
        );
        
        SettlementContract.SettlementInfo memory info = settlement.getSettlement(BATCH_ID_1);
        
        assertEq(info.recipient, cooperative);
        assertEq(info.amount, SETTLEMENT_AMOUNT);
        assertEq(info.decimals, DECIMALS_USD);
        assertEq(info.currencyCode, CURRENCY_USD);
        assertEq(info.paymentToken, PAYMENT_TOKEN_OFFCHAIN);
        assertGt(info.settledAt, 0);
        assertTrue(info.settled);
    }

    function test_RevertWhen_SettlingAlreadySettledBatch() public {
        settlement.settleCommissioning(
            BATCH_ID_1,
            cooperative,
            SETTLEMENT_AMOUNT,
            DECIMALS_USD,
            CURRENCY_USD,
            PAYMENT_TOKEN_OFFCHAIN
        );
        
        vm.expectRevert(
            abi.encodeWithSelector(
                SettlementContract.AlreadySettled.selector,
                BATCH_ID_1
            )
        );
        settlement.settleCommissioning(
            BATCH_ID_1,
            cooperative,
            SETTLEMENT_AMOUNT,
            DECIMALS_USD,
            CURRENCY_USD,
            PAYMENT_TOKEN_OFFCHAIN
        );
    }

    function test_RevertWhen_SettlingWithZeroAddress() public {
        vm.expectRevert(SettlementContract.InvalidRecipient.selector);
        settlement.settleCommissioning(
            BATCH_ID_1,
            address(0),
            SETTLEMENT_AMOUNT,
            DECIMALS_USD,
            CURRENCY_USD,
            PAYMENT_TOKEN_OFFCHAIN
        );
    }

    function test_RevertWhen_SettlingWithZeroAmount() public {
        vm.expectRevert(SettlementContract.InvalidAmount.selector);
        settlement.settleCommissioning(
            BATCH_ID_1,
            cooperative,
            0,
            DECIMALS_USD,
            CURRENCY_USD,
            PAYMENT_TOKEN_OFFCHAIN
        );
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
        
        settlement.settleCommissioning(
            BATCH_ID_1,
            cooperative,
            SETTLEMENT_AMOUNT,
            DECIMALS_USD,
            CURRENCY_USD,
            PAYMENT_TOKEN_OFFCHAIN
        );
        settlement.settleCommissioning(
            BATCH_ID_2,
            cooperative2,
            SETTLEMENT_AMOUNT * 2,
            DECIMALS_USD,
            CURRENCY_USD,
            PAYMENT_TOKEN_OFFCHAIN
        );
        
        assertTrue(settlement.isSettled(BATCH_ID_1));
        assertTrue(settlement.isSettled(BATCH_ID_2));
        
        SettlementContract.SettlementInfo memory info1 = settlement.getSettlement(BATCH_ID_1);
        SettlementContract.SettlementInfo memory info2 = settlement.getSettlement(BATCH_ID_2);
        
        assertEq(info1.recipient, cooperative);
        assertEq(info1.amount, SETTLEMENT_AMOUNT);
        assertEq(info1.currencyCode, CURRENCY_USD);
        assertEq(info2.recipient, cooperative2);
        assertEq(info2.amount, SETTLEMENT_AMOUNT * 2);
        assertEq(info2.currencyCode, CURRENCY_USD);
    }

    function test_SettlementTimestamp() public {
        uint256 beforeTimestamp = block.timestamp;
        
        settlement.settleCommissioning(
            BATCH_ID_1,
            cooperative,
            SETTLEMENT_AMOUNT,
            DECIMALS_USD,
            CURRENCY_USD,
            PAYMENT_TOKEN_OFFCHAIN
        );
        
        (,,,,, uint256 settledAt,) = settlement.settlements(BATCH_ID_1);
        
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
        
        settlement.settleCommissioning(
            batchId,
            recipient,
            amount,
            DECIMALS_USD,
            CURRENCY_USD,
            PAYMENT_TOKEN_OFFCHAIN
        );
        
        assertTrue(settlement.isSettled(batchId));
        
        (
            address storedRecipient,
            uint256 storedAmount,
            uint8 storedDecimals,
            string memory storedCurrency,
            address storedPaymentToken,
            ,
            bool settled
        ) = settlement.settlements(batchId);
        
        assertEq(storedRecipient, recipient);
        assertEq(storedAmount, amount);
        assertEq(storedDecimals, DECIMALS_USD);
        assertEq(storedCurrency, CURRENCY_USD);
        assertEq(storedPaymentToken, PAYMENT_TOKEN_OFFCHAIN);
        assertTrue(settled);
    }

    function test_RevertWhen_SettlingWithEmptyCurrency() public {
        vm.expectRevert(SettlementContract.InvalidCurrency.selector);
        settlement.settleCommissioning(
            BATCH_ID_1,
            cooperative,
            SETTLEMENT_AMOUNT,
            DECIMALS_USD,
            "",  // Empty currency code
            PAYMENT_TOKEN_OFFCHAIN
        );
    }

    function test_SettleWithDifferentCurrencies() public {
        // Settlement 1: USD
        settlement.settleCommissioning(
            BATCH_ID_1,
            cooperative,
            900000,  // $9,000.00
            2,       // 2 decimals
            "USD",
            address(0)
        );
        
        // Settlement 2: ETH
        address buyer = makeAddr("buyer");
        settlement.settleCommissioning(
            BATCH_ID_2,
            buyer,
            5 ether,  // 5 ETH
            18,       // 18 decimals
            "ETH",
            address(0)
        );
        
        SettlementContract.SettlementInfo memory info1 = settlement.getSettlement(BATCH_ID_1);
        SettlementContract.SettlementInfo memory info2 = settlement.getSettlement(BATCH_ID_2);
        
        assertEq(info1.amount, 900000);
        assertEq(info1.decimals, 2);
        assertEq(info1.currencyCode, "USD");
        
        assertEq(info2.amount, 5 ether);
        assertEq(info2.decimals, 18);
        assertEq(info2.currencyCode, "ETH");
    }
}
