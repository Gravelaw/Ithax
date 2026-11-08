/**
 * The screens later M9 tickets build (Data and Experiment AKS-120, Run monitor, Results and
 * Settings AKS-138). Settings already holds About, which the first-start notice names.
 */

export const LATER = "This screen arrives in a later build.";

export function ScreenPlaceholder({ title }: { title: string }) {
  return (
    <section className="placeholder" aria-labelledby="screen-heading">
      <h1 id="screen-heading" className="title">
        {title}
      </h1>
      <p className="muted">{LATER}</p>
    </section>
  );
}

export function SettingsPlaceholder() {
  return (
    <section className="placeholder" aria-labelledby="screen-heading">
      <h1 id="screen-heading" className="title">
        Settings
      </h1>
      <p className="muted">{LATER}</p>
      <h2 className="heading" id="about-heading">
        About
      </h2>
      <p>
        Build a model of a process, run it many times, and see where the waits and bottlenecks are.
        Results are estimates from a simulation. Use them to support your judgement, not to replace
        it.
      </p>
      <p>
        This is free software under the GNU AGPL version 3.{" "}
        <a href="./LICENSE.txt">Read the licence</a>.{" "}
        <a href="./THIRD-PARTY-NOTICES.txt">Notices of the software it includes</a>.
      </p>
    </section>
  );
}
