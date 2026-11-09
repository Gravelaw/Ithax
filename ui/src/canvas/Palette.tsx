/**
 * The palette (`docs/design/canvas-interactions.md` "Adding a block"): the block types the
 * installed adapters provide (`GET /v1/schema`), in the three groups of the design system,
 * with a filter box. A type is added by dragging it onto the canvas; by clicking it and then
 * the canvas (Escape cancels); or from the keyboard with Enter, at the centre of the view.
 */
import type { DragEvent } from "react";
import { useState } from "react";
import type { ComponentType } from "../api/types";
import { iconOf } from "./BlockNode";
import { lock, useBusy } from "./busy";
import { categoryOf, GROUPS } from "./model";
import { own } from "./own";

export const BLOCK_MIME = "application/x-lcsim-block";

export function Palette({
  types,
  placing,
  readOnly,
  onPlace,
  onAdd,
}: {
  types: Record<string, ComponentType>;
  placing: string | null;
  readOnly: boolean;
  /** Click: start (or stop) placing this type with the next click on the canvas. */
  onPlace: (type: string | null) => void;
  /** Enter: add this type at once. */
  onAdd: (type: string) => void;
}) {
  const busy = useBusy();
  const [filter, setFilter] = useState("");
  const wanted = filter.trim().toLowerCase();
  const known = Object.keys(types).filter(
    (type) => own<{ domain: string }>(types, type)?.domain === "process",
  );
  const groups = [
    ...GROUPS.map((group) => ({
      ...group,
      types: group.types.filter((type) => known.includes(type)),
    })),
    {
      category: "other",
      label: "Other",
      types: known.filter((type) => categoryOf(type) === "other"),
    },
  ]
    .map((group) => ({
      ...group,
      types: group.types.filter((type) => wanted === "" || type.includes(wanted)),
    }))
    .filter((group) => group.types.length > 0);

  const start = (event: DragEvent<HTMLButtonElement>, type: string) => {
    event.dataTransfer.setData(BLOCK_MIME, type);
    event.dataTransfer.effectAllowed = "copy";
  };

  return (
    <aside
      className="palette"
      data-region="palette"
      aria-labelledby="palette-heading"
      tabIndex={-1}
    >
      <h2 className="heading" id="palette-heading">
        Blocks
      </h2>
      <label className="visually-hidden" htmlFor="palette-filter">
        Filter blocks
      </label>
      <input
        id="palette-filter"
        className="palette-filter"
        type="search"
        placeholder="Filter blocks"
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
      />
      {placing !== null ? (
        <p className="hint" role="status">
          Click the canvas to place {placing}. Escape cancels.
        </p>
      ) : null}
      {groups.map((group) => (
        <section key={group.category} aria-labelledby={`palette-${group.category}`}>
          <h3 className="palette-group small" id={`palette-${group.category}`}>
            {group.label}
          </h3>
          <ul className="palette-list">
            {group.types.map((type) => {
              const Glyph = iconOf(type);
              return (
                <li key={type}>
                  <button
                    type="button"
                    className={`palette-item cat-${categoryOf(type)}`}
                    draggable={!readOnly && !busy}
                    {...lock(readOnly, busy)}
                    aria-pressed={placing === type}
                    title={own<{ description: string }>(types, type)?.description}
                    onDragStart={(event) => start(event, type)}
                    onClick={() => onPlace(placing === type ? null : type)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        onAdd(type);
                      }
                    }}
                  >
                    <span className="palette-disc" aria-hidden="true">
                      <Glyph size={16} weight="duotone" />
                    </span>
                    <span className="mono">{type}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </aside>
  );
}
