import {
  MilvusClient,
  DataType,
  MetricType,
} from '@zilliz/milvus2-sdk-node';

/**
 * Minimal Bun.js example for the milvus-lite Docker image (kennytian/milvus-lite).
 *
 * Auth is read from the environment:
 *   - MILVUS_LITE_TOKEN                    -> token form (takes precedence)
 *   - MILVUS_LITE_USERNAME + MILVUS_LITE_PASSWORD -> username/password form
 *   - neither                               -> no auth
 *   - MILVUS_LITE_ADDR                     -> server address (default 127.0.0.1:19530)
 *
 * The server is a Milvus Lite 3.x standalone gRPC server on port 19530.
 */

const ADDR = process.env.MILVUS_LITE_ADDR ?? '127.0.0.1:19530';
const TOKEN = (process.env.MILVUS_LITE_TOKEN ?? '').trim();
const USERNAME = (process.env.MILVUS_LITE_USERNAME ?? '').trim();
const PASSWORD = process.env.MILVUS_LITE_PASSWORD ?? '';

const COLLECTION_NAME = 'demo_bun';
const DIM = 8;

/** Build the client options with the appropriate auth (token wins over user/pass). */
function buildClientOptions() {
  const opts: Record<string, string> = { address: ADDR };
  if (TOKEN) {
    opts.token = TOKEN;
    console.log(`[auth] using token auth (address=${ADDR})`);
  } else if (USERNAME && PASSWORD) {
    opts.username = USERNAME;
    opts.password = PASSWORD;
    console.log(`[auth] using username/password auth (user=${USERNAME}, address=${ADDR})`);
  } else {
    console.log(`[auth] no auth configured (address=${ADDR})`);
  }
  return opts;
}

async function main() {
  const client = new MilvusClient(buildClientOptions());
  await client.connectPromise;

  // --- Create the collection (idempotent). ------------------------------
  const exists = await client.hasCollection({ collection_name: COLLECTION_NAME });
  if (exists.value) {
    console.log(`[collection] "${COLLECTION_NAME}" already exists, reusing it.`);
  } else {
    await client.createCollection({
      collection_name: COLLECTION_NAME,
      fields: [
        { name: 'id', data_type: DataType.Int64, is_primary_key: true, autoID: true },
        { name: 'text', data_type: DataType.VarChar, max_length: 512 },
        { name: 'vector', data_type: DataType.FloatVector, dim: DIM },
      ],
      index_params: [
        {
          field_name: 'vector',
          index_type: 'FLAT',
          metric_type: MetricType.IP,
          params: {},
        },
      ],
    });
    console.log(`[collection] created "${COLLECTION_NAME}" (dim=${DIM}).`);
  }

  // --- Load the collection into memory. ---------------------------------
  await client.loadCollectionSync({ collection_name: COLLECTION_NAME });
  console.log(`[load] loaded "${COLLECTION_NAME}".`);

  // --- Insert a couple of rows. -----------------------------------------
  const queryVector = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8];
  const rows = [
    { text: 'hello world', vector: queryVector.slice() },
    { text: 'another doc', vector: [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2] },
  ];
  const insertRes = await client.insert({
    collection_name: COLLECTION_NAME,
    data: rows,
  });
  console.log(`[insert] inserted ${rows.length} rows.`);

  // --- Search. ----------------------------------------------------------
  const searchRes = await client.search({
    collection_name: COLLECTION_NAME,
    data: [queryVector],
    limit: 2,
    consistency_level: 'Strong', // see the rows inserted a moment ago
    output_fields: ['text'],
  });

  console.log('\nSearch results (nearest to the query vector):');
  const hits = searchRes.results ?? [];
  for (const hit of hits) {
    console.log(`  score=${hit.score?.toFixed(6)}  text=${JSON.stringify(hit.text)}`);
  }

  await client.closeConnection();
  console.log('\n[done] connection closed.');
}

main().catch((err) => {
  console.error('Failed:', err);
  process.exit(1);
});
