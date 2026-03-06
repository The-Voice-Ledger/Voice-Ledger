#!/usr/bin/env python3
"""
DeFi Financing Pool Manager

Manages interactions with the on-chain financing pool contracts:
  - FinancingPool (ERC-4626 vault): deposit / redeem / stats
  - TradeEscrow: requestAdvance / confirmDelivery / trade status
  - FeeDistributor: read-only analytics

Follows the same pattern as token_manager.py and blockchain_anchor.py.

Created: March 5, 2026
"""

import os
import sys
import json
import logging
from typing import Optional, Dict, Any
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

logger = logging.getLogger(__name__)


def _load_abi(name: str) -> list:
    """Load a contract ABI from blockchain_abis/."""
    abi_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "blockchain_abis",
        f"{name}.json",
    )
    with open(abi_path, "r") as f:
        data = json.load(f)
        return data if isinstance(data, list) else data.get("abi", data)


class FinancingManager:
    """Manages the DeFi financing pool, escrow, and fee distributor."""

    def __init__(self):
        self.rpc_url = os.getenv("BASE_SEPOLIA_RPC_URL")
        self.private_key = os.getenv("PRIVATE_KEY_SEP")
        self.pool_address = os.getenv("FINANCING_POOL_ADDRESS")
        self.escrow_address = os.getenv("TRADE_ESCROW_ADDRESS")
        self.distributor_address = os.getenv("FEE_DISTRIBUTOR_ADDRESS")
        self.usdc_address = os.getenv("USDC_ADDRESS")

        missing = [
            k
            for k, v in {
                "BASE_SEPOLIA_RPC_URL": self.rpc_url,
                "PRIVATE_KEY_SEP": self.private_key,
                "FINANCING_POOL_ADDRESS": self.pool_address,
                "TRADE_ESCROW_ADDRESS": self.escrow_address,
                "FEE_DISTRIBUTOR_ADDRESS": self.distributor_address,
                "USDC_ADDRESS": self.usdc_address,
            }.items()
            if not v
        ]
        if missing:
            raise ValueError(f"Missing env vars: {', '.join(missing)}")

        # Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to {self.rpc_url}")

        self.account = Account.from_key(self.private_key)

        # Contracts
        self.pool = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.pool_address),
            abi=_load_abi("FinancingPool"),
        )
        self.escrow = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.escrow_address),
            abi=_load_abi("TradeEscrow"),
        )
        self.distributor = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.distributor_address),
            abi=_load_abi("FeeDistributor"),
        )
        self.usdc = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.usdc_address),
            abi=_load_abi("ERC20"),
        )

        logger.info(
            "FinancingManager initialised — pool=%s escrow=%s chain=%d",
            self.pool_address,
            self.escrow_address,
            self.w3.eth.chain_id,
        )

    # ─────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────

    def _send_tx(self, tx_func, gas: int = 500_000) -> Optional[str]:
        """Build, sign, broadcast a transaction and return its hash."""
        try:
            nonce = self.w3.eth.get_transaction_count(
                self.account.address, "pending"
            )
            base_fee = self.w3.eth.gas_price
            tx = tx_func.build_transaction(
                {
                    "from": self.account.address,
                    "chainId": self.w3.eth.chain_id,
                    "gas": gas,
                    "maxFeePerGas": int(base_fee * 2),
                    "maxPriorityFeePerGas": self.w3.to_wei(0.001, "gwei"),
                    "nonce": nonce,
                }
            )
            signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            if receipt["status"] != 1:
                logger.error("Tx reverted: %s", tx_hash.hex())
                return None
            logger.info("Tx confirmed: %s (gas=%d)", tx_hash.hex(), receipt["gasUsed"])
            return tx_hash.hex()
        except Exception as e:
            logger.exception("Transaction failed: %s", e)
            return None

    # ─────────────────────────────────────────
    # Pool — read
    # ─────────────────────────────────────────

    def pool_stats(self) -> Dict[str, Any]:
        """Return current pool metrics (all read-only calls)."""
        total_assets = self.pool.functions.totalAssets().call()
        total_advanced = self.pool.functions.totalAdvanced().call()
        available = self.pool.functions.availableForAdvance().call()
        utilisation = self.pool.functions.utilisationBps().call()
        cumulative_fees = self.pool.functions.cumulativeTradeFees().call()
        total_supply = self.pool.functions.totalSupply().call()

        return {
            "total_assets_usdc": total_assets / 1e6,
            "total_advanced_usdc": total_advanced / 1e6,
            "available_for_advance_usdc": available / 1e6,
            "utilisation_pct": utilisation / 100,  # bps → %
            "cumulative_fees_usdc": cumulative_fees / 1e6,
            "total_shares": total_supply / 1e6,
            "share_price_usdc": (
                (total_assets / total_supply) if total_supply > 0 else 1.0
            ),
        }

    def investor_balance(self, address: str) -> Dict[str, Any]:
        """Return an investor's vlUSDC shares and redeemable USDC."""
        addr = Web3.to_checksum_address(address)
        shares = self.pool.functions.balanceOf(addr).call()
        redeemable = self.pool.functions.previewRedeem(shares).call() if shares > 0 else 0
        return {
            "address": address,
            "shares": shares / 1e6,
            "redeemable_usdc": redeemable / 1e6,
        }

    # ─────────────────────────────────────────
    # Pool — write (investor actions)
    # ─────────────────────────────────────────

    def deposit(self, amount_usdc: float, receiver: str) -> Optional[str]:
        """
        Deposit USDC into the pool on behalf of `receiver`.

        NOTE: The caller's wallet (PRIVATE_KEY_SEP) must hold the USDC
        and have approved the pool contract beforehand.
        """
        amount = int(amount_usdc * 1e6)
        receiver_addr = Web3.to_checksum_address(receiver)
        return self._send_tx(
            self.pool.functions.deposit(amount, receiver_addr),
            gas=300_000,
        )

    def redeem(self, shares: float, receiver: str, owner: str) -> Optional[str]:
        """Redeem vlUSDC shares for USDC."""
        share_amount = int(shares * 1e6)
        return self._send_tx(
            self.pool.functions.redeem(
                share_amount,
                Web3.to_checksum_address(receiver),
                Web3.to_checksum_address(owner),
            ),
            gas=300_000,
        )

    # ─────────────────────────────────────────
    # Escrow — read
    # ─────────────────────────────────────────

    def get_trade(self, trade_id: int) -> Optional[Dict[str, Any]]:
        """Fetch trade details by ID."""
        try:
            t = self.escrow.functions.getTrade(trade_id).call()
            return {
                "trade_id": trade_id,
                "token_id": t[0],
                "token_amount": t[1],
                "seller": t[2],
                "buyer": t[3],
                "agreed_price_usdc": t[4] / 1e6,
                "advance_amount_usdc": t[5] / 1e6,
                "fee_bps": t[6],
                "fee_amount_usdc": t[7] / 1e6,
                "shipment_hash": "0x" + t[8].hex(),
                "farm_id": t[9],
                "created_at": t[10],
                "settled_at": t[11],
                "deadline": t[12],
                "status": ["None", "Active", "Settled", "Defaulted", "Cancelled"][t[13]],
            }
        except Exception as e:
            logger.error("getTrade(%d) failed: %s", trade_id, e)
            return None

    def is_token_pledged(self, token_id: int) -> bool:
        """Check if an ERC-1155 token is currently locked as collateral."""
        return self.escrow.functions.isTokenPledged(token_id).call()

    # ─────────────────────────────────────────
    # Escrow — write
    # ─────────────────────────────────────────

    def request_advance(
        self,
        token_id: int,
        token_amount: int,
        buyer: str,
        agreed_price_usdc: float,
        shipment_hash: str,
        farm_id: str,
    ) -> Optional[str]:
        """
        Seller requests an advance.  Token must be approved to escrow.

        Returns tx hash or None.
        """
        price = int(agreed_price_usdc * 1e6)
        shipment_bytes = Web3.to_bytes(hexstr=shipment_hash)
        return self._send_tx(
            self.escrow.functions.requestAdvance(
                token_id,
                token_amount,
                Web3.to_checksum_address(buyer),
                price,
                shipment_bytes,
                farm_id,
            ),
            gas=800_000,
        )

    def confirm_delivery(self, trade_id: int) -> Optional[str]:
        """
        Buyer confirms delivery and repays.  Buyer must have approved
        USDC to the escrow contract.

        Returns tx hash or None.
        """
        return self._send_tx(
            self.escrow.functions.confirmDelivery(trade_id),
            gas=600_000,
        )

    def cancel_trade(self, trade_id: int) -> Optional[str]:
        """Cancel a trade (seller returns advance, gets token back)."""
        return self._send_tx(
            self.escrow.functions.cancelTrade(trade_id),
            gas=500_000,
        )

    def mark_default(self, trade_id: int) -> Optional[str]:
        """Mark an overdue trade as defaulted (anyone can call)."""
        return self._send_tx(
            self.escrow.functions.markDefault(trade_id),
            gas=400_000,
        )

    # ─────────────────────────────────────────
    # Fee distributor — read
    # ─────────────────────────────────────────

    def fee_stats(self) -> Dict[str, Any]:
        """Cumulative fee distribution analytics."""
        return {
            "total_distributed_usdc": self.distributor.functions.totalDistributed().call() / 1e6,
            "total_to_investors_usdc": self.distributor.functions.totalToInvestors().call() / 1e6,
            "total_to_protocol_usdc": self.distributor.functions.totalToProtocol().call() / 1e6,
            "total_to_reserve_usdc": self.distributor.functions.totalToReserve().call() / 1e6,
            "investor_bps": self.distributor.functions.investorBps().call(),
            "protocol_bps": self.distributor.functions.protocolBps().call(),
            "reserve_bps": self.distributor.functions.reserveBps().call(),
        }


# ─────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────

_manager: Optional[FinancingManager] = None


def get_financing_manager() -> FinancingManager:
    """Return (or create) the singleton FinancingManager."""
    global _manager
    if _manager is None:
        _manager = FinancingManager()
    return _manager


# ─────────────────────────────────────────
# CLI smoke test
# ─────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mgr = get_financing_manager()
    stats = mgr.pool_stats()
    print("\n=== Pool Stats ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    fees = mgr.fee_stats()
    print("\n=== Fee Stats ===")
    for k, v in fees.items():
        print(f"  {k}: {v}")
