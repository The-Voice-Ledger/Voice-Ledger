/**
 * Voice Ledger Oracle — Chainlink CRE Workflow
 *
 * A single CRE workflow with three trigger→handler pairs:
 *
 *   1. CronTrigger   → Proof of Provenance data feed  (every 5 min)
 *   2. LogTrigger     → Event-Reactive Compliance       (watches EventAnchored)
 *   3. HTTPTrigger    → EUDR Deforestation Oracle        (on-demand attestation)
 *
 * Deployed as one unit to a Chainlink DON on Base Sepolia.
 *
 * @author  Voice Ledger × Chainlink CRE
 * @date    February 2026
 */

import {
  bytesToHex,
  ConsensusAggregationByFields,
  consensusIdenticalAggregation,
  cre,
  getNetwork,
  hexToBase64,
  identical,
  median,
  Runner,
  type CronPayload,
  type EVMLog,
  type HTTPPayload,
  type HTTPSendRequester,
  type Runtime,
  TxStatus,
} from "@chainlink/cre-sdk";

import {
  decodeEventLog,
  encodeAbiParameters,
  parseAbi,
  parseAbiParameters,
} from "viem";

import { z } from "zod";

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Config schema (validated by CRE Runner at startup)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const configSchema = z.object({
  /** Cron schedule for Trigger 1 (e.g. "0 *\/5 * * * *" = every 5 min) */
  schedule: z.string(),

  /** Base URL of the Voice Ledger provenance API */
  apiBaseUrl: z.string().url(),

  /** Hex-encoded data-feed ID for the provenance feed */
  provenanceDataIdHex: z.string(),

  /** EVM target chains (usually just Base Sepolia) */
  evms: z.array(
    z.object({
      chainSelectorName: z.string(),
      epcisEventAnchorAddress: z.string(),
      provenanceReceiverAddress: z.string(),
      dataFeedsCacheAddress: z.string(),
      gasLimit: z.string(),
    }),
  ),
});

type Config = z.infer<typeof configSchema>;

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Shared types
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

interface ProvenanceMetrics {
  totalFarmers: number;
  totalBatches: number;
  verifiedBatches: number;
  totalQuantityKg: number;
  eudrCompliantPercent: number;
  batchesAnchored: number;
  lastUpdated: number;
}

interface DeforestationResult {
  farmId: string;
  latitude: number;       // scaled ×1e6
  longitude: number;      // scaled ×1e6
  riskLevelCode: number;  // 0=LOW 1=MEDIUM 2=HIGH 3=UNKNOWN
  eudrCompliant: boolean;
  treeLossHectaresScaled: number;  // scaled ×1e4
  timestamp: number;
}

interface BatchDetails {
  batchId: string;
  gtin: string;
  quantityKg: number;
  origin: string;
  originCountry: string;
  originRegion: string;
  variety: string;
  qualityGrade: string;
  status: string;
  farmerId: string;
  farmerName: string;
  farmerLocation: string;
  farmerEudrCompliant: boolean;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// EPCISEventAnchor ABI (only the event we watch)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const epcisAnchorAbi = parseAbi([
  "event EventAnchored(bytes32 indexed eventHash, string batchId, string eventType, uint256 timestamp, address indexed submitter)",
]);

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// HTTP fetch functions (executed inside DON nodes)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/** Fetch aggregated provenance metrics from Voice Ledger API */
const fetchProvenanceMetrics = (
  sendRequester: HTTPSendRequester,
  config: Config,
): ProvenanceMetrics => {
  const resp = sendRequester
    .sendRequest({ method: "GET", url: `${config.apiBaseUrl}/api/provenance` })
    .result();
  return JSON.parse(Buffer.from(resp.body).toString("utf-8"));
};

/** Fetch batch details by batch_id */
const fetchBatchDetails = (
  sendRequester: HTTPSendRequester,
  config: Config,
  batchId: string,
): BatchDetails => {
  const resp = sendRequester
    .sendRequest({
      method: "GET",
      url: `${config.apiBaseUrl}/api/batch/${batchId}`,
    })
    .result();
  return JSON.parse(Buffer.from(resp.body).toString("utf-8"));
};

/** Fetch deforestation check result for a farm */
const fetchDeforestationResult = (
  sendRequester: HTTPSendRequester,
  config: Config,
  farmId: string,
): DeforestationResult => {
  const resp = sendRequester
    .sendRequest({
      method: "GET",
      url: `${config.apiBaseUrl}/api/deforestation/${farmId}`,
    })
    .result();
  return JSON.parse(Buffer.from(resp.body).toString("utf-8"));
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TRIGGER 1 — Proof of Provenance (Cron)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const onProvenanceCron = (
  runtime: Runtime<Config>,
  _payload: CronPayload,
): string => {
  runtime.log("[Trigger 1] Proof of Provenance — cron fired");

  // ── 1. Fetch metrics with median consensus across DON nodes ──
  const httpClient = new cre.capabilities.HTTPClient();
  const metrics = httpClient
    .sendRequest(
      runtime,
      fetchProvenanceMetrics,
      ConsensusAggregationByFields<ProvenanceMetrics>({
        totalFarmers: median,
        totalBatches: median,
        verifiedBatches: median,
        totalQuantityKg: median,
        eudrCompliantPercent: median,
        batchesAnchored: median,
        lastUpdated: median,
      }),
    )(runtime.config)
    .result();

  runtime.log(
    `[Trigger 1] DON consensus reached — ${metrics.totalFarmers} farmers, ` +
      `${metrics.totalBatches} batches, ${metrics.eudrCompliantPercent}% EUDR compliant`,
  );

  // ── 2. ABI-encode report payload ──
  const dataIdBytes = `0x${runtime.config.provenanceDataIdHex}` as `0x${string}`;

  const encodedPayload = encodeAbiParameters(
    parseAbiParameters(
      "bytes32 dataId, uint256 totalFarmers, uint256 totalBatches, " +
        "uint256 verifiedBatches, uint256 totalQuantityKg, " +
        "uint256 eudrCompliantPercent, uint256 batchesAnchored, uint256 lastUpdated",
    ),
    [
      dataIdBytes,
      BigInt(metrics.totalFarmers),
      BigInt(metrics.totalBatches),
      BigInt(metrics.verifiedBatches),
      BigInt(metrics.totalQuantityKg),
      BigInt(metrics.eudrCompliantPercent),
      BigInt(metrics.batchesAnchored),
      BigInt(metrics.lastUpdated),
    ],
  );

  // ── 3. DON-sign and write report to each target chain ──
  const report = runtime
    .report({
      encodedPayload: hexToBase64(encodedPayload),
      encoderName: "EVM",
      signingAlgo: "ECDSA_SECP256K1",
      hashingAlgo: "KECCAK256",
    })
    .result();

  for (const evm of runtime.config.evms) {
    const network = getNetwork({
      chainFamily: "evm",
      chainSelectorName: evm.chainSelectorName,
      isTestnet: true,
    });
    if (!network) throw new Error(`Unknown chain: ${evm.chainSelectorName}`);
    const evmClient = new cre.capabilities.EVMClient(
      network.chainSelector.selector,
    );
    const tx = evmClient
      .writeReport(runtime, {
        receiver: evm.dataFeedsCacheAddress,
        report,
        gasConfig: { gasLimit: evm.gasLimit },
      })
      .result();

    runtime.log(
      `[Trigger 1] Report written → ${evm.chainSelectorName} ` +
        `(status: ${tx.txStatus === TxStatus.SUCCESS ? "SUCCESS" : "PENDING"})`,
    );
  }

  return JSON.stringify(metrics);
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TRIGGER 2 — Event-Reactive Compliance (LogTrigger)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const onEventAnchored = (
  runtime: Runtime<Config>,
  log: EVMLog,
): string => {
  runtime.log("[Trigger 2] EventAnchored detected on-chain");

  // ── 1. Decode the EventAnchored log ──
  const topics = log.topics.map((t: Uint8Array) => bytesToHex(t)) as [
    `0x${string}`,
    ...`0x${string}`[],
  ];
  const data = bytesToHex(log.data);

  const decoded = decodeEventLog({
    abi: epcisAnchorAbi,
    data,
    topics,
  });

  const batchId = (decoded.args as any).batchId as string;
  const eventType = (decoded.args as any).eventType as string;
  runtime.log(`[Trigger 2] Batch: ${batchId} | Event: ${eventType}`);

  // ── 2. Fetch full batch details with median consensus on numeric fields ──
  const httpClient = new cre.capabilities.HTTPClient();
  const batchDetails = httpClient
    .sendRequest(
      runtime,
      fetchBatchDetails,
      ConsensusAggregationByFields<BatchDetails>({
        batchId: identical,
        gtin: identical,
        quantityKg: median,
        origin: identical,
        originCountry: identical,
        originRegion: identical,
        variety: identical,
        qualityGrade: identical,
        status: identical,
        farmerId: identical,
        farmerName: identical,
        farmerLocation: identical,
        farmerEudrCompliant: identical,
      }),
    )(runtime.config, batchId)
    .result();

  runtime.log(
    `[Trigger 2] Batch details retrieved — ${batchDetails.quantityKg}kg ` +
      `${batchDetails.variety || "coffee"} from ${batchDetails.origin || "Ethiopia"}`,
  );

  // ── 3. POST notification to buyer webhook (best-effort) ──
  //        In production: config would contain buyer webhook URLs.
  //        For hackathon: we log the notification payload.
  const notification = {
    type: "NEW_BATCH_ANCHORED",
    batchId: batchDetails.batchId,
    gtin: batchDetails.gtin,
    quantityKg: batchDetails.quantityKg,
    origin: batchDetails.originRegion || batchDetails.origin,
    variety: batchDetails.variety,
    qualityGrade: batchDetails.qualityGrade,
    eudrCompliant: batchDetails.farmerEudrCompliant,
    timestamp: Math.floor(Date.now() / 1000),
  };

  runtime.log(
    `[Trigger 2] Buyer notification prepared: ${JSON.stringify(notification)}`,
  );

  return JSON.stringify({ batchId, eventType, notified: true });
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TRIGGER 3 — EUDR Deforestation Oracle (HTTP)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const onDeforestationRequest = (
  runtime: Runtime<Config>,
  payload: HTTPPayload,
): string => {
  runtime.log("[Trigger 3] Deforestation attestation requested");

  // ── 1. Parse incoming HTTP request body ──
  const body = JSON.parse(Buffer.from(payload.input).toString("utf-8")) as {
    farm_id: string;
  };
  const farmId = body.farm_id;
  runtime.log(`[Trigger 3] Farm ID: ${farmId}`);

  // ── 2. Each DON node independently calls GFW via our API ──
  //        Identical consensus: all nodes must get the same result
  const httpClient = new cre.capabilities.HTTPClient();
  const result = httpClient
    .sendRequest(
      runtime,
      fetchDeforestationResult,
      consensusIdenticalAggregation<DeforestationResult>(),
    )(runtime.config, farmId)
    .result();

  runtime.log(
    `[Trigger 3] DON consensus reached — risk: ${result.riskLevelCode}, ` +
      `compliant: ${result.eudrCompliant}, loss: ${result.treeLossHectaresScaled / 10000} ha`,
  );

  // ── 3. ABI-encode deforestation attestation ──
  const encodedPayload = encodeAbiParameters(
    parseAbiParameters(
      "string farmId, int64 latitude, int64 longitude, uint8 riskLevel, " +
        "bool eudrCompliant, uint256 treeLossScaled, uint256 timestamp",
    ),
    [
      result.farmId,
      BigInt(result.latitude),
      BigInt(result.longitude),
      result.riskLevelCode,
      result.eudrCompliant,
      BigInt(result.treeLossHectaresScaled),
      BigInt(result.timestamp),
    ],
  );

  // ── 4. DON-sign and write attestation on-chain ──
  const report = runtime
    .report({
      encodedPayload: hexToBase64(encodedPayload),
      encoderName: "EVM",
      signingAlgo: "ECDSA_SECP256K1",
      hashingAlgo: "KECCAK256",
    })
    .result();

  for (const evm of runtime.config.evms) {
    const network = getNetwork({
      chainFamily: "evm",
      chainSelectorName: evm.chainSelectorName,
      isTestnet: true,
    });
    if (!network) throw new Error(`Unknown chain: ${evm.chainSelectorName}`);
    const evmClient = new cre.capabilities.EVMClient(
      network.chainSelector.selector,
    );
    const tx = evmClient
      .writeReport(runtime, {
        receiver: evm.provenanceReceiverAddress,
        report,
        gasConfig: { gasLimit: evm.gasLimit },
      })
      .result();

    runtime.log(
      `[Trigger 3] Attestation written → ${evm.chainSelectorName} ` +
        `(status: ${tx.txStatus === TxStatus.SUCCESS ? "SUCCESS" : "PENDING"})`,
    );
  }

  return JSON.stringify({
    farmId: result.farmId,
    riskLevel: result.riskLevelCode,
    eudrCompliant: result.eudrCompliant,
    attested: true,
  });
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Workflow initialisation — register all three triggers
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const initWorkflow = (config: Config) => {
  // Resolve Base Sepolia network
  const primaryEvm = config.evms[0];
  const network = getNetwork({
    chainFamily: "evm",
    chainSelectorName: primaryEvm.chainSelectorName,
    isTestnet: true,
  });
  if (!network) throw new Error(`Unknown chain: ${primaryEvm.chainSelectorName}`);

  // Trigger capabilities
  const cronCapability = new cre.capabilities.CronCapability();
  const evmClient = new cre.capabilities.EVMClient(
    network.chainSelector.selector,
  );
  const httpCapability = new cre.capabilities.HTTPCapability();

  return [
    // Trigger 1 — Proof of Provenance (cron)
    cre.handler(
      cronCapability.trigger({ schedule: config.schedule }),
      onProvenanceCron,
    ),

    // Trigger 2 — Event Watcher (log trigger on EPCISEventAnchor)
    cre.handler(
      evmClient.logTrigger({
        addresses: [primaryEvm.epcisEventAnchorAddress],
      }),
      onEventAnchored,
    ),

    // Trigger 3 — Deforestation Oracle (HTTP trigger)
    cre.handler(httpCapability.trigger({}), onDeforestationRequest),
  ];
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Entrypoint
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

export async function main() {
  const runner = await Runner.newRunner<Config>({ configSchema });
  await runner.run(initWorkflow);
}

main();
