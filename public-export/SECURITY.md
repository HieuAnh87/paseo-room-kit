# Public artifact security

Treat an export as publishable only after its manifest and scanner pass.
The export boundary is an explicit allowlist, not a directory copy: only the
files named by the exporter are eligible, and the output must be a new or
empty directory outside the source checkout.

Keep these outside a public artifact:

- provider authentication and credential stores;
- API keys, bearer values, cookies, passwords, and database connection strings;
- machine-specific home paths and runtime identity values;
- project records, transcripts, operational logs, and other local records;
- private source notes or organization-specific names.

The scanner rejects private-name fixtures, personal Unix and Windows home
paths, UUID and runtime-identity shapes, non-synthetic corporate email
addresses, credential/token/private-key shapes, database URIs, and private
network/internal endpoints, VCS metadata, and private operational audit/catalog
metadata. It also verifies that the generated manifest exactly matches the
reviewed allowlist. It permits clearly synthetic placeholders such as
`<TOKEN>`, `test@example.com`, `$HOME`, and the all-zero UUID so generic
examples remain usable.

HTTP(S) links are not credentials by themselves. The scanner narrowly allows
ordinary public links, including localhost health examples, Paseo links, and
upstream links; it still rejects URL user-info and sensitive query values.

The explicitly allowlisted blank `templates/SUPERVISOR_NOTEBOOK.md` is a
template, not populated operational history. References to that template are
allowed; populated records and private audit/inventory material are not.

Never add a real secret to a fixture to test the scanner. Use a representative
shape that cannot authenticate, then remove the fixture before export.
