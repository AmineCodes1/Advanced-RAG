declare module "react-cytoscapejs" {
  import type { CSSProperties, ReactNode } from "react";
  import type cytoscape from "cytoscape";

  type ElementDefinition = cytoscape.ElementDefinition;

  interface CytoscapeProps {
    elements: ElementDefinition[];
    style?: CSSProperties;
    layout?: cytoscape.LayoutOptions;
    stylesheet?: Array<{
      selector: string;
      style: Record<string, string | number>;
    }>;
    cy?: (instance: cytoscape.Core) => void;
    children?: ReactNode;
  }

  const CytoscapeComponent: (props: CytoscapeProps) => JSX.Element;
  export default CytoscapeComponent;
}
