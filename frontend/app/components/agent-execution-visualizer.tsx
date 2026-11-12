"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  ReactFlow,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

type TraceEvent = {
  node: string;
  status: "active" | "completed" | "skipped";
  duration_ms: number | null;
};

type TraceState = TraceEvent;

const names = [
  "router",
  "retrieve_vector",
  "retrieve_graph",
  "retrieve_hybrid",
  "grade",
  "rewrite",
  "generate",
  "hallucination_check",
  "prepare_regeneration",
];

function TraceNode({ data }: NodeProps<Node<TraceState>>) {
  const state = data;
  const color =
    state.status === "active"
      ? "border-[#c56b3d] bg-[#fff3eb]"
      : state.status === "completed"
        ? "border-[#4e8d70] bg-[#edf8f0]"
        : state.status === "skipped"
          ? "border-[#b8c2bd] bg-[#f1f3f1]"
          : "border-[#17483b]/15 bg-white";
  return (
    <div className={`min-w-36 rounded-xl border px-3 py-2 text-xs shadow-sm ${color}`}>
      <div className="font-medium text-[#17352f]">{state.node}</div>
      <div className="mt-1 text-[10px] text-[#416058]">
        {state.status}{state.duration_ms !== null ? ` · ${state.duration_ms} ms` : ""}
      </div>
    </div>
  );
}

const nodeTypes = { trace: TraceNode };

export default function AgentExecutionVisualizer({ conversationId }: { conversationId: string | null }) {
  const [states, setStates] = useState<Record<string, TraceState>>({});
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (!conversationId) return;
    const websocketUrl = backendUrl().replace(/^http/, "ws") + `/ws/agent-trace?conversation_id=${encodeURIComponent(conversationId)}`;
    const socket = new WebSocket(websocketUrl);
    socket.onmessage = (event) => {
      const trace = JSON.parse(event.data) as TraceEvent;
      setStates((current) => ({ ...current, [trace.node]: trace }));
    };
    socket.onclose = () => {
      if (conversationId) window.setTimeout(() => setRetry((value) => value + 1), 1000);
    };
    return () => socket.close();
  }, [conversationId, retry]);

  const nodes = useMemo(
    () =>
      names.map((name, index) => ({
        id: name,
        type: "trace",
        position: { x: (index % 3) * 170, y: Math.floor(index / 3) * 90 },
        data: states[name] ?? { node: name, status: "skipped", duration_ms: null },
      })),
    [states],
  );
  const edges = useMemo(
    () => [
      ["router", "retrieve_vector"],
      ["router", "retrieve_graph"],
      ["router", "retrieve_hybrid"],
      ["retrieve_vector", "grade"],
      ["retrieve_graph", "grade"],
      ["retrieve_hybrid", "grade"],
      ["grade", "rewrite"],
      ["grade", "generate"],
      ["rewrite", "router"],
      ["generate", "hallucination_check"],
      ["hallucination_check", "prepare_regeneration"],
      ["prepare_regeneration", "generate"],
    ].map(([source, target]) => ({ id: `${source}-${target}`, source, target })),
    [],
  );

  return (
    <aside className="h-[390px] border-t border-[#17483b]/10 bg-[#f4f6f1] p-3 lg:h-auto lg:w-[430px] lg:border-l lg:border-t-0">
      <p className="mb-2 px-2 font-[family-name:var(--font-geist-mono)] text-[10px] uppercase tracking-[0.18em] text-[#c56b3d]">
        Agent execution
      </p>
      <ReactFlow nodes={nodes as Node[]} edges={edges} nodeTypes={nodeTypes} fitView>
        <Background color="#cbd8d0" gap={20} />
        <Controls />
      </ReactFlow>
    </aside>
  );
}

function backendUrl() {
  return process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
}
