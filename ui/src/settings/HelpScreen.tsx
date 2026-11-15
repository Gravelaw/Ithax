/**
 * Help (`#/help`, reached from Settings, About): "Open source licences" lists every package
 * and engine the product uses, with its licence and authors (issue 89; owner decisions B4,
 * C7 and F4). Nothing here is typed in: the service's list comes from the package's licence
 * list and the installed packages' metadata (`GET /v1/licences`), and the interface's from
 * its own build (`third-party.json`), so the page cannot drift from what is shipped.
 */
import { useEffect, useState } from "react";
import type { ApiClient, ApiResult } from "../api/client";
import type { LicencedPart, Licences } from "../api/types";
import { ServiceProblem } from "../components/ServiceProblem";
import "../results/results.css";

/** Said where the desktop shell's crates are listed when this service has none to list. */
export const CRATES_ELSEWHERE =
  "The desktop shell's Rust crates are listed in THIRD-PARTY-LICENSES.txt, in the folder the package was unpacked to.";

function PartsTable({
  caption,
  first,
  parts,
}: {
  caption: string;
  first: string;
  parts: readonly LicencedPart[];
}) {
  const withAuthors = parts.some((part) => part.authors !== undefined);
  return (
    <table className="data-table">
      <caption className="visually-hidden">{caption}</caption>
      <thead>
        <tr>
          <th scope="col">{first}</th>
          <th scope="col">Version</th>
          <th scope="col">Licence</th>
          {withAuthors ? <th scope="col">Authors</th> : null}
        </tr>
      </thead>
      <tbody>
        {parts.map((part) => (
          <tr key={`${part.name} ${part.version ?? ""}`}>
            <th scope="row" className="mono">
              {part.name}
            </th>
            <td>{part.version ?? "not given"}</td>
            <td>{part.licence}</td>
            {withAuthors ? <td>{part.authors ?? "not given"}</td> : null}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ServiceParts({ licences }: { licences: Licences }) {
  const { product, python } = licences;
  return (
    <>
      <p>
        {product.name} {product.version} is free software under {product.licence}.{" "}
        <a href="./LICENSE.txt">Read the licence</a>. Its source:{" "}
        <a href={product.source}>{product.source}</a>.
      </p>
      <h3 className="heading">Engines</h3>
      <PartsTable caption="Engines" first="Engine" parts={licences.engines} />
      <h3 className="heading">Python</h3>
      <PartsTable caption="Python" first="Python" parts={[python]} />
      {python.bundled.length > 0 ? (
        <PartsTable caption="Libraries built into Python" first="Library" parts={python.bundled} />
      ) : null}
      <h3 className="heading">Python packages</h3>
      <PartsTable caption="Python packages" first="Package" parts={licences.packages} />
      <h3 className="heading">Desktop shell</h3>
      {licences.crates.length > 0 ? (
        <PartsTable caption="Desktop shell crates" first="Crate" parts={licences.crates} />
      ) : (
        <p>{CRATES_ELSEWHERE}</p>
      )}
    </>
  );
}

export function HelpScreen({ client }: { client: ApiClient }) {
  const [licences, setLicences] = useState<ApiResult<Licences> | null>(null);
  const [interfaceParts, setInterfaceParts] = useState<ApiResult<LicencedPart[]> | null>(null);

  useEffect(() => {
    let open = true;
    void client.getLicences().then((result) => {
      if (open) setLicences(result);
    });
    void client.getInterfacePackages().then((result) => {
      if (open) setInterfaceParts(result);
    });
    return () => {
      open = false;
    };
  }, [client]);

  return (
    <section className="settings-screen" aria-labelledby="screen-heading">
      <h1 id="screen-heading" className="title">
        Help
      </h1>
      <div className="settings-section">
        <h2 className="heading">Open source licences</h2>
        <p>
          Every package and engine this product uses, with its licence and authors. The licence
          texts: <a href="./THIRD-PARTY-NOTICES.txt">notices of the interface's packages</a>, and
          THIRD-PARTY-LICENSES.txt in the folder the package was unpacked to.
        </p>
        <ServiceProblem result={licences} />
        {licences?.kind === "ok" ? <ServiceParts licences={licences.data} /> : null}
        <h3 className="heading">Interface packages</h3>
        <ServiceProblem result={interfaceParts} />
        {interfaceParts?.kind === "ok" ? (
          <PartsTable caption="Interface packages" first="Package" parts={interfaceParts.data} />
        ) : null}
      </div>
    </section>
  );
}
