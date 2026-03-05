// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {FinancingPool} from "../src/FinancingPool.sol";
import {TradeEscrow} from "../src/TradeEscrow.sol";
import {FeeDistributor} from "../src/FeeDistributor.sol";

/**
 * @title  DeployDeFiPool
 * @notice Deployment script for the Voice Ledger DeFi financing pool contracts.
 *
 *         Deploys: FinancingPool, FeeDistributor, TradeEscrow
 *         Then wires permissions (setEscrow on pool + distributor).
 *
 *         Required env vars:
 *           USDC_ADDRESS                     — USDC token on target chain
 *           COFFEE_BATCH_TOKEN_ADDRESS       — Existing CoffeeBatchToken
 *           EPCIS_EVENT_ANCHOR_ADDRESS       — Existing EPCISEventAnchor
 *           PROVENANCE_DATA_RECEIVER_ADDRESS — Existing ProvenanceDataReceiver
 *           SETTLEMENT_CONTRACT_ADDRESS      — Existing SettlementContract
 *           TREASURY_ADDRESS                 — Protocol treasury wallet
 *           RESERVE_FUND_ADDRESS             — Reserve fund wallet
 *
 * @dev    Run: forge script script/DeployDeFiPool.s.sol --rpc-url $RPC_URL
 *              --broadcast --verify -vvvv
 */
contract DeployDeFiPool is Script {

    struct DeployedContracts {
        FinancingPool financingPool;
        FeeDistributor feeDistributor;
        TradeEscrow tradeEscrow;
    }

    function run() external returns (DeployedContracts memory) {
        // ── Read env ──
        address usdc       = vm.envAddress("USDC_ADDRESS");
        address batchToken = vm.envAddress("COFFEE_BATCH_TOKEN_ADDRESS");
        address epcis      = vm.envAddress("EPCIS_EVENT_ANCHOR_ADDRESS");
        address provenance = vm.envAddress("PROVENANCE_DATA_RECEIVER_ADDRESS");
        address settlement = vm.envAddress("SETTLEMENT_CONTRACT_ADDRESS");
        address treasury   = vm.envAddress("TREASURY_ADDRESS");
        address reserve    = vm.envAddress("RESERVE_FUND_ADDRESS");

        vm.startBroadcast();

        // 1. Deploy FinancingPool (ERC-4626 vault)
        FinancingPool pool = new FinancingPool(IERC20(usdc));

        // 2. Deploy FeeDistributor
        FeeDistributor distributor = new FeeDistributor(
            usdc,
            address(pool),
            treasury,
            reserve
        );

        // 3. Deploy TradeEscrow (orchestrator)
        TradeEscrow escrow = new TradeEscrow(
            batchToken,
            epcis,
            provenance,
            settlement,
            address(pool),
            address(distributor),
            usdc
        );

        // 4. Wire permissions
        pool.setEscrow(address(escrow));
        distributor.setEscrow(address(escrow));

        vm.stopBroadcast();

        // ── Log addresses ──
        console2.log("==========================================");
        console2.log("Voice Ledger DeFi Pool - Deployed");
        console2.log("==========================================");
        console2.log("");
        console2.log("FinancingPool (vlUSDC vault):", address(pool));
        console2.log("FeeDistributor:             ", address(distributor));
        console2.log("TradeEscrow:                ", address(escrow));
        console2.log("");
        console2.log("==========================================");
        console2.log("Existing contracts (unchanged):");
        console2.log("==========================================");
        console2.log("CoffeeBatchToken:           ", batchToken);
        console2.log("EPCISEventAnchor:           ", epcis);
        console2.log("ProvenanceDataReceiver:     ", provenance);
        console2.log("SettlementContract:         ", settlement);
        console2.log("USDC:                       ", usdc);
        console2.log("");
        console2.log("==========================================");
        console2.log("Add to .env:");
        console2.log("==========================================");
        console2.log(string.concat("FINANCING_POOL_ADDRESS=", vm.toString(address(pool))));
        console2.log(string.concat("FEE_DISTRIBUTOR_ADDRESS=", vm.toString(address(distributor))));
        console2.log(string.concat("TRADE_ESCROW_ADDRESS=", vm.toString(address(escrow))));

        return DeployedContracts({
            financingPool: pool,
            feeDistributor: distributor,
            tradeEscrow: escrow
        });
    }
}
