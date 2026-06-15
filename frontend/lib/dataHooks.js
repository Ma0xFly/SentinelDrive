"use client";

import { useCallback, useEffect, useState } from "react";

export function useApiResource(loader, dependencies = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await loader());
    } catch (requestError) {
      setError(requestError.message || "请求失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }, dependencies);

  useEffect(() => {
    load();
  }, [load]);

  return { data, error, loading, reload: load };
}
