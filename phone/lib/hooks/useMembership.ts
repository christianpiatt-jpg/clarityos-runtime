// phone/lib/hooks/useMembership.ts — read /membership/state and expose
// mutations. Mirrors web/src/hooks/useMembership.ts.

import { useCallback, useEffect, useState } from "react";
import {
  billingConfirmIntent,
  gBuyPack20,
  gBuySingle,
  membershipActivate,
  membershipCancel,
  membershipState,
  type ActivateResult,
  type MembershipStateView,
  type PurchaseResult,
} from "../api";

export interface UseMembershipResult {
  state: MembershipStateView | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  activate: (acceptTerms: boolean) => Promise<ActivateResult | null>;
  cancel: () => Promise<MembershipStateView | null>;
  buySingle: () => Promise<PurchaseResult | null>;
  buyPack20: () => Promise<PurchaseResult | null>;
  confirmIntent: (intent_id: string) => Promise<void>;
}

export function useMembership(): UseMembershipResult {
  const [state, setState] = useState<MembershipStateView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await membershipState();
      setState(r.state);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const activate = useCallback(async (acceptTerms: boolean) => {
    setError(null);
    try {
      const r = await membershipActivate(acceptTerms);
      setState(r.state);
      return r;
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    }
  }, []);

  const cancel = useCallback(async () => {
    setError(null);
    try {
      const r = await membershipCancel();
      setState(r.state);
      return r.state;
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    }
  }, []);

  const buySingle = useCallback(async () => {
    setError(null);
    try {
      const r = await gBuySingle();
      setState((s) => (s ? {
        ...s,
        g_credits: { ...s.g_credits, balance: r.balance },
      } : s));
      return r;
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    }
  }, []);

  const buyPack20 = useCallback(async () => {
    setError(null);
    try {
      const r = await gBuyPack20();
      setState((s) => (s ? {
        ...s,
        g_credits: { ...s.g_credits, balance: r.balance },
      } : s));
      return r;
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    }
  }, []);

  const confirmIntent = useCallback(async (intent_id: string) => {
    setError(null);
    try {
      await billingConfirmIntent(intent_id);
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [refresh]);

  return {
    state, loading, error, refresh,
    activate, cancel, buySingle, buyPack20, confirmIntent,
  };
}
