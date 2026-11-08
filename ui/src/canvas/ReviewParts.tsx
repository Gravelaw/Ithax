/**
 * What the Canvas shows of an outside change (spec 3 "Canvas behaviour", External edits;
 * `docs/design/canvas-interactions.md` "Reviewing an outside change"; `design-system.md`
 * "Block states", "Icons"; wireframes `01-canvas.svg`, `01c-canvas-states.svg`): the
 * one-line notice naming the client, the top bar's "N changes to review", the chips of the
 * marks, and the "Changes to review" list with Accept and Reject, which is also the way to
 * review from the keyboard and with a screen reader.
 *
 * Accept and Reject are changes like any other: while a write awaits its answer they are
 * unavailable (`aria-disabled`, keeping the focus) and a click is refused with the wait
 * notice (the session refuses them too).
 */
import {
  ArrowCounterClockwiseIcon,
  CheckIcon,
  ListChecksIcon,
  PlusIcon,
  XIcon,
} from "@phosphor-icons/react";
import { createContext, useContext } from "react";
import type { Model } from "../api/types";
import { lock, useBusy } from "./busy";
import { shown } from "./model";
import { own } from "./own";
import {
  type Change,
  type ChangeKind,
  changeKind,
  changeSubject,
  describeChange,
  type FieldChange,
  fieldChanges,
  fieldName,
} from "./review";
import type { Outside } from "./session";

/** What the marks' buttons do; given by the screen, which knows the session. */
export interface ReviewActions {
  accept(key: string): void;
  reject(key: string): void;
  acceptAll(): void;
  rejectAll(): void;
  /** Read-only (a write gets no answer): the buttons are disabled. */
  readOnly: boolean;
}

const NONE: ReviewActions = {
  accept: () => undefined,
  reject: () => undefined,
  acceptAll: () => undefined,
  rejectAll: () => undefined,
  readOnly: true,
};

export const ReviewContext = createContext<ReviewActions>(NONE);

export function useReview(): ReviewActions {
  return useContext(ReviewContext);
}

const CLIENT_WORDS: Readonly<Record<string, string>> = {
  mcp: "by an assistant (mcp)",
  script: "by a script (script)",
  ui: "in another window (ui)",
};

/** "by an assistant (mcp)", joined with "and"; "by another program" when none is known. */
export function whoChanged(clients: readonly string[]): string {
  if (clients.length === 0) return "by another program";
  return clients
    .map((client) => own<string>(CLIENT_WORDS, client) ?? `by another program (${client})`)
    .join(" and ");
}

/** What the Canvas says it did after an outside change. */
export const CANVAS_RELOADED = "The canvas has been reloaded; undo history was cleared.";

/**
 * The one-line notice of an outside change (`canvas-interactions.md` "External edits");
 * `reloaded` says what the screen did (another screen than the Canvas names the model).
 */
export function outsideText(
  outside: Outside,
  clients: readonly string[],
  reloaded: string = CANVAS_RELOADED,
): string {
  const who = whoChanged(clients);
  return outside.conflict
    ? `Your last change was not saved because the model had just been changed ${who}. Please make it again.`
    : `The model was changed ${who}. ${reloaded}`;
}

export function OutsideNotice({
  outside,
  clients,
  reloaded,
  onDismiss,
}: {
  outside: Outside;
  clients: readonly string[];
  reloaded?: string;
  onDismiss: () => void;
}) {
  return (
    <p className="notice notice-outside">
      <span>{outsideText(outside, clients, reloaded)}</span>
      <button type="button" className="icon-button" aria-label="Dismiss" onClick={onDismiss}>
        <XIcon aria-hidden="true" size={14} />
      </button>
    </p>
  );
}

/** The top bar's "N changes to review", which opens the list. */
export function ReviewCount({ count, onOpen }: { count: number; onOpen: () => void }) {
  if (count === 0) return null;
  return (
    <button type="button" className="review-count" onClick={onOpen}>
      <ListChecksIcon aria-hidden="true" size={16} />
      {count} change{count === 1 ? "" : "s"} to review
    </button>
  );
}

const WORDS: Readonly<Record<ChangeKind, string>> = {
  added: "Added",
  changed: "Changed",
  removed: "Removed",
};

/** A mark's chip: an icon and its word, so it does not rely on colour. */
export function MarkChip({ kind, title }: { kind: ChangeKind; title?: string }) {
  const Glyph = kind === "added" ? PlusIcon : ListChecksIcon;
  return (
    <span className={`mark-chip mark-${kind}`} title={title}>
      <Glyph aria-hidden="true" size={12} />
      {WORDS[kind]}
    </span>
  );
}

/** Accept and Reject for one change. */
export function MarkButtons({ item, subject }: { item: Change; subject: string }) {
  const actions = useReview();
  const busy = useBusy();
  const stop = (event: { stopPropagation: () => void }) => event.stopPropagation();
  return (
    <span className="mark-buttons nodrag nopan">
      <button
        type="button"
        className="small-button"
        aria-label={`Accept the change to ${subject}`}
        {...lock(actions.readOnly, busy)}
        onPointerDown={stop}
        onClick={(event) => {
          stop(event);
          actions.accept(item.key);
        }}
      >
        <CheckIcon aria-hidden="true" size={14} />
        Accept
      </button>
      <button
        type="button"
        className="small-button"
        aria-label={`Reject the change to ${subject}`}
        {...lock(actions.readOnly, busy)}
        onPointerDown={stop}
        onClick={(event) => {
          stop(event);
          actions.reject(item.key);
        }}
      >
        <ArrowCounterClockwiseIcon aria-hidden="true" size={14} />
        Reject
      </button>
    </span>
  );
}

function valueText(value: unknown): string {
  return value === undefined ? "(none)" : shown(value);
}

/** A changed item's fields, the old value beside the new (`design-system.md` "Block states"). */
export function ChangedFields({ fields }: { fields: readonly FieldChange[] }) {
  return (
    <ul className="changed-fields">
      {fields.map((field) => (
        <li key={field.path}>
          <span className="mono">{fieldName(field.path)}</span>:{" "}
          <span className="old-value">{valueText(field.before)}</span> →{" "}
          <span className="new-value">{valueText(field.after)}</span>
        </li>
      ))}
    </ul>
  );
}

/** The changes of one marked block, for its side panel. */
export function BlockReview({ item, model }: { item: Change; model: Model }) {
  const kind = changeKind(item);
  const subject = changeSubject(item, model.domain);
  return (
    <section className="panel-section block-review" aria-labelledby="block-review-heading">
      <h2 className="subheading" id="block-review-heading">
        <MarkChip kind={kind} /> by another client
      </h2>
      {kind === "changed" ? <ChangedFields fields={fieldChanges(item.before, item.after)} /> : null}
      <MarkButtons item={item} subject={subject} />
    </section>
  );
}

/**
 * The "Changes to review" list: one row per mark with Accept and Reject, and Accept all and
 * Reject all. `onShow` selects a row's item where the screen can show it.
 */
export function ReviewList({
  marks,
  model,
  onShow,
  shows = (item) => changeKind(item) !== "removed",
}: {
  marks: readonly Change[];
  model: Model;
  onShow?: (item: Change) => void;
  /** Whether `onShow` can show a change; by default every change but a removal. */
  shows?: (item: Change) => boolean;
}) {
  const actions = useReview();
  const busy = useBusy();
  if (marks.length === 0) return null;
  return (
    <section className="panel-section review-list" aria-labelledby="review-heading">
      <h2 className="heading" id="review-heading" tabIndex={-1}>
        {marks.length} change{marks.length === 1 ? "" : "s"} to review
      </h2>
      <div className="review-all">
        <button
          type="button"
          className="secondary"
          {...lock(actions.readOnly, busy)}
          onClick={() => actions.acceptAll()}
        >
          <CheckIcon aria-hidden="true" size={14} />
          Accept all
        </button>
        <button
          type="button"
          className="secondary"
          {...lock(actions.readOnly, busy)}
          onClick={() => actions.rejectAll()}
        >
          <ArrowCounterClockwiseIcon aria-hidden="true" size={14} />
          Reject all
        </button>
      </div>
      <ul className="review-rows">
        {marks.map((item) => {
          const subject = changeSubject(item, model.domain);
          return (
            <li key={item.key} className={`review-row mark-row-${changeKind(item)}`}>
              {onShow && shows(item) ? (
                <button type="button" className="link review-text" onClick={() => onShow(item)}>
                  {describeChange(item, model.domain)}
                </button>
              ) : (
                <span className="review-text">{describeChange(item, model.domain)}</span>
              )}
              <MarkButtons item={item} subject={subject} />
            </li>
          );
        })}
      </ul>
    </section>
  );
}
