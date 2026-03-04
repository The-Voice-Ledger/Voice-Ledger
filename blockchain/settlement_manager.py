"""
Settlement Manager — Record off-chain bank-transfer settlements on Base Sepolia.

Two settlement legs are supported:
  1. **Buyer settlement** — buyer pays into WAGA's European bank account.
  2. **Cooperative payout** — WAGA forwards funds to the Ethiopian cooperative.

Both legs call ``SettlementContract.settleCommissioning()`` with different
settlement-ID ranges so they never collide:

  ┌────────────────────────┬──────────────────────────────────┐
  │ Range                  │ Meaning                          │
  ├────────────────────────┼──────────────────────────────────┤
  │    acceptance_id       │ Buyer payment (RFQ acceptance)   │
  │  + 1 000 000 000       │ Coop payout  (RFQ acceptance)    │
  │  + 2 000 000 000       │ Buyer payment (pool commitment)  │
  │  + 3 000 000 000       │ Coop payout  (pool commitment)   │
  └────────────────────────┴──────────────────────────────────┘

Environment variables required:
  BASE_SEPOLIA_RPC_URL
  PRIVATE_KEY_SEP
  SETTLEMENT_CONTRACT_ADDRESS
"""

import json
import logging
import os
import time
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account

load_dotenv()

logger = logging.getLogger(__name__)

# ID-range offsets
_BUYER_ACCEPTANCE_OFFSET = 0
_COOP_ACCEPTANCE_OFFSET = 1_000_000_000
_BUYER_COMMITMENT_OFFSET = 2_000_000_000
_COOP_COMMITMENT_OFFSET = 3_000_000_000


class SettlementManager:
    """Interact with the deployed SettlementContract on Base Sepolia."""

    def __init__(self):
        self.rpc_url = os.getenv("BASE_SEPOLIA_RPC_URL")
        self.private_key = os.getenv("PRIVATE_KEY_SEP")
        self.contract_address = os.getenv("SETTLEMENT_CONTRACT_ADDRESS")

        if not all([self.rpc_url, self.private_key, self.contract_address]):
            raise ValueError(
                "Missing env vars: BASE_SEPOLIA_RPC_URL, PRIVATE_KEY_SEP, "
                "SETTLEMENT_CONTRACT_ADDRESS"
            )

        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot reach {self.rpc_url}")

        self.account = Account.from_key(self.private_key)

        abi_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "blockchain_abis",
            "SettlementContract.json",
        )
        with open(abi_path, "r") as f:
            abi_json = json.load(f)
            abi = abi_json.get("abi", abi_json)

        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.contract_address), abi=abi
        )
        logger.info(
            "SettlementManager ready  chain=%s  account=%s  contract=%s",
            self.w3.eth.chain_id,
            self.account.address,
            self.contract_address,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_settle_tx(
        self,
        settlement_id: int,
        recipient_address: str,
        amount_cents: int,
        decimals: int = 2,
        currency_code: str = "USD",
        payment_token: str = "0x0000000000000000000000000000000000000000",
    ) -> Dict[str, Any]:
        """Build, sign, send ``settleCommissioning`` and wait for receipt."""
        recipient = Web3.to_checksum_address(recipient_address)
        token = Web3.to_checksum_address(payment_token)

        nonce = self.w3.eth.get_transaction_count(self.account.address)

        fn = self.contract.functions.settleCommissioning(
            settlement_id, recipient, amount_cents, decimals, currency_code, token
        )
        gas_estimate = fn.estimate_gas({"from": self.account.address})

        tx = fn.build_transaction(
            {
                "from": self.account.address,
                "nonce": nonce,
                "gas": int(gas_estimate * 1.3),
                "maxFeePerGas": self.w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": self.w3.to_wei(0.001, "gwei"),
                "chainId": self.w3.eth.chain_id,
            }
        )

        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash_hex = tx_hash.hex()

        # Wait up to 60 s for confirmation
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        result = {
            "tx_hash": tx_hash_hex,
            "block_number": receipt["blockNumber"],
            "gas_used": receipt["gasUsed"],
            "timestamp": int(time.time()),
            "confirmed": receipt["status"] == 1,
            "settlement_id": settlement_id,
        }
        logger.info("Settlement TX %s  block=%s  confirmed=%s",
                     tx_hash_hex, result["block_number"], result["confirmed"])
        return result

    # ------------------------------------------------------------------
    # Public API — buyer settlements
    # ------------------------------------------------------------------

    def record_settlement(
        self,
        acceptance_id: int,
        recipient_address: str,
        amount_usd: float,
        payment_method: str = "BANK_TRANSFER",
    ) -> Dict[str, Any]:
        """
        Record a buyer-to-WAGA settlement for an **RFQ acceptance**.

        Called when the buyer confirms a bank transfer into the European
        holding account.  The on-chain record is permanent proof of payment.
        """
        settlement_id = acceptance_id + _BUYER_ACCEPTANCE_OFFSET
        amount_cents = int(round(amount_usd * 100))
        result = self._send_settle_tx(
            settlement_id=settlement_id,
            recipient_address=recipient_address,
            amount_cents=amount_cents,
            currency_code="USD",
        )
        result["payment_method"] = payment_method
        return result

    def record_commitment_settlement(
        self,
        commitment_id: int,
        recipient_address: str,
        amount_usd: float,
        payment_method: str = "BANK_TRANSFER",
    ) -> Dict[str, Any]:
        """
        Record a buyer-to-WAGA settlement for a **pool commitment**.
        """
        settlement_id = commitment_id + _BUYER_COMMITMENT_OFFSET
        amount_cents = int(round(amount_usd * 100))
        result = self._send_settle_tx(
            settlement_id=settlement_id,
            recipient_address=recipient_address,
            amount_cents=amount_cents,
            currency_code="USD",
        )
        result["payment_method"] = payment_method
        return result

    # ------------------------------------------------------------------
    # Public API — cooperative payouts
    # ------------------------------------------------------------------

    def record_cooperative_payout_for_acceptance(
        self,
        acceptance_id: int,
        recipient_address: str,
        amount_usd: float,
    ) -> Dict[str, Any]:
        """
        Record a WAGA-to-cooperative payout for an **RFQ acceptance**.

        Called when WAGA transfers the buyer's funds from the European bank
        to the cooperative's Ethiopian bank account.
        """
        settlement_id = acceptance_id + _COOP_ACCEPTANCE_OFFSET
        amount_cents = int(round(amount_usd * 100))
        return self._send_settle_tx(
            settlement_id=settlement_id,
            recipient_address=recipient_address,
            amount_cents=amount_cents,
            currency_code="USD",
        )

    def record_cooperative_payout_for_commitment(
        self,
        commitment_id: int,
        recipient_address: str,
        amount_usd: float,
    ) -> Dict[str, Any]:
        """
        Record a WAGA-to-cooperative payout for a **pool commitment**.
        """
        settlement_id = commitment_id + _COOP_COMMITMENT_OFFSET
        amount_cents = int(round(amount_usd * 100))
        return self._send_settle_tx(
            settlement_id=settlement_id,
            recipient_address=recipient_address,
            amount_cents=amount_cents,
            currency_code="USD",
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def is_settled(self, settlement_id: int) -> bool:
        """Check if a given settlement ID has been recorded on-chain."""
        return self.contract.functions.isSettled(settlement_id).call()

    def get_settlement_info(self, settlement_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve on-chain settlement info, or None if not yet settled."""
        try:
            info = self.contract.functions.getSettlement(settlement_id).call()
            return {
                "recipient": info[0],
                "amount": info[1],
                "decimals": info[2],
                "currency_code": info[3],
                "payment_token": info[4],
                "settled_at": info[5],
                "settled": info[6],
            }
        except Exception:
            return None

    def check_buyer_settlement(
        self, record_id: int, record_type: str = "acceptance"
    ) -> Optional[Dict[str, Any]]:
        """
        Check buyer settlement status for an acceptance or commitment.

        Args:
            record_id: RFQAcceptance.id or BuyerCommitment.id
            record_type: "acceptance" or "commitment"
        """
        offset = (
            _BUYER_ACCEPTANCE_OFFSET
            if record_type == "acceptance"
            else _BUYER_COMMITMENT_OFFSET
        )
        return self.get_settlement_info(record_id + offset)

    def check_coop_payout(
        self, record_id: int, record_type: str = "acceptance"
    ) -> Optional[Dict[str, Any]]:
        """Check cooperative payout status on-chain."""
        offset = (
            _COOP_ACCEPTANCE_OFFSET
            if record_type == "acceptance"
            else _COOP_COMMITMENT_OFFSET
        )
        return self.get_settlement_info(record_id + offset)
