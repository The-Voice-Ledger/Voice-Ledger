// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ERC4626} from "@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";

/**
 * @title  FinancingPool
 * @notice ERC-4626 yield vault that accepts USDC deposits and funds trade
 *         advances for confirmed coffee shipments.
 *
 *         Investors deposit USDC → receive vlUSDC share tokens.
 *         The escrow contract draws from the pool to advance sellers.
 *         Buyer repayments (principal + fee) flow back, growing total assets.
 *         Investors redeem vlUSDC for USDC + accrued yield at any time
 *         (subject to available liquidity).
 *
 * @dev    Denomination asset: USDC (6 decimals on Base).
 *         Only the authorised TradeEscrow contract may call
 *         `drawFunds` / `returnFunds`.
 */
contract FinancingPool is ERC4626 {
    using SafeERC20 for IERC20;
    using Math for uint256;

    // ─────────────────────────────────────────────
    // Errors
    // ─────────────────────────────────────────────
    error Unauthorized();
    error EscrowNotSet();
    error InsufficientPoolLiquidity(uint256 requested, uint256 available);
    error ZeroAmount();
    error DrawExceedsMaxAdvance(uint256 requested, uint256 maxAllowed);

    // ─────────────────────────────────────────────
    // Events
    // ─────────────────────────────────────────────
    event EscrowUpdated(address indexed oldEscrow, address indexed newEscrow);
    event FundsDrawn(uint256 indexed tradeId, uint256 amount);
    event FundsReturned(uint256 indexed tradeId, uint256 principal, uint256 fee);
    event DefaultWrittenOff(uint256 indexed tradeId, uint256 principal);
    event MaxAdvanceRatioUpdated(uint256 oldRatio, uint256 newRatio);
    event MaxSingleAdvanceUpdated(uint256 oldMax, uint256 newMax);

    // ─────────────────────────────────────────────
    // State
    // ─────────────────────────────────────────────

    /// @notice Contract owner (deployer)
    address public owner;

    /// @notice Authorised TradeEscrow contract
    address public escrow;

    /// @notice Total USDC currently out on active advances
    uint256 public totalAdvanced;

    /// @notice Maximum fraction of pool that can be out on advances (basis points, 10000 = 100%)
    uint256 public maxAdvanceRatioBps;

    /// @notice Maximum single advance size (USDC, 6 decimals). 0 = no cap.
    uint256 public maxSingleAdvance;

    /// @notice Cumulative total trade fees passed through the system (analytics only).
    ///         NOTE: Only the investor share (~62.5%) accrues in the pool;
    ///         the rest goes to protocol treasury and reserve fund.
    uint256 public cumulativeTradeFees;

    /// @notice Cumulative principal written off from buyer defaults
    uint256 public cumulativeDefaulted;

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
        if (escrow == address(0)) revert EscrowNotSet();
        if (msg.sender != escrow) revert Unauthorized();
        _;
    }

    // ─────────────────────────────────────────────
    // Constructor
    // ─────────────────────────────────────────────

    /**
     * @param _usdc  Address of the USDC token on this chain
     */
    constructor(IERC20 _usdc)
        ERC4626(IERC20(_usdc))
        ERC20("Voice Ledger Pool Share", "vlUSDC")
    {
        owner = msg.sender;
        maxAdvanceRatioBps = 8_000; // 80% utilisation cap by default
        maxSingleAdvance = 0;       // no cap initially
    }

    // ─────────────────────────────────────────────
    // Admin
    // ─────────────────────────────────────────────

    /**
     * @notice Set or update the TradeEscrow contract address.
     * @param _escrow  New escrow address
     */
    function setEscrow(address _escrow) external onlyOwner {
        emit EscrowUpdated(escrow, _escrow);
        escrow = _escrow;
    }

    /**
     * @notice Update the maximum advance ratio (basis points).
     * @param _bps  New ratio (e.g. 8000 = 80%)
     */
    function setMaxAdvanceRatio(uint256 _bps) external onlyOwner {
        emit MaxAdvanceRatioUpdated(maxAdvanceRatioBps, _bps);
        maxAdvanceRatioBps = _bps;
    }

    /**
     * @notice Update the maximum single advance cap.
     * @param _max  Max USDC per advance (6 decimals). 0 = no cap.
     */
    function setMaxSingleAdvance(uint256 _max) external onlyOwner {
        emit MaxSingleAdvanceUpdated(maxSingleAdvance, _max);
        maxSingleAdvance = _max;
    }

    // ─────────────────────────────────────────────
    // Escrow interface
    // ─────────────────────────────────────────────

    /**
     * @notice Draw USDC from the pool to fund a seller advance.
     * @dev    Only callable by the authorised TradeEscrow.
     * @param  tradeId   Unique trade identifier (from escrow)
     * @param  amount    USDC amount (6 decimals)
     * @param  recipient Seller address to receive the advance
     */
    function drawFunds(uint256 tradeId, uint256 amount, address recipient) external onlyEscrow {
        if (amount == 0) revert ZeroAmount();

        // Check single-advance cap
        if (maxSingleAdvance > 0 && amount > maxSingleAdvance) {
            revert DrawExceedsMaxAdvance(amount, maxSingleAdvance);
        }

        // Check pool-wide utilisation cap
        uint256 poolTotal = totalAssets();
        uint256 maxAdvanceable = (poolTotal * maxAdvanceRatioBps) / BPS;
        if (totalAdvanced + amount > maxAdvanceable) {
            revert InsufficientPoolLiquidity(amount, maxAdvanceable - totalAdvanced);
        }

        // Check actual USDC balance (belt + suspenders)
        uint256 available = IERC20(asset()).balanceOf(address(this));
        if (amount > available) {
            revert InsufficientPoolLiquidity(amount, available);
        }

        totalAdvanced += amount;

        // Transfer USDC to seller
        IERC20(asset()).safeTransfer(recipient, amount);

        emit FundsDrawn(tradeId, amount);
    }

    /**
     * @notice Return principal + fee to the pool after buyer repayment.
     * @dev    Only callable by the authorised TradeEscrow. The escrow must
     *         have already transferred USDC to this contract before calling.
     * @param  tradeId   Unique trade identifier
     * @param  principal Original advance amount
     * @param  fee       Fee portion (already deducted from buyer payment by escrow)
     */
    function returnFunds(uint256 tradeId, uint256 principal, uint256 fee) external onlyEscrow {
        // Reduce outstanding advances
        totalAdvanced -= principal;
        cumulativeTradeFees += fee;

        emit FundsReturned(tradeId, principal, fee);
    }

    /**
     * @notice Write off a defaulted advance — reduces totalAdvanced so the
     *         pool's totalAssets accurately reflects the loss.
     * @dev    Only callable by the authorised TradeEscrow on markDefault().
     * @param  tradeId   Defaulted trade identifier
     * @param  principal Original advance amount that will not be recovered
     */
    function writeOffDefault(uint256 tradeId, uint256 principal) external onlyEscrow {
        totalAdvanced -= principal;
        cumulativeDefaulted += principal;
        emit DefaultWrittenOff(tradeId, principal);
    }

    // ─────────────────────────────────────────────
    // View helpers
    // ─────────────────────────────────────────────

    /**
     * @notice Available USDC that can still be drawn for new advances.
     */
    function availableForAdvance() external view returns (uint256) {
        uint256 poolTotal = totalAssets();
        uint256 maxAdvanceable = (poolTotal * maxAdvanceRatioBps) / BPS;
        if (totalAdvanced >= maxAdvanceable) return 0;

        uint256 capRoom = maxAdvanceable - totalAdvanced;
        uint256 cashOnHand = IERC20(asset()).balanceOf(address(this));
        return capRoom < cashOnHand ? capRoom : cashOnHand;
    }

    /**
     * @notice Current pool utilisation in basis points.
     */
    function utilisationBps() external view returns (uint256) {
        uint256 poolTotal = totalAssets();
        if (poolTotal == 0) return 0;
        return (totalAdvanced * BPS) / poolTotal;
    }

    /**
     * @notice Override totalAssets to include USDC currently out on advances.
     * @dev    Without this, ERC-4626 would under-report the pool's true value
     *         because USDC held by borrowers is not in the contract's balance.
     *         totalAssets = USDC balance + outstanding advances
     */
    function totalAssets() public view override returns (uint256) {
        return IERC20(asset()).balanceOf(address(this)) + totalAdvanced;
    }

    // ─────────────────────────────────────────────
    // Ownership
    // ─────────────────────────────────────────────

    function transferOwnership(address newOwner) external onlyOwner {
        owner = newOwner;
    }
}
