// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";
import {ProvenanceDataReceiver} from "../src/ProvenanceDataReceiver.sol";

contract ProvenanceDataReceiverTest is Test {
    ProvenanceDataReceiver public receiver;
    address public owner;
    address public forwarder;
    address public stranger;

    // Mirror events for expectEmit
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

    function setUp() public {
        owner = makeAddr("owner");
        forwarder = makeAddr("forwarder");
        stranger = makeAddr("stranger");

        vm.prank(owner);
        receiver = new ProvenanceDataReceiver(forwarder);
    }

    // ─────────────────────────────────────────────
    // Constructor
    // ─────────────────────────────────────────────

    function test_Constructor() public view {
        assertEq(receiver.owner(), owner);
        assertEq(receiver.forwarder(), forwarder);
    }

    // ─────────────────────────────────────────────
    // Provenance report (type 0x01)
    // ─────────────────────────────────────────────

    function test_ProvenanceReport_ViaTypeByte() public {
        bytes32 dataId = bytes32("voiceledger-provenance");
        bytes memory payload = abi.encode(
            dataId,
            uint256(23),   // totalFarmers
            uint256(47),   // totalBatches
            uint256(42),   // verifiedBatches
            uint256(12400),// totalQuantityKg
            uint256(94),   // eudrCompliantPercent
            uint256(42),   // batchesAnchored
            uint256(1700000000) // lastUpdated
        );
        bytes memory report = abi.encodePacked(uint8(0x01), payload);

        vm.prank(forwarder);
        vm.expectEmit(false, false, false, true);
        emit ProvenanceUpdated(23, 47, 94, 42, 1700000000);

        receiver.onReport(report);

        ProvenanceDataReceiver.ProvenanceReport memory r = receiver.getProvenanceMetrics();
        assertEq(r.totalFarmers, 23);
        assertEq(r.totalBatches, 47);
        assertEq(r.verifiedBatches, 42);
        assertEq(r.totalQuantityKg, 12400);
        assertEq(r.eudrCompliantPercent, 94);
        assertEq(r.batchesAnchored, 42);
        assertEq(r.lastUpdated, 1700000000);
        assertTrue(r.exists);
        assertEq(receiver.reportCount(), 1);
    }

    function test_ProvenanceReport_ViaMetadataOverload() public {
        bytes32 dataId = bytes32("voiceledger-provenance");
        bytes memory payload = abi.encode(
            dataId,
            uint256(10),
            uint256(20),
            uint256(15),
            uint256(5000),
            uint256(80),
            uint256(18),
            uint256(1700000001)
        );
        bytes memory metadata = hex"00";

        vm.prank(forwarder);
        receiver.onReport(metadata, payload);

        ProvenanceDataReceiver.ProvenanceReport memory r = receiver.getProvenanceMetrics();
        assertEq(r.totalFarmers, 10);
        assertEq(r.totalBatches, 20);
        assertTrue(r.exists);
    }

    function test_ProvenanceReport_HistoryAccumulates() public {
        bytes32 dataId = bytes32("voiceledger-provenance");

        for (uint256 i = 1; i <= 3; i++) {
            bytes memory payload = abi.encode(
                dataId, i * 10, i * 20, i * 15, i * 1000, i * 30, i * 10, 1700000000 + i
            );
            bytes memory report = abi.encodePacked(uint8(0x01), payload);
            vm.prank(forwarder);
            receiver.onReport(report);
        }

        assertEq(receiver.reportCount(), 3);
        // Latest should be the third
        ProvenanceDataReceiver.ProvenanceReport memory latest = receiver.getProvenanceMetrics();
        assertEq(latest.totalFarmers, 30);
    }

    // ─────────────────────────────────────────────
    // Deforestation attestation (type 0x02)
    // ─────────────────────────────────────────────

    function test_DeforestationAttestation_ViaTypeByte() public {
        bytes memory payload = abi.encode(
            "FARM-001",
            int64(9032000),   // latitude × 1e6
            int64(38746900),  // longitude × 1e6
            uint8(0),         // riskLevel = LOW
            true,             // eudrCompliant
            uint256(3500),    // treeLossScaled × 1e4 = 0.35 ha
            uint256(1700000000)
        );
        bytes memory report = abi.encodePacked(uint8(0x02), payload);

        vm.prank(forwarder);
        receiver.onReport(report);

        ProvenanceDataReceiver.DeforestationAttestation memory a =
            receiver.getDeforestationAttestation("FARM-001");
        assertEq(a.farmId, "FARM-001");
        assertEq(a.latitude, int64(9032000));
        assertEq(a.longitude, int64(38746900));
        assertEq(a.riskLevel, 0);
        assertTrue(a.eudrCompliant);
        assertEq(a.treeLossScaled, 3500);
        assertTrue(a.exists);

        assertTrue(receiver.isFarmCompliant("FARM-001"));
        assertEq(receiver.attestedFarmCount(), 1);
    }

    function test_DeforestationAttestation_HighRisk_NotCompliant() public {
        bytes memory payload = abi.encode(
            "FARM-BAD",
            int64(8000000),
            int64(37000000),
            uint8(2),         // HIGH
            false,            // not compliant
            uint256(25000),   // 2.5 ha loss
            uint256(1700000000)
        );
        bytes memory report = abi.encodePacked(uint8(0x02), payload);

        vm.prank(forwarder);
        receiver.onReport(report);

        assertFalse(receiver.isFarmCompliant("FARM-BAD"));
    }

    function test_DeforestationAttestation_UpdateExisting() public {
        // First attestation
        bytes memory payload1 = abi.encode(
            "FARM-002", int64(9000000), int64(38000000), uint8(1), false, uint256(15000), uint256(1700000000)
        );
        vm.prank(forwarder);
        receiver.onReport(abi.encodePacked(uint8(0x02), payload1));

        assertFalse(receiver.isFarmCompliant("FARM-002"));
        assertEq(receiver.attestedFarmCount(), 1);

        // Updated attestation - farm is now compliant
        bytes memory payload2 = abi.encode(
            "FARM-002", int64(9000000), int64(38000000), uint8(0), true, uint256(2000), uint256(1700000001)
        );
        vm.prank(forwarder);
        receiver.onReport(abi.encodePacked(uint8(0x02), payload2));

        assertTrue(receiver.isFarmCompliant("FARM-002"));
        // Should NOT double-count the farm
        assertEq(receiver.attestedFarmCount(), 1);
    }

    function test_MultipleFarms() public {
        string[3] memory farms = ["FARM-A", "FARM-B", "FARM-C"];
        for (uint256 i = 0; i < 3; i++) {
            bytes memory payload = abi.encode(
                farms[i], int64(9000000), int64(38000000), uint8(0), true, uint256(1000), uint256(1700000000 + i)
            );
            vm.prank(forwarder);
            receiver.onReport(abi.encodePacked(uint8(0x02), payload));
        }
        assertEq(receiver.attestedFarmCount(), 3);
    }

    // ─────────────────────────────────────────────
    // Access control
    // ─────────────────────────────────────────────

    function test_RevertWhen_StrangerSubmitsReport() public {
        bytes memory report = abi.encodePacked(
            uint8(0x01),
            abi.encode(bytes32(0), uint256(1), uint256(1), uint256(1), uint256(1), uint256(1), uint256(1), uint256(1))
        );

        vm.prank(stranger);
        vm.expectRevert(ProvenanceDataReceiver.Unauthorized.selector);
        receiver.onReport(report);
    }

    function test_OwnerCanSubmitReport() public {
        bytes memory report = abi.encodePacked(
            uint8(0x01),
            abi.encode(bytes32(0), uint256(5), uint256(10), uint256(8), uint256(2000), uint256(90), uint256(9), uint256(1700000000))
        );

        vm.prank(owner);
        receiver.onReport(report);

        assertEq(receiver.getProvenanceMetrics().totalFarmers, 5);
    }

    function test_RevertWhen_InvalidReportType() public {
        bytes memory report = abi.encodePacked(uint8(0xFF), abi.encode(uint256(1)));

        vm.prank(forwarder);
        vm.expectRevert(abi.encodeWithSelector(ProvenanceDataReceiver.InvalidReportType.selector, uint8(0xFF)));
        receiver.onReport(report);
    }

    // ─────────────────────────────────────────────
    // Admin
    // ─────────────────────────────────────────────

    function test_SetForwarder() public {
        address newForwarder = makeAddr("newForwarder");

        vm.prank(owner);
        receiver.setForwarder(newForwarder);
        assertEq(receiver.forwarder(), newForwarder);
    }

    function test_RevertWhen_NonOwnerSetsForwarder() public {
        vm.prank(stranger);
        vm.expectRevert(ProvenanceDataReceiver.Unauthorized.selector);
        receiver.setForwarder(stranger);
    }

    // ─────────────────────────────────────────────
    // Edge cases
    // ─────────────────────────────────────────────

    function test_RevertWhen_QueryingNonExistentFarm() public {
        vm.expectRevert(abi.encodeWithSelector(ProvenanceDataReceiver.FarmNotAttested.selector, "GHOST"));
        receiver.getDeforestationAttestation("GHOST");
    }

    function test_IsFarmCompliant_ReturnsFalseForUnknown() public view {
        assertFalse(receiver.isFarmCompliant("NONEXISTENT"));
    }

    function test_InitialState_Empty() public view {
        assertEq(receiver.reportCount(), 0);
        assertEq(receiver.attestedFarmCount(), 0);
    }
}
