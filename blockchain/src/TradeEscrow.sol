// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ERC1155Holder} from "@openzeppelin/contracts/token/ERC1155/utils/ERC1155Holder.sol";
import {IERC1155} from "@openzeppelin/contracts/token/ERC1155/IERC1155.sol";

// Existing Voice Ledger contract interfaces (read-only)
interface ICoffeeBatchToken {
    struct BatchMetadata {
        string batchId;
        uint256 quantity;
        string metadata;
        string ipfsCid;
        uint256 createdAt;
        bool exists;
        bool isAggregated;
        uint256[] childTokenIds;
    }
    function getBatchMetadata(uint256 tokenId) external view returns (BatchMetadata memory);
    function balanceOf(address account, uint256 id) external view returns (uint256);
    function safeTransferFrom(address from, address to, uint256 id, uint256 amount, bytes calldata data) external;
}

interface IEPCISEventAnchor {
    function isAnchored(bytes32 eventHash) external view returns (bool);
}

interface IProvenanceDataReceiver {
    function isFarmCompliant(string calldata farmId) external view returns (bool);
}

interface ISettlementContract {
    function settleCommissioning(
        uint256 batchId,
        address recipient,
        uint256 amount,
        uint8 decimals,
        string calldata currencyCode,
        address paymentToken
    ) external;
}

interface IFinancingPool {
    function drawFunds(uint256 tradeId, uint256 amount, address recipient) external;
    function returnFunds(uint256 tradeId, uint256 principal, uint256 fee) external;
    function writeOffDefault(uint256 tradeId, uint256 principal) external;
    function asset() external view returns (address);
}

interface IFeeDistributor {
    function distributeFee(uint256 tradeId, uint256 totalFee) external;
}

/**
 * @title  TradeEscrow
 * @notice Orchestrates the financing flow for confirmed coffee shipments.
 *
 *         1. Seller requests advance → token locked, USDC sent to seller
 *         2. Buyer confirms delivery + pays → token released, pool repaid
 *
 *         Mandatory gates before advancing:
 *         - ERC-1155 container token exists and is transferred to this contract
 *         - Shipment EPCIS event hash is anchored on-chain
 *         - CRE deforestation attestation confirms farm compliance
 *
 *         Integrates with 4 existing contracts (read/call, no modifications):
 *         - CoffeeBatchToken  (ERC-1155 collateral, safeTransferFrom)
 *         - EPCISEventAnchor  (read: isAnchored)
 *         - ProvenanceDataReceiver (read: isFarmCompliant)
 *         - SettlementContract (write: settleCommissioning for final settlement)
 *
 * @dev    Designed for Base Sepolia. Solidity 0.8.20.
 */
contract TradeEscrow is ERC1155Holder {
    using SafeERC20 for IERC20;

    // ─────────────────────────────────────────────
    // Enums
    // ─────────────────────────────────────────────
    enum TradeStatus {
        None,           // 0 — does not exist
        Active,         // 1 — advance disbursed, token in escrow, awaiting delivery
        Settled,        // 2 — buyer paid, token released, pool repaid
        Defaulted,      // 3 — buyer failed to pay within grace period
        Cancelled       // 4 — cancelled before delivery (token returned to seller)
    }

    // ─────────────────────────────────────────────
    // Structs
    // ─────────────────────────────────────────────
    struct Trade {
        uint256 tokenId;          // ERC-1155 container token held as collateral
        uint256 tokenAmount;      // ERC-1155 amount (usually = container quantity)
        address seller;           // Cooperative / exporter receiving the advance
        address buyer;            // Confirmed buyer who will repay
        uint256 agreedPrice;      // Full price in USDC (6 decimals)
        uint256 advanceAmount;    // USDC sent to seller (agreedPrice - fee)
        uint256 feeBps;           // Fee in basis points (e.g. 200 = 2%)
        uint256 feeAmount;        // Absolute fee in USDC
        bytes32 shipmentHash;     // EPCIS shipment event hash (verified on-chain)
        string  farmId;           // Farm ID for CRE compliance check
        uint256 createdAt;        // Timestamp of advance
        uint256 settledAt;        // Timestamp of settlement (0 if active)
        uint256 deadline;         // Payment deadline (createdAt + maxTransitDays)
        TradeStatus status;
    }

    // ─────────────────────────────────────────────
    // Errors
    // ─────────────────────────────────────────────
    error Unauthorized();
    error ZeroAddress();
    error ZeroAmount();
    error TradeAlreadyExists(uint256 tradeId);
    error TradeNotFound(uint256 tradeId);
    error TradeNotActive(uint256 tradeId);
    error InvalidFee(uint256 feeBps);
    error ShipmentNotAnchored(bytes32 shipmentHash);
    error FarmNotCompliant(string farmId);
    error TokenNotInEscrow(uint256 tokenId);
    error BuyerPaymentInsufficient(uint256 expected, uint256 received);
    error DeadlineNotReached(uint256 deadline, uint256 currentTime);
    error DeadlineExceeded(uint256 deadline);

    // ─────────────────────────────────────────────
    // Events
    // ─────────────────────────────────────────────
    event AdvanceDisbursed(
        uint256 indexed tradeId,
        uint256 indexed tokenId,
        address indexed seller,
        address buyer,
        uint256 agreedPrice,
        uint256 advanceAmount,
        uint256 feeAmount
    );

    event DeliveryConfirmed(
        uint256 indexed tradeId,
        uint256 indexed tokenId,
        address indexed buyer,
        uint256 paymentAmount
    );

    event TradeDefaulted(
        uint256 indexed tradeId,
        uint256 indexed tokenId,
        address indexed seller
    );

    event TradeCancelled(
        uint256 indexed tradeId,
        uint256 indexed tokenId,
        address indexed seller
    );

    event DefaultFeeBpsUpdated(uint256 oldBps, uint256 newBps);
    event MaxTransitSecondsUpdated(uint256 oldSeconds, uint256 newSeconds);

    // ─────────────────────────────────────────────
    // State
    // ─────────────────────────────────────────────

    /// @notice Contract owner
    address public owner;

    /// @notice External contract references
    ICoffeeBatchToken public coffeeBatchToken;
    IEPCISEventAnchor public epcisAnchor;
    IProvenanceDataReceiver public provenanceReceiver;
    ISettlementContract public settlementContract;
    IFinancingPool public financingPool;
    IFeeDistributor public feeDistributor;

    /// @notice USDC token (same as pool's asset)
    IERC20 public usdc;

    /// @notice Auto-incrementing trade counter
    uint256 public nextTradeId;

    /// @notice Default fee in basis points (200 = 2.0%)
    uint256 public defaultFeeBps;

    /// @notice Maximum transit period in seconds before buyer is considered in default
    uint256 public maxTransitSeconds;

    /// @notice Trade ID → Trade details
    mapping(uint256 => Trade) public trades;

    /// @notice tokenId → tradeId mapping to prevent double-pledging
    mapping(uint256 => uint256) public tokenToTrade;

    // ─────────────────────────────────────────────
    // Constants
    // ─────────────────────────────────────────────
    uint256 private constant BPS = 10_000;
    uint256 private constant MAX_FEE_BPS = 500; // 5% hard cap

    // ─────────────────────────────────────────────
    // Modifiers
    // ─────────────────────────────────────────────
    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    // ─────────────────────────────────────────────
    // Constructor
    // ─────────────────────────────────────────────

    /**
     * @param _coffeeBatchToken    Deployed CoffeeBatchToken (ERC-1155) address
     * @param _epcisAnchor         Deployed EPCISEventAnchor address
     * @param _provenanceReceiver  Deployed ProvenanceDataReceiver address
     * @param _settlementContract  Deployed SettlementContract address
     * @param _financingPool       Deployed FinancingPool address
     * @param _feeDistributor      Deployed FeeDistributor address
     * @param _usdc                USDC token address on this chain
     */
    constructor(
        address _coffeeBatchToken,
        address _epcisAnchor,
        address _provenanceReceiver,
        address _settlementContract,
        address _financingPool,
        address _feeDistributor,
        address _usdc
    ) {
        owner = msg.sender;

        coffeeBatchToken = ICoffeeBatchToken(_coffeeBatchToken);
        epcisAnchor = IEPCISEventAnchor(_epcisAnchor);
        provenanceReceiver = IProvenanceDataReceiver(_provenanceReceiver);
        settlementContract = ISettlementContract(_settlementContract);
        financingPool = IFinancingPool(_financingPool);
        feeDistributor = IFeeDistributor(_feeDistributor);
        usdc = IERC20(_usdc);

        nextTradeId = 1;
        defaultFeeBps = 200;                 // 2.0%
        maxTransitSeconds = 60 days;         // 60-day default deadline
    }

    // ─────────────────────────────────────────────
    // Core: Request Advance
    // ─────────────────────────────────────────────

    /**
     * @notice Seller requests an advance against a confirmed shipment.
     *
     *         Pre-conditions (all enforced on-chain):
     *         1. ERC-1155 token exists and sender has balance
     *         2. Token is not already pledged to another trade
     *         3. Shipment EPCIS event hash is anchored
     *         4. Farm is CRE-attested as EUDR compliant
     *
     *         Flow:
     *         - ERC-1155 transferred from seller to this contract
     *         - USDC drawn from FinancingPool → sent to seller
     *
     * @param tokenId       ERC-1155 container token ID
     * @param tokenAmount   Amount of ERC-1155 tokens (container quantity)
     * @param buyer         Confirmed buyer address
     * @param agreedPrice   Full agreed price in USDC (6 decimals)
     * @param shipmentHash  SHA-256 hash of the EPCIS shipment event
     * @param farmId        Farm identifier for CRE compliance lookup
     * @return tradeId      Newly created trade ID
     */
    function requestAdvance(
        uint256 tokenId,
        uint256 tokenAmount,
        address buyer,
        uint256 agreedPrice,
        bytes32 shipmentHash,
        string calldata farmId
    ) external returns (uint256 tradeId) {
        if (buyer == address(0)) revert ZeroAddress();
        if (agreedPrice == 0) revert ZeroAmount();

        // ── Gate 1: Token not already pledged ──
        if (tokenToTrade[tokenId] != 0) revert TradeAlreadyExists(tokenToTrade[tokenId]);

        // ── Gate 2: Shipment event is anchored on-chain ──
        if (!epcisAnchor.isAnchored(shipmentHash)) revert ShipmentNotAnchored(shipmentHash);

        // ── Gate 3: Farm is CRE-attested as EUDR compliant ──
        if (!provenanceReceiver.isFarmCompliant(farmId)) revert FarmNotCompliant(farmId);

        // ── Calculate fee and advance ──
        uint256 feeBps = defaultFeeBps;
        if (feeBps > MAX_FEE_BPS) revert InvalidFee(feeBps);
        uint256 feeAmount = (agreedPrice * feeBps) / BPS;
        uint256 advanceAmount = agreedPrice - feeAmount;

        // ── Assign trade ID ──
        tradeId = nextTradeId++;

        // ── Transfer ERC-1155 token from seller to escrow ──
        coffeeBatchToken.safeTransferFrom(msg.sender, address(this), tokenId, tokenAmount, "");

        // Verify token is now held by this contract
        if (coffeeBatchToken.balanceOf(address(this), tokenId) < tokenAmount) {
            revert TokenNotInEscrow(tokenId);
        }

        // ── Record the trade ──
        trades[tradeId] = Trade({
            tokenId: tokenId,
            tokenAmount: tokenAmount,
            seller: msg.sender,
            buyer: buyer,
            agreedPrice: agreedPrice,
            advanceAmount: advanceAmount,
            feeBps: feeBps,
            feeAmount: feeAmount,
            shipmentHash: shipmentHash,
            farmId: farmId,
            createdAt: block.timestamp,
            settledAt: 0,
            deadline: block.timestamp + maxTransitSeconds,
            status: TradeStatus.Active
        });

        tokenToTrade[tokenId] = tradeId;

        // ── Draw USDC from pool → send directly to seller ──
        financingPool.drawFunds(tradeId, advanceAmount, msg.sender);

        emit AdvanceDisbursed(
            tradeId,
            tokenId,
            msg.sender,
            buyer,
            agreedPrice,
            advanceAmount,
            feeAmount
        );
    }

    // ─────────────────────────────────────────────
    // Core: Confirm Delivery & Repay
    // ─────────────────────────────────────────────

    /**
     * @notice Buyer confirms delivery and repays the pool.
     *
     *         The buyer must have approved this contract for `agreedPrice` USDC
     *         before calling. Flow:
     *
     *         1. Pull `agreedPrice` USDC from buyer
     *         2. Send `advanceAmount` (principal) back to pool
     *         3. Send `feeAmount` to FeeDistributor
     *         4. Transfer ERC-1155 token from escrow to buyer
     *         5. Record final settlement in SettlementContract
     *
     * @param tradeId  The trade to settle
     */
    function confirmDelivery(uint256 tradeId) external {
        Trade storage trade = trades[tradeId];
        if (trade.status == TradeStatus.None) revert TradeNotFound(tradeId);
        if (trade.status != TradeStatus.Active) revert TradeNotActive(tradeId);
        if (msg.sender != trade.buyer) revert Unauthorized();
        if (block.timestamp > trade.deadline) revert DeadlineExceeded(trade.deadline);

        // ── Pull full agreed price from buyer ──
        usdc.safeTransferFrom(msg.sender, address(this), trade.agreedPrice);

        // ── Return principal to pool (pool pulls via safeTransferFrom) ──
        usdc.forceApprove(address(financingPool), trade.advanceAmount);
        financingPool.returnFunds(tradeId, trade.advanceAmount, trade.feeAmount);

        // ── Send fee to distributor ──
        usdc.safeTransfer(address(feeDistributor), trade.feeAmount);
        feeDistributor.distributeFee(tradeId, trade.feeAmount);

        // ── Release ERC-1155 token to buyer ──
        coffeeBatchToken.safeTransferFrom(
            address(this),
            trade.buyer,
            trade.tokenId,
            trade.tokenAmount,
            ""
        );

        // ── Record final settlement on existing SettlementContract ──
        settlementContract.settleCommissioning(
            trade.tokenId,
            trade.buyer,
            trade.agreedPrice,
            6,                // USDC decimals
            "USDC",
            address(usdc)
        );

        // ── Update trade state ──
        trade.status = TradeStatus.Settled;
        trade.settledAt = block.timestamp;
        delete tokenToTrade[trade.tokenId];

        emit DeliveryConfirmed(tradeId, trade.tokenId, msg.sender, trade.agreedPrice);
    }

    // ─────────────────────────────────────────────
    // Default handling
    // ─────────────────────────────────────────────

    /**
     * @notice Mark a trade as defaulted after the deadline passes.
     *         Returns the ERC-1155 token to the seller (the goods are still the
     *         seller's property if the buyer didn't pay).
     *
     * @dev    In a production system this would trigger insurance / dispute
     *         resolution. For now the pool absorbs the loss and the seller
     *         keeps their goods.
     *
     * @param tradeId  The overdue trade
     */
    function markDefault(uint256 tradeId) external {
        Trade storage trade = trades[tradeId];
        if (trade.status == TradeStatus.None) revert TradeNotFound(tradeId);
        if (trade.status != TradeStatus.Active) revert TradeNotActive(tradeId);
        if (block.timestamp < trade.deadline) revert DeadlineNotReached(trade.deadline, block.timestamp);

        // Return token to seller (goods never accepted by buyer)
        coffeeBatchToken.safeTransferFrom(
            address(this),
            trade.seller,
            trade.tokenId,
            trade.tokenAmount,
            ""
        );

        // Write off the advance so pool accounting stays accurate
        financingPool.writeOffDefault(tradeId, trade.advanceAmount);

        trade.status = TradeStatus.Defaulted;
        trade.settledAt = block.timestamp;
        delete tokenToTrade[trade.tokenId];

        emit TradeDefaulted(tradeId, trade.tokenId, trade.seller);
    }

    // ─────────────────────────────────────────────
    // Cancel (before delivery, owner only — emergency)
    // ─────────────────────────────────────────────

    /**
     * @notice Emergency cancel: seller returns the advance, gets token back.
     * @dev    Seller must have approved this contract for `advanceAmount` USDC.
     * @param  tradeId  The trade to cancel
     */
    function cancelTrade(uint256 tradeId) external {
        Trade storage trade = trades[tradeId];
        if (trade.status == TradeStatus.None) revert TradeNotFound(tradeId);
        if (trade.status != TradeStatus.Active) revert TradeNotActive(tradeId);
        // Only seller or owner can cancel
        if (msg.sender != trade.seller && msg.sender != owner) revert Unauthorized();

        // Seller must return the advance amount
        usdc.safeTransferFrom(trade.seller, address(this), trade.advanceAmount);

        // Return principal to pool (pool pulls via safeTransferFrom, no fee)
        usdc.forceApprove(address(financingPool), trade.advanceAmount);
        financingPool.returnFunds(tradeId, trade.advanceAmount, 0);

        // Return token to seller
        coffeeBatchToken.safeTransferFrom(
            address(this),
            trade.seller,
            trade.tokenId,
            trade.tokenAmount,
            ""
        );

        trade.status = TradeStatus.Cancelled;
        trade.settledAt = block.timestamp;
        delete tokenToTrade[trade.tokenId];

        emit TradeCancelled(tradeId, trade.tokenId, trade.seller);
    }

    // ─────────────────────────────────────────────
    // View helpers
    // ─────────────────────────────────────────────

    /**
     * @notice Get full trade details.
     */
    function getTrade(uint256 tradeId) external view returns (Trade memory) {
        if (trades[tradeId].status == TradeStatus.None) revert TradeNotFound(tradeId);
        return trades[tradeId];
    }

    /**
     * @notice Check if a token is currently pledged as collateral.
     */
    function isTokenPledged(uint256 tokenId) external view returns (bool) {
        return tokenToTrade[tokenId] != 0;
    }

    /**
     * @notice Get the trade ID for a pledged token.
     */
    function getTradeForToken(uint256 tokenId) external view returns (uint256) {
        return tokenToTrade[tokenId];
    }

    // ─────────────────────────────────────────────
    // Admin
    // ─────────────────────────────────────────────

    function setDefaultFeeBps(uint256 _bps) external onlyOwner {
        if (_bps > MAX_FEE_BPS) revert InvalidFee(_bps);
        emit DefaultFeeBpsUpdated(defaultFeeBps, _bps);
        defaultFeeBps = _bps;
    }

    function setMaxTransitSeconds(uint256 _seconds) external onlyOwner {
        emit MaxTransitSecondsUpdated(maxTransitSeconds, _seconds);
        maxTransitSeconds = _seconds;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        owner = newOwner;
    }
}
