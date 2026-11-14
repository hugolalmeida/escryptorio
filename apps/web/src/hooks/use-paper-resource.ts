"use client";
import { useEffect, useRef, useState } from "react";
import { paperGet } from "@/lib/paper";

type State<T> = { key: string | null; data: T | null; error: string | null; loading: boolean; observed: number | null };

// Each resource owns its error and request generation. A newer request always wins.
export function usePaperResource<T>(path: string | null, refresh: number): State<T> {
  const [state, setState] = useState<State<T>>({ key: null, data: null, error: null, loading: !!path, observed: null });
  const generation = useRef(0);
  useEffect(() => {
    if (!path) { setState({ key: null, data: null, error: null, loading: false, observed: null }); return; }
    let controller: AbortController | null = null;
    let active = true;
    setState({ key: path, data: null, error: null, loading: true, observed: null });
    const load = async () => {
      controller?.abort();
      controller = new AbortController();
      const current = ++generation.current;
      try {
        const result = await paperGet<T>(path, controller.signal);
        if (active && current === generation.current) setState({ key: path, data: result.data, error: null, loading: false, observed: result.observed_at_ms });
      } catch {
        if (active && current === generation.current) setState({ key: path, data: null, error: "Consulta indisponível ou integridade não pôde ser verificada.", loading: false, observed: null });
      }
    };
    void load();
    const timer = window.setInterval(load, 15000);
    return () => { active = false; generation.current++; controller?.abort(); window.clearInterval(timer); };
  }, [path, refresh]);
  // React effects run after render; never display data from the preceding path.
  return state.key === path ? state : { key: path, data: null, error: null, loading: !!path, observed: null };
}
