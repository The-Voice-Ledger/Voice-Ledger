// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title  ProvenanceDataReceiver
 * @notice Receives DON-signed reports from the Voice Ledger CRE workflow.
 *
 *         Two report types:
 *           0x01 — Proof of Provenance metrics (from CronTrigger)
 *           0x02 — Deforestation attestation   (from HTTPTrigger)
 *
 *         In production, this contract would inherit from Chainlink's
 *         KeystoneClient to validate DON signatures via the KeystoneRouter.
 *         For the hackathon / simulation, we accept reports from a
 *         trusted forwarder address (set at deploy time).
 *
 * @dev    Designed for Base Sepolia (chain ID 84532).
 *         Solidity 0.8.20 to match existing Voice Ledger contracts.
 */
contract ProvenanceDataReceiver {

    // ─────────────────────────────────────────────
    // Errors
    // ─────────────────────────────────────────────
    error Unauthorized();
    error InvalidReportType(uint8 reportType);
    error FarmNotAttested(string farmId);

    // ─────────────────────────────────────────────
    // Events
    // ─────────────────────────────────────────────
    event ProvenanceUpdated(
        uint256 totalFarmers,
        uint256 totalBatches,
        uint256 eudrCompliantPercent,
        uint256 batchesAnchored,
        uint256 timestamp
    );

    event DeforestationAttested(
        string indexed farmId,
        int64 latitude,
        int64 longitude,
        uint8 riskLevel,
        bool eudrCompliant,
        uint256 treeLossScaled,
        uint256 timestamp
    );

    // ─────────────────────────────────────────────
    // Structs
    // ─────────────────────────────────────────────

    struct ProvenanceReport {
        uint256 totalFarmers;
        uint256 totalBatches;
        uint256 verifiedBatches;
        uint256 totalQuantityKg;
        uint256 eudrCompliantPercent;
        uint256 batchesAnchored;
        uint256 lastUpdated;
        bool    exists;
    }

    struct DeforestationAttestation {
        string  farmId;
        int64   latitude;          // scaled ×1e6
        int64   longitude;         // scaled ×1e6
        uint8   riskLevel;         // 0=LOW 1=MEDIUM 2=HIGH 3=UNKNOWN
        bool    eudrCompliant;
        uint256 treeLossScaled;    // scaled ×1e4 (hectares)
        uint256 timestamp;
        bool    exists;
    }

    // ─────────────────────────────────────────────
    // State
    // ─────────────────────────────────────────────

    /// @notice Address authorised to submit reports (DON forwarder or owner)
    address public forwarder;

    /// @notice Contract owner
    address public owner;

    /// @notice Latest DON-attested provenance metrics
    ProvenanceReport public latestReport;

    /// @notice Historical provenance reports (index → report)
    ProvenanceReport[] public reportHistory;

    /// @notice DON-attested deforestation results keyed by farm ID
    mapping(string => DeforestationAttestation) public attestations;

    /// @notice List of all attested farm IDs (for enumeration)
    string[] public attestedFarms;

    // ─────────────────────────────────────────────
    // Modifiers
    // ─────────────────────────────────────────────

    modifier onlyForwarder() {
        if (msg.sender != forwarder && msg.sender != owner) revert Unauthorized();
        _;
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    // ─────────────────────────────────────────────
    // Constructor
    // ─────────────────────────────────────────────

    /**
     * @param _forwarder  Trusted forwarder that will relay DON reports.
     *                    In production: Chainlink KeystoneRouter address.
     *                    For hackathon: deployer wallet.
     */
    constructor(address _forwarder) {
        owner = msg.sender;
        forwarder = _forwarder;
    }

    // ─────────────────────────────────────────────
    // Report ingestion
    // ─────────────────────────────────────────────

    /**
     * @notice Accept a DON-signed report.  Type byte determines decode path.
     * @param report  ABI-encoded report prefixed with a 1-byte type tag.
     */
    function onReport(bytes calldata report) external onlyForwarder {
        uint8 reportType = uint8(report[0]);

        if (reportType == 0x01) {
            _processProvenanceReport(report[1:]);
        } else if (reportType == 0x02) {
            _processDeforestationAttestation(report[1:]);
        } else {
            revert InvalidReportType(reportType);
        }
    }

    /**
     * @notice Convenience: accept a raw provenance report (no type prefix).
     *         Matches the DataFeedsCache pattern used by CRE writeReport.
     */
    function onReport(bytes calldata /*metadata*/, bytes calldata report) external onlyForwarder {
        // The CRE writeReport sends (metadata, report).
        // We ignore metadata and decode the report directly.
        // Attempt provenance first; fall back to deforestation.
        // Differentiated by length: provenance = 8×32 bytes, deforestation = 7 mixed.
        if (report.length >= 256) {
            _processProvenanceReportRaw(report);
        } else {
            _processDeforestationAttestationRaw(report);
        }
    }

    // ─────────────────────────────────────────────
    // Internal decoders
    // ─────────────────────────────────────────────

    function _processProvenanceReport(bytes calldata data) internal {
        _processProvenanceReportRaw(data);
    }

    function _processProvenanceReportRaw(bytes calldata data) internal {
        (
            /* bytes32 dataId */,
            uint256 totalFarmers,
            uint256 totalBatches,
            uint256 verifiedBatches,
            uint256 totalQuantityKg,
            uint256 eudrCompliantPercent,
            uint256 batchesAnchored,
            uint256 lastUpdated
        ) = abi.decode(data, (bytes32, uint256, uint256, uint256, uint256, uint256, uint256, uint256));

        latestReport = ProvenanceReport({
            totalFarmers: totalFarmers,
            totalBatches: totalBatches,
            verifiedBatches: verifiedBatches,
            totalQuantityKg: totalQuantityKg,
            eudrCompliantPercent: eudrCompliantPercent,
            batchesAnchored: batchesAnchored,
            lastUpdated: lastUpdated,
            exists: true
        });

        reportHistory.push(latestReport);

        emit ProvenanceUpdated(
            totalFarmers,
            totalBatches,
            eudrCompliantPercent,
            batchesAnchored,
            lastUpdated
        );
    }

    function _processDeforestationAttestation(bytes calldata data) internal {
        _processDeforestationAttestationRaw(data);
    }

    function _processDeforestationAttestationRaw(bytes calldata data) internal {
        (
            string memory farmId,
            int64 latitude,
            int64 longitude,
            uint8 riskLevel,
            bool eudrCompliant,
            uint256 treeLossScaled,
            uint256 ts
        ) = abi.decode(data, (string, int64, int64, uint8, bool, uint256, uint256));

        // Track new farms
        if (!attestations[farmId].exists) {
            attestedFarms.push(farmId);
        }

        attestations[farmId] = DeforestationAttestation({
            farmId: farmId,
            latitude: latitude,
            longitude: longitude,
            riskLevel: riskLevel,
            eudrCompliant: eudrCompliant,
            treeLossScaled: treeLossScaled,
            timestamp: ts,
            exists: true
        });

        emit DeforestationAttested(farmId, latitude, longitude, riskLevel, eudrCompliant, treeLossScaled, ts);
    }

    // ─────────────────────────────────────────────
    // Public read functions (for importers / UIs)
    // ─────────────────────────────────────────────

    /**
     * @notice Get the latest DON-attested provenance metrics.
     */
    function getProvenanceMetrics()
        external
        view
        returns (ProvenanceReport memory)
    {
        return latestReport;
    }

    /**
     * @notice Get DON-attested deforestation result for a farm.
     */
    function getDeforestationAttestation(string calldata farmId)
        external
        view
        returns (DeforestationAttestation memory)
    {
        if (!attestations[farmId].exists) revert FarmNotAttested(farmId);
        return attestations[farmId];
    }

    /**
     * @notice Number of historical provenance reports stored.
     */
    function reportCount() external view returns (uint256) {
        return reportHistory.length;
    }

    /**
     * @notice Number of farms with deforestation attestations.
     */
    function attestedFarmCount() external view returns (uint256) {
        return attestedFarms.length;
    }

    /**
     * @notice Quick EUDR compliance check: is this farm compliant?
     */
    function isFarmCompliant(string calldata farmId) external view returns (bool) {
        if (!attestations[farmId].exists) return false;
        return attestations[farmId].eudrCompliant;
    }

    // ─────────────────────────────────────────────
    // Admin
    // ─────────────────────────────────────────────

    /**
     * @notice Update the trusted forwarder address.
     */
    function setForwarder(address _forwarder) external onlyOwner {
        forwarder = _forwarder;
    }
}
