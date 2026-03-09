#!/usr/bin/env python3
"""
Chainlink CRE Client - Python interface for the Voice Ledger CRE workflow.

Provides three capabilities:

  1. Read DON-attested provenance metrics from ProvenanceDataReceiver
  2. Read DON-attested deforestation results from ProvenanceDataReceiver
  3. Request new deforestation attestation via CRE HTTP trigger

In production the HTTP trigger request goes to the DON gateway URL.
In simulation mode (no DON gateway set) the client calls the local
provenance API, ABI-encodes the result, and writes it directly to
ProvenanceDataReceiver as the trusted forwarder - exercising the full
smart-contract path without requiring a live DON.

Environment variables:
    BASE_SEPOLIA_RPC_URL           - RPC endpoint (required)
    PRIVATE_KEY_SEP                - Forwarder wallet private key (required)
    PROVENANCE_RECEIVER_ADDRESS    - ProvenanceDataReceiver contract address
    CRE_DON_GATEWAY_URL            - DON HTTP trigger gateway (optional)
    CRE_API_BASE_URL               - Voice Ledger provenance API base URL

Created: February 2026
"""

import os
import sys
import json
import time
import logging
import requests
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

# Add parent to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────

@dataclass
class ProvenanceMetrics:
    """DON-attested provenance metrics from ProvenanceDataReceiver."""
    total_farmers: int
    total_batches: int
    verified_batches: int
    total_quantity_kg: int
    eudr_compliant_percent: int
    batches_anchored: int
    last_updated: int
    exists: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DeforestationAttestation:
    """DON-attested deforestation result from ProvenanceDataReceiver."""
    farm_id: str
    latitude: float         # degrees (unscaled)
    longitude: float        # degrees (unscaled)
    risk_level: int         # 0=LOW 1=MEDIUM 2=HIGH 3=UNKNOWN
    eudr_compliant: bool
    tree_loss_hectares: float  # unscaled
    timestamp: int
    exists: bool

    @property
    def risk_label(self) -> str:
        return {0: "LOW", 1: "MEDIUM", 2: "HIGH", 3: "UNKNOWN"}.get(
            self.risk_level, "UNKNOWN"
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["risk_label"] = self.risk_label
        return d


# ─────────────────────────────────────────────────────────
# CRE Client
# ─────────────────────────────────────────────────────────

class CREClient:
    """
    Python client for the Voice Ledger × Chainlink CRE integration.

    Reads DON-attested data from ProvenanceDataReceiver and can
    trigger new deforestation attestations via the CRE HTTP trigger.
    """

    def __init__(self):
        """Initialise Web3 connection and load ProvenanceDataReceiver ABI."""
        self.rpc_url = os.getenv("BASE_SEPOLIA_RPC_URL")
        self.private_key = os.getenv("PRIVATE_KEY_SEP")
        self.receiver_address = os.getenv("PROVENANCE_RECEIVER_ADDRESS")
        self.don_gateway_url = os.getenv("CRE_DON_GATEWAY_URL")  # optional
        self.api_base_url = os.getenv(
            "CRE_API_BASE_URL", "http://localhost:8100"
        )

        if not self.rpc_url:
            raise ValueError("Missing BASE_SEPOLIA_RPC_URL")

        # Web3 setup
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to {self.rpc_url}")

        # Account (for simulation-mode writes)
        if self.private_key:
            self.account = Account.from_key(self.private_key)
        else:
            self.account = None

        # Load ABI
        abi_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "blockchain_abis",
            "ProvenanceDataReceiver.json",
        )
        if not os.path.exists(abi_path):
            raise FileNotFoundError(f"ABI not found: {abi_path}")

        with open(abi_path) as f:
            abi_data = json.load(f)

        self.abi = abi_data.get("abi", abi_data)

        # Contract (may be None if not deployed yet)
        if self.receiver_address and self.receiver_address != "0x" + "0" * 40:
            self.contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.receiver_address),
                abi=self.abi,
            )
            self._deployed = True
            logger.info(
                "CREClient connected to ProvenanceDataReceiver at %s",
                self.receiver_address,
            )
        else:
            self.contract = None
            self._deployed = False
            logger.warning(
                "ProvenanceDataReceiver not deployed - reads will return "
                "defaults, simulation writes disabled"
            )

    # ─────────────────────────────────────────────
    # Read: Provenance metrics
    # ─────────────────────────────────────────────

    def get_provenance_metrics(self) -> ProvenanceMetrics:
        """
        Read the latest DON-attested provenance metrics from chain.

        Returns:
            ProvenanceMetrics with aggregated supply-chain stats.
        """
        if not self._deployed:
            return ProvenanceMetrics(
                total_farmers=0, total_batches=0, verified_batches=0,
                total_quantity_kg=0, eudr_compliant_percent=0,
                batches_anchored=0, last_updated=0, exists=False,
            )

        try:
            result = self.contract.functions.getProvenanceMetrics().call()
            # Result is a tuple matching ProvenanceReport struct
            return ProvenanceMetrics(
                total_farmers=result[0],
                total_batches=result[1],
                verified_batches=result[2],
                total_quantity_kg=result[3],
                eudr_compliant_percent=result[4],
                batches_anchored=result[5],
                last_updated=result[6],
                exists=result[7],
            )
        except Exception as e:
            logger.error("Failed to read provenance metrics: %s", e)
            return ProvenanceMetrics(
                total_farmers=0, total_batches=0, verified_batches=0,
                total_quantity_kg=0, eudr_compliant_percent=0,
                batches_anchored=0, last_updated=0, exists=False,
            )

    # ─────────────────────────────────────────────
    # Read: Deforestation attestation
    # ─────────────────────────────────────────────

    def get_deforestation_attestation(
        self, farm_id: str
    ) -> DeforestationAttestation:
        """
        Read a DON-attested deforestation result for a farm.

        Args:
            farm_id: Farmer identifier (e.g. "FARMER-001")

        Returns:
            DeforestationAttestation from the chain.
        """
        if not self._deployed:
            return DeforestationAttestation(
                farm_id=farm_id, latitude=0, longitude=0, risk_level=3,
                eudr_compliant=False, tree_loss_hectares=0, timestamp=0,
                exists=False,
            )

        try:
            result = self.contract.functions.getDeforestationAttestation(
                farm_id
            ).call()
            return DeforestationAttestation(
                farm_id=result[0],
                latitude=result[1] / 1e6,      # unscale
                longitude=result[2] / 1e6,      # unscale
                risk_level=result[3],
                eudr_compliant=result[4],
                tree_loss_hectares=result[5] / 1e4,  # unscale
                timestamp=result[6],
                exists=result[7],
            )
        except Exception as e:
            logger.warning(
                "No attestation for farm %s: %s", farm_id, e
            )
            return DeforestationAttestation(
                farm_id=farm_id, latitude=0, longitude=0, risk_level=3,
                eudr_compliant=False, tree_loss_hectares=0, timestamp=0,
                exists=False,
            )

    def is_farm_compliant(self, farm_id: str) -> bool:
        """Quick check: has the DON attested this farm as EUDR compliant?"""
        if not self._deployed:
            return False
        try:
            return self.contract.functions.isFarmCompliant(farm_id).call()
        except Exception:
            return False

    # ─────────────────────────────────────────────
    # Write: Request deforestation attestation
    # ─────────────────────────────────────────────

    def request_deforestation_attestation(
        self, farm_id: str
    ) -> Dict[str, Any]:
        """
        Request a DON-attested deforestation check for a farm.

        In production: POSTs to the CRE DON gateway (HTTP trigger).
        In simulation: Calls the local provenance API, ABI-encodes the
        result, and submits it to ProvenanceDataReceiver.onReport()
        as the trusted forwarder - exercising the full contract path.

        Args:
            farm_id: Farmer identifier

        Returns:
            Dict with attestation result, tx_hash (if written), and mode.
        """
        if self.don_gateway_url:
            return self._request_via_don(farm_id)
        else:
            return self._request_via_simulation(farm_id)

    def _request_via_don(self, farm_id: str) -> Dict[str, Any]:
        """POST to the live CRE DON HTTP trigger gateway."""
        try:
            resp = requests.post(
                self.don_gateway_url,
                json={"farm_id": farm_id},
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(
                "DON attestation requested for %s - %s", farm_id, result
            )
            return {
                "mode": "don",
                "farm_id": farm_id,
                "status": "requested",
                "don_response": result,
            }
        except Exception as e:
            logger.error("DON request failed for %s: %s", farm_id, e)
            return {
                "mode": "don",
                "farm_id": farm_id,
                "status": "failed",
                "error": str(e),
            }

    def _request_via_simulation(self, farm_id: str) -> Dict[str, Any]:
        """
        Simulation mode: call local API → ABI-encode → submit on-chain.

        This exercises the entire smart-contract path without a live DON.
        The forwarder wallet signs the transaction, simulating what the
        DON would do after reaching consensus.
        """
        # Step 1: Fetch deforestation data from local provenance API
        api_url = f"{self.api_base_url}/api/deforestation/{farm_id}"
        try:
            resp = requests.get(api_url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError:
            # API not running - generate mock data from database
            logger.warning(
                "Provenance API not reachable - using database fallback"
            )
            data = self._deforestation_from_database(farm_id)
            if not data:
                return {
                    "mode": "simulation",
                    "farm_id": farm_id,
                    "status": "failed",
                    "error": "Provenance API unreachable and farm not in DB",
                }
        except Exception as e:
            logger.error("API call failed for %s: %s", farm_id, e)
            return {
                "mode": "simulation",
                "farm_id": farm_id,
                "status": "failed",
                "error": str(e),
            }

        # Step 2: ABI-encode as deforestation attestation report
        # Type prefix 0x02 + abi.encode(string, int64, int64, uint8, bool, uint256, uint256)
        if not self._deployed or not self.account:
            # Can't write to chain, but return the data
            return {
                "mode": "simulation_readonly",
                "farm_id": farm_id,
                "status": "attested_offchain",
                "attestation": data,
            }

        try:
            # Build the type-prefixed report
            report = self._encode_deforestation_report(data)

            # Step 3: Submit to ProvenanceDataReceiver.onReport(bytes)
            tx = self.contract.functions.onReport(report).build_transaction({
                "from": self.account.address,
                "nonce": self.w3.eth.get_transaction_count(
                    self.account.address
                ),
                "gas": 500_000,
                "gasPrice": self.w3.eth.gas_price,
                "chainId": self.w3.eth.chain_id,
            })

            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(
                signed.raw_transaction
            )
            receipt = self.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=60
            )

            tx_hex = tx_hash.hex() if isinstance(tx_hash, bytes) else tx_hash

            logger.info(
                "Simulation attestation written for %s - tx: %s",
                farm_id, tx_hex,
            )

            return {
                "mode": "simulation",
                "farm_id": farm_id,
                "status": "attested_onchain",
                "tx_hash": tx_hex,
                "block_number": receipt.get("blockNumber"),
                "attestation": data,
            }

        except Exception as e:
            logger.error(
                "Simulation write failed for %s: %s", farm_id, e
            )
            return {
                "mode": "simulation",
                "farm_id": farm_id,
                "status": "failed",
                "error": str(e),
                "attestation": data,
            }

    def _encode_deforestation_report(self, data: dict) -> bytes:
        """
        ABI-encode a deforestation attestation with type prefix 0x02.

        Matches the decoding logic in ProvenanceDataReceiver.
        _processDeforestationAttestation().
        """
        farm_id = data.get("farmId", data.get("farm_id", ""))
        latitude = int(data.get("latitude", 0))        # already scaled ×1e6
        longitude = int(data.get("longitude", 0))       # already scaled ×1e6
        risk_code = int(data.get("riskLevelCode", data.get("risk_level", 3)))
        eudr_compliant = bool(data.get("eudrCompliant", False))
        tree_loss = int(
            data.get("treeLossHectaresScaled", data.get("tree_loss_scaled", 0))
        )
        timestamp = int(data.get("timestamp", int(time.time())))

        # ABI-encode the tuple
        encoded_data = self.w3.codec.encode(
            ["string", "int64", "int64", "uint8", "bool", "uint256", "uint256"],
            [farm_id, latitude, longitude, risk_code, eudr_compliant, tree_loss, timestamp],
        )

        # Prepend type prefix 0x02
        return b"\x02" + encoded_data

    def _deforestation_from_database(self, farm_id: str) -> Optional[dict]:
        """
        Fallback: build deforestation payload from database farmer GPS.

        Used when provenance API is not running.
        """
        try:
            from database.connection import get_db
            from database.models import FarmerIdentity

            with get_db() as db:
                farmer = db.query(FarmerIdentity).filter(
                    FarmerIdentity.farmer_id == farm_id
                ).first()

                if not farmer or not farmer.latitude or not farmer.longitude:
                    return None

                # Use farmer's stored deforestation data if available
                risk_code = 0  # LOW by default
                eudr_compliant = True
                tree_loss = 0

                if farmer.deforestation_risk:
                    risk_map = {"low": 0, "medium": 1, "high": 2, "unknown": 3}
                    risk_code = risk_map.get(
                        farmer.deforestation_risk.lower(), 3
                    )
                    eudr_compliant = farmer.deforestation_compliant or False
                    tree_loss = int(
                        (farmer.tree_cover_loss_hectares or 0) * 10000
                    )

                return {
                    "farmId": farm_id,
                    "latitude": int(farmer.latitude * 1e6),
                    "longitude": int(farmer.longitude * 1e6),
                    "riskLevelCode": risk_code,
                    "eudrCompliant": eudr_compliant,
                    "treeLossHectaresScaled": tree_loss,
                    "timestamp": int(time.time()),
                }

        except Exception as e:
            logger.error("Database fallback failed: %s", e)
            return None


# ─────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────

_cre_client: Optional[CREClient] = None


def get_cre_client() -> CREClient:
    """Get or create the module-level CREClient singleton."""
    global _cre_client
    if _cre_client is None:
        _cre_client = CREClient()
    return _cre_client


# ─────────────────────────────────────────────────────────
# Convenience functions
# ─────────────────────────────────────────────────────────

def request_attestation(farm_id: str) -> Dict[str, Any]:
    """Request a DON deforestation attestation (convenience wrapper)."""
    return get_cre_client().request_deforestation_attestation(farm_id)


def read_attestation(farm_id: str) -> DeforestationAttestation:
    """Read a DON attestation from chain (convenience wrapper)."""
    return get_cre_client().get_deforestation_attestation(farm_id)


def read_metrics() -> ProvenanceMetrics:
    """Read DON-attested provenance metrics (convenience wrapper)."""
    return get_cre_client().get_provenance_metrics()


if __name__ == "__main__":
    print("Chainlink CRE Client - Voice Ledger")
    print("=" * 50)

    try:
        client = CREClient()
        print(f"✅ Connected to {client.rpc_url}")
        print(f"   Receiver deployed: {client._deployed}")
        print(f"   DON gateway: {client.don_gateway_url or 'simulation mode'}")

        if client._deployed:
            metrics = client.get_provenance_metrics()
            print(f"\n📊 Provenance Metrics:")
            print(f"   Farmers: {metrics.total_farmers}")
            print(f"   Batches: {metrics.total_batches}")
            print(f"   EUDR Compliant: {metrics.eudr_compliant_percent}%")
    except Exception as e:
        print(f"❌ Error: {e}")
