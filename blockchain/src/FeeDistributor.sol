// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/**
 * @title  FeeDistributor
 * @notice Splits trade-advance fees three ways:
 *
 *         ┌─────────────────────────────────────────────────┐
 *         │  Total fee (e.g. 2% of agreed price)            │
 *         │                                                 │
 *         │  62.5%  → Pool investors  (accrues in pool)     │
 *         │  25.0%  → Protocol treasury (Voice Ledger)      │
 *         │  12.5%  → Reserve fund    (default coverage)    │
 *         └─────────────────────────────────────────────────┘
 *
 *         Default split per the DEFI_TRADE_FINANCE spec:
 *           Investor yield:  1.25% out of 2%  = 62.5%
 *           Protocol:        0.50% out of 2%  = 25.0%
 *           Reserve:         0.25% out of 2%  = 12.5%
 *
 *         The escrow contract sends USDC to this contract, then calls
 *         `distributeFee` which forwards each portion to its destination.
 *         The investor share is sent back to the FinancingPool (accrues
 *         as totalAssets, increasing share price for all depositors).
 *
 * @dev    Solidity 0.8.20. All amounts in USDC (6 decimals).
 */
contract FeeDistributor {
    using SafeERC20 for IERC20;

    // ─────────────────────────────────────────────
    // Errors
    // ─────────────────────────────────────────────
    error Unauthorized();
    error ZeroAddress();
    error ZeroAmount();
    error InvalidSplit();

    // ─────────────────────────────────────────────
    // Events
    // ─────────────────────────────────────────────
    event FeeDistributed(
        uint256 indexed tradeId,
        uint256 totalFee,
        uint256 investorShare,
        uint256 protocolShare,
        uint256 reserveShare
    );

    event SplitUpdated(
        uint256 investorBps,
        uint256 protocolBps,
        uint256 reserveBps
    );

    event TreasuryUpdated(address indexed oldTreasury, address indexed newTreasury);
    event ReserveFundUpdated(address indexed oldReserve, address indexed newReserve);

    // ─────────────────────────────────────────────
    // State
    // ─────────────────────────────────────────────

    /// @notice Contract owner
    address public owner;

    /// @notice USDC token
    IERC20 public usdc;

    /// @notice Financing pool — investor yield is sent here
    address public financingPool;

    /// @notice Voice Ledger protocol treasury
    address public treasury;

    /// @notice Reserve fund for default coverage
    address public reserveFund;

    /// @notice Authorised caller (TradeEscrow)
    address public escrow;

    /// @notice Fee split in basis points (must sum to 10000)
    uint256 public investorBps;
    uint256 public protocolBps;
    uint256 public reserveBps;

    /// @notice Cumulative totals (for analytics / dashboards)
    uint256 public totalDistributed;
    uint256 public totalToInvestors;
    uint256 public totalToProtocol;
    uint256 public totalToReserve;

    // ─────────────────────────────────────────────
    // Constants
    // ─────────────────────────────────────────────
    uint256 private constant BPS = 10_000;

    // ─────────────────────────────────────────────
    // Modifiers
    // ─────────────────────────────────────────────
    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    modifier onlyEscrow() {
        if (msg.sender != escrow) revert Unauthorized();
        _;
    }

    // ─────────────────────────────────────────────
    // Constructor
    // ─────────────────────────────────────────────

    /**
     * @param _usdc           USDC token address
     * @param _financingPool  FinancingPool address (investor yield destination)
     * @param _treasury       Voice Ledger protocol treasury
     * @param _reserveFund    Reserve fund address for default coverage
     */
    constructor(
        address _usdc,
        address _financingPool,
        address _treasury,
        address _reserveFund
    ) {
        if (_usdc == address(0) || _financingPool == address(0) 
            || _treasury == address(0) || _reserveFund == address(0))
            revert ZeroAddress();

        owner = msg.sender;
        usdc = IERC20(_usdc);
        financingPool = _financingPool;
        treasury = _treasury;
        reserveFund = _reserveFund;

        // Default split: 62.5% / 25% / 12.5% of total fee
        investorBps = 6_250;
        protocolBps = 2_500;
        reserveBps  = 1_250;
    }

    // ─────────────────────────────────────────────
    // Core
    // ─────────────────────────────────────────────

    /**
     * @notice Distribute a trade fee that has already been transferred to this contract.
     * @dev    Called by TradeEscrow after sending USDC here.
     * @param  tradeId   Trade identifier for event tracking
     * @param  totalFee  Total USDC fee amount (must match balance received)
     */
    function distributeFee(uint256 tradeId, uint256 totalFee) external onlyEscrow {
        if (totalFee == 0) revert ZeroAmount();

        uint256 toInvestors = (totalFee * investorBps) / BPS;
        uint256 toProtocol  = (totalFee * protocolBps) / BPS;
        uint256 toReserve   = totalFee - toInvestors - toProtocol; // remainder to avoid dust

        // Transfer investor yield to pool (becomes part of totalAssets, increases share price)
        if (toInvestors > 0) {
            usdc.safeTransfer(financingPool, toInvestors);
        }

        // Transfer protocol revenue to treasury
        if (toProtocol > 0) {
            usdc.safeTransfer(treasury, toProtocol);
        }

        // Transfer to reserve fund
        if (toReserve > 0) {
            usdc.safeTransfer(reserveFund, toReserve);
        }

        // Update analytics
        totalDistributed += totalFee;
        totalToInvestors += toInvestors;
        totalToProtocol  += toProtocol;
        totalToReserve   += toReserve;

        emit FeeDistributed(tradeId, totalFee, toInvestors, toProtocol, toReserve);
    }

    // ─────────────────────────────────────────────
    // Admin
    // ─────────────────────────────────────────────

    /**
     * @notice Set the authorised escrow contract.
     */
    function setEscrow(address _escrow) external onlyOwner {
        escrow = _escrow;
    }

    /**
     * @notice Update the fee split. Must sum to 10000 bps.
     */
    function setSplit(uint256 _investorBps, uint256 _protocolBps, uint256 _reserveBps) external onlyOwner {
        if (_investorBps + _protocolBps + _reserveBps != BPS) revert InvalidSplit();
        investorBps = _investorBps;
        protocolBps = _protocolBps;
        reserveBps  = _reserveBps;
        emit SplitUpdated(_investorBps, _protocolBps, _reserveBps);
    }

    /**
     * @notice Update the protocol treasury address.
     */
    function setTreasury(address _treasury) external onlyOwner {
        if (_treasury == address(0)) revert ZeroAddress();
        emit TreasuryUpdated(treasury, _treasury);
        treasury = _treasury;
    }

    /**
     * @notice Update the reserve fund address.
     */
    function setReserveFund(address _reserveFund) external onlyOwner {
        if (_reserveFund == address(0)) revert ZeroAddress();
        emit ReserveFundUpdated(reserveFund, _reserveFund);
        reserveFund = _reserveFund;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        owner = newOwner;
    }
}
