/**
 * A block: one model component (`docs/design/design-system.md` "Block styles", "Block
 * states", "Port styles"). Its shape says its category (capsule, rounded box, tag), an icon
 * disc and a title say what it is, badges count its issues (a round badge for errors, a
 * triangle for warnings), and its ports are the type's (a branch's routes on the right).
 */
import {
  ArrowsSplitIcon,
  BoxArrowDownIcon,
  BoxArrowUpIcon,
  CalendarDotsIcon,
  CubeIcon,
  type Icon,
  RowsIcon,
  SignInIcon,
  SignOutIcon,
  TimerIcon,
  UserGearIcon,
  UsersThreeIcon,
  WarehouseIcon,
  WrenchIcon,
} from "@phosphor-icons/react";
import { Handle, type Node, type NodeProps, Position } from "@xyflow/react";
import { memo } from "react";
import type { Component } from "../api/types";
import { type Category, shown, typeLine } from "./model";

export const ICONS: Record<string, Icon> = {
  source: SignInIcon,
  sink: SignOutIcon,
  delay: TimerIcon,
  branch: ArrowsSplitIcon,
  server: UserGearIcon,
  queue: RowsIcon,
  batch: BoxArrowDownIcon,
  unbatch: BoxArrowUpIcon,
  store: WarehouseIcon,
  resource_pool: UsersThreeIcon,
  schedule: CalendarDotsIcon,
  failure: WrenchIcon,
};

export function iconOf(type: string): Icon {
  return ICONS[type] ?? CubeIcon;
}

export interface BlockData extends Record<string, unknown> {
  component: Component;
  category: Category;
  inputs: string[];
  outputs: string[];
  /** For each port, the end it is connected to, for its title. */
  connected: Record<string, string[]>;
  errors: number;
  warnings: number;
  /** The messages of its issues, for the badge's title. */
  messages: string;
}

export type BlockNodeType = Node<BlockData, "block">;

/** "till, server, capacity 1, 1 error" (`docs/design/accessibility.md` "Screen readers"). */
export function blockName(data: BlockData): string {
  const parts = [data.component.label ?? data.component.id, typeLine(data.component)];
  if (data.component.label) parts.splice(1, 0, data.component.id);
  if (data.errors) parts.push(`${data.errors} error${data.errors === 1 ? "" : "s"}`);
  if (data.warnings) parts.push(`${data.warnings} warning${data.warnings === 1 ? "" : "s"}`);
  return parts.join(", ").replace(" · ", ", ");
}

function portTop(index: number, count: number): string {
  return `${((index + 1) / (count + 1)) * 100}%`;
}

function Badge({ data }: { data: BlockData }) {
  if (data.errors > 0) {
    return (
      <span className="badge badge-error" title={data.messages}>
        <span className="badge-count">{data.errors}</span>
        <span className="badge-mark" aria-hidden="true">
          !
        </span>
      </span>
    );
  }
  if (data.warnings > 0) {
    return (
      <span className="badge badge-warning" title={data.messages}>
        <span className="badge-count">{data.warnings}</span>
        <span className="badge-mark badge-triangle" aria-hidden="true">
          !
        </span>
      </span>
    );
  }
  return null;
}

function ResourceMark({ component }: { component: Component }) {
  if (component.type === "resource_pool") {
    const capacity = component.params.capacity;
    return capacity === undefined ? null : (
      <span className="resource-count small">{shown(capacity)}</span>
    );
  }
  if (component.type === "schedule") return <span className="resource-strip" aria-hidden="true" />;
  if (component.type === "failure") return <span className="resource-stripes" aria-hidden="true" />;
  return null;
}

function BlockNodeView({ data, selected, isConnectable }: NodeProps<BlockNodeType>) {
  const { component, category } = data;
  const Glyph = iconOf(component.type);
  const routes = component.type === "branch";
  return (
    <div
      className={`block block-${category}${data.errors > 0 ? " block-error" : ""}${
        selected ? " block-selected" : ""
      }`}
      style={
        routes && data.outputs.length > 2
          ? { minHeight: `${4 + (data.outputs.length - 2) * 1.25}rem` }
          : undefined
      }
    >
      {data.inputs.map((port, index) => (
        <Handle
          key={`in-${port}`}
          id={port}
          type="target"
          position={Position.Left}
          isConnectable={isConnectable}
          className={`port${(data.connected[port]?.length ?? 0) > 0 ? " port-connected" : ""}`}
          style={{ top: portTop(index, data.inputs.length) }}
          title={`Input port ${port} of ${component.id}`}
        />
      ))}
      <span className="block-disc" aria-hidden="true">
        <Glyph size={20} weight="duotone" />
      </span>
      <span className="block-text">
        <span className="block-title">{component.label ?? component.id}</span>
        <span className="block-type small">
          {component.label ? <span className="mono">{component.id} · </span> : null}
          {typeLine(component)}
        </span>
      </span>
      <ResourceMark component={component} />
      <Badge data={data} />
      {data.outputs.map((port, index) => (
        <Handle
          key={`out-${port}`}
          id={port}
          type="source"
          position={Position.Right}
          isConnectable={isConnectable}
          className={`port${(data.connected[port]?.length ?? 0) > 0 ? " port-connected" : ""}`}
          style={{ top: portTop(index, data.outputs.length) }}
          title={`Output port ${port} of ${component.id}${
            data.connected[port]?.length ? `, connected to ${data.connected[port]?.join(", ")}` : ""
          }`}
        >
          {routes ? <span className="port-label mono">{port}</span> : null}
        </Handle>
      ))}
      {/* Where reference lines meet the block; never a port. */}
      <Handle
        id="ref-out"
        type="source"
        position={Position.Bottom}
        className="ref-handle"
        isConnectable={false}
      />
      <Handle
        id="ref-in"
        type="target"
        position={Position.Top}
        className="ref-handle"
        isConnectable={false}
      />
    </div>
  );
}

export const BlockNode = memo(BlockNodeView);
