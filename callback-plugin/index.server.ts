import type { PluginServerContext } from "@getpaseo/plugin/server";
import { startRelay } from "./server/relay.ts";

export default function contribute(server: PluginServerContext) {
  return startRelay(server);
}
