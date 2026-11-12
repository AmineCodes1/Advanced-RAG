"use client";

import { useMemo, useState } from "react";
import CytoscapeComponent from "react-cytoscapejs";

export type GraphData = {
  nodes: Array<{ id: string; label: string; type: string }>;
  edges: Array<{ source: string; target: string; relation: string }>;
};

export default function InteractiveGraphExplorer({ graph }: { graph?: GraphData }) {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const elements = useMemo(
    () => [
      ...((graph?.nodes ?? []).map((node) => ({ data: { id: node.id, label: node.label, type: node.type } }))),
      ...((graph?.edges ?? []).map((edge, index) => ({
        data: { id: `edge-${index}`, source: edge.source, target: edge.target, label: edge.relation },
      }))),
    ],
    [graph],
  );

  if (!graph || graph.nodes.length === 0 || graph.edges.length === 0) {
    return (
      <p className="mt-4 text-xs text-[#416058]">
        Aucune relation d&apos;entité mobilisée pour cette réponse.
      </p>
    );
  }

  return (
    <div className="mt-5 overflow-hidden rounded-2xl border border-[#17483b]/10 bg-[#f4f6f1]">
      <p className="border-b border-[#17483b]/10 px-4 py-3 font-[family-name:var(--font-geist-mono)] text-[10px] uppercase tracking-[0.18em] text-[#c56b3d]">
        Knowledge graph
      </p>
      <CytoscapeComponent
        elements={elements}
        style={{ width: "100%", height: "280px" }}
        layout={{ name: "cose", animate: false, fit: true, padding: 24 }}
        stylesheet={[
          {
            selector: "node",
            style: {
              label: "data(label)",
              "background-color": "#17483b",
              color: "#17352f",
              "font-size": "10px",
              "text-valign": "bottom",
              "text-margin-y": 6,
            },
          },
          {
            selector: "edge",
            style: {
              label: "data(label)",
              width: 1.5,
              "line-color": "#9bb6a7",
              "target-arrow-color": "#9bb6a7",
              "target-arrow-shape": "triangle",
              "curve-style": "bezier",
              color: "#416058",
              "font-size": "9px",
              "text-background-color": "#f4f6f1",
              "text-background-opacity": 1,
            },
          },
          {
            selector: ".muted",
            style: { opacity: 0.18 },
          },
          {
            selector: ".highlighted",
            style: { "background-color": "#c56b3d", "line-color": "#c56b3d", opacity: 1 },
          },
        ]}
        cy={(cy) => {
          cy.removeListener("tap");
          cy.on("tap", "node", (event) => {
            const nodeId = event.target.id();
            setSelectedNode(nodeId);
            cy.elements().removeClass("muted highlighted");
            cy.elements().addClass("muted");
            event.target.removeClass("muted").addClass("highlighted");
            event.target.connectedEdges().removeClass("muted").addClass("highlighted");
            event.target.connectedEdges().connectedNodes().removeClass("muted").addClass("highlighted");
          });
          cy.on("tap", (event) => {
            if (event.target === cy) {
              setSelectedNode(null);
              cy.elements().removeClass("muted highlighted");
            }
          });
        }}
      />
      {selectedNode && <p className="px-4 pb-3 text-xs text-[#416058]">Entité sélectionnée : {selectedNode}</p>}
    </div>
  );
}
