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
  CronCapability,
  decodeJson,
  EVMClient,
  getNetwork,
  handler,
  hexToBase64,
  HTTPCapability,
  HTTPClient,
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

  /** Base URL of the Voice Ledger provenance API
   *  Note: z.string().url() uses `new URL()` which is unavailable in QuickJS/WASM.
   *  We use a regex instead so validation works in both Node and CRE simulation. */
  apiBaseUrl: z.string().regex(/^https?:\/\/.+/, "Must be an http(s) URL"),

  /** GFW (Global Forest Watch) API key for independent spot-check by DON nodes */
  gfwApiKey: z.string().optional().default(""),

  /** GFW data API base URL */
  gfwApiUrl: z.string().optional().default("https://data-api.globalforestwatch.org"),

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
  geostoreId: string;     // GFW geostore ID for DON spot-check
  timestamp: number;
}

/** Raw GFW tree cover loss data returned by DON spot-check */
interface GfwTreeLoss {
  totalTreeLossHaScaled: number;  // sum of tree_loss_ha × 1e4 (integer)
  recordCount: number;            // number of yearly records
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
  return JSON.parse(new TextDecoder().decode(resp.body));
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
  return JSON.parse(new TextDecoder().decode(resp.body));
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
  return JSON.parse(new TextDecoder().decode(resp.body));
};

/**
 * DON Spot-Check: fetch raw tree cover loss directly from GFW.
 *
 * Uses the same geostore_id that our API used, so the geographic area is
 * identical. Each DON node independently queries GFW and sums the post-2020
 * tree loss. The result is compared against our API's claim.
 */
const fetchGfwTreeLoss = (
  sendRequester: HTTPSendRequester,
  config: Config,
  geostoreId: string,
): GfwTreeLoss => {
  // NOTE: Do NOT alias umd_tree_cover_loss__year to "year" — GFW treats
  // it as an invalid layer name.
  const sql =
    "SELECT umd_tree_cover_loss__year, " +
    "SUM(umd_tree_cover_loss__ha) as tree_loss_ha " +
    "FROM data " +
    "WHERE umd_tree_cover_loss__year > 2020 " +
    "GROUP BY umd_tree_cover_loss__year ORDER BY umd_tree_cover_loss__year";

  // API key is passed as a *query parameter* (not header) because the
  // /latest/ path triggers a 307 redirect that strips headers.  An origin
  // header matching the key's allowed-domains list is also required.
  let url =
    `${config.gfwApiUrl}/dataset/umd_tree_cover_loss/latest/query/json` +
    `?sql=${encodeURIComponent(sql)}&geostore_id=${encodeURIComponent(geostoreId)}`;
  if (config.gfwApiKey) {
    url += `&x-api-key=${encodeURIComponent(config.gfwApiKey)}`;
  }

  const headers: Record<string, string> = { origin: "http://localhost" };

  const resp = sendRequester
    .sendRequest({ method: "GET", url, headers })
    .result();
  const body = JSON.parse(new TextDecoder().decode(resp.body));
  const records: Array<{
    umd_tree_cover_loss__year: number;
    tree_loss_ha: number;
  }> = body.data || [];

  // Sum and scale to integer (×1e4) — same scaling as our API
  const totalLossHa = records.reduce(
    (sum: number, r: { tree_loss_ha: number }) => sum + (r.tree_loss_ha || 0),
    0,
  );

  return {
    totalTreeLossHaScaled: Math.round(totalLossHa * 10000),
    recordCount: records.length,
  };
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
  const httpClient = new HTTPClient();
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
      encoderName: "evm",
      signingAlgo: "ecdsa",
      hashingAlgo: "keccak256",
    })
    .result();

  for (const evm of runtime.config.evms) {
    const network = getNetwork({
      chainFamily: "evm",
      chainSelectorName: evm.chainSelectorName,
      isTestnet: true,
    });
    if (!network) throw new Error(`Unknown chain: ${evm.chainSelectorName}`);
    const evmClient = new EVMClient(
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
  const httpClient = new HTTPClient();
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
  const body = decodeJson(payload.input) as {
    farm_id: string;
  };
  const farmId = body.farm_id;
  runtime.log(`[Trigger 3] Farm ID: ${farmId}`);

  // ── 2. Fetch our API's computed result (includes geostoreId) ──
  //        Identical consensus: all nodes must get the same result
  const httpClient = new HTTPClient();
  const apiResult = httpClient
    .sendRequest(
      runtime,
      fetchDeforestationResult,
      consensusIdenticalAggregation<DeforestationResult>(),
    )(runtime.config, farmId)
    .result();

  runtime.log(
    `[Trigger 3] API result — risk: ${apiResult.riskLevelCode}, ` +
      `compliant: ${apiResult.eudrCompliant}, loss: ${apiResult.treeLossHectaresScaled / 10000} ha, ` +
      `geostore: ${apiResult.geostoreId}`,
  );

  // ── 3. DON Spot-Check: independently query GFW with the same geostore ──
  //        Each node calls GFW directly, sums post-2020 tree loss.
  //        Identical consensus: all nodes must get the same raw GFW data.
  const gfwResult = httpClient
    .sendRequest(
      runtime,
      fetchGfwTreeLoss,
      consensusIdenticalAggregation<GfwTreeLoss>(),
    )(runtime.config, apiResult.geostoreId)
    .result();

  runtime.log(
    `[Trigger 3] GFW spot-check — raw loss: ${gfwResult.totalTreeLossHaScaled / 10000} ha ` +
      `(${gfwResult.recordCount} yearly records)`,
  );

  // ── 4. Compare: our API vs direct GFW query ──
  //        Apply the same EUDR threshold (< 0.5 ha = compliant)
  const EUDR_THRESHOLD_SCALED = 5000; // 0.5 ha × 1e4
  const spotCheckCompliant = gfwResult.totalTreeLossHaScaled < EUDR_THRESHOLD_SCALED;

  // Check tree loss values match (allow ±1 unit tolerance for rounding)
  const lossMatch =
    Math.abs(apiResult.treeLossHectaresScaled - gfwResult.totalTreeLossHaScaled) <= 1;
  const complianceMatch = apiResult.eudrCompliant === spotCheckCompliant;

  if (!lossMatch || !complianceMatch) {
    runtime.log(
      `[Trigger 3] ⚠ SPOT CHECK MISMATCH — ` +
        `API loss: ${apiResult.treeLossHectaresScaled}, GFW loss: ${gfwResult.totalTreeLossHaScaled}, ` +
        `API compliant: ${apiResult.eudrCompliant}, spot-check compliant: ${spotCheckCompliant}`,
    );
    // Refuse to attest — return dispute without writing on-chain
    return JSON.stringify({
      farmId: apiResult.farmId,
      attested: false,
      reason: "spot_check_mismatch",
      apiTreeLoss: apiResult.treeLossHectaresScaled,
      gfwTreeLoss: gfwResult.totalTreeLossHaScaled,
    });
  }

  runtime.log("[Trigger 3] ✓ Spot-check PASSED — API and GFW agree");

  // ── 5. ABI-encode deforestation attestation ──
  const encodedPayload = encodeAbiParameters(
    parseAbiParameters(
      "string farmId, int64 latitude, int64 longitude, uint8 riskLevel, " +
        "bool eudrCompliant, uint256 treeLossScaled, uint256 timestamp",
    ),
    [
      apiResult.farmId,
      BigInt(apiResult.latitude),
      BigInt(apiResult.longitude),
      apiResult.riskLevelCode,
      apiResult.eudrCompliant,
      BigInt(apiResult.treeLossHectaresScaled),
      BigInt(apiResult.timestamp),
    ],
  );

  // ── 6. DON-sign and write attestation on-chain ──
  const report = runtime
    .report({
      encodedPayload: hexToBase64(encodedPayload),
      encoderName: "evm",
      signingAlgo: "ecdsa",
      hashingAlgo: "keccak256",
    })
    .result();

  for (const evm of runtime.config.evms) {
    const network = getNetwork({
      chainFamily: "evm",
      chainSelectorName: evm.chainSelectorName,
      isTestnet: true,
    });
    if (!network) throw new Error(`Unknown chain: ${evm.chainSelectorName}`);
    const evmClient = new EVMClient(
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
    farmId: apiResult.farmId,
    riskLevel: apiResult.riskLevelCode,
    eudrCompliant: apiResult.eudrCompliant,
    spotCheckPassed: true,
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
  const cronCap = new CronCapability();
  const evmClient = new EVMClient(network.chainSelector.selector);
  const httpCap = new HTTPCapability();

  return [
    // Trigger 1 — Proof of Provenance (cron)
    handler(
      cronCap.trigger({ schedule: config.schedule }),
      onProvenanceCron,
    ),

    // Trigger 2 — Event Watcher (log trigger on EPCISEventAnchor)
    handler(
      evmClient.logTrigger({
        addresses: [hexToBase64(primaryEvm.epcisEventAnchorAddress)],
      }),
      onEventAnchored,
    ),

    // Trigger 3 — Deforestation Oracle (HTTP trigger)
    handler(httpCap.trigger({}), onDeforestationRequest),
  ];
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Entrypoint
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

export async function main() {
  const runner = await Runner.newRunner<Config>({ configSchema });
  await runner.run(initWorkflow);
}
