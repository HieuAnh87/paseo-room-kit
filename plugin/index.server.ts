import type { PluginServerContext } from "@getpaseo/plugin/server";
import { snapshot } from "./server/snapshot.ts";
import { snapshotRpc } from "./shared/snapshot.ts";

export default function contribute(server: PluginServerContext) {
  server.handle(snapshotRpc, async (_input, { paseo }) => snapshot(paseo));
  return () => {};
}
