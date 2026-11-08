/**
 * A reference line: a server's `pool`, or a `schedule`'s or `failure`'s `target`
 * (`docs/design/design-system.md` "Line styles"). It is not a connection: drawn in the
 * resource colour with no arrowhead and a dot on the block it names, it differs by kind in
 * pattern (long dashes, dots, dash-dot), icon and word, and it cannot be selected; it
 * changes only when the setting changes in the side panel.
 */
import { CalendarDotsIcon, type Icon, UsersThreeIcon, WrenchIcon } from "@phosphor-icons/react";
import {
  BaseEdge,
  type Edge,
  EdgeLabelRenderer,
  type EdgeProps,
  getStraightPath,
  useInternalNode,
} from "@xyflow/react";
import { memo } from "react";
import type { ReferenceKind } from "./model";

export const REFERENCE_STYLE: Record<ReferenceKind, { dash: string; word: string; icon: Icon }> = {
  pool: { dash: "10 5", word: "staffs", icon: UsersThreeIcon },
  schedule: { dash: "1.5 4", word: "sets hours", icon: CalendarDotsIcon },
  failure: { dash: "8 4 2 4", word: "breaks down", icon: WrenchIcon },
};

export type ReferenceEdgeType = Edge<{ kind: ReferenceKind }, "reference">;

interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Where the line from one box's centre towards another's leaves the first box. */
export function borderPoint(from: Box, towards: Box): { x: number; y: number } {
  const cx = from.x + from.width / 2;
  const cy = from.y + from.height / 2;
  const dx = towards.x + towards.width / 2 - cx;
  const dy = towards.y + towards.height / 2 - cy;
  if (dx === 0 && dy === 0) return { x: cx, y: cy };
  const scale = Math.min(
    dx === 0 ? Number.POSITIVE_INFINITY : from.width / 2 / Math.abs(dx),
    dy === 0 ? Number.POSITIVE_INFINITY : from.height / 2 / Math.abs(dy),
  );
  return { x: cx + dx * scale, y: cy + dy * scale };
}

function boxOf(node: ReturnType<typeof useInternalNode>): Box | null {
  if (!node) return null;
  return {
    x: node.internals.positionAbsolute.x,
    y: node.internals.positionAbsolute.y,
    width: node.measured.width ?? 0,
    height: node.measured.height ?? 0,
  };
}

/** A reference line runs between the two blocks' borders, on the line joining their centres. */
function ReferenceEdgeView({ id, source, target, data }: EdgeProps<ReferenceEdgeType>) {
  const kind = data?.kind ?? "pool";
  const style = REFERENCE_STYLE[kind];
  const from = boxOf(useInternalNode(source));
  const to = boxOf(useInternalNode(target));
  if (from === null || to === null) return null;
  const start = borderPoint(from, to);
  const end = borderPoint(to, from);
  const [path, labelX, labelY] = getStraightPath({
    sourceX: start.x,
    sourceY: start.y,
    targetX: end.x,
    targetY: end.y,
  });
  const targetX = end.x;
  const targetY = end.y;
  const Glyph = style.icon;
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        className={`reference reference-${kind}`}
        style={{ strokeDasharray: style.dash }}
      />
      <circle cx={targetX} cy={targetY} r={3.5} className="reference-dot" />
      <EdgeLabelRenderer>
        <span
          className={`reference-chip small reference-chip-${kind}`}
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
        >
          <Glyph size={12} weight="regular" aria-hidden="true" />
          {style.word}
        </span>
      </EdgeLabelRenderer>
    </>
  );
}

export const ReferenceEdge = memo(ReferenceEdgeView);
