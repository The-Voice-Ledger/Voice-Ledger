// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

import {FinancingPool} from "../src/FinancingPool.sol";
import {TradeEscrow} from "../src/TradeEscrow.sol";
import {FeeDistributor} from "../src/FeeDistributor.sol";
import {CoffeeBatchToken} from "../src/CoffeeBatchToken.sol";
import {EPCISEventAnchor} from "../src/EPCISEventAnchor.sol";
import {SettlementContract} from "../src/SettlementContract.sol";
import {ProvenanceDataReceiver} from "../src/ProvenanceDataReceiver.sol";

// ─────────────────────────────────────────────────────────
// Mock USDC (6-decimal ERC-20)
// ─────────────────────────────────────────────────────────
contract MockUSDC is ERC20 {
    constructor() ERC20("USD Coin", "USDC") {}
    function decimals() public pure override returns (uint8) { return 6; }
    function mint(address to, uint256 amount) external { _mint(to, amount); }
}

// ─────────────────────────────────────────────────────────
// Full integration test for FinancingPool + TradeEscrow + FeeDistributor
// ─────────────────────────────────────────────────────────
contract DeFiPoolIntegrationTest is Test {

    // ── Contracts ──
    MockUSDC public usdc;
    CoffeeBatchToken public batchToken;
    EPCISEventAnchor public epcisAnchor;
    SettlementContract public settlement;
    ProvenanceDataReceiver public provenance;
    FinancingPool public pool;
    TradeEscrow public escrow;
    FeeDistributor public distributor;

    // ── Actors ──
    address public deployer;
    address public investor1;
    address public investor2;
    address public seller;     // cooperative / exporter
    address public buyer;
    address public treasury;
    address public reserveFund;

    // ── Test constants ──
    uint256 constant CONTAINER_PRICE = 63_000e6;  // $63,000 USDC
    uint256 constant INVESTOR_DEPOSIT = 200_000e6; // $200k
    string constant BATCH_ID = "BATCH-ETH-001";
    string constant CONTAINER_ID = "CONTAINER-001";
    string constant FARM_ID = "FARM-YIRGA-001";
    bytes32 constant SHIPMENT_HASH = keccak256("epcis:shipment:CONTAINER-001:2026-03-05");
    string constant METADATA_JSON = '{"origin":"Ethiopia","variety":"Yirgacheffe","grade":"G1"}';
    string constant IPFS_CID = "QmTestCid1234567890abcdef";

    // ──────────────────────────────
    // Setup
    // ──────────────────────────────

    function setUp() public {
        deployer   = address(this);
        investor1  = makeAddr("investor1");
        investor2  = makeAddr("investor2");
        seller     = makeAddr("seller");
        buyer      = makeAddr("buyer");
        treasury   = makeAddr("treasury");
        reserveFund = makeAddr("reserveFund");

        // Deploy mock USDC
        usdc = new MockUSDC();

        // Deploy existing Voice Ledger contracts
        batchToken  = new CoffeeBatchToken();
        epcisAnchor = new EPCISEventAnchor("Guzo");
        settlement  = new SettlementContract();
        provenance  = new ProvenanceDataReceiver(deployer); // deployer is forwarder

        // Deploy new DeFi contracts
        pool = new FinancingPool(IERC20(address(usdc)));

        distributor = new FeeDistributor(
            address(usdc),
            address(pool),
            treasury,
            reserveFund
        );

        escrow = new TradeEscrow(
            address(batchToken),
            address(epcisAnchor),
            address(provenance),
            address(settlement),
            address(pool),
            address(distributor),
            address(usdc)
        );

        // Wire up permissions
        pool.setEscrow(address(escrow));
        distributor.setEscrow(address(escrow));

        // ── Seed the world ──

        // Investor deposits $200k USDC into pool
        usdc.mint(investor1, INVESTOR_DEPOSIT);
        vm.startPrank(investor1);
        usdc.approve(address(pool), INVESTOR_DEPOSIT);
        pool.deposit(INVESTOR_DEPOSIT, investor1);
        vm.stopPrank();

        // Mint a container token to the seller
        uint256 tokenId = batchToken.mintBatch(
            seller,
            500, // 500 units
            CONTAINER_ID,
            METADATA_JSON,
            IPFS_CID
        );
        assertEq(tokenId, 1);

        // Anchor the shipment EPCIS event
        epcisAnchor.anchorEvent(SHIPMENT_HASH, CONTAINER_ID, "ShippingEvent");

        // Submit CRE deforestation attestation (farm is EUDR compliant)
        bytes memory attestation = abi.encode(
            FARM_ID,
            int64(6_130000),   // latitude (Yirgacheffe)
            int64(38_410000),  // longitude
            uint8(0),          // LOW risk
            true,              // EUDR compliant
            uint256(0),        // zero tree loss
            block.timestamp
        );
        provenance.onReport(abi.encodePacked(uint8(0x02), attestation));

        // Seller approves escrow to transfer their ERC-1155
        vm.prank(seller);
        batchToken.setApprovalForAll(address(escrow), true);

        // Buyer gets USDC to pay later
        usdc.mint(buyer, CONTAINER_PRICE);
    }

    // ──────────────────────────────
    // Happy path: full cycle
    // ──────────────────────────────

    function test_FullTradeLifecycle() public {
        // ── Step 1: Seller requests advance ──
        vm.prank(seller);
        uint256 tradeId = escrow.requestAdvance(
            1,                  // tokenId
            500,                // tokenAmount
            buyer,
            CONTAINER_PRICE,
            SHIPMENT_HASH,
            FARM_ID
        );
        assertEq(tradeId, 1);

        // Verify: token is in escrow
        assertEq(batchToken.balanceOf(address(escrow), 1), 500);
        assertEq(batchToken.balanceOf(seller, 1), 0);

        // Verify: seller received advance (63000 - 2% fee = 61740 USDC)
        uint256 expectedFee = (CONTAINER_PRICE * 200) / 10_000; // 1,260 USDC
        uint256 expectedAdvance = CONTAINER_PRICE - expectedFee;
        assertEq(usdc.balanceOf(seller), expectedAdvance);

        // Verify: pool outstanding advances increased
        assertEq(pool.totalAdvanced(), expectedAdvance);

        // Verify: trade is active
        TradeEscrow.Trade memory trade = escrow.getTrade(tradeId);
        assertEq(uint8(trade.status), uint8(TradeEscrow.TradeStatus.Active));
        assertEq(trade.seller, seller);
        assertEq(trade.buyer, buyer);
        assertEq(trade.agreedPrice, CONTAINER_PRICE);
        assertEq(trade.advanceAmount, expectedAdvance);
        assertEq(trade.feeAmount, expectedFee);

        // Verify: token is marked as pledged
        assertTrue(escrow.isTokenPledged(1));

        // ── Step 2: Buyer confirms delivery and pays ──
        vm.startPrank(buyer);
        usdc.approve(address(escrow), CONTAINER_PRICE);
        escrow.confirmDelivery(tradeId);
        vm.stopPrank();

        // Verify: token released to buyer
        assertEq(batchToken.balanceOf(buyer, 1), 500);
        assertEq(batchToken.balanceOf(address(escrow), 1), 0);

        // Verify: buyer paid full price
        assertEq(usdc.balanceOf(buyer), 0);

        // Verify: trade is settled
        trade = escrow.getTrade(tradeId);
        assertEq(uint8(trade.status), uint8(TradeEscrow.TradeStatus.Settled));

        // Verify: token no longer pledged
        assertFalse(escrow.isTokenPledged(1));

        // Verify: pool outstanding advances reduced back to 0
        assertEq(pool.totalAdvanced(), 0);

        // Verify: fee was distributed (62.5% / 25% / 12.5%)
        uint256 investorShare = (expectedFee * 6_250) / 10_000;  // 787.5 → 787 (truncation)
        uint256 protocolShare = (expectedFee * 2_500) / 10_000;  // 315
        uint256 reserveShare  = expectedFee - investorShare - protocolShare;

        assertEq(usdc.balanceOf(treasury), protocolShare);
        assertEq(usdc.balanceOf(reserveFund), reserveShare);

        // Investor share went back to pool (increases totalAssets)
        // Pool should have: original deposit - advance + principal returned + investor yield
        // = 200_000 - 61_740 + 61_740 + 787 = 200_787 ... but investor share comes from fee
        // totalAssets = balance + totalAdvanced = (200_000 - 61_740 + 61_740 + 787) + 0
        assertEq(pool.totalAssets(), INVESTOR_DEPOSIT + investorShare);

        // Verify: settlement recorded on existing contract
        assertTrue(settlement.isSettled(1)); // tokenId = 1
        SettlementContract.SettlementInfo memory info = settlement.getSettlement(1);
        assertEq(info.recipient, buyer);
        assertEq(info.amount, CONTAINER_PRICE);
        assertEq(info.decimals, 6);

        // Verify: cumulative analytics
        assertEq(pool.cumulativeFeesEarned(), expectedFee);
        assertEq(distributor.totalDistributed(), expectedFee);
    }

    // ──────────────────────────────
    // Pool ERC-4626 mechanics
    // ──────────────────────────────

    function test_PoolDepositAndRedeem() public {
        // investor1 already has shares from setUp
        uint256 shares = pool.balanceOf(investor1);
        assertGt(shares, 0);

        // investor2 deposits
        usdc.mint(investor2, 100_000e6);
        vm.startPrank(investor2);
        usdc.approve(address(pool), 100_000e6);
        uint256 shares2 = pool.deposit(100_000e6, investor2);
        vm.stopPrank();
        assertGt(shares2, 0);

        // Total assets = 300k
        assertEq(pool.totalAssets(), 300_000e6);

        // investor2 redeems
        vm.startPrank(investor2);
        pool.redeem(shares2, investor2, investor2);
        vm.stopPrank();
        assertEq(usdc.balanceOf(investor2), 100_000e6);
    }

    function test_PoolSharePriceIncreasesAfterFees() public {
        uint256 sharesBefore = pool.balanceOf(investor1);
        uint256 previewRedeemBefore = pool.previewRedeem(sharesBefore);

        // Execute a full trade cycle to generate fees
        _executeFullTrade();

        // After fees, the same shares are worth more USDC
        uint256 previewRedeemAfter = pool.previewRedeem(sharesBefore);
        assertGt(previewRedeemAfter, previewRedeemBefore);
    }

    function test_PoolUtilisation() public {
        assertEq(pool.utilisationBps(), 0);

        vm.prank(seller);
        escrow.requestAdvance(1, 500, buyer, CONTAINER_PRICE, SHIPMENT_HASH, FARM_ID);

        // Utilisation = advance / totalAssets
        uint256 expectedAdvance = CONTAINER_PRICE - (CONTAINER_PRICE * 200 / 10_000);
        uint256 expectedBps = (expectedAdvance * 10_000) / pool.totalAssets();
        assertEq(pool.utilisationBps(), expectedBps);
    }

    // ──────────────────────────────
    // Gate: Shipment not anchored
    // ──────────────────────────────

    function test_RevertWhen_ShipmentNotAnchored() public {
        bytes32 fakeHash = keccak256("not-anchored");

        vm.prank(seller);
        vm.expectRevert(
            abi.encodeWithSelector(TradeEscrow.ShipmentNotAnchored.selector, fakeHash)
        );
        escrow.requestAdvance(1, 500, buyer, CONTAINER_PRICE, fakeHash, FARM_ID);
    }

    // ──────────────────────────────
    // Gate: Farm not CRE compliant
    // ──────────────────────────────

    function test_RevertWhen_FarmNotCompliant() public {
        string memory badFarm = "FARM-NONCOMPLIANT";

        vm.prank(seller);
        vm.expectRevert(
            abi.encodeWithSelector(TradeEscrow.FarmNotCompliant.selector, badFarm)
        );
        escrow.requestAdvance(1, 500, buyer, CONTAINER_PRICE, SHIPMENT_HASH, badFarm);
    }

    // ──────────────────────────────
    // Gate: Double-pledge prevention
    // ──────────────────────────────

    function test_RevertWhen_TokenAlreadyPledged() public {
        vm.prank(seller);
        escrow.requestAdvance(1, 500, buyer, CONTAINER_PRICE, SHIPMENT_HASH, FARM_ID);

        // Try to pledge same token again
        vm.prank(seller);
        vm.expectRevert(
            abi.encodeWithSelector(TradeEscrow.TradeAlreadyExists.selector, 1)
        );
        escrow.requestAdvance(1, 500, buyer, CONTAINER_PRICE, SHIPMENT_HASH, FARM_ID);
    }

    // ──────────────────────────────
    // Pool liquidity cap
    // ──────────────────────────────

    function test_RevertWhen_AdvanceExceedsPoolCap() public {
        // Set a very low max single advance
        pool.setMaxSingleAdvance(1_000e6); // $1,000

        vm.prank(seller);
        vm.expectRevert(
            abi.encodeWithSelector(
                FinancingPool.DrawExceedsMaxAdvance.selector,
                CONTAINER_PRICE - (CONTAINER_PRICE * 200 / 10_000),
                1_000e6
            )
        );
        escrow.requestAdvance(1, 500, buyer, CONTAINER_PRICE, SHIPMENT_HASH, FARM_ID);
    }

    function test_RevertWhen_PoolLiquidityInsufficient() public {
        // Set utilisation cap to 1% (only $2,000 available)
        pool.setMaxAdvanceRatio(100);

        vm.prank(seller);
        vm.expectRevert(); // InsufficientPoolLiquidity
        escrow.requestAdvance(1, 500, buyer, CONTAINER_PRICE, SHIPMENT_HASH, FARM_ID);
    }

    // ──────────────────────────────
    // Buyer default
    // ──────────────────────────────

    function test_MarkDefault_AfterDeadline() public {
        vm.prank(seller);
        uint256 tradeId = escrow.requestAdvance(1, 500, buyer, CONTAINER_PRICE, SHIPMENT_HASH, FARM_ID);

        // Fast-forward past deadline (60 days default)
        vm.warp(block.timestamp + 61 days);

        escrow.markDefault(tradeId);

        // Token returned to seller
        assertEq(batchToken.balanceOf(seller, 1), 500);

        // Trade marked as defaulted
        TradeEscrow.Trade memory trade = escrow.getTrade(tradeId);
        assertEq(uint8(trade.status), uint8(TradeEscrow.TradeStatus.Defaulted));

        // Token no longer pledged
        assertFalse(escrow.isTokenPledged(1));
    }

    function test_RevertWhen_DefaultBeforeDeadline() public {
        vm.prank(seller);
        uint256 tradeId = escrow.requestAdvance(1, 500, buyer, CONTAINER_PRICE, SHIPMENT_HASH, FARM_ID);

        vm.expectRevert(); // DeadlineNotReached
        escrow.markDefault(tradeId);
    }

    // ──────────────────────────────
    // Cancellation
    // ──────────────────────────────

    function test_CancelTrade_SellerReturnsAdvance() public {
        vm.prank(seller);
        uint256 tradeId = escrow.requestAdvance(1, 500, buyer, CONTAINER_PRICE, SHIPMENT_HASH, FARM_ID);

        uint256 advanceAmount = CONTAINER_PRICE - (CONTAINER_PRICE * 200 / 10_000);

        // Seller approves escrow to pull back the advance
        vm.startPrank(seller);
        usdc.approve(address(escrow), advanceAmount);
        escrow.cancelTrade(tradeId);
        vm.stopPrank();

        // Token returned to seller
        assertEq(batchToken.balanceOf(seller, 1), 500);

        // Seller's USDC balance = 0 (advance returned to pool)
        assertEq(usdc.balanceOf(seller), 0);

        // Pool is whole again (no fee charged on cancellation)
        assertEq(pool.totalAdvanced(), 0);
        assertEq(pool.totalAssets(), INVESTOR_DEPOSIT);

        // Trade is cancelled
        TradeEscrow.Trade memory trade = escrow.getTrade(tradeId);
        assertEq(uint8(trade.status), uint8(TradeEscrow.TradeStatus.Cancelled));
    }

    function test_RevertWhen_BuyerTriesToCancel() public {
        vm.prank(seller);
        uint256 tradeId = escrow.requestAdvance(1, 500, buyer, CONTAINER_PRICE, SHIPMENT_HASH, FARM_ID);

        vm.prank(buyer);
        vm.expectRevert(TradeEscrow.Unauthorized.selector);
        escrow.cancelTrade(tradeId);
    }

    // ──────────────────────────────
    // Fee distributor
    // ──────────────────────────────

    function test_FeeDistributorSplit() public {
        _executeFullTrade();

        uint256 expectedFee = (CONTAINER_PRICE * 200) / 10_000; // 1,260 USDC
        uint256 investorShare = (expectedFee * 6_250) / 10_000;
        uint256 protocolShare = (expectedFee * 2_500) / 10_000;
        uint256 reserveShare  = expectedFee - investorShare - protocolShare;

        assertEq(distributor.totalDistributed(), expectedFee);
        assertEq(distributor.totalToInvestors(), investorShare);
        assertEq(distributor.totalToProtocol(), protocolShare);
        assertEq(distributor.totalToReserve(), reserveShare);

        assertEq(usdc.balanceOf(treasury), protocolShare);
        assertEq(usdc.balanceOf(reserveFund), reserveShare);
    }

    function test_FeeDistributorSplitUpdate() public {
        // Change split to 50/30/20
        distributor.setSplit(5_000, 3_000, 2_000);

        _executeFullTrade();

        uint256 expectedFee = (CONTAINER_PRICE * 200) / 10_000;
        uint256 investorShare = (expectedFee * 5_000) / 10_000;
        uint256 protocolShare = (expectedFee * 3_000) / 10_000;

        assertEq(distributor.totalToInvestors(), investorShare);
        assertEq(distributor.totalToProtocol(), protocolShare);
    }

    function test_RevertWhen_InvalidSplit() public {
        vm.expectRevert(FeeDistributor.InvalidSplit.selector);
        distributor.setSplit(5_000, 3_000, 3_000); // sums to 11000
    }

    // ──────────────────────────────
    // Authorization
    // ──────────────────────────────

    function test_RevertWhen_UnauthorizedDrawFunds() public {
        vm.prank(seller);
        vm.expectRevert(FinancingPool.Unauthorized.selector);
        pool.drawFunds(1, 1_000e6, seller);
    }

    function test_RevertWhen_UnauthorizedDistributeFee() public {
        vm.prank(seller);
        vm.expectRevert(FeeDistributor.Unauthorized.selector);
        distributor.distributeFee(1, 1_000e6);
    }

    function test_RevertWhen_OnlyBuyerCanConfirmDelivery() public {
        vm.prank(seller);
        uint256 tradeId = escrow.requestAdvance(1, 500, buyer, CONTAINER_PRICE, SHIPMENT_HASH, FARM_ID);

        vm.prank(seller);
        vm.expectRevert(TradeEscrow.Unauthorized.selector);
        escrow.confirmDelivery(tradeId);
    }

    function test_RevertWhen_DeliveryAfterDeadline() public {
        vm.prank(seller);
        uint256 tradeId = escrow.requestAdvance(1, 500, buyer, CONTAINER_PRICE, SHIPMENT_HASH, FARM_ID);

        vm.warp(block.timestamp + 61 days);

        vm.startPrank(buyer);
        usdc.approve(address(escrow), CONTAINER_PRICE);
        vm.expectRevert(); // DeadlineExceeded
        escrow.confirmDelivery(tradeId);
        vm.stopPrank();
    }

    // ──────────────────────────────
    // Admin functions
    // ──────────────────────────────

    function test_UpdateDefaultFeeBps() public {
        escrow.setDefaultFeeBps(150); // 1.5%
        assertEq(escrow.defaultFeeBps(), 150);
    }

    function test_RevertWhen_FeeExceedsHardCap() public {
        vm.expectRevert(
            abi.encodeWithSelector(TradeEscrow.InvalidFee.selector, 600)
        );
        escrow.setDefaultFeeBps(600); // 6% > 5% cap
    }

    function test_UpdateMaxTransitSeconds() public {
        escrow.setMaxTransitSeconds(90 days);
        assertEq(escrow.maxTransitSeconds(), 90 days);
    }

    function test_RevertWhen_ConfirmingSettledTrade() public {
        _executeFullTrade();

        vm.startPrank(buyer);
        usdc.mint(buyer, CONTAINER_PRICE); // give buyer more USDC
        usdc.approve(address(escrow), CONTAINER_PRICE);
        vm.expectRevert(
            abi.encodeWithSelector(TradeEscrow.TradeNotActive.selector, 1)
        );
        escrow.confirmDelivery(1);
        vm.stopPrank();
    }

    // ──────────────────────────────
    // View helpers
    // ──────────────────────────────

    function test_AvailableForAdvance() public {
        uint256 available = pool.availableForAdvance();
        // 80% of 200k = 160k
        assertEq(available, (INVESTOR_DEPOSIT * 8_000) / 10_000);
    }

    function test_GetTradeForToken() public {
        vm.prank(seller);
        uint256 tradeId = escrow.requestAdvance(1, 500, buyer, CONTAINER_PRICE, SHIPMENT_HASH, FARM_ID);

        assertEq(escrow.getTradeForToken(1), tradeId);
    }

    // ──────────────────────────────
    // Internal helper
    // ──────────────────────────────

    function _executeFullTrade() internal returns (uint256 tradeId) {
        vm.prank(seller);
        tradeId = escrow.requestAdvance(1, 500, buyer, CONTAINER_PRICE, SHIPMENT_HASH, FARM_ID);

        vm.startPrank(buyer);
        usdc.approve(address(escrow), CONTAINER_PRICE);
        escrow.confirmDelivery(tradeId);
        vm.stopPrank();
    }
}
