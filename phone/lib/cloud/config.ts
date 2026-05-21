// Architecture D feature flags.
//
// All flags default OFF. Flipping a flag does not change behavior on its
// own — each flag is checked at the integration point in the matching
// stub module. The stubs throw with a clear "not configured" message if
// the flag is true but the backend route doesn't exist yet.
//
// Migration order (recommended): clarityEngine → modelProxy → vaultSync
// → continuity. clarityEngine is the lowest-risk first move because
// transform() is already pure and stateless; the other three need
// auth, storage, and cross-device coordination respectively.

export interface CloudFeatures {
  /** When true, /copy renders distilled text from the Cloud Run clarity
   *  endpoint instead of running transform() locally. */
  clarityEngine: boolean;
  /** When true, vault writes mirror to a server-side per-user store. */
  vaultSync: boolean;
  /** When true, continuity options are pulled from Firestore instead of
   *  (or in addition to) local AsyncStorage. */
  continuity: boolean;
  /** When true, modelRouter dispatches go through the Cloud Run model
   *  proxy. Real API keys live server-side; the bundle ships none. */
  modelProxy: boolean;
}

export const CLOUD_FEATURES: CloudFeatures = {
  clarityEngine: false,
  vaultSync: false,
  continuity: false,
  modelProxy: false,
};

/** Per-feature endpoint paths under the Cloud Run base URL. The base
 *  URL itself comes from lib/config.ts (`API_BASE`). */
export const CLOUD_ROUTES = {
  clarity: "/clarity/transform",
  vaultPush: "/vault/push",
  vaultPull: "/vault/pull",
  continuity: "/continuity/options",
  modelProxy: "/model/route",
} as const;

export function isCloudEnabled(feature: keyof CloudFeatures): boolean {
  return CLOUD_FEATURES[feature] === true;
}
